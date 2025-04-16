# Руководство разработчика DMarket Trading Bot

Данное руководство предназначено для разработчиков, которые хотят внести вклад в проект DMarket Trading Bot, модифицировать существующий функционал или интегрировать бота с другими системами.

## Содержание

- [Структура проекта](#структура-проекта)
- [Установка среды разработки](#установка-среды-разработки)
- [Стиль кода и соглашения](#стиль-кода-и-соглашения)
- [Архитектура бота](#архитектура-бота)
- [Рабочий процесс разработки](#рабочий-процесс-разработки)
- [Стратегии торговли](#стратегии-торговли)
- [Тестирование](#тестирование)
- [Работа с базой данных](#работа-с-базой-данных)
- [Интеграция с API](#интеграция-с-api)
- [Работа с Telegram ботом](#работа-с-telegram-ботом)
- [Логирование и мониторинг](#логирование-и-мониторинг)
- [Деплой и CI/CD](#деплой-и-cicd)
- [Часто задаваемые вопросы](#часто-задаваемые-вопросы)

## Структура проекта

Проект имеет следующую структуру директорий:

```
├── src/                     # Основной исходный код
│   ├── api/                 # API клиенты и интеграции
│   │   ├── dmarket/         # Клиент DMarket API
│   │   ├── steam/           # Интеграция с Steam API
│   │   └── common.py        # Общие компоненты API
│   ├── core/                # Ядро приложения
│   │   ├── config.py        # Конфигурация приложения
│   │   ├── constants.py     # Константы проекта
│   │   └── exceptions.py    # Пользовательские исключения
│   ├── database/            # Работа с БД
│   │   ├── models/          # SQLAlchemy модели
│   │   ├── migrations/      # Alembic миграции
│   │   └── repository/      # Репозитории для доступа к данным
│   ├── models/              # Доменные модели
│   │   ├── item.py          # Модель предмета
│   │   ├── order.py         # Модель ордера
│   │   └── user.py          # Модель пользователя
│   ├── services/            # Бизнес-логика
│   │   ├── trading/         # Торговые сервисы
│   │   ├── analytics/       # Аналитические сервисы
│   │   └── notification/    # Сервисы уведомлений
│   ├── strategies/          # Торговые стратегии
│   │   ├── base.py          # Базовая стратегия
│   │   ├── simple.py        # Простая стратегия
│   │   └── advanced.py      # Продвинутая стратегия
│   ├── telegram/            # Telegram-бот
│   │   ├── handlers/        # Обработчики команд
│   │   ├── keyboards.py     # Инлайн-клавиатуры
│   │   └── bot.py           # Инициализация бота
│   └── utils/               # Утилиты
│       ├── logger.py        # Настройка логирования
│       └── helpers.py       # Вспомогательные функции
├── tests/                   # Тесты
│   ├── unit/                # Модульные тесты
│   ├── integration/         # Интеграционные тесты
│   └── conftest.py          # Конфигурация pytest
├── scripts/                 # Вспомогательные скрипты
│   ├── setup_db.py          # Скрипт создания БД
│   └── generate_docs.py     # Генерация документации
├── docs/                    # Документация
│   ├── api/                 # Документация по API
│   └── user/                # Пользовательская документация
├── docker/                  # Docker файлы
│   ├── Dockerfile           # Основной Dockerfile
│   └── docker-compose.yml   # Конфигурация docker-compose
├── .github/                 # GitHub workflow файлы
│   └── workflows/           # CI/CD workflows
├── pyproject.toml           # Конфигурация Poetry
├── requirements.txt         # Зависимости
├── .env.example             # Пример .env файла
├── README.md                # Общее описание проекта
└── DEVELOPMENT.md           # Данный файл
```

## Установка среды разработки

### Предварительные требования

- Python 3.9+
- PostgreSQL (опционально)
- Redis (опционально)
- Git

### Шаги установки

1. Клонируйте репозиторий:

```bash
git clone https://github.com/yourusername/dmarket-trading-bot.git
cd dmarket-trading-bot
```

2. Создайте виртуальное окружение и установите зависимости:

```bash
# Установка Poetry (если не установлено)
curl -sSL https://install.python-poetry.org | python3 -

# Установка зависимостей через Poetry
poetry install

# Или через pip, если не используете Poetry
pip install -r requirements.txt
```

3. Настройте `.env` файл:

```bash
cp .env.example .env
# Отредактируйте .env файл, добавив нужные значения
```

4. Настройте pre-commit хуки для проверки качества кода:

```bash
pre-commit install
```

5. Инициализируйте базу данных:

```bash
python -m scripts.setup_db
```

## Стиль кода и соглашения

### PEP 8

Проект придерживается стандарта PEP 8 для Python. Основные правила:

- Используйте 4 пробела для отступов (не табуляцию)
- Максимальная длина строки 88 символов (согласно Black)
- Документируйте все публичные функции, классы и методы
- Используйте snake_case для переменных и функций, CamelCase для классов

### Инструменты контроля качества кода

Проект использует следующие инструменты:

- **Black**: для форматирования кода  
  `black src/ tests/`

- **isort**: для сортировки импортов  
  `isort src/ tests/`

- **flake8**: для проверки стиля кода  
  `flake8 src/ tests/`

- **mypy**: для статической типизации  
  `mypy src/`

- **pytest**: для тестирования  
  `pytest tests/`

### Документация кода

Используйте Google-style docstrings для документирования кода:

```python
def get_item_price(item_id: str, currency: str = "USD") -> float:
    """
    Получает текущую цену предмета в указанной валюте.
    
    Args:
        item_id: Уникальный идентификатор предмета
        currency: Код валюты (по умолчанию USD)
    
    Returns:
        Текущая цена предмета
        
    Raises:
        ItemNotFoundException: Если предмет не найден
        APIError: При ошибке API
    """
    # код функции
```

## Архитектура бота

DMarket Trading Bot построен на модульной архитектуре, где каждый модуль отвечает за конкретную функциональность:

```
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  Telegram Bot │<─────│    Services   │<─────│  API Clients  │
└───────────────┘      └───────────────┘      └───────────────┘
        │                      │                      │
        │                      v                      │
        │              ┌───────────────┐              │
        └─────────────►│   Strategies  │<─────────────┘
                       └───────────────┘
                              │
                              v
                      ┌───────────────┐
                      │   Database    │
                      └───────────────┘
```

### Основные компоненты

1. **API Layer**: Отвечает за взаимодействие с внешними API (DMarket, Steam и др.)
2. **Core**: Содержит основную бизнес-логику и конфигурацию
3. **Database Layer**: Управляет доступом к данным и хранению состояния
4. **Models**: Определяет доменные модели
5. **Services**: Реализует бизнес-логику и координирует работу других компонентов
6. **Strategies**: Реализует различные торговые стратегии
7. **Telegram Bot**: Управляет пользовательским интерфейсом через Telegram
8. **Utils**: Содержит вспомогательные утилиты и инструменты

### Поток данных

1. Пользователь взаимодействует с Telegram ботом
2. Бот передает команды в соответствующие сервисы
3. Сервисы используют API-клиенты для получения данных и выполнения операций
4. Торговые стратегии анализируют данные и принимают решения
5. Результаты сохраняются в базе данных и отображаются пользователю

## Рабочий процесс разработки

### Ветвление Git

Проект использует Git Flow для управления ветками:

- `main` - стабильная версия для релизов
- `develop` - ветка разработки
- `feature/*` - ветки для новых функций
- `bugfix/*` - ветки для исправления ошибок
- `release/*` - ветки для подготовки релизов

### Создание новой функциональности

1. Создайте новую ветку от `develop`:
   ```
   git checkout develop
   git pull
   git checkout -b feature/my-new-feature
   ```

2. Разработайте функциональность и напишите тесты

3. Убедитесь, что код соответствует стилю:
   ```
   black src/ tests/
   isort src/ tests/
   flake8
   mypy src/
   ```

4. Запустите тесты:
   ```
   pytest
   ```

5. Отправьте изменения и создайте Pull Request в `develop`

### Внесение изменений в API

При внесении изменений в API слой:

1. Обновите документацию API в `docs/api/`
2. Создайте или обновите интеграционные тесты
3. Обновите клиентский код, если необходимо
4. Обновите версию API в соответствии с семантическим версионированием

## Стратегии торговли

### Создание новой стратегии

Все стратегии наследуются от базового класса `BaseStrategy`:

```python
from src.strategies.base import BaseStrategy
from src.models.item import Item
from src.models.order import Order

class MyCustomStrategy(BaseStrategy):
    """
    Моя пользовательская торговая стратегия.
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        # Инициализация стратегии
    
    def analyze_market(self, items: list[Item]) -> list[Item]:
        """Анализ рынка и выбор предметов для торговли."""
        # Реализация анализа
        return filtered_items
    
    def generate_orders(self, items: list[Item]) -> list[Order]:
        """Генерация ордеров на основе анализа."""
        # Логика создания ордеров
        return orders
    
    def should_cancel_order(self, order: Order) -> bool:
        """Определяет, нужно ли отменить существующий ордер."""
        # Логика отмены ордеров
        return should_cancel
```

После создания стратегии, зарегистрируйте ее в фабрике стратегий:

```python
# src/strategies/__init__.py
from src.strategies.simple import SimpleStrategy
from src.strategies.advanced import AdvancedStrategy
from src.strategies.my_custom import MyCustomStrategy

STRATEGY_MAP = {
    "simple": SimpleStrategy,
    "advanced": AdvancedStrategy,
    "my_custom": MyCustomStrategy
}

def get_strategy(name: str, config: dict):
    """Фабрика для создания экземпляров стратегий."""
    if name not in STRATEGY_MAP:
        raise ValueError(f"Unknown strategy: {name}")
    return STRATEGY_MAP[name](config)
```

## Тестирование

### Типы тестов

Проект использует следующие типы тестов:

- **Модульные тесты**: Тестирование отдельных функций и классов
- **Интеграционные тесты**: Тестирование взаимодействия между компонентами
- **End-to-End тесты**: Тестирование полного процесса работы бота

### Запуск тестов

```bash
# Запустить все тесты
pytest

# Запустить только модульные тесты
pytest tests/unit/

# Запустить тесты с покрытием кода
pytest --cov=src tests/

# Запустить конкретный тест
pytest tests/unit/test_trading_service.py::test_create_order
```

### Мокирование внешних зависимостей

Для тестирования используйте `unittest.mock` или `pytest-mock` для мокирования внешних API и сервисов:

```python
def test_dmarket_api_client(mocker):
    # Мокирование HTTP-запроса
    mock_response = mocker.patch('requests.get')
    mock_response.return_value.json.return_value = {"item": {"id": "123", "price": 10.5}}
    mock_response.return_value.status_code = 200
    
    # Тестирование клиента
    client = DMarketAPIClient("api_key", "secret")
    result = client.get_item("123")
    
    assert result.id == "123"
    assert result.price == 10.5
```

## Работа с базой данных

### Миграции с Alembic

Проект использует Alembic для управления миграциями базы данных:

```bash
# Создание новой миграции
alembic revision --autogenerate -m "Description of changes"

# Применение миграций
alembic upgrade head

# Откат последней миграции
alembic downgrade -1
```

### Работа с моделями SQLAlchemy

Модели данных находятся в `src/database/models/`. Пример модели:

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class ItemModel(Base):
    __tablename__ = "items"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    market_hash_name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    orders = relationship("OrderModel", back_populates="item")
```

### Репозитории для доступа к данным

Для доступа к базе данных используются репозитории:

```python
from src.database.models import ItemModel
from sqlalchemy.orm import Session
from typing import List, Optional

class ItemRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, item_id: str) -> Optional[ItemModel]:
        return self.session.query(ItemModel).filter(ItemModel.id == item_id).first()
    
    def get_all(self) -> List[ItemModel]:
        return self.session.query(ItemModel).all()
    
    def create(self, item: ItemModel) -> ItemModel:
        self.session.add(item)
        self.session.commit()
        return item
    
    def update(self, item: ItemModel) -> ItemModel:
        self.session.merge(item)
        self.session.commit()
        return item
    
    def delete(self, item_id: str) -> None:
        item = self.get_by_id(item_id)
        if item:
            self.session.delete(item)
            self.session.commit()
```

## Интеграция с API

### DMarket API

Клиент для работы с DMarket API реализован в `src/api/dmarket/client.py`. Основные методы:

```python
from src.api.dmarket.client import DMarketAPIClient

# Создание клиента
client = DMarketAPIClient(api_key="your_api_key", secret_key="your_secret_key")

# Получение предмета по ID
item = client.get_item("item_id")

# Поиск предметов по фильтрам
items = client.search_items(
    game="csgo",
    category="weapon",
    min_price=10,
    max_price=100,
    limit=20
)

# Создание ордера на покупку
order = client.create_buy_order(
    item_id="item_id",
    price=15.50,
    currency="USD"
)

# Отмена ордера
client.cancel_order("order_id")
```

### Добавление новых интеграций

Для добавления новой интеграции с API:

1. Создайте новый модуль в `src/api/` (например, `src/api/new_service/`)
2. Реализуйте клиент, который наследуется от базового класса `APIClient`
3. Добавьте методы для всех необходимых операций API
4. Напишите тесты для новой интеграции
5. Добавьте документацию в `docs/api/`

## Работа с Telegram ботом

### Структура Telegram бота

Telegram бот реализован с использованием библиотеки python-telegram-bot и состоит из:

- **Handlers**: Обработчики команд и сообщений
- **Keyboards**: Инлайн-клавиатуры для интерактивного взаимодействия
- **States**: Состояния для управления диалогами
- **Context**: Контекст для хранения данных сессии пользователя

### Добавление новых команд

Для добавления новой команды создайте обработчик в `src/telegram/handlers/`:

```python
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

async def my_new_command(update: Update, context: CallbackContext) -> None:
    """Обработчик новой команды."""
    await update.message.reply_text("Это моя новая команда!")

# Регистрация команды в диспетчере
def register_handlers(dispatcher):
    dispatcher.add_handler(CommandHandler("mynewcommand", my_new_command))
```

### Создание инлайн-клавиатур

Для создания интерактивного пользовательского интерфейса используйте инлайн-клавиатуры:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_item_actions_keyboard(item_id: str):
    """Создает клавиатуру с действиями для предмета."""
    keyboard = [
        [
            InlineKeyboardButton("Купить", callback_data=f"buy:{item_id}"),
            InlineKeyboardButton("Продать", callback_data=f"sell:{item_id}")
        ],
        [
            InlineKeyboardButton("Анализ цены", callback_data=f"analyze:{item_id}"),
            InlineKeyboardButton("Отмена", callback_data="cancel")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
```

## Логирование и мониторинг

### Настройка логирования

Проект использует стандартный модуль logging с настройкой в `src/utils/logger.py`:

```python
import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, log_level: str = None) -> logging.Logger:
    """
    Настраивает и возвращает логгер с указанным именем.
    """
    level = getattr(logging, (log_level or os.getenv("LOG_LEVEL", "INFO")).upper())
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Форматтер для логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Обработчик для вывода в файл с ротацией
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f"{name}.log"),
        maxBytes=10 * 1024 * 1024,  # 10 МБ
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger
```

### Мониторинг ошибок с Sentry

Для отслеживания ошибок используется Sentry:

```python
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

def setup_sentry():
    """
    Настраивает интеграцию с Sentry для отслеживания ошибок.
    """
    sentry_dsn = os.getenv("SENTRY_DSN")
    if not sentry_dsn:
        return
    
    # Настройка интеграции с логированием
    logging_integration = LoggingIntegration(
        level=logging.INFO,      # Захват всех INFO логов
        event_level=logging.ERROR  # Отправка в Sentry только ERROR логов
    )
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[logging_integration],
        release=os.getenv("VERSION", "development"),
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=0.1
    )
```

## Деплой и CI/CD

### Docker

Проект можно запустить в Docker-контейнере:

```bash
# Сборка образа
docker build -t dmarket-bot -f docker/Dockerfile .

# Запуск контейнера
docker run -d --name dmarket-bot --env-file .env dmarket-bot
```

### GitHub Actions

CI/CD настроено с использованием GitHub Actions. Основные workflows:

1. **Tests**: Запускает линтеры и тесты при каждом push и pull request
2. **Build**: Собирает Docker-образ и публикует в регистр
3. **Deploy**: Деплоит приложение на сервер (staging или production)

Пример workflow для тестирования:

```yaml
# .github/workflows/tests.yml
name: Run Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install poetry
        poetry install
    
    - name: Lint with flake8
      run: |
        poetry run flake8 src/ tests/
    
    - name: Type check with mypy
      run: |
        poetry run mypy src/
    
    - name: Test with pytest
      run: |
        poetry run pytest --cov=src tests/
```

### Деплой на сервер

Для деплоя на сервер используется Ansible или Docker Swarm/Kubernetes.

Пример Ansible playbook:

```yaml
# deploy/playbook.yml
---
- name: Deploy DMarket Trading Bot
  hosts: trading_server
  vars:
    app_name: dmarket-bot
    
  tasks:
    - name: Pull Docker image
      docker_image:
        name: "{{ docker_registry }}/{{ app_name }}:{{ version }}"
        source: pull
    
    - name: Stop and remove existing container
      docker_container:
        name: "{{ app_name }}"
        state: absent
    
    - name: Run container
      docker_container:
        name: "{{ app_name }}"
        image: "{{ docker_registry }}/{{ app_name }}:{{ version }}"
        restart_policy: unless-stopped
        env_file: "/opt/{{ app_name }}/.env"
        volumes:
          - "/opt/{{ app_name }}/logs:/app/logs"
        networks:
          - name: app_network
```

## Часто задаваемые вопросы

### Как добавить новую торговую стратегию?

1. Создайте новый класс, наследующийся от `BaseStrategy`
2. Реализуйте методы `analyze_market`, `generate_orders` и `should_cancel_order`
3. Зарегистрируйте стратегию в фабрике стратегий в `src/strategies/__init__.py`
4. Добавьте информацию о стратегии в документацию `docs/STRATEGIES.md`

### Как изменить настройки базы данных?

Настройки базы данных задаются в переменных окружения в `.env` файле:

```
DB_DRIVER=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=username
DB_PASSWORD=password
DB_NAME=dmarket_bot
```

Или для SQLite:

```
DB_DRIVER=sqlite
DB_PATH=database.db
```

### Как добавить новую команду в Telegram бота?

1. Создайте обработчик в `src/telegram/handlers/commands.py`
2. Зарегистрируйте его в функции регистрации обработчиков
3. Добавьте описание команды в файл `src/telegram/bot.py` для отображения в меню команд
4. Если необходимо, создайте инлайн-клавиатуру в `src/telegram/keyboards.py`

### Как настроить мониторинг ошибок?

1. Зарегистрируйтесь на [Sentry](https://sentry.io)
2. Получите DSN для вашего проекта
3. Добавьте переменную `SENTRY_DSN` в файл `.env`
4. При запуске приложения Sentry будет автоматически инициализирован

### Как обновить API ключи?

API ключи хранятся в файле `.env` и могут быть обновлены в любое время. После обновления ключей перезапустите приложение для применения изменений.

```
DMARKET_API_KEY=new_api_key
DMARKET_API_SECRET=new_api_secret
```

### Как настроить бота для работы с новой игрой?

1. Добавьте константы и параметры для новой игры в `src/core/constants.py`
2. Обновите API клиент для работы с новыми параметрами
3. Создайте или адаптируйте стратегии для новой игры
4. Обновите UI бота, добавив новую игру в список доступных
5. Добавьте документацию об особенностях работы с новой игрой

### Как отлаживать ошибки в боте?

1. Увеличьте уровень логирования, установив `LOG_LEVEL=DEBUG` в `.env`
2. Проверьте логи в директории `logs/`
3. Если включен Sentry, просмотрите ошибки в панели Sentry
4. Используйте отладчик в IDE для пошаговой отладки кода
5. Добавьте временные отладочные логи в проблемные места

### Как выполнить миграцию данных между версиями?

1. Создайте скрипт миграции в `scripts/migrations/`
2. Для схемы БД используйте Alembic:
   ```bash
   alembic revision --autogenerate -m "Migration description"
   alembic upgrade head
   ```
3. Для миграции данных создайте отдельные скрипты и запустите их после миграции схемы:
   ```bash
   python -m scripts.migrations.migrate_user_data
   ``` 