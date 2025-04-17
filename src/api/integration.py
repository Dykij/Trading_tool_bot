"""
Модуль интеграции для DMarket Trading Bot.

Этот модуль обеспечивает простую интеграцию между компонентами проекта,
предоставляя высокоуровневые функции для работы с API, сбора данных,
анализа и торговых операций.
"""

import logging
import os
import time
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

# Импортируем компоненты системы
from src.db.db_funcs import (
    get_item_by_item_id, add_item_price, create_or_update_item,
    get_latest_price, add_arbitrage_opportunity
)

# Импортируем ML модули с проверкой их доступности
try:
    from src.ml import ML_AVAILABLE, MLPredictor, investment_opportunity_to_dict
    ML_IMPORT_SUCCESSFUL = True
except ImportError:
    logging.warning("Не удалось импортировать модули ML. Будет использована заглушка.")
    ML_AVAILABLE = False
    ML_IMPORT_SUCCESSFUL = False

# Импортируем функции базы данных
try:
    from src.db.db_funcs import (
        save_market_data, 
        save_item_price_history, 
        get_item_price_history,
        update_investment_opportunity
    )
    DB_IMPORT_SUCCESSFUL = True
except ImportError:
    logging.warning("Не удалось импортировать функции базы данных. Некоторые функции будут недоступны.")
    DB_IMPORT_SUCCESSFUL = False

# Создаем классы для отсутствующих модулей
class APIClient:
    """Клиент для работы с API торговой площадки."""
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Инициализирует клиент API.
        
        Args:
            api_key: API ключ для авторизации
            api_secret: API секрет для авторизации
        """
        self.api_key = api_key
        self.api_secret = api_secret
        
    def get_popular_items(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получает список популярных предметов.
        
        Args:
            limit: Ограничение на количество предметов
            
        Returns:
            List[Dict[str, Any]]: Список популярных предметов
        """
        # Заглушка - возвращаем тестовые данные
        return [
            {"id": f"item_{i}", "name": f"Popular Item {i}"} 
            for i in range(limit)
        ]
        
    def get_item_price(self, item_id: str, source: str) -> Optional[float]:
        """
        Получает цену предмета из указанного источника.
        
        Args:
            item_id: Идентификатор предмета
            source: Источник данных (например, "dmarket", "steam")
            
        Returns:
            Optional[float]: Цена предмета или None, если не найдена
        """
        # Заглушка - генерируем случайную цену
        import random
        return round(random.uniform(1.0, 100.0), 2)

class TradingStrategy:
    """Стратегия для торговли на торговой площадке."""
    
    def __init__(
        self, 
        name: str,
        min_profit_ratio: float = 1.05,
        max_trades_per_day: int = 10,
        risk_tolerance: float = 0.5
    ):
        """
        Инициализирует торговую стратегию.
        
        Args:
            name: Название стратегии
            min_profit_ratio: Минимальный коэффициент прибыли для торговли
            max_trades_per_day: Максимальное количество сделок в день
            risk_tolerance: Толерантность к риску (0.0-1.0)
        """
        self.name = name
        self.min_profit_ratio = min_profit_ratio
        self.max_trades_per_day = max_trades_per_day
        self.risk_tolerance = risk_tolerance
        
    def evaluate_opportunity(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Оценивает торговую возможность.
        
        Args:
            opportunity: Торговая возможность
            
        Returns:
            Dict[str, Any]: Результат оценки
        """
        # Заглушка - базовая оценка прибыльности
        profit_ratio = opportunity.get("profit_ratio", 1.0)
        is_profitable = profit_ratio >= self.min_profit_ratio
        
        return {
            "opportunity_id": opportunity.get("id", "unknown"),
            "profit_ratio": profit_ratio,
            "is_profitable": is_profitable,
            "risk_score": 1.0 - self.risk_tolerance,
            "recommendation": "execute" if is_profitable else "skip"
        }

class TradingBot:
    """Торговый бот для автоматизации торговли."""
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        api_secret: Optional[str] = None,
        strategy: Optional[TradingStrategy] = None
    ):
        """
        Инициализирует торгового бота.
        
        Args:
            api_key: API ключ для авторизации
            api_secret: API секрет для авторизации
            strategy: Торговая стратегия
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.strategy = strategy or TradingStrategy(name="Default")
        self.api_client = APIClient(api_key, api_secret)
        
    def check_connection(self) -> bool:
        """
        Проверяет соединение с API.
        
        Returns:
            bool: True, если соединение установлено, иначе False
        """
        # Заглушка - всегда возвращаем True
        return True
        
    def execute_trade(
        self, 
        from_source: str, 
        to_source: str, 
        item_id: str, 
        amount: float
    ) -> Dict[str, Any]:
        """
        Выполняет торговую операцию.
        
        Args:
            from_source: Источник, откуда берется предмет
            to_source: Источник, куда помещается предмет
            item_id: Идентификатор предмета
            amount: Количество предметов
            
        Returns:
            Dict[str, Any]: Результат операции
        """
        # Заглушка - симуляция успешной торговой операции
        return {
            "success": True,
            "from": from_source,
            "to": to_source,
            "item_id": item_id,
            "amount": amount,
            "result_amount": amount * 1.05,  # Симуляция 5% прибыли
            "timestamp": datetime.now().isoformat()
        }

# Заглушка для модели предсказания цен
class PricePredictionModel:
    """Заглушка для модели предсказания цен."""
    def predict(self, item_data):
        return {"predicted_price": item_data.get("current_price", 0) * 1.05}

# Функция-заглушка для поиска арбитражных циклов
def find_all_arbitrage_cycles(graph, start_currency="", min_profit=0.0, max_length=5):
    """
    Заглушка для функции поиска арбитражных циклов.
    В реальной реализации использовала бы алгоритм поиска циклов в графе.
    """
    # Возвращаем пустой список, так как это просто заглушка
    return []

# Настройка логирования
logger = logging.getLogger("integration")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/integration.log')
    ]
)

class StatArbitrage:
    """
    Класс для статистического арбитража.
    
    Анализирует рыночные данные для поиска возможностей арбитража
    на основе статистических отклонений цен.
    """
    
    def __init__(self, min_price_difference: float = 5.0):
        """
        Инициализирует систему статистического арбитража.
        
        Args:
            min_price_difference: Минимальная процентная разница в цене
                                 для определения арбитражной возможности
        """
        self.min_price_difference = min_price_difference
        self.items = {}
        self.price_data = {}
        self.graph = {}
        self.api_client = APIClient()
        self.prediction_model = PricePredictionModel()
        
    def reset(self):
        """Сбрасывает внутреннее состояние."""
        self.items = {}
        self.price_data = {}
        self.graph = {}
    
    def add_item(self, item_id: str, name: str, prices: Dict[str, float]):
        """
        Добавляет предмет для анализа.

        Args:
            item_id: Уникальный идентификатор предмета
            name: Название предмета
            prices: Словарь с ценами из разных источников
        """
        self.items[item_id] = {
            "name": name,
            "prices": prices
        }
        
        # Обновляем данные о ценах
        for source, price in prices.items():
            if source not in self.price_data:
                self.price_data[source] = {}
            self.price_data[source][item_id] = price
        
        # Обновляем граф для поиска арбитражных возможностей
        for source1, price1 in prices.items():
            for source2, price2 in prices.items():
                if source1 != source2:
                    # Создаем ребро в графе
                    if price1 > 0:  # Избегаем деления на ноль
                        price_ratio = price2 / price1
                        price_diff_percent = (price2 - price1) / price1 * 100
                        
                        if price_diff_percent >= self.min_price_difference:
                            self.add_edge(source1, source2, item_id, price_ratio, price_diff_percent)
    
    def add_edge(self, from_source: str, to_source: str, 
                item_id: str, price_ratio: float, price_diff_percent: float):
        """
        Добавляет ребро в граф для анализа арбитража.
        
        Args:
            from_source: Источник цены, откуда начинается ребро
            to_source: Источник цены, куда ведет ребро
            item_id: Идентификатор предмета
            price_ratio: Соотношение цен (to_price / from_price)
            price_diff_percent: Процентная разница в цене
        """
        # Создаем ключи в графе, если их еще нет
        if from_source not in self.graph:
            self.graph[from_source] = {}
        
        if to_source not in self.graph[from_source]:
            self.graph[from_source][to_source] = []
        
        # Добавляем информацию о ребре
        self.graph[from_source][to_source].append({
            "item_id": item_id,
            "name": self.items[item_id]["name"],
            "ratio": price_ratio,
            "diff_percent": price_diff_percent
        })
    
    def find_arbitrage_opportunities(self, max_cycle_length: int = 3) -> List[Dict[str, Any]]:
        """
        Находит возможности для арбитража.

        Args:
            max_cycle_length: Максимальная длина цикла арбитража

        Returns:
            List[Dict[str, Any]]: Список найденных возможностей арбитража
        """
        opportunities = []
        
        # Находим циклы в графе с использованием алгоритма поиска циклов
        cycles = find_all_arbitrage_cycles(
            self.graph, 
            min_profit=self.min_price_difference,
            max_length=max_cycle_length
        )
        
        # Обрабатываем найденные циклы
        for cycle in cycles:
            cycle_profit = 1.0  # Начальное значение для произведения
            
            # Вычисляем общую прибыль для цикла
            for step in cycle:
                from_source = step["from"]
                to_source = step["to"]
                item_id = step["item_id"]
                
                # Получаем соотношение цен
                for edge in self.graph[from_source][to_source]:
                    if edge["item_id"] == item_id:
                        cycle_profit *= edge["ratio"]
                        break
            
            # Преобразуем в процентную прибыль
            profit_percent = (cycle_profit - 1.0) * 100
            
            # Добавляем в список возможностей, если прибыль положительная
            if profit_percent > 0:
                opportunity = {
                    "cycle": cycle,
                    "profit_percent": profit_percent,
                    "estimated_absolute_profit": self._calculate_absolute_profit(cycle, cycle_profit)
                }
                opportunities.append(opportunity)
        
        # Сортируем по прибыльности
        opportunities.sort(key=lambda x: x["profit_percent"], reverse=True)
        
        return opportunities
    
    def _calculate_absolute_profit(self, cycle: List[Dict[str, Any]], 
                                 cycle_profit: float) -> float:
        """
        Рассчитывает абсолютную прибыль для цикла арбитража.
        
        Args:
            cycle: Цикл арбитража
            cycle_profit: Относительная прибыль цикла
            
        Returns:
            float: Абсолютная прибыль в валюте
        """
        # Предполагаем, что начинаем с первого предмета в цикле
        if not cycle:
            return 0.0
        
        # Получаем стартовую сумму (цену первого предмета)
        first_step = cycle[0]
        from_source = first_step["from"]
        item_id = first_step["item_id"]
        
        # Стартовая сумма - цена предмета из первого источника
        start_amount = self.price_data.get(from_source, {}).get(item_id, 0.0)
        
        # Рассчитываем абсолютную прибыль
        absolute_profit = start_amount * (cycle_profit - 1.0)
        
        return absolute_profit
    
    def predict_future_opportunities(self, time_horizon: int = 1) -> List[Dict[str, Any]]:
        """
        Прогнозирует будущие возможности арбитража на основе модели ML.

        Args:
            time_horizon: Горизонт прогнозирования в днях

        Returns:
            List[Dict[str, Any]]: Список прогнозируемых возможностей
        """
        predicted_opportunities = []
        
        # Получаем текущие цены
        current_prices = {}
        for source, items in self.price_data.items():
            current_prices[source] = items.copy()
        
        # Для каждого предмета делаем прогноз цены
        for item_id, item_info in self.items.items():
            item_data = {
                "item_id": item_id,
                "name": item_info["name"],
                "current_price": max(item_info["prices"].values()),
                "price_history": self._get_price_history(item_id)
            }
            
            # Получаем прогноз цены от модели ML
            prediction = self.prediction_model.predict(item_data)
            predicted_price = prediction["predicted_price"]
            
            # Для каждого источника создаем прогноз
            for source in item_info["prices"]:
                # Предполагаем, что цена изменится в сторону прогноза
                current_price = item_info["prices"][source]
                price_diff = predicted_price - current_price
                
                # Линейно интерполируем на заданный горизонт времени
                daily_change = price_diff / time_horizon
                
                # Обновляем прогнозируемые цены для каждого дня
                for day in range(1, time_horizon + 1):
                    day_key = f"{source}_day{day}"
                    if day_key not in current_prices:
                        current_prices[day_key] = {}
                    
                    # Прогнозируемая цена на день
                    forecasted_price = current_price + (daily_change * day)
                    current_prices[day_key][item_id] = forecasted_price
        
        # Создаем временную копию исходного графа
        original_graph = self.graph.copy()
        original_price_data = self.price_data.copy()
        
        # Для каждого дня в горизонте прогнозирования
        for day in range(1, time_horizon + 1):
            # Обновляем данные о ценах для прогноза
            day_price_data = {}
            for source in self.price_data:
                day_key = f"{source}_day{day}"
                if day_key in current_prices:
                    day_price_data[source] = current_prices[day_key]
                else:
                    day_price_data[source] = self.price_data[source]
            
            # Временно заменяем данные о ценах
            self.price_data = day_price_data
            
            # Перестраиваем граф на основе прогнозируемых цен
            self.graph = {}
            for item_id, item_info in self.items.items():
                forecasted_prices = {}
                for source in item_info["prices"]:
                    if source in day_price_data and item_id in day_price_data[source]:
                        forecasted_prices[source] = day_price_data[source][item_id]
                    else:
                        forecasted_prices[source] = item_info["prices"][source]
                
                # Обновляем граф с прогнозируемыми ценами
                for source1, price1 in forecasted_prices.items():
                    for source2, price2 in forecasted_prices.items():
                        if source1 != source2 and price1 > 0:
                            price_ratio = price2 / price1
                            price_diff_percent = (price2 - price1) / price1 * 100
                            
                            if price_diff_percent >= self.min_price_difference:
                                self.add_edge(source1, source2, item_id, price_ratio, price_diff_percent)
            
            # Ищем возможности арбитража с прогнозируемыми ценами
            opportunities = self.find_arbitrage_opportunities()
            
            # Добавляем информацию о дне прогноза
            for opportunity in opportunities:
                opportunity["forecasted_day"] = day
                opportunity["forecasted_date"] = (
                    datetime.now() + timedelta(days=day)
                ).strftime("%Y-%m-%d")
                
                predicted_opportunities.append(opportunity)
        
        # Восстанавливаем исходное состояние
        self.graph = original_graph
        self.price_data = original_price_data
        
        # Сортируем по прибыльности
        predicted_opportunities.sort(key=lambda x: x["profit_percent"], reverse=True)
        
        return predicted_opportunities
    
    def _get_price_history(self, item_id: str) -> List[Dict[str, Any]]:
        """
        Получает историю цен для предмета.

        Args:
            item_id: Идентификатор предмета
            
        Returns:
            List[Dict[str, Any]]: История цен
        """
        # В реальной реализации здесь был бы запрос к БД или API
        # Для примера возвращаем пустой список
        return []
    
    def export_opportunities(self, opportunities: List[Dict[str, Any]], 
                          format: str = 'json') -> Optional[str]:
        """
        Экспортирует найденные возможности арбитража.
        
        Args:
            opportunities: Список возможностей
            format: Формат экспорта ('json', 'csv')

        Returns:
            Optional[str]: Путь к экспортированному файлу или None
        """
        if not opportunities:
            logger.warning("Нет возможностей для экспорта")
            return None
        
        # Создаем директорию для отчетов, если она не существует
        os.makedirs('reports', exist_ok=True)
        
        # Генерируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"arbitrage_opportunities_{timestamp}"
        
        if format == 'json':
            filepath = f"reports/{filename}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(opportunities, f, ensure_ascii=False, indent=2)
            logger.info(f"Возможности арбитража экспортированы в JSON: {filepath}")
            return filepath
        elif format == 'csv':
            # Для CSV нам нужно преобразовать структуру данных
            import csv
            
            filepath = f"reports/{filename}.csv"
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                
                # Записываем заголовки
                writer.writerow([
                    "cycle_id", "profit_percent", "estimated_profit",
                    "cycle_length", "cycle_description", "forecasted_day",
                    "forecasted_date"
                ])
                
                # Записываем данные
                for i, opp in enumerate(opportunities):
                    cycle_description = " -> ".join([
                        f"{step['from']}({step['item_id'][:8]}...)" 
                        for step in opp["cycle"]
                    ])
                    
                    writer.writerow([
                        i + 1,
                        f"{opp['profit_percent']:.2f}%",
                        f"{opp['estimated_absolute_profit']:.2f}",
                        len(opp["cycle"]),
                        cycle_description,
                        opp.get("forecasted_day", "N/A"),
                        opp.get("forecasted_date", "N/A")
                    ])
            
            logger.info(f"Возможности арбитража экспортированы в CSV: {filepath}")
            return filepath
        else:
            logger.error(f"Неподдерживаемый формат экспорта: {format}")
            return None


class IntegrationManager:
    """
    Менеджер интеграции разных компонентов системы.
    
    Отвечает за связывание и координацию работы различных компонентов:
    - Парсеры данных
    - Арбитражные стратегии
    - Торговые боты
    - База данных
    - Система уведомлений
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Инициализирует менеджер интеграции.
        
        Args:
            config: Конфигурация менеджера
        """
        self.config = config or {}
        self.api_client = APIClient()
        self.trading_bot = None
        self.stat_arbitrage = StatArbitrage()
        self.is_running = False
        self.last_update = None
        
        logger.info("Инициализирован менеджер интеграции")
    
    def initialize_trading_bot(self, api_key: str, api_secret: str, 
                             strategy: Optional[TradingStrategy] = None) -> bool:
        """
        Инициализирует торгового бота с указанными параметрами.

        Args:
            api_key: Ключ API
            api_secret: Секрет API
            strategy: Стратегия торговли

        Returns:
            bool: True, если инициализация успешна, иначе False
        """
        try:
            # Создаем экземпляр торгового бота
            self.trading_bot = TradingBot(
                api_key=api_key,
                api_secret=api_secret,
                strategy=strategy
            )
            
            # Проверяем подключение
            if not self.trading_bot.check_connection():
                logger.error("Не удалось установить соединение с API")
                return False
            
            logger.info("Торговый бот успешно инициализирован")
            return True
        except Exception as e:
            logger.error(f"Ошибка при инициализации торгового бота: {str(e)}")
            return False
    
    def collect_market_data(self) -> Dict[str, Any]:
        """
        Собирает данные с рынка для анализа.
        
        Returns:
            Dict[str, Any]: Собранные данные
        """
        data = {
            "items": {},
            "prices": {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Получаем список популярных предметов
            popular_items = self.api_client.get_popular_items(limit=10)
            
            # Для каждого предмета получаем цены из разных источников
            for item in popular_items:
                item_id = item["id"]
                name = item["name"]
                
                # Получаем цены из разных источников
                prices = {}
                
                # DMarket
                dmarket_price = self.api_client.get_item_price(item_id, source="dmarket")
                if dmarket_price is not None:
                    prices["dmarket"] = dmarket_price
                
                # Target site
                target_price = self.api_client.get_item_price(item_id, source="target")
                if target_price is not None:
                    prices["target"] = target_price
                
                # Steam market
                steam_price = self.api_client.get_item_price(item_id, source="steam")
                if steam_price is not None:
                    prices["steam"] = steam_price
                
                # Сохраняем данные о предмете
                if prices:
                    data["items"][item_id] = {
                        "id": item_id,
                        "name": name,
                        "prices": prices
                    }
                    
                    # Обновляем данные об арбитраже
                    self.stat_arbitrage.add_item(item_id, name, prices)
                    
                    # Сохраняем в БД
                    self._save_item_to_db(item_id, name, prices)
            
            # Обновляем время последнего обновления
            self.last_update = datetime.now()
            logger.info(f"Собраны данные о {len(data['items'])} предметах")
            
            return data
        except Exception as e:
            logger.error(f"Ошибка при сборе данных: {str(e)}")
            return data
    
    def _save_item_to_db(self, item_id: str, name: str, prices: Dict[str, float]) -> None:
        """
        Сохраняет данные о предмете в базе данных.
        
        Args:
            item_id: Идентификатор предмета
            name: Название предмета
            prices: Словарь с ценами из разных источников
        """
        try:
            # Создаем или обновляем предмет в БД
            item_data = {
                "item_id": item_id,
                "name": name,
                "market_hash_name": name,  # Для простоты используем то же имя
                "game": "csgo"  # Для примера всегда используем CSGO
            }
            
            item = create_or_update_item(item_data)
            
            # Получаем целочисленный ID из объекта SQLAlchemy
            db_item_id = None
            if hasattr(item, 'id'):
                if callable(item.id):
                    db_item_id = item.id()
                else:
                    # Получаем значение атрибута id
                    db_item_id = getattr(item, 'id')
            
            if db_item_id is not None:
                # Добавляем цены для каждого источника
                for source, price in prices.items():
                    add_item_price(
                        item_id=db_item_id,
                        price=price,
                        source=source
                    )
            
            logger.debug(f"Сохранены данные о предмете: {name}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных о предмете {name}: {str(e)}")
    
    def analyze_arbitrage_opportunities(self) -> List[Dict[str, Any]]:
        """
        Анализирует возможности для арбитража.
        
        Returns:
            List[Dict[str, Any]]: Список возможностей арбитража
        """
        try:
            # Получаем возможности арбитража
            opportunities = self.stat_arbitrage.find_arbitrage_opportunities()
            
            # Сохраняем их в БД
            for opp in opportunities:
                # Создаем текстовое представление цикла
                cycle_str = " -> ".join([
                    f"{step['from']}({step['item_id'][:8]}...)" 
                    for step in opp["cycle"]
                ])
                
                # Сохраняем в БД
                add_arbitrage_opportunity(
                    cycle=cycle_str,
                    profit_percentage=opp["profit_percent"],
                    absolute_profit=opp["estimated_absolute_profit"]
                )
            
            logger.info(f"Найдено {len(opportunities)} возможностей арбитража")
            return opportunities
        except Exception as e:
            logger.error(f"Ошибка при анализе возможностей арбитража: {str(e)}")
            return []
    
    def predict_future_opportunities(self, time_horizon: int = 3) -> List[Dict[str, Any]]:
        """
        Прогнозирует будущие возможности арбитража.

        Args:
            time_horizon: Горизонт прогнозирования в днях

        Returns:
            List[Dict[str, Any]]: Список прогнозируемых возможностей
        """
        try:
            # Получаем прогнозируемые возможности
            opportunities = self.stat_arbitrage.predict_future_opportunities(time_horizon)
            
            logger.info(f"Спрогнозировано {len(opportunities)} будущих возможностей арбитража")
            return opportunities
        except Exception as e:
            logger.error(f"Ошибка при прогнозировании возможностей арбитража: {str(e)}")
            return []
    
    def execute_trades(self, opportunities: List[Dict[str, Any]], 
                     max_trades: int = 3) -> List[Dict[str, Any]]:
        """
        Выполняет торговые операции на основе найденных возможностей.
        
        Args:
            opportunities: Список возможностей арбитража
            max_trades: Максимальное количество сделок
            
        Returns:
            List[Dict[str, Any]]: Результаты выполненных сделок
        """
        if not self.trading_bot:
            logger.error("Торговый бот не инициализирован")
            return []
        
        executed_trades = []
        
        # Сортируем возможности по прибыльности
        sorted_opps = sorted(
            opportunities, 
            key=lambda x: x["profit_percent"], 
            reverse=True
        )
        
        # Выполняем сделки для лучших возможностей
        for i, opp in enumerate(sorted_opps[:max_trades]):
            try:
                # Для каждого шага в цикле арбитража
                trade_result = {
                    "opportunity": opp,
                    "steps": [],
                    "success": True,
                    "total_profit": 0,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Начальная сумма для первого шага
                available_amount = None
                
                for step in opp["cycle"]:
                    from_source = step["from"]
                    to_source = step["to"]
                    item_id = step["item_id"]
                    
                    # Получаем текущую цену
                    current_price = self.api_client.get_item_price(
                        item_id, 
                        source=from_source
                    )
                    
                    # Определяем сумму для торговли
                    if available_amount is None:
                        # Первый шаг - используем фиксированную сумму
                        trade_amount = 1.0  # Для примера 1 единица предмета
                    else:
                        # Последующие шаги - используем доступную сумму
                        trade_amount = available_amount / current_price
                    
                    # Выполняем торговую операцию
                    trade = self.trading_bot.execute_trade(
                        from_source=from_source,
                        to_source=to_source,
                        item_id=item_id,
                        amount=trade_amount
                    )
                    
                    # Обновляем доступную сумму
                    available_amount = trade.get("result_amount")
                    
                    # Добавляем информацию о шаге
                    trade_result["steps"].append({
                        "from": from_source,
                        "to": to_source,
                        "item_id": item_id,
                        "amount": trade_amount,
                        "price": current_price,
                        "result_amount": available_amount,
                        "success": trade.get("success", False)
                    })
                    
                    # Если шаг не удался, прерываем цикл
                    if not trade.get("success", False):
                        trade_result["success"] = False
                        break
                
                # Рассчитываем итоговую прибыль
                if trade_result["success"] and available_amount is not None:
                    # Предполагаем, что начали с 1.0
                    trade_result["total_profit"] = available_amount - 1.0
                
                executed_trades.append(trade_result)
                
                logger.info(
                    f"Выполнена сделка для арбитражного цикла с прибылью "
                    f"{trade_result['total_profit']:.2f}"
                )
            except Exception as e:
                logger.error(f"Ошибка при выполнении сделки: {str(e)}")
        
        return executed_trades
    
    async def run_trading_bot_workflow(
        self, 
        api_key: str,
        api_secret: str,
        update_interval: int = 3600,
        max_trades_per_run: int = 3,
        time_horizon: int = 3
    ) -> None:
        """
        Запускает полный рабочий процесс торгового бота.

        Args:
            api_key: Ключ API
            api_secret: Секрет API
            update_interval: Интервал обновления данных в секундах
            max_trades_per_run: Максимальное количество сделок за один запуск
            time_horizon: Горизонт прогнозирования в днях
        """
        # Инициализируем торгового бота
        if not self.initialize_trading_bot(api_key, api_secret):
            logger.error("Не удалось инициализировать торгового бота. Процесс остановлен.")
            return
        
        self.is_running = True
        logger.info("Запущен рабочий процесс торгового бота")
        
        try:
            while self.is_running:
                # Сбор данных о рынке
                logger.info("Сбор данных о рынке...")
                market_data = self.collect_market_data()
                
                # Анализ возможностей арбитража
                logger.info("Анализ возможностей арбитража...")
                current_opportunities = self.analyze_arbitrage_opportunities()
                
                # Прогнозирование будущих возможностей
                logger.info("Прогнозирование будущих возможностей...")
                future_opportunities = self.predict_future_opportunities(time_horizon)
                
                # Выполнение торговых операций
                if current_opportunities:
                    logger.info("Выполнение торговых операций...")
                    executed_trades = self.execute_trades(
                        current_opportunities, 
                        max_trades=max_trades_per_run
                    )
                    
                    # Экспорт результатов
                    if executed_trades:
                        self._export_trading_results(executed_trades)
                else:
                    logger.info("Не найдено подходящих возможностей для торговли")
                
                # Экспорт прогнозов
                if future_opportunities:
                    self.stat_arbitrage.export_opportunities(
                        future_opportunities, 
                        format='json'
                    )
                
                # Ожидание до следующего обновления
                logger.info(f"Ожидание {update_interval} секунд до следующего обновления...")
                await asyncio.sleep(update_interval)
        except KeyboardInterrupt:
            logger.info("Процесс остановлен пользователем")
        except Exception as e:
            logger.error(f"Ошибка в рабочем процессе: {str(e)}")
        finally:
            self.is_running = False
            logger.info("Рабочий процесс торгового бота завершен")
    
    def stop(self) -> None:
        """Останавливает рабочий процесс."""
        self.is_running = False
        logger.info("Запрошена остановка рабочего процесса")
    
    def _export_trading_results(self, trades: List[Dict[str, Any]]) -> Optional[str]:
        """
        Экспортирует результаты торговли.
        
        Args:
            trades: Список выполненных сделок
            
        Returns:
            Optional[str]: Путь к экспортированному файлу или None
        """
        if not trades:
            return None
        
        # Создаем директорию для отчетов, если она не существует
        os.makedirs('reports', exist_ok=True)
        
        # Генерируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"reports/trading_results_{timestamp}.json"
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(trades, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Результаты торговли экспортированы в: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Ошибка при экспорте результатов торговли: {str(e)}")
            return None


# Для тестирования
async def main():
    """
    Основная функция для тестирования интеграции.
    """
    # Инициализируем менеджер интеграции
    manager = IntegrationManager()
    
    # Собираем данные о рынке
    market_data = manager.collect_market_data()
    print(f"Собраны данные о {len(market_data['items'])} предметах")
    
    # Анализируем возможности арбитража
    opportunities = manager.analyze_arbitrage_opportunities()
    print(f"Найдено {len(opportunities)} возможностей арбитража")
    
    # Экспортируем результаты
    if opportunities:
        export_path = manager.stat_arbitrage.export_opportunities(opportunities)
        print(f"Результаты экспортированы в: {export_path}")
    
    # Для демонстрации запускаем полный рабочий процесс на короткое время
    # Примечание: для реального использования нужны действительные API ключи
    try:
        print("Запуск рабочего процесса торгового бота на 60 секунд...")
        
        # Создаем задачу
        task = asyncio.create_task(
            manager.run_trading_bot_workflow(
                api_key="demo_key",
                api_secret="demo_secret",
                update_interval=30,  # 30 секунд для демонстрации
                max_trades_per_run=1
            )
        )
        
        # Ждем 60 секунд
        await asyncio.sleep(60)
        
        # Останавливаем процесс
        manager.stop()
        
        # Ждем завершения задачи
        await task
    except Exception as e:
        print(f"Ошибка при запуске рабочего процесса: {str(e)}")


if __name__ == "__main__":
    # Запускаем асинхронную функцию main
    asyncio.run(main())
