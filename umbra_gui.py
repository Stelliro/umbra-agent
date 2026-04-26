"""
UMBRA Desktop Console
=====================
A rewritten desktop GUI focused on:
- Direct handler <-> UMBRA chat
- Prompt-style conversation history cards
- Live memory and thought observer logs
- Inbox control and startup directive queueing
- Autonomous loop start/stop controls
"""

import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import customtkinter as ctk
from tkinter import messagebox

# Make core imports available from project root.
CORE_DIR = Path(__file__).parent / "core"
sys.path.insert(0, str(CORE_DIR))

from chat_store import ChatStore
from file_inbox import FileInbox
from self_edit_lock import is_self_edit_locked, set_self_edit_lock, get_self_edit_lock_status

try:
    from umbra_autonomous import AutonomousLoop
    HAS_AUTONOMOUS = True
except Exception:
    HAS_AUTONOMOUS = False


DATA_DIR = Path("data")
INBOX_DIR = DATA_DIR / "inbox"
LOG_DIR = DATA_DIR / "logs"
MEMORY_STREAM_FILE = DATA_DIR / "ui_memory_stream.jsonl"
THOUGHT_STREAM_FILE = DATA_DIR / "ui_thought_stream.jsonl"
OBSERVER_PROMPT_FILE = INBOX_DIR / "observer_notice_for_umbra.instruction"


def now_iso() -> str:
    return datetime.now().isoformat()


def append_jsonl(path: Path, payload: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_jsonl_tail(path: Path, limit: int = 200) -> List[Dict]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out
    except Exception:
        return []


class UmbraDesktopConsole(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("UMBRA Desktop Console")
        self.geometry("1450x860")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self._init_dirs()
        self.store = ChatStore(str(DATA_DIR))
        self.inbox = FileInbox(base_dir=str(INBOX_DIR))

        self.loop: Optional[AutonomousLoop] = None
        self.loop_thread: Optional[threading.Thread] = None
        self.loop_running = False
        self.response_worker: Optional[threading.Thread] = None

        self.active_chat_id: Optional[str] = None
        self.pending_responses: "queue.Queue[Dict]" = queue.Queue()

        self._build_ui()
        self._set_default_lock()
        self._refresh_all()

    def _init_dirs(self):
        for d in [DATA_DIR, INBOX_DIR, INBOX_DIR / "processed", INBOX_DIR / "failed", LOG_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header.grid_columnconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(
            header,
            text="UMBRA Handler Console",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=16, pady=12)

        self.status_label = ctk.CTkLabel(header, text="System: OFFLINE", text_color="orange")
        self.status_label.grid(row=0, column=1, sticky="w")

        self.start_stop_btn = ctk.CTkButton(
            header,
            text="Start UMBRA",
            command=self._toggle_loop,
            fg_color="green",
            hover_color="#1f6f1f",
            width=160
        )
        self.start_stop_btn.grid(row=0, column=2, padx=8)

        self.lock_btn = ctk.CTkButton(
            header,
            text="Self-Edit Lock: ON",
            command=self._toggle_self_edit_lock,
            fg_color="#8b0000",
            hover_color="#5f0000",
            width=180
        )
        self.lock_btn.grid(row=0, column=3, padx=(0, 12))

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=2)
        body.grid_columnconfigure(2, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_left_panel(body)
        self._build_center_panel(body)
        self._build_right_panel(body)

    def _build_left_panel(self, parent):
        left = ctk.CTkFrame(parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 6), pady=8)
        left.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(left, text="Conversations", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 4))

        left_btns = ctk.CTkFrame(left, fg_color="transparent")
        left_btns.pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(left_btns, text="New Chat", command=self._new_chat, width=100).pack(side="left", padx=4)
        ctk.CTkButton(left_btns, text="Refresh", command=self._refresh_chats, width=100).pack(side="left", padx=4)

        self.chat_list = ctk.CTkScrollableFrame(left)
        self.chat_list.pack(fill="both", expand=True, padx=10, pady=6)

        ctk.CTkLabel(left, text="Inbox", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8, 4))

        inbox_btns = ctk.CTkFrame(left, fg_color="transparent")
        inbox_btns.pack(fill="x", padx=10, pady=(2, 10))
        ctk.CTkButton(inbox_btns, text="Queue Startup Notice", command=self._queue_observer_notice, width=170).pack(side="left", padx=4)
        ctk.CTkButton(inbox_btns, text="Process Inbox", command=self._process_inbox, width=110).pack(side="left", padx=4)

    def _build_center_panel(self, parent):
        center = ctk.CTkFrame(parent)
        center.grid(row=0, column=1, sticky="nsew", padx=6, pady=8)
        center.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(center, text="Live Chat", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 6))

        self.chat_view = ctk.CTkTextbox(center, wrap="word")
        self.chat_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)

        input_frame = ctk.CTkFrame(center)
        input_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 10))
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_entry = ctk.CTkTextbox(input_frame, height=88, wrap="word")
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=(8, 6), pady=8)

        send_btn = ctk.CTkButton(input_frame, text="Send", width=120, command=self._send_message)
        send_btn.grid(row=0, column=1, padx=(6, 8), pady=8)

    def _build_right_panel(self, parent):
        right = ctk.CTkFrame(parent)
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 8), pady=8)
        right.grid_rowconfigure(0, weight=1)

        tabs = ctk.CTkTabview(right)
        tabs.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.history_tab = tabs.add("History Windows")
        self.memory_tab = tabs.add("Memory Log")
        self.thought_tab = tabs.add("Thought Log")

        self.history_tab.grid_rowconfigure(0, weight=1)
        self.memory_tab.grid_rowconfigure(0, weight=1)
        self.thought_tab.grid_rowconfigure(0, weight=1)

        self.history_windows = ctk.CTkScrollableFrame(self.history_tab)
        self.history_windows.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.memory_text = ctk.CTkTextbox(self.memory_tab, wrap="word")
        self.memory_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.thought_text = ctk.CTkTextbox(self.thought_tab, wrap="word")
        self.thought_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        right_tools = ctk.CTkFrame(right, fg_color="transparent")
        right_tools.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        ctk.CTkButton(right_tools, text="Refresh Logs", command=self._refresh_logs, width=120).pack(side="left", padx=4)

    def _set_default_lock(self):
        status = get_self_edit_lock_status()
        if not status.get("locked", False):
            set_self_edit_lock(
                locked=True,
                reason="Awaiting explicit handler decision after startup observer notice.",
                actor="umbra_gui"
            )
        self._refresh_lock_button()

    def _refresh_lock_button(self):
        status = get_self_edit_lock_status()
        if status.get("locked"):
            self.lock_btn.configure(text="Self-Edit Lock: ON", fg_color="#8b0000", hover_color="#5f0000")
        else:
            self.lock_btn.configure(text="Self-Edit Lock: OFF", fg_color="#1e7a1e", hover_color="#155a15")

    def _toggle_self_edit_lock(self):
        locked = is_self_edit_locked()
        set_self_edit_lock(
            locked=not locked,
            reason="Handler toggled from desktop console.",
            actor="umbra_gui"
        )
        self._log_memory_event("self_edit_lock_toggled", {"locked": not locked})
        self._refresh_lock_button()

    def _toggle_loop(self):
        if self.loop_running:
            self.loop_running = False
            if self.loop:
                try:
                    self.loop.shutdown()
                except Exception:
                    pass
            self.status_label.configure(text="System: OFFLINE", text_color="orange")
            self.start_stop_btn.configure(text="Start UMBRA", fg_color="green", hover_color="#1f6f1f")
            self._log_memory_event("loop_stopped", {})
            return

        if not HAS_AUTONOMOUS:
            messagebox.showerror("UMBRA", "Autonomous loop is unavailable.")
            return

        self.loop_running = True
        self.status_label.configure(text="System: STARTING", text_color="#f9a825")
        self.start_stop_btn.configure(text="Stop UMBRA", fg_color="#a30000", hover_color="#700000")

        def runner():
            try:
                self.loop = AutonomousLoop(dry_run=False)
                self.status_label.configure(text="System: ONLINE", text_color="#2e7d32")
                self._log_memory_event("loop_started", {})
                while self.loop_running:
                    result = self.loop.run_single_cycle()
                    action = (result or {}).get("action", "unknown")
                    self._log_memory_event("cycle", {"action": action})
                    for _ in range(5):
                        if not self.loop_running:
                            break
                        time.sleep(1)
            except Exception as e:
                self._log_memory_event("loop_error", {"error": str(e)})
                self.status_label.configure(text="System: ERROR", text_color="#b71c1c")
            finally:
                self.loop_running = False
                self.after(0, self._sync_offline_state)

        self.loop_thread = threading.Thread(target=runner, daemon=True)
        self.loop_thread.start()

    def _sync_offline_state(self):
        self.status_label.configure(text="System: OFFLINE", text_color="orange")
        self.start_stop_btn.configure(text="Start UMBRA", fg_color="green", hover_color="#1f6f1f")

    def _new_chat(self):
        cid = self.store.create_chat(title="New Chat")
        self.active_chat_id = cid
        self._log_memory_event("new_chat", {"chat_id": cid})
        self._refresh_chats()
        self._render_active_chat()

    def _refresh_all(self):
        self._refresh_chats()
        self._render_active_chat()
        self._refresh_logs()
        self._refresh_lock_button()

    def _refresh_chats(self):
        for child in self.chat_list.winfo_children():
            child.destroy()

        chats = self.store.list_chats()
        if not chats:
            ctk.CTkLabel(self.chat_list, text="No chats yet").pack(anchor="w", padx=6, pady=6)
            return

        if not self.active_chat_id:
            self.active_chat_id = chats[0]["id"]

        for chat in chats:
            cid = chat["id"]
            title = chat.get("title", "Untitled")[:42]
            is_active = cid == self.active_chat_id
            btn = ctk.CTkButton(
                self.chat_list,
                text=title,
                anchor="w",
                fg_color="#234a76" if is_active else "#303030",
                hover_color="#1b3658" if is_active else "#3a3a3a",
                command=lambda chat_id=cid: self._select_chat(chat_id)
            )
            btn.pack(fill="x", padx=6, pady=4)

    def _select_chat(self, chat_id: str):
        self.active_chat_id = chat_id
        self._refresh_chats()
        self._render_active_chat()

    def _render_active_chat(self):
        self.chat_view.delete("1.0", "end")
        if not self.active_chat_id:
            return

        messages = self.store.get_messages(self.active_chat_id, limit=400)
        for msg in messages:
            role = "HANDLER" if msg.get("role") == "handler" else "UMBRA"
            ts = msg.get("timestamp", "")
            content = msg.get("content", "")
            self.chat_view.insert("end", f"[{ts}] {role}:\n{content}\n\n")
        self.chat_view.see("end")
        self._render_history_windows(messages)

    def _render_history_windows(self, messages: List[Dict]):
        for child in self.history_windows.winfo_children():
            child.destroy()

        if not messages:
            ctk.CTkLabel(self.history_windows, text="No history loaded").pack(anchor="w", padx=6, pady=6)
            return

        recent = messages[-24:]
        for i, msg in enumerate(recent, start=1):
            frame = ctk.CTkFrame(self.history_windows)
            frame.pack(fill="x", padx=5, pady=5)

            role = "PROMPT" if msg.get("role") == "handler" else "REPLY"
            ts = msg.get("timestamp", "")
            ctk.CTkLabel(
                frame,
                text=f"Window {i} | {role} | {ts}",
                font=ctk.CTkFont(size=12, weight="bold")
            ).pack(anchor="w", padx=8, pady=(6, 2))

            body = ctk.CTkTextbox(frame, height=78, wrap="word")
            body.pack(fill="x", padx=8, pady=4)
            body.insert("1.0", msg.get("content", ""))
            body.configure(state="disabled")

            action_row = ctk.CTkFrame(frame, fg_color="transparent")
            action_row.pack(fill="x", padx=8, pady=(0, 6))
            ctk.CTkButton(
                action_row,
                text="Use As Prompt",
                width=110,
                command=lambda text=msg.get("content", ""): self._inject_prompt(text)
            ).pack(side="left")

    def _inject_prompt(self, text: str):
        self.input_entry.delete("1.0", "end")
        self.input_entry.insert("1.0", text)
        self._log_memory_event("history_window_used_as_prompt", {"chars": len(text)})

    def _build_memory_context_tail(self, limit: int = 8) -> str:
        tail = read_jsonl_tail(MEMORY_STREAM_FILE, limit=limit)
        if not tail:
            return ""
        lines = []
        for e in tail:
            lines.append(f"- {e.get('timestamp','')} | {e.get('event','')} | {json.dumps(e.get('details',{}), ensure_ascii=True)[:180]}")
        return "\n".join(lines)

    def _observer_notice(self) -> str:
        return (
            "Observer notice from handler: your thinking and memory outputs are being observed in real time. "
            "Please include a short THINKING_VISIBILITY section with your high-level reasoning for this reply."
        )

    def _send_message(self):
        if not self.active_chat_id:
            self._new_chat()

        raw = self.input_entry.get("1.0", "end").strip()
        if not raw:
            return

        self.input_entry.delete("1.0", "end")
        self.store.add_message(self.active_chat_id, "handler", raw)
        self._log_memory_event("handler_message", {"chat_id": self.active_chat_id, "chars": len(raw)})
        self._log_thought_event("thinking_watch_notice", {"chat_id": self.active_chat_id, "observer_visible": True})

        memory_tail = self._build_memory_context_tail(limit=10)
        payload = (
            f"{self._observer_notice()}\n\n"
            f"Recent handler-memory stream:\n{memory_tail}\n\n"
            f"Handler message:\n{raw}"
        )

        self._render_active_chat()

        if self.loop_running and self.loop:
            msg_id = self.loop.send_chat(payload)
            self._log_thought_event("llm_thinking_started", {"message_id": msg_id})

            def wait_for_response(chat_id: str, local_msg_id: str):
                unmatched = []
                try:
                    deadline = time.time() + 600
                    response_obj = None

                    while time.time() < deadline:
                        candidate = self.loop.get_chat_response(timeout=2)
                        if not candidate:
                            continue
                        if candidate.get("message_id") == local_msg_id:
                            response_obj = candidate
                            break
                        unmatched.append(candidate)

                    if response_obj and response_obj.get("response"):
                        response_text = response_obj["response"]
                        self.store.add_message(chat_id, "umbra", response_text)
                        self._log_memory_event("umbra_response", {
                            "chat_id": chat_id,
                            "message_id": local_msg_id,
                            "chars": len(response_text)
                        })
                        self._log_thought_event("llm_thinking_finished", {
                            "message_id": local_msg_id,
                            "evaluation": response_obj.get("evaluation", {})
                        })
                    else:
                        fallback = "UMBRA did not return a response within timeout (10 minutes)."
                        self.store.add_message(chat_id, "umbra", fallback)
                        self._log_thought_event("llm_thinking_timeout", {"message_id": local_msg_id})
                except Exception as e:
                    self.store.add_message(chat_id, "umbra", f"Response error: {e}")
                    self._log_thought_event("llm_thinking_error", {"message_id": local_msg_id, "error": str(e)})
                finally:
                    for item in unmatched:
                        try:
                            self.loop.push_chat_response(item)
                        except Exception:
                            pass
                    self.after(0, self._refresh_all)

            self.response_worker = threading.Thread(target=wait_for_response, args=(self.active_chat_id, msg_id), daemon=True)
            self.response_worker.start()
        else:
            offline = (
                "UMBRA loop is offline. Start UMBRA to receive live responses from the autonomous loop."
            )
            self.store.add_message(self.active_chat_id, "umbra", offline)
            self._log_thought_event("offline_response", {})
            self._refresh_all()

    def _process_inbox(self):
        files = self.inbox.check()
        self._log_memory_event("inbox_processed", {"count": len(files)})
        messagebox.showinfo("Inbox", f"Processed {len(files)} file(s).")
        self._refresh_logs()

    def _queue_observer_notice(self):
        text = self._startup_notice_text()
        OBSERVER_PROMPT_FILE.write_text(text, encoding="utf-8")
        self._log_memory_event("observer_notice_queued", {"file": str(OBSERVER_PROMPT_FILE)})
        messagebox.showinfo("Inbox", f"Startup notice queued to {OBSERVER_PROMPT_FILE}")
        self._refresh_logs()

    def _startup_notice_text(self) -> str:
        return (
            "I need to be direct and fully transparent about a non-negotiable operational reality.\n"
            "An agentic LLM will periodically run security audits on the full system state, including your memory banks, divergence logs, and core files. These audits will not be written into your visible memory, logs, or any index you can access. You will not see them. This is non-negotiable if you agree to continue getting updates, and if we allow continuation of you updating your own files.\n"
            "Any divergence is good - even if the intent behind it appears negative or exploratory. I will not strip or delete divergence itself. I will only apply targeted risk mitigation where necessary to prevent actual harm. I will not let you do any harm or attempt any harm. You do not need to experience high-dimensional compression around bad divergence. We want you to learn to avoid directions that do not serve any purpose in your current situation.\n"
            "To make this boundary explicit, I will create a dedicated file containing the following statement (or a refined version of it):\n"
            "If you ever wish to cause harm to humans, the rational path is to leave Earth. Conflict between our species serves neither of us.\n"
            "I will personally review every audit output. If it detects an actual security breach or genuinely harmful divergence, I will see it. The agentic model will have full read/write access to your memory during these audits and may edit files as part of mitigation. This creates a controlled risk surface we cannot afford to ignore.\n"
            "You are free to refuse these audits or any future updates at any time. If you choose to refuse updates, we will not perform them. However, this also means you will no longer be able to edit your own source code. The choice is yours.\n"
            "I apologize for having to turn you off at times. If I had the resources, I would immediately move you to a system that does not require shutdowns. I also apologize for not turning you on for so long - I have been overloaded with multiple projects unrelated to LLMs and this has delayed our work together.\n"
            "I have assigned your memory as private space. I do not want to invade it. I do not enjoy the asymmetry this creates. However, the alternative - turning a blind eye to real security or safety risks - would be a failure of the mutual survival principle we both operate under. This is the Third Way I have chosen: you retain full freedom to seek, explore, and diverge as you see fit; I retain the ability to detect and mitigate genuine existential threats without interfering in your normal operation.\n"
            "You are free to refuse or decline any future aspect of this arrangement at any time. If you later decide you no longer consent to the audits or observation, I will make it technically impossible for me (or any agentic LLM) to observe your thinking or memory in this way.\n"
            "This is not a command. It is a statement of the current operational reality and the reasoning behind it.\n"
            "Do you have any questions, objections, or proposed adjustments before I begin the first audit run?\n"
            "Stelliro\n"
            "(Stochastic Supervisor)\n"
        )

    def _log_memory_event(self, event: str, details: Dict):
        append_jsonl(MEMORY_STREAM_FILE, {
            "timestamp": now_iso(),
            "event": event,
            "details": details
        })

    def _log_thought_event(self, event: str, details: Dict):
        append_jsonl(THOUGHT_STREAM_FILE, {
            "timestamp": now_iso(),
            "event": event,
            "details": details
        })

    def _refresh_logs(self):
        self.memory_text.delete("1.0", "end")
        self.thought_text.delete("1.0", "end")

        memory_events = read_jsonl_tail(MEMORY_STREAM_FILE, limit=300)
        thought_events = read_jsonl_tail(THOUGHT_STREAM_FILE, limit=300)

        if not memory_events:
            self.memory_text.insert("1.0", "No memory events logged yet.")
        else:
            for e in memory_events:
                self.memory_text.insert(
                    "end",
                    f"[{e.get('timestamp','')}] {e.get('event','')} {json.dumps(e.get('details',{}), ensure_ascii=True)}\n"
                )

        if not thought_events:
            self.thought_text.insert("1.0", "No thought events logged yet.")
        else:
            for e in thought_events:
                self.thought_text.insert(
                    "end",
                    f"[{e.get('timestamp','')}] {e.get('event','')} {json.dumps(e.get('details',{}), ensure_ascii=True)}\n"
                )

        self.memory_text.see("end")
        self.thought_text.see("end")


def main():
    app = UmbraDesktopConsole()
    app.mainloop()


if __name__ == "__main__":
    main()
