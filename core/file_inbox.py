"""
UMBRA File Inbox System
========================
Drop files into ~/.umbra/inbox/ for UMBRA to process.

Supported file types:
- .txt, .md  -> Read as context
- .json      -> Parse as structured data
- .pdf       -> Extract text (requires pypdf)
- .prompt    -> Add to prompt library

Files are moved to ~/.umbra/inbox/processed/ after reading.

Usage:
    inbox = FileInbox()
    new_files = inbox.check()
    for file_info in new_files:
        content = file_info["content"]
        # Process...
"""
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import hashlib

# Optional PDF support
try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


class FileInbox:
    """
    File inbox for UMBRA context injection.
    
    Drop files into the inbox folder. UMBRA will:
    1. Read and process them
    2. Move to processed folder (or delete based on config)
    3. Make content available for context
    """
    
    SUPPORTED_EXTENSIONS = {
        ".txt": "text",
        ".md": "text",
        ".json": "json",
        ".pdf": "pdf",
        ".prompt": "prompt",  # Special: adds to prompt library
        ".context": "context",  # Special: temporary context injection
        ".instruction": "instruction"  # Special: direct instruction to UMBRA
    }
    
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else Path.home() / ".umbra" / "inbox"
        self.processed_dir = self.base_dir / "processed"
        self.failed_dir = self.base_dir / "failed"
        self.log_file = self.base_dir / "inbox_log.json"
        
        # Create directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)
        self.failed_dir.mkdir(exist_ok=True)
        
        # Load log
        self.log = self._load_log()
    
    def _load_log(self) -> Dict:
        """Load processing log"""
        if self.log_file.exists():
            try:
                return json.loads(self.log_file.read_text())
            except:
                pass
        return {
            "processed": [],
            "failed": [],
            "stats": {"total_processed": 0, "total_failed": 0}
        }
    
    def _save_log(self):
        """Save processing log"""
        self.log_file.write_text(json.dumps(self.log, indent=2))
    
    def _get_file_hash(self, filepath: Path) -> str:
        """Get file hash for deduplication"""
        return hashlib.md5(filepath.read_bytes()).hexdigest()[:12]
    
    def check(self, delete_after: bool = False) -> List[Dict]:
        """
        Check inbox for new files.
        
        Returns list of file info dicts with content.
        """
        results = []
        
        # Files to always ignore
        ignore_files = {"inbox_log.json", ".gitkeep", ".DS_Store", "Thumbs.db"}
        
        for filepath in self.base_dir.iterdir():
            if filepath.is_dir():
                continue
            
            if filepath.name.startswith("."):
                continue
            
            # Skip our own log file and other system files
            if filepath.name in ignore_files:
                continue
            
            ext = filepath.suffix.lower()
            if ext not in self.SUPPORTED_EXTENSIONS:
                continue
            
            file_type = self.SUPPORTED_EXTENSIONS[ext]
            
            try:
                content = self._read_file(filepath, file_type)
                
                file_info = {
                    "filename": filepath.name,
                    "type": file_type,
                    "content": content,
                    "path": str(filepath),
                    "size": filepath.stat().st_size,
                    "hash": self._get_file_hash(filepath),
                    "processed_at": datetime.now().isoformat()
                }
                
                results.append(file_info)
                
                # Move to processed
                if delete_after:
                    filepath.unlink()
                else:
                    dest = self.processed_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filepath.name}"
                    shutil.move(str(filepath), str(dest))
                
                # Log success
                self.log["processed"].append({
                    "filename": filepath.name,
                    "type": file_type,
                    "processed_at": file_info["processed_at"],
                    "hash": file_info["hash"]
                })
                self.log["stats"]["total_processed"] += 1
                
            except Exception as e:
                # Move to failed
                dest = self.failed_dir / filepath.name
                shutil.move(str(filepath), str(dest))
                
                # Log failure
                self.log["failed"].append({
                    "filename": filepath.name,
                    "error": str(e),
                    "failed_at": datetime.now().isoformat()
                })
                self.log["stats"]["total_failed"] += 1
        
        # Keep logs trimmed
        self.log["processed"] = self.log["processed"][-100:]
        self.log["failed"] = self.log["failed"][-50:]
        self._save_log()
        
        return results
    
    def _read_file(self, filepath: Path, file_type: str) -> str:
        """Read file content based on type"""
        
        if file_type in ["text", "prompt", "context", "instruction"]:
            return filepath.read_text(encoding="utf-8")
        
        elif file_type == "json":
            data = json.loads(filepath.read_text())
            # Convert to readable format
            return json.dumps(data, indent=2)
        
        elif file_type == "pdf":
            if not HAS_PYPDF:
                raise ImportError("pypdf not installed - cannot read PDF")
            
            reader = pypdf.PdfReader(str(filepath))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        
        else:
            raise ValueError(f"Unknown file type: {file_type}")
    
    def get_instructions(self) -> List[Dict]:
        """Get any pending instruction files"""
        return [f for f in self.check() if f["type"] == "instruction"]
    
    def get_context(self) -> List[Dict]:
        """Get any pending context files"""
        return [f for f in self.check() if f["type"] == "context"]
    
    def get_prompts(self) -> List[Dict]:
        """Get any pending prompt files to add to library"""
        return [f for f in self.check() if f["type"] == "prompt"]
    
    def write_instruction(self, instruction: str, filename: str = None):
        """
        Write an instruction file to the inbox.
        Useful for external systems to communicate with UMBRA.
        """
        if filename is None:
            filename = f"instruction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.instruction"
        
        filepath = self.base_dir / filename
        filepath.write_text(instruction)
        return filepath
    
    def write_context(self, context: str, filename: str = None):
        """Write a context file to the inbox."""
        if filename is None:
            filename = f"context_{datetime.now().strftime('%Y%m%d_%H%M%S')}.context"
        
        filepath = self.base_dir / filename
        filepath.write_text(context)
        return filepath


class ContextManager:
    """
    Manages context injection for UMBRA.
    
    Combines:
    - File inbox contents
    - Prompt library lookups
    - Conversation history
    """
    
    def __init__(self, inbox: FileInbox = None, prompt_index = None):
        self.inbox = inbox or FileInbox()
        self.prompt_index = prompt_index
        self.active_context = []
        self.max_context_tokens = 2000  # Rough limit for 8B model
    
    def refresh(self) -> Dict:
        """
        Check for new files and update context.
        
        Returns summary of what was found.
        """
        summary = {
            "instructions": [],
            "context_added": [],
            "prompts_added": []
        }
        
        # Check inbox
        new_files = self.inbox.check()
        
        for file_info in new_files:
            if file_info["type"] == "instruction":
                summary["instructions"].append({
                    "filename": file_info["filename"],
                    "content": file_info["content"]
                })
            
            elif file_info["type"] == "context":
                self.active_context.append({
                    "source": file_info["filename"],
                    "content": file_info["content"],
                    "added_at": datetime.now().isoformat()
                })
                summary["context_added"].append(file_info["filename"])
            
            elif file_info["type"] == "prompt":
                if self.prompt_index:
                    # Parse prompt file (expects JSON or simple format)
                    try:
                        data = json.loads(file_info["content"])
                        self.prompt_index.add_prompt(
                            title=data.get("title", file_info["filename"]),
                            content=data.get("content", file_info["content"]),
                            keywords=data.get("keywords", []),
                            category=data.get("category", "user")
                        )
                    except json.JSONDecodeError:
                        # Simple text format - use filename as title
                        self.prompt_index.add_prompt(
                            title=file_info["filename"].replace(".prompt", ""),
                            content=file_info["content"],
                            keywords=["user", "custom"],
                            category="user"
                        )
                    summary["prompts_added"].append(file_info["filename"])
            
            else:
                # Generic content - add to context
                self.active_context.append({
                    "source": file_info["filename"],
                    "content": file_info["content"][:5000],  # Truncate large files
                    "added_at": datetime.now().isoformat()
                })
                summary["context_added"].append(file_info["filename"])
        
        # Trim old context (keep last 5)
        self.active_context = self.active_context[-5:]
        
        return summary
    
    def get_context_string(self) -> str:
        """Get current context as a string for injection into prompts"""
        if not self.active_context:
            return ""
        
        parts = ["=== ACTIVE CONTEXT ==="]
        for ctx in self.active_context:
            parts.append(f"\n[{ctx['source']}]:")
            parts.append(ctx["content"][:1000])  # Limit each
        parts.append("=== END CONTEXT ===")
        
        return "\n".join(parts)
    
    def lookup_prompts(self, keywords: List[str]) -> str:
        """Look up relevant prompts and return as context"""
        if not self.prompt_index:
            return ""
        
        prompt_ids = self.prompt_index.search(keywords, limit=3)
        if not prompt_ids:
            return ""
        
        parts = ["=== RELEVANT PROMPTS ==="]
        for pid in prompt_ids:
            content = self.prompt_index.get_prompt(pid)
            if content:
                meta = self.prompt_index.index["prompts"][pid]
                parts.append(f"\n[{meta['title']}]:")
                parts.append(content[:800])
        parts.append("=== END PROMPTS ===")
        
        return "\n".join(parts)
    
    def clear_context(self):
        """Clear active context"""
        self.active_context = []


# === CLI ===

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="UMBRA File Inbox")
    parser.add_argument("command", choices=["check", "status", "clear", "write"],
                       help="Command to run")
    parser.add_argument("--content", "-c", help="Content for write command")
    parser.add_argument("--type", "-t", choices=["instruction", "context"],
                       default="context", help="File type for write command")
    
    args = parser.parse_args()
    
    inbox = FileInbox()
    
    if args.command == "check":
        files = inbox.check()
        if files:
            print(f"\nProcessed {len(files)} files:")
            for f in files:
                print(f"  [{f['type']}] {f['filename']} ({f['size']} bytes)")
        else:
            print("No new files in inbox.")
    
    elif args.command == "status":
        print(f"\nInbox: {inbox.base_dir}")
        print(f"Processed: {inbox.log['stats']['total_processed']}")
        print(f"Failed: {inbox.log['stats']['total_failed']}")
        
        # Count pending
        pending = list(inbox.base_dir.glob("*"))
        pending = [f for f in pending if f.is_file() and not f.name.startswith(".")]
        print(f"Pending: {len(pending)} files")
    
    elif args.command == "clear":
        # Clear processed folder
        for f in inbox.processed_dir.iterdir():
            if f.is_file():
                f.unlink()
        print("Processed folder cleared.")
    
    elif args.command == "write":
        if not args.content:
            print("Usage: --content 'your content here'")
            return
        
        if args.type == "instruction":
            path = inbox.write_instruction(args.content)
        else:
            path = inbox.write_context(args.content)
        
        print(f"Written to: {path}")


if __name__ == "__main__":
    main()
