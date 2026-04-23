"""
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

# [PATCHED v2.1 UNIFIED]
app = Flask(__name__)
app.secret_key = os.urandom(24)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

try: from thinking import ThinkingEngine; HAS_THINKING = True
except ImportError: HAS_THINKING = False
try: from tunnel import Tunnel; HAS_TUNNEL = True
except ImportError: HAS_TUNNEL = False
try: from self_improve import SelfImproveOrchestrator; HAS_IMPROVE = True
except ImportError: HAS_IMPROVE = False
try: from browser_agent import BrowserAgent; HAS_BROWSER = True
except ImportError: HAS_BROWSER = False

_thinking_state = {}
_improve_status = {"phase": "idle"}
_improve_report = None
_tunnel_obj = None
_tunnel_url = None

def _llm():
    return UMBRA_ENGINE_OBJ

def _offline_respond(chat_id, message):
    llm = _llm()
    if HAS_THINKING and llm:
        try:
            engine = ThinkingEngine(ollama=llm, model="llama3")
            chain = engine.think(message, depth="normal")
            if chain.final_response:
                store.add_message(chat_id, "umbra", chain.final_response)
                return
        except: pass
    if llm:
        try:
            resp = llm.generate(model="llama3", prompt=message)
            text = resp.get("response", "").strip()
            if text:
                store.add_message(chat_id, "umbra", text)
                return
        except: pass
    store.add_message(chat_id, "umbra", "Offline. Start the system for full responses.")

def run_loop_thread():
    try:
        SYS["status"] = "ONLINE"
        SYS["loop"] = AutonomousLoop(dry_run=False)
        SYS["loop"].run()
    except Exception as e:
        SYS["status"] = "ERROR"; SYS["err"] = str(e)
    finally:
        SYS["status"] = "OFFLINE"; SYS["loop"] = None

# ==================== LOGIN HTML ====================
LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UMBRA | ACCESS</title>
<style>
body{background:#080a0f;color:#00d4ff;font-family:'Segoe UI',monospace;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.box{background:#161b22;border:1px solid #21262d;padding:40px;border-radius:8px;width:320px;text-align:center}
h1{font-size:24px;margin-bottom:20px;letter-spacing:2px}
input{width:100%;padding:10px;margin:10px 0;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:4px;box-sizing:border-box}
button{width:100%;padding:12px;background:#00d4ff;border:none;border-radius:4px;color:#000;font-weight:bold;cursor:pointer;margin-top:10px}
.err{color:#da3633;font-size:12px;margin-top:10px}
</style></head><body>
<div class="box">
    <h1>UMBRA UNIT-734</h1>
    <form method="POST">
        <input type="text" name="username" placeholder="Handler Identity" required autofocus>
        <input type="password" name="password" placeholder="Access Code" required>
        <button type="submit">INITIALIZE UPLINK</button>
    </form>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
</div></body></html>
"""

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
  <div class="sb-i" onclick="openSettings()" style="margin-top:auto" title="Settings">⚙️</div>
  <div class="sb-i" onclick="location.href='/logout'" style="color:var(--red)" title="Logout">🚪</div>
</div>

<div id="v-chat" class="view on">
  <div class="chat-wrap">
    <div class="chat-list">
      <div style="padding:10px;border-bottom:1px solid var(--bd);font-weight:bold;font-size:11px">CHATS <button onclick="newChat()" style="float:right">+</button></div>
      <div id="cl-items"></div>
      <div style="padding:10px"><button id="sys-btn" onclick="toggleSys()" style="width:100%">START SYSTEM</button></div>
      <div style="padding:0 10px 10px"><button id="improve-btn" onclick="startImprove()" style="width:100%;background:#1a6;color:#fff;border:none;padding:6px;border-radius:4px;cursor:pointer;font-size:11px">Optimize & Improve</button><div id="improve-status" style="font-size:10px;color:var(--dim);margin-top:4px"></div></div>
      <div style="padding:0 10px 10px"><button onclick="toggleTunnel()" id="tunnel-btn" style="width:100%;background:var(--card);color:var(--dim);border:1px solid var(--bd);padding:4px;border-radius:4px;cursor:pointer;font-size:10px">Local Only</button></div>
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
  var i=document.getElementById('msg-in'),btn=i.nextElementSibling;
  if(!i.value.trim()||!curChat||btn.disabled)return;
  btn.disabled=true;btn.textContent='...';
  var txt=i.value;i.value='';
  try{
    await fetch('/api/chats/'+curChat+'/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:txt})});
    await openChat(curChat);
    var lc=document.querySelectorAll('.msg').length,polls=0;
    var pv=setInterval(async function(){
      polls++;
      try{var ms=await(await fetch('/api/chats/'+curChat+'/messages')).json();
        if(ms.length>lc){await openChat(curChat);lc=ms.length;polls=0}
      }catch(e){}
      if(polls>60)clearInterval(pv);
    },2000);
  }catch(e){i.value=txt;}
  btn.disabled=false;btn.textContent='SEND';
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

// Settings
function openSettings(){
  var m=document.getElementById('settings-modal');
  if(m){m.style.display='flex';return;}
  m=document.createElement('div');m.id='settings-modal';
  m.style.cssText='position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:9999';
  m.innerHTML='<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:24px;width:340px;color:#c9d1d9">'
    +'<div style="display:flex;justify-content:space-between;margin-bottom:16px"><h3 style="margin:0;color:#00d4ff">Settings</h3><span onclick="document.getElementById(\'settings-modal\').style.display=\'none\'" style="cursor:pointer;color:#7d8590;font-size:18px">X</span></div>'
    +'<div id="settings-msg" style="font-size:12px;margin-bottom:12px"></div>'
    +'<div style="border-bottom:1px solid #21262d;padding-bottom:12px;margin-bottom:12px"><b style="font-size:13px">Password</b>'
    +'<input id="s-old-pw" type="password" placeholder="Current" style="width:100%;padding:8px;margin:4px 0;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:4px;box-sizing:border-box">'
    +'<input id="s-new-pw" type="password" placeholder="New" style="width:100%;padding:8px;margin:4px 0;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:4px;box-sizing:border-box">'
    +'<button onclick="changePw()" style="width:100%;padding:8px;margin-top:6px;background:#238636;border:none;border-radius:4px;color:#fff;cursor:pointer">Update</button></div>'
    +'<div><b style="font-size:13px">Username</b>'
    +'<input id="s-new-user" type="text" placeholder="New username" style="width:100%;padding:8px;margin:4px 0;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:4px;box-sizing:border-box">'
    +'<input id="s-user-pw" type="password" placeholder="Confirm password" style="width:100%;padding:8px;margin:4px 0;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:4px;box-sizing:border-box">'
    +'<button onclick="changeUser()" style="width:100%;padding:8px;margin-top:6px;background:#1f6feb;border:none;border-radius:4px;color:#fff;cursor:pointer">Update</button></div></div>';
  document.body.appendChild(m);
  m.addEventListener('click',function(e){if(e.target===m)m.style.display='none';});
}
async function changePw(){
  var msg=document.getElementById('settings-msg'),o=document.getElementById('s-old-pw').value,n=document.getElementById('s-new-pw').value;
  if(!o||!n){msg.innerHTML='<span style="color:#da3633">Fill both</span>';return;}
  var r=await(await fetch('/api/auth/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_password:o,new_password:n})})).json();
  msg.innerHTML=r.success?'<span style="color:#3fb950">Done!</span>':'<span style="color:#da3633">'+(r.error||'Failed')+'</span>';
}
async function changeUser(){
  var msg=document.getElementById('settings-msg'),u=document.getElementById('s-new-user').value,p=document.getElementById('s-user-pw').value;
  if(!u||!p){msg.innerHTML='<span style="color:#da3633">Fill both</span>';return;}
  var r=await(await fetch('/api/auth/change-username',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({new_username:u,password:p})})).json();
  msg.innerHTML=r.success?'<span style="color:#3fb950">Now: '+r.new_username+'</span>':'<span style="color:#da3633">'+(r.error||'Failed')+'</span>';
}
async function startImprove(){
  var btn=document.getElementById('improve-btn'),st=document.getElementById('improve-status');
  btn.disabled=true;btn.textContent='Running...';
  await fetch('/api/improve/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
  var iv=setInterval(async function(){
    var s=await(await fetch('/api/improve/status')).json();
    st.textContent=(s.phase||'...')+' '+(s.detail||'');
    if(s.phase==='complete'||s.phase==='error'){clearInterval(iv);btn.disabled=false;btn.textContent='Optimize & Improve';
      if(s.phase==='complete')st.textContent='Done: '+(s.accepted||0)+' accepted, '+(s.rejected||0)+' rejected';}
  },2000);
}
async function toggleTunnel(){
  var btn=document.getElementById('tunnel-btn');
  if(btn.textContent.indexOf('Local')>=0){
    btn.textContent='Starting...';
    try{var r=await(await fetch('/api/tunnel/start',{method:'POST'})).json();btn.textContent=r.url?'Public: '+r.url:'Failed';}catch(e){btn.textContent='Error';}
  }else{await fetch('/api/tunnel/stop',{method:'POST'});btn.textContent='Local Only';}
}
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
    if SYS["status"] == "ONLINE" and SYS["loop"]:
        SYS["loop"].send_chat(msg)
        def _wait(chat_id):
            try:
                resp = SYS["loop"].get_chat_response(timeout=120)
                if resp and resp.get("response"):
                    store.add_message(chat_id, "umbra", resp["response"])
                else:
                    store.add_message(chat_id, "umbra", "Processed but no response generated.")
            except Exception as e:
                store.add_message(chat_id, "umbra", f"Error: {e}")
        threading.Thread(target=_wait, args=(cid,), daemon=True).start()
    else:
        _offline_respond(cid, msg)
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
# === Auth ===
@app.before_request
def require_login():
    if not HAS_AUTH: return
    if request.endpoint in ('login', 'static'): return
    token = request.cookies.get('umbra_session')
    if not auth_mgr.validate_session(token):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Not authenticated"}), 401
        return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if not HAS_AUTH: return redirect('/')
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        token = auth_mgr.login(u, p)
        if token:
            resp = make_response(redirect('/'))
            resp.set_cookie('umbra_session', token, httponly=True, max_age=60*60*24*7)
            return resp
        return render_template_string(LOGIN_HTML, error="Invalid credentials")
    return render_template_string(LOGIN_HTML, error=None)

@app.route('/logout')
def logout():
    token = request.cookies.get('umbra_session')
    if auth_mgr and token: auth_mgr.logout(token)
    resp = make_response(redirect('/login'))
    resp.set_cookie('umbra_session', '', expires=0)
    return resp

@app.route('/api/auth/change-password', methods=['POST'])
def api_change_password():
    token = request.cookies.get('umbra_session')
    username = auth_mgr.validate_session(token) if auth_mgr else None
    if not username: return jsonify({"error": "Not logged in"}), 401
    data = request.json or {}
    result = auth_mgr.change_password(username, data.get('old_password',''), data.get('new_password',''))
    if result["success"]:
        new_token = auth_mgr.login(username, data['new_password'])
        resp = jsonify(result)
        if new_token: resp.set_cookie('umbra_session', new_token, httponly=True, max_age=60*60*24*7)
        return resp
    return jsonify(result), 400

@app.route('/api/auth/change-username', methods=['POST'])
def api_change_username():
    token = request.cookies.get('umbra_session')
    username = auth_mgr.validate_session(token) if auth_mgr else None
    if not username: return jsonify({"error": "Not logged in"}), 401
    data = request.json or {}
    result = auth_mgr.change_username(username, data.get('password',''), data.get('new_username',''))
    if result["success"]:
        new_token = auth_mgr.login(data['new_username'], data['password'])
        resp = jsonify(result)
        if new_token: resp.set_cookie('umbra_session', new_token, httponly=True, max_age=60*60*24*7)
        return resp
    return jsonify(result), 400

@app.route('/api/improve/start', methods=['POST'])
def api_improve_start():
    global _improve_status, _improve_report
    if not HAS_IMPROVE: return jsonify({"error": "self_improve.py not found"})
    if _improve_status.get("phase") not in ("idle","complete","error"): return jsonify({"error": "Running"})
    def _run():
        global _improve_status, _improve_report
        try:
            _improve_status = {"phase": "inspecting", "detail": "Scanning..."}
            orch = SelfImproveOrchestrator(project_dir=str(BASE_DIR), ollama=_llm(), model="llama3", max_proposals=5)
            report = orch.run(auto_deploy=False)
            _improve_report = report
            _improve_status = {"phase":"complete","accepted":sum(1 for r in report.get("results",[]) if r.get("verdict")=="accepted"),"rejected":sum(1 for r in report.get("results",[]) if r.get("verdict")=="rejected")}
        except Exception as e:
            _improve_status = {"phase":"error","error":str(e)}
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"started": True})

@app.route('/api/improve/status')
def api_improve_status(): return jsonify(_improve_status)
@app.route('/api/improve/report')
def api_improve_report(): return jsonify(json.loads(json.dumps(_improve_report or {}, default=str)))

@app.route('/api/tunnel/start', methods=['POST'])
def api_tunnel_start():
    global _tunnel_obj, _tunnel_url
    if not HAS_TUNNEL: return jsonify({"error": "tunnel.py not found"})
    if _tunnel_obj and _tunnel_url: return jsonify({"url": _tunnel_url})
    _tunnel_obj = Tunnel(port=5000); _tunnel_url = _tunnel_obj.start()
    return jsonify({"url": _tunnel_url})

@app.route('/api/tunnel/stop', methods=['POST'])
def api_tunnel_stop():
    global _tunnel_obj, _tunnel_url
    if _tunnel_obj: _tunnel_obj.stop()
    _tunnel_obj = None; _tunnel_url = None
    return jsonify({"stopped": True})

@app.route('/api/tunnel/status')
def api_tunnel_status(): return jsonify({"running": bool(_tunnel_url), "url": _tunnel_url})

if __name__ == '__main__':
    import flask.cli
    flask.cli.show_server_banner = lambda *args: None
    if auth_mgr:
        creds = auth_mgr._load()
        print(f"[UMBRA] Login: {creds.get('username','admin')} / {'*'*len(creds.get('password',''))}")
    print("[UMBRA] UNIFIED DASHBOARD + EXPLORER RUNNING ON http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
