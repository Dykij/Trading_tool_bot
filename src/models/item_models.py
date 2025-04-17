from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class GameType(Enum):
    """Перечисление поддерживаемых игр."""
    CS2 = "cs2"
    DOTA2 = "dota2"
    TF2 = "tf2"


class RarityLevel(Enum):
    """Уровни редкости предметов."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    MYTHICAL = "mythical"
    LEGENDARY = "legendary"
    ANCIENT = "ancient"
    IMMORTAL = "immortal"
    ARCANA = "arcana"
    COVERT = "covert"  # Для CS2
    CLASSIFIED = "classified"  # Для CS2
    RESTRICTED = "restricted"  # Для CS2
    MIL_SPEC = "mil-spec"  # Для CS2
    INDUSTRIAL = "industrial"  # Для CS2
    CONSUMER = "consumer"  # Для CS2


class ExteriorQuality(Enum):
    """Внешнее качество предметов CS2."""
    FACTORY_NEW = "factory new"
    MINIMAL_WEAR = "minimal wear"
    FIELD_TESTED = "field tested"
    WELL_WORN = "well worn"
    BATTLE_SCARRED = "battle scarred"
    NOT_PAINTED = "not painted"  # Для предметов без качества


@dataclass
class PricePoint:
    """Цена предмета из конкретного источника."""
    marketplace: str
    price: float  # Цена в USD
    currency: str = "USD"
    volume_day: Optional[int] = None  # Объем торгов за день
    updated_at: datetime = field(default_factory=datetime.now)
    lowest_price: Optional[float] = None  # Самая низкая текущая цена
    highest_price: Optional[float] = None  # Самая высокая текущая цена
    median_price: Optional[float] = None  # Медианная цена
    extra_data: Dict[str, Any] = field(default_factory=dict)  # Дополнительные данные


@dataclass
class CS2Item:
    """Модель предмета из CS2."""
    market_hash_name: str
    name: str
    item_type: str  # Тип предмета (knife, glove, rifle, etc.)
    weapon_type: Optional[str] = None  # Конкретный тип оружия (AK-47, M4A4, etc.)
    rarity: RarityLevel = RarityLevel.COMMON
    exterior: ExteriorQuality = ExteriorQuality.NOT_PAINTED
    stattrak: bool = False
    souvenir: bool = False
    float_value: Optional[float] = None  # Значение износа (0.0-1.0)
    pattern_index: Optional[int] = None  # Индекс паттерна
    prices: Dict[str, PricePoint] = field(default_factory=dict)  # Словарь цен с разных площадок
    image_url: Optional[str] = None
    inspect_link: Optional[str] = None
    tradable: bool = True
    special_tags: List[str] = field(default_factory=list)  # blue gem, fade, etc.
    last_updated: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Дополнительная инициализация после создания."""
        if isinstance(self.rarity, str):
            try:
                self.rarity = RarityLevel[self.rarity.upper()]
            except KeyError:
                # Пытаемся найти ближайшее соответствие
                for rarity in RarityLevel:
                    if rarity.value.lower() == self.rarity.lower():
                        self.rarity = rarity
                        break
                else:
                    self.rarity = RarityLevel.COMMON
                    
        if isinstance(self.exterior, str):
            try:
                self.exterior = ExteriorQuality[self.exterior.upper().replace(" ", "_")]
            except KeyError:
                # Пытаемся найти ближайшее соответствие
                for ext in ExteriorQuality:
                    if ext.value.lower() == self.exterior.lower():
                        self.exterior = ext
                        break
                else:
                    self.exterior = ExteriorQuality.NOT_PAINTED

    def get_best_price(self) -> Optional[float]:
        """Возвращает лучшую (самую низкую) цену для предмета."""
        if not self.prices:
            return None
        return min(point.price for point in self.prices.values())
    
    def get_price_difference(self) -> Dict[str, Dict[str, float]]:
        """Рассчитывает разницу цен между разными площадками."""
        if len(self.prices) < 2:
            return {}
        
        result = {}
        marketplaces = list(self.prices.keys())
        
        for i, marketplace1 in enumerate(marketplaces):
            result[marketplace1] = {}
            for marketplace2 in marketplaces[i+1:]:
                price1 = self.prices[marketplace1].price
                price2 = self.prices[marketplace2].price
                
                if price1 and price2:
                    diff = price2 - price1
                    diff_percent = (diff / price1) * 100
                    result[marketplace1][marketplace2] = {
                        "diff": diff,
                        "diff_percent": diff_percent
                    }
        
        return result


@dataclass
class Dota2Item:
    """Модель предмета из Dota2."""
    market_hash_name: str
    name: str
    hero: Optional[str] = None  # Герой для которого предмет
    item_type: str = "misc"  # Тип предмета (set, courier, ward, etc.)
    rarity: RarityLevel = RarityLevel.COMMON
    quality: str = "standard"  # Качество (standard, genuine, corrupted, etc.)
    gems: List[Dict[str, str]] = field(default_factory=list)  # Список драгоценных камней
    prices: Dict[str, PricePoint] = field(default_factory=dict)  # Словарь цен с разных площадок
    image_url: Optional[str] = None
    tradable: bool = True
    style_unlocked: bool = False
    last_updated: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Дополнительная инициализация после создания."""
        if isinstance(self.rarity, str):
            try:
                self.rarity = RarityLevel[self.rarity.upper()]
            except KeyError:
                # Пытаемся найти ближайшее соответствие
                for rarity in RarityLevel:
                    if rarity.value.lower() == self.rarity.lower():
                        self.rarity = rarity
                        break
                else:
                    self.rarity = RarityLevel.COMMON
    
    def get_best_price(self) -> Optional[float]:
        """Возвращает лучшую (самую низкую) цену для предмета."""
        if not self.prices:
            return None
        return min(point.price for point in self.prices.values())
    
    def get_gems_value(self) -> float:
        """Оценивает стоимость гемов в предмете."""
        # В реальном приложении здесь будет логика оценки стоимости гемов
        return 0.0


@dataclass
class TF2Item:
    """Модель предмета из Team Fortress 2."""
    market_hash_name: str
    name: str
    item_type: str = "misc"  # Тип предмета (hat, weapon, etc.)
    class_name: Optional[str] = None  # Класс (Soldier, Heavy, etc.)
    quality: str = "unique"  # Качество (unique, strange, unusual, etc.)
    effect: Optional[str] = None  # Необычный эффект (если есть)
    rarity: RarityLevel = RarityLevel.COMMON
    craftable: bool = True
    prices: Dict[str, PricePoint] = field(default_factory=dict)  # Словарь цен с разных площадок
    image_url: Optional[str] = None
    tradable: bool = True
    last_updated: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Дополнительная инициализация после создания."""
        if isinstance(self.rarity, str):
            try:
                self.rarity = RarityLevel[self.rarity.upper()]
            except KeyError:
                # Пытаемся найти ближайшее соответствие
                for rarity in RarityLevel:
                    if rarity.value.lower() == self.rarity.lower():
                        self.rarity = rarity
                        break
                else:
                    self.rarity = RarityLevel.COMMON
    
    def get_best_price(self) -> Optional[float]:
        """Возвращает лучшую (самую низкую) цену для предмета."""
        if not self.prices:
            return None
        return min(point.price for point in self.prices.values())
    
    def is_unusual(self) -> bool:
        """Проверяет, является ли предмет необычным."""
        return self.quality.lower() == "unusual" and self.effect is not None


@dataclass
class SkinArbitrageOption:
    """Модель для представления арбитражной возможности для скинов."""
    item_name: str
    game: GameType
    buy_market: str
    buy_price: float
    sell_market: str
    sell_price: float
    profit: float
    profit_percent: float
    volume_day: Optional[int] = None  # Объем торгов за день
    risk_score: float = 50.0  # Оценка риска от 0 до 100
    item_details: Union[CS2Item, Dota2Item, TF2Item, None] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Вычисляет прибыль, если она не указана."""
        if not self.profit:
            self.profit = self.sell_price - self.buy_price
            
        if not self.profit_percent and self.buy_price > 0:
            self.profit_percent = (self.profit / self.buy_price) * 100
    
    @property
    def risk_adjusted_profit(self) -> float:
        """Рассчитывает прибыль с учетом риска."""
        if self.risk_score <= 0:
            return self.profit
        return self.profit * (100.0 - self.risk_score) / 100.0 