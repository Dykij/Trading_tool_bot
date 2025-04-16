# Руководство разработчика DMarket Trading Bot

Данное руководство содержит необходимую информацию для разработчиков, желающих вносить вклад в проект DMarket Trading Bot или адаптировать его под свои нужды.

## Содержание

- [Архитектура проекта](#архитектура-проекта)
- [Организация кода](#организация-кода)
- [Основные компоненты](#основные-компоненты)
- [Стандарты кодирования](#стандарты-кодирования)
- [Система типизации](#система-типизации)
- [Асинхронное программирование](#асинхронное-программирование)
- [Логирование](#логирование)
- [Обработка ошибок](#обработка-ошибок)
- [Тестирование](#тестирование)
- [Создание новых модулей](#создание-новых-модулей)
- [Интеграция с DMarket API](#интеграция-с-dmarket-api)
- [Интеграция с Telegram](#интеграция-с-telegram)
- [Работа с базой данных](#работа-с-базой-данных)
- [Системы кэширования](#системы-кэширования)
- [Рекомендуемые инструменты разработки](#рекомендуемые-инструменты-разработки)
- [Процесс создания Pull Request](#процесс-создания-pull-request)

## Архитектура проекта

DMarket Trading Bot построен на основе принципов модульной архитектуры с четким разделением ответственности. Основные архитектурные принципы:

### Многоуровневая архитектура

Проект разделен на несколько логических уровней:

1. **Уровень данных**: Взаимодействие с API, базой данных, хранение и обработка данных
2. **Уровень бизнес-логики**: Реализация торговых стратегий, анализ рынка, алгоритмы
3. **Уровень представления**: Telegram-бот и другие интерфейсы взаимодействия с пользователем

### Компонентная модель

```
┌─────────────────────────────────────┐
│            Интерфейсы               │
│  (Telegram-бот, CLI, Web-интерфейс) │
└───────────────────┬─────────────────┘
                    │
┌───────────────────▼─────────────────┐
│         Торговые стратегии          │
│ (Статистический арбитраж, Скальпинг)│
└───────────────────┬─────────────────┘
                    │
┌───────────────────▼─────────────────┐
│       Аналитические компоненты       │
│    (ML-предиктор, Анализ графов)    │
└───────────────────┬─────────────────┘
                    │
┌───────────────────▼─────────────────┐
│        Компоненты доступа к данным   │
│   (API-обертка, Кэширование, БД)    │
└─────────────────────────────────────┘
```

## Организация кода

Исходный код проекта организован следующим образом:

```
dmarket_trading_bot/
├── api_wrapper.py          # Обертка для DMarket API
├── bellman_ford.py         # Алгоритм Беллмана-Форда для поиска арбитража
├── cli.py                  # Интерфейс командной строки
├── config.py               # Конфигурационные параметры
├── data_collector.py       # Сбор и обработка данных
├── integration.py          # Интеграция компонентов
├── keyboards.py            # Клавиатуры для Telegram-бота
├── linear_programming.py   # Алгоритмы линейного программирования
├── main.py                 # Точка входа в приложение
├── ml_predictor.py         # Модуль машинного обучения для предсказания цен
├── stat_arbitrage.py       # Алгоритмы статистического арбитража
├── trading_bot.py          # Основная логика торгового бота
├── db/                     # Компоненты для работы с базой данных
│   ├── __init__.py
│   ├── models.py           # Модели данных
│   └── repository.py       # Репозитории для доступа к данным
├── handlers/               # Обработчики команд Telegram-бота
│   ├── __init__.py
│   ├── bot_handlers.py     # Основные обработчики команд
│   └── callbacks.py        # Обработчики колбэков
├── keyboards/              # Модули клавиатур для интерфейса
│   └── keyboards.py        # Определения клавиатур
├── parsers/                # Парсеры различных источников данных
│   ├── __init__.py
│   ├── base_parser.py      # Базовый класс парсера
│   ├── cache_manager.py    # Управление кэшированием
│   └── target_parser.py    # Целевой парсер для DMarket
├── schemas/                # Схемы данных
│   ├── __init__.py
│   └── api_schemas.py      # Схемы API
├── tests/                  # Тесты
│   ├── __init__.py
│   ├── integration/        # Интеграционные тесты
│   ├── unit/               # Модульные тесты
│   └── conftest.py         # Конфигурация тестов
└── utils/                  # Вспомогательные утилиты
    ├── __init__.py
    ├── formatters.py       # Форматирование данных
    ├── helpers.py          # Вспомогательные функции
    └── validators.py       # Функции валидации
```

## Основные компоненты

### API Wrapper

`api_wrapper.py` предоставляет интерфейс для взаимодействия с DMarket API. Основной класс:

```python
class DMarketAPI:
    def __init__(self, api_key=None, api_secret=None, base_url=None):
        # ...

    async def get_items(self, params=None):
        # ...

    async def get_item_price(self, item_id):
        # ...

    async def buy_item(self, item_id, price):
        # ...

    async def sell_item(self, item_id, price):
        # ...
```

### Торговый бот

`trading_bot.py` содержит логику торгового бота:

```python
class TradingBot:
    def __init__(self, api_client, config=None):
        # ...

    async def collect_market_data(self, limit=100):
        # ...

    async def analyze_opportunities(self, market_data):
        # ...

    async def execute_trade(self, opportunity):
        # ...

    async def run_trading_cycle(self, interval=60):
        # ...
```

### Статистический арбитраж

`stat_arbitrage.py` содержит алгоритмы для поиска арбитражных возможностей:

```python
class StatArbitrage:
    def __init__(self, min_profit_ratio=1.0):
        # ...

    def build_price_graph(self, market_data):
        # ...

    def find_arbitrage_opportunities(self, graph):
        # ...

    def find_arbitrage_cycle_in_graph(self, graph, source_node=None):
        # ...
```

### ML-предиктор

`ml_predictor.py` содержит модели машинного обучения для прогнозирования цен:

```python
class MLPredictor:
    def __init__(self, model_path=None):
        # ...

    def train_model(self, historical_data):
        # ...

    def predict_future_price(self, item_history):
        # ...

    def evaluate_model(self, test_data):
        # ...
```

## Стандарты кодирования

### Стиль кода

Проект следует стандарту [PEP 8](https://www.python.org/dev/peps/pep-0008/) с некоторыми дополнениями:

- Максимальная длина строки: 100 символов
- Отступы: 4 пробела (без табуляций)
- Именование:
  - Классы: `CamelCase`
  - Функции/методы: `snake_case`
  - Переменные: `snake_case`
  - Константы: `UPPER_SNAKE_CASE`
  - Приватные атрибуты: `_leading_underscore`

### Docstrings

Для документирования кода используется формат Google style docstrings:

```python
def function_name(param1, param2):
    """Краткое описание функции.

    Более подробное описание функции, которое может
    занимать несколько строк.

    Args:
        param1 (тип): Описание первого параметра.
        param2 (тип): Описание второго параметра.

    Returns:
        тип: Описание возвращаемого значения.

    Raises:
        ИмяИсключения: Описание когда и почему может быть вызвано исключение.
    """
    # Реализация функции
```

### Импорты

Порядок импортов должен быть следующим:

1. Стандартная библиотека Python
2. Сторонние библиотеки
3. Локальные модули проекта

Пример:

```python
# Стандартная библиотека
import os
import json
from datetime import datetime

# Сторонние библиотеки
import aiohttp
import numpy as np
from aiogram import Bot

# Локальные модули
from api_wrapper import DMarketAPI
from utils.helpers import format_price
```

## Система типизации

Проект использует аннотации типов Python для улучшения читаемости кода и обеспечения статической проверки типов:

```python
from typing import Dict, List, Optional, Any, Union

def get_item_prices(item_ids: List[str]) -> Dict[str, float]:
    """Получает цены для списка предметов.

    Args:
        item_ids: Список идентификаторов предметов.

    Returns:
        Словарь с ценами предметов, где ключ - ID предмета, значение - цена.
    """
    result: Dict[str, float] = {}
    # Реализация
    return result

class PriceAnalyzer:
    def __init__(self, threshold: Optional[float] = None) -> None:
        self.threshold: float = threshold or 0.05
    
    def analyze(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Реализация
        return {"result": "..."}
```

## Асинхронное программирование

Проект активно использует `asyncio` для асинхронного выполнения операций:

### Основные принципы

1. Все функции, которые выполняют I/O операции (сетевые запросы, операции с базой данных), должны быть асинхронными
2. Используйте `async with` и `async for` для работы с асинхронными контекстными менеджерами и итераторами
3. Избегайте блокирующих операций в асинхронных функциях
4. Используйте `asyncio.gather` для параллельного выполнения задач

Пример:

```python
async def fetch_multiple_items(api_client: DMarketAPI, item_ids: List[str]) -> List[Dict[str, Any]]:
    """Получает информацию о нескольких предметах параллельно.

    Args:
        api_client: Клиент API DMarket.
        item_ids: Список идентификаторов предметов.

    Returns:
        Список с информацией о предметах.
    """
    tasks = [api_client.get_item(item_id) for item_id in item_ids]
    return await asyncio.gather(*tasks)
```

## Логирование

Для логирования используется модуль `logging` с настройками уровней для разных компонентов:

```python
import logging

# Настройка логгера для модуля
logger = logging.getLogger(__name__)

def process_data(data):
    """Обрабатывает данные."""
    try:
        # Обработка данных
        logger.info("Данные успешно обработаны")
        return result
    except Exception as e:
        logger.error(f"Ошибка при обработке данных: {e}", exc_info=True)
        raise
```

### Уровни логирования

- **DEBUG**: Детальная информация для отладки
- **INFO**: Подтверждение, что всё работает как ожидалось
- **WARNING**: Указание на возможные проблемы
- **ERROR**: Ошибки, из-за которых функция не может выполнить свою задачу
- **CRITICAL**: Критические ошибки, требующие немедленного внимания

## Обработка ошибок

### Подход к обработке исключений

1. Используйте специализированные исключения для разных типов ошибок
2. Обрабатывайте исключения на соответствующем уровне абстракции
3. Повторяйте операции для временных ошибок с использованием `tenacity`
4. Всегда логируйте исключения с полной информацией

Пример:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class APIError(Exception):
    """Базовое исключение для ошибок API."""
    pass

class ItemNotFoundError(APIError):
    """Исключение для случая, когда предмет не найден."""
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch_item_with_retry(api_client, item_id):
    """Получает информацию о предмете с автоматическими повторными попытками.

    Args:
        api_client: Клиент API.
        item_id: Идентификатор предмета.

    Returns:
        Данные о предмете.

    Raises:
        ItemNotFoundError: Если предмет не найден.
        APIError: Если произошла ошибка при обращении к API.
    """
    try:
        return await api_client.get_item(item_id)
    except Exception as e:
        if "Item not found" in str(e):
            raise ItemNotFoundError(f"Предмет {item_id} не найден") from e
        raise APIError(f"Ошибка API при получении предмета {item_id}: {e}") from e
```

## Тестирование

### Типы тестов

1. **Модульные тесты**: Проверяют отдельные функции и классы
2. **Интеграционные тесты**: Проверяют взаимодействие между компонентами
3. **Функциональные тесты**: Проверяют соответствие требованиям

### Инструменты тестирования

- **pytest**: Фреймворк для написания тестов
- **pytest-asyncio**: Расширение для тестирования асинхронного кода
- **unittest.mock**: Модуль для создания моков и стабов

### Пример модульного теста

```python
import pytest
from unittest.mock import MagicMock, patch

from trading_bot import TradingBot

@pytest.fixture
def mock_api_client():
    """Создает мок API клиента."""
    client = MagicMock()
    client.get_items.return_value = [
        {"id": "item1", "price": 10.0},
        {"id": "item2", "price": 20.0}
    ]
    return client

@pytest.fixture
def trading_bot(mock_api_client):
    """Создает экземпляр TradingBot с моком API клиента."""
    return TradingBot(api_client=mock_api_client)

@pytest.mark.asyncio
async def test_collect_market_data(trading_bot, mock_api_client):
    """Тестирует сбор рыночных данных."""
    market_data = await trading_bot.collect_market_data(limit=10)
    
    # Проверяем, что API метод был вызван с правильными параметрами
    mock_api_client.get_items.assert_called_once_with({"limit": 10})
    
    # Проверяем результат
    assert len(market_data) == 2
    assert market_data[0]["id"] == "item1"
    assert market_data[1]["price"] == 20.0
```

## Создание новых модулей

### Шаблон для нового модуля

```python
"""
Описание модуля и его назначение.

Этот модуль содержит функциональность для [описание].
"""

import logging
from typing import Dict, List, Optional

# Настройка логгера
logger = logging.getLogger(__name__)

class NewModule:
    """Основной класс нового модуля.

    Этот класс предоставляет функциональность для [описание].

    Attributes:
        attr1: Описание атрибута.
        attr2: Описание атрибута.
    """

    def __init__(self, param1: str, param2: Optional[int] = None) -> None:
        """Инициализирует новый модуль.

        Args:
            param1: Описание параметра.
            param2: Описание параметра. По умолчанию None.
        """
        self.attr1 = param1
        self.attr2 = param2 or 0
        logger.debug(f"Инициализирован {self.__class__.__name__} с параметрами: {param1}, {param2}")

    def method1(self, input_data: Dict[str, str]) -> List[str]:
        """Обрабатывает входные данные.

        Args:
            input_data: Входные данные для обработки.

        Returns:
            Список обработанных значений.

        Raises:
            ValueError: Если входные данные недействительны.
        """
        if not input_data:
            logger.warning("Получены пустые входные данные")
            return []

        try:
            # Реализация метода
            result = [value.upper() for value in input_data.values()]
            logger.info(f"Успешно обработано {len(result)} значений")
            return result
        except Exception as e:
            logger.error(f"Ошибка при обработке данных: {e}", exc_info=True)
            raise
```

## Интеграция с DMarket API

### Основные эндпоинты

- `/exchange/v1/market/items`: Получение списка предметов на рынке
- `/exchange/v1/market/item-info`: Детальная информация о предмете
- `/exchange/v1/user/inventory`: Инвентарь пользователя
- `/exchange/v1/user/orders`: Заказы пользователя
- `/exchange/v1/buy-order`: Создание ордера на покупку
- `/exchange/v1/sell-order`: Создание ордера на продажу

### Пример работы с API

```python
from api_wrapper import DMarketAPI

async def fetch_cs_go_items(api_key, api_secret, limit=100):
    """Получает предметы CS:GO с рынка DMarket.

    Args:
        api_key: Публичный ключ API.
        api_secret: Секретный ключ API.
        limit: Максимальное количество предметов. По умолчанию 100.

    Returns:
        Список предметов CS:GO.
    """
    api = DMarketAPI(api_key=api_key, api_secret=api_secret)
    
    params = {
        "gameId": "a8db", # ID игры CS:GO
        "limit": limit,
        "orderBy": "price",
        "orderDir": "asc",
    }
    
    items = await api.get_items(params=params)
    return items
```

## Интеграция с Telegram

### Настройка бота

```python
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

# Инициализация бота и диспетчера
bot = Bot(token="YOUR_BOT_TOKEN")
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обрабатывает команду /start."""
    await message.answer(
        "Привет! Я DMarket Trading Bot. Используйте /help, чтобы узнать больше."
    )

# Запуск бота
async def main():
    await dp.start_polling(bot)
```

### Клавиатуры и inline-кнопки

```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard():
    """Создает основную клавиатуру бота."""
    buttons = [
        [
            InlineKeyboardButton(text="🔍 Поиск предметов", callback_data="search_items"),
            InlineKeyboardButton(text="💰 Мой баланс", callback_data="my_balance")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
```

## Работа с базой данных

### SQLAlchemy модели

```python
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    """Модель пользователя в базе данных."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Отношения
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    trades = relationship("Trade", back_populates="user")

class UserSettings(Base):
    """Настройки пользователя."""
    
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    notification_enabled = Column(Boolean, default=True)
    max_trade_amount = Column(Float, default=100.0)
    
    # Отношения
    user = relationship("User", back_populates="settings")
```

### Асинхронная работа с базой данных

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

# Создание асинхронного движка
engine = create_async_engine(
    "sqlite+aiosqlite:///database.db",
    echo=True,
)

# Создание фабрики сессий
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """Получает пользователя по ID Telegram.

    Args:
        telegram_id: ID пользователя в Telegram.

    Returns:
        Объект пользователя или None, если пользователь не найден.
    """
    async with async_session() as session:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
```

## Системы кэширования

### Кэширование API-запросов

```python
import functools
import json
import os
import time
from typing import Any, Callable, Dict, Optional

def cached(duration: int = 300, cache_file: str = None):
    """Декоратор для кэширования результатов функции.

    Args:
        duration: Продолжительность кэширования в секундах. По умолчанию 300 (5 минут).
        cache_file: Путь к файлу кэша. По умолчанию None (используется имя функции).

    Returns:
        Декорированная функция.
    """
    def decorator(func: Callable):
        cache: Dict[str, Dict[str, Any]] = {}
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Создаем ключ кэша из аргументов
            cache_key = f"{args}_{kwargs}"
            
            # Проверяем, есть ли в кэше актуальные данные
            now = time.time()
            if cache_key in cache and cache[cache_key]["expires"] > now:
                return cache[cache_key]["data"]
            
            # Если нет, вызываем оригинальную функцию
            result = await func(*args, **kwargs)
            
            # Сохраняем результат в кэш
            cache[cache_key] = {
                "data": result,
                "expires": now + duration
            }
            
            # Если указан файл кэша, сохраняем в него
            if cache_file:
                try:
                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    with open(cache_file, "w") as f:
                        json.dump(cache, f)
                except Exception as e:
                    logger.warning(f"Не удалось сохранить кэш в файл: {e}")
            
            return result
        
        return wrapper
    
    return decorator
```

## Рекомендуемые инструменты разработки

### Общие инструменты

- **Visual Studio Code**: IDE с отличной поддержкой Python
- **PyCharm**: Профессиональная IDE для Python
- **Git**: Система контроля версий

### Линтеры и форматтеры

- **flake8**: Проверка стиля кода
- **pylint**: Статический анализ кода
- **black**: Автоматическое форматирование кода
- **isort**: Сортировка импортов

### Проверка типов

- **mypy**: Статическая проверка типов

### Дебаггинг

- **pdb**: Встроенный отладчик Python
- **ipdb**: Улучшенная версия pdb с поддержкой IPython

## Процесс создания Pull Request

1. **Форк репозитория**: Создайте форк основного репозитория
2. **Клонирование**: Клонируйте свой форк на локальную машину
3. **Создание ветки**: Создайте новую ветку для ваших изменений
4. **Внесение изменений**: Внесите необходимые изменения в код
5. **Тестирование**: Убедитесь, что все тесты проходят успешно
6. **Коммит**: Создайте коммит с описательным сообщением
7. **Отправка изменений**: Отправьте изменения в ваш форк
8. **Создание PR**: Создайте Pull Request в основной репозиторий
9. **Code Review**: Ждите ревью от других разработчиков
10. **Исправление замечаний**: При необходимости исправьте замечания
11. **Слияние**: После одобрения ваши изменения будут слиты с основной веткой