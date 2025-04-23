# main.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import json
import os
import time
from twilio.rest import Client
from dotenv import load_dotenv
from pathlib import Path
import sys

# ========== CONFIGURAÇÃO ==========
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
DESTINO = os.getenv("DESTINO")

client = Client(TWILIO_SID, TWILIO_TOKEN)

REMEDIOS_ARQUIVO = "remedios.json"
HISTORICO_ARQUIVO = "historico.json"
PACIENTE_ARQUIVO = "paciente.json"
COMANDOS_ARQUIVO = "ultimos_comandos.json"
scheduler = BackgroundScheduler()

# ========== UTILITÁRIOS ==========
def carregar_json(caminho, tipo_lista=False):
    if not os.path.exists(caminho):
        return [] if tipo_lista else {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return [] if tipo_lista else {}

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_nome_paciente():
    dados = carregar_json(PACIENTE_ARQUIVO)
    return dados.get("nome", "Paciente")

def emoji_por_horario():
    hora = datetime.now().hour
    if hora < 12:
        return "☀️"
    elif hora < 18:
        return "🌤️"
    return "🌙"

def registrar_ultimo_comando(remedio, hora):
    comandos = carregar_json(COMANDOS_ARQUIVO)
    comandos[DESTINO] = {"remedio": remedio, "hora": hora}
    salvar_json(COMANDOS_ARQUIVO, comandos)

# ========== MENSAGENS ==========
def enviar_mensagem(mensagem):
    try:
        client.messages.create(body=mensagem, from_=TWILIO_NUMBER, to=DESTINO)
        print(f"[📤] Mensagem enviada: {mensagem}")
    except Exception as e:
        print(f"[❌] Erro ao enviar mensagem: {e}")

# ========== AGENDA ==========
def agendar_alertas():
    remedios = carregar_json(REMEDIOS_ARQUIVO, tipo_lista=True)
    agora = datetime.now()
    hoje = agora.date()

    for r in remedios:
        inicio = datetime.strptime(r["data_inicio"], "%Y-%m-%d").date()
        fim = inicio + timedelta(days=r["duracao_meses"] * 30)

        if not (inicio <= hoje <= fim):
            continue

        if r["frequencia"] == "semanal" and (hoje - inicio).days % 7 != 0:
            continue

        for h in r.get("horarios", []):
            hora_str = h["hora"]
            hora_base = datetime.combine(hoje, datetime.strptime(hora_str, "%H:%M").time())
            periodo = h.get("periodo", "")
            nome_formatado = f"{r['nome']} ({periodo})" if periodo else r["nome"]
            obs = f"\n📌 Obs: {r['obs']}" if r.get("obs") else ""

            for minutos in [15, 5]:
                agendamento = hora_base - timedelta(minutes=minutos)
                if agendamento > agora:
                    scheduler.add_job(
                        func=enviar_mensagem,
                        trigger=CronTrigger(
                            year=agendamento.year, month=agendamento.month, day=agendamento.day,
                            hour=agendamento.hour, minute=agendamento.minute
                        ),
                        args=[f"{emoji_por_horario()} Em {minutos} minutos: tome *{nome_formatado}* - {r['dosagem']} às {hora_str}.{obs}"],
                        name=f"{r['nome']}_{hora_str}_{minutos}",
                        replace_existing=True,
                    )

def agendar_relatorio_diario():
    def gerar_relatorio():
        historico = carregar_json(HISTORICO_ARQUIVO)
        hoje = datetime.now().strftime("%Y-%m-%d")
        nome = carregar_nome_paciente()

        confirmados = [c for c in historico.get("confirmacoes", []) if c["data"] == hoje]
        if confirmados:
            linhas = "\n".join(f"- {c['remedio']} às {c['hora']}" for c in confirmados)
            mensagem = f"📊 Relatório (22:05) - {nome}:\nVocê tomou:\n{linhas}"
        else:
            mensagem = f"📊 Relatório (22:05) - {nome}:\n😅 Nenhum remédio confirmado hoje."

        enviar_mensagem(mensagem)

    scheduler.add_job(gerar_relatorio, CronTrigger(hour=22, minute=5), name="relatorio_diario", replace_existing=True)

def agendar_resumo_semanal():
    def gerar_resumo():
        historico = carregar_json(HISTORICO_ARQUIVO)
        hoje = datetime.now().date()
        inicio = hoje - timedelta(days=7)
        nome = carregar_nome_paciente()

        confirmados = [
            c for c in historico.get("confirmacoes", [])
            if c["confirmado"] and inicio.strftime("%Y-%m-%d") <= c["data"] <= hoje.strftime("%Y-%m-%d")
        ]
        if confirmados:
            dias = {}
            for c in confirmados:
                dias.setdefault(c["data"], []).append(f"- {c['remedio']} às {c['hora']}")
            mensagem = f"📅 Resumo semanal - {nome}:\n"
            for dia, itens in sorted(dias.items()):
                mensagem += f"\n🗓️ {dia}:\n" + "\n".join(itens)
        else:
            mensagem = f"📅 Resumo semanal - {nome}:\n😴 Nenhum remédio confirmado nos últimos 7 dias."

        enviar_mensagem(mensagem)

    scheduler.add_job(gerar_resumo, CronTrigger(day_of_week="sun", hour=22, minute=10), name="resumo_semanal", replace_existing=True)

def agendar_reenvio_pendentes():
    def reenviar():
        historico = carregar_json(HISTORICO_ARQUIVO)
        hoje = datetime.now().strftime("%Y-%m-%d")
        agora = datetime.now()
        nome = carregar_nome_paciente()

        pendentes = historico.get("pendencias", [])
        reenviadas = 0

        for p in pendentes:
            if p["data"] != hoje or p["status"] != "pendente":
                continue
            try:
                hora_remedio = datetime.strptime(p["horario"], "%H:%M")
                tempo = (agora - datetime.combine(datetime.today(), hora_remedio.time())).total_seconds()

                if tempo > 300:
                    p["tentativas"] = p.get("tentativas", 0) + 1
                    registrar_ultimo_comando(p["remedio"], p["horario"])
                    mensagem = (
                        f"{emoji_por_horario()} Olá {nome}, você tomou o *{p['remedio']}* das *{p['horario']}*?\n"
                        f"Tentativa {p['tentativas']}. Responda com 'tomei o {p['remedio']}' ou 'não tomei'."
                    )
                    enviar_mensagem(mensagem)
                    reenviadas += 1
            except Exception as e:
                print(f"[⚠️] Erro na pendência: {e}")

        if reenviadas:
            salvar_json(HISTORICO_ARQUIVO, historico)

    scheduler.add_job(reenviar, trigger='interval', minutes=10, name="reenvio_pendentes", replace_existing=True)

# ========== EXECUÇÃO ==========
if __name__ == "__main__":
    print("🩺 Agendador iniciado...")
    scheduler.start()

    agendar_alertas()
    agendar_relatorio_diario()
    agendar_resumo_semanal()
    agendar_reenvio_pendentes()

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("🛑 Agendador encerrado.")
