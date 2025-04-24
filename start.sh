#!/bin/bash

# Finaliza imediatamente se algum comando falhar
set -e

echo "🚀 Iniciando todos os serviços do Bot de Lembrete de Remédios..."

# ========= FLASK APP INICIAIS =========
echo "✅ Iniciando app.py (mensagens iniciais)..."
python app.py &

echo "✅ Iniciando main.py (agendador de alertas)..."
python main.py &

echo "✅ Iniciando reenvio.py (verificador de pendências)..."
python reenvio.py &

# ========= WEBHOOK =========
echo "🟢 Iniciando webhook.py (ponto de entrada principal)..."
python webhook.py
