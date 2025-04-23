import json
import datetime
import time
import os
from twilio.rest import Client
from dotenv import load_dotenv
from pathlib import Path

# ========== CARREGAR VARIÁVEIS DO AMBIENTE ==========
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMERO = os.getenv("TWILIO_NUMBER")
SEU_NUMERO = os.getenv("DESTINO")

# ========== DEBUG ==========
print("🔍 TWILIO_SID:", TWILIO_SID)
print("🔍 TWILIO_TOKEN:", TWILIO_TOKEN)
print("🔍 TWILIO_NUMERO:", TWILIO_NUMERO)
print("🔍 SEU_NUMERO:", SEU_NUMERO)

if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_NUMERO, SEU_NUMERO]):
    raise EnvironmentError("⚠️ Variáveis do Twilio não estão configuradas corretamente no .env")

client = Client(TWILIO_SID, TWILIO_TOKEN)

# ========== CONSTANTES ==========
HISTORICO_ARQUIVO = "historico.json"
LIMITE_TENTATIVAS = 3
INTERVALO_REENVIO = 600  # 10 minutos

# ========== FUNÇÕES ==========
def log(msg):
    agora = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{agora} {msg}")

def carregar_historico():
    if not os.path.exists(HISTORICO_ARQUIVO):
        return {"confirmacoes": [], "pendencias": []}
    try:
        with open(HISTORICO_ARQUIVO, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "confirmacoes": data.get("confirmacoes", []),
                "pendencias": data.get("pendencias", [])
            }
    except Exception as e:
        log(f"[❌ ERRO] Falha ao carregar histórico: {e}")
        return {"confirmacoes": [], "pendencias": []}

def salvar_historico(historico):
    try:
        with open(HISTORICO_ARQUIVO, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"[❌ ERRO] Falha ao salvar histórico: {e}")

def enviar_mensagem(texto):
    try:
        client.messages.create(from_=TWILIO_NUMERO, to=SEU_NUMERO, body=texto)
        log(f"[📤 REENVIO] {texto}")
    except Exception as e:
        log(f"[❌ ERRO WHATSAPP] {e}")

def verificar_pendencias():
    historico = carregar_historico()
    hoje = datetime.datetime.now().strftime("%Y-%m-%d")
    agora = datetime.datetime.now()
    novas_pendencias = []

    pendencias_ativas = [
        p for p in historico.get("pendencias", [])
        if p.get("data") == hoje
    ]

    log(f"[🔎] Total de pendências para hoje: {len(pendencias_ativas)}")

    for pendencia in pendencias_ativas:
        nome = pendencia.get("remedio")
        horario = pendencia.get("horario")
        tentativas = pendencia.get("tentativas", 0)

        hora_completa = datetime.datetime.strptime(f"{hoje} {horario}", "%Y-%m-%d %H:%M")
        if hora_completa > agora:
            log(f"[⏳ AGUARDANDO] {nome} às {horario}")
            novas_pendencias.append(pendencia)
            continue

        confirmado = any(
            c.get("remedio") == nome and c.get("data") == hoje and c.get("hora") == horario
            for c in historico.get("confirmacoes", [])
        )
        if confirmado:
            log(f"[✅ CONFIRMADO] {nome} às {horario}")
            continue

        if tentativas < LIMITE_TENTATIVAS:
            pendencia["tentativas"] = tentativas + 1
            mensagem = (
                f"🔔 Lembrete #{pendencia['tentativas']}: você tomou o remédio {nome} às {horario}?\n"
                "Responda SIM ou NÃO."
            )
            enviar_mensagem(mensagem)
            novas_pendencias.append(pendencia)
            log(f"[🔁 NOVA TENTATIVA {pendencia['tentativas']}/{LIMITE_TENTATIVAS}] {nome} às {horario}")
        else:
            log(f"[⚠️ LIMITE ATINGIDO] {nome} às {horario} ({tentativas} tentativas)")

    historico["pendencias"] = novas_pendencias
    salvar_historico(historico)

# ========== EXECUÇÃO ==========
if __name__ == "__main__":
    log("🔁 Monitor de reenvios iniciado.")
    while True:
        verificar_pendencias()
        time.sleep(INTERVALO_REENVIO)
