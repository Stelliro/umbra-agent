import shutil
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, scrolledtext

class UmbraCodeSurgeon:
    def __init__(self, root):
        self.root = root
        self.root.title("UMBRA Code Surgeon (Indentation Fix)")
        self.root.geometry("600x550")
        self.root.configure(bg="#2c3e50")

        tk.Label(root, text="CODE SURGEON", font=("Consolas", 16, "bold"), 
                 bg="#2c3e50", fg="#2ecc71").pack(pady=20)
        
        self.log_area = scrolledtext.ScrolledText(root, width=70, height=18, 
                                                bg="black", fg="#2ecc71", font=("Consolas", 9))
        self.log_area.pack(pady=10)

        self.btn = tk.Button(root, text="REWRITE DAMAGED BLOCKS", 
                           command=self.apply_fix, width=30, height=2,
                           bg="#27ae60", fg="white", font=("Consolas", 12, "bold"))
        self.btn.pack(pady=20)
        
        # Target the file in core/ if it exists, else root
        self.target_file = Path("core/umbra_autonomous.py")
        if not self.target_file.exists():
            self.target_file = Path("umbra_autonomous.py")

    def log(self, msg):
        self.log_area.insert(tk.END, f"> {msg}\n")
        self.log_area.see(tk.END)

    def apply_fix(self):
        if not self.target_file.exists():
            self.log("❌ File not found!")
            return

        # Backup
        shutil.copy(self.target_file, f"{self.target_file}.indent_backup")
        self.log("✅ Backup created.")

        with open(self.target_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        skip_mode = False
        repaired_count = 0

        # BLOCK 1: The Clean LLMInterface Constructor
        clean_llm_init = [
            "    def __init__(self, evolver: PromptEvolver, objectives: ObjectivesManager, state_engine=None):\n",
            "        self.evolver = evolver\n",
            "        self.objectives = objectives\n",
            "        self.state_engine = state_engine\n"
        ]

        # BLOCK 2: The Clean AutonomousLoop Constructor Call
        # We look for the line initiating LLMInterface
        
        for i, line in enumerate(lines):
            # FIX 1: LLMInterface Indentation
            if "class LLMInterface" in line:
                new_lines.append(line)
                self.log("Found LLMInterface. Scanning for __init__...")
                continue

            # If we find the LLMInterface __init__, we replace it entirely
            if "def __init__(self, evolver: PromptEvolver" in line and "class LLMInterface" not in line:
                # Check if we are inside LLMInterface (simple heuristic: indentation)
                # This is a bit loose but effective for this specific crash
                if "state_engine" in line or "objectives)" in line:
                    self.log("⚠️ Found damaged LLMInterface constructor. Replacing...")
                    new_lines.extend(clean_llm_init)
                    skip_mode = True # Skip the existing bad lines
                    repaired_count += 1
                    continue

            # Stop skipping when we hit the next function
            if skip_mode:
                if line.strip().startswith("def ") or line.strip().startswith("class "):
                    skip_mode = False
                    new_lines.append(line)
                # If we see assignment lines, we skip them (they are part of the bad block)
                elif "self.evolver =" in line or "self.objectives =" in line or "self.state_engine =" in line:
                    continue
                else:
                    # If it's a blank line or comment, keep it but turn off skip if indentation changes
                    if len(line.strip()) > 0 and not line.startswith(" "):
                         skip_mode = False
                         new_lines.append(line)
                    else:
                         # It's likely part of the body, skip it
                         continue
            else:
                # FIX 2: AutonomousLoop Call (Single line fix)
                if "self.llm = LLMInterface(self.evolver, self.objectives)" in line:
                    self.log("✅ Wiring AutonomousLoop -> LLMInterface...")
                    new_line = line.replace(
                        "self.llm = LLMInterface(self.evolver, self.objectives)", 
                        "self.llm = LLMInterface(self.evolver, self.objectives, state_engine=self.state_engine)"
                    )
                    new_lines.append(new_line)
                    repaired_count += 1
                
                # FIX 3: Catch any leftover 'state_engine=self.state_engine)' from previous bad regex
                elif "state_engine=self.state_engine)" in line and "LLMInterface" in line:
                     # This line is likely fine, just ensure indentation
                     new_lines.append(line)
                
                else:
                    new_lines.append(line)

        try:
            with open(self.target_file, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            
            self.log(f"\n✨ SURGERY COMPLETE. Repaired {repaired_count} blocks.")
            messagebox.showinfo("Success", "Code structure repaired.")
            
        except Exception as e:
            self.log(f"❌ Save failed: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = UmbraCodeSurgeon(root)
    root.mainloop()