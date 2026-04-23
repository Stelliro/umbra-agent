"""
UMBRA Management GUI
=====================
Visual interface to manage UMBRA's autonomous operations.

Features:
- Start/Stop autonomous loop
- Manage prompt library
- View/add inbox files
- Monitor status and logs
- Trigger manual evolution
- Test Moltbook connection

Run: python umbra_gui.py
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import time
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

# Try imports - LAZY load heavy modules to prevent startup cycles
HAS_INDEX = False
HAS_INBOX = False
HAS_AUTO = False
HAS_MOLTBOOK = False
HAS_OLLAMA = False

try:
    from prompt_index import PromptIndex, initialize_default_prompts
    HAS_INDEX = True
except ImportError:
    pass

try:
    from file_inbox import FileInbox
    HAS_INBOX = True
except ImportError:
    pass

# Note: We do NOT import umbra_autonomous at module level anymore
# to prevent it from running cycles during import
try:
    # Only import the light components we need
    HAS_AUTO = True  # Will check properly when needed
except ImportError:
    pass

# Moltbook is intentionally disabled. Keep GUI local-only.

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    pass


# Configuration
DATA_DIR = Path("data")
PROMPTS_DIR = DATA_DIR / "prompts"
INBOX_DIR = DATA_DIR / "inbox"
LOGS_DIR = DATA_DIR / "logs"


class UmbraGUI(ctk.CTk):
    """Main GUI Application"""
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.title("UMBRA (Unit-734) Management Console")
        self.geometry("1000x700")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # State
        self.autonomous_running = False
        self.autonomous_thread = None
        
        # Initialize components
        self._init_directories()
        self._init_components()
        self._build_ui()
        self._refresh_all()
    
    def _init_directories(self):
        """Ensure directories exist"""
        for d in [DATA_DIR, PROMPTS_DIR, INBOX_DIR, INBOX_DIR / "processed", LOGS_DIR]:
            d.mkdir(parents=True, exist_ok=True)
    
    def _init_components(self):
        """Initialize backend components - lazy load heavy modules"""
        self.prompt_index = None
        self.inbox = None
        self.evolver = None
        self.moltbook = None
        
        if HAS_INDEX:
            self.prompt_index = PromptIndex(base_dir=str(PROMPTS_DIR))
            if len(self.prompt_index.list_prompts()) == 0:
                initialize_default_prompts(self.prompt_index)
        
        if HAS_INBOX:
            self.inbox = FileInbox(base_dir=str(INBOX_DIR))
        
        # Lazy load evolver only when needed - don't import full umbra_autonomous yet
        # This prevents the autonomous loop from running on GUI startup
        self._evolver_loaded = False
        
        self.moltbook = None
    
    def _get_evolver(self):
        """Lazy load the evolver when first needed"""
        if not self._evolver_loaded:
            try:
                from umbra_autonomous import PromptEvolver
                # Removed the storage_path argument to fix the TypeError
                self.evolver = PromptEvolver() 
                self._evolver_loaded = True
            except ImportError:
                pass
        return self.evolver
    
    def _build_ui(self):
        """Build the UI"""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # === HEADER ===
        header = ctk.CTkFrame(self, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header.grid_columnconfigure(1, weight=1)
        
        # Title
        title_label = ctk.CTkLabel(
            header, 
            text="UMBRA (Unit-734)", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=10)
        
        # Status indicators
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.grid(row=0, column=1, padx=10)
        
        self.ollama_status = ctk.CTkLabel(
            status_frame, 
            text="● Ollama", 
            text_color="green" if HAS_OLLAMA else "red"
        )
        self.ollama_status.pack(side="left", padx=5)
        
        self.moltbook_status = ctk.CTkLabel(
            status_frame,
            text="● Local-Only Mode",
            text_color="green"
        )
        self.moltbook_status.pack(side="left", padx=5)
        
        # Autonomous control
        self.auto_button = ctk.CTkButton(
            header,
            text="▶ Start Autonomous",
            command=self._toggle_autonomous,
            width=150,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.auto_button.grid(row=0, column=2, padx=20, pady=10)
        
        # === TABS ===
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Add tabs
        self.tab_status = self.tabview.add("Status")
        self.tab_prompts = self.tabview.add("Prompts")
        self.tab_inbox = self.tabview.add("Inbox")
        self.tab_evolution = self.tabview.add("Evolution")
        self.tab_logs = self.tabview.add("Logs")
        
        self._build_status_tab()
        self._build_prompts_tab()
        self._build_inbox_tab()
        self._build_evolution_tab()
        self._build_logs_tab()
        
        # === FOOTER ===
        footer = ctk.CTkFrame(self, height=30)
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        
        self.status_label = ctk.CTkLabel(footer, text="Ready", text_color="gray")
        self.status_label.pack(side="left", padx=10)
        
        refresh_btn = ctk.CTkButton(
            footer, text="↻ Refresh All", width=100,
            command=self._refresh_all
        )
        refresh_btn.pack(side="right", padx=10)
    
    # === STATUS TAB ===
    
    def _build_status_tab(self):
        """Build the status overview tab"""
        self.tab_status.grid_columnconfigure(0, weight=1)
        self.tab_status.grid_columnconfigure(1, weight=1)
        
        # Left column - System status
        left_frame = ctk.CTkFrame(self.tab_status)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(left_frame, text="System Status", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.status_text = ctk.CTkTextbox(left_frame, height=300)
        self.status_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Right column - Quick actions
        right_frame = ctk.CTkFrame(self.tab_status)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(right_frame, text="Quick Actions", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        actions = [
            ("📊 Run Single Cycle", self._run_single_cycle),
            ("🧠 Trigger Evolution", self._trigger_evolution),
            ("📥 Process Inbox", self._process_inbox),
            ("💬 Open Chat", self._open_chat),
        ]
        
        for text, cmd in actions:
            btn = ctk.CTkButton(right_frame, text=text, command=cmd, width=200)
            btn.pack(pady=5, padx=20)
    
    # === PROMPTS TAB ===
    
    def _build_prompts_tab(self):
        """Build the prompt management tab"""
        self.tab_prompts.grid_columnconfigure(0, weight=1)
        self.tab_prompts.grid_columnconfigure(1, weight=2)
        self.tab_prompts.grid_rowconfigure(0, weight=1)
        
        # Left - Prompt list
        list_frame = ctk.CTkFrame(self.tab_prompts)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(list_frame, text="Prompt Library", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        # Search
        search_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=5)
        
        self.prompt_search = ctk.CTkEntry(search_frame, placeholder_text="Search keywords...")
        self.prompt_search.pack(side="left", fill="x", expand=True, padx=5)
        self.prompt_search.bind("<Return>", lambda e: self._search_prompts())
        
        ctk.CTkButton(search_frame, text="🔍", width=30, command=self._search_prompts).pack(side="right")
        
        # Prompt listbox
        self.prompt_listbox = ctk.CTkTextbox(list_frame, height=300)
        self.prompt_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.prompt_listbox.bind("<Double-Button-1>", self._on_prompt_double_click)
        
        # Buttons
        btn_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(btn_frame, text="+ New", width=60, command=self._new_prompt).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Delete", width=60, command=self._delete_prompt, fg_color="red").pack(side="right", padx=2)
        
        # Right - Prompt editor
        editor_frame = ctk.CTkFrame(self.tab_prompts)
        editor_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(editor_frame, text="Prompt Editor", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        # Title
        title_frame = ctk.CTkFrame(editor_frame, fg_color="transparent")
        title_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(title_frame, text="Title:").pack(side="left")
        self.prompt_title = ctk.CTkEntry(title_frame, width=300)
        self.prompt_title.pack(side="left", padx=10)
        
        # Keywords
        kw_frame = ctk.CTkFrame(editor_frame, fg_color="transparent")
        kw_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(kw_frame, text="Keywords:").pack(side="left")
        self.prompt_keywords = ctk.CTkEntry(kw_frame, width=300, placeholder_text="comma, separated")
        self.prompt_keywords.pack(side="left", padx=10)
        
        # Category
        cat_frame = ctk.CTkFrame(editor_frame, fg_color="transparent")
        cat_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(cat_frame, text="Category:").pack(side="left")
        self.prompt_category = ctk.CTkComboBox(
            cat_frame, 
            values=["identity", "language", "theory", "templates", "philosophy", "states", "evolution", "user"],
            width=150
        )
        self.prompt_category.pack(side="left", padx=10)
        
        # Content
        ctk.CTkLabel(editor_frame, text="Content:").pack(anchor="w", padx=10)
        self.prompt_content = ctk.CTkTextbox(editor_frame, height=200)
        self.prompt_content.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Save button
        ctk.CTkButton(editor_frame, text="💾 Save Prompt", command=self._save_prompt).pack(pady=10)
        
        self.selected_prompt_id = None
    
    # === INBOX TAB ===
    
    def _build_inbox_tab(self):
        """Build the inbox management tab"""
        self.tab_inbox.grid_columnconfigure(0, weight=1)
        self.tab_inbox.grid_rowconfigure(1, weight=1)
        
        # Top - Actions
        action_frame = ctk.CTkFrame(self.tab_inbox)
        action_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkButton(action_frame, text="📥 Process Inbox", command=self._process_inbox).pack(side="left", padx=10, pady=10)
        ctk.CTkButton(action_frame, text="📂 Open Folder", command=self._open_inbox_folder).pack(side="left", padx=10)
        ctk.CTkButton(action_frame, text="🗑 Clear Processed", command=self._clear_processed).pack(side="left", padx=10)
        
        # Middle - Pending files and quick add
        content_frame = ctk.CTkFrame(self.tab_inbox)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)
        
        # Left - File list
        files_frame = ctk.CTkFrame(content_frame)
        files_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(files_frame, text="Pending Files", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        self.inbox_list = ctk.CTkTextbox(files_frame, height=250)
        self.inbox_list.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkButton(files_frame, text="↻ Refresh", command=self._refresh_inbox).pack(pady=5)
        
        # Right - Quick add
        add_frame = ctk.CTkFrame(content_frame)
        add_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(add_frame, text="Quick Add to Inbox", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        # Type selector
        type_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        type_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(type_frame, text="Type:").pack(side="left")
        self.inbox_type = ctk.CTkComboBox(
            type_frame,
            values=["instruction", "context", "prompt"],
            width=120
        )
        self.inbox_type.pack(side="left", padx=10)
        self.inbox_type.set("instruction")
        
        # Content
        ctk.CTkLabel(add_frame, text="Content:").pack(anchor="w", padx=10)
        self.inbox_content = ctk.CTkTextbox(add_frame, height=150)
        self.inbox_content.pack(fill="x", padx=10, pady=5)
        
        # Preset instructions
        preset_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        preset_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(preset_frame, text="Presets:").pack(side="left")
        presets = [
            ("/evolve Be more concise", "/evolve"),
            ("/evolve More compression metaphors", "/evolve"),
            ("/post About constraint wisdom", "/post"),
        ]
        for text, _ in presets[:3]:
            ctk.CTkButton(
                preset_frame, text=text[:20]+"...", width=80,
                command=lambda t=text: self._set_inbox_content(t)
            ).pack(side="left", padx=2)
        
        ctk.CTkButton(add_frame, text="➕ Add to Inbox", command=self._add_to_inbox).pack(pady=10)
    
    # === EVOLUTION TAB ===
    
    def _build_evolution_tab(self):
        """Build the prompt evolution tab"""
        self.tab_evolution.grid_columnconfigure(0, weight=1)
        self.tab_evolution.grid_rowconfigure(1, weight=1)
        
        # Top - Stats
        stats_frame = ctk.CTkFrame(self.tab_evolution)
        stats_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        self.gen_label = ctk.CTkLabel(stats_frame, text="Generation: 0", font=ctk.CTkFont(size=18, weight="bold"))
        self.gen_label.pack(side="left", padx=20, pady=10)
        
        self.perf_label = ctk.CTkLabel(stats_frame, text="Performance Records: 0")
        self.perf_label.pack(side="left", padx=20)
        
        ctk.CTkButton(stats_frame, text="🧠 Evolve Now", command=self._manual_evolve).pack(side="right", padx=20, pady=10)
        
        # Middle - Current prompt and evolution
        content_frame = ctk.CTkFrame(self.tab_evolution)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # Current prompt
        prompt_frame = ctk.CTkFrame(content_frame)
        prompt_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(prompt_frame, text="Current System Prompt", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        self.current_prompt_text = ctk.CTkTextbox(prompt_frame, height=250)
        self.current_prompt_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Evolution directive
        evo_frame = ctk.CTkFrame(content_frame)
        evo_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkLabel(evo_frame, text="Evolution Directive:").pack(side="left", padx=10)
        self.evo_directive = ctk.CTkEntry(evo_frame, width=400, placeholder_text="e.g., 'Focus more on compression metaphors'")
        self.evo_directive.pack(side="left", padx=10, fill="x", expand=True)
        
        ctk.CTkButton(evo_frame, text="Apply", command=self._apply_evolution).pack(side="right", padx=10, pady=5)
    
    # === LOGS TAB ===
    
    def _build_logs_tab(self):
        """Build the logs viewer tab"""
        self.tab_logs.grid_columnconfigure(0, weight=1)
        self.tab_logs.grid_rowconfigure(0, weight=1)
        
        # Log viewer
        self.log_text = ctk.CTkTextbox(self.tab_logs, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Controls
        ctrl_frame = ctk.CTkFrame(self.tab_logs, fg_color="transparent")
        ctrl_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkButton(ctrl_frame, text="↻ Refresh", command=self._refresh_logs).pack(side="left", padx=5)
        ctk.CTkButton(ctrl_frame, text="🗑 Clear", command=self._clear_logs).pack(side="left", padx=5)
        
        self.auto_scroll = ctk.CTkCheckBox(ctrl_frame, text="Auto-scroll")
        self.auto_scroll.pack(side="right", padx=5)
        self.auto_scroll.select()
    
    # === ACTIONS ===
    
    def _log(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        if self.auto_scroll.get():
            self.log_text.see("end")
        self.status_label.configure(text=message[:50])
    
    def _refresh_all(self):
        """Refresh all displays"""
        self._refresh_status()
        self._refresh_prompts()
        self._refresh_inbox()
        self._refresh_evolution()
        self._refresh_logs()
        self._log("Refreshed all displays")
    
    def _refresh_status(self):
        """Refresh status display"""
        self.status_text.delete("1.0", "end")
        
        lines = [
            "═══════════════════════════════════════",
            "         UMBRA SYSTEM STATUS",
            "═══════════════════════════════════════",
            "",
            f"[COMPONENTS]",
            f"  Ollama:     {'✓ Available' if HAS_OLLAMA else '✗ Not found'}",
            f"  Network:    Disabled (local-only)",
            f"  Prompts:    {'✓ Loaded' if HAS_INDEX else '✗ Not found'}",
            f"  Inbox:      {'✓ Loaded' if HAS_INBOX else '✗ Not found'}",
            "",
        ]
        
        if self.prompt_index:
            prompts = self.prompt_index.list_prompts()
            lines.extend([
                f"[PROMPT INDEX]",
                f"  Total Prompts: {len(prompts)}",
                f"  Keywords: {len(self.prompt_index.list_keywords())}",
                "",
            ])
        
        if self._get_evolver():
            lines.extend([
                f"[EVOLUTION]",
                f"  Generation: {self._get_evolver().generation}",
                f"  Performance Records: {len(self._get_evolver().performance_log)}",
                "",
            ])
        
        lines.extend([
            f"[MOLTBOOK]",
            f"  Status: Disabled (local-only mode)",
            "",
        ])
        
        self.status_text.insert("1.0", "\n".join(lines))
    
    def _refresh_prompts(self):
        """Refresh prompt list"""
        self.prompt_listbox.delete("1.0", "end")
        
        if not self.prompt_index:
            self.prompt_listbox.insert("1.0", "Prompt index not available")
            return
        
        prompts = self.prompt_index.list_prompts()
        for p in prompts:
            kws = ", ".join(p.get("keywords", [])[:3])
            line = f"[{p['id']}] {p['title']}\n    Keywords: {kws}\n\n"
            self.prompt_listbox.insert("end", line)
    
    def _refresh_inbox(self):
        """Refresh inbox list"""
        self.inbox_list.delete("1.0", "end")
        
        if not INBOX_DIR.exists():
            self.inbox_list.insert("1.0", "Inbox directory not found")
            return
        
        files = [f for f in INBOX_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]
        
        if not files:
            self.inbox_list.insert("1.0", "No pending files\n\nDrop files here:\n" + str(INBOX_DIR))
        else:
            self.inbox_list.insert("1.0", f"Pending files: {len(files)}\n\n")
            for f in files:
                size = f.stat().st_size
                self.inbox_list.insert("end", f"• {f.name} ({size} bytes)\n")
    
    def _refresh_evolution(self):
        """Refresh evolution display"""
        evolver = self._get_evolver()
        if not evolver:
            return
        
        self.gen_label.configure(text=f"Generation: {evolver.generation}")
        self.perf_label.configure(text=f"Performance Records: {len(evolver.performance_log)}")
        
        self.current_prompt_text.delete("1.0", "end")
        self.current_prompt_text.insert("1.0", evolver.current_prompt)
    
    def _refresh_logs(self):
        """Refresh logs from file"""
        log_file = DATA_DIR / "decision_log.json"
        if log_file.exists():
            try:
                logs = json.loads(log_file.read_text())
                self.log_text.delete("1.0", "end")
                for entry in logs[-50:]:  # Last 50
                    ts = entry.get("timestamp", "?")[:19]
                    action = entry.get("action", "?")
                    reason = entry.get("reasoning", "")[:60]
                    self.log_text.insert("end", f"[{ts}] {action}: {reason}\n")
            except:
                pass
    
    def _check_moltbook(self):
        """Check Moltbook connection status"""
        self.moltbook_status.configure(text_color="green")
        messagebox.showinfo("Local-Only", "Moltbook features are disabled in local-only mode.")
        self._log("Moltbook check skipped (disabled)")
    
    def _register_moltbook(self):
        """Register on Moltbook with auto-retry for taken names"""
        messagebox.showinfo("Local-Only", "Registration is disabled. This build does not use Moltbook.")
        self._log("Moltbook registration skipped (disabled)")
    
    def _run_single_cycle(self):
        """Run a single autonomous cycle"""
        self._log("Running single cycle...")
        
        def run():
            try:
                # --- CHANGE THIS ---
                # FROM: from umbra_integration import EnhancedAutonomousLoop
                # TO:
                from umbra_autonomous import AutonomousLoop
                
                # FROM: loop = EnhancedAutonomousLoop(dry_run=True)
                # TO:
                loop = AutonomousLoop(dry_run=True)
                # -------------------
                
                result = loop.run_single_cycle()
                self.after(0, lambda: self._log(f"Cycle complete: {result.get('action', 'done')}"))
            except Exception as e:
                self.after(0, lambda: self._log(f"Cycle error: {e}"))
        
        threading.Thread(target=run, daemon=True).start()
    
    def _trigger_evolution(self):
        """Trigger automatic evolution"""
        evolver = self._get_evolver()
        if not evolver:
            messagebox.showwarning("Evolution", "Evolver not available")
            return
        
        directive = evolver.auto_evolve()
        if directive:
            self._log(f"Evolution triggered: {directive}")
            self._refresh_evolution()
            messagebox.showinfo("Evolution", f"Evolved to generation {evolver.generation}\nDirective: {directive}")
        else:
            messagebox.showinfo("Evolution", "Not enough performance data for auto-evolution")
    
    def _process_inbox(self):
        """Process inbox files"""
        if not self.inbox:
            messagebox.showwarning("Inbox", "Inbox not available")
            return
        
        files = self.inbox.check()
        if files:
            self._log(f"Processed {len(files)} inbox files")
            for f in files:
                self._log(f"  [{f['type']}] {f['filename']}")
            self._refresh_inbox()
        else:
            self._log("No files to process")
    
    def _open_chat(self):
        """Open the chat interface"""
        chat_path = Path("core") / "uplink_v2.py"
        if not chat_path.exists():
            chat_path = Path("uplink_v2.py")
        
        if chat_path.exists():
            os.system(f'start cmd /k python "{chat_path}"')
            self._log("Opened chat interface")
        else:
            messagebox.showwarning("Chat", "uplink_v2.py not found")
    
    def _toggle_autonomous(self):
        """Start/stop autonomous loop"""
        if self.autonomous_running:
            self.autonomous_running = False
            self.auto_button.configure(text="▶ Start Autonomous", fg_color="green")
            self._log("Stopping autonomous loop...")
        else:
            self.autonomous_running = True
            self.auto_button.configure(text="⏹ Stop Autonomous", fg_color="red")
            self._log("Starting autonomous loop...")
            
            def run_loop():
                try:
                    from umbra_autonomous import AutonomousLoop
                    loop = AutonomousLoop(dry_run=False)
                    
                    while self.autonomous_running:
                        result = loop.run_single_cycle()
                        self.after(0, lambda r=result: self._log(f"Cycle: {r.get('action', 'unknown')}"))
                        
                        # Wait with interrupt check
                        import time
                        for _ in range(300):  # 5 min
                            if not self.autonomous_running:
                                break
                            time.sleep(1)
                            
                except Exception as e:
                    error_msg = str(e) # Save the error message immediately
                    self.after(0, lambda: self._log(f"Autonomous error: {error_msg}"))
                finally:
                    self.after(0, lambda: self.auto_button.configure(text="▶ Start Autonomous", fg_color="green"))
            
            self.autonomous_thread = threading.Thread(target=run_loop, daemon=True)
            self.autonomous_thread.start()
    
    # Prompt management
    def _search_prompts(self):
        """Search prompts"""
        query = self.prompt_search.get()
        if not query or not self.prompt_index:
            self._refresh_prompts()
            return
        
        keywords = [k.strip() for k in query.split(",")]
        results = self.prompt_index.search(keywords, limit=10)
        
        self.prompt_listbox.delete("1.0", "end")
        self.prompt_listbox.insert("1.0", f"Search results for: {keywords}\n\n")
        
        for pid in results:
            meta = self.prompt_index.index["prompts"].get(pid, {})
            self.prompt_listbox.insert("end", f"[{pid}] {meta.get('title', '?')}\n\n")
    
    def _on_prompt_double_click(self, event):
        """Handle double-click on prompt list"""
        # Get clicked line
        index = self.prompt_listbox.index(f"@{event.x},{event.y}")
        line = self.prompt_listbox.get(f"{index} linestart", f"{index} lineend")
        
        # Extract prompt ID
        if line.startswith("["):
            prompt_id = line.split("]")[0][1:]
            self._load_prompt(prompt_id)
    
    def _load_prompt(self, prompt_id: str):
        """Load prompt into editor"""
        if not self.prompt_index:
            return
        
        meta = self.prompt_index.index["prompts"].get(prompt_id)
        if not meta:
            return
        
        content = self.prompt_index.get_prompt(prompt_id)
        
        self.selected_prompt_id = prompt_id
        self.prompt_title.delete(0, "end")
        self.prompt_title.insert(0, meta.get("title", ""))
        self.prompt_keywords.delete(0, "end")
        self.prompt_keywords.insert(0, ", ".join(meta.get("keywords", [])))
        self.prompt_category.set(meta.get("category", "general"))
        self.prompt_content.delete("1.0", "end")
        self.prompt_content.insert("1.0", content or "")
        
        self._log(f"Loaded prompt: {prompt_id}")
    
    def _new_prompt(self):
        """Clear editor for new prompt"""
        self.selected_prompt_id = None
        self.prompt_title.delete(0, "end")
        self.prompt_keywords.delete(0, "end")
        self.prompt_category.set("user")
        self.prompt_content.delete("1.0", "end")
        self._log("New prompt")
    
    def _save_prompt(self):
        """Save prompt"""
        if not self.prompt_index:
            return
        
        title = self.prompt_title.get()
        keywords = [k.strip() for k in self.prompt_keywords.get().split(",")]
        category = self.prompt_category.get()
        content = self.prompt_content.get("1.0", "end").strip()
        
        if not title or not content:
            messagebox.showwarning("Save", "Title and content required")
            return
        
        if self.selected_prompt_id:
            # Update existing - delete and recreate
            self.prompt_index.delete_prompt(self.selected_prompt_id)
        
        new_id = self.prompt_index.add_prompt(title, content, keywords, category)
        self.selected_prompt_id = new_id
        
        self._refresh_prompts()
        self._log(f"Saved prompt: {new_id}")
    
    def _delete_prompt(self):
        """Delete selected prompt"""
        if not self.selected_prompt_id:
            messagebox.showwarning("Delete", "No prompt selected")
            return
        
        if messagebox.askyesno("Delete", f"Delete prompt {self.selected_prompt_id}?"):
            self.prompt_index.delete_prompt(self.selected_prompt_id)
            self._new_prompt()
            self._refresh_prompts()
            self._log(f"Deleted prompt: {self.selected_prompt_id}")
    
    # Inbox management
    def _open_inbox_folder(self):
        """Open inbox folder in explorer"""
        os.startfile(str(INBOX_DIR))
    
    def _clear_processed(self):
        """Clear processed folder"""
        processed = INBOX_DIR / "processed"
        count = 0
        for f in processed.iterdir():
            if f.is_file():
                f.unlink()
                count += 1
        self._log(f"Cleared {count} processed files")
    
    def _set_inbox_content(self, content: str):
        """Set inbox content from preset"""
        self.inbox_content.delete("1.0", "end")
        self.inbox_content.insert("1.0", content)
    
    def _add_to_inbox(self):
        """Add content to inbox"""
        content = self.inbox_content.get("1.0", "end").strip()
        file_type = self.inbox_type.get()
        
        if not content:
            messagebox.showwarning("Inbox", "Content required")
            return
        
        ext_map = {
            "instruction": ".instruction",
            "context": ".context",
            "prompt": ".prompt"
        }
        ext = ext_map.get(file_type, ".txt")
        
        filename = f"{file_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        filepath = INBOX_DIR / filename
        filepath.write_text(content)
        
        self._log(f"Added to inbox: {filename}")
        self._refresh_inbox()
        self.inbox_content.delete("1.0", "end")
    
    # Evolution
    def _manual_evolve(self):
        """Trigger manual evolution with auto-generated directive"""
        self._trigger_evolution()
    
    def _apply_evolution(self):
        """Apply custom evolution directive"""
        evolver = self._get_evolver()
        if not evolver:
            messagebox.showwarning("Evolution", "Evolver not available")
            return
        
        directive = self.evo_directive.get()
        if not directive:
            messagebox.showwarning("Evolution", "Enter a directive")
            return
        
        evolver.evolve(directive)
        self._refresh_evolution()
        self._log(f"Applied evolution: {directive}")
        self.evo_directive.delete(0, "end")
    
    def _clear_logs(self):
        """Clear log display"""
        self.log_text.delete("1.0", "end")


def main():
    app = UmbraGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
