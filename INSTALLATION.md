# Руководство по установке DMarket Trading Bot

Это руководство поможет вам установить и настроить DMarket Trading Bot для автоматизации торговли на платформе DMarket.

## Системные требования

- Python 3.9 или выше
- Git
- Redis (опционально, но рекомендуется для хранения состояния)
- PostgreSQL (опционально, для хранения данных и статистики)
- 2 ГБ ОЗУ минимум (рекомендуется 4 ГБ)
- 2 ГБ свободного места на диске

## Установка

### Метод 1: Стандартная установка

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/yourusername/dmarket-trading-bot.git
   cd dmarket-trading-bot
   ```

2. Создайте виртуальное окружение:
   ```bash
   # Windows
   python -m venv dmarket_bot_env
   dmarket_bot_env\Scripts\activate

   # Linux/macOS
   python3 -m venv dmarket_bot_env
   source dmarket_bot_env/bin/activate
   ```

3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

### Метод 2: Установка с Poetry

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/yourusername/dmarket-trading-bot.git
   cd dmarket-trading-bot
   ```

2. Установите Poetry (если еще не установлено):
   ```bash
   # Windows
   (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

   # Linux/macOS
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Установите зависимости с помощью Poetry:
   ```bash
   poetry install
   poetry shell
   ```

### Метод 3: Установка через Docker

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/yourusername/dmarket-trading-bot.git
   cd dmarket-trading-bot
   ```

2. Соберите и запустите Docker-контейнер:
   ```bash
   docker-compose up --build
   ```

## Настройка

### Создание конфигурационного файла

1. Скопируйте пример файла конфигурации:
   ```bash
   cp .env.example .env
   ```

2. Отредактируйте файл `.env`, заполнив необходимые значения:

   ```
   # API ключи DMarket
   DMARKET_API_KEY=ваш_api_ключ
   DMARKET_API_SECRET=ваш_api_секрет
   
   # Настройки Telegram бота
   TELEGRAM_BOT_TOKEN=токен_вашего_бота
   ADMIN_USER_IDS=123456789,987654321
   
   # Настройки базы данных
   DB_URL=postgresql://username:password@localhost:5432/dmarket_bot
   
   # Настройки Redis
   REDIS_URL=redis://localhost:6379/0
   
   # Настройки для логирования
   LOG_LEVEL=INFO
   SENTRY_DSN=ваш_sentry_dsn
   
   # Настройки торговли
   DEFAULT_GAME=csgo
   MAX_PRICE=100
   MIN_PROFIT_PERCENT=5
   ```

### Получение API ключей DMarket

1. Зарегистрируйтесь на [DMarket](https://dmarket.com)
2. Перейдите в настройки аккаунта → API ключи
3. Создайте новый API ключ с необходимыми разрешениями
4. Скопируйте API ключ и секрет в файл `.env`

### Создание Telegram бота

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Напишите `/newbot` и следуйте инструкциям
3. Скопируйте полученный токен в файл `.env` в поле `TELEGRAM_BOT_TOKEN`
4. Добавьте свой Telegram ID в поле `ADMIN_USER_IDS`

### Настройка базы данных (PostgreSQL)

1. Установите PostgreSQL на свой сервер:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install postgresql postgresql-contrib
   
   # CentOS/RHEL
   sudo yum install postgresql-server postgresql-contrib
   sudo postgresql-setup initdb
   sudo systemctl start postgresql
   ```

2. Создайте базу данных и пользователя:
   ```bash
   sudo -u postgres psql
   ```
   
   ```sql
   CREATE DATABASE dmarket_bot;
   CREATE USER dmarket_user WITH ENCRYPTED PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE dmarket_bot TO dmarket_user;
   \q
   ```

3. Обновите файл `.env`, указав URL подключения к базе данных:
   ```
   DB_URL=postgresql://dmarket_user:your_password@localhost:5432/dmarket_bot
   ```

### Настройка Redis (опционально, но рекомендуется)

1. Установите Redis:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install redis-server
   
   # CentOS/RHEL
   sudo yum install redis
   sudo systemctl start redis
   ```

2. Обновите файл `.env`, указав URL подключения к Redis:
   ```
   REDIS_URL=redis://localhost:6379/0
   ```

## Запуск бота

### Метод 1: Запуск из командной строки

1. Активируйте виртуальное окружение (если еще не активировано):
   ```bash
   # Windows
   dmarket_bot_env\Scripts\activate
   
   # Linux/macOS
   source dmarket_bot_env/bin/activate
   ```

2. Запустите бот:
   ```bash
   python telegram_bot.py
   ```

### Метод 2: Запуск с помощью Systemd (Linux)

1. Создайте файл службы:
   ```bash
   sudo nano /etc/systemd/system/dmarket-bot.service
   ```

2. Добавьте следующее содержимое:
   ```
   [Unit]
   Description=DMarket Trading Bot
   After=network.target
   
   [Service]
   User=your_username
   WorkingDirectory=/path/to/dmarket-trading-bot
   Environment="PATH=/path/to/dmarket-trading-bot/dmarket_bot_env/bin"
   ExecStart=/path/to/dmarket-trading-bot/dmarket_bot_env/bin/python telegram_bot.py
   Restart=always
   RestartSec=5
   
   [Install]
   WantedBy=multi-user.target
   ```

3. Включите и запустите службу:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable dmarket-bot
   sudo systemctl start dmarket-bot
   ```

4. Проверьте статус:
   ```bash
   sudo systemctl status dmarket-bot
   ```

### Метод 3: Запуск с помощью Docker

Если вы установили бот с помощью Docker, он уже должен быть запущен. Если нет:

```bash
docker-compose up -d
```

## Первоначальная настройка бота

1. Откройте Telegram и найдите своего бота по имени, которое вы указали при создании.
2. Отправьте команду `/start` для инициализации бота.
3. Бот проверит, есть ли ваш ID в списке администраторов. Если да, вы получите доступ к административным командам.
4. Настройте торговые параметры с помощью команды `/settings`.

## Проверка работоспособности

1. В Telegram отправьте боту команду `/status`.
2. Бот должен ответить сообщением о своем текущем состоянии и соединении с DMarket API.

## Решение проблем

### Бот не отвечает

1. Проверьте, запущен ли процесс бота:
   ```bash
   ps aux | grep telegram_bot.py
   ```

2. Проверьте логи:
   ```bash
   # Если запущен через systemd
   sudo journalctl -u dmarket-bot -f
   
   # Если запущен через Docker
   docker-compose logs
   ```

### Ошибки подключения к API

1. Проверьте правильность API ключей в файле `.env`.
2. Убедитесь, что у вас есть доступ к API DMarket.
3. Проверьте, не превышен ли лимит запросов к API.

### Ошибки базы данных

1. Проверьте, работает ли PostgreSQL:
   ```bash
   sudo systemctl status postgresql
   ```

2. Проверьте подключение к базе данных:
   ```bash
   psql -U dmarket_user -h localhost -d dmarket_bot
   ```

### Ошибки Redis

1. Проверьте, работает ли Redis:
   ```bash
   sudo systemctl status redis
   ```

2. Проверьте подключение к Redis:
   ```bash
   redis-cli ping
   ```

## Обновление бота

### Метод 1: Обновление через Git

1. Остановите бота:
   ```bash
   # Если запущен через systemd
   sudo systemctl stop dmarket-bot
   
   # Если запущен вручную
   # Найдите PID и используйте kill
   ```

2. Получите последние изменения:
   ```bash
   cd /path/to/dmarket-trading-bot
   git pull
   ```

3. Обновите зависимости:
   ```bash
   # Активируйте виртуальное окружение
   source dmarket_bot_env/bin/activate
   
   # Обновите зависимости
   pip install -r requirements.txt
   ```

4. Запустите бота:
   ```bash
   # Если используется systemd
   sudo systemctl start dmarket-bot
   
   # Если запускаете вручную
   python telegram_bot.py
   ```

### Метод 2: Обновление через Docker

```bash
cd /path/to/dmarket-trading-bot
git pull
docker-compose down
docker-compose up --build -d
```

## Резервное копирование

### Резервное копирование базы данных

```bash
pg_dump -U dmarket_user -h localhost dmarket_bot > backup_$(date +%Y%m%d).sql
```

### Резервное копирование конфигурации

```bash
cp .env .env.backup_$(date +%Y%m%d)
```

## Техническая поддержка

Если у вас возникли проблемы с установкой или настройкой бота:

1. Проверьте раздел часто задаваемых вопросов (FAQ) в документации
2. Проверьте открытые и закрытые issues в репозитории проекта
3. Откройте новый issue с подробным описанием вашей проблемы

## Дополнительные ресурсы

- [Документация по API DMarket](https://docs.dmarket.com)
- [Документация Telegram Bot API](https://core.telegram.org/bots/api)
- [Руководство пользователя DMarket Trading Bot](./USAGE.md)
- [Руководство разработчика DMarket Trading Bot](./DEVELOPMENT.md)