"""
File Janitor v1.0 — Boot-Time Project Cleanup
===============================================
Runs at startup to keep the project directory clean.
- Deletes leftover patch files (patch_*.py)
- Moves misplaced core modules to core/
- Removes __pycache__ dirs
- Cleans up .bak, .tmp, .pyc files from root
"""
import os, shutil, logging, re
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger("UMBRA-JANITOR")

# Files that belong in core/ not root
CORE_MODULES = {
    "sentinel.py", "swarm.py", "auth.py", "persona.py", "deps.py",
    "startup_sequence.py", "chat_store.py", "code_agent.py",
    "phoenix_council.py", "umbra_engine.py", "umbra_boot.py",
    "setup_engine.py", "file_janitor.py", "github_sync.py",
}

# Patterns for files that should be deleted
DELETE_PATTERNS = [
    r"^patch_.*\.py$",         # Patcher scripts
    r"^fix_.*\.py$",           # One-off fix scripts
    r"^hotfix.*\.py$",         # Hotfixes
    r".*\.py\.bak$",           # Python backups in root
    r".*\.tmp$",               # Temp files
    r".*\.pyc$",               # Compiled python in root
]

# Never delete these
PROTECTED = {
    "umbra_autonomous.py", "umbra_web.py", "umbra_state.py",
    "moltbook_client.py", "sd_bridge.py",
    "requirements.txt", "setup.py", "config.py",
    "README.md", "LICENSE",
}


class FileJanitor:
    """Scans and cleans the project directory at boot."""

    def __init__(self, project_dir="."):
        self.project_dir = Path(project_dir)
        self.core_dir = self.project_dir / "core"

    def scan(self) -> Dict:
        """Scan for files that need attention. Non-destructive."""
        report = {
            "patch_files": [],
            "backup_files": [],
            "misplaced_files": [],
            "temp_files": [],
            "pycache_dirs": 0,
            "total_issues": 0,
        }

        for item in self.project_dir.iterdir():
            name = item.name

            # Skip directories (except pycache)
            if item.is_dir():
                if name == "__pycache__":
                    report["pycache_dirs"] += 1
                # Check subdirs for pycache too
                for sub_pc in item.rglob("__pycache__"):
                    report["pycache_dirs"] += 1
                continue

            # Skip protected files
            if name in PROTECTED:
                continue

            # Check for patch/fix scripts
            if re.match(r"^(?:patch|fix|hotfix).*\.py$", name, re.IGNORECASE):
                report["patch_files"].append(str(item))
                continue

            # Check for backup files
            if name.endswith((".bak", ".backup", ".orig")):
                report["backup_files"].append(str(item))
                continue

            # Check for temp files
            if name.endswith((".tmp", ".pyc")):
                report["temp_files"].append(str(item))
                continue

            # Check for misplaced core modules
            if name in CORE_MODULES:
                # It's in root but should be in core/
                report["misplaced_files"].append({
                    "current": str(item),
                    "target": str(self.core_dir / name),
                })

        # Count pycache in all subdirs
        for pc in self.project_dir.rglob("__pycache__"):
            if pc.parent == self.project_dir:
                continue  # Already counted
            report["pycache_dirs"] += 1

        report["total_issues"] = (
            len(report["patch_files"]) + len(report["backup_files"]) +
            len(report["misplaced_files"]) + len(report["temp_files"]) +
            report["pycache_dirs"]
        )
        return report

    def clean(self, dry_run=True) -> Dict:
        """
        Clean the project directory.
        dry_run=True: report what would happen. dry_run=False: do it.
        """
        report = self.scan()
        result = {
            "deleted": 0, "moved": 0, "pycache_removed": 0,
            "would_delete": 0, "would_move": 0,
        }

        # Delete patch files
        for fp in report["patch_files"]:
            if dry_run:
                result["would_delete"] += 1
                logger.info(f"  [DRY] Would delete: {fp}")
            else:
                try:
                    os.remove(fp)
                    result["deleted"] += 1
                    logger.info(f"  🗑️ Deleted: {fp}")
                except OSError as e:
                    logger.warning(f"  ⚠ Can't delete {fp}: {e}")

        # Delete backup files
        for fp in report["backup_files"]:
            if dry_run:
                result["would_delete"] += 1
            else:
                try:
                    os.remove(fp)
                    result["deleted"] += 1
                    logger.info(f"  🗑️ Deleted: {fp}")
                except OSError:
                    pass

        # Delete temp files
        for fp in report["temp_files"]:
            if dry_run:
                result["would_delete"] += 1
            else:
                try:
                    os.remove(fp)
                    result["deleted"] += 1
                except OSError:
                    pass

        # Move misplaced files
        for item in report["misplaced_files"]:
            src = item["current"]
            dst = item["target"]
            if dry_run:
                result["would_move"] += 1
                logger.info(f"  [DRY] Would move: {src} → {dst}")
            else:
                try:
                    self.core_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(src, dst)
                    result["moved"] += 1
                    logger.info(f"  📦 Moved: {Path(src).name} → core/")
                except (OSError, shutil.Error) as e:
                    logger.warning(f"  ⚠ Can't move {src}: {e}")

        # Remove __pycache__
        if not dry_run:
            for pc in self.project_dir.rglob("__pycache__"):
                try:
                    shutil.rmtree(pc)
                    result["pycache_removed"] += 1
                except OSError:
                    pass

        return result

    def get_summary(self, report: Dict = None) -> str:
        """Human-readable summary of what needs cleaning."""
        if report is None:
            report = self.scan()

        parts = []
        if report["patch_files"]:
            parts.append(f"{len(report['patch_files'])} patch file(s) to delete")
        if report["backup_files"]:
            parts.append(f"{len(report['backup_files'])} backup file(s)")
        if report["misplaced_files"]:
            names = [Path(f["current"]).name for f in report["misplaced_files"]]
            parts.append(f"{len(names)} misplaced module(s): {', '.join(names)}")
        if report["pycache_dirs"]:
            parts.append(f"{report['pycache_dirs']} __pycache__ dir(s)")
        if report["temp_files"]:
            parts.append(f"{len(report['temp_files'])} temp file(s)")

        if not parts:
            return "Project directory is clean."
        return f"Cleanup needed: {'; '.join(parts)}."


def boot_cleanup(project_dir=".", dry_run=False) -> str:
    """Run at boot. Returns status line."""
    j = FileJanitor(project_dir)
    report = j.scan()
    if report["total_issues"] == 0:
        return "JANITOR:CLEAN"
    summary = j.get_summary(report)
    if not dry_run:
        result = j.clean(dry_run=False)
        return f"JANITOR:CLEANED({result['deleted']}d,{result['moved']}m,{result['pycache_removed']}p)"
    return f"JANITOR:NEEDS_CLEAN({summary})"
