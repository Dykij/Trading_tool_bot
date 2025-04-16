# Политика безопасности DMarket Trading Bot

Этот документ содержит рекомендации и лучшие практики по обеспечению безопасности при работе с DMarket Trading Bot.

## Содержание

- [Обнаружение и сообщение о проблемах безопасности](#обнаружение-и-сообщение-о-проблемах-безопасности)
- [Безопасное хранение учетных данных](#безопасное-хранение-учетных-данных)
- [Защита API ключей](#защита-api-ключей)
- [Безопасная работа с API DMarket](#безопасная-работа-с-api-dmarket)
- [Защита от атак и вредоносного кода](#защита-от-атак-и-вредоносного-кода)
- [Обновление зависимостей и устранение уязвимостей](#обновление-зависимостей-и-устранение-уязвимостей)
- [Безопасная конфигурация Telegram-бота](#безопасная-конфигурация-telegram-бота)
- [Защита торговых операций](#защита-торговых-операций)

## Обнаружение и сообщение о проблемах безопасности

Если вы обнаружили уязвимость в коде или проблему безопасности:

1. **Не публикуйте информацию о проблеме публично**, особенно если это критическая уязвимость
2. Создайте новую задачу (issue) в репозитории с пометкой "Security Issue" или "Security Vulnerability"
3. Подробно опишите проблему, шаги для её воспроизведения и возможное влияние
4. При необходимости добавьте информацию о возможных путях исправления

## Безопасное хранение учетных данных

Никогда не храните чувствительные данные (API ключи, токены доступа, пароли) напрямую в исходном коде. Вместо этого используйте один из следующих методов:

### 1. Использование переменных окружения

```python
import os

# Загрузка API ключей из переменных окружения
api_key = os.environ.get("DMARKET_API_KEY")
api_secret = os.environ.get("DMARKET_API_SECRET")
telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")

# Проверка наличия необходимых переменных
if not api_key или not api_secret:
    raise ValueError("Необходимо установить переменные окружения DMARKET_API_KEY и DMARKET_API_SECRET")
```

### 2. Использование .env файлов (с python-dotenv)

```python
from dotenv import load_dotenv
import os

# Загрузка переменных из .env файла
load_dotenv()

# Доступ к загруженным переменным
api_key = os.environ.get("DMARKET_API_KEY")
api_secret = os.environ.get("DMARKET_API_SECRET")
```

Обязательно добавьте `.env` файл в `.gitignore`, чтобы предотвратить его случайное добавление в репозиторий:

```
# .gitignore
.env
config.local.py
*.pem
*.key
```

### 3. Использование отдельного файла конфигурации

```python
# config_example.py (включен в репозиторий)
class Config:
    DMARKET_API_URL = "https://api.dmarket.com"
    DMARKET_API_KEY = "your_api_key_here"  # Замените на ваш ключ
    DMARKET_API_SECRET = "your_api_secret_here"  # Замените на ваш секрет

# config.py (не включен в репозиторий)
class Config:
    DMARKET_API_URL = "https://api.dmarket.com"
    DMARKET_API_KEY = "actual_api_key"
    DMARKET_API_SECRET = "actual_api_secret"
```

## Защита API ключей

### Лучшие практики для работы с API ключами

1. **Используйте минимально необходимые права доступа** - создавайте ключи только с теми разрешениями, которые действительно нужны
2. **Регулярно обновляйте ключи** - меняйте API ключи каждые 1-3 месяца
3. **Ограничивайте уровень доступа** - если возможно, ограничивайте доступ по IP-адресу или другим параметрам
4. **Не используйте один и тот же ключ для разработки и продакшн** - создавайте отдельные ключи для разных окружений
5. **Следите за использованием ключей** - регулярно проверяйте журналы активности для выявления подозрительной активности

### Безопасное хранение файлов

Если вы храните конфиденциальные данные в файлах, убедитесь, что:

- Файлы имеют правильные права доступа (например, 600 для Linux)
- Файлы хранятся вне web-доступных директорий
- На файлы нельзя сослаться напрямую из кода, который может быть доступен пользователям

## Безопасная работа с API DMarket

### Защита от превышения лимитов API

DMarket API имеет ограничения на количество запросов. Для предотвращения блокировки используйте следующие подходы:

#### Контроль частоты запросов

```python
import time
from functools import wraps

def rate_limit(calls_limit, time_period):
    """Декоратор для ограничения частоты вызовов функции."""
    calls = []
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            # Удаление устаревших вызовов
            while calls и calls[0] < current_time - time_period:
                calls.pop(0)
            
            # Проверка лимита
            if len(calls) >= calls_limit:
                sleep_time = calls[0] + time_period - current_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            # Добавление текущего вызова
            calls.append(time.time())
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(calls_limit=10, time_period=60)  # Максимум 10 вызовов в минуту
def get_market_data():
    # Реализация запроса к API
    pass
```

#### Экспоненциальный откат при ошибках

```python
def exponential_backoff(max_retries=5, initial_delay=1, backoff_factor=2):
    """Декоратор для повторных попыток с экспоненциальным откатом."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        raise e
                    
                    time.sleep(delay)
                    delay *= backoff_factor
            
            return None  # Этот код не должен выполниться
        return wrapper
    return decorator

@exponential_backoff(max_retries=3, initial_delay=2, backoff_factor=2)
def api_request():
    # Реализация запроса к API
    pass
```

### Обработка ошибок аутентификации

Никогда не игнорируйте ошибки аутентификации или другие проблемы безопасности. Обрабатывайте их должным образом:

```python
try:
    response = api.get_market_items()
except AuthenticationError as e:
    logger.error(f"Ошибка аутентификации API: {e}")
    notify_admin("Проблема с API ключами! Требуется вмешательство.")
    # Никогда не продолжайте выполнение при проблемах с аутентификацией
    raise SystemExit("Критическая ошибка аутентификации")
```

## Защита от атак и вредоносного кода

### Валидация ввода для Telegram-бота

Всегда проверяйте данные, полученные от пользователей через Telegram:

```python
def validate_user_input(text):
    """Валидирует пользовательский ввод."""
    # Проверка на допустимые символы
    if not re.match(r'^[a-zA-Z0-9 .,_-]+$', text):
        return False, "Ввод содержит недопустимые символы"
    
    # Проверка на максимальную длину
    if len(text) > 100:
        return False, "Ввод слишком длинный (максимум 100 символов)"
    
    return True, text

@dp.message_handler()
async def handle_message(message: types.Message):
    is_valid, result = validate_user_input(message.text)
    if not is_valid:
        await message.reply(f"Ошибка: {result}")
        return
    
    # Продолжение обработки сообщения
    # ...
```

### Защита от SQL-инъекций

Если вы работаете с базой данных, всегда используйте параметризованные запросы:

```python
# НЕПРАВИЛЬНО - уязвимо к SQL-инъекциям
query = f"SELECT * FROM items WHERE name = '{user_input}'"

# ПРАВИЛЬНО - использование параметризованных запросов
query = "SELECT * FROM items WHERE name = ?"
cursor.execute(query, (user_input,))
```

### Проверка скачиваемых данных

Если ваш бот загружает файлы или данные из внешних источников, всегда проверяйте их перед использованием:

```python
import hashlib

def verify_file_integrity(file_path, expected_hash):
    """Проверяет целостность файла по хешу."""
    with open(file_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    
    return file_hash == expected_hash

def download_and_verify(url, expected_hash, save_path):
    """Загружает файл и проверяет его целостность."""
    # Загрузка файла
    response = requests.get(url)
    with open(save_path, 'wb') as f:
        f.write(response.content)
    
    # Проверка целостности
    if not verify_file_integrity(save_path, expected_hash):
        os.remove(save_path)  # Удаление подозрительного файла
        raise SecurityError("Целостность загруженного файла нарушена")
    
    return save_path
```

## Обновление зависимостей и устранение уязвимостей

### Проверка уязвимостей в зависимостях

Регулярно проверяйте зависимости на наличие известных уязвимостей:

```bash
# Установка инструмента для проверки безопасности зависимостей
pip install safety

# Проверка уязвимостей
safety check -r requirements.txt
```

Вы также можете использовать `pip-audit` для более подробного анализа:

```bash
pip install pip-audit
pip-audit
```

### Автоматическое обновление зависимостей

Настройте регулярное обновление зависимостей с помощью скриптов или GitHub Dependabot:

```bash
# Обновление всех зависимостей
pip install --upgrade -r requirements.txt

# Обновление конкретной зависимости
pip install --upgrade requests
```

### Фиксация версий в requirements.txt

Для предотвращения непредвиденных обновлений фиксируйте точные версии зависимостей:

```
# requirements.txt
requests==2.28.1
aiohttp==3.8.3
aiogram==2.25.1
```

## Безопасная конфигурация Telegram-бота

### Ограничение доступа к командам

Ограничивайте доступ к административным командам только для авторизованных пользователей:

```python
from aiogram import types
from functools import wraps

# Список ID администраторов
ADMIN_IDS = [123456789, 987654321]

def admin_required(func):
    """Декоратор для ограничения доступа к командам только админам."""
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.from_user.id not in ADMIN_IDS:
            await message.reply("У вас нет доступа к этой команде")
            return
        return await func(message, *args, **kwargs)
    return wrapper

@dp.message_handler(commands=['admin_command'])
@admin_required
async def admin_command(message: types.Message):
    """Административная команда, доступная только админам."""
    await message.reply("Выполняется административная команда")
```

### Защита от флуда и спама

Настройте защиту от спама и флуда для Telegram-бота:

```python
from aiogram import Dispatcher
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message
import time
import asyncio

class AntiFloodMiddleware(BaseMiddleware):
    """Middleware для защиты от флуда."""
    
    def __init__(self, limit=5, interval=3):
        """
        Args:
            limit: Максимальное количество сообщений за интервал
            interval: Интервал в секундах
        """
        super().__init__()
        self.limit = limit
        self.interval = interval
        self.user_timeouts = {}  # user_id -> [timestamps]
    
    async def on_pre_process_message(self, message: Message, data: dict):
        user_id = message.from_user.id
        current_time = time.time()
        
        # Инициализация списка для нового пользователя
        if user_id not in self.user_timeouts:
            self.user_timeouts[user_id] = []
        
        # Удаление устаревших временных меток
        self.user_timeouts[user_id] = [
            t for t in self.user_timeouts[user_id] 
            if current_time - t <= self.interval
        ]
        
        # Проверка на флуд
        if len(self.user_timeouts[user_id]) >= self.limit:
            await message.reply("Слишком много сообщений. Пожалуйста, подождите.")
            raise asyncio.CancelledError()
        
        # Добавление текущей временной метки
        self.user_timeouts[user_id].append(current_time)

# Регистрация middleware в диспетчере
dp = Dispatcher()
dp.middleware.setup(AntiFloodMiddleware(limit=5, interval=3))
```

## Защита торговых операций

### Лимиты на торговые операции

Установите лимиты на торговые операции для минимизации потенциальных убытков:

```python
class TradingLimits:
    MAX_TRANSACTION_AMOUNT = 100.0  # Максимальная сумма одной сделки
    MAX_DAILY_AMOUNT = 500.0        # Максимальная сумма сделок в день
    MIN_PROFIT_PERCENT = 2.0        # Минимальный процент прибыли
    
    @classmethod
    def validate_transaction(cls, amount, profit_percent):
        """Проверяет транзакцию на соответствие лимитам."""
        if amount > cls.MAX_TRANSACTION_AMOUNT:
            return False, f"Превышен лимит на сделку: {amount} > {cls.MAX_TRANSACTION_AMOUNT}"
        
        if profit_percent < cls.MIN_PROFIT_PERCENT:
            return False, f"Недостаточная прибыль: {profit_percent}% < {cls.MIN_PROFIT_PERCENT}%"
        
        # Проверка дневного лимита
        today_amount = get_today_trading_amount()  # Реализуйте эту функцию
        if today_amount + amount > cls.MAX_DAILY_AMOUNT:
            return False, f"Превышен дневной лимит: {today_amount + amount} > {cls.MAX_DAILY_AMOUNT}"
        
        return True, "OK"

# Использование в торговом боте
def execute_trade(item_id, amount, profit_percent):
    is_valid, message = TradingLimits.validate_transaction(amount, profit_percent)
    if not is_valid:
        logger.warning(f"Транзакция отклонена: {message}")
        return False
    
    # Выполнение торговой операции
    # ...
    return True
```

### Двухфакторное подтверждение

Для критических операций можно использовать двухфакторное подтверждение:

```python
@dp.message_handler(commands=['confirm_trade'])
@admin_required
async def confirm_trade(message: types.Message):
    """Подтверждение торговой операции."""
    trade_id = get_pending_trade_id(message.from_user.id)
    if not trade_id:
        await message.reply("Нет ожидающих подтверждения операций")
        return
    
    # Генерация и отправка кода подтверждения
    confirmation_code = generate_confirmation_code()
    store_confirmation_code(message.from_user.id, trade_id, confirmation_code)
    
    # Отправка кода через другой канал (например, email)
    send_email_confirmation(message.from_user.id, confirmation_code)
    
    await message.reply("Код подтверждения отправлен на вашу почту. Введите его для завершения операции.")

@dp.message_handler(regexp=r'^\d{6}$')
@admin_required
async def verify_confirmation_code(message: types.Message):
    """Проверка кода подтверждения."""
    user_id = message.from_user.id
    code = message.text
    
    trade_id, stored_code = get_stored_confirmation(user_id)
    if not trade_id или code != stored_code:
        await message.reply("Неверный код подтверждения или истек срок его действия")
        return
    
    # Выполнение операции
    execute_confirmed_trade(trade_id)
    clear_confirmation(user_id)
    
    await message.reply("Операция успешно подтверждена и выполнена")
```

### Журналирование торговых операций

Всегда ведите подробный журнал всех торговых операций:

```python
def log_trade(trade_data):
    """Записывает информацию о торговой операции в журнал."""
    logger.info(
        f"Торговая операция: {trade_data['type']} | "
        f"Предмет: {trade_data['item_id']} | "
        f"Цена: {trade_data['price']} | "
        f"Время: {trade_data['timestamp']}"
    )
    
    # Сохранение в базу данных
    db.save_trade(trade_data)
    
    # Дополнительные действия при критических операциях
    if trade_data['amount'] > 50.0:
        notify_admin(f"Выполнена крупная операция: {trade_data}")
```