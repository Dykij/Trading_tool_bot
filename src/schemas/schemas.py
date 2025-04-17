"""
Модуль схем данных для торгового бота DMarket.

Этот модуль содержит модели Pydantic, которые определяют структуры данных,
используемые во всем приложении для проверки, сериализации и десериализации данных.
Схемы обеспечивают валидацию данных и автоматическую документацию API.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class ItemPrice(BaseModel):
    """
    Модель цены предмета в разных валютах.

    Эта модель представляет цену предмета в различных поддерживаемых валютах,
    при этом обязательной является только цена в USD.

    Attributes:
        USD: Цена в долларах США (обязательно).
        EUR: Цена в евро (опционально).
        BTC: Цена в биткоинах (опционально).
        ETH: Цена в эфире (опционально).
        USDT: Цена в Tether (опционально).
        USDC: Цена в USD Coin (опционально).
        DMARKET: Цена в токенах DMarket (опционально).

    Examples:
        >>> price = ItemPrice(USD=10.5, EUR=9.0)
        >>> price.USD
        10.5
    """
    USD: float
    EUR: Optional[float] = None
    BTC: Optional[float] = None
    ETH: Optional[float] = None
    USDT: Optional[float] = None
    USDC: Optional[float] = None
    DMARKET: Optional[float] = None

    @field_validator('USD', 'EUR', 'BTC', 'ETH', 'USDT', 'USDC', 'DMARKET')
    def validate_price(cls, v):
        """Проверяет, что все цены неотрицательные."""
        if v is not None and v < 0:
            raise ValueError('Цена не может быть отрицательной')
        return v


class ItemToBuy(BaseModel):
    """
    Модель для предмета, который нужно купить.

    Представляет собой предмет, который пользователь хочет приобрести,
    включая целевую цену и дополнительные условия.

    Attributes:
        name: Название предмета.
        price: Целевая цена в USD.
        id: Идентификатор предмета (опционально).
        created_at: Время создания записи.
        updated_at: Время последнего обновления.
        target_condition: Целевое состояние предмета (опционально).
        max_price: Максимальная цена, которую пользователь готов заплатить.
        notify_on_price_drop: Уведомлять о снижении цены.

    Examples:
        >>> item = ItemToBuy(name="AWP | Asiimov", price=45.0, target_condition="Factory New", max_price=50.0)
        >>> item.name
        'AWP | Asiimov'
    """
    name: str
    price: float
    id: Optional[int] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    target_condition: Optional[str] = None
    max_price: Optional[float] = None
    notify_on_price_drop: bool = True

    @field_validator('price')
    def price_must_be_positive(cls, v):
        """Проверка, что цена положительная."""
        if v is not None and v <= 0:
            raise ValueError('Цена должна быть положительной')
        return v

    @model_validator(mode='before')
    def validate_max_price(cls, data):
        """Проверяет, что максимальная цена не меньше целевой цены."""
        if isinstance(data, dict):
            price = data.get('price')
            max_price = data.get('max_price')

            if price is not None and max_price is not None and max_price < price:
                raise ValueError("Максимальная цена не может быть меньше целевой цены")

        return data


class ItemHistory(BaseModel):
    """
    Модель для хранения истории цен предмета.

    Содержит идентификатор и название предмета, а также список цен с отметками времени,
    что позволяет отслеживать изменение цены предмета с течением времени.

    Attributes:
        item_id: Уникальный идентификатор предмета.
        name: Название предмета.
        prices: Список исторических цен с датами.

    Examples:
        >>> history = ItemHistory(
        ...     item_id="123abc",
        ...     name="AK-47 | Redline",
        ...     prices=[{"date": datetime.now(), "price": {"USD": 25.5}}]
        ... )
    """
    item_id: str
    name: str
    prices: List[Dict[str, Union[datetime, ItemPrice]]]

    model_config = ConfigDict(
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    )


class BotUser(BaseModel):
    """
    Модель пользователя бота.

    Представляет пользователя Telegram-бота с его идентификатором, настройками
    и списком отслеживаемых предметов.

    Attributes:
        user_id: Идентификатор пользователя в Telegram.
        username: Имя пользователя (опционально).
        items: Список отслеживаемых предметов.
        created_at: Время создания пользователя.
        settings: Настройки пользователя.
        email: Email пользователя для уведомлений (опционально).
        is_admin: Флаг, указывающий, является ли пользователь администратором.

    Examples:
        >>> user = BotUser(
        ...     user_id=123456789,
        ...     username="trader_user",
        ...     items=[ItemToBuy(name="Dragon Lore", price=1000.0)]
        ... )
    """
    user_id: int
    username: Optional[str] = None
    items: List[ItemToBuy] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    settings: Dict[str, Any] = Field(default_factory=dict)
    email: Optional[str] = None
    is_admin: bool = False

    model_config = ConfigDict(
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    )


class MarketItem(BaseModel):
    """
    Модель предмета на рынке.

    Представляет предмет, доступный на рынке DMarket, включая его идентификатор,
    название, цену, состояние и другие атрибуты.

    Attributes:
        item_id: Идентификатор предмета.
        name: Название предмета.
        price: Цена предмета в разных валютах.
        condition: Состояние предмета.
        image_url: URL изображения предмета.
        available: Доступность предмета для покупки.
        float_value: Значение float для скинов (опционально).
        category: Категория предмета.
        tradable: Можно ли обменивать предмет.
        created_at: Время создания объявления.

    Examples:
        >>> item = MarketItem(
        ...     item_id="123abc",
        ...     name="Karambit | Fade",
        ...     price=ItemPrice(USD=350.0, EUR=300.0),
        ...     condition="Factory New",
        ...     category="knife"
        ... )
    """
    item_id: str
    name: str
    price: ItemPrice
    condition: Optional[str] = None
    image_url: Optional[str] = None
    available: bool = True
    float_value: Optional[float] = None
    category: Optional[str] = None
    tradable: bool = True
    created_at: Optional[datetime] = Field(default_factory=datetime.now)

    @field_validator('float_value')
    def validate_float(cls, v):
        """Проверяет, что float находится в правильном диапазоне."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError('Float должен быть в диапазоне от 0 до 1')
        return v


class ArbitrageOpportunity(BaseModel):
    """
    Модель возможности арбитража.

    Представляет обнаруженную возможность арбитража между разными рынками
    или валютами, включая расчетную прибыль.

    Attributes:
        id: Уникальный идентификатор возможности.
        items: Список предметов в арбитражном цикле.
        profit_percentage: Процент прибыли.
        profit_absolute: Абсолютная прибыль в USD.
        detected_at: Время обнаружения возможности.
        is_executed: Была ли возможность использована.
    """
    id: UUID = Field(default_factory=uuid4)
    items: List[MarketItem]
    profit_percentage: float
    profit_absolute: float
    detected_at: datetime = Field(default_factory=datetime.now)
    is_executed: bool = False

    @field_validator('profit_percentage', 'profit_absolute')
    def validate_profit(cls, v):
        """Устанавливает разумные ограничения для прибыли."""
        if v > 1000:  # Ограничение на нереалистично высокие значения
            raise ValueError('Слишком высокое значение прибыли')
        return v
