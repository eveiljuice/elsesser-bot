# CI/CD Setup Instructions

## TL;DR
Автоматический деплой на сервер при пуше в main ветку GitHub через SSH и systemd service.

## Что нужно сделать:

### 1. На сервере (один раз):
```bash
# Склонировать репо
git clone https://github.com/YOUR_USERNAME/elsesser-bot.git
cd elsesser-bot

# Создать venv и установить зависимости
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Создать .env файл с переменными
nano .env
# Добавить: BOT_TOKEN, ADMIN_CHANNEL_ID, и т.д.

# Настроить systemd service
chmod +x deploy/setup-service.sh
bash deploy/setup-service.sh
```

### 2. В GitHub репозитории (Settings → Secrets and variables → Actions):
Добавить секреты:
- `SERVER_HOST` - IP или домен сервера (например: 123.45.67.89)
- `SERVER_USER` - SSH юзер (например: ubuntu или root)
- `SERVER_PORT` - SSH порт (обычно 22)
- `SSH_PRIVATE_KEY` - приватный SSH ключ (содержимое ~/.ssh/id_rsa)
- `PROJECT_PATH` - путь к проекту на сервере (например: /home/ubuntu/elsesser-bot)

### 3. Генерация SSH ключа (если нет):
```bash
# На локальной машине
ssh-keygen -t ed25519 -C "github-actions"

# Добавить публичный ключ на сервер
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@server

# Скопировать приватный ключ в GitHub Secrets
cat ~/.ssh/id_ed25519
```

### 4. Проверить:
- Запушить изменения в main ветку
- Зайти в GitHub → Actions → проверить статус workflow
- На сервере: `sudo systemctl status elsesser-bot`
- Проверить логи: `sudo journalctl -u elsesser-bot -f`

### 5. Полезные команды на сервере:
```bash
sudo systemctl status elsesser-bot    # Статус
sudo systemctl restart elsesser-bot   # Перезапуск
sudo systemctl stop elsesser-bot      # Остановка
sudo journalctl -u elsesser-bot -f    # Логи в реальном времени
```
