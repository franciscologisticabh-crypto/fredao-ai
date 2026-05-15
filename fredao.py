# =========================================================
# FREDÃO ULTRA — Cotador Inteligente de Fretes
# Flask + Gemini + Supabase
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
contextos  = {}

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

    # =====================================================
    # EXTRAÇÃO
    # =====================================================

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

    # =====================================================
    # RECUPERA CONTEXTO
    # =====================================================

    cep_final     = ctx.get("cep")
    tipos_final   = ctx.get("tipos")
    cidade_final  = ctx.get("cidade")
    uf_final      = ctx.get("uf")

    dados = []

    # =====================================================
    # CONSULTA AUTOMÁTICA
    # =====================================================

    if cep_final:

        dados = consultar_por_cep(cep_final)

    elif cidade_final:

        dados = consultar_por_cidade(
            cidade_final,
            uf_final
        )

    # =====================================================
    # REGRAS INTELIGENTES
    # =====================================================

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
# CLEAR
# =========================================================

@app.route("/clear", methods=["POST"])
def clear():

    sid = session.get("sid")

    historicos.pop(sid, None)
    contextos.pop(sid, None)

    return jsonify({"ok": True})


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
# HOME
# =========================================================

@app.route("/")
def home():

    return """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>FREDÃO ULTRA</title>

<style>

body{
    margin:0;
    background:#0f172a;
    color:white;
    font-family:Arial;
}

.topo{
    background:#111827;
    padding:20px;
    font-size:32px;
    font-weight:bold;
    border-bottom:1px solid #334155;
}

.chat{
    height:75vh;
    overflow-y:auto;
    padding:20px;
}

.msg-user{
    background:#2563eb;
    padding:12px;
    border-radius:10px;
    margin:10px 0;
    max-width:80%;
    margin-left:auto;
}

.msg-bot{
    background:#1e293b;
    padding:12px;
    border-radius:10px;
    margin:10px 0;
    max-width:80%;
}

.barra{
    position:fixed;
    bottom:0;
    width:100%;
    display:flex;
    background:#111827;
    padding:15px;
    gap:10px;
}

input{
    flex:1;
    padding:15px;
    border:none;
    border-radius:10px;
    font-size:16px;
}

button{
    background:#2563eb;
    color:white;
    border:none;
    padding:15px 25px;
    border-radius:10px;
    cursor:pointer;
    font-weight:bold;
}

button:hover{
    background:#1d4ed8;
}

pre{
    white-space:pre-wrap;
}

</style>
</head>

<body>

<div class="topo">
    FREDÃO ULTRA 🚚
</div>

<div id="chat" class="chat">
    <div class="msg-bot">
        Olá. Sou o Fredão Ultra.<br><br>
        Informe:
        <br>• CEP
        <br>• cidade
        <br>• kit / receptor / acessórios
    </div>
</div>

<div class="barra">
    <input id="msg" placeholder="Digite sua mensagem...">
    <button onclick="enviar()">Enviar</button>
</div>

<script>

async function enviar(){

    const input = document.getElementById("msg")
    const chat = document.getElementById("chat")

    const texto = input.value.trim()

    if(!texto) return

    chat.innerHTML += `
        <div class="msg-user">
            ${texto}
        </div>
    `

    input.value = ""

    chat.innerHTML += `
        <div class="msg-bot" id="loading">
            Fredão está pensando...
        </div>
    `

    chat.scrollTop = chat.scrollHeight

    try{

        const resp = await fetch("/chat",{
            method:"POST",
            headers:{
                "Content-Type":"application/json"
            },
            body:JSON.stringify({
                message:texto
            })
        })

        const data = await resp.json()

        document.getElementById("loading").remove()

        chat.innerHTML += `
            <div class="msg-bot">
                <pre>${data.reply || data.error}</pre>
            </div>
        `

        chat.scrollTop = chat.scrollHeight

    }catch(e){

        document.getElementById("loading").remove()

        chat.innerHTML += `
            <div class="msg-bot">
                Erro de comunicação.
            </div>
        `
    }
}

</script>

</body>
</html>
"""


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