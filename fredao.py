# fredao.py

# =========================================================
# FREDÃO ULTRA — FRONT PREMIUM + BACKEND INTELIGENTE
# =========================================================

from flask import Flask, request, jsonify, session
from google import genai
from google.genai import types
from dotenv import load_dotenv
from supabase import create_client, Client

import uuid
import os
import re

# =========================================================
# CONFIG
# =========================================================

load_dotenv()

API_KEY       = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL  = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY", "")

MODEL = "gemini-2.5-flash"
PORT = int(os.environ.get("PORT", 8080))

CEP_ORIGEM     = "30441194"
CEP_ORIGEM_FMT = "30441-194"

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY não encontrada")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL/SUPABASE_KEY ausentes")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# APP
# =========================================================

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", os.urandom(24))

client = genai.Client(api_key=API_KEY)

historicos = {}
contextos = {}

# =========================================================
# CONSULTAS
# =========================================================


def limpar_cep(cep: str) -> str:
    return re.sub(r"\D", "", cep or "")



def consultar_por_cep(cep: str):

    cep_limpo = limpar_cep(cep)

    if len(cep_limpo) != 8:
        return []

    try:

        cep_int = int(cep_limpo)

        resp = (
            supabase.table("nova_base")
            .select(
                """
                transportadora,
                base,
                cidade,
                uf,
                tipo_entrega,
                prazo_entrega,
                envio_kit,
                envio_receptor,
                envio_acessorios,
                coleta,
                entrega,
                st
                """
            )
            .lte("cep_inicial", cep_int)
            .gte("cep_final", cep_int)
            .order("prazo_entrega")
            .execute()
        )

        print("\n========== DEBUG SUPABASE ==========")
        print("CEP:", cep_limpo)
        print("RESULTADO:", resp.data)
        print("====================================\n")

        return resp.data or []

    except Exception as e:
        print("ERRO SUPABASE:", e)
        return []



def consultar_por_cidade(cidade: str, uf: str = None):

    try:

        cidade = cidade.strip().upper()

        q = (
            supabase.table("nova_base")
            .select("*")
            .eq("cidade", cidade)
        )

        if uf:
            q = q.eq("uf", uf.upper())

        resp = (
            q.order("prazo_entrega")
             .limit(10)
             .execute()
        )

        return resp.data or []

    except Exception as e:
        print("ERRO CIDADE:", e)
        return []

# =========================================================
# EXTRAÇÕES
# =========================================================


def extrair_cep(texto):

    match = re.search(r"\b\d{5}-?\d{3}\b", texto)

    if not match:
        return None

    return limpar_cep(match.group())



def extrair_tipo_envio(texto):

    texto = texto.lower()

    tipos = []

    if any(x in texto for x in ["kit", "kits"]):
        tipos.append("kit")

    if any(x in texto for x in ["receptor", "receptores"]):
        tipos.append("receptor")

    if any(x in texto for x in [
        "acessorio",
        "acessorios",
        "acessório",
        "acessórios",
        "peca",
        "peça"
    ]):
        tipos.append("acessorios")

    if any(x in texto for x in [
        "todos",
        "tudo",
        "os 3",
        "os três",
        "todas"
    ]):
        return ["kit", "receptor", "acessorios"]

    return tipos



def extrair_cidade_uf(texto):

    ufs = [
        "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG",
        "MS","MT","PA","PB","PE","PI","PR","RJ","RN","RO",
        "RR","RS","SC","SE","SP","TO"
    ]

    texto_upper = texto.upper()

    uf = None

    for item in ufs:
        if re.search(rf"\b{item}\b", texto_upper):
            uf = item
            break

    padrao = re.search(
        r"(?:para|cidade|destino|em)\s+([A-Za-zÀ-ú\s]{3,40})",
        texto,
        re.IGNORECASE
    )

    cidade = None

    if padrao:
        cidade = padrao.group(1).strip()

        if uf:
            cidade = re.sub(
                rf"\b{uf}\b",
                "",
                cidade,
                flags=re.IGNORECASE
            ).strip()

    return cidade, uf

# =========================================================
# FORMATADOR
# =========================================================


def formatar_resultados(dados, origem, tipos=None):

    if not dados:
        return "[SEM_COBERTURA]"

    linhas = []

    linhas.append(
        f"📦 Origem fixa: {CEP_ORIGEM_FMT} (Matriz BH)\n"
    )

    for item in dados:

        coleta = "✅ Sim" if item.get("coleta") == "Y" else "❌ Não"
        entrega = "✅ Sim" if item.get("entrega") == "Y" else "❌ Não"

        valores = []

        if not tipos or "kit" in tipos:
            valores.append(
                f"📦 KIT: R$ {item.get('envio_kit')}"
            )

        if not tipos or "receptor" in tipos:
            valores.append(
                f"📡 RECEPTOR: R$ {item.get('envio_receptor')}"
            )

        if not tipos or "acessorios" in tipos:
            valores.append(
                f"🔧 ACESSÓRIOS: R$ {item.get('envio_acessorios')}"
            )

        bloco = f"""
🚚 {item.get("transportadora")}
📍 Base: {item.get("base")}
🏙 Destino: {item.get("cidade")}/{item.get("uf")}
📦 Tipo: {item.get("tipo_entrega")}
⏱ Prazo: {item.get("prazo_entrega")} dias úteis
🛻 Coleta: {coleta}
📬 Entrega: {entrega}

{" | ".join(valores)}
        """

        linhas.append(bloco)

    return "\n".join(linhas)

# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
Você é o FREDÃO ULTRA.

Você é:
- extremamente inteligente
- rápido
- corporativo
- humano
- objetivo
- amigável

REGRAS IMPORTANTES:

- Nunca invente valores
- Nunca invente cobertura
- Use SOMENTE os dados enviados pelo sistema
- Se não houver dados, informe isso claramente
- Seja conversacional
- Compare transportadoras
- Sugira melhor opção
- Explique D2D e ST naturalmente
- Destaque prazos e valores
- Seja útil como um operador logístico especialista

IMPORTANTE:
O backend SEMPRE envia dados reais do Supabase.
Você NÃO deve criar informações sozinho.
"""

# =========================================================
# FRONT PREMIUM
# =========================================================

HTML = r'''<!DOCTYPE html>
<html lang="pt-BR">

<head>

<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>

<title>FREDÃO</title>

<link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>

<style>

:root{

    --bg:#081120;
    --bg2:#0f172a;

    --card:#172033;
    --card2:#1e293b;

    --primary:#2563eb;
    --primary2:#1d4ed8;

    --border:#334155;

    --text:#ffffff;
    --muted:#94a3b8;

}

*{
    margin:0;
    padding:0;
    box-sizing:border-box;
}

body{

    background:
        radial-gradient(circle at top,#12203f 0%,#081120 45%);

    color:var(--text);

    font-family:'Sora',sans-serif;

    height:100vh;

    overflow:hidden;

}

.shell{

    display:flex;
    height:100vh;

}

.sidebar{

    width:270px;

    background:rgba(15,23,42,.95);

    border-right:1px solid rgba(255,255,255,.06);

    backdrop-filter:blur(20px);

    display:flex;
    flex-direction:column;

}

.logo{

    padding:30px;

    border-bottom:1px solid rgba(255,255,255,.06);

    font-size:28px;

    font-weight:700;

    display:flex;
    align-items:center;
    gap:12px;

}

.logo-icon{

    font-size:34px;

    animation:floatRobot 3s ease-in-out infinite;

}

.newchat{

    margin:18px;

    padding:16px;

    background:linear-gradient(
        135deg,
        var(--primary),
        var(--primary2)
    );

    border:none;

    border-radius:16px;

    color:white;

    cursor:pointer;

    font-weight:600;

    font-size:15px;

    transition:.25s;

}

.newchat:hover{

    transform:translateY(-2px);

    box-shadow:
        0 10px 30px rgba(37,99,235,.35);

}

.main{

    flex:1;

    display:flex;
    flex-direction:column;

}

.topbar{

    height:85px;

    border-bottom:1px solid rgba(255,255,255,.06);

    background:rgba(8,17,32,.75);

    backdrop-filter:blur(20px);

    display:flex;

    align-items:center;

    justify-content:space-between;

    padding:0 35px;

}

.title{

    font-size:24px;

    font-weight:700;

}

.status{

    color:#22c55e;

    font-size:14px;

    display:flex;
    align-items:center;
    gap:8px;

}

.status-dot{

    width:10px;
    height:10px;

    background:#22c55e;

    border-radius:50%;

    box-shadow:
        0 0 12px #22c55e;

}

.chat{

    flex:1;

    overflow-y:auto;

    padding:40px;

}

.chat::-webkit-scrollbar{
    width:8px;
}

.chat::-webkit-scrollbar-thumb{
    background:#23304d;
    border-radius:10px;
}

.row{

    display:flex;

    margin-bottom:28px;

    animation:fadeIn .25s ease;

}

.row.user{

    justify-content:flex-end;

}

.bubble{

    max-width:78%;

    padding:22px;

    border-radius:22px;

    line-height:1.8;

    font-size:14px;

    white-space:pre-wrap;

    box-shadow:
        0 8px 30px rgba(0,0,0,.25);

}

.bot .bubble{

    background:rgba(23,32,51,.95);

    border:1px solid rgba(255,255,255,.06);

}

.user .bubble{

    background:linear-gradient(
        135deg,
        var(--primary),
        var(--primary2)
    );

}

.input-area{

    padding:24px;

    border-top:1px solid rgba(255,255,255,.06);

    background:rgba(8,17,32,.85);

    backdrop-filter:blur(20px);

}

.input-box{

    background:rgba(23,32,51,.95);

    border:1px solid rgba(255,255,255,.06);

    border-radius:22px;

    display:flex;

    align-items:flex-end;

    gap:14px;

    padding:14px;

}

textarea{

    flex:1;

    background:transparent;

    border:none;

    resize:none;

    outline:none;

    color:white;

    font-size:15px;

    line-height:1.6;

    font-family:'Sora',sans-serif;

    max-height:180px;

}

textarea::placeholder{
    color:#7b8ba8;
}

button.send{

    width:54px;
    height:54px;

    border:none;

    border-radius:16px;

    background:linear-gradient(
        135deg,
        var(--primary),
        var(--primary2)
    );

    color:white;

    cursor:pointer;

    font-size:18px;

    transition:.25s;

}

button.send:hover{

    transform:scale(1.05);

    box-shadow:
        0 10px 25px rgba(37,99,235,.35);

}

.welcome{

    text-align:center;

    margin-top:80px;

}

.robot-wrap{

    position:relative;

    width:170px;
    height:170px;

    margin:0 auto 30px auto;

    display:flex;
    align-items:center;
    justify-content:center;

}

.robot{

    position:relative;

    z-index:2;

    font-size:95px;

    animation:floatRobot 3s ease-in-out infinite;

    filter:
        drop-shadow(0 0 15px rgba(37,99,235,.7))
        drop-shadow(0 0 35px rgba(37,99,235,.5));

}

.robot-glow{

    position:absolute;

    width:120px;
    height:120px;

    border-radius:50%;

    background:radial-gradient(
        circle,
        rgba(37,99,235,.45) 0%,
        rgba(37,99,235,.15) 50%,
        transparent 75%
    );

    animation:pulseGlow 2.5s infinite ease-in-out;

}

.welcome h1{

    font-size:46px;

    margin-bottom:16px;

}

.welcome p{

    color:var(--muted);

    font-size:18px;

}

@keyframes fadeIn{

    from{
        opacity:0;
        transform:translateY(10px);
    }

    to{
        opacity:1;
        transform:translateY(0);
    }

}

@keyframes floatRobot{

    0%{
        transform:translateY(0px);
    }

    50%{
        transform:translateY(-12px);
    }

    100%{
        transform:translateY(0px);
    }

}

@keyframes pulseGlow{

    0%{
        transform:scale(1);
        opacity:.7;
    }

    50%{
        transform:scale(1.15);
        opacity:1;
    }

    100%{
        transform:scale(1);
        opacity:.7;
    }

}

@media(max-width:900px){

    .sidebar{
        display:none;
    }

    .bubble{
        max-width:100%;
    }

    .chat{
        padding:20px;
    }

    .welcome h1{
        font-size:32px;
    }

}

</style>

</head>

<body>

<div class="shell">

    <div class="sidebar">

        <div class="logo">

            <div class="logo-icon">
                🤖
            </div>

            FREDÃO

        </div>

        <button class="newchat" onclick="limpar()">
            + Nova Conversa
        </button>

    </div>

    <div class="main">

        <div class="topbar">

            <div class="title">
                FREDÃO
            </div>

            <div class="status">

                <div class="status-dot"></div>

                Online

            </div>

        </div>

        <div id="chat" class="chat">

            <div class="welcome">

                <div class="robot-wrap">

                    <div class="robot-glow"></div>

                    <div class="robot">
                        🤖
                    </div>

                </div>

                <h1>Olá! Eu sou o FREDÃO</h1>

                <p>
                    Especialista em fretes LATAM e Azul Cargo
                </p>

            </div>

        </div>

        <div class="input-area">

            <div class="input-box">

                <textarea
                    id="msg"
                    placeholder="Digite sua mensagem..."
                    rows="1"
                ></textarea>

                <button class="send" onclick="enviar()">
                    ➤
                </button>

            </div>

        </div>

    </div>

</div>

<script>

const input = document.getElementById("msg")
const chat = document.getElementById("chat")

input.addEventListener("input",()=>{

    input.style.height="auto"

    input.style.height=
        Math.min(input.scrollHeight,180)+"px"

})

input.addEventListener("keydown",function(e){

    if(e.key === "Enter" && !e.shiftKey){

        e.preventDefault()

        enviar()

    }

})

function addUser(text){

    chat.innerHTML += `
    <div class="row user">
        <div class="bubble">${text}</div>
    </div>
    `

    chat.scrollTop = chat.scrollHeight

}

function addBot(text){

    chat.innerHTML += `
    <div class="row bot">
        <div class="bubble">${text}</div>
    </div>
    `

    chat.scrollTop = chat.scrollHeight

}

async function enviar(){

    const texto = input.value.trim()

    if(!texto) return

    document.querySelector('.welcome')?.remove()

    addUser(texto)

    input.value = ""

    input.style.height = "auto"

    addBot("🤖 FREDÃO está analisando sua rota logística...")

    const loadings =
        document.querySelectorAll('.bot .bubble')

    const loading =
        loadings[loadings.length-1]

    try{

        const resp = await fetch('/chat',{

            method:'POST',

            headers:{
                'Content-Type':'application/json'
            },

            body:JSON.stringify({
                message:texto
            })

        })

        const data = await resp.json()

        loading.innerText =
            data.reply || data.error

    }catch(e){

        loading.innerText =
            'Erro de comunicação com o servidor.'

    }

}

async function limpar(){

    await fetch('/clear',{
        method:'POST'
    })

    location.reload()

}

</script>

</body>
</html>
'''

# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())

    return HTML

# =========================================================
# INFO
# =========================================================

@app.route("/info")
def info():

    return jsonify({
        "model": MODEL,
        "status": "online"
    })

# =========================================================
# CLEAR
# =========================================================

@app.route("/clear", methods=["POST"])
def clear():

    sid = session.get("sid")

    historicos.pop(sid, None)
    contextos.pop(sid, None)

    return jsonify({"ok": True})

# =========================================================
# CHAT
# =========================================================

@app.route("/chat", methods=["POST"])
def chat():

    sid = session.get("sid")

    if not sid:
        sid = str(uuid.uuid4())
        session["sid"] = sid

    body = request.get_json(force=True)

    msg = (body.get("message") or "").strip()

    if not msg:
        return jsonify({"error": "mensagem vazia"}), 400

    if sid not in historicos:
        historicos[sid] = []

    if sid not in contextos:
        contextos[sid] = {
            "cep": None,
            "cidade": None,
            "uf": None,
            "tipos": None
        }

    ctx = contextos[sid]

    cep = extrair_cep(msg)

    if cep:
        ctx["cep"] = cep

    tipos = extrair_tipo_envio(msg)

    if tipos:
        ctx["tipos"] = tipos

    cidade, uf = extrair_cidade_uf(msg)

    if cidade:
        ctx["cidade"] = cidade

    if uf:
        ctx["uf"] = uf

    cep_final = ctx.get("cep")
    tipos_final = ctx.get("tipos")
    cidade_final = ctx.get("cidade")
    uf_final = ctx.get("uf")

    dados = []

    if cep_final:

        dados = consultar_por_cep(cep_final)

    elif cidade_final:

        dados = consultar_por_cidade(
            cidade_final,
            uf_final
        )

    if not cep_final and not cidade_final:

        resposta_backend = """
[SEM_DESTINO]

O colaborador ainda não informou
CEP nem cidade de destino.

Peça isso educadamente.
"""

    elif not tipos_final:

        resposta_backend = f"""
[SEM_TIPO]

O destino já foi identificado.

Pergunte qual tipo deseja:
- Kit
- Receptor
- Acessórios
- Todos
"""

    elif not dados:

        resposta_backend = f"""
[SEM_COBERTURA]

Nenhuma cobertura encontrada.
"""

    else:

        resposta_backend = formatar_resultados(
            dados,
            cep_final or cidade_final,
            tipos_final
        )

    mensagem_final = f"""
DADOS DO BACKEND:

{resposta_backend}

MENSAGEM ORIGINAL:
{msg}
"""

    try:

        historicos[sid].append(
            types.Content(
                role="user",
                parts=[types.Part(text=mensagem_final)]
            )
        )

        response = client.models.generate_content(
            model=MODEL,
            contents=historicos[sid],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
            )
        )

        reply = response.text.strip()

        historicos[sid].append(
            types.Content(
                role="model",
                parts=[types.Part(text=reply)]
            )
        )

        return jsonify({
            "reply": reply
        })

    except Exception as e:

        print("ERRO GEMINI:", e)

        return jsonify({
            "error": str(e)
        }), 500

# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    print("\n========================================")
    print("FREDÃO ULTRA ONLINE 🚚")
    print("Modelo:", MODEL)
    print("Origem:", CEP_ORIGEM_FMT)
    print("========================================\n")

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=True
    )