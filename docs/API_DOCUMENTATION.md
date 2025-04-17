# API документация DMarket Trading Bot

Этот документ содержит детальную информацию о взаимодействии с API DMarket и внутренними API компонентами проекта.

## Содержание

- [API DMarket](#api-dmarket)
  - [Инициализация](#инициализация)
  - [Методы для работы с рынком](#методы-для-работы-с-рынком)
  - [Методы для работы с инвентарем](#методы-для-работы-с-инвентарем)
  - [Торговые операции](#торговые-операции)
  - [Дополнительные методы](#дополнительные-методы)
  - [Асинхронные методы](#асинхронные-методы)
- [Telegram Bot API](#telegram-bot-api)
  - [Обработчики команд](#обработчики-команд)
  - [Клавиатуры и меню](#клавиатуры-и-меню)
- [Внутренние API](#внутренние-api)
  - [Trading Bot API](#trading-bot-api)
  - [ML Predictor API](#ml-predictor-api)
  - [Data Collector API](#data-collector-api)
  - [Database API](#database-api)
- [Обработка ошибок](#обработка-ошибок)
  - [Типы ошибок](#типы-ошибок)
  - [Стратегии повторных попыток](#стратегии-повторных-попыток)
- [Примеры использования](#примеры-использования)

## API DMarket

### Инициализация

Для начала работы с API DMarket необходимо создать экземпляр класса `DMarketAPI`:

```python
from api_wrapper import DMarketAPI

# Синхронное использование
api = DMarketAPI(
    api_key="ваш_api_ключ", 
    api_secret="ваш_api_секрет", 
    timeout=30,
    max_retries=3
)

# Асинхронное использование
async def example():
    result = await api.get_market_items_async(limit=10)
    return result
```

#### Параметры конструктора

| Параметр | Тип | Описание | По умолчанию |
|----------|-----|----------|--------------|
| api_key | str | API-ключ DMarket для авторизации | Обязательный |
| api_secret | str | API-секрет для подписи запросов | None |
| base_url | str | Базовый URL API | "https://api.dmarket.com" |
| timeout | int | Таймаут для запросов в секундах | 30 |
| max_retries | int | Максимальное число повторных попыток | 3 |

### Методы для работы с рынком

#### `get_market_items()`

Получает список предметов на рынке с возможностью фильтрации и сортировки.

```python
items = api.get_market_items(
    game_id="csgo", 
    limit=100, 
    offset=0,
    currency="USD",
    order_by="price",
    order_dir="asc"
)
```

**Параметры:**
- `game_id` (str): Идентификатор игры (по умолчанию "csgo")
- `limit` (int): Максимальное количество предметов (по умолчанию 100)
- `offset` (int): Смещение для пагинации (по умолчанию 0)
- `currency` (str): Валюта для цен (по умолчанию "USD")
- `order_by` (str): Поле для сортировки (по умолчанию "price")
- `order_dir` (str): Направление сортировки ("asc" или "desc")
- `title` (str, опционально): Фильтр по названию предмета
- `category` (str, опционально): Фильтр по категории предмета
- `price_from` (float, опционально): Минимальная цена для фильтрации
- `price_to` (float, опционально): Максимальная цена для фильтрации
- `rarity` (str, опционально): Фильтр по редкости предметов

**Возвращает:**
- `dict`: JSON-ответ с информацией о предметах на рынке

#### `search_items()`

Выполняет расширенный поиск предметов на рынке по различным параметрам.

```python
results = api.search_items(
    game_id="csgo",
    title="AK-47",
    min_price=10.0,
    max_price=100.0,
    currency="USD",
    limit=50,
    sort_by="price",
    sort_dir="asc",
    exact_match=False
)
```

**Параметры:**
- `game_id` (str): Идентификатор игры (по умолчанию "csgo")
- `title` (str): Название или часть названия предмета
- `category` (str, опционально): Категория предмета
- `min_price` (float, опционально): Минимальная цена
- `max_price` (float, опционально): Максимальная цена
- `currency` (str): Валюта для цен (по умолчанию "USD")
- `limit` (int): Максимальное количество предметов (по умолчанию 100)
- `offset` (int): Смещение для пагинации (по умолчанию 0)
- `sort_by` (str): Поле для сортировки (по умолчанию "price")
- `sort_dir` (str): Направление сортировки ("asc" или "desc")
- `exact_match` (bool): Искать точное совпадение названия (по умолчанию False)

**Возвращает:**
- `dict`: Результаты поиска предметов

#### `get_item_history()`

Получает историю цен конкретного предмета за определенный период.

```python
history = api.get_item_history(
    item_id="some-item-id",
    limit=100,
    offset=0,
    date_from=datetime(2023, 1, 1),
    date_to=datetime(2023, 12, 31)
)
```

**Параметры:**
- `item_id` (str): Идентификатор предмета
- `limit` (int): Максимальное количество записей истории (по умолчанию 100)
- `offset` (int): Смещение для пагинации (по умолчанию 0)
- `date_from` (datetime, опционально): Начальная дата для фильтрации истории
- `date_to` (datetime, опционально): Конечная дата для фильтрации истории

**Возвращает:**
- `dict`: История цен и продаж предмета

### Методы для работы с инвентарем

#### `get_user_inventory()`

Получает информацию об инвентаре пользователя.

```python
inventory = api.get_user_inventory(
    game_id="csgo",
    in_market=False
)
```

**Параметры:**
- `game_id` (str): Идентификатор игры (по умолчанию "csgo")
- `in_market` (bool): Фильтровать только предметы, выставленные на рынок

**Возвращает:**
- `dict`: Информация о предметах в инвентаре пользователя

### Торговые операции

#### `buy_item()`

Покупает предмет на рынке.

```python
# Покупка с использованием числового значения цены
result = api.buy_item(
    item_id="some-item-id",
    price=15.75,
    currency="USD"
)

# Покупка с использованием объекта ItemPrice
from schemas.schemas import ItemPrice
price_obj = ItemPrice(USD=15.75)
result = api.buy_item(
    item_id="some-item-id",
    price=price_obj
)
```

**Параметры:**
- `item_id` (str): Идентификатор предмета
- `price` (Union[int, float, ItemPrice]): Цена покупки (число или объект ItemPrice)
- `currency` (str): Валюта для цены (используется, если price - число)

**Возвращает:**
- `dict`: Результат операции покупки

#### `sell_item()`

Выставляет предмет на продажу.

```python
result = api.sell_item(
    item_id="some-item-id",
    price=20.0,
    currency="USD"
)
```

**Параметры:**
- `item_id` (str): Идентификатор предмета
- `price` (Union[int, float, ItemPrice]): Цена продажи (число или объект ItemPrice)
- `currency` (str): Валюта для цены (используется, если price - число)

**Возвращает:**
- `dict`: Результат операции продажи

#### `cancel_offer()`

Отменяет предложение о продаже.

```python
result = api.cancel_offer("offer-id-123")
```

**Параметры:**
- `offer_id` (str): Идентификатор предложения

**Возвращает:**
- `dict`: Результат операции отмены

### Дополнительные методы

#### `get_available_games()`

Получает список доступных игр на платформе.

```python
games = api.get_available_games()
```

**Возвращает:**
- `list`: Список игр с их идентификаторами и названиями

#### `get_balance()`

Получает баланс пользователя в разных валютах.

```python
balance = api.get_balance()
```

**Возвращает:**
- `dict`: Информация о балансе пользователя

#### `get_price_aggregation()`

Получает агрегированные данные о ценах для указанного предмета.

```python
aggregation = api.get_price_aggregation(
    item_name="AK-47 | Redline",
    game_id="csgo",
    currency="USD"
)
```

**Параметры:**
- `item_name` (str): Название предмета
- `game_id` (str): Идентификатор игры (по умолчанию "csgo")
- `currency` (str): Валюта для цен (по умолчанию "USD")

**Возвращает:**
- `dict`: Агрегированные данные о ценах (минимальная, средняя, максимальная)

#### `ping()`

Проверяет доступность API и правильность настроек аутентификации.

```python
is_available = api.ping()
```

**Возвращает:**
- `bool`: True, если API доступен и аутентификация работает, иначе False

### Асинхронные методы

Все вышеуказанные методы также имеют асинхронные версии с суффиксом `_async`:

```python
import asyncio

async def main():
    # Получение предметов
    items = await api.get_market_items_async(limit=50)
    
    # Поиск предметов
    search_results = await api.search_items_async(title="Knife")
    
    # Покупка предмета
    buy_result = await api.buy_item_async(
        item_id="some-item-id",
        price=15.5
    )
    
    # Продажа предмета
    sell_result = await api.sell_item_async(
        item_id="another-item-id",
        price=20.0
    )

# Запуск асинхронной функции
asyncio.run(main())
```

## Telegram Bot API

### Обработчики команд

Модуль `handlers.bot_handlers` содержит обработчики команд для Telegram-бота.

#### Основные обработчики

```python
@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    # Инициализирует бота и отправляет приветственное сообщение

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    # Отправляет справочную информацию

@router.message(Command("status"))
async def cmd_status(message: Message):
    """Обработчик команды /status"""
    # Отправляет информацию о статусе торгового бота
```

### Клавиатуры и меню

Модуль `keyboards.keyboards` содержит функции для создания интерактивных клавиатур.

```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from handlers.callbacks import MenuCallback

def get_main_menu() -> InlineKeyboardMarkup:
    """Создает главное меню бота"""
    buttons = [
        [InlineKeyboardButton(text="Статус", callback_data=MenuCallback(action="status").pack())],
        [InlineKeyboardButton(text="Настройки", callback_data=MenuCallback(action="settings").pack())],
        [InlineKeyboardButton(text="Статистика", callback_data=MenuCallback(action="stats").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
```

## Внутренние API

### Trading Bot API

Модуль `trading_bot.py` предоставляет API для управления торговым ботом.

#### Класс `TradingBot`

```python
class TradingBot:
    """Основной класс торгового бота"""
    
    def __init__(self, config, api_client=None):
        """Инициализирует экземпляр торгового бота"""
        
    def start(self):
        """Запускает торгового бота"""
        
    def stop(self):
        """Останавливает торгового бота"""
        
    def get_opportunities(self):
        """Ищет арбитражные возможности"""
        
    def execute_trade(self, opportunity):
        """Выполняет торговую операцию"""
        
    def get_status(self):
        """Возвращает текущий статус бота"""
```

### ML Predictor API

Модуль `ml_predictor.py` предоставляет API для прогнозирования цен.

#### Класс `MLPredictor`

```python
class MLPredictor:
    """Класс для прогнозирования цен на основе ML"""
    
    def __init__(self, model_path=None):
        """Инициализирует предиктор с опциональной загрузкой модели"""
        
    def train(self, historical_data):
        """Обучает модель на исторических данных"""
        
    def predict(self, item_id):
        """Предсказывает цену предмета"""
        
    def evaluate_model(self, test_data=None):
        """Оценивает точность модели"""
        
    def save_model(self, path=None):
        """Сохраняет модель"""
        
    def load_model(self, path):
        """Загружает модель"""
```

### Data Collector API

Модуль `data_collector.py` предоставляет API для сбора данных с рынка.

#### Класс `DataCollector`

```python
class DataCollector:
    """Класс для сбора данных с рынка"""
    
    def __init__(self, api_client):
        """Инициализирует коллектор данных"""
        
    def collect_market_data(self, games=None, limit=1000):
        """Собирает данные с рынка"""
        
    def save_to_db(self, data):
        """Сохраняет данные в базу данных"""
        
    def load_historical_data(self, item_id=None, start_date=None, end_date=None):
        """Загружает исторические данные из базы"""
```

### Database API

Модуль `db.db_funcs` предоставляет API для работы с базой данных.

```python
def db_get_user_settings(user_id):
    """Получает настройки пользователя"""
    
def db_update_user_settings(user_id, settings):
    """Обновляет настройки пользователя"""
    
def db_save_market_data(data):
    """Сохраняет рыночные данные"""
    
def db_get_market_data(item_id=None, start_date=None, end_date=None):
    """Получает рыночные данные"""
    
def db_save_trade(trade_data):
    """Сохраняет информацию о торговой операции"""
    
def db_get_trades(user_id=None, start_date=None, end_date=None):
    """Получает информацию о торговых операциях"""
```

## Обработка ошибок

### Типы ошибок

#### `APIError`

Базовый класс для исключений API.

```python
class APIError(Exception):
    """Базовый класс для исключений API."""
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None, 
        response: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(f"{message} (status={status_code}): {response}")
```

#### Специфические ошибки

- `AuthenticationError`: Ошибка аутентификации в API
- `RateLimitError`: Превышение лимита запросов
- `NetworkError`: Проблемы с соединением
- `ValidationError`: Ошибки валидации данных

### Стратегии повторных попыток

Проект использует библиотеку `tenacity` для управления повторными попытками:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((RequestException, RateLimitError, NetworkError))
)
def some_api_method():
    # Метод с автоматическими повторными попытками
    pass
```

## Примеры использования

### Пример 1: Поиск арбитражных возможностей

```python
from api_wrapper import DMarketAPI
from trading_bot import TradingBot

# Инициализация API
api = DMarketAPI(api_key="your_key", api_secret="your_secret")

# Проверка соединения
if not api.ping():
    print("Не удалось подключиться к API DMarket")
    exit(1)

# Создание экземпляра бота
bot = TradingBot(api_client=api)

# Поиск возможностей
opportunities = bot.get_opportunities()
print(f"Найдено {len(opportunities)} арбитражных возможностей")

# Выполнение торговых операций
for opportunity in opportunities:
    result = bot.execute_trade(opportunity)
    print(f"Результат торговой операции: {result}")
```

### Пример 2: Прогнозирование цен

```python
from ml_predictor import MLPredictor
from data_collector import DataCollector
from api_wrapper import DMarketAPI

# Инициализация API и сборщика данных
api = DMarketAPI(api_key="your_key", api_secret="your_secret")
collector = DataCollector(api_client=api)

# Загрузка исторических данных
item_id = "some-item-id"
historical_data = collector.load_historical_data(item_id=item_id)

# Создание и обучение предиктора
predictor = MLPredictor()
predictor.train(historical_data)

# Прогнозирование цены
predicted_price = predictor.predict(item_id)
print(f"Прогнозируемая цена для предмета {item_id}: {predicted_price}")

# Оценка точности модели
accuracy = predictor.evaluate_model()
print(f"Точность модели: {accuracy}")
```

### Пример 3: Асинхронная работа с API

```python
import asyncio
from api_wrapper import DMarketAPI

async def main():
    api = DMarketAPI(api_key="your_key", api_secret="your_secret")
    
    # Асинхронное получение данных
    items = await api.get_market_items_async(limit=50)
    
    # Обработка результатов
    for item in items.get('objects', []):
        print(f"Предмет: {item.get('title')}, Цена: {item.get('price', {}).get('amount')}")
    
    # Асинхронный поиск
    search_results = await api.search_items_async(
        title="AWP",
        min_price=10.0,
        max_price=100.0
    )
    
    print(f"Найдено {len(search_results.get('objects', []))} предметов")

# Запуск асинхронной функции
asyncio.run(main())
```