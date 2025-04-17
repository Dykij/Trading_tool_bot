"""
Расширенный модуль для работы с множественными источниками рыночных данных.

Этот модуль расширяет существующую функциональность multi_source_provider.py,
добавляя более продвинутые способы сбора, агрегации и анализа данных с нескольких 
торговых площадок одновременно.
"""

import logging
import asyncio
import itertools
from typing import Dict, List, Any, Optional, Union, Tuple, TypedDict, Set, Callable
from datetime import datetime, timedelta
import statistics

# Импорт базовых компонентов системы
from src.api.multi_source_provider import (
    MarketDataProvider, MarketDataAggregator, get_market_aggregator, compare_prices
)
from src.utils.error_handler import handle_exceptions, ErrorType, TradingError

# Настройка логирования
logger = logging.getLogger(__name__)


class MarketItemStatistics(TypedDict):
    """Статистика по предмету на рынке."""
    mean_price: float
    median_price: float
    min_price: float
    max_price: float
    price_volatility: float
    best_source: str
    price_trend: str  # "up", "down", "stable"
    last_update: str  # ISO формат даты и времени
    data_completeness: float  # процент доступных данных от 0 до 1
    confidence_score: float  # оценка достоверности от 0 до 1


class SearchResults(TypedDict):
    """Результаты поиска по нескольким источникам."""
    query: str
    game: str
    total_items: int
    sources: List[str]
    items: List[Dict[str, Any]]
    stats: Dict[str, Any]


class MultiSourceMarketProvider:
    """
    Расширенный провайдер данных для работы с множественными источниками.
    
    Предоставляет унифицированный интерфейс для сбора и анализа данных с различных 
    торговых площадок. Добавляет функции для анализа, кэширования и оптимизации 
    запросов.
    """
    
    def __init__(
        self, 
        cache_ttl: int = 300,  # время жизни кэша в секундах (5 минут)
        concurrency_limit: int = 10  # максимальное количество одновременных запросов
    ):
        """
        Инициализирует расширенный провайдер данных.
        
        Args:
            cache_ttl: Время жизни кэша в секундах
            concurrency_limit: Ограничение на количество одновременных запросов
        """
        self.cache_ttl = cache_ttl
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.aggregator = get_market_aggregator()
        self.cache = {}  # кэш запросов
        self.cache_timestamps = {}  # метки времени для кэша
        self.default_sources = ["dmarket", "steam"]  # источники по умолчанию
        
    async def get_item_details(
        self, 
        game_code: str, 
        item_name: str,
        sources: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Получает детальную информацию о предмете из всех доступных источников.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            sources: Список источников данных (если None, используются все)
            force_refresh: Принудительно обновить кэш
            
        Returns:
            Dict[str, Any]: Объединенная детальная информация о предмете
        """
        cache_key = f"item_details:{game_code}:{item_name}"
        if not force_refresh and cache_key in self.cache:
            # Проверяем актуальность кэша
            if (datetime.now() - self.cache_timestamps[cache_key]).total_seconds() < self.cache_ttl:
                logger.debug(f"Используем кэш для получения деталей предмета {item_name}")
                return self.cache[cache_key]
        
        # Определяем источники
        if sources is None:
            sources = self.default_sources
        
        # Получаем информацию из всех источников
        async with self.semaphore:
            item_info = await self.aggregator.get_item_info(game_code, item_name, sources)
        
        # Получаем историю цен
        async with self.semaphore:
            price_history = await self.aggregator.get_item_price_history(
                game_code, item_name, days=30, sources=sources
            )
        
        # Объединяем данные из всех источников
        combined_data = {
            "item_name": item_name,
            "game": game_code,
            "sources": sources,
            "info": item_info,
            "price_history": price_history,
            "stats": await self._calculate_market_statistics(item_info, price_history),
            "timestamp": datetime.now().isoformat()
        }
        
        # Сохраняем в кэш
        self.cache[cache_key] = combined_data
        self.cache_timestamps[cache_key] = datetime.now()
        
        return combined_data
    
    async def _calculate_market_statistics(
        self, 
        item_info: Dict[str, Dict[str, Any]],
        price_history: Dict[str, List[Dict[str, Any]]]
    ) -> MarketItemStatistics:
        """
        Рассчитывает статистику по предмету на рынке.
        
        Args:
            item_info: Информация о предмете из разных источников
            price_history: История цен из разных источников
            
        Returns:
            MarketItemStatistics: Статистика по предмету
        """
        # Извлекаем текущие цены
        current_prices = []
        best_source = None
        min_price = float('inf')
        
        for source, info in item_info.items():
            if "error" in info:
                continue
                
            if "price" in info and "USD" in info["price"]:
                price = float(info["price"]["USD"])
                current_prices.append(price)
                
                if price < min_price:
                    min_price = price
                    best_source = source
        
        # Если нет текущих цен, возвращаем пустую статистику
        if not current_prices:
            return {
                "mean_price": 0.0,
                "median_price": 0.0,
                "min_price": 0.0,
                "max_price": 0.0,
                "price_volatility": 0.0,
                "best_source": "unknown",
                "price_trend": "unknown",
                "last_update": datetime.now().isoformat(),
                "data_completeness": 0.0,
                "confidence_score": 0.0
            }
        
        # Рассчитываем базовую статистику
        mean_price = statistics.mean(current_prices)
        median_price = statistics.median(current_prices)
        max_price = max(current_prices)
        
        # Оцениваем волатильность на основе всех текущих цен
        price_volatility = statistics.stdev(current_prices) / mean_price if len(current_prices) > 1 else 0.0
        
        # Определяем тренд цены на основе истории
        trend = "stable"
        all_history_prices = []
        
        for source, history in price_history.items():
            if isinstance(history, list) and len(history) > 1:
                # Фильтруем записи с ошибками
                valid_history = [item for item in history if "error" not in item and "price" in item]
                if valid_history:
                    # Сортируем по дате (от старых к новым)
                    sorted_history = sorted(
                        valid_history, 
                        key=lambda x: datetime.fromisoformat(x["date"]) if "date" in x else datetime.now()
                    )
                    all_history_prices.extend([(item.get("date", ""), float(item["price"])) for item in sorted_history])
        
        # Если есть достаточно исторических данных, определяем тренд
        if all_history_prices:
            # Сортируем по дате
            all_history_prices.sort(key=lambda x: x[0])
            
            # Берем первую и последнюю цену
            first_price = all_history_prices[0][1]
            last_price = all_history_prices[-1][1]
            
            # Определяем тренд (порог 5%)
            if last_price > first_price * 1.05:
                trend = "up"
            elif last_price < first_price * 0.95:
                trend = "down"
        
        # Оцениваем полноту данных
        max_data_points = len(self.default_sources) * 30  # максимально возможное количество точек данных
        actual_data_points = sum(len(h) for h in price_history.values() if isinstance(h, list))
        data_completeness = min(1.0, actual_data_points / max_data_points if max_data_points > 0 else 0)
        
        # Оцениваем достоверность в зависимости от наличия данных и их согласованности
        confidence_score = data_completeness * (1.0 - min(1.0, price_volatility))
        
        return {
            "mean_price": mean_price,
            "median_price": median_price,
            "min_price": min_price,
            "max_price": max_price,
            "price_volatility": price_volatility,
            "best_source": best_source or "unknown",
            "price_trend": trend,
            "last_update": datetime.now().isoformat(),
            "data_completeness": data_completeness,
            "confidence_score": confidence_score
        }
    
    async def search_across_sources(
        self,
        game_code: str,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = 20,
        merge_results: bool = True
    ) -> SearchResults:
        """
        Выполняет поиск предмета по всем источникам и объединяет результаты.
        
        Args:
            game_code: Код игры
            query: Поисковый запрос
            sources: Список источников данных (если None, используются все)
            limit: Максимальное количество результатов
            merge_results: Объединять ли результаты из разных источников
            
        Returns:
            SearchResults: Объединенные результаты поиска
        """
        # Определяем источники
        if sources is None:
            sources = self.default_sources
        
        # Выполняем поиск по всем источникам
        all_results = {}
        tasks = []
        
        for source in sources:
            provider = self.aggregator.get_provider(source)
            if provider:
                task = asyncio.create_task(provider.search_items(game_code, query, limit))
                tasks.append((source, task))
        
        # Собираем результаты
        for source, task in tasks:
            try:
                results = await task
                all_results[source] = results
            except Exception as e:
                logger.error(f"Ошибка поиска в {source}: {e}")
                all_results[source] = [{"error": str(e)}]
        
        # Объединяем результаты, если требуется
        if merge_results:
            merged_items = []
            item_ids = set()
            
            for source, results in all_results.items():
                for item in results:
                    if "error" in item:
                        continue
                    
                    # Добавляем источник к каждому предмету
                    item["source"] = source
                    
                    # Используем ID предмета или его название для дедупликации
                    item_id = item.get("itemId", "") or item.get("title", "")
                    if item_id and item_id not in item_ids:
                        merged_items.append(item)
                        item_ids.add(item_id)
            
            # Ограничиваем количество результатов
            merged_items = merged_items[:limit]
            
            # Считаем статистику
            stats = {
                "total_found": sum(len(results) for results in all_results.values() 
                                if isinstance(results, list)),
                "sources_count": len(all_results),
                "unique_items": len(merged_items)
            }
            
            return {
                "query": query,
                "game": game_code,
                "total_items": len(merged_items),
                "sources": list(all_results.keys()),
                "items": merged_items,
                "stats": stats
            }
        else:
            # Возвращаем результаты по источникам без объединения
            total_items = sum(len(results) for results in all_results.values() 
                             if isinstance(results, list))
            
            return {
                "query": query,
                "game": game_code,
                "total_items": total_items,
                "sources": list(all_results.keys()),
                "items": {source: results for source, results in all_results.items()},
                "stats": {"total_found": total_items}
            }
    
    async def get_arbitrage_opportunities(
        self, 
        game_code: str,
        min_price_diff_percent: float = 5.0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Находит возможности для арбитража между разными источниками.
        
        Args:
            game_code: Код игры
            min_price_diff_percent: Минимальная разница в цене в процентах
            limit: Максимальное количество результатов
            
        Returns:
            List[Dict[str, Any]]: Список возможностей для арбитража
        """
        # Получаем популярные предметы с DMarket (основной источник)
        dmarket_provider = self.aggregator.get_provider("dmarket")
        if not dmarket_provider:
            raise TradingError(
                "Провайдер DMarket не зарегистрирован",
                ErrorType.CONFIGURATION_ERROR
            )
        
        popular_items = await dmarket_provider.get_popular_items(game_code, limit=100)
        
        # Проверяем каждый популярный предмет
        opportunities = []
        
        for item in popular_items[:min(100, len(popular_items))]:  # ограничиваем количество проверяемых предметов
            item_name = item.get("title", "")
            if not item_name:
                continue
            
            # Получаем детали предмета из всех источников
            try:
                comparison = await self.aggregator.get_price_comparison(game_code, item_name)
                
                # Проверяем возможность арбитража
                if (comparison.get("price_difference_percent") or 0) >= min_price_diff_percent:
                    opportunities.append({
                        "item_name": item_name,
                        "buy_from": comparison.get("best_source"),
                        "buy_price": comparison.get("min_price"),
                        "sell_to": next((s for s, p in comparison.get("prices", {}).items() 
                                          if p == comparison.get("max_price")), None),
                        "sell_price": comparison.get("max_price"),
                        "price_diff": comparison.get("price_difference"),
                        "price_diff_percent": comparison.get("price_difference_percent"),
                        "profit_potential": "high" if comparison.get("price_difference_percent", 0) > 15 else "medium"
                    })
                    
                    # Если достигли лимита, останавливаемся
                    if len(opportunities) >= limit:
                        break
            except Exception as e:
                logger.warning(f"Ошибка при анализе арбитража для {item_name}: {e}")
        
        # Сортируем по разнице в цене (от большей к меньшей)
        opportunities.sort(key=lambda x: x.get("price_diff_percent", 0), reverse=True)
        
        return opportunities[:limit]


# Глобальный экземпляр провайдера
_multi_source_provider: Optional[MultiSourceMarketProvider] = None


def get_multi_source_provider() -> MultiSourceMarketProvider:
    """
    Получает глобальный экземпляр расширенного провайдера данных.
    
    Returns:
        MultiSourceMarketProvider: Экземпляр расширенного провайдера данных
    """
    global _multi_source_provider
    if _multi_source_provider is None:
        _multi_source_provider = MultiSourceMarketProvider()
    
    return _multi_source_provider


async def find_arbitrage_opportunities(
    game_code: str = "a8db",  # CS2 по умолчанию
    min_price_diff: float = 5.0,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Находит возможности для арбитража между разными источниками.
    
    Args:
        game_code: Код игры
        min_price_diff: Минимальная разница в цене в процентах
        limit: Максимальное количество результатов
        
    Returns:
        List[Dict[str, Any]]: Список возможностей для арбитража
    """
    provider = get_multi_source_provider()
    return await provider.get_arbitrage_opportunities(game_code, min_price_diff, limit) 