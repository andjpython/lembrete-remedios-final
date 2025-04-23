# webhook.py

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import json
import datetime
import os
import re
import difflib
from dotenv import load_dotenv
from pathlib import Path
import random

app = Flask(__name__)

# ========== ENV ==========
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# ========== LOG INICIAL ==========
print("🚀 webhook.py está rodando normalmente no Render!")

# ========== ARQUIVOS ==========
HISTORICO_ARQUIVO = "historico.json"
REMEDIOS_ARQUIVO = "remedios.json"
CONTEXTO_ARQUIVO = "contexto.json"

# ========== JSON ==========
def carregar_json(caminho):
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_json(caminho, conteudo):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, indent=2, ensure_ascii=False)

# ========== UTILS ==========
def normalizar(texto):
    return texto.strip().lower()

def encontrar_nome_proximo(nome_digitado, nomes_validos):
    nome_digitado = nome_digitado.strip().lower()
    correspondencias = difflib.get_close_matches(
        nome_digitado, [n.lower() for n in nomes_validos], n=1, cutoff=0.6
    )
    if correspondencias:
        for n in nomes_validos:
            if n.lower() == correspondencias[0]:
                return n
    return None

def gerar_saudacao():
    hora = datetime.datetime.now().hour
    if hora < 12:
        return "☀️ Bom dia!"
    elif hora < 18:
        return "🌤️ Boa tarde!"
    return "🌙 Boa noite!"

def mensagem_confirmacao(remedio, hora):
    opcoes = [
        f"✅ Show! Marquei que você tomou *{remedio}* às *{hora}*. 👌",
        f"📝 Anotado! *{remedio}* às *{hora}* registrado com sucesso!",
        f"💊 Beleza! Já deixei aqui: *{remedio}* às *{hora}*!",
        f"📌 Confirmação feita! *{remedio}*, horário *{hora}*. Tá na mão.",
        f"🎯 Pronto! *{remedio}* das *{hora}* já tá confirmado.",
    ]
    return random.choice(opcoes)

def erro_engracado():
    frases = [
        "😵‍💫 Ih rapaz, essa eu não entendi!",
        "🤖 Ainda não aprendi isso... mas tô tentando!",
        "😅 Tenta de novo aí com outras palavras!",
        "🧠 Buguei com esse comando. Refaz aí rapidinho?",
        "👀 Hein? Repete aí mais devagar que eu não peguei...",
    ]
    return random.choice(frases)

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

# ========== ROTA DE MONITORAMENTO ==========
@app.route("/ping", methods=["GET"])
def ping():
    return "✅ Bot ativo!", 200

# ========== ROTA ==========
@app.route("/webhook", methods=["POST"])
def responder():
    mensagem = request.values.get("Body", "").strip()
    numero = request.values.get("From", "desconhecido")
    resposta = MessagingResponse()

    texto = normalizar(mensagem)
    historico = carregar_json(HISTORICO_ARQUIVO)
    remedios = carregar_json(REMEDIOS_ARQUIVO)
    contexto = carregar_json(CONTEXTO_ARQUIVO)
    hoje = datetime.datetime.now().strftime("%Y-%m-%d")
    nomes_remedios = [r["nome"] for r in remedios]

    # Aqui vem toda a lógica de comandos já existente...
    # (sua parte do código original continua a partir daqui sem alterações)
    # ...

    # ========== DEFAULT ==========
    comandos = (
        "💬 Exemplos de comandos:\n"
        "- *tomei o Lipidil*\n"
        "- *quais faltam?*\n"
        "- *o que já tomei?*\n"
        "- *errei, não tomei o [remédio]*\n"
        "- *corrige, tomei o [remédio] às [hora]*"
    )
    resposta.message(f"{gerar_saudacao()}\n{erro_engracado()}\n{comandos}")
    return str(resposta)

# ========== EXECUÇÃO ==========
if __name__ == "__main__":
    print("🟢 Webhook do WhatsApp iniciado.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
