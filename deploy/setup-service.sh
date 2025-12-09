#!/bin/bash
# Скрипт для первичной настройки systemd service на сервере
# Запускать один раз: bash deploy/setup-service.sh

PROJECT_PATH=$(pwd)
USER=$(whoami)

# Создаем systemd service файл
sudo tee /etc/systemd/system/elsesser-bot.service > /dev/null <<EOF
[Unit]
Description=Elsesser Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_PATH
Environment="PATH=$PROJECT_PATH/venv/bin"
ExecStart=$PROJECT_PATH/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd и запускаем сервис
sudo systemctl daemon-reload
sudo systemctl enable elsesser-bot
sudo systemctl start elsesser-bot

echo "✓ Service created and started"
echo "Commands:"
echo "  sudo systemctl status elsesser-bot    # Check status"
echo "  sudo systemctl restart elsesser-bot   # Restart"
echo "  sudo journalctl -u elsesser-bot -f    # View logs"
