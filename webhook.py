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

    # ========== CORRIGE ==========
    if "corrige" in texto:
        match = re.search(r"corrige.*?tomei o ([\w\s\-]+).*?às (\d{1,2}:\d{2})", texto)
        if match:
            nome = encontrar_nome_proximo(match.group(1), nomes_remedios)
            nova_hora = match.group(2)
            if nome:
                for c in historico.get("confirmacoes", []):
                    if c["remedio"].lower() == nome.lower() and c["data"] == hoje:
                        c["hora"] = nova_hora
                        salvar_json(HISTORICO_ARQUIVO, historico)
                        atualizar_contexto(numero, "correcao", nome, nova_hora)
                        resposta.message(f"⏰ Corrigido! *{nome}* às *{nova_hora}*.")
                        return str(resposta)
                resposta.message(f"🤔 Nenhuma confirmação de *{nome}* encontrada hoje.")
                return str(resposta)
            resposta.message("🤨 Qual remédio? Não entendi direito...")
            return str(resposta)

    # ========== CANCELA ==========
    if "não tomei" in texto or "errei" in texto:
        for nome in nomes_remedios:
            if nome.lower() in texto:
                historico["confirmacoes"] = [
                    c
                    for c in historico.get("confirmacoes", [])
                    if not (c["remedio"].lower() == nome.lower() and c["data"] == hoje)
                ]
                salvar_json(HISTORICO_ARQUIVO, historico)
                atualizar_contexto(numero, "cancelamento", nome)
                resposta.message(f"🗑️ Remoção confirmada de *{nome}*.")
                return str(resposta)
        resposta.message("😬 Qual remédio você quer apagar mesmo?")
        return str(resposta)

    # ========== CONFIRMA ==========
    if "tomei" in texto or texto in ["sim", "claro", "foi", "confirmado", "já tomei"]:
        nome_confirmado = None
        hora_confirmada = None

        for r in remedios:
            if r["nome"].lower() in texto:
                nome_confirmado = r["nome"]
                hora_confirmada = r["horarios"][0]["hora"]
                break
        if not nome_confirmado:
            for r in remedios:
                if any(p in texto for p in r["nome"].lower().split()):
                    nome_confirmado = encontrar_nome_proximo(r["nome"], nomes_remedios)
                    if nome_confirmado:
                        hora_confirmada = r["horarios"][0]["hora"]
                        break
        if not nome_confirmado:
            pendencias = [
                p
                for p in historico.get("pendencias", [])
                if p["data"] == hoje and p["status"] == "pendente"
            ]
            if pendencias:
                nome_confirmado = pendencias[0]["remedio"]
                hora_confirmada = pendencias[0]["horario"]
            else:
                resposta.message("🤔 Qual remédio você tomou mesmo?")
                return str(resposta)

        historico.setdefault("confirmacoes", []).append(
            {
                "remedio": nome_confirmado,
                "data": hoje,
                "hora": hora_confirmada or "horário desconhecido",
                "confirmado": True,
            }
        )

        historico["pendencias"] = [
            p
            for p in historico.get("pendencias", [])
            if not (
                p["remedio"].lower() == nome_confirmado.lower() and p["data"] == hoje
            )
        ]
        salvar_json(HISTORICO_ARQUIVO, historico)
        atualizar_contexto(numero, "confirmacao", nome_confirmado, hora_confirmada)

        resposta.message(
            f"{gerar_saudacao()}\n{mensagem_confirmacao(nome_confirmado, hora_confirmada)}"
        )
        return str(resposta)

    # ========== PENDENTES ==========
    if "falta" in texto or "pendente" in texto or "quais" in texto:
        pendentes = []
        for r in remedios:
            for h in r["horarios"]:
                confirmado = any(
                    c["remedio"].lower() == r["nome"].lower()
                    and c["data"] == hoje
                    and c["hora"] == h["hora"]
                    for c in historico.get("confirmacoes", [])
                )
                if not confirmado:
                    pendentes.append(f"{r['nome']} às {h['hora']}")
        atualizar_contexto(numero, "pendentes")

        if pendentes:
            resposta.message(
                f"📋 Ainda falta tomar:\n" + "\n".join(f"🔔 {p}" for p in pendentes)
            )
        else:
            resposta.message("🎉 Nenhum remédio pendente hoje!")
        return str(resposta)

    # ========== CONFIRMADOS ==========
    if "confirmado" in texto or "o que já tomei" in texto or "tomei hoje" in texto:
        confirmados = [
            c
            for c in historico.get("confirmacoes", [])
            if c["data"] == hoje and c["confirmado"]
        ]
        atualizar_contexto(numero, "confirmados")

        if confirmados:
            lista = "\n".join(f"✅ {c['remedio']} às {c['hora']}" for c in confirmados)
            resposta.message(f"🧾 Hoje você tomou:\n{lista}")
        else:
            resposta.message("📭 Nenhum remédio confirmado hoje.")
        return str(resposta)

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
