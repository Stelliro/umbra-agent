"""
UMBRA Auth (Simple) — JSON credentials file
=============================================
Stores username + password in ~/.config/umbra/login.json (plaintext, mode 600).
Kept OUTSIDE the project on purpose: the file explorer is confined to the
workshop folder and UMBRA's tools to env/, so the model can never read it.
No hashing, no salt, no expiry: the web UI only listens on 127.0.0.1.

login.json format:
  {"username": "admin", "password": "umbra"}

Change via settings UI, API, or just edit the file.
"""
import json, logging, secrets
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("UMBRA-AUTH")

LOGIN_DIR = Path.home() / ".config" / "umbra"


def _new_creds() -> Dict:
    # No shared default password: a fresh install gets a random one (printed once at creation)
    return {"username": "admin", "password": secrets.token_urlsafe(9)}


class AuthManager:
    def __init__(self, data_dir=None):
        self.path = Path(data_dir or LOGIN_DIR) / "login.json"
        self._sessions = {}  # token → username
        self._ensure_file()

    def _ensure_file(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            creds = _new_creds()
            self._save(creds)
            print(f"[UMBRA] Created login {self.path}  user: {creds['username']}  password: {creds['password']}")

    def _load(self) -> Dict:
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {}  # unreadable file: nobody can log in (never fall back to a known password)

    def _save(self, creds: Dict):
        self.path.write_text(json.dumps(creds, indent=2))
        self.path.chmod(0o600)

    # === Core ===

    def login(self, username: str, password: str) -> Optional[str]:
        creds = self._load()
        if not creds.get("password"):
            return None
        if secrets.compare_digest(str(username), str(creds.get("username", ""))) and \
                secrets.compare_digest(str(password), str(creds["password"])):
            token = secrets.token_hex(16)
            self._sessions[token] = username
            logger.info(f"Login: {username}")
            return token
        return None

    def validate_session(self, token: str) -> Optional[str]:
        if not token:
            return None
        return self._sessions.get(token)

    def logout(self, token: str):
        self._sessions.pop(token, None)

    # === Credential Changes ===

    def change_password(self, username: str, old_password: str, new_password: str) -> Dict:
        creds = self._load()
        if username != creds.get("username") or old_password != creds.get("password"):
            return {"success": False, "error": "Current credentials incorrect"}
        if not new_password:
            return {"success": False, "error": "New password cannot be empty"}
        creds["password"] = new_password
        self._save(creds)
        self._sessions.clear()
        logger.info(f"Password changed for {username}")
        return {"success": True}

    def change_username(self, old_username: str, password: str, new_username: str) -> Dict:
        creds = self._load()
        if old_username != creds.get("username") or password != creds.get("password"):
            return {"success": False, "error": "Current credentials incorrect"}
        if not new_username:
            return {"success": False, "error": "New username cannot be empty"}
        creds["username"] = new_username
        self._save(creds)
        self._sessions.clear()
        logger.info(f"Username changed: {old_username} -> {new_username}")
        return {"success": True, "new_username": new_username}

    # === Compat stubs (keep web UI happy) ===

    def has_admin(self) -> bool:
        return True

    def create_admin(self, username: str, password: str, display_name: str = "") -> Optional[str]:
        self._save({"username": username, "password": password})
        return "ok"

    def check_permission(self, token: str, permission: str) -> bool:
        return self.validate_session(token) is not None

    def check_token_limit(self, token: str, message_tokens: int) -> bool:
        return True

    def status(self) -> Dict:
        creds = self._load()
        return {"username": creds.get("username", "admin"), "sessions": len(self._sessions)}
