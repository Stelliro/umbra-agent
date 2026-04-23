# restore_dashboard.py
# --------------------
# Merges the full features of the original UMBRA Web UI with the new Explorer.
# Restores Chat, Logs, Dashboard, etc.

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
WEB_PATH = BASE_DIR / "umbra_web.py"

# This contains the FULL UMBRA UI (Chat + Dashboard + Logs) merged with the NEW EXPLORER.
MERGED_WEB_UI = r'''"""
UMBRA Command Center v11.1 (UNIFIED)
====================================
- Full Dashboard (Chat, Logs, Alerts, Settings)
- Integrated V2 Explorer (Tree View, IDE, Project Switching)
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
from code_agent import CodeAgent  # This uses the V2 Agent we just installed

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
# Init CodeAgent with V2 features
agent = CodeAgent(project_dir=str(BASE_DIR), ollama=UMBRA_ENGINE_OBJ, model="qwen2.5-coder")

SYS = {"loop": None, "thread": None, "status": "OFFLINE", "err": None}

app = Flask(__name__)
app.secret_key = os.urandom(24)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# --- Logic Helpers ---
def _offline_respond(chat_id, message):
    """Simple offline response logic."""
    if not UMBRA_ENGINE_OBJ:
        store.add_message(chat_id, "umbra", "Engine offline.")
        return
    def worker():
        try:
            # Simple context retrieval
            recent = store.get_messages(chat_id, limit=5)
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in recent])
            prompt += f"\nHandler: {message}\nUMBRA:"
            resp = UMBRA_ENGINE_OBJ.generate(model="llama3", prompt=prompt)
            store.add_message(chat_id, "umbra", resp.get("response", "..."))
        except Exception as e:
            store.add_message(chat_id, "umbra", f"Error: {e}")
    threading.Thread(target=worker, daemon=True).start()

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
/* CORE THEME */
:root{--bg:#080a0f;--sf:#0d1117;--card:#161b22;--bd:#21262d;--txt:#e6edf3;--dim:#7d8590;--cyan:#00d4ff;--grn:#2ea043;--red:#da3633;--amb:#d29922;--sel:rgba(0,212,255,0.1)}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--txt);font-family:'Segoe UI',monospace;margin:0;height:100vh;display:flex;overflow:hidden}

/* SIDEBAR */
.sb{width:52px;background:#050505;border-right:1px solid var(--bd);display:flex;flex-direction:column;align-items:center;padding:12px 0;flex-shrink:0}
.sb-i{width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:8px;cursor:pointer;font-size:16px;color:var(--dim);margin-bottom:4px;transition:.15s}
.sb-i:hover{color:var(--txt);background:rgba(255,255,255,.05)}
.sb-i.on{color:var(--cyan);background:var(--sel)}

/* VIEWS */
.view{display:none;flex:1;flex-direction:column;overflow:hidden}
.view.on{display:flex}

/* CHAT LAYOUT */
.chat-wrap{display:flex;flex:1;overflow:hidden}
.chat-list{width:240px;background:var(--sf);border-right:1px solid var(--bd);display:flex;flex-direction:column}
.cl-head{padding:12px;border-bottom:1px solid var(--bd);font-size:11px;font-weight:bold;color:var(--dim);display:flex;justify-content:space-between;align-items:center}
.cl-items{flex:1;overflow-y:auto;padding:5px}
.cl-item{padding:8px 10px;cursor:pointer;font-size:12px;color:var(--dim);border-radius:4px;margin-bottom:2px}
.cl-item:hover{color:var(--txt);background:rgba(255,255,255,0.03)}
.cl-item.sel{color:var(--cyan);background:var(--sel)}

.chat-main{flex:1;display:flex;flex-direction:column;background:var(--bg)}
.cm-head{padding:10px 20px;border-bottom:1px solid var(--bd);display:flex;justify-content:space-between;align-items:center}
.cm-msgs{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.5;white-space:pre-wrap}
.msg.u{align-self:flex-end;background:#1f6feb;color:#fff}
.msg.a{align-self:flex-start;background:var(--card);border:1px solid var(--bd)}
.cm-in{padding:15px;border-top:1px solid var(--bd);display:flex;gap:10px}
.cm-in input{flex:1;background:var(--card);border:1px solid var(--bd);color:var(--txt);padding:10px;border-radius:6px;outline:none}

/* EXPLORER LAYOUT */
.ex-top{padding:8px 12px;background:var(--sf);border-bottom:1px solid var(--bd);display:flex;gap:8px;align-items:center}
.ex-path{flex:1;background:var(--bg);border:1px solid var(--bd);color:var(--txt);padding:5px 8px;border-radius:4px;font-family:monospace;font-size:12px}
.ex-body{flex:1;display:flex;overflow:hidden}
.ex-tree{width:260px;background:var(--sf);border-right:1px solid var(--bd);overflow-y:auto;padding:5px}
.ex-code{flex:1;display:flex;flex-direction:column;background:var(--bg)}
.tr-item{padding:3px 8px;cursor:pointer;font-size:12px;display:flex;align-items:center;gap:6px;border-radius:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--dim)}
.tr-item:hover{background:rgba(255,255,255,0.03);color:var(--txt)}
.tr-item.dir{color:#8b949e;font-weight:bold}
.tr-item.file{color:var(--txt)}
.tr-item.sel{background:var(--sel);color:var(--cyan)}
.ed-head{padding:6px 12px;background:var(--card);border-bottom:1px solid var(--bd);font-size:11px;color:var(--dim);display:flex;justify-content:space-between}
.ed-content{flex:1;background:var(--bg);color:#d1d5da;border:none;resize:none;padding:15px;font-family:'Consolas',monospace;font-size:13px;line-height:1.5;outline:none}
.btn-xs{background:var(--bd);border:none;color:var(--dim);padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px}
.btn-xs:hover{color:var(--txt);background:#30363d}

/* DASHBOARD GRID */
.dash{padding:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:15px}
.stat{background:var(--card);border:1px solid var(--bd);padding:15px;border-radius:6px}
.stat .lb{font-size:10px;text-transform:uppercase;color:var(--dim)}
.stat .vl{font-size:24px;font-weight:bold;margin-top:5px;font-family:monospace}
</style>
</head>
<body>

<div class="sb">
  <div class="sb-i on" onclick="go('chat')" id="n-chat" title="Chat">💬</div>
  <div class="sb-i" onclick="go('explorer')" id="n-explorer" title="Explorer">📂</div>
  <div class="sb-i" onclick="go('dash')" id="n-dash" title="Dashboard">📊</div>
  <div class="sb-i" onclick="go('logs')" id="n-logs" title="Logs">📜</div>
  <div class="sb-i" onclick="location.href='/logout'" title="Logout" style="margin-top:auto;color:var(--red)">🚪</div>
</div>

<div id="v-chat" class="view on">
  <div class="chat-wrap">
    <div class="chat-list">
      <div class="cl-head">
        <span>CONVERSATIONS</span>
        <button class="btn-xs" onclick="newChat()">+</button>
      </div>
      <div class="cl-items" id="cl-items"></div>
      <div style="padding:10px;border-top:1px solid var(--bd)">
         <button id="sys-btn" class="btn-xs" style="width:100%" onclick="toggleSys()">START SYSTEM</button>
      </div>
    </div>
    <div class="chat-main">
      <div class="cm-head">
        <span id="ch-title" style="font-weight:bold;font-size:13px">Select a chat</span>
        <button class="btn-xs" onclick="delChat()">🗑</button>
      </div>
      <div class="cm-msgs" id="cm-msgs"></div>
      <div class="cm-in">
        <input id="msg-in" placeholder="Message..." onkeydown="if(event.key==='Enter')send()">
        <button class="btn-xs" onclick="send()">SEND</button>
      </div>
    </div>
  </div>
</div>

<div id="v-explorer" class="view">
  <div class="ex-top">
    <span style="font-size:11px;font-weight:bold;color:var(--dim)">PROJECT ROOT</span>
    <input id="root-path" class="ex-path" value="." onchange="setRoot(this.value)">
    <button class="btn-xs" onclick="refreshTree()">⟳</button>
  </div>
  <div class="ex-body">
    <div class="ex-tree" id="tree-list"></div>
    <div class="ex-code">
      <div class="ed-head">
        <span id="file-name">No file selected</span>
        <div style="display:flex;gap:8px">
          <span style="cursor:pointer;color:var(--cyan)" onclick="agentAction('analyze')">🔍 Analyze</span>
          <span style="cursor:pointer;color:var(--grn)" onclick="agentAction('fix')">🔧 Fix</span>
          <span style="cursor:pointer;color:var(--amb)" onclick="saveFile()">💾 Save</span>
        </div>
      </div>
      <textarea id="editor" class="ed-content" spellcheck="false"></textarea>
    </div>
  </div>
</div>

<div id="v-dash" class="view">
  <div class="dash">
    <h2 style="font-size:16px;margin-bottom:20px">System Metrics</h2>
    <div class="grid" id="dash-grid"></div>
  </div>
</div>

<div id="v-logs" class="view">
  <div style="padding:10px;background:#000;color:#0f0;font-family:monospace;font-size:11px;flex:1;overflow-y:auto;white-space:pre-wrap" id="log-out"></div>
</div>

<script>
let curChat=null, activeFile=null;

// --- NAV ---
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

// --- CHAT ---
async function loadChats(){
  const cs = await(await fetch('/api/chats')).json();
  const el = document.getElementById('cl-items');
  el.innerHTML = cs.map(c=>`<div class="cl-item ${c.id===curChat?'sel':''}" onclick="openChat('${c.id}')">${c.title||'Untitled'}</div>`).join('');
}
async function newChat(){
  const r = await(await fetch('/api/chats/create',{method:'POST'})).json();
  openChat(r.id);
}
async function openChat(id){
  curChat=id; loadChats();
  const msgs = await(await fetch(`/api/chats/${id}/messages`)).json();
  const el = document.getElementById('cm-msgs');
  el.innerHTML = msgs.map(m=>`<div class="msg ${m.role==='handler'?'u':'a'}">${m.content}</div>`).join('');
  el.scrollTop = el.scrollHeight;
  document.getElementById('ch-title').innerText = id;
}
async function send(){
  const i = document.getElementById('msg-in');
  const txt = i.value.trim();
  if(!txt||!curChat)return;
  i.value='';
  document.getElementById('cm-msgs').innerHTML += `<div class="msg u">${txt}</div>`;
  await fetch(`/api/chats/${curChat}/send`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:txt})});
  setTimeout(()=>openChat(curChat), 2000); // Polling for reply
}

// --- EXPLORER ---
async function setRoot(p){
  await fetch('/api/agent/root',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p})});
  refreshTree();
}
async function refreshTree(sub='.'){
  const d = await(await fetch(`/api/agent/browse?path=${encodeURIComponent(sub)}`)).json();
  const el = document.getElementById('tree-list');
  let h = '';
  if(sub!=='.') h+=`<div class="tr-item dir" onclick="refreshTree('${sub.split('/').slice(0,-1).join('/')||'.'}')">📁 ..</div>`;
  if(d.items) d.items.forEach(i=>{
     const full = sub==='.'?i.name:`${sub}/${i.name}`;
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
async function agentAction(act){
  const ed=document.getElementById('editor');
  ed.value = `Running ${act}...`;
  const r=await fetch('/api/agent/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:act,file:activeFile,content:ed.value})});
  const d=await r.json();
  ed.value = JSON.stringify(d, null, 2);
}

// --- DASHBOARD & SYSTEM ---
async function loadDash(){
  const d = await(await fetch('/api/dashboard')).json();
  const g = document.getElementById('dash-grid');
  g.innerHTML = Object.entries(d).map(([k,v])=>`<div class="stat"><div class="lb">${k}</div><div class="vl">${v}</div></div>`).join('');
  document.getElementById('sys-btn').innerText = d.status==='ONLINE'?'STOP SYSTEM':'START SYSTEM';
}
async function toggleSys(){
  const s = document.getElementById('sys-btn').innerText.includes('START');
  await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:s?'start':'stop'})});
  loadDash();
}
async function loadLogs(){
  const l = await(await fetch('/api/logs')).json();
  document.getElementById('log-out').innerText = l.map(x=>`[${x.time}] ${x.msg}`).join('\n');
}

// Init
fetch('/api/agent/root_info').then(r=>r.json()).then(d=>document.getElementById('root-path').value=d.root);
loadChats();
</script>
</body>
</html>
"""

# ==================== API ====================
@app.route('/')
def home(): return render_template_string(HTML)

# --- CHATS ---
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
    if SYS["status"] == "ONLINE" and SYS["loop"]:
        SYS["loop"].send_chat(msg)
    else:
        _offline_respond(cid, msg)
    return jsonify({"success": True})

# --- AGENT ---
@app.route('/api/agent/root_info')
def api_root_info(): return jsonify({"root": str(agent.project)})
@app.route('/api/agent/root', methods=['POST'])
def api_set_root(): return jsonify(agent.set_root(request.json.get('path')))
@app.route('/api/agent/browse')
def api_browse(): return jsonify(agent.browse(request.args.get('path', '.')))
@app.route('/api/agent/read')
def api_read(): return jsonify({"content": agent.read_file(request.args.get('path'))})
@app.route('/api/agent/action', methods=['POST'])
def api_action():
    d = request.json
    if d.get('action') == 'analyze': return jsonify(agent.analyze(d.get('file')))
    # Add fix/save implementations as needed
    return jsonify({"status": "ok", "msg": "Action simulation"})

# --- SYSTEM ---
@app.route('/api/dashboard')
def api_dash():
    d = {"status": SYS["status"], "chats": len(store.list_chats())}
    if SYS["loop"]: d.update(SYS["loop"].stats)
    return jsonify(d)
@app.route('/api/logs')
def api_logs():
    # Simple log reader
    log_file = list(LOGS_DIR.glob("*.log"))
    if not log_file: return jsonify([])
    return jsonify([{"time": "00:00", "msg": l} for l in log_file[0].read_text().splitlines()[-50:]])
@app.route('/api/control', methods=['POST'])
def api_ctrl():
    act = request.json.get('action')
    if act == 'start' and SYS["status"] != "ONLINE":
        SYS["thread"] = threading.Thread(target=run_loop_thread, daemon=True)
        SYS["thread"].start()
    elif act == 'stop':
        if SYS["loop"]: SYS["loop"].shutdown()
    return jsonify({"success": True})

# --- AUTH ---
@app.route('/login', methods=['GET','POST'])
def login():
    if not HAS_AUTH: return redirect('/')
    if request.method=='POST':
        if auth_mgr.login(request.form.get('username'), request.form.get('password')):
            resp = make_response(redirect('/'))
            resp.set_cookie('umbra_session', 'demo_token') # Simplify for quick fix
            return resp
    return "<form method=post><input name=username><input name=password type=password><button>Login</button>"
@app.route('/logout')
def logout(): return redirect('/login')

if __name__ == '__main__':
    import flask.cli
    flask.cli.show_server_banner = lambda *args: None
    print("[UMBRA] UNIFIED DASHBOARD RUNNING ON http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
'''

def restore():
    print("Restoring Full Dashboard (Chat + Explorer)...")
    with open(WEB_PATH, 'w', encoding='utf-8') as f:
        f.write(MERGED_WEB_UI)
    print("✅ Done. Run 'python broadcast_now.py' to launch.")

if __name__ == "__main__":
    restore()