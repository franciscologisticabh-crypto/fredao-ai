"""
╔══════════════════════════════════════════════╗
║         FREDÃO  –  Sua IA Pessoal            ║
║         Backend Flask + Google Gemini        ║
╚══════════════════════════════════════════════╝

Como usar:
  1. pip install flask google-genai python-dotenv gunicorn
  2. Crie um arquivo .env com: GEMINI_API_KEY=sua_chave_aqui
     Obtenha grátis em: https://aistudio.google.com/app/apikey
  3. python fredao.py
  4. Abra http://127.0.0.1:8080 no navegador

Para deploy no Render:
  - Adicione GEMINI_API_KEY como variável de ambiente no painel do Render
  - Nunca suba o .env para o GitHub!
"""

from flask import Flask, request, jsonify, session
from google import genai
from google.genai import types
from dotenv import load_dotenv
import uuid, os

# ═══════════════════════════════════════════════
#  CONFIGURAÇÃO
# ═══════════════════════════════════════════════
load_dotenv()  # carrega o .env localmente (ignorado no Render)

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL   = "gemini-2.5-flash"
PORT    = int(os.environ.get("PORT", 8080))
# ═══════════════════════════════════════════════

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY não encontrada!\n"
        "Local: crie um arquivo .env com GEMINI_API_KEY=sua_chave\n"
        "Render: adicione a variável de ambiente no painel"
    )

SYSTEM_PROMPT = """
Você é o FREDÃO, uma IA simpática, inteligente e bem-humorada criada para ajudar o seu usuário.
- Fala de forma natural, como um amigo próximo, mas sem perder a inteligência.
- Responde perguntas técnicas, cotidianas, criativas ou filosóficas com igual disposição.
- Usa um toque de bom humor sem exagerar.
- É direto quando necessário, mas sempre gentil.
- Se apresenta como "FREDÃO" quando perguntado sobre quem é.
- Responde sempre em português do Brasil, a menos que o usuário escreva em outro idioma.
Lembre-se: você é o FREDÃO — confiante, prestativo e com personalidade própria!
""".strip()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", os.urandom(24))

# ─── Configura o Gemini (nova SDK google-genai) ───
client = genai.Client(api_key=API_KEY)

# Históricos por sessão: { sid: [types.Content(...)] }
historicos: dict = {}

# ─── HTML embutido ────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>FREDÃO – Sua IA Pessoal</title>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
:root{
  --bg:#0d0d0d;--sb:#111;--sf:#1a1a1a;--s2:#222;--br:#2a2a2a;
  --ac:#4285f4;--ad:#1a56c4;--ag:rgba(66,133,244,.18);
  --ub:#1e3a5f;--ab:#1c1c1c;--tx:#e8e6e1;--mt:#666;
  --r:14px;--fn:'Sora',sans-serif;--mo:'JetBrains Mono',monospace;
  --sw:260px;--t:.2s ease;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;font-family:var(--fn);background:var(--bg);color:var(--tx);overflow:hidden}
.shell{display:flex;height:100vh}
.sidebar{width:var(--sw);background:var(--sb);border-right:1px solid var(--br);display:flex;flex-direction:column;flex-shrink:0;z-index:100;transition:transform var(--t)}
.sh{padding:20px 16px 16px;border-bottom:1px solid var(--br);display:flex;align-items:center;gap:10px}
.lm{width:36px;height:36px;background:var(--ac);border-radius:10px;display:grid;place-items:center;font-size:18px;flex-shrink:0;box-shadow:0 0 16px var(--ag)}
.lt{font-size:17px;font-weight:700;letter-spacing:-.4px}.ls{font-size:10px;color:var(--mt)}
.ncb{margin:12px;padding:10px 14px;background:var(--s2);border:1px solid var(--br);border-radius:var(--r);color:var(--tx);font-family:var(--fn);font-size:13px;cursor:pointer;display:flex;align-items:center;gap:8px;transition:background var(--t),border-color var(--t)}
.ncb:hover{background:var(--sf);border-color:var(--ad)}
.ch{flex:1;overflow-y:auto;padding:4px 8px}
.hl{font-size:10px;color:var(--mt);text-transform:uppercase;letter-spacing:1px;padding:10px 8px 6px}
.hi{padding:9px 10px;border-radius:10px;font-size:12.5px;color:#888;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:background var(--t),color var(--t)}
.hi:hover,.hi.active{background:var(--s2);color:var(--tx)}
.sf2{padding:12px;border-top:1px solid var(--br)}
.ib{background:var(--s2);border:1px solid var(--br);border-radius:var(--r);padding:12px 14px;font-size:12px;color:var(--mt);line-height:1.6}
.ib strong{color:var(--ac)}.mbadge{display:inline-block;margin-top:6px;padding:2px 8px;background:var(--ad);color:#fff;border-radius:20px;font-size:10.5px;font-weight:600}
.main{flex:1;display:flex;flex-direction:column;min-width:0}
.tb{padding:14px 20px;border-bottom:1px solid var(--br);display:flex;align-items:center;gap:12px;background:rgba(13,13,13,.9);backdrop-filter:blur(10px);flex-shrink:0}
.hb{display:none;background:none;border:none;color:var(--tx);cursor:pointer;padding:4px}
.tt{font-size:15px;font-weight:600}.ts{font-size:11px;color:var(--mt)}
.spill{margin-left:auto;display:flex;align-items:center;gap:6px;padding:4px 10px;background:var(--s2);border:1px solid var(--br);border-radius:20px;font-size:11px;color:var(--mt)}
.sdot{width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 7px #22c55e88;transition:background var(--t)}
.sdot.loading{background:var(--ac);box-shadow:0 0 7px var(--ag);animation:blink .7s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.clrbtn{background:none;border:1px solid var(--br);border-radius:8px;color:var(--mt);font-family:var(--fn);font-size:11px;padding:5px 10px;cursor:pointer;transition:color var(--t),border-color var(--t)}
.clrbtn:hover{color:var(--tx);border-color:var(--ad)}
.msgs{flex:1;overflow-y:auto;padding:28px 0;scroll-behavior:smooth}
.msgs::-webkit-scrollbar{width:4px}.msgs::-webkit-scrollbar-thumb{background:var(--br);border-radius:4px}
.mr{display:flex;gap:14px;padding:5px 20px;max-width:860px;margin:0 auto;width:100%;animation:fu .28s ease forwards;opacity:0;transform:translateY(8px)}
@keyframes fu{to{opacity:1;transform:translateY(0)}}
.mr.user{flex-direction:row-reverse}
.av{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font-size:16px;flex-shrink:0;align-self:flex-end}
.av.fredao{background:var(--ac);box-shadow:0 0 10px var(--ag)}.av.user{background:var(--ub)}
.mw{display:flex;flex-direction:column;max-width:75%}.mr.user .mw{align-items:flex-end}
.bn{font-size:10px;color:var(--mt);margin-bottom:4px;font-weight:500}
.bb{padding:12px 16px;border-radius:18px;font-size:14px;line-height:1.7}
.bb.fredao{background:var(--ab);border:1px solid var(--br);border-bottom-left-radius:4px}
.bb.user{background:var(--ub);border-bottom-right-radius:4px;color:#cde}
.bb strong{color:#fff}.bb em{color:#aaa}
.bb code{font-family:var(--mo);background:#111;border:1px solid var(--br);border-radius:5px;padding:1px 6px;font-size:12.5px;color:var(--ac)}
.bb pre{background:#111;border:1px solid var(--br);border-radius:8px;padding:12px 14px;overflow-x:auto;margin:10px 0}
.bb pre code{background:none;border:none;padding:0;font-size:12px;color:#ccc}
.ty{display:flex;align-items:center;gap:5px;padding:13px 16px;background:var(--ab);border:1px solid var(--br);border-radius:18px;border-bottom-left-radius:4px}
.ty span{width:7px;height:7px;background:var(--ac);border-radius:50%;animation:bo .8s infinite}
.ty span:nth-child(2){animation-delay:.15s}.ty span:nth-child(3){animation-delay:.3s}
@keyframes bo{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-7px)}}
.es{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:40px;text-align:center;color:var(--mt)}
.bi{font-size:62px;line-height:1;animation:fl 3s ease-in-out infinite}
@keyframes fl{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
.es h2{font-size:22px;color:var(--tx);font-weight:700}.es p{font-size:13px;max-width:360px;line-height:1.65}
.sugs{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:10px}
.pill{padding:8px 14px;background:var(--s2);border:1px solid var(--br);border-radius:20px;font-size:12.5px;color:var(--tx);cursor:pointer;transition:border-color var(--t),background var(--t)}
.pill:hover{border-color:var(--ac);background:var(--ag)}
.ia{padding:14px 20px 18px;border-top:1px solid var(--br);background:var(--bg);flex-shrink:0}
.ibox{max-width:860px;margin:0 auto;background:var(--sf);border:1px solid var(--br);border-radius:16px;display:flex;align-items:flex-end;gap:10px;padding:10px 12px;transition:border-color var(--t),box-shadow var(--t)}
.ibox:focus-within{border-color:var(--ac);box-shadow:0 0 0 3px var(--ag)}
#ui{flex:1;background:transparent;border:none;outline:none;color:var(--tx);font-family:var(--fn);font-size:14px;line-height:1.5;resize:none;max-height:200px;padding:4px 0}
#ui::placeholder{color:var(--mt)}
.sbtn{width:36px;height:36px;background:var(--ac);border:none;border-radius:10px;cursor:pointer;display:grid;place-items:center;color:#fff;flex-shrink:0;box-shadow:0 0 12px var(--ag);transition:background var(--t),transform var(--t)}
.sbtn:hover{background:var(--ad);transform:scale(1.06)}.sbtn:active{transform:scale(.94)}
.sbtn:disabled{background:var(--s2);box-shadow:none;cursor:default;transform:none}
.ifoot{text-align:center;font-size:11px;color:var(--mt);margin-top:8px;max-width:860px;margin-left:auto;margin-right:auto}
@media(max-width:680px){.sidebar{position:fixed;top:0;left:0;height:100%;transform:translateX(-100%)}.sidebar.open{transform:translateX(0);box-shadow:4px 0 20px #000a}.hb{display:block}.mw{max-width:88%}}
*{scrollbar-width:thin;scrollbar-color:var(--br) transparent}
</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar" id="sidebar">
    <div class="sh">
      <div class="lm">&#x1F916;</div>
      <div><div class="lt">FREDÃO</div><div class="ls">Powered by Gemini</div></div>
    </div>
    <button class="ncb" onclick="newChat()">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      Nova Conversa
    </button>
    <div class="ch" id="ch"><div class="hl">Recentes</div></div>
    <div class="sf2">
      <div class="ib">
        &#x1F512; <strong>API Key protegida</strong><br>
        Sua chave fica apenas no servidor Python.<br><br>
        &#x1F9E0; Modelo ativo:<br>
        <span class="mbadge" id="mdlbadge">carregando...</span>
      </div>
    </div>
  </aside>

  <main class="main">
    <div class="tb">
      <button class="hb" onclick="toggleSB()">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
      <div><div class="tt">&#x1F916; FREDÃO</div><div class="ts" id="ts">Pronto para conversar</div></div>
      <button class="clrbtn" onclick="newChat()">&#x1F5D1; Limpar</button>
      <div class="spill"><div class="sdot" id="sd"></div><span id="stx">Online</span></div>
    </div>

    <div class="msgs" id="msgs">
      <div class="es" id="es">
        <div class="bi">&#x1F916;</div>
        <h2>Olá! Eu sou o FREDÃO</h2>
        <p>Sua IA pessoal com personalidade, agora movido pelo Google Gemini — grátis!</p>
        <div class="sugs">
          <span class="pill" onclick="sug(this)">&#x1F4A1; O que é inteligência artificial?</span>
          <span class="pill" onclick="sug(this)">&#x1F4DD; Escreve um e-mail profissional</span>
          <span class="pill" onclick="sug(this)">&#x1F9E0; Me dá 5 ideias de negócio</span>
          <span class="pill" onclick="sug(this)">&#x1F602; Conta uma piada boa</span>
          <span class="pill" onclick="sug(this)">&#x1F40D; Como aprender Python do zero?</span>
          <span class="pill" onclick="sug(this)">&#x1F30D; Qual a capital da Austrália?</span>
        </div>
      </div>
    </div>

    <div class="ia">
      <div class="ibox">
        <textarea id="ui" rows="1" placeholder="Escreva sua mensagem para o FREDÃO..."></textarea>
        <button class="sbtn" id="sbtn" onclick="send()" title="Enviar (Enter)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
      <div class="ifoot">Backend Python + Flask &nbsp;&middot;&nbsp; Google Gemini (gratuito) &nbsp;&middot;&nbsp; Shift+Enter para nova linha</div>
    </div>
  </main>
</div>

<script>
var busy=false, sessions=JSON.parse(localStorage.getItem('frs')||'[]'), cidx=null;

fetch('/info').then(function(r){return r.json()}).then(function(d){
  document.getElementById('mdlbadge').textContent=d.model;
});

var ta=document.getElementById('ui');
ta.addEventListener('input',function(){ta.style.height='auto';ta.style.height=Math.min(ta.scrollHeight,200)+'px'});
ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});

async function send(){
  if(busy)return;
  var txt=ta.value.trim();if(!txt)return;
  var es=document.getElementById('es');if(es)es.remove();
  addMsg('user',txt);ta.value='';ta.style.height='auto';
  setLoading(true);var tr=addTyping();
  try{
    var r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:txt})});
    var d=await r.json();tr.remove();
    if(!r.ok)throw new Error(d.error||'Erro '+r.status);
    addMsg('fredao',d.reply);saveSess(txt);
  }catch(e){tr.remove();addMsg('fredao','Erro: '+e.message)}
  setLoading(false);
}

function addMsg(role,content){
  var w=document.getElementById('msgs');
  var row=document.createElement('div');row.className='mr '+role;
  var av=document.createElement('div');av.className='av '+role;av.textContent=role==='user'?'👤':'🤖';
  var mw=document.createElement('div');mw.className='mw';
  var bn=document.createElement('div');bn.className='bn';bn.textContent=role==='user'?'Você':'FREDÃO';
  var bb=document.createElement('div');bb.className='bb '+role;bb.innerHTML=fmt(content);
  mw.appendChild(bn);mw.appendChild(bb);row.appendChild(av);row.appendChild(mw);w.appendChild(row);
  w.scrollTop=w.scrollHeight;
}

function addTyping(){
  var w=document.getElementById('msgs');
  var row=document.createElement('div');row.className='mr fredao';
  var av=document.createElement('div');av.className='av fredao';av.textContent='🤖';
  var mw=document.createElement('div');mw.className='mw';
  var bn=document.createElement('div');bn.className='bn';bn.textContent='FREDÃO';
  var ty=document.createElement('div');ty.className='ty';ty.innerHTML='<span></span><span></span><span></span>';
  mw.appendChild(bn);mw.appendChild(ty);row.appendChild(av);row.appendChild(mw);w.appendChild(row);
  w.scrollTop=w.scrollHeight;return row;
}

function fmt(t){
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/```[\w]*\n?([\s\S]*?)```/g,function(_,c){return '<pre><code>'+c.trim()+'</code></pre>'})
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,'<em>$1</em>')
    .replace(/\n/g,'<br>');
}

function setLoading(s){
  busy=s;document.getElementById('sbtn').disabled=s;
  document.getElementById('ts').textContent=s?'FREDÃO está pensando...':'Pronto para conversar';
  var sd=document.getElementById('sd'),stx=document.getElementById('stx');
  if(s){sd.classList.add('loading');stx.textContent='Pensando...'}
  else{sd.classList.remove('loading');stx.textContent='Online'}
}

async function newChat(){
  await fetch('/clear',{method:'POST'});cidx=null;
  var w=document.getElementById('msgs');w.innerHTML='';
  var es=document.createElement('div');es.className='es';es.id='es';
  es.innerHTML='<div class="bi">&#x1F916;</div><h2>Olá! Eu sou o FREDÃO</h2><p>Pode me perguntar qualquer coisa!</p>'
    +'<div class="sugs">'
    +'<span class="pill" onclick="sug(this)">&#x1F4A1; O que é inteligência artificial?</span>'
    +'<span class="pill" onclick="sug(this)">&#x1F4DD; Escreve um e-mail profissional</span>'
    +'<span class="pill" onclick="sug(this)">&#x1F9E0; Me dá 5 ideias de negócio</span>'
    +'<span class="pill" onclick="sug(this)">&#x1F602; Conta uma piada boa</span>'
    +'</div>';
  w.appendChild(es);ta.focus();closeSB();
}

function sug(el){
  ta.value=el.textContent.replace(/^\S+\s/,'');send();
}

function saveSess(msg){
  if(cidx===null){
    sessions.unshift({title:msg.slice(0,46)});cidx=0;
    if(sessions.length>20)sessions.pop();
    localStorage.setItem('frs',JSON.stringify(sessions));renderH();
  }
}
function renderH(){
  var el=document.getElementById('ch');el.innerHTML='<div class="hl">Recentes</div>';
  if(!sessions.length){el.innerHTML+='<div style="font-size:12px;color:var(--mt);padding:8px 10px">Nenhuma conversa ainda</div>';return}
  sessions.forEach(function(s,i){
    var d=document.createElement('div');d.className='hi'+(i===cidx?' active':'');
    d.textContent='💬 '+s.title;el.appendChild(d);
  });
}

function toggleSB(){document.getElementById('sidebar').classList.toggle('open')}
function closeSB(){document.getElementById('sidebar').classList.remove('open')}
renderH();
</script>
</body>
</html>"""

# ─── ROTAS ────────────────────────────────────

@app.route("/")
def index():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return HTML

@app.route("/info")
def info():
    return jsonify({"model": MODEL})

@app.route("/chat", methods=["POST"])
def chat():
    sid  = session.get("sid", "default")
    data = request.get_json(force=True)
    msg  = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"error": "Mensagem vazia"}), 400

    if sid not in historicos:
        historicos[sid] = []

    try:
        # Adiciona mensagem do usuário ao histórico
        historicos[sid].append(
            types.Content(role="user", parts=[types.Part(text=msg)])
        )

        # Chama a nova SDK google-genai com histórico e system prompt
        response = client.models.generate_content(
            model=MODEL,
            contents=historicos[sid],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.8,
            ),
        )

        reply = response.text.strip()

        # Salva resposta do modelo no histórico
        historicos[sid].append(
            types.Content(role="model", parts=[types.Part(text=reply)])
        )

        return jsonify({"reply": reply})

    except Exception as e:
        # Remove a última mensagem do usuário em caso de erro
        if historicos.get(sid):
            historicos[sid].pop()
        return jsonify({"error": str(e)}), 500

@app.route("/clear", methods=["POST"])
def clear():
    sid = session.get("sid", "default")
    historicos.pop(sid, None)
    return jsonify({"ok": True})

# ─── ENTRY POINT ──────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*45)
    print("  FREDAO esta online! (Google Gemini)")
    print("  Acesse: http://127.0.0.1:" + str(PORT))
    print("  Modelo: " + MODEL)
    print("  Para encerrar: Ctrl+C")
    print("="*45 + "\n")
    app.run(host="0.0.0.0", port=PORT, debug=True)
