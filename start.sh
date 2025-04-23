#!/bin/bash

echo "🚀 Iniciando todos os serviços..."

# Roda os scripts principais em background
python app.py &       # ✅ Envia mensagens iniciais e verificação do dia
echo "✅ app.py iniciado em background."

python main.py &      # ✅ Agendador de alertas e relatórios
echo "✅ main.py iniciado em background."

python reenvio.py &   # ✅ Reenvio automático de lembretes
echo "✅ reenvio.py iniciado em background."

# Mantém o container vivo com o webhook (não usar & aqui)
echo "🟢 Iniciando webhook.py em primeiro plano (Render monitora esse script)..."
python webhook.py
