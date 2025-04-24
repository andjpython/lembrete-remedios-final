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
        return f"\u2600\ufe0f Bom dia! Agora s\u00e3o {horario}. Vamos iniciar o dia!"
    elif hora < 18:
        return f"\ud83c\udf24\ufe0f Boa tarde! Agora s\u00e3o {horario}. Vamos seguir firmes!"
    return f"\ud83c\udf19 Boa noite! Agora s\u00e3o {horario}. Vamos encerrar bem o dia!"

def erro_engracado():
    frases = [
        "\ud83e\udd75 Ih rapaz, essa eu n\u00e3o entendi!",
        "\ud83e\udd16 Ainda n\u00e3o aprendi isso... mas t\u00f4 tentando!",
        "\ud83d\ude05 Tenta de novo a\u00ed com outras palavras!",
        "\ud83e\udde0 Buguei com esse comando. Refaz a\u00ed rapidinho?",
        "\ud83d\udc40 Hein? Repete a\u00ed mais devagar que eu n\u00e3o peguei...",
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
    semana = agora_br().isoweekday()
    lista = []
    for r in remedios:
        if r["frequencia"] == "diario" or (r["frequencia"] == "semanal" and datetime.datetime.strptime(r["data_inicio"], "%Y-%m-%d").isoweekday() == semana):
            for h in r["horarios"]:
                periodo = f" ({h.get('periodo')})" if h.get("periodo") else ""
                lista.append(f"\ud83d\udd14 {r['nome']}{periodo} \u00e0s {h['hora']}")
    return "\n".join(sorted(lista)) or "Nenhum rem\u00e9dio hoje! \ud83d\ude0a"

# ========== ROTAS ==========
@app.route("/ping", methods=["GET", "HEAD"])
def ping():
    with open(PING_LOG, "w") as f:
        f.write(agora_br().isoformat())
    return "\u2705 Bot ativo!", 200

@app.route("/webhook", methods=["POST", "HEAD"])
def responder():
    if request.method == "HEAD":
        return "", 200

    mensagem = request.values.get("Body", "").strip()
    numero = request.values.get("From", "desconhecido")
    resposta = MessagingResponse()

    texto = normalizar(mensagem)
    remedios = carregar_json(REMEDIOS_ARQUIVO)

    if any(comando in texto for comando in ["rem\u00e9dio tenho que tomar", "quais remedios", "rem\u00e9dios de hoje"]):
        resposta.message(f"\ud83d\udcc3 Hoje voc\u00ea ainda precisa tomar:\n{listar_remedios_do_dia(remedios)}")
    else:
        comandos = (
            "\ud83d\udd0d Exemplos de comandos:\n"
            "- *tomei o Lipidil*\n"
            "- *quais faltam?*\n"
            "- *o que j\u00e1 tomei?*\n"
            "- *errei, n\u00e3o tomei o [rem\u00e9dio]*\n"
            "- *corrige, tomei o [rem\u00e9dio] \u00e0s [hora]*"
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
                        body="\ud83d\udea8 Aten\u00e7\u00e3o! O Render n\u00e3o est\u00e1 pingando o webhook h\u00e1 mais de 15 minutos!"
                    )
            else:
                print("\u26a0\ufe0f Arquivo de ping n\u00e3o encontrado.")
        except Exception as e:
            print(f"Erro no monitoramento de pings: {e}")
        time.sleep(60)

# ========== EXECU\u00c7\u00c3O ==========
if __name__ == "__main__":
    threading.Thread(target=monitorar_pings, daemon=True).start()
    print("\ud83d\udfe2 Webhook do WhatsApp iniciado.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
