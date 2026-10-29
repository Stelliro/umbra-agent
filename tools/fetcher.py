#!/usr/bin/env python3
"""
Fetcher: UMBRA's only window to the web. Runs OUTSIDE the sandbox (stdlib only).

UMBRA has no network. It sends a request over the unix socket data/run/fetch.sock
and this process decides whether to fetch:

  - https only, GET only, no cookies, no logins, no forms
  - host must be on the allowlist in ~/.config/umbra/fetch_allowlist.txt
    (one domain per line; subdomains included; UMBRA cannot see or edit this file)
  - redirects are followed only to allowlisted hosts
  - at most MAX_BYTES per page, FETCHES_PER_HOUR per hour
  - HTML is reduced to plain text (no scripts, styles, forms)
  - every request, allowed or refused, is logged to ~/.local/state/umbra/fetch_log.jsonl (outside the sandbox)
  - Wikipedia article links are fetched as the article's plain text (no menus)

Request (one JSON line):  {"op": "fetch", "url": "https://..."}
                          {"op": "wiki_search", "query": "...", "lang": "simple"}
Reply   (one JSON line):  {"ok": true, "url": ..., "title": ..., "text": ...} or {"ok": false, "error": ...}

Usage (run_umbra.sh starts it):  python3 tools/fetcher.py /path/to/data/run/fetch.sock
"""
import json, os, re, socket, socketserver, sys, threading, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = Path.home() / ".config" / "umbra" / "fetch_allowlist.txt"
LOG = Path.home() / ".local" / "state" / "umbra" / "fetch_log.jsonl"  # outside the sandbox: UMBRA cannot edit it
MAX_BYTES = 600_000
MAX_TEXT = 60_000
FETCHES_PER_HOUR = 40
TIMEOUT = 15
USER_AGENT = "UMBRA-research-fetcher/1.0 (local, read-only; personal research)"
DEFAULT_ALLOW = ["wikipedia.org", "wikimedia.org", "arxiv.org", "docs.python.org"]

_recent = []
_lock = threading.Lock()


def allowlist():
    if not ALLOWLIST.exists():
        ALLOWLIST.parent.mkdir(parents=True, exist_ok=True)
        ALLOWLIST.write_text("# One domain per line. Subdomains are included.\n" + "\n".join(DEFAULT_ALLOW) + "\n")
    return [l.strip().lower() for l in ALLOWLIST.read_text().splitlines() if l.strip() and not l.startswith("#")]


def host_allowed(host):
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in allowlist())


def log(entry):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": datetime.now().isoformat(), **entry}, ensure_ascii=False) + "\n")


class TextOnly(HTMLParser):
    """Visible text of a page; drops scripts, styles, nav, forms and similar."""
    SKIP = {"script", "style", "noscript", "nav", "footer", "form", "svg", "iframe", "button", "select", "template"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "pre", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)

    def text(self):
        t = re.sub(r"[ \t\r\f\v]+", " ", "".join(self.out))
        return re.sub(r"\n\s*\n+", "\n\n", t).strip()


class AllowlistRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlparse(newurl)
        if u.scheme != "https" or not host_allowed(u.hostname):
            raise urllib.error.HTTPError(newurl, code, "redirect to a host not on the allowlist", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(AllowlistRedirects())  # no cookie handler: no cookies kept


def rate_ok():
    now = time.time()
    with _lock:
        _recent[:] = [t for t in _recent if now - t < 3600]
        if len(_recent) >= FETCHES_PER_HOUR:
            return False
        _recent.append(now)
        return True


def fetch(url):
    u = urllib.parse.urlparse(url or "")
    if u.scheme != "https":
        return {"ok": False, "error": "only https URLs"}
    if not host_allowed(u.hostname):
        return {"ok": False, "error": f"{u.hostname} is not on the allowlist"}
    if not rate_ok():
        return {"ok": False, "error": f"limit reached ({FETCHES_PER_HOUR} fetches per hour)"}
    m = re.match(r"^/wiki/([^?#]+)", u.path or "")
    if m and (u.hostname or "").endswith("wikipedia.org"):
        return wiki_article(u.hostname, urllib.parse.unquote(m.group(1)), url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/json"})
    try:
        with OPENER.open(req, timeout=TIMEOUT) as r:
            ctype = r.headers.get("Content-Type", "")
            raw = r.read(MAX_BYTES + 1)
            final = r.geturl()
    except Exception as e:
        return {"ok": False, "error": f"fetch failed: {e}"}
    truncated = len(raw) > MAX_BYTES
    body = raw[:MAX_BYTES].decode("utf-8", errors="replace")
    if "html" in ctype:
        p = TextOnly()
        p.feed(body)
        title, text = p.title.strip(), p.text()
    elif "json" in ctype or "text" in ctype:
        title, text = "", body
    else:
        return {"ok": False, "error": f"not a text page ({ctype})"}
    return {"ok": True, "url": final, "title": title, "text": text[:MAX_TEXT], "truncated": truncated or len(text) > MAX_TEXT}


def wiki_article(host, title, original_url):
    """A Wikipedia article as plain text via the MediaWiki extracts API (no menus or page chrome)."""
    q = urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
                                "format": "json", "titles": title[:300]})
    req = urllib.request.Request(f"https://{host}/w/api.php?{q}", headers={"User-Agent": USER_AGENT})
    try:
        with OPENER.open(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read(MAX_BYTES).decode("utf-8", errors="replace"))
        page = next(iter(data["query"]["pages"].values()))
    except Exception as e:
        return {"ok": False, "error": f"fetch failed: {e}"}
    if "missing" in page:
        return {"ok": False, "error": f"no article called {title!r}"}
    text = page.get("extract", "")
    return {"ok": True, "url": original_url, "title": page.get("title", title), "text": text[:MAX_TEXT],
            "truncated": len(text) > MAX_TEXT}


def wiki_search(query, lang="simple"):
    """Titles matching a query, via Wikipedia's own search API (still subject to the allowlist and limit)."""
    if lang not in ("simple", "en"):
        lang = "simple"
    q = urllib.parse.urlencode({"action": "opensearch", "search": query[:200], "limit": 8, "namespace": 0, "format": "json"})
    r = fetch(f"https://{lang}.wikipedia.org/w/api.php?{q}")
    if not r["ok"]:
        return r
    try:
        _, titles, _, links = json.loads(r["text"])
    except Exception:
        return {"ok": False, "error": "search returned something unexpected"}
    return {"ok": True, "results": [{"title": t, "url": l} for t, l in zip(titles, links)]}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            req = json.loads(self.rfile.readline(10_000).decode("utf-8"))
        except Exception:
            return
        op = req.get("op")
        if op == "fetch":
            res = fetch(req.get("url", ""))
        elif op == "wiki_search":
            res = wiki_search(req.get("query", ""), req.get("lang", "simple"))
        else:
            res = {"ok": False, "error": "unknown op"}
        log({"op": op, "url": req.get("url"), "query": req.get("query"), "ok": res.get("ok"),
             "error": res.get("error"), "chars": len(res.get("text", "")) if res.get("ok") else 0})
        self.wfile.write((json.dumps(res, ensure_ascii=False) + "\n").encode("utf-8"))


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    if os.path.exists(path):
        os.unlink(path)
    os.umask(0o077)
    allowlist()  # create the default file if missing
    with Server(path, Handler) as srv:
        print(f"[FETCH] serving {path}; allowlist {ALLOWLIST}: {', '.join(allowlist())}")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
