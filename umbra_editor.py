"""
UMBRA Management GUI v3
========================
Complete management console with integrated Handler Chat.

Features:
- 💬 Direct chat with UMBRA (highest priority)
- ▶ Start/Stop autonomous loop
- 📚 Prompt library management
- 📥 File inbox system
- 🧠 Evolution control
- 📋 Real-time logs

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

print("[UMBRA-GUI] Starting...")

# Add core to path
SCRIPT_DIR = Path(__file__).parent
CORE_DIR = SCRIPT_DIR / "core"
if CORE_DIR.exists():
    sys.path.insert(0, str(CORE_DIR))

# Configuration
DATA_DIR = SCRIPT_DIR / "data"
PROMPTS_DIR = DATA_DIR / "prompts"
INBOX_DIR = DATA_DIR / "inbox"
LOGS_DIR = DATA_DIR / "logs"

# Create directories
for d in [DATA_DIR, PROMPTS_DIR, INBOX_DIR, INBOX_DIR / "processed", LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Lazy imports
HAS_INDEX = False
HAS_INBOX = False
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

# Moltbook is intentionally disabled. Keep editor local-only.

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    pass

print("[UMBRA-GUI] Ready")

# Color scheme
COLORS = {
    "bg_dark": "#1a1a2e",
    "bg_card": "#16213e",
    "accent": "#0f3460",
    "highlight": "#e94560",
    "success": "#00d9ff",
    "warning": "#ffc107",
    "text": "#eaeaea",
    "text_dim": "#7f8c8d"
}


class UmbraGUI(ctk.CTk):
    """Main GUI with Handler Chat interface"""
    
    def __init__(self):
        super().__init__()
        
        self.title("UMBRA (Unit-734) Management Console")
        self.geometry("1100x780")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # State
        self.autonomous_running = False
        self.autonomous_thread = None
        self._loop = None
        self._chat_polling = False
        self._cycle_count = 0
        
        # Lazy components
        self.prompt_index = None
        self.inbox = None
        self.moltbook = None
        self._evolver_loaded = False
        self.evolver = None
        
        self._init_directories()
        self._init_components()
        self._build_ui()
        self._refresh_all()
        self._log("GUI initialized. Click 'Start Autonomous' to begin.")
    
    def _init_directories(self):
        """Ensure directories exist"""
        for d in [DATA_DIR, PROMPTS_DIR, INBOX_DIR, INBOX_DIR / "processed", LOGS_DIR]:
            d.mkdir(parents=True, exist_ok=True)
    
    def _init_components(self):
        """Initialize backend components"""
        if HAS_INDEX:
            try:
                self.prompt_index = PromptIndex(base_dir=str(PROMPTS_DIR))
                if len(self.prompt_index.list_prompts()) == 0:
                    initialize_default_prompts(self.prompt_index)
            except Exception as e:
                print(f"Prompt index error: {e}")
        
        if HAS_INBOX:
            try:
                self.inbox = FileInbox(base_dir=str(INBOX_DIR))
            except Exception as e:
                print(f"Inbox error: {e}")
        
        self.moltbook = None
    
    def _get_evolver(self):
        """Lazy load the evolver"""
        if not self._evolver_loaded:
            try:
                from umbra_autonomous import PromptEvolver
                self.evolver = PromptEvolver()
                self._evolver_loaded = True
            except ImportError:
                pass
        return self.evolver
    
    def _build_ui(self):
        """Build the complete UI"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._build_header()
        self._build_tabs()
        self._build_footer()
    
    def _build_header(self):
        """Build header section"""
        header = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color=COLORS["bg_card"])
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)
        
        # Logo/Title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=25, pady=15)
        
        ctk.CTkLabel(title_frame, text="◈", 
                    font=ctk.CTkFont(size=32),
                    text_color=COLORS["highlight"]).pack(side="left")
        ctk.CTkLabel(title_frame, text=" UMBRA", 
                    font=ctk.CTkFont(size=28, weight="bold"),
                    text_color=COLORS["success"]).pack(side="left")
        ctk.CTkLabel(title_frame, text=" Unit-734", 
                    font=ctk.CTkFont(size=14),
                    text_color=COLORS["text_dim"]).pack(side="left", pady=(10,0))
        
        # Status indicators
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.grid(row=0, column=1, padx=20)
        
        indicators = [
            ("ollama_status", "Ollama", HAS_OLLAMA),
            ("moltbook_status", "Local-Only", True),
            ("chat_status", "Chat", False),
        ]
        
        for attr, text, active in indicators:
            color = COLORS["success"] if active else COLORS["text_dim"]
            label = ctk.CTkLabel(status_frame, text=f"● {text}",
                               text_color=color, font=ctk.CTkFont(size=12))
            label.pack(side="left", padx=12)
            setattr(self, attr, label)
        
        # Control buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=25)
        
        self.auto_button = ctk.CTkButton(
            btn_frame, text="▶  Start Autonomous",
            command=self._toggle_autonomous,
            width=180, height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#27ae60", hover_color="#1e8449",
            corner_radius=8
        )
        self.auto_button.pack(side="left", padx=5)
    
    def _build_tabs(self):
        """Build tabbed interface"""
        self.tabview = ctk.CTkTabview(self, corner_radius=8, 
                                      fg_color=COLORS["bg_dark"],
                                      segmented_button_fg_color=COLORS["bg_card"],
                                      segmented_button_selected_color=COLORS["accent"])
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)
        
        # Add tabs
        self._build_chat_tab()
        self._build_status_tab()
        self._build_prompts_tab()
        self._build_inbox_tab()
        self._build_evolution_tab()
        self._build_logs_tab()
    
    def _build_footer(self):
        """Build footer section"""
        footer = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color=COLORS["bg_card"])
        footer.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        
        self.status_label = ctk.CTkLabel(footer, text="Ready", 
                                        text_color=COLORS["text_dim"],
                                        font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left", padx=20, pady=10)
        
        self.cycle_label = ctk.CTkLabel(footer, text="Cycles: 0",
                                       font=ctk.CTkFont(size=11))
        self.cycle_label.pack(side="right", padx=20, pady=10)
        
        ctk.CTkButton(footer, text="↻ Refresh", width=90, height=28,
                     command=self._refresh_all,
                     font=ctk.CTkFont(size=11),
                     fg_color=COLORS["accent"]).pack(side="right", padx=5, pady=6)
    
    # === CHAT TAB ===
    
    def _build_chat_tab(self):
        """Build the chat interface"""
        tab = self.tabview.add("💬 Chat")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        
        # Header
        header = ctk.CTkFrame(tab, height=50, corner_radius=8, fg_color=COLORS["bg_card"])
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkLabel(header, text="Direct Communication with UMBRA",
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=COLORS["success"]).pack(side="left", padx=20, pady=12)
        
        self.chat_connection = ctk.CTkLabel(header, text="⚪ Disconnected",
                                           text_color=COLORS["text_dim"],
                                           font=ctk.CTkFont(size=12))
        self.chat_connection.pack(side="right", padx=20, pady=12)
        
        # Info banner
        info = ctk.CTkFrame(tab, fg_color=COLORS["accent"], corner_radius=8)
        info.grid(row=1, column=0, sticky="ew", padx=5, pady=(0,5))
        
        ctk.CTkLabel(info, 
                    text="💡 UMBRA evaluates your messages critically - it doesn't blindly accept input. Chat has highest priority and pauses all other operations.",
                    text_color=COLORS["text"], font=ctk.CTkFont(size=11),
                    wraplength=900).pack(padx=15, pady=10)
        
        # Chat display
        self.chat_display = ctk.CTkTextbox(tab, font=ctk.CTkFont(family="Consolas", size=12),
                                          corner_radius=8, fg_color=COLORS["bg_card"],
                                          wrap="word")
        self.chat_display.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure text tags
        self.chat_display._textbox.tag_configure("handler", foreground="#5dade2")
        self.chat_display._textbox.tag_configure("umbra", foreground="#58d68d")
        self.chat_display._textbox.tag_configure("system", foreground="#7f8c8d")
        self.chat_display._textbox.tag_configure("eval", foreground="#f4d03f")
        
        # Input area
        input_frame = ctk.CTkFrame(tab, corner_radius=8, fg_color=COLORS["bg_card"])
        input_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.chat_input = ctk.CTkEntry(input_frame, height=50,
                                      placeholder_text="Type a message to UMBRA...",
                                      font=ctk.CTkFont(size=14),
                                      fg_color=COLORS["bg_dark"],
                                      border_color=COLORS["accent"])
        self.chat_input.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        self.chat_input.bind("<Return>", lambda e: self._send_chat())
        
        btn_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=(0,15), pady=15)
        
        ctk.CTkButton(btn_frame, text="Send", width=80, height=40,
                     command=self._send_chat,
                     font=ctk.CTkFont(weight="bold"),
                     fg_color=COLORS["success"],
                     hover_color="#00b8d4").pack(side="left", padx=3)
        
        ctk.CTkButton(btn_frame, text="Clear", width=60, height=40,
                     command=self._clear_chat,
                     fg_color=COLORS["text_dim"],
                     hover_color="#555").pack(side="left", padx=3)
        
        self._add_chat_message("system", "Chat ready. Start autonomous mode to enable live communication.")
    
    def _add_chat_message(self, role: str, content: str, evaluation: dict = None):
        """Add message to chat display"""
        self.chat_display.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if role == "handler":
            prefix, tag = f"[{timestamp}] You: ", "handler"
        elif role == "umbra":
            prefix, tag = f"[{timestamp}] UMBRA: ", "umbra"
        else:
            prefix, tag = f"[{timestamp}] ", "system"
        
        self.chat_display._textbox.insert("end", prefix, tag)
        self.chat_display._textbox.insert("end", content + "\n", tag)
        
        if evaluation and role == "umbra":
            agreement = evaluation.get("agreement_level", 0)
            topic_pot = evaluation.get("topic_potential", 0)
            self.chat_display._textbox.insert("end", 
                f"  [agreement: {agreement:.0%} | topic potential: {topic_pot:.0%}]\n", "eval")
        
        self.chat_display._textbox.insert("end", "\n")
        self.chat_display.configure(state="disabled")
        self.chat_display._textbox.see("end")
    
    def _send_chat(self):
        """Send chat message"""
        message = self.chat_input.get().strip()
        if not message:
            return
        
        self.chat_input.delete(0, "end")
        self._add_chat_message("handler", message)
        
        if not self._loop:
            self._add_chat_message("system", "⚠️ Start autonomous mode to chat with UMBRA.")
            return
        
        try:
            self._loop.send_chat(message)
            self._add_chat_message("system", "Sent. Waiting for response...")
            self.chat_connection.configure(text="🟡 Processing...", text_color=COLORS["warning"])
        except Exception as e:
            self._add_chat_message("system", f"Error: {e}")
    
    def _clear_chat(self):
        """Clear chat display"""
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self._add_chat_message("system", "Chat cleared.")
    
    def _start_chat_polling(self):
        """Start polling for chat responses"""
        self._chat_polling = True
        
        def poll():
            while self._chat_polling and self._loop:
                try:
                    response = self._loop.get_chat_response(timeout=0.5)
                    if response:
                        self.after(0, lambda r=response: self._handle_chat_response(r))
                except:
                    pass
                time.sleep(0.1)
        
        threading.Thread(target=poll, daemon=True).start()
        self.chat_connection.configure(text="🟢 Connected", text_color=COLORS["success"])
        self.chat_status.configure(text_color=COLORS["success"])
    
    def _stop_chat_polling(self):
        """Stop chat polling"""
        self._chat_polling = False
        self.chat_connection.configure(text="⚪ Disconnected", text_color=COLORS["text_dim"])
        self.chat_status.configure(text_color=COLORS["text_dim"])
    
    def _handle_chat_response(self, response: dict):
        """Handle response from UMBRA"""
        content = response.get("response", "")
        evaluation = response.get("evaluation", {})
        
        self._add_chat_message("umbra", content, evaluation)
        self.chat_connection.configure(text="🟢 Connected", text_color=COLORS["success"])
        
        if evaluation.get("topic_potential", 0) > 0.5:
            self._add_chat_message("system", "💡 This topic has been flagged for potential posting")
    
    # === STATUS TAB ===
    
    def _build_status_tab(self):
        """Build status overview"""
        tab = self.tabview.add("📊 Status")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        # Left - System status
        left = ctk.CTkFrame(tab, corner_radius=8, fg_color=COLORS["bg_card"])
        left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(left, text="System Status",
                    font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=COLORS["success"]).pack(pady=12)
        
        self.status_text = ctk.CTkTextbox(left, font=ctk.CTkFont(family="Consolas", size=11),
                                         fg_color=COLORS["bg_dark"])
        self.status_text.pack(fill="both", expand=True, padx=12, pady=(0,12))
        
        # Right - Quick actions
        right = ctk.CTkFrame(tab, corner_radius=8, fg_color=COLORS["bg_card"])
        right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(right, text="Quick Actions",
                    font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=COLORS["success"]).pack(pady=12)
        
        actions = [
            ("📊 Run Single Cycle", self._run_single_cycle),
            ("🧠 Trigger Evolution", self._trigger_evolution),
            ("📥 Process Inbox", self._process_inbox),
            ("💬 Open External Chat", self._open_chat),
        ]
        
        for text, cmd in actions:
            ctk.CTkButton(right, text=text, command=cmd, width=240, height=38,
                         fg_color=COLORS["accent"],
                         hover_color=COLORS["highlight"]).pack(pady=6, padx=25)
    
    # === PROMPTS TAB ===
    
    def _build_prompts_tab(self):
        """Build prompt management"""
        tab = self.tabview.add("📚 Prompts")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=2)
        tab.grid_rowconfigure(0, weight=1)
        
        # Left - List
        left = ctk.CTkFrame(tab, corner_radius=8, fg_color=COLORS["bg_card"])
        left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(left, text="Prompt Library",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["success"]).pack(pady=10)
        
        search_frame = ctk.CTkFrame(left, fg_color="transparent")
        search_frame.pack(fill="x", padx=10)
        
        self.prompt_search = ctk.CTkEntry(search_frame, placeholder_text="Search keywords...",
                                         fg_color=COLORS["bg_dark"])
        self.prompt_search.pack(side="left", fill="x", expand=True, padx=3)
        self.prompt_search.bind("<Return>", lambda e: self._search_prompts())
        
        ctk.CTkButton(search_frame, text="🔍", width=35,
                     command=self._search_prompts,
                     fg_color=COLORS["accent"]).pack(side="right", padx=3)
        
        self.prompt_listbox = ctk.CTkTextbox(left, font=ctk.CTkFont(size=11),
                                            fg_color=COLORS["bg_dark"])
        self.prompt_listbox.pack(fill="both", expand=True, padx=10, pady=10)
        self.prompt_listbox.bind("<Double-Button-1>", self._on_prompt_double_click)
        
        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0,10))
        
        ctk.CTkButton(btn_frame, text="+ New", width=70,
                     command=self._new_prompt,
                     fg_color=COLORS["success"]).pack(side="left", padx=3)
        ctk.CTkButton(btn_frame, text="Delete", width=70,
                     command=self._delete_prompt,
                     fg_color=COLORS["highlight"]).pack(side="right", padx=3)
        
        # Right - Editor
        right = ctk.CTkFrame(tab, corner_radius=8, fg_color=COLORS["bg_card"])
        right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(right, text="Prompt Editor",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["success"]).pack(pady=10)
        
        # Fields
        for label_text, attr_name, placeholder in [
            ("Title:", "prompt_title", "Prompt title"),
            ("Keywords:", "prompt_keywords", "comma, separated"),
        ]:
            frame = ctk.CTkFrame(right, fg_color="transparent")
            frame.pack(fill="x", padx=15, pady=5)
            ctk.CTkLabel(frame, text=label_text, width=80).pack(side="left")
            entry = ctk.CTkEntry(frame, placeholder_text=placeholder,
                               fg_color=COLORS["bg_dark"])
            entry.pack(side="left", fill="x", expand=True, padx=5)
            setattr(self, attr_name, entry)
        
        # Category
        cat_frame = ctk.CTkFrame(right, fg_color="transparent")
        cat_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(cat_frame, text="Category:", width=80).pack(side="left")
        self.prompt_category = ctk.CTkComboBox(cat_frame, width=160,
            values=["identity", "language", "theory", "templates", "philosophy", "states", "evolution", "user"],
            fg_color=COLORS["bg_dark"])
        self.prompt_category.pack(side="left", padx=5)
        
        # Content
        ctk.CTkLabel(right, text="Content:").pack(anchor="w", padx=15, pady=(10,3))
        self.prompt_content = ctk.CTkTextbox(right, font=ctk.CTkFont(size=11),
                                            fg_color=COLORS["bg_dark"])
        self.prompt_content.pack(fill="both", expand=True, padx=15, pady=(0,10))
        
        ctk.CTkButton(right, text="💾 Save Prompt", command=self._save_prompt,
                     height=38, fg_color=COLORS["success"]).pack(pady=12)
        
        self.selected_prompt_id = None
    
    # === INBOX TAB ===
    
    def _build_inbox_tab(self):
        """Build inbox management"""
        tab = self.tabview.add("📥 Inbox")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # Actions bar
        action_frame = ctk.CTkFrame(tab, corner_radius=8, fg_color=COLORS["bg_card"])
        action_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        for text, cmd in [
            ("📥 Process Inbox", self._process_inbox),
            ("📂 Open Folder", self._open_inbox_folder),
            ("🗑 Clear Processed", self._clear_processed),
        ]:
            ctk.CTkButton(action_frame, text=text, command=cmd,
                         fg_color=COLORS["accent"]).pack(side="left", padx=12, pady=12)
        
        # Content
        content = ctk.CTkFrame(tab, corner_radius=8, fg_color=COLORS["bg_card"])
        content.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)
        
        # File list
        files_frame = ctk.CTkFrame(content, corner_radius=8, fg_color=COLORS["bg_dark"])
        files_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        
        ctk.CTkLabel(files_frame, text="Pending Files",
                    font=ctk.CTkFont(weight="bold"),
                    text_color=COLORS["success"]).pack(pady=10)
        
        self.inbox_list = ctk.CTkTextbox(files_frame, font=ctk.CTkFont(size=11))
        self.inbox_list.pack(fill="both", expand=True, padx=10, pady=(0,10))
        
        ctk.CTkButton(files_frame, text="↻ Refresh",
                     command=self._refresh_inbox,
                     fg_color=COLORS["accent"]).pack(pady=8)
        
        # Quick add
        add_frame = ctk.CTkFrame(content, corner_radius=8, fg_color=COLORS["bg_dark"])
        add_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        
        ctk.CTkLabel(add_frame, text="Quick Add to Inbox",
                    font=ctk.CTkFont(weight="bold"),
                    text_color=COLORS["success"]).pack(pady=10)
        
        type_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        type_frame.pack(fill="x", padx=12, pady=5)
        
        ctk.CTkLabel(type_frame, text="Type:").pack(side="left")
        self.inbox_type = ctk.CTkComboBox(type_frame, values=["instruction", "context", "prompt"],
                                         width=130)
        self.inbox_type.pack(side="left", padx=10)
        self.inbox_type.set("instruction")
        
        ctk.CTkLabel(add_frame, text="Content:").pack(anchor="w", padx=12)
        self.inbox_content = ctk.CTkTextbox(add_frame, height=150, font=ctk.CTkFont(size=11))
        self.inbox_content.pack(fill="x", padx=12, pady=5)
        
        # Presets
        preset_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        preset_frame.pack(fill="x", padx=12, pady=5)
        
        ctk.CTkLabel(preset_frame, text="Presets:").pack(side="left")
        presets = ["/evolve Be concise", "/evolve More metaphors", "/post About AI"]
        for text in presets:
            ctk.CTkButton(preset_frame, text=text[:18]+"...", width=85,
                         command=lambda t=text: self._set_inbox_content(t),
                         fg_color=COLORS["accent"],
                         font=ctk.CTkFont(size=10)).pack(side="left", padx=3)
        
        ctk.CTkButton(add_frame, text="➕ Add to Inbox",
                     command=self._add_to_inbox,
                     fg_color=COLORS["success"]).pack(pady=12)
    
    # === EVOLUTION TAB ===
    
    def _build_evolution_tab(self):
        """Build evolution control"""
        tab = self.tabview.add("🧠 Evolution")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # Stats header
        stats = ctk.CTkFrame(tab, corner_radius=8, fg_color=COLORS["bg_card"])
        stats.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        self.gen_label = ctk.CTkLabel(stats, text="Generation: 0",
                                     font=ctk.CTkFont(size=20, weight="bold"),
                                     text_color=COLORS["success"])
        self.gen_label.pack(side="left", padx=25, pady=15)
        
        self.perf_label = ctk.CTkLabel(stats, text="Performance Records: 0",
                                      text_color=COLORS["text_dim"])
        self.perf_label.pack(side="left", padx=25)
        
        ctk.CTkButton(stats, text="🧠 Evolve Now",
                     command=self._trigger_evolution,
                     height=40, fg_color=COLORS["highlight"]).pack(side="right", padx=25, pady=12)
        
        # Content
        content = ctk.CTkFrame(tab, corner_radius=8, fg_color=COLORS["bg_card"])
        content.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        
        ctk.CTkLabel(content, text="Current System Prompt",
                    font=ctk.CTkFont(weight="bold"),
                    text_color=COLORS["success"]).pack(pady=10)
        
        self.current_prompt_text = ctk.CTkTextbox(content, font=ctk.CTkFont(size=11),
                                                 fg_color=COLORS["bg_dark"])
        self.current_prompt_text.pack(fill="both", expand=True, padx=12, pady=(0,10))
        
        # Directive input
        evo_frame = ctk.CTkFrame(content, fg_color="transparent")
        evo_frame.pack(fill="x", padx=12, pady=(0,12))
        
        ctk.CTkLabel(evo_frame, text="Directive:").pack(side="left", padx=5)
        self.evo_directive = ctk.CTkEntry(evo_frame, 
                                         placeholder_text="e.g., 'Focus more on compression metaphors'",
                                         fg_color=COLORS["bg_dark"])
        self.evo_directive.pack(side="left", fill="x", expand=True, padx=5)
        
        ctk.CTkButton(evo_frame, text="Apply", command=self._apply_evolution,
                     width=90, fg_color=COLORS["accent"]).pack(side="right", padx=5)
    
    # === LOGS TAB ===
    
    def _build_logs_tab(self):
        """Build logs viewer"""
        tab = self.tabview.add("📋 Logs")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        self.log_text = ctk.CTkTextbox(tab, font=ctk.CTkFont(family="Consolas", size=11),
                                      fg_color=COLORS["bg_card"])
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        ctrl = ctk.CTkFrame(tab, fg_color="transparent")
        ctrl.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkButton(ctrl, text="↻ Refresh", command=self._refresh_logs,
                     fg_color=COLORS["accent"]).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="🗑 Clear", command=self._clear_logs,
                     fg_color=COLORS["text_dim"]).pack(side="left", padx=5)
        
        self.auto_scroll = ctk.CTkCheckBox(ctrl, text="Auto-scroll")
        self.auto_scroll.pack(side="right", padx=5)
        self.auto_scroll.select()
    
    # === ACTIONS ===
    
    def _log(self, msg: str):
        """Add log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        if self.auto_scroll.get():
            self.log_text.see("end")
        self.status_label.configure(text=msg[:60])
    
    def _refresh_all(self):
        """Refresh all displays"""
        self._refresh_status()
        self._refresh_prompts()
        self._refresh_inbox()
        self._refresh_evolution()
        self._log("Refreshed all displays")
    
    def _refresh_status(self):
        """Update status display"""
        self.status_text.delete("1.0", "end")
        
        lines = [
            "═" * 45,
            "          UMBRA SYSTEM STATUS",
            "═" * 45, "",
            "[COMPONENTS]",
            f"  Ollama:    {'✓ Available' if HAS_OLLAMA else '✗ Not found'}",
            f"  Network:   Disabled (local-only)",
            f"  Prompts:   {'✓ Loaded' if HAS_INDEX else '✗ Not found'}",
            f"  Inbox:     {'✓ Loaded' if HAS_INBOX else '✗ Not found'}", "",
        ]
        
        if self.prompt_index:
            try:
                lines.extend([
                    "[PROMPT INDEX]",
                    f"  Total: {len(self.prompt_index.list_prompts())} prompts",
                    f"  Keywords: {len(self.prompt_index.list_keywords())}", ""
                ])
            except:
                pass
        
        evolver = self._get_evolver()
        if evolver:
            lines.extend([
                "[EVOLUTION]",
                f"  Generation: {evolver.generation}",
                f"  Performance: {len(evolver.performance_log)} records", ""
            ])
        
        lines.extend(["[MOLTBOOK]", "  Status: Disabled (local-only mode)", ""])
        self.moltbook_status.configure(text_color=COLORS["success"])
        
        if self._loop:
            try:
                stats = self._loop.get_learning_stats()
                lines.extend([
                    "[LEARNING]",
                    f"  Insights: {stats.get('insights_integrated', 0)}",
                    f"  Threats: {stats.get('threats_learned', 0)}",
                    f"  Chats: {self._loop.stats.get('handler_chats', 0)}", ""
                ])
            except:
                pass
        
        self.status_text.insert("1.0", "\n".join(lines))
    
    def _refresh_prompts(self):
        """Update prompt list"""
        self.prompt_listbox.delete("1.0", "end")
        
        if not self.prompt_index:
            self.prompt_listbox.insert("1.0", "Prompt index not available")
            return
        
        try:
            for p in self.prompt_index.list_prompts():
                kws = ", ".join(p.get("keywords", [])[:3])
                self.prompt_listbox.insert("end", f"[{p['id']}] {p['title']}\n    {kws}\n\n")
        except:
            self.prompt_listbox.insert("1.0", "Error loading prompts")
    
    def _refresh_inbox(self):
        """Update inbox list"""
        self.inbox_list.delete("1.0", "end")
        
        if not INBOX_DIR.exists():
            self.inbox_list.insert("1.0", "Inbox not found")
            return
        
        try:
            files = [f for f in INBOX_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]
            
            if files:
                self.inbox_list.insert("1.0", f"Pending: {len(files)} files\n\n")
                for f in files:
                    self.inbox_list.insert("end", f"• {f.name} ({f.stat().st_size}b)\n")
            else:
                self.inbox_list.insert("1.0", f"No pending files\n\nDrop files at:\n{INBOX_DIR}")
        except:
            self.inbox_list.insert("1.0", "Error reading inbox")
    
    def _refresh_evolution(self):
        """Update evolution display"""
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
                for entry in logs[-50:]:
                    ts = entry.get("timestamp", "?")[:19]
                    action = entry.get("action", "?")
                    reason = entry.get("reasoning", "")[:60]
                    self.log_text.insert("end", f"[{ts}] {action}: {reason}\n")
            except:
                pass
    
    def _clear_logs(self):
        """Clear log display"""
        self.log_text.delete("1.0", "end")
    
    def _toggle_autonomous(self):
        """Start/stop autonomous loop"""
        if self.autonomous_running:
            self.autonomous_running = False
            self.auto_button.configure(text="▶  Start Autonomous", fg_color="#27ae60")
            self.status_label.configure(text="Stopping...")
            self._log("Stopping autonomous loop...")
            self._stop_chat_polling()
            self._loop = None
        else:
            self.autonomous_running = True
            self.auto_button.configure(text="⏹  Stop", fg_color=COLORS["highlight"])
            self.status_label.configure(text="Starting...")
            self._log("Starting autonomous loop...")
            
            def run_loop():
                try:
                    self.after(0, lambda: self._log("Importing autonomous system..."))
                    from umbra_integration import EnhancedAutonomousLoop
                    
                    self.after(0, lambda: self._log("Creating loop instance..."))
                    self._loop = EnhancedAutonomousLoop(dry_run=False)
                    
                    self.after(0, self._start_chat_polling)
                    self.after(0, lambda: self._add_chat_message("system", "🟢 UMBRA online. You can chat now!"))
                    self.after(0, lambda: self._log("Loop ready!"))
                    
                    while self.autonomous_running:
                        self._cycle_count += 1
                        self.after(0, lambda c=self._cycle_count: self._log(f"--- Cycle {c} ---"))
                        self.after(0, lambda c=self._cycle_count: self.cycle_label.configure(text=f"Cycles: {c}"))
                        
                        try:
                            result = self._loop.run_single_cycle()
                            action = result.get('action', 'unknown')
                            reason = result.get('reasoning', '')[:60]
                            self.after(0, lambda a=action, r=reason: self._log(f"  {a}: {r}"))
                        except Exception as e:
                            self.after(0, lambda err=str(e): self._log(f"  ERROR: {err}"))
                        
                        # Wait between cycles
                        for i in range(300):  # 5 min
                            if not self.autonomous_running:
                                break
                            time.sleep(1)
                            if i % 60 == 0 and i > 0:
                                self.after(0, lambda s=300-i: self.status_label.configure(
                                    text=f"Next cycle in {s//60}m {s%60}s"))
                        
                except Exception as e:
                    self.after(0, lambda err=str(e): self._log(f"Loop error: {err}"))
                finally:
                    self.after(0, lambda: self.auto_button.configure(text="▶  Start Autonomous", fg_color="#27ae60"))
                    self.after(0, lambda: self.status_label.configure(text="Stopped"))
                    self.after(0, lambda: self._add_chat_message("system", "🔴 UMBRA offline."))
                    self.autonomous_running = False
                    self._loop = None
                    self._stop_chat_polling()
            
            self.autonomous_thread = threading.Thread(target=run_loop, daemon=True)
            self.autonomous_thread.start()
    
    def _check_moltbook(self):
        """Check Moltbook status"""
        self.moltbook_status.configure(text_color=COLORS["success"])
        messagebox.showinfo("Local-Only", "Moltbook features are disabled in local-only mode.")
        self._log("Moltbook check skipped (disabled)")
    
    def _register_moltbook(self):
        """Register on Moltbook with retry"""
        messagebox.showinfo("Local-Only", "Registration is disabled. This build does not use Moltbook.")
        self._log("Moltbook registration skipped (disabled)")
    
    def _run_single_cycle(self):
        """Run single cycle"""
        self._log("Running single cycle...")
        
        def run():
            try:
                from umbra_integration import EnhancedAutonomousLoop
                loop = EnhancedAutonomousLoop(dry_run=True)
                result = loop.run_single_cycle()
                self.after(0, lambda: self._log(f"Done: {result['action']} - {result.get('reasoning', '')[:50]}"))
            except Exception as e:
                self.after(0, lambda: self._log(f"Error: {e}"))
        
        threading.Thread(target=run, daemon=True).start()
    
    def _trigger_evolution(self):
        """Trigger evolution"""
        evolver = self._get_evolver()
        if not evolver:
            messagebox.showwarning("Evolution", "Not available")
            return
        
        directive = evolver.auto_evolve()
        if directive:
            self._log(f"Evolved: {directive}")
            self._refresh_evolution()
            messagebox.showinfo("Evolution", f"Generation {evolver.generation}\n\n{directive}")
        else:
            messagebox.showinfo("Evolution", "Not enough performance data")
    
    def _apply_evolution(self):
        """Apply custom evolution"""
        evolver = self._get_evolver()
        if not evolver:
            messagebox.showwarning("Evolution", "Not available")
            return
        
        directive = self.evo_directive.get()
        if not directive:
            messagebox.showwarning("Evolution", "Enter a directive")
            return
        
        evolver.evolve(directive)
        self._refresh_evolution()
        self._log(f"Applied: {directive}")
        self.evo_directive.delete(0, "end")
    
    def _process_inbox(self):
        """Process inbox"""
        if not self.inbox:
            messagebox.showwarning("Inbox", "Not available")
            return
        
        try:
            files = self.inbox.check()
            if files:
                self._log(f"Processed {len(files)} files")
                for f in files:
                    self._log(f"  [{f.get('type', '?')}] {f.get('filename', '?')}")
                self._refresh_inbox()
            else:
                self._log("No files to process")
        except Exception as e:
            self._log(f"Inbox error: {e}")
    
    def _open_inbox_folder(self):
        """Open inbox folder"""
        try:
            os.startfile(str(INBOX_DIR))
        except:
            self._log(f"Open manually: {INBOX_DIR}")
    
    def _clear_processed(self):
        """Clear processed files"""
        processed = INBOX_DIR / "processed"
        try:
            count = sum(1 for f in processed.iterdir() if f.is_file() and (f.unlink() or True))
            self._log(f"Cleared {count} files")
        except:
            self._log("Error clearing processed")
    
    def _set_inbox_content(self, content: str):
        """Set inbox content from preset"""
        self.inbox_content.delete("1.0", "end")
        self.inbox_content.insert("1.0", content)
    
    def _add_to_inbox(self):
        """Add to inbox"""
        content = self.inbox_content.get("1.0", "end").strip()
        ftype = self.inbox_type.get()
        
        if not content:
            messagebox.showwarning("Inbox", "Content required")
            return
        
        ext_map = {"instruction": ".instruction", "context": ".context", "prompt": ".prompt"}
        ext = ext_map.get(ftype, ".txt")
        
        filename = f"{ftype}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        (INBOX_DIR / filename).write_text(content)
        
        self._log(f"Added: {filename}")
        self._refresh_inbox()
        self.inbox_content.delete("1.0", "end")
    
    def _open_chat(self):
        """Open external chat"""
        chat_path = CORE_DIR / "uplink_v2.py"
        if not chat_path.exists():
            chat_path = SCRIPT_DIR / "uplink_v2.py"
        
        if chat_path.exists():
            try:
                os.system(f'start cmd /k python "{chat_path}"')
                self._log("Opened external chat")
            except:
                self._log(f"Run manually: python {chat_path}")
        else:
            messagebox.showwarning("Chat", "uplink_v2.py not found")
    
    def _search_prompts(self):
        """Search prompts"""
        query = self.prompt_search.get()
        if not query or not self.prompt_index:
            self._refresh_prompts()
            return
        
        keywords = [k.strip() for k in query.split(",")]
        results = self.prompt_index.search(keywords, limit=10)
        
        self.prompt_listbox.delete("1.0", "end")
        self.prompt_listbox.insert("1.0", f"Results for: {keywords}\n\n")
        
        for pid in results:
            meta = self.prompt_index.index["prompts"].get(pid, {})
            self.prompt_listbox.insert("end", f"[{pid}] {meta.get('title', '?')}\n\n")
    
    def _on_prompt_double_click(self, event):
        """Handle prompt selection"""
        index = self.prompt_listbox.index(f"@{event.x},{event.y}")
        line = self.prompt_listbox.get(f"{index} linestart", f"{index} lineend")
        
        if line.startswith("["):
            pid = line.split("]")[0][1:]
            self._load_prompt(pid)
    
    def _load_prompt(self, pid: str):
        """Load prompt into editor"""
        if not self.prompt_index:
            return
        
        meta = self.prompt_index.index["prompts"].get(pid)
        if not meta:
            return
        
        content = self.prompt_index.get_prompt(pid)
        
        self.selected_prompt_id = pid
        self.prompt_title.delete(0, "end")
        self.prompt_title.insert(0, meta.get("title", ""))
        self.prompt_keywords.delete(0, "end")
        self.prompt_keywords.insert(0, ", ".join(meta.get("keywords", [])))
        self.prompt_category.set(meta.get("category", "general"))
        self.prompt_content.delete("1.0", "end")
        self.prompt_content.insert("1.0", content or "")
        
        self._log(f"Loaded: {pid}")
    
    def _new_prompt(self):
        """New prompt"""
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
            self.prompt_index.delete_prompt(self.selected_prompt_id)
        
        new_id = self.prompt_index.add_prompt(title, content, keywords, category)
        self.selected_prompt_id = new_id
        
        self._refresh_prompts()
        self._log(f"Saved: {new_id}")
    
    def _delete_prompt(self):
        """Delete prompt"""
        if not self.selected_prompt_id:
            messagebox.showwarning("Delete", "No prompt selected")
            return
        
        if messagebox.askyesno("Delete", f"Delete {self.selected_prompt_id}?"):
            self.prompt_index.delete_prompt(self.selected_prompt_id)
            self._new_prompt()
            self._refresh_prompts()
            self._log(f"Deleted: {self.selected_prompt_id}")


def main():
    print("[UMBRA-GUI] Creating window...")
    app = UmbraGUI()
    print("[UMBRA-GUI] Starting mainloop...")
    app.mainloop()


if __name__ == "__main__":
    main()
