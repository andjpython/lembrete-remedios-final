import json
import os
import time
from datetime import datetime, timedelta
from twilio.rest import Client
from dotenv import load_dotenv
from pathlib import Path
from pytz import timezone

# ========== INÍCIO ==========
print("🟢 app.py rodando...")

def agora_br():
    return datetime.now(timezone("America/Sao_Paulo"))

def log(msg):
    print(f"[{agora_br().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

log("🚀 app.py está rodando normalmente no Render!")

# ========== AMBIENTE ==========
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
DESTINO = os.getenv("DESTINO")

print("🔍 TWILIO_ACCOUNT_SID:", TWILIO_SID)
print("🔍 TWILIO_AUTH_TOKEN:", TWILIO_TOKEN)
print("🔍 TWILIO_NUMBER:", TWILIO_NUMBER)
print("🔍 DESTINO:", DESTINO)

if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_NUMBER, DESTINO]):
    raise EnvironmentError("⚠️ Variáveis de ambiente do Twilio não configuradas corretamente.")

client = Client(TWILIO_SID, TWILIO_TOKEN)

# ========== FUNÇÕES UTILITÁRIAS ==========
def enviar_mensagem(mensagem):
    try:
        client.messages.create(from_=TWILIO_NUMBER, to=DESTINO, body=mensagem)
        log(f"[✅ ENVIADO] {mensagem}")
    except Exception as e:
        log(f"[❌ ERRO AO ENVIAR WHATSAPP] {e}")

def carregar_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"[❌ ERRO AO LER {caminho}] {e}")
    return [] if "remedios" in caminho else {"confirmacoes": [], "pendencias": []}

def salvar_json(caminho, conteudo):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, indent=2, ensure_ascii=False)

def saudacao_horario():
    hora = agora_br().hour
    if hora < 12:
        return "☀️ Bom dia"
    elif hora < 18:
        return "🌤️ Boa tarde"
    return "🌙 Boa noite"

def esta_no_periodo_tratamento(remedio):
    inicio = datetime.strptime(remedio["data_inicio"], "%Y-%m-%d").date()
    dias = int(float(remedio["duracao_meses"]) * 30)
    fim = inicio + timedelta(days=dias)
    hoje = agora_br().date()
    return inicio <= hoje <= fim

def e_dia_certo(remedio):
    if remedio["frequencia"] == "diario":
        return True
    if remedio["frequencia"] == "semanal":
        inicio = datetime.strptime(remedio["data_inicio"], "%Y-%m-%d").date()
        hoje = agora_br().date()
        return (hoje - inicio).days % 7 == 0
    return False

def registrar_pendencia(remedio, hora):
    historico = carregar_json("historico.json")
    pendencias = historico.get("pendencias", [])
    data_hoje = agora_br().strftime("%Y-%m-%d")

    for p in pendencias:
        if p["remedio"] == remedio["nome"] and p["data"] == data_hoje and p["horario"] == hora:
            p["tentativas"] += 1
            salvar_json("historico.json", historico)
            log(f"[🔁 PENDÊNCIA ATUALIZADA] {p}")
            return

    nova = {
        "remedio": remedio["nome"],
        "horario": hora,
        "data": data_hoje,
        "status": "pendente",
        "tentativas": 1
    }
    pendencias.append(nova)
    historico["pendencias"] = pendencias
    salvar_json("historico.json", historico)
    log(f"[📝 PENDÊNCIA REGISTRADA] {nova}")

def notificar_remedio(remedio, hora, tipo_aviso):
    periodo = next((f" ({h['periodo']})" for h in remedio.get("horarios", []) if h["hora"] == hora and "periodo" in h), "")
    msg_tipo = {
        "15min": f"⏳ Em 15 minutos, tome {remedio['nome']}{periodo} - {remedio['dosagem']} ({hora}).",
        "5min": f"⚠️ Faltam 5 minutos para tomar {remedio['nome']}{periodo} - {remedio['dosagem']} ({hora}).",
        "agora": f"🚨 Hora de tomar {remedio['nome']}{periodo} - {remedio['dosagem']}! Tome com água. ({hora})"
    }
    enviar_mensagem(msg_tipo[tipo_aviso])
    registrar_pendencia(remedio, hora)

def verificar_horarios(remedios):
    agora = agora_br()
    hora_atual = agora.strftime("%H:%M")
    notificou = False

    for remedio in remedios:
        if not esta_no_periodo_tratamento(remedio) or not e_dia_certo(remedio):
            continue
        for h in remedio.get("horarios", []):
            hora_remedio = datetime.strptime(h["hora"], "%H:%M").time()
            hora_base = datetime.combine(agora.date(), hora_remedio)
            for tipo, minutos in [("15min", 15), ("5min", 5), ("agora", 0)]:
                if hora_atual == (hora_base - timedelta(minutes=minutos)).strftime("%H:%M"):
                    notificar_remedio(remedio, h["hora"], tipo)
                    notificou = True

    if not notificou:
        log("🔍 Nenhum remédio agendado neste minuto.")

def verificar_pendentes_do_dia(remedios, historico, data):
    pendentes = []
    for r in remedios:
        if not esta_no_periodo_tratamento(r) or not e_dia_certo(r):
            continue
        for h in r.get("horarios", []):
            confirmado = any(
                c["remedio"] == r["nome"] and c["data"] == data and c["hora"] == h["hora"]
                for c in historico.get("confirmacoes", [])
            )
            if not confirmado:
                periodo = f" ({h['periodo']})" if "periodo" in h else ""
                pendentes.append(f"{r['nome']}{periodo} às {h['hora']}")
    return pendentes

# ========== EXECUÇÃO ==========
def iniciar():
    log("🚀 app.py iniciou normalmente!")
    agora = agora_br()
    enviar_mensagem(f"{saudacao_horario()}! Agora são {agora.strftime('%H:%M')}. Vamos iniciar o dia!")

    remedios = carregar_json("remedios.json")
    historico = carregar_json("historico.json")
    hoje = agora.strftime("%Y-%m-%d")

    pendentes = verificar_pendentes_do_dia(remedios, historico, hoje)

    if pendentes:
        lista = "\n".join(f"🔔 {item}" for item in pendentes)
        enviar_mensagem(f"📋 Hoje você ainda precisa tomar:\n{lista}")
    else:
        enviar_mensagem("🎉 Parabéns! Você já tomou todos os remédios do dia.")

if __name__ == "__main__":
    iniciar()
