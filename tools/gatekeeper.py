#!/usr/bin/env python3
"""
Gatekeeper — the only door into the sandboxed UMBRA web app.

Runs OUTSIDE the sandbox (standard library only). Listens on 127.0.0.1:5000,
asks the browser for the login (HTTP Basic), checks it against
~/.config/umbra/login.json, and forwards allowed requests to the web app's
unix socket inside the sandbox. The sandbox never sees the login file and has
no network of its own; this socket is its only line to the outside.

Usage (run_umbra.sh starts it for you):
    python3 tools/gatekeeper.py /path/to/data/run/umbra.sock
"""
import base64, http.client, json, os, secrets, socket, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOGIN_FILE = Path.home() / ".config" / "umbra" / "login.json"
LISTEN = ("127.0.0.1", 5000)
HOP_HEADERS = {"connection", "keep-alive", "proxy-authorization", "authorization", "te",
               "trailers", "transfer-encoding", "upgrade", "host"}


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout=300):
        super().__init__("localhost", timeout=timeout)
        self.unix_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.unix_path)


def load_login():
    try:
        creds = json.loads(LOGIN_FILE.read_text())
        if creds.get("username") and creds.get("password"):
            return creds
    except Exception:
        pass
    return None


class Gate(BaseHTTPRequestHandler):
    sock_path = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet; UMBRA logs its own activity

    def _authorized(self) -> bool:
        creds = load_login()  # re-read each time, so a password change applies at once
        header = self.headers.get("Authorization", "")
        if not creds or not header.startswith("Basic "):
            return False
        try:
            user, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
        except Exception:
            return False
        return secrets.compare_digest(user, creds["username"]) and secrets.compare_digest(pw, creds["password"])

    def _handle(self):
        if not self._authorized():
            body = b"Login required"
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="UMBRA", charset="UTF-8"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
        try:
            conn = UnixHTTPConnection(self.sock_path)
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
        except (FileNotFoundError, ConnectionRefusedError):
            data = b"UMBRA is not running (no socket). Start it with run_umbra.sh web."
            self.send_response(503)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(resp.status, resp.reason)
        for k, v in resp.getheaders():
            if k.lower() not in HOP_HEADERS and k.lower() != "content-length":
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        conn.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _handle

    def do_HEAD(self):
        self._handle()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if not load_login():
        sys.exit(f"[GATE] No usable login at {LOGIN_FILE}. Create it with: "
                 '{"username": "...", "password": "..."}')
    Gate.sock_path = sys.argv[1]
    server = ThreadingHTTPServer(LISTEN, Gate)
    print(f"[GATE] http://localhost:{LISTEN[1]}  (login from {LOGIN_FILE})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
