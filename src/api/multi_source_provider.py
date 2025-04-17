"""
Модуль для работы с различными источниками рыночных данных.

Реализует паттерн провайдера для абстрагирования доступа к разным API маркетплейсов.
Позволяет получать данные не только с DMarket, но и с других источников.
"""

import logging
import asyncio
import abc
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta

# Импорт API DMarket (основной провайдер)
from src.api.api_wrapper import DMarketAPI
from src.utils.error_handler import handle_exceptions, ErrorType, TradingError

# Настройка логирования
logger = logging.getLogger(__name__)


class MarketDataProvider(abc.ABC):
    """
    Абстрактный базовый класс для провайдеров рыночных данных.
    
    Определяет общий интерфейс для всех провайдеров, независимо от источника данных.
    """
    
    @abc.abstractmethod
    async def get_item_info(self, game_code: str, item_name: str) -> Dict[str, Any]:
        """
        Получает информацию о предмете.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            
        Returns:
            Dict[str, Any]: Информация о предмете
        """
        pass
    
    @abc.abstractmethod
    async def get_item_price_history(
        self, 
        game_code: str, 
        item_name: str, 
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Получает историю цен предмета.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            days: Количество дней истории
            
        Returns:
            List[Dict[str, Any]]: История цен
        """
        pass
    
    @abc.abstractmethod
    async def get_popular_items(
        self, 
        game_code: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получает список популярных предметов.
        
        Args:
            game_code: Код игры
            limit: Ограничение на количество предметов
            
        Returns:
            List[Dict[str, Any]]: Список популярных предметов
        """
        pass
    
    @abc.abstractmethod
    async def search_items(
        self, 
        game_code: str, 
        query: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Выполняет поиск предметов по запросу.
        
        Args:
            game_code: Код игры
            query: Поисковый запрос
            limit: Ограничение на количество результатов
            
        Returns:
            List[Dict[str, Any]]: Результаты поиска
        """
        pass


class DMarketDataProvider(MarketDataProvider):
    """
    Провайдер данных для DMarket.
    
    Реализует интерфейс провайдера данных для API DMarket.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Инициализирует провайдер данных DMarket.
        
        Args:
            api_key: API ключ DMarket
            api_secret: API секрет DMarket
        """
        self.api = DMarketAPI(api_key, api_secret)
        
    @handle_exceptions(ErrorType.API_ERROR)
    async def get_item_info(self, game_code: str, item_name: str) -> Dict[str, Any]:
        """
        Получает информацию о предмете с DMarket.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            
        Returns:
            Dict[str, Any]: Информация о предмете
        """
        try:
            # Ищем предмет по названию
            search_results = await self.api.search_items(game_code, item_name, limit=1)
            
            if not search_results:
                raise TradingError(
                    f"Предмет '{item_name}' не найден на DMarket",
                    ErrorType.DATA_ERROR
                )
            
            # Получаем дополнительную информацию о предмете
            item_info = await self.api.get_item_details(game_code, search_results[0]["itemId"])
            
            return item_info
        except Exception as e:
            logger.error(f"Ошибка получения информации о предмете с DMarket: {e}")
            raise TradingError(
                f"Ошибка получения информации о предмете: {str(e)}",
                ErrorType.API_ERROR,
                original_exception=e
            )
    
    @handle_exceptions(ErrorType.API_ERROR)
    async def get_item_price_history(
        self, 
        game_code: str, 
        item_name: str, 
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Получает историю цен предмета с DMarket.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            days: Количество дней истории
            
        Returns:
            List[Dict[str, Any]]: История цен
        """
        try:
            # Ищем предмет по названию
            search_results = await self.api.search_items(game_code, item_name, limit=1)
            
            if not search_results:
                raise TradingError(
                    f"Предмет '{item_name}' не найден на DMarket",
                    ErrorType.DATA_ERROR
                )
            
            # Получаем историю цен
            price_history = await self.api.get_price_history(
                game_code, 
                search_results[0]["itemId"], 
                days=days
            )
            
            return price_history
        except Exception as e:
            logger.error(f"Ошибка получения истории цен с DMarket: {e}")
            raise TradingError(
                f"Ошибка получения истории цен: {str(e)}",
                ErrorType.API_ERROR,
                original_exception=e
            )
    
    @handle_exceptions(ErrorType.API_ERROR)
    async def get_popular_items(
        self, 
        game_code: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получает список популярных предметов с DMarket.
        
        Args:
            game_code: Код игры
            limit: Ограничение на количество предметов
            
        Returns:
            List[Dict[str, Any]]: Список популярных предметов
        """
        try:
            # Получаем популярные предметы
            popular_items = await self.api.get_popular_items(game_code, limit=limit)
            
            return popular_items
        except Exception as e:
            logger.error(f"Ошибка получения популярных предметов с DMarket: {e}")
            raise TradingError(
                f"Ошибка получения популярных предметов: {str(e)}",
                ErrorType.API_ERROR,
                original_exception=e
            )
    
    @handle_exceptions(ErrorType.API_ERROR)
    async def search_items(
        self, 
        game_code: str, 
        query: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Выполняет поиск предметов по запросу на DMarket.
        
        Args:
            game_code: Код игры
            query: Поисковый запрос
            limit: Ограничение на количество результатов
            
        Returns:
            List[Dict[str, Any]]: Результаты поиска
        """
        try:
            # Выполняем поиск
            search_results = await self.api.search_items(game_code, query, limit=limit)
            
            return search_results
        except Exception as e:
            logger.error(f"Ошибка поиска предметов на DMarket: {e}")
            raise TradingError(
                f"Ошибка поиска предметов: {str(e)}",
                ErrorType.API_ERROR,
                original_exception=e
            )


class SteamDataProvider(MarketDataProvider):
    """
    Провайдер данных для Steam Market.
    
    Реализует интерфейс провайдера данных для API Steam Market.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Инициализирует провайдер данных Steam.
        
        Args:
            api_key: API ключ Steam (опционально)
        """
        self.api_key = api_key
        # TODO: Реализовать интеграцию с API Steam
        
    async def get_item_info(self, game_code: str, item_name: str) -> Dict[str, Any]:
        """
        Получает информацию о предмете с Steam Market.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            
        Returns:
            Dict[str, Any]: Информация о предмете
        """
        # Заглушка для демонстрации
        logger.warning("Steam API не реализован. Возвращаем тестовые данные.")
        
        return {
            "itemId": f"steam_{item_name.replace(' ', '_')}",
            "title": item_name,
            "price": {"USD": 49.99},
            "game": game_code,
            "category": "Оружие",
            "rarity": "Тайное",
            "source": "steam"
        }
    
    async def get_item_price_history(
        self, 
        game_code: str, 
        item_name: str, 
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Получает историю цен предмета с Steam Market.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            days: Количество дней истории
            
        Returns:
            List[Dict[str, Any]]: История цен
        """
        # Заглушка для демонстрации
        logger.warning("Steam API не реализован. Возвращаем тестовые данные.")
        
        # Создаем тестовые данные об истории цен
        now = datetime.now()
        base_price = 50.0
        history = []
        
        for i in range(days):
            date = now - timedelta(days=i)
            # Создаем случайное отклонение цены в пределах ±10%
            price_change = (0.9 + 0.2 * (i % 10) / 10)
            price = base_price * price_change
            
            history.append({
                "date": date.isoformat(),
                "price": price,
                "volume": 100 + i * 2,
                "game": game_code,
                "itemId": f"steam_{item_name.replace(' ', '_')}",
                "source": "steam"
            })
        
        return history
    
    async def get_popular_items(
        self, 
        game_code: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получает список популярных предметов с Steam Market.
        
        Args:
            game_code: Код игры
            limit: Ограничение на количество предметов
            
        Returns:
            List[Dict[str, Any]]: Список популярных предметов
        """
        # Заглушка для демонстрации
        logger.warning("Steam API не реализован. Возвращаем тестовые данные.")
        
        # Создаем тестовые данные о популярных предметах
        popular_items = []
        
        items = [
            "AK-47 | Redline",
            "AWP | Asiimov",
            "M4A4 | Howl",
            "Desert Eagle | Blaze",
            "Karambit | Fade"
        ]
        
        for i, item_name in enumerate(items[:min(limit, len(items))]):
            popular_items.append({
                "itemId": f"steam_{item_name.replace(' ', '_')}",
                "title": item_name,
                "price": {"USD": 50.0 + i * 10},
                "game": game_code,
                "category": "Оружие",
                "rarity": "Тайное",
                "source": "steam"
            })
        
        return popular_items
    
    async def search_items(
        self, 
        game_code: str, 
        query: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Выполняет поиск предметов по запросу на Steam Market.
        
        Args:
            game_code: Код игры
            query: Поисковый запрос
            limit: Ограничение на количество результатов
            
        Returns:
            List[Dict[str, Any]]: Результаты поиска
        """
        # Заглушка для демонстрации
        logger.warning("Steam API не реализован. Возвращаем тестовые данные.")
        
        # Создаем тестовые данные о результатах поиска
        search_results = []
        
        # Если запрос содержит ключевые слова, создаем соответствующие результаты
        if "ak" in query.lower() or "redline" in query.lower():
            search_results.append({
                "itemId": "steam_AK-47_Redline",
                "title": "AK-47 | Redline",
                "price": {"USD": 45.50},
                "game": game_code,
                "source": "steam"
            })
        
        if "awp" in query.lower() or "asiimov" in query.lower():
            search_results.append({
                "itemId": "steam_AWP_Asiimov",
                "title": "AWP | Asiimov",
                "price": {"USD": 85.75},
                "game": game_code,
                "source": "steam"
            })
        
        # Если результатов нет или запрос общий, возвращаем общие результаты
        if not search_results or query.lower() in ["", "knife", "skin"]:
            search_results = [
                {
                    "itemId": "steam_Karambit_Fade",
                    "title": "Karambit | Fade",
                    "price": {"USD": 450.00},
                    "game": game_code,
                    "source": "steam"
                },
                {
                    "itemId": "steam_M4A4_Howl",
                    "title": "M4A4 | Howl",
                    "price": {"USD": 1250.00},
                    "game": game_code,
                    "source": "steam"
                }
            ]
        
        return search_results[:limit]


class MarketDataAggregator:
    """
    Агрегатор данных с разных маркетплейсов.
    
    Объединяет данные из разных источников и предоставляет единый интерфейс.
    """
    
    def __init__(self):
        """Инициализирует агрегатор данных с разных маркетплейсов."""
        self.providers = {}
        
    def register_provider(self, source_name: str, provider: MarketDataProvider):
        """
        Регистрирует провайдер данных.
        
        Args:
            source_name: Название источника данных
            provider: Провайдер данных
        """
        self.providers[source_name] = provider
        logger.info(f"Зарегистрирован провайдер данных: {source_name}")
        
    def get_provider(self, source_name: str) -> Optional[MarketDataProvider]:
        """
        Получает провайдер данных по имени.
        
        Args:
            source_name: Название источника данных
            
        Returns:
            Optional[MarketDataProvider]: Провайдер данных или None, если не найден
        """
        return self.providers.get(source_name)
    
    async def get_item_info(
        self, 
        game_code: str, 
        item_name: str, 
        sources: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Получает информацию о предмете из разных источников.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            sources: Список источников данных (если None, используются все)
            
        Returns:
            Dict[str, Dict[str, Any]]: Информация о предмете из разных источников
        """
        result = {}
        
        # Определяем список источников
        if sources is None:
            sources = list(self.providers.keys())
        
        # Выполняем запросы ко всем источникам
        tasks = []
        for source in sources:
            provider = self.get_provider(source)
            if provider:
                task = asyncio.create_task(provider.get_item_info(game_code, item_name))
                tasks.append((source, task))
        
        # Собираем результаты
        for source, task in tasks:
            try:
                info = await task
                result[source] = info
            except Exception as e:
                logger.error(f"Ошибка получения информации о предмете из {source}: {e}")
                result[source] = {"error": str(e)}
        
        return result
    
    async def get_item_price_history(
        self, 
        game_code: str, 
        item_name: str, 
        days: int = 30,
        sources: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Получает историю цен предмета из разных источников.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            days: Количество дней истории
            sources: Список источников данных (если None, используются все)
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: История цен из разных источников
        """
        result = {}
        
        # Определяем список источников
        if sources is None:
            sources = list(self.providers.keys())
        
        # Выполняем запросы ко всем источникам
        tasks = []
        for source in sources:
            provider = self.get_provider(source)
            if provider:
                task = asyncio.create_task(provider.get_item_price_history(game_code, item_name, days))
                tasks.append((source, task))
        
        # Собираем результаты
        for source, task in tasks:
            try:
                history = await task
                result[source] = history
            except Exception as e:
                logger.error(f"Ошибка получения истории цен из {source}: {e}")
                result[source] = [{"error": str(e)}]
        
        return result
    
    async def get_price_comparison(
        self, 
        game_code: str, 
        item_name: str
    ) -> Dict[str, Any]:
        """
        Сравнивает цены на предмет из разных источников.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            
        Returns:
            Dict[str, Any]: Сравнение цен из разных источников
        """
        # Получаем информацию о предмете из всех источников
        item_info = await self.get_item_info(game_code, item_name)
        
        # Извлекаем цены из каждого источника
        prices = {}
        for source, info in item_info.items():
            if "error" in info:
                prices[source] = None
            elif "price" in info and "USD" in info["price"]:
                prices[source] = float(info["price"]["USD"])
            else:
                prices[source] = None
        
        # Находим минимальную и максимальную цены
        valid_prices = [p for p in prices.values() if p is not None]
        min_price = min(valid_prices) if valid_prices else None
        max_price = max(valid_prices) if valid_prices else None
        avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else None
        
        # Находим лучший источник для покупки
        best_source = None
        if min_price is not None:
            for source, price in prices.items():
                if price == min_price:
                    best_source = source
                    break
        
        return {
            "item_name": item_name,
            "game": game_code,
            "prices": prices,
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": avg_price,
            "best_source": best_source,
            "price_difference": max_price - min_price if min_price is not None and max_price is not None else None,
            "price_difference_percent": ((max_price / min_price) - 1) * 100 if min_price and max_price else None
        }


# Создаем глобальный экземпляр агрегатора
_aggregator: Optional[MarketDataAggregator] = None


def get_market_aggregator() -> MarketDataAggregator:
    """
    Получает глобальный экземпляр агрегатора данных.
    
    Returns:
        MarketDataAggregator: Экземпляр агрегатора данных
    """
    global _aggregator
    if _aggregator is None:
        _aggregator = MarketDataAggregator()
        
        # Регистрируем провайдеры по умолчанию
        try:
            from src.utils.secure_config import get_dmarket_api_keys
            
            # Получаем API ключи из защищенного хранилища
            dmarket_keys = get_dmarket_api_keys()
            
            # Регистрируем провайдер DMarket
            _aggregator.register_provider(
                "dmarket", 
                DMarketDataProvider(
                    api_key=dmarket_keys.get("api_key"),
                    api_secret=dmarket_keys.get("api_secret")
                )
            )
            
            # Регистрируем провайдер Steam
            _aggregator.register_provider("steam", SteamDataProvider())
            
        except Exception as e:
            logger.error(f"Ошибка инициализации провайдеров данных: {e}")
    
    return _aggregator


async def compare_prices(game_code: str, item_name: str) -> Dict[str, Any]:
    """
    Сравнивает цены на предмет из разных источников.
    
    Args:
        game_code: Код игры
        item_name: Название предмета
        
    Returns:
        Dict[str, Any]: Сравнение цен из разных источников
    """
    aggregator = get_market_aggregator()
    return await aggregator.get_price_comparison(game_code, item_name) 