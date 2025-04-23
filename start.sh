#!/bin/bash

echo "🚀 Iniciando todos os serviços..."

# Roda os scripts em background
python app.py &      # Mensagens iniciais do dia
python main.py &     # Agendador e notificações
python reenvio.py &  # Verificação de pendências

# Mantém o container vivo com o webhook
python webhook.py
