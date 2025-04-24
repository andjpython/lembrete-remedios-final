from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import json
import datetime
import os
import re
import difflib
from dotenv import load_dotenv
from pathlib import Path
import random
import threading
import time
import pytz

app = Flask(__name__)

# ========== ENV ==========
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
DESTINO = os.getenv("DESTINO")
client = Client(TWILIO_SID, TWILIO_TOKEN)

# ========== ARQUIVOS ==========
HISTORICO_ARQUIVO = "historico.json"
REMEDIOS_ARQUIVO = "remedios.json"
CONTEXTO_ARQUIVO = "contexto.json"
PING_LOG = "ping_log.txt"

# ========== UTILS ==========
def agora_br():
    return datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))

def carregar_json(caminho):
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_json(caminho, conteudo):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, indent=2, ensure_ascii=False)

def normalizar(texto):
    return texto.strip().lower()

def gerar_saudacao_com_hora():
    agora = agora_br()
    hora = agora.hour
    horario = agora.strftime("%H:%M")
    if hora < 12:
        return f"☀️ Bom dia! Agora são {horario}. Vamos iniciar o dia!"
    elif hora < 18:
        return f"🌤️ Boa tarde! Agora são {horario}. Vamos seguir firmes!"
    return f"🌙 Boa noite! Agora são {horario}. Vamos encerrar bem o dia!"

def erro_engracado():
    frases = [
        "🥵 Ih rapaz, essa eu não entendi!",
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

def listar_remedios_do_dia(remedios):
    hoje = agora_br().strftime("%Y-%m-%d")
    semana = agora_br().isoweekday()
    lista = []
    for r in remedios:
        if r["frequencia"] == "diario" or (r["frequencia"] == "semanal" and datetime.datetime.strptime(r["data_inicio"], "%Y-%m-%d").isoweekday() == semana):
            for h in r["horarios"]:
                periodo = f" ({h.get('periodo')})" if h.get("periodo") else ""
                lista.append(f"🔔 {r['nome']}{periodo} às {h['hora']}")
    return "\n".join(sorted(lista)) or "Nenhum remédio hoje! 😊"

# ========== ROTAS ==========
@app.route("/ping", methods=["GET", "HEAD"])
def ping():
    with open(PING_LOG, "w") as f:
        f.write(agora_br().isoformat())
    return "✅ Bot ativo!", 200

@app.route("/webhook", methods=["POST", "HEAD"])
def responder():
    if request.method == "HEAD":
        return "", 200

    mensagem = request.values.get("Body", "").strip()
    numero = request.values.get("From", "desconhecido")
    resposta = MessagingResponse()

    texto = normalizar(mensagem)
    remedios = carregar_json(REMEDIOS_ARQUIVO)

    if "remédio tenho que tomar" in texto or "quais remedios" in texto or "remédios de hoje" in texto:
        resposta.message(f"📃 Hoje você ainda precisa tomar:\n{listar_remedios_do_dia(remedios)}")
    else:
        comandos = (
            "🔍 Exemplos de comandos:\n"
            "- *tomei o Lipidil*\n"
            "- *quais faltam?*\n"
            "- *o que já tomei?*\n"
            "- *errei, não tomei o [remédio]*\n"
            "- *corrige, tomei o [remédio] às [hora]*"
        )
        resposta.message(f"{gerar_saudacao_com_hora()}\n\n{erro_engracado()}\n\n{comandos}")
    return str(resposta)

# ========== MONITORAMENTO ==========
def monitorar_pings():
    while True:
        try:
            if os.path.exists(PING_LOG):
                with open(PING_LOG, "r") as f:
                    ultima = datetime.datetime.fromisoformat(f.read().strip())
                agora = agora_br()
                delta = (agora - ultima).total_seconds()
                if delta > 900:
                    client.messages.create(
                        from_=TWILIO_NUMBER,
                        to=DESTINO,
                        body="🚨 Atenção! O Render não está pingando o webhook há mais de 15 minutos!"
                    )
            else:
                print("⚠️ Arquivo de ping não encontrado.")
        except Exception as e:
            print(f"Erro no monitoramento de pings: {e}")
        time.sleep(60)

# ========== EXECUÇÃO ==========
if __name__ == "__main__":
    threading.Thread(target=monitorar_pings, daemon=True).start()
    print("🟢 Webhook do WhatsApp iniciado.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
