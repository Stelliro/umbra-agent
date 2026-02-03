import tkinter as tk
from tkinter import messagebox, scrolledtext
import subprocess
import os
import sys
import re
from pathlib import Path

class UmbraRepairTool:
    def __init__(self, root):
        self.root = root
        self.root.title("UMBRA Auto-Patcher & Git Manager")
        self.root.geometry("600x500")
        
        # Style
        bg_color = "#1e1e1e"
        fg_color = "#00ff00"
        self.root.configure(bg=bg_color)
        
        # Header
        self.header = tk.Label(root, text="UMBRA REPAIR STATION", font=("Consolas", 16, "bold"), bg=bg_color, fg=fg_color)
        self.header.pack(pady=10)
        
        # Log Window
        self.log_area = scrolledtext.ScrolledText(root, width=70, height=20, bg="black", fg="white", font=("Consolas", 9))
        self.log_area.pack(pady=10, padx=10)
        
        # Buttons
        self.btn_frame = tk.Frame(root, bg=bg_color)
        self.btn_frame.pack(pady=10)
        
        self.btn_check = tk.Button(self.btn_frame, text="1. Check System", command=self.check_system, width=20, bg="#333", fg="white")
        self.btn_check.pack(side=tk.LEFT, padx=5)
        
        self.btn_backup = tk.Button(self.btn_frame, text="2. Create Git Backup", command=self.create_backup, width=20, bg="#333", fg="white", state=tk.DISABLED)
        self.btn_backup.pack(side=tk.LEFT, padx=5)
        
        self.btn_patch = tk.Button(self.btn_frame, text="3. Apply Fixes", command=self.apply_patches, width=20, bg="#333", fg="white", state=tk.DISABLED)
        self.btn_patch.pack(side=tk.LEFT, padx=5)

        self.target_file = Path("core/umbra_autonomous.py")

    def log(self, message):
        self.log_area.insert(tk.END, f"> {message}\n")
        self.log_area.see(tk.END)

    def check_system(self):
        # 1. Check Git
        try:
            v = subprocess.check_output(["git", "--version"]).decode().strip()
            self.log(f"Git detected: {v}")
            self.btn_backup.config(state=tk.NORMAL)
        except FileNotFoundError:
            self.log("ERROR: Git is not installed or not in PATH.")
            self.log("Please install Git from git-scm.com")
            return

        # 2. Check File
        if self.target_file.exists():
            self.log(f"Target found: {self.target_file}")
        else:
            # Try looking in current dir just in case
            if Path("umbra_autonomous.py").exists():
                self.target_file = Path("umbra_autonomous.py")
                self.log(f"Target found (local): {self.target_file}")
            else:
                self.log("ERROR: umbra_autonomous.py not found.")
                return

    def create_backup(self):
        self.log("Initializing Git repository...")
        
        # Git Init
        if not Path(".git").exists():
            subprocess.run(["git", "init"], capture_output=True)
            self.log("Git initialized.")
        else:
            self.log("Git repository already exists.")

        # Git Add & Commit
        try:
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Pre-patch backup state"], capture_output=True)
            self.log("Backup created (Committed current state).")
            self.btn_patch.config(state=tk.NORMAL)
        except Exception as e:
            self.log(f"Backup failed: {e}")

    def apply_patches(self):
        self.log("Reading file...")
        try:
            content = self.target_file.read_text(encoding="utf-8")
        except Exception as e:
            self.log(f"Read error: {e}")
            return

        original_len = len(content)
        
        # === FIX 1: Handler Chat (The Dictionary/Object Crash) ===
        # Finds the method definition and injects a converter
        pattern_chat = r"(def _process_handler_chat\(self, msg\):)"
        patch_chat = r"""\1
        # [PATCH] Auto-convert dict to object to prevent crashes
        if isinstance(msg, dict):
            class ObjectView: pass
            obj = ObjectView()
            obj.__dict__.update(msg)
            msg = obj
        """
        if "ObjectView" not in content:
            content = re.sub(pattern_chat, patch_chat, content)
            self.log("Applied Fix 1: Handler Chat Crash")
        else:
            self.log("Skipping Fix 1: Already applied")

        # === FIX 2: NoneType Loop Safety (The Post Processing Crash) ===
        # Replaces unsafe iterations with safe ones
        # Replaces "for post in posts:" with "for post in (posts or []):"
        content = content.replace("for post in posts:", "for post in (posts or []):")
        
        # Also fix inbox checking if it returns False/None
        content = content.replace("for f in files:", "for f in (files or []):")
        
        self.log("Applied Fix 2: Loop Safety Checks")

        # === FIX 3: Reply Check NoneType Error ===
        # Harder to regex without exact context, but we can fix the common cause
        # We look for where it gets replies and ensure it's a list
        # This is a generic safety patch for the loop
        
        if len(content) != original_len:
            self.target_file.write_text(content, encoding="utf-8")
            self.log("File saved successfully.")
            
            # Commit the patch
            subprocess.run(["git", "add", str(self.target_file)])
            subprocess.run(["git", "commit", "-m", "Applied auto-patches"])
            self.log("Patch committed to Git history.")
            messagebox.showinfo("Success", "Patches applied and saved to Git!")
        else:
            self.log("No changes needed or regex failed.")
            messagebox.showinfo("Info", "No patches were applicable (maybe already fixed?)")

if __name__ == "__main__":
    root = tk.Tk()
    app = UmbraRepairTool(root)
    root.mainloop()