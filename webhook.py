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

    # Lista de nomes válidos
    nomes_validos = [r["nome"].lower() for r in remedios]

    # Tentativa de aproximação de nomes
    def corrigir_nome(nome_digitado):
        match = difflib.get_close_matches(nome_digitado.lower(), nomes_validos, n=1, cutoff=0.6)
        return match[0].title() if match else nome_digitado.title()

    # === LISTAR REMÉDIOS DO DIA ===
    comandos_dia = [
        "remédio tenho que tomar", "quais remedios", "remédios de hoje",
        "quais faltam", "falta algum", "o que falta", "qual não tomei"
    ]
    if any(comando in texto for comando in comandos_dia):
        resposta.message(f"📋 Hoje você ainda precisa tomar:\n{listar_remedios_do_dia(remedios)}")
        return str(resposta)

    # === LISTAR JÁ TOMADOS ===
    if "o que já tomei" in texto or "já tomei" in texto:
        confirmados = [c for c in historico.get("confirmacoes", []) if c["data"] == hoje and c.get("confirmado")]
        if confirmados:
            lista = "\n".join(f"- {c['remedio']} às {c['hora']}" for c in confirmados)
            resposta.message(f"✅ Hoje você já tomou:\n{lista}")
        else:
            resposta.message("📭 Nenhum remédio confirmado hoje ainda.")
        return str(resposta)

    # === CONFIRMAÇÃO: "tomei o Lipidil"
    match = re.search(r"tomei o ([\w\s\-]+)", texto)
    if match:
        nome_digitado = match.group(1).strip()
        remedio_nome = corrigir_nome(nome_digitado)
        historico.setdefault("confirmacoes", []).append({
            "data": hoje,
            "hora": hora_atual,
            "remedio": remedio_nome,
            "confirmado": True
        })
        salvar_json(HISTORICO_ARQUIVO, historico)
        atualizar_contexto(numero, "tomei", remedio=remedio_nome, hora=hora_atual)
        resposta.message(f"💊 Marquei que você tomou *{remedio_nome}* às {hora_atual}.")
        return str(resposta)

    # === NEGAÇÃO: "não tomei o Lipidil"
    match = re.search(r"não tomei o ([\w\s\-]+)", texto)
    if match:
        nome_digitado = match.group(1).strip()
        remedio_nome = corrigir_nome(nome_digitado)
        historico.setdefault("pendencias", []).append({
            "data": hoje,
            "horario": hora_atual,
            "remedio": remedio_nome,
            "status": "pendente",
            "tentativas": 0
        })
        salvar_json(HISTORICO_ARQUIVO, historico)
        atualizar_contexto(numero, "nao_tomei", remedio=remedio_nome)
        resposta.message(f"🕐 Marquei que *{remedio_nome}* ainda está pendente.")
        return str(resposta)

    # === CORREÇÃO: "corrige, tomei o [remédio] às [hora]"
    match = re.search(r"corrige.*tomei o ([\w\s\-]+) às (\d{2}:\d{2})", texto)
    if match:
        nome_digitado = match.group(1).strip()
        hora_corrigida = match.group(2)
        remedio_nome = corrigir_nome(nome_digitado)
        historico.setdefault("confirmacoes", []).append({
            "data": hoje,
            "hora": hora_corrigida,
            "remedio": remedio_nome,
            "confirmado": True
        })
        salvar_json(HISTORICO_ARQUIVO, historico)
        atualizar_contexto(numero, "corrige", remedio=remedio_nome, hora=hora_corrigida)
        resposta.message(f"🔁 Corrigido! Você tomou *{remedio_nome}* às {hora_corrigida}.")
        return str(resposta)

    # === ERRO: "errei, não tomei o Lipidil"
    match = re.search(r"errei.*não tomei o ([\w\s\-]+)", texto)
    if match:
        nome_digitado = match.group(1).strip()
        remedio_nome = corrigir_nome(nome_digitado)
        historico["confirmacoes"] = [
            c for c in historico.get("confirmacoes", [])
            if not (c["data"] == hoje and c["remedio"].lower() == remedio_nome.lower())
        ]
        salvar_json(HISTORICO_ARQUIVO, historico)
        atualizar_contexto(numero, "errei", remedio=remedio_nome)
        resposta.message(f"⚠️ Ok! Apaguei a confirmação do *{remedio_nome}*.")
        return str(resposta)

    # === DEFAULT
    comandos = (
        "🔍 Exemplos de comandos:\n"
        "- *tomei o Lipidil*\n"
        "- *não tomei o Zyloric*\n"
        "- *quais faltam?*\n"
        "- *o que já tomei?*\n"
        "- *errei, não tomei o [remédio]*\n"
        "- *corrige, tomei o [remédio] às [hora]*"
    )
    resposta.message(f"{gerar_saudacao_com_hora()}\n\n{erro_engracado()}\n\n{comandos}")
    return str(resposta)
