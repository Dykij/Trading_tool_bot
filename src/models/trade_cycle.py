from typing import List, Optional
from dataclasses import dataclass


@dataclass
class TradeCycle:
    """
    Класс для представления торгового цикла между предметами.
    
    Attributes:
        cycle_id: Уникальный идентификатор цикла
        items: Список идентификаторов предметов в цикле
        profit_percent: Процент потенциальной прибыли от цикла
        cost: Стоимость выполнения цикла в базовой валюте
        risk_score: Оценка риска от 0 до 100
        expected_duration: Ожидаемая продолжительность выполнения цикла в секундах
        description: Опциональное описание цикла
    """
    cycle_id: str
    items: List[str]
    profit_percent: float
    cost: float
    risk_score: float
    expected_duration: float
    description: Optional[str] = None
    
    def __post_init__(self):
        """Проверка и нормализация данных после инициализации."""
        # Гарантируем, что прибыль - это число
        self.profit_percent = float(self.profit_percent)
        
        # Гарантируем, что стоимость - положительное число
        self.cost = max(0.0, float(self.cost))
        
        # Оценка риска от 0 до 100
        self.risk_score = max(0.0, min(100.0, float(self.risk_score)))
        
        # Продолжительность не может быть отрицательной
        self.expected_duration = max(0.0, float(self.expected_duration))
    
    @property
    def profit_amount(self) -> float:
        """Абсолютное значение прибыли от цикла."""
        return self.cost * self.profit_percent / 100.0
    
    @property
    def risk_adjusted_profit(self) -> float:
        """Прибыль, скорректированная с учетом риска."""
        if self.risk_score <= 0:
            return self.profit_amount
        return self.profit_amount * (100.0 - self.risk_score) / 100.0
    
    @property
    def profit_risk_ratio(self) -> float:
        """Соотношение прибыли к риску."""
        if self.risk_score <= 0:
            return float('inf')  # Если риск нулевой, соотношение бесконечно
        return self.profit_percent / self.risk_score 