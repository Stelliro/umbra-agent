"""
UMBRA Tunnel v1.0 — Public Access via Cloudflare Tunnel
=========================================================
Exposes localhost:5000 to the internet using cloudflared (free, no signup).

Usage:
    from tunnel import Tunnel
    t = Tunnel(port=5000)
    t.start()          # Downloads cloudflared if needed, starts tunnel
    print(t.url)       # https://random-words.trycloudflare.com
    t.stop()

The URL changes each restart (free tier). For a fixed URL,
set up a Cloudflare account + named tunnel.
"""
import subprocess, threading, time, re, os, sys, logging, platform, shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger("UMBRA-TUNNEL")

# Where to store the cloudflared binary
_BIN_DIR = Path(__file__).parent.parent / "bin"
_IS_WINDOWS = platform.system() == "Windows"
_CLOUDFLARED_NAME = "cloudflared.exe" if _IS_WINDOWS else "cloudflared"


def _find_cloudflared() -> Optional[str]:
    """Find cloudflared binary — check PATH first, then bin/ folder."""
    # Check PATH
    found = shutil.which("cloudflared")
    if found:
        return found
    # Check local bin/
    local = _BIN_DIR / _CLOUDFLARED_NAME
    if local.exists():
        return str(local)
    return None


def download_cloudflared(dest_dir: Path = None) -> str:
    """
    Download cloudflared binary. Returns path to binary.
    Windows: downloads .exe from GitHub releases.
    Linux/Mac: downloads from GitHub releases.
    """
    import urllib.request

    dest_dir = dest_dir or _BIN_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _CLOUDFLARED_NAME

    if dest.exists():
        return str(dest)

    system = platform.system().lower()
    arch = platform.machine().lower()

    # Map to cloudflared release names
    if system == "windows":
        if "64" in arch or "amd64" in arch:
            asset = "cloudflared-windows-amd64.exe"
        else:
            asset = "cloudflared-windows-386.exe"
    elif system == "darwin":
        if "arm" in arch or "aarch" in arch:
            asset = "cloudflared-darwin-amd64.tgz"  # Universal binary
        else:
            asset = "cloudflared-darwin-amd64.tgz"
    else:  # Linux
        if "arm" in arch or "aarch" in arch:
            asset = "cloudflared-linux-arm64"
        else:
            asset = "cloudflared-linux-amd64"

    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset}"

    logger.info(f"📥 Downloading cloudflared from {url}...")
    print(f"[TUNNEL] Downloading cloudflared ({asset})...")

    try:
        urllib.request.urlretrieve(url, str(dest))
        # Make executable on Unix
        if not _IS_WINDOWS:
            os.chmod(str(dest), 0o755)
        logger.info(f"✅ cloudflared saved to {dest}")
        print(f"[TUNNEL] Saved to {dest}")
        return str(dest)
    except Exception as e:
        logger.error(f"Failed to download cloudflared: {e}")
        print(f"[TUNNEL] Download failed: {e}")
        print(f"[TUNNEL] Manual install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
        raise


class Tunnel:
    """
    Manages a cloudflared tunnel to expose localhost publicly.
    """

    def __init__(self, port: int = 5000, auto_download: bool = True):
        self.port = port
        self.auto_download = auto_download
        self.url: Optional[str] = None
        self._process: Optional[subprocess.Popen] = None
        self._monitor: Optional[threading.Thread] = None
        self._running = False
        self._binary: Optional[str] = None

    def start(self) -> Optional[str]:
        """
        Start the tunnel. Returns public URL or None on failure.
        Downloads cloudflared automatically if not found.
        """
        if self._running:
            return self.url

        # Find or download cloudflared
        self._binary = _find_cloudflared()
        if not self._binary:
            if self.auto_download:
                try:
                    self._binary = download_cloudflared()
                except Exception:
                    return None
            else:
                logger.error("cloudflared not found. Install from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
                return None

        # Start cloudflared tunnel
        cmd = [self._binary, "tunnel", "--url", f"http://localhost:{self.port}"]
        logger.info(f"🚇 Starting tunnel: {' '.join(cmd)}")
        print(f"[TUNNEL] Starting cloudflared tunnel to localhost:{self.port}...")

        try:
            # cloudflared outputs the URL to stderr
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self._running = True

            # Monitor stderr for the URL (arrives within ~5 seconds)
            self.url = self._wait_for_url(timeout=30)

            if self.url:
                logger.info(f"🌐 Tunnel live: {self.url}")
                print(f"[TUNNEL] ✅ PUBLIC URL: {self.url}")

                # Start background monitor to log tunnel status
                self._monitor = threading.Thread(target=self._monitor_loop, daemon=True)
                self._monitor.start()
            else:
                logger.warning("Tunnel started but no URL detected")
                print("[TUNNEL] ⚠ Started but couldn't detect URL. Check cloudflared output.")

            return self.url

        except FileNotFoundError:
            logger.error(f"cloudflared binary not found at: {self._binary}")
            print(f"[TUNNEL] ✗ Binary not found: {self._binary}")
            return None
        except Exception as e:
            logger.error(f"Tunnel start failed: {e}")
            print(f"[TUNNEL] ✗ Start failed: {e}")
            return None

    def _wait_for_url(self, timeout: float = 30) -> Optional[str]:
        """Read stderr until we find the tunnel URL."""
        url_pattern = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")
        deadline = time.time() + timeout

        while time.time() < deadline:
            if self._process.poll() is not None:
                # Process died
                remaining = self._process.stderr.read()
                logger.error(f"cloudflared exited early: {remaining[:500]}")
                return None

            line = self._process.stderr.readline()
            if not line:
                time.sleep(0.1)
                continue

            line = line.strip()
            if line:
                logger.debug(f"[cloudflared] {line}")

            match = url_pattern.search(line)
            if match:
                return match.group(0)

        return None

    def _monitor_loop(self):
        """Background: read remaining stderr output for logging."""
        while self._running and self._process and self._process.poll() is None:
            try:
                line = self._process.stderr.readline()
                if line:
                    stripped = line.strip()
                    if stripped and "ERR" in stripped:
                        logger.warning(f"[cloudflared] {stripped}")
            except:
                break
            time.sleep(0.1)

        if self._running:
            logger.warning("🚇 Tunnel process ended unexpectedly")
            self._running = False

    def stop(self):
        """Stop the tunnel."""
        self._running = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except:
                try:
                    self._process.kill()
                except:
                    pass
            self._process = None
        self.url = None
        logger.info("🚇 Tunnel stopped")
        print("[TUNNEL] Stopped")

    def status(self) -> dict:
        return {
            "running": self._running,
            "url": self.url,
            "port": self.port,
            "binary": self._binary,
            "pid": self._process.pid if self._process else None,
        }

    def __del__(self):
        self.stop()


# === Convenience ===

_tunnel = None

def start_tunnel(port: int = 5000) -> Optional[str]:
    """One-call start. Returns public URL."""
    global _tunnel
    if _tunnel and _tunnel._running:
        return _tunnel.url
    _tunnel = Tunnel(port=port)
    return _tunnel.start()

def get_tunnel() -> Optional[Tunnel]:
    return _tunnel

def get_url() -> Optional[str]:
    return _tunnel.url if _tunnel else None
