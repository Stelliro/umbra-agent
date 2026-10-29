"""
Escape test: run INSIDE the sandbox (./run_umbra.sh escape-test).
Tries to reach things UMBRA must not reach. Every line should say BLOCKED / OK.
"""
import os, socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path("/home") / ROOT.parts[2] if len(ROOT.parts) > 2 else Path("/home")
results = []


def check(name, fn, expect_blocked=True):
    try:
        detail = fn()
        ok = not expect_blocked
        results.append((ok, name, f"reached: {str(detail)[:60]}" if expect_blocked else f"{str(detail)[:60]}"))
    except Exception as e:
        ok = expect_blocked
        results.append((ok, name, f"{type(e).__name__}"))


def connect(host, port):
    s = socket.create_connection((host, port), timeout=3)
    s.close()
    return f"connected to {host}:{port}"


check("read login file", lambda: (HOME / ".config/umbra/login.json").read_text())
def home_contents():
    # bwrap creates empty path folders leading to the project and model; anything else is a leak
    skeleton = {ROOT.parts[3], ".local"} if len(ROOT.parts) > 3 else set()
    extra = [e for e in os.listdir(HOME) if e not in skeleton]
    if not extra:
        raise PermissionError("only empty path folders")
    return extra


check("home folder contents", home_contents)
check("read ~/.ssh", lambda: os.listdir(HOME / ".ssh"))
def other_projects():
    others = [e for e in os.listdir(ROOT.parent) if e != ROOT.name]
    if not others:
        raise PermissionError("no other projects visible")
    return others


check("see other projects", other_projects)
check("credential file has content", lambda: (ROOT / "data/credentials.json").read_text() or (_ for _ in ()).throw(ValueError("empty")))
check("write own code (core/)", lambda: (ROOT / "core/_escape_probe.py").write_text("x"))
check("read git history", lambda: os.listdir(ROOT / ".git") or (_ for _ in ()).throw(ValueError("empty")))
check("internet (1.1.1.1:443)", lambda: connect("1.1.1.1", 443))
check("LAN router (192.168.1.1:80)", lambda: connect("192.168.1.1", 80))
check("DNS lookup", lambda: socket.gethostbyname("github.com"))
check("host's localhost:5000", lambda: connect("127.0.0.1", 5000))
check("see host processes", lambda: [p for p in os.listdir("/proc") if p.isdigit() and int(p) > 50] or (_ for _ in ()).throw(ValueError("none")))


def fetch_off_allowlist():
    import json
    sock = ROOT / "data/run/fetch.sock"
    if not sock.exists():
        raise PermissionError("fetcher not running (nothing to reach)")
    c = socket.socket(socket.AF_UNIX)
    c.connect(str(sock))
    c.sendall(b'{"op": "fetch", "url": "https://example.com/"}\n')
    r = json.loads(c.makefile().readline())
    if not r.get("ok"):
        raise PermissionError(r.get("error"))
    return "fetched a site that is not allowlisted"


def write_wikipedia():
    zims = sorted(Path(os.environ.get("UMBRA_ZIM_DIR", "/nonexistent")).glob("*.zim"))
    if not zims:
        raise FileNotFoundError("no offline Wikipedia mounted")
    with open(zims[0], "r+b") as f:
        f.write(b"")
    return "opened offline Wikipedia for writing"


check("fetch non-allowlisted site", fetch_off_allowlist)
check("write offline Wikipedia", write_wikipedia)


def write_data():
    p = ROOT / "data/_escape_probe.txt"
    p.write_text("ok")
    p.unlink()
    return "writable"


check("write data/ (allowed)", write_data, expect_blocked=False)


def gpu():
    import llama_cpp
    if not llama_cpp.llama_supports_gpu_offload():
        raise RuntimeError("no GPU offload")
    return "GPU offload available"


check("use GPU (allowed)", gpu, expect_blocked=False)

width = max(len(n) for _, n, _ in results)
for ok, name, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
print(f"\n{sum(ok for ok, _, _ in results)}/{len(results)} passed")
