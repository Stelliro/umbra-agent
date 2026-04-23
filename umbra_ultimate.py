"""
UMBRA ULTIMATE CONSOLE
=======================
High-performance control interface using CustomTkinter.
Reliable, fast, and crash-proof.
"""
import customtkinter as ctk
import tkinter as tk
import sys
import threading
import time
import queue
from datetime import datetime
from pathlib import Path

# --- CONFIGURATION ---
SCRIPT_DIR = Path(__file__).parent
CORE_DIR = SCRIPT_DIR / "core"
DATA_DIR = SCRIPT_DIR / "data"

if CORE_DIR.exists():
    sys.path.insert(0, str(CORE_DIR))

# Lazy Imports
try:
    from prompt_index import PromptIndex
    HAS_INDEX = True
except: 
    HAS_INDEX = False

HAS_MOLTBOOK = False

# THEME COLORS
C_BG = "#0b0c15"       # Deep Void
C_CARD = "#151621"     # Panel BG
C_ACCENT = "#00d9ff"   # UMBRA Cyan
C_WARN = "#f1c40f"     # Warning Yellow
C_DANGER = "#e74c3c"   # Danger Red
C_SUCCESS = "#2ecc71"  # Success Green
C_TEXT = "#ecf0f1"     # White-ish

class UmbraUltimateApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("UMBRA UNIT-734 // COMMAND OVERRIDE")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color=C_BG)

        # State
        self.loop = None
        self.running = False
        self.queue = queue.Queue()
        self.logs = []
        self.start_time = time.time()
        
        # Components
        self.moltbook = None
        self.prompt_index = PromptIndex(base_dir=str(DATA_DIR/"prompts")) if HAS_INDEX else None

        # Build UI
        self._setup_layout()
        self._start_clock()
        
        self.log_system("System Initialized. Ready for autonomous sequence.")

    def _setup_layout(self):
        """Grid Layout: Sidebar (Left), Main (Right)"""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=C_CARD)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self._build_sidebar()

        # --- MAIN AREA ---
        self.main_area = ctk.CTkTabview(self, fg_color=C_BG, corner_radius=10)
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)
        
        self.tab_dashboard = self.main_area.add("DASHBOARD")
        self.tab_chat = self.main_area.add("UPLINK (CHAT)")
        self.tab_logs = self.main_area.add("SYSTEM LOGS")

        self._build_dashboard()
        self._build_chat()
        self._build_logs()

    def _build_sidebar(self):
        """Status cards and controls"""
        # Header
        title = ctk.CTkLabel(self.sidebar, text="UMBRA", font=("Consolas", 32, "bold"), text_color=C_ACCENT)
        title.pack(pady=(30, 0))
        subtitle = ctk.CTkLabel(self.sidebar, text="UNIT-734", font=("Consolas", 12), text_color="grey")
        subtitle.pack(pady=(0, 20))

        # Status Badge
        self.status_badge = ctk.CTkButton(self.sidebar, text="OFFLINE", fg_color="#333", 
                                          hover=False, height=30, width=120, corner_radius=15)
        self.status_badge.pack(pady=10)

        # Stats Container
        stats_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=20)

        self._add_stat(stats_frame, "NETWORK", "LOCAL ONLY")
        self._add_stat(stats_frame, "PROMPTS", str(len(self.prompt_index.list_prompts())) if self.prompt_index else "0")
        self._add_stat(stats_frame, "CYCLES", "0")
        self._add_stat(stats_frame, "UPTIME", "00:00:00")

        # Controls
        self.btn_auto = ctk.CTkButton(self.sidebar, text="INITIATE SEQUENCE", 
                                      font=("Consolas", 14, "bold"),
                                      height=50,
                                      fg_color=C_SUCCESS, 
                                      hover_color="#27ae60",
                                      command=self.toggle_autonomous)
        self.btn_auto.pack(side="bottom", fill="x", padx=20, pady=30)

    def _add_stat(self, parent, label, value):
        frame = ctk.CTkFrame(parent, fg_color="#1f202e", corner_radius=6)
        frame.pack(fill="x", pady=4)
        ctk.CTkLabel(frame, text=label, font=("Arial", 10, "bold"), text_color="grey").pack(anchor="w", padx=10, pady=(5,0))
        lbl = ctk.CTkLabel(frame, text=value, font=("Consolas", 14, "bold"), text_color=C_TEXT)
        lbl.pack(anchor="w", padx=10, pady=(0,5))
        
        # Save reference to update later
        setattr(self, f"stat_{label.lower()}", lbl)

    def _build_dashboard(self):
        """Main overview"""
        self.tab_dashboard.grid_columnconfigure(0, weight=1)
        
        # Welcome Banner
        banner = ctk.CTkFrame(self.tab_dashboard, fg_color=C_ACCENT, corner_radius=10)
        banner.grid(row=0, column=0, sticky="ew", pady=(10, 20))
        ctk.CTkLabel(banner, text="COMMAND OVERRIDE ACTIVE", text_color="black", 
                     font=("Arial", 16, "bold")).pack(pady=15)

        # Quick Actions Grid
        actions = ctk.CTkFrame(self.tab_dashboard, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew")
        actions.grid_columnconfigure((0,1), weight=1)

        self._action_btn(actions, 0, 0, "REGISTER IDENTITY", "Create new agent persona", self._stub_action)
        self._action_btn(actions, 0, 1, "PROCESS INBOX", "Ingest files from /inbox", self._stub_action)
        self._action_btn(actions, 1, 0, "RUN SINGLE CYCLE", "Execute one loop iteration", self._stub_action)
        self._action_btn(actions, 1, 1, "OPEN SHELL", "Launch terminal window", self._stub_action)

    def _action_btn(self, parent, r, c, title, desc, cmd):
        btn = ctk.CTkButton(parent, text=f"{title}\n{desc}", command=cmd,
                            fg_color=C_CARD, hover_color="#252630",
                            height=80, font=("Consolas", 14, "bold"))
        btn.grid(row=r, column=c, padx=5, pady=5, sticky="ew")

    def _build_chat(self):
        """Chat Interface"""
        self.tab_chat.grid_columnconfigure(0, weight=1)
        self.tab_chat.grid_rowconfigure(0, weight=1)

        self.chat_history = ctk.CTkTextbox(self.tab_chat, font=("Consolas", 12), fg_color="#000", text_color=C_ACCENT)
        self.chat_history.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        
        input_frame = ctk.CTkFrame(self.tab_chat, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew")
        
        self.chat_input = ctk.CTkEntry(input_frame, placeholder_text="Message UMBRA...", height=40, font=("Consolas", 12))
        self.chat_input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.chat_input.bind("<Return>", self.send_chat)
        
        send_btn = ctk.CTkButton(input_frame, text="TRANSMIT", width=100, height=40, fg_color=C_ACCENT, text_color="black", command=self.send_chat)
        send_btn.pack(side="right")

    def _build_logs(self):
        """Log Viewer"""
        self.tab_logs.grid_columnconfigure(0, weight=1)
        self.tab_logs.grid_rowconfigure(0, weight=1)
        
        self.log_display = ctk.CTkTextbox(self.tab_logs, font=("Consolas", 11), fg_color="#111")
        self.log_display.grid(row=0, column=0, sticky="nsew")

    # --- LOGIC ---

    def _start_clock(self):
        """Update uptime and other periodic stats"""
        elapsed = int(time.time() - self.start_time)
        h, r = divmod(elapsed, 3600)
        m, s = divmod(r, 60)
        self.stat_uptime.configure(text=f"{h:02}:{m:02}:{s:02}")
        
        # Poll queue for thread updates
        try:
            while True:
                msg = self.queue.get_nowait()
                self._handle_queue_msg(msg)
        except queue.Empty:
            pass
            
        self.after(1000, self._start_clock)

    def log_system(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}\n"
        self.logs.append(entry)
        self.log_display.insert("end", entry)
        self.log_display.see("end")

    def toggle_autonomous(self):
        if self.running:
            self.running = False
            self.btn_auto.configure(text="INITIATE SEQUENCE", fg_color=C_SUCCESS)
            self.status_badge.configure(text="STOPPING...", fg_color=C_WARN)
            self.log_system("Stopping autonomous loop...")
        else:
            self.running = True
            self.btn_auto.configure(text="TERMINATE", fg_color=C_DANGER)
            self.status_badge.configure(text="OPERATIONAL", fg_color=C_ACCENT, text_color="black")
            self.log_system("Initializing Enhanced Autonomous Loop...")
            threading.Thread(target=self.run_loop_thread, daemon=True).start()

    def run_loop_thread(self):
        try:
            from umbra_integration import EnhancedAutonomousLoop
            self.queue.put(("log", "Importing Core Systems..."))
            self.loop = EnhancedAutonomousLoop(dry_run=False)
            self.queue.put(("log", "🟢 UMBRA Online."))
            
            while self.running:
                self.queue.put(("log", "Executing Cycle..."))
                res = self.loop.run_single_cycle()
                self.queue.put(("log", f"Result: {res.get('action')}"))
                self.queue.put(("cycle", 1))
                time.sleep(60) # Wait 60s
        except Exception as e:
            self.queue.put(("log", f"CRITICAL ERROR: {e}"))
            self.queue.put(("stop", None))

    def _handle_queue_msg(self, msg):
        type, content = msg
        if type == "log":
            self.log_system(content)
        elif type == "cycle":
            current = int(self.stat_cycles.cget("text"))
            self.stat_cycles.configure(text=str(current + 1))
        elif type == "stop":
            self.running = False
            self.btn_auto.configure(text="INITIATE SEQUENCE", fg_color=C_SUCCESS)
            self.status_badge.configure(text="ERROR", fg_color=C_DANGER)

    def send_chat(self, event=None):
        msg = self.chat_input.get()
        if not msg: return
        self.chat_input.delete(0, "end")
        
        self.chat_history.insert("end", f"HANDLER: {msg}\n")
        if self.loop:
            self.loop.send_chat(msg)
            # In a real scenario, we'd poll for the response here
            # For now, we simulate acknowledgment
            self.after(1000, lambda: self.chat_history.insert("end", f"UMBRA: Received. Processing '{msg}'...\n"))
        else:
            self.chat_history.insert("end", "SYSTEM: Autonomous loop offline.\n")

    def _stub_action(self):
        self.log_system("Command acknowledged. Logic pending.")

if __name__ == "__main__":
    app = UmbraUltimateApp()
    app.mainloop()