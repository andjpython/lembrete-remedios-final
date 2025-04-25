import os
import time
import json
import datetime
import re
import difflib
import pytz
import random
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

# ========== TIMEZONE ==========
os.environ["TZ"] = "America/Sao_Paulo"
time.tzset()

# ========== FLASK APP ==========
app = Flask(__name__)

# ========== ARQUIVOS ==========
HISTORICO_ARQUIVO = "historico.json"
REMEDIOS_ARQUIVO = "remedios.json"
CONTEXTO_ARQUIVO = "contexto.json"

# ========== FUNÇÕES UTILITÁRIAS ==========
def agora_br():
    return datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))

def normalizar(texto):
    return texto.strip().lower()

def carregar_json(caminho):
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_json(caminho, conteudo):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, indent=2, ensure_ascii=False)

def atualizar_contexto(numero, comando, remedio=None, hora=None):
    contexto = carregar_json(CONTEXTO_ARQUIVO)
    if numero not in contexto:
        contexto[numero] = {}
    contexto[numero]["ultimo_comando"] = comando
    if remedio:
        contexto[numero]["remedio"] = remedio
    if hora:
        contexto[numero]["hora"] = hora
    salvar_json(CONTEXTO_ARQUIVO, contexto)

def gerar_saudacao_com_hora():
    hora = agora_br().hour
    horario = agora_br().strftime("%H:%M")
    if hora < 12:
        return f"☀️ Bom dia! Agora são {horario}."
    elif hora < 18:
        return f"🌤️ Boa tarde! Agora são {horario}."
    return f"🌙 Boa noite! Agora são {horario}."

def erro_engracado():
    return random.choice([
        "🥶 Ih rapaz, essa eu não entendi!",
        "🤖 Ainda não aprendi isso... mas tô tentando!",
        "😅 Tenta de novo aí com outras palavras!",
        "🧠 Buguei com esse comando. Refaz aí rapidinho?",
        "👀 Hein? Repete aí mais devagar que eu não peguei..."
    ])

def listar_remedios_do_dia(remedios):
    hoje = agora_br().date()
    lista = []
    for r in remedios:
        inicio = datetime.datetime.strptime(r["data_inicio"], "%Y-%m-%d").date()
        dias = (hoje - inicio).days
        if not (inicio <= hoje):
            continue
        if r["frequencia"] == "diario" or (r["frequencia"] == "semanal" and dias % 7 == 0):
            for h in r["horarios"]:
                periodo = f" ({h.get('periodo')})" if h.get("periodo") else ""
                lista.append(f"🔔 {r['nome']}{periodo} às {h['hora']}")
    return "\n".join(sorted(lista)) or "Nenhum remédio hoje! 😊"

# ========== ROTA DE MONITORAMENTO ==========
@app.route("/ping", methods=["GET", "HEAD"])
def ping():
    return "pong", 200

# ========== WEBHOOK ==========
@app.route("/webhook", methods=["POST", "HEAD"])
def responder():
    if request.method == "HEAD":
        return "", 200

    mensagem = request.values.get("Body", "").strip()
    numero = request.values.get("From", "desconhecido")
    resposta = MessagingResponse()
    texto = normalizar(mensagem)

    remedios = carregar_json(REMEDIOS_ARQUIVO)
    historico = carregar_json(HISTORICO_ARQUIVO)
    hoje = agora_br().strftime("%Y-%m-%d")
    hora_atual = agora_br().strftime("%H:%M")

    nomes_validos = [r["nome"].lower() for r in remedios]
    def corrigir_nome(nome_digitado):
        match = difflib.get_close_matches(nome_digitado.lower(), nomes_validos, n=1, cutoff=0.6)
        return match[0].title() if match else nome_digitado.title()

    # === LISTAR REMÉDIOS ===
    if any(c in texto for c in [
        "remédio tenho que tomar", "quais remedios", "remédios de hoje",
        "quais faltam", "falta algum", "o que falta", "qual não tomei"]):
        resposta.message(f"📋 Hoje você ainda precisa tomar:\n{listar_remedios_do_dia(remedios)}")
        return str(resposta)

    # === CONFIRMADOS ===
    if "o que já tomei" in texto or "já tomei" in texto:
        confirmados = [c for c in historico.get("confirmacoes", []) if c["data"] == hoje and c.get("confirmado")]
        if confirmados:
            lista = "\n".join(f"- {c['remedio']} às {c['hora']}" for c in confirmados)
            resposta.message(f"✅ Hoje você já tomou:\n{lista}")
        else:
            resposta.message("📭 Nenhum remédio confirmado hoje ainda.")
        return str(resposta)

    # === TOMOU ===
    match = re.search(r"tomei o ([\w\s\-]+)", texto)
    if match:
        nome = corrigir_nome(match.group(1).strip())
        historico.setdefault("confirmacoes", []).append({
            "data": hoje, "hora": hora_atual, "remedio": nome, "confirmado": True
        })
        salvar_json(HISTORICO_ARQUIVO, historico)
        atualizar_contexto(numero, "tomei", remedio=nome, hora=hora_atual)
        resposta.message(f"💊 Marquei que você tomou *{nome}* às {hora_atual}.")
        return str(resposta)

    # === NÃO TOMOU ===
    match = re.search(r"não tomei o ([\w\s\-]+)", texto)
    if match:
        nome = corrigir_nome(match.group(1).strip())
        historico.setdefault("pendencias", []).append({
            "data": hoje, "horario": hora_atual, "remedio": nome,
            "status": "pendente", "tentativas": 0
        })
        salvar_json(HISTORICO_ARQUIVO, historico)
        atualizar_contexto(numero, "nao_tomei", remedio=nome)
        resposta.message(f"🕐 Marquei que *{nome}* ainda está pendente.")
        return str(resposta)

    # === CORRIGIR HORÁRIO ===
    match = re.search(r"corrige.*tomei o ([\w\s\-]+) (?:às|as) (\d{2}:\d{2})", texto)
    if match:
        nome = corrigir_nome(match.group(1).strip())
        hora_corrigida = match.group(2)
        historico.setdefault("confirmacoes", []).append({
            "data": hoje, "hora": hora_corrigida, "remedio": nome, "confirmado": True
        })
        salvar_json(HISTORICO_ARQUIVO, historico)
        atualizar_contexto(numero, "corrige", remedio=nome, hora=hora_corrigida)
        resposta.message(f"🔁 Corrigido! Você tomou *{nome}* às {hora_corrigida}.")
        return str(resposta)

    # === ERROU ===
    match = re.search(r"errei.*não tomei o ([\w\s\-]+)", texto)
    if match:
        nome = corrigir_nome(match.group(1).strip())
        historico["confirmacoes"] = [
            c for c in historico.get("confirmacoes", [])
            if not (c["data"] == hoje and c["remedio"].lower() == nome.lower())
        ]
        salvar_json(HISTORICO_ARQUIVO, historico)
        atualizar_contexto(numero, "errei", remedio=nome)
        resposta.message(f"⚠️ Ok! Apaguei a confirmação do *{nome}*.")
        return str(resposta)

    # === COMANDO DESCONHECIDO ===
    comandos = (
        "🔍 Exemplos de comandos:\n"
        "• tomei o Lipidil\n"
        "• não tomei o Zyloric\n"
        "• o que já tomei?\n"
        "• quais faltam?\n"
        "• errei, não tomei o Lipidil\n"
        "• corrige, tomei o OHDE às 12:00"
    )
    resposta.message(f"{gerar_saudacao_com_hora()}\n\n{erro_engracado()}\n\n{comandos}")
    return str(resposta)

# ========== EXECUÇÃO ==========
if __name__ == "__main__":
    print("🟢 Webhook do WhatsApp iniciado e ouvindo na porta padrão do Render...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
