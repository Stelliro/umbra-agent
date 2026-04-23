# force_upgrade.py
# ----------------
# Forcefully upgrades UMBRA to v11.0 (Explorer Edition).
# Replaces 'umbra_web.py' and 'core/code_agent.py'.

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
CORE_DIR = BASE_DIR / "core"

# ==============================================================================
# 1. NEW CODE AGENT (Explorer Backend)
# ==============================================================================
CODE_AGENT_V2 = r'''"""
Code Agent v2.0 — Project Explorer Edition
===========================================
Back-end logic for file browsing, reading, and project root switching.
"""
import json, os, re, shutil, time, logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("UMBRA-AGENT")

FORBIDDEN_DIRS = {"contract", ".git", "__pycache__", "node_modules", ".svn", ".hg"}
PROTECTED_FILES = {"umbra_autonomous.py", "umbra_web.py", "umbra_engine.py", "phoenix_council.py"}
MAX_FILE_SIZE = 500_000

class CodeAgent:
    def __init__(self, project_dir=".", ollama=None, model="qwen2.5-coder", backup_dir=None):
        self.project = Path(project_dir).resolve()
        self.ollama = ollama
        self.model = model
        self.backup_dir = Path(backup_dir or self.project / "data" / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.edit_log_file = self.backup_dir / "edit_log.json"
        self._edit_log = self._load_log()
        self.pending_edits = []

    def set_root(self, new_path):
        """Switch the active project root."""
        p = Path(new_path).resolve()
        if not p.exists():
            return {"error": f"Path does not exist: {new_path}"}
        if not p.is_dir():
            return {"error": "Path is not a directory"}
        self.project = p
        return {"success": True, "root": str(self.project)}

    def browse(self, rel_path="."):
        """List files and folders."""
        try:
            target = (self.project / rel_path).resolve()
            if not target.exists():
                return {"error": "Path not found"}
            
            items = []
            for item in target.iterdir():
                try:
                    if item.name.startswith('.') or item.name in FORBIDDEN_DIRS:
                        continue
                    stats = item.stat()
                    items.append({
                        "name": item.name,
                        "type": "dir" if item.is_dir() else "file",
                        "size": stats.st_size if item.is_file() else 0,
                        "mtime": datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M")
                    })
                except PermissionError:
                    continue
            
            # Sort: Directories first, then files
            items.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
            
            return {
                "current": str(rel_path),
                "abs_path": str(target),
                "items": items
            }
        except Exception as e:
            return {"error": str(e)}

    def read_file(self, rel_path):
        try:
            p = (self.project / rel_path).resolve()
            if not p.exists(): return None
            if p.stat().st_size > MAX_FILE_SIZE: return "<< FILE TOO LARGE >>"
            return p.read_text(encoding='utf-8', errors='replace')
        except Exception: return None

    def _load_log(self):
        if self.edit_log_file.exists():
            try: return json.loads(self.edit_log_file.read_text())
            except: pass
        return {"edits": []}
    
    def get_edit_history(self):
        return self._edit_log.get("edits", [])

    def analyze(self, rel_path):
        # Placeholder for actual analysis logic
        return {"status": "Analysis simulation", "file": rel_path}

    def list_files(self): return [] # Legacy support
'''

# ==============================================================================
# 2. NEW WEB UI (Unified Dashboard + Explorer)
# ==============================================================================
WEB_UI_V2 = r'''"""
UMBRA Command Center v11.0 (UNIFIED)
====================================
Features:
- Full Chat & Dashboard
- NEW: File Explorer Tab
- NEW: Project Root Switcher
"""
import sys, os, json, time, logging, threading
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, redirect, url_for, make_response

BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR / 'core'))

# --- Core Imports ---
try:
    from umbra_engine import get_engine, OllamaCompat
    _engine = get_engine(models_dir=str(BASE_DIR / "models"))
    UMBRA_ENGINE_OBJ = OllamaCompat(_engine)
except ImportError:
    UMBRA_ENGINE_OBJ = None

try: from umbra_boot import HandlerAlert; HAS_ALERTS = True
except ImportError: HAS_ALERTS = False

from chat_store import ChatStore
from code_agent import CodeAgent

try: from auth import AuthManager; HAS_AUTH = True
except ImportError: HAS_AUTH = False

try: from umbra_autonomous import AutonomousLoop; AUTONOMOUS_AVAILABLE = True
except ImportError: AUTONOMOUS_AVAILABLE = False

# --- Init ---
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
for d in [DATA_DIR, LOGS_DIR]: d.mkdir(parents=True, exist_ok=True)

auth_mgr = AuthManager(str(DATA_DIR)) if HAS_AUTH else None
store = ChatStore(str(DATA_DIR))
agent = CodeAgent(project_dir=str(BASE_DIR), ollama=UMBRA_ENGINE_OBJ, model="qwen2.5-coder")

SYS = {"loop": None, "thread": None, "status": "OFFLINE", "err": None}

app = Flask(__name__)
app.secret_key = os.urandom(24)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

def _offline_respond(chat_id, message):
    store.add_message(chat_id, "umbra", f"Echo (Offline): {message}")

def run_loop_thread():
    try:
        SYS["status"] = "ONLINE"
        SYS["loop"] = AutonomousLoop(dry_run=False)
        SYS["loop"].run()
    except Exception as e:
        SYS["status"] = "ERROR"; SYS["err"] = str(e)
    finally:
        SYS["status"] = "OFFLINE"; SYS["loop"] = None

# ==================== HTML ====================
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UMBRA | Command Center</title>
<style>
:root{--bg:#080a0f;--sf:#0d1117;--card:#161b22;--bd:#21262d;--txt:#e6edf3;--dim:#7d8590;--cyan:#00d4ff;--grn:#2ea043;--red:#da3633;--amb:#d29922;--sel:rgba(0,212,255,0.1)}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--txt);font-family:'Segoe UI',monospace;margin:0;height:100vh;display:flex;overflow:hidden}

/* LAYOUT */
.sb{width:52px;background:#050505;border-right:1px solid var(--bd);display:flex;flex-direction:column;align-items:center;padding:12px 0;flex-shrink:0}
.sb-i{width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:8px;cursor:pointer;font-size:16px;color:var(--dim);margin-bottom:4px}
.sb-i:hover{color:var(--txt);background:rgba(255,255,255,.05)}
.sb-i.on{color:var(--cyan);background:var(--sel)}

.view{display:none;flex:1;flex-direction:column;overflow:hidden}
.view.on{display:flex}

/* CHAT */
.chat-wrap{display:flex;flex:1;overflow:hidden}
.chat-list{width:240px;background:var(--sf);border-right:1px solid var(--bd);display:flex;flex-direction:column}
.cl-item{padding:8px 10px;cursor:pointer;font-size:12px;color:var(--dim);border-bottom:1px solid rgba(255,255,255,0.05)}
.cl-item.sel{color:var(--cyan);background:var(--sel)}
.chat-main{flex:1;display:flex;flex-direction:column}
.cm-msgs{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:10px;border-radius:8px;font-size:13px;white-space:pre-wrap}
.msg.u{align-self:flex-end;background:#1f6feb;color:#fff}
.msg.a{align-self:flex-start;background:var(--card);border:1px solid var(--bd)}
.cm-in{padding:15px;border-top:1px solid var(--bd);display:flex;gap:10px}
.cm-in input{flex:1;background:var(--card);border:1px solid var(--bd);color:var(--txt);padding:10px}

/* EXPLORER */
.ex-top{padding:8px 12px;background:var(--sf);border-bottom:1px solid var(--bd);display:flex;gap:8px;align-items:center}
.ex-path{flex:1;background:var(--bg);border:1px solid var(--bd);color:var(--txt);padding:5px 8px;font-family:monospace;font-size:12px}
.ex-body{flex:1;display:flex;overflow:hidden}
.ex-tree{width:260px;background:var(--sf);border-right:1px solid var(--bd);overflow-y:auto;padding:5px}
.ex-code{flex:1;display:flex;flex-direction:column;background:var(--bg)}
.tr-item{padding:3px 8px;cursor:pointer;font-size:12px;display:flex;align-items:center;gap:6px;overflow:hidden;text-overflow:ellipsis;color:var(--dim)}
.tr-item:hover{background:rgba(255,255,255,0.03);color:var(--txt)}
.tr-item.dir{color:#8b949e;font-weight:bold}
.tr-item.file{color:var(--txt)}
.ed-content{flex:1;background:var(--bg);color:#d1d5da;border:none;resize:none;padding:15px;font-family:'Consolas',monospace;font-size:13px;line-height:1.5;outline:none}

/* DASH */
.dash{padding:20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:15px}
.stat{background:var(--card);border:1px solid var(--bd);padding:15px;border-radius:6px}
</style>
</head>
<body>

<div class="sb">
  <div class="sb-i on" onclick="go('chat')" id="n-chat">💬</div>
  <div class="sb-i" onclick="go('explorer')" id="n-explorer">📂</div>
  <div class="sb-i" onclick="go('dash')" id="n-dash">📊</div>
  <div class="sb-i" onclick="go('logs')" id="n-logs">📜</div>
  <div class="sb-i" onclick="location.href='/logout'" style="margin-top:auto;color:var(--red)">🚪</div>
</div>

<div id="v-chat" class="view on">
  <div class="chat-wrap">
    <div class="chat-list">
      <div style="padding:10px;border-bottom:1px solid var(--bd);font-weight:bold;font-size:11px">CHATS <button onclick="newChat()" style="float:right">+</button></div>
      <div id="cl-items"></div>
      <div style="padding:10px"><button id="sys-btn" onclick="toggleSys()" style="width:100%">START SYSTEM</button></div>
    </div>
    <div class="chat-main">
      <div class="cm-msgs" id="cm-msgs"></div>
      <div class="cm-in"><input id="msg-in" onkeydown="if(event.key==='Enter')send()"><button onclick="send()">SEND</button></div>
    </div>
  </div>
</div>

<div id="v-explorer" class="view">
  <div class="ex-top">
    <span>ROOT</span>
    <input id="root-path" class="ex-path" value="." onchange="setRoot(this.value)">
    <button onclick="refreshTree()">⟳</button>
  </div>
  <div class="ex-body">
    <div class="ex-tree" id="tree-list"></div>
    <div class="ex-code">
      <div style="padding:5px;background:var(--card);border-bottom:1px solid var(--bd);font-size:11px" id="file-name">Select a file</div>
      <textarea id="editor" class="ed-content" spellcheck="false"></textarea>
    </div>
  </div>
</div>

<div id="v-dash" class="view"><div class="dash" id="dash-grid"></div></div>

<div id="v-logs" class="view"><pre id="log-out" style="padding:10px;color:#0f0;overflow:auto"></pre></div>

<script>
let curChat=null, activeFile=null;
function go(v){
  document.querySelectorAll('.view').forEach(e=>e.classList.remove('on'));
  document.querySelectorAll('.sb-i').forEach(e=>e.classList.remove('on'));
  document.getElementById('v-'+v).classList.add('on');
  document.getElementById('n-'+v).classList.add('on');
  if(v==='chat') loadChats();
  if(v==='explorer') refreshTree();
  if(v==='dash') loadDash();
  if(v==='logs') loadLogs();
}

// CHAT
async function loadChats(){
  const cs=await(await fetch('/api/chats')).json();
  document.getElementById('cl-items').innerHTML=cs.map(c=>`<div class="cl-item ${c.id===curChat?'sel':''}" onclick="openChat('${c.id}')">${c.title||'Chat'}</div>`).join('');
}
async function newChat(){const r=await(await fetch('/api/chats/create',{method:'POST'})).json();openChat(r.id)}
async function openChat(id){
  curChat=id;loadChats();
  const msgs=await(await fetch(`/api/chats/${id}/messages`)).json();
  const el=document.getElementById('cm-msgs');
  el.innerHTML=msgs.map(m=>`<div class="msg ${m.role==='handler'?'u':'a'}">${m.content}</div>`).join('');
  el.scrollTop=el.scrollHeight;
}
async function send(){
  const i=document.getElementById('msg-in');
  if(!i.value.trim()||!curChat)return;
  await fetch(`/api/chats/${curChat}/send`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:i.value})});
  i.value=''; openChat(curChat);
}

// EXPLORER
async function setRoot(p){
  await fetch('/api/agent/root',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p})});
  refreshTree();
}
async function refreshTree(sub='.'){
  const d=await(await fetch(`/api/agent/browse?path=${encodeURIComponent(sub)}`)).json();
  const el=document.getElementById('tree-list');
  let h='';
  if(sub!=='.') h+=`<div class="tr-item dir" onclick="refreshTree('${sub.split('/').slice(0,-1).join('/')||'.'}')">📁 ..</div>`;
  if(d.items) d.items.forEach(i=>{
    const full=sub==='.'?i.name:`${sub}/${i.name}`;
    if(i.type==='dir') h+=`<div class="tr-item dir" onclick="refreshTree('${full}')">📁 ${i.name}</div>`;
    else h+=`<div class="tr-item file" onclick="loadFile('${full}')">📄 ${i.name}</div>`;
  });
  el.innerHTML=h;
}
async function loadFile(p){
  activeFile=p; document.getElementById('file-name').innerText=p;
  const d=await(await fetch(`/api/agent/read?path=${encodeURIComponent(p)}`)).json();
  document.getElementById('editor').value=d.content||'';
}

// DASH
async function loadDash(){
  const d=await(await fetch('/api/dashboard')).json();
  document.getElementById('dash-grid').innerHTML=Object.entries(d).map(([k,v])=>`<div class="stat"><div style="font-size:10px;color:#888">${k.toUpperCase()}</div><div style="font-size:20px;font-weight:bold">${v}</div></div>`).join('');
  document.getElementById('sys-btn').innerText=d.status==='ONLINE'?'STOP SYSTEM':'START SYSTEM';
}
async function toggleSys(){
  const s=document.getElementById('sys-btn').innerText.includes('START');
  await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:s?'start':'stop'})});
  loadDash();
}
async function loadLogs(){
  const l=await(await fetch('/api/logs')).json();
  document.getElementById('log-out').innerText=l.map(x=>`[${x.time}] ${x.msg}`).join('\n');
}

// Init
fetch('/api/agent/root_info').then(r=>r.json()).then(d=>document.getElementById('root-path').value=d.root);
loadChats();
</script>
</body>
</html>
"""

# ==================== ROUTES ====================
@app.route('/')
def home(): return render_template_string(HTML)

@app.route('/api/chats')
def api_chats(): return jsonify(store.list_chats())
@app.route('/api/chats/create', methods=['POST'])
def api_create(): return jsonify({"id": store.create_chat()})
@app.route('/api/chats/<cid>/messages')
def api_msgs(cid): return jsonify(store.get_messages(cid))
@app.route('/api/chats/<cid>/send', methods=['POST'])
def api_send(cid):
    msg = request.json.get('message')
    store.add_message(cid, "handler", msg)
    if SYS["status"] == "ONLINE" and SYS["loop"]: SYS["loop"].send_chat(msg)
    else: _offline_respond(cid, msg)
    return jsonify({"success": True})

@app.route('/api/agent/root_info')
def api_root_info(): return jsonify({"root": str(agent.project)})
@app.route('/api/agent/root', methods=['POST'])
def api_set_root(): return jsonify(agent.set_root(request.json.get('path')))
@app.route('/api/agent/browse')
def api_browse(): return jsonify(agent.browse(request.args.get('path', '.')))
@app.route('/api/agent/read')
def api_read(): return jsonify({"content": agent.read_file(request.args.get('path'))})

@app.route('/api/dashboard')
def api_dash():
    d = {"status": SYS["status"], "chats": len(store.list_chats())}
    if SYS["loop"]: d.update(SYS["loop"].stats)
    return jsonify(d)
@app.route('/api/logs')
def api_logs():
    if not LOGS_DIR.exists(): return jsonify([])
    lf = list(LOGS_DIR.glob("*.log"))
    if not lf: return jsonify([])
    return jsonify([{"time": "00:00", "msg": l} for l in lf[0].read_text().splitlines()[-50:]])
@app.route('/api/control', methods=['POST'])
def api_ctrl():
    act = request.json.get('action')
    if act == 'start':
        SYS["thread"] = threading.Thread(target=run_loop_thread, daemon=True)
        SYS["thread"].start()
    elif act == 'stop' and SYS["loop"]: SYS["loop"].shutdown()
    return jsonify({"success": True})
@app.route('/login', methods=['GET','POST'])
def login(): return redirect('/')
@app.route('/logout')
def logout(): return redirect('/')

if __name__ == '__main__':
    import flask.cli
    flask.cli.show_server_banner = lambda *args: None
    print("[UMBRA] UNIFIED DASHBOARD + EXPLORER RUNNING ON http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
'''

def install():
    print("[INSTALL] Overwriting core/code_agent.py...")
    with open(CORE_DIR / "code_agent.py", "w", encoding="utf-8") as f:
        f.write(CODE_AGENT_V2)
    
    print("[INSTALL] Overwriting umbra_web.py...")
    with open(BASE_DIR / "umbra_web.py", "w", encoding="utf-8") as f:
        f.write(WEB_UI_V2)
        
    print("[SUCCESS] Upgrade Complete.")
    print("Run 'python broadcast_now.py' to launch.")

if __name__ == "__main__":
    install()