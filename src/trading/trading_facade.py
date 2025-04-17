"""
Фасад для интеграции алгоритмических модулей с API DMarket.

Этот модуль предоставляет единый интерфейс для взаимодействия между 
алгоритмическими модулями (bellman_ford, linear_programming) и API DMarket.
"""

import os
import sys
import logging
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

# Настройка логгера
logger = logging.getLogger(__name__)

# Глобальный экземпляр сервиса
_trading_service = None

class TradingFacade:
    """
    Класс-фасад, предоставляющий унифицированный интерфейс для работы 
    с торговыми API и алгоритмическими модулями.
    """
    def __init__(self):
        """Инициализация фасада."""
        self.api_wrapper = None
        self.arbitrage_manager = None
        self.cs2_scraper = None
        self.initialized = False
        
    async def initialize(self):
        """Асинхронная инициализация компонентов фасада."""
        if self.initialized:
            return
            
        logger.info("Инициализация торгового фасада...")
        
        try:
            # Инициализация API
            await self._initialize_api()
            
            # Инициализация скрапера CS2
            await self._initialize_cs2_scraper()
            
            # Импорт менеджера арбитража
            # В реальном сценарии здесь нужно будет импортировать ArbitrageManager из src.telegram.telegram_bot
            # или, что еще лучше, вынести его в отдельный модуль
            try:
                from src.telegram.telegram_bot import arbitrage_manager
                self.arbitrage_manager = arbitrage_manager
                logger.info("Успешно импортирован менеджер арбитража")
            except ImportError:
                logger.warning("Не удалось импортировать менеджер арбитража, используется локальная реализация")
            
            # Попробуем импортировать модули напрямую
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                
                # Импортируем алгоритмические модули напрямую
                try:
                    import bellman_ford
                    self.bellman_ford = bellman_ford
                    logger.info("Импортирован модуль bellman_ford")
                except ImportError:
                    logger.warning("Не удалось импортировать модуль bellman_ford")
                    self.bellman_ford = None
                    
                try:
                    import linear_programming
                    self.linear_programming = linear_programming
                    logger.info("Импортирован модуль linear_programming")
                except ImportError:
                    logger.warning("Не удалось импортировать модуль linear_programming")
                    self.linear_programming = None
            except Exception as e:
                logger.error(f"Ошибка при импорте алгоритмических модулей: {e}")
                
            self.initialized = True
            logger.info("Торговый фасад успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка при инициализации торгового фасада: {e}")
    
    async def _initialize_api(self):
        """Инициализация API-клиентов."""
        try:
            # Импортируем API-wrapper
            try:
                from src.api.api_wrapper import APIWrapper
                # Создаем экземпляр API-wrapper
                self.api_wrapper = APIWrapper()
                # Инициализируем API-wrapper
                await self.api_wrapper.initialize()
                logger.info("API-wrapper успешно инициализирован")
            except ImportError:
                logger.warning("Не удалось импортировать APIWrapper, используем заглушку")
                self.api_wrapper = DummyAPIWrapper()
        except Exception as e:
            logger.error(f"Ошибка при инициализации API: {e}")
            # Создаем заглушку для API
            self.api_wrapper = DummyAPIWrapper()
            
    async def _initialize_cs2_scraper(self):
        """Инициализация скрапера CS2."""
        try:
            # Импортируем CS2Scraper
            try:
                from src.scrapers.cs2_scraper import CS2Scraper
                # Создаем экземпляр скрапера
                self.cs2_scraper = CS2Scraper(
                    cache_ttl=3600,  # 1 час
                    request_delay=0.5,
                    max_retries=3
                )
                logger.info("Скрапер CS2 успешно инициализирован")
            except ImportError:
                logger.warning("Не удалось импортировать CS2Scraper")
                self.cs2_scraper = None
        except Exception as e:
            logger.error(f"Ошибка при инициализации скрапера CS2: {e}")
            self.cs2_scraper = None
    
    async def get_market_data(self, game_id: str) -> Dict[str, Any]:
        """
        Получает данные рынка для определенной игры.
        
        Args:
            game_id: Идентификатор игры
            
        Returns:
            Dict[str, Any]: Данные рынка в формате, пригодном для алгоритмов арбитража
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            if self.api_wrapper:
                # Получаем данные о рынке
                market_data = await self.api_wrapper.get_market_data(game_id)
                logger.info(f"Получены данные рынка для игры {game_id}")
                return market_data
            else:
                logger.warning(f"API-wrapper не инициализирован, возвращаем тестовые данные для {game_id}")
                return self._get_dummy_market_data(game_id)
        except Exception as e:
            logger.error(f"Ошибка при получении данных рынка: {e}")
            return self._get_dummy_market_data(game_id)
    
    async def get_cs2_market_data(self, category: Optional[str] = None, 
                                 limit: int = 100,
                                 min_price: Optional[float] = None,
                                 max_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Получает данные рынка CS2 с использованием скрапера.
        
        Args:
            category: Категория предметов (knife, pistol и т.д.)
            limit: Максимальное количество предметов
            min_price: Минимальная цена в USD
            max_price: Максимальная цена в USD
            
        Returns:
            Dict[str, Any]: Данные рынка CS2
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            if self.cs2_scraper:
                # Получаем данные с рынка Steam через скрапер
                items = await self.cs2_scraper.get_market_listings(
                    limit=limit,
                    category=category,
                    min_price=min_price,
                    max_price=max_price,
                    sort_by='popular'
                )
                
                if not items:
                    logger.warning("Скрапер CS2 не вернул данные, используем тестовые данные")
                    return self._get_dummy_cs2_market_data()
                
                # Преобразуем в формат, подходящий для алгоритмов
                market_data = {
                    "game_id": "cs2",
                    "timestamp": int(asyncio.get_event_loop().time()),
                    "items": []
                }
                
                for item in items:
                    processed_item = {
                        "id": item.get("id", ""),
                        "name": item.get("name", ""),
                        "price": item.get("price", 0.0),
                        "market": "Steam",
                        "category": item.get("category", "other"),
                        "image_url": item.get("image", ""),
                        "listings": item.get("listings", 0),
                        "wear": item.get("wear", "Unknown"),
                        "rarity": item.get("rarity", "Unknown"),
                        "market_url": item.get("url", "")
                    }
                    market_data["items"].append(processed_item)
                
                logger.info(f"Получено {len(market_data['items'])} предметов CS2 через скрапер")
                return market_data
            else:
                logger.warning("Скрапер CS2 не инициализирован, возвращаем тестовые данные")
                return self._get_dummy_cs2_market_data()
        except Exception as e:
            logger.error(f"Ошибка при получении данных рынка CS2: {e}")
            return self._get_dummy_cs2_market_data()
    
    async def get_cs2_item_details(self, item_name: str) -> Dict[str, Any]:
        """
        Получает детальную информацию о предмете CS2.
        
        Args:
            item_name: Название предмета
            
        Returns:
            Dict[str, Any]: Детальная информация о предмете
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            if self.cs2_scraper:
                # Получаем детальную информацию о предмете
                item_details = await self.cs2_scraper.get_item_details(item_name)
                
                if not item_details:
                    logger.warning(f"Скрапер CS2 не вернул данные для предмета '{item_name}', используем тестовые данные")
                    return {"name": item_name, "error": "Предмет не найден"}
                
                logger.info(f"Получены детальные данные для предмета CS2 '{item_name}'")
                return item_details
            else:
                logger.warning("Скрапер CS2 не инициализирован, возвращаем тестовые данные")
                return {"name": item_name, "error": "Скрапер не инициализирован"}
        except Exception as e:
            logger.error(f"Ошибка при получении деталей предмета CS2 '{item_name}': {e}")
            return {"name": item_name, "error": str(e)}
    
    async def find_arbitrage_opportunities(self, game_id: str) -> List[Dict[str, Any]]:
        """
        Ищет арбитражные возможности для определенной игры.
        
        Args:
            game_id: Идентификатор игры
            
        Returns:
            List[Dict[str, Any]]: Список арбитражных возможностей или структурированное сообщение об ошибке
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            # Получаем данные рынка
            market_data = await self.get_market_data(game_id)
            
            if not market_data or not market_data.get("items"):
                logger.error(f"Не удалось получить данные рынка для {game_id} или отсутствуют предметы")
                return [{"error": "no_market_data", "message": f"Не удалось получить данные рынка для {game_id}", "game_id": game_id}]
            
            # Проверяем, доступен ли менеджер арбитража
            if self.arbitrage_manager:
                # Используем менеджер арбитража для поиска возможностей
                try:
                    opportunities = await self.arbitrage_manager.find_all_arbitrage_opportunities(market_data)
                    logger.info(f"Найдено {len(opportunities)} арбитражных возможностей через ArbitrageManager")
                    if opportunities:
                        # Добавляем метаданные к результатам
                        for opp in opportunities:
                            opp["source"] = "arbitrage_manager"
                            opp["game_id"] = game_id
                        return opportunities
                except Exception as e:
                    error_detail = str(e)
                    logger.error(f"Ошибка при использовании ArbitrageManager: {error_detail}", exc_info=True)
                    # Продолжаем выполнение и попробуем другой метод
            
            # Если менеджер арбитража не доступен или не нашел возможностей,
            # пробуем использовать bellman_ford напрямую
            if hasattr(self, 'bellman_ford') and self.bellman_ford:
                try:
                    if hasattr(self.bellman_ford, 'find_all_arbitrage_opportunities_async'):
                        opportunities = await self.bellman_ford.find_all_arbitrage_opportunities_async(market_data)
                        logger.info(f"Найдено {len(opportunities)} арбитражных возможностей через bellman_ford")
                        if opportunities:
                            # Добавляем метаданные к результатам
                            for opp in opportunities:
                                opp["source"] = "bellman_ford"
                                opp["game_id"] = game_id
                            return opportunities
                except Exception as e:
                    error_detail = str(e)
                    logger.error(f"Ошибка при использовании bellman_ford напрямую: {error_detail}", exc_info=True)
            
            # Если не удалось использовать ни один из алгоритмов
            logger.warning("Не удалось найти арбитражные возможности, возвращаем информацию об ошибке")
            return [{"error": "no_opportunities_found", 
                    "message": "Не удалось найти арбитражные возможности ни одним из доступных методов", 
                    "game_id": game_id, 
                    "items_count": len(market_data.get("items", [])),
                    "fallback": True}]
        
        except Exception as e:
            error_detail = str(e)
            logger.error(f"Ошибка при поиске арбитражных возможностей: {error_detail}", exc_info=True)
            return [{"error": "general_error", 
                    "message": f"Произошла ошибка при поиске арбитражных возможностей: {error_detail}", 
                    "game_id": game_id}]
    
    async def find_cs2_arbitrage_opportunities(self) -> List[Dict[str, Any]]:
        """
        Ищет арбитражные возможности для CS2, используя данные из скрапера и DMarket.
        
        Returns:
            List[Dict[str, Any]]: Список арбитражных возможностей или структурированное сообщение об ошибке
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            # Получаем данные с Steam через скрапер
            steam_data = await self.get_cs2_market_data(limit=200)
            
            # Получаем данные с DMarket
            dmarket_data = await self.get_market_data("a8db")  # "a8db" - код CS2 в DMarket
            
            # Проверяем наличие данных
            steam_items_count = len(steam_data.get("items", []))
            dmarket_items_count = len(dmarket_data.get("items", []))
            
            if steam_items_count == 0 and dmarket_items_count == 0:
                logger.error("Не удалось получить данные ни из Steam, ни из DMarket")
                return [{"error": "no_market_data", 
                        "message": "Не удалось получить данные ни из Steam, ни из DMarket", 
                        "game_id": "cs2"}]
            
            # Объединяем данные для поиска арбитража
            combined_data = {
                "game_id": "cs2",
                "timestamp": int(asyncio.get_event_loop().time()),
                "items": []
            }
            
            # Добавляем данные из Steam
            for item in steam_data.get("items", []):
                combined_data["items"].append(item)
            
            # Добавляем данные из DMarket
            for item in dmarket_data.get("items", []):
                # Убедимся, что маркет указан правильно
                item["market"] = "DMarket"
                combined_data["items"].append(item)
            
            # Логируем информацию о собранных данных
            logger.info(f"Собрано {len(combined_data['items'])} предметов для анализа (Steam: {steam_items_count}, DMarket: {dmarket_items_count})")
            
            # Выполняем поиск арбитражных возможностей
            opportunities = []
            error_messages = []
            
            # Если есть менеджер арбитража, используем его
            if self.arbitrage_manager:
                try:
                    opportunities = await self.arbitrage_manager.find_all_arbitrage_opportunities(combined_data)
                    logger.info(f"Найдено {len(opportunities)} арбитражных возможностей для CS2 через ArbitrageManager")
                    if opportunities:
                        # Добавляем метаданные к результатам
                        for opp in opportunities:
                            opp["source"] = "arbitrage_manager"
                            opp["game_id"] = "cs2"
                        return opportunities
                except Exception as e:
                    error_detail = str(e)
                    error_messages.append(f"ArbitrageManager: {error_detail}")
                    logger.error(f"Ошибка при использовании ArbitrageManager для CS2: {error_detail}", exc_info=True)
            
            # Если менеджер не доступен или не нашел возможностей, используем bellman_ford
            if not opportunities and hasattr(self, 'bellman_ford') and self.bellman_ford:
                try:
                    if hasattr(self.bellman_ford, 'find_all_arbitrage_opportunities_async'):
                        opportunities = await self.bellman_ford.find_all_arbitrage_opportunities_async(combined_data)
                        logger.info(f"Найдено {len(opportunities)} арбитражных возможностей для CS2 через bellman_ford")
                        if opportunities:
                            # Добавляем метаданные к результатам
                            for opp in opportunities:
                                opp["source"] = "bellman_ford"
                                opp["game_id"] = "cs2"
                            return opportunities
                except Exception as e:
                    error_detail = str(e)
                    error_messages.append(f"Bellman-Ford: {error_detail}")
                    logger.error(f"Ошибка при использовании bellman_ford для CS2: {error_detail}", exc_info=True)
            
            # Если ничего не найдено, возвращаем структурированную информацию об ошибке
            logger.warning("Не удалось найти арбитражные возможности для CS2, возвращаем информацию об ошибке")
            return [{
                "error": "no_opportunities_found", 
                "message": "Не удалось найти арбитражные возможности для CS2", 
                "game_id": "cs2",
                "items_count": len(combined_data.get("items", [])),
                "steam_items": steam_items_count,
                "dmarket_items": dmarket_items_count,
                "error_details": error_messages if error_messages else None,
                "fallback": True
            }]
                
        except Exception as e:
            error_detail = str(e)
            logger.error(f"Ошибка при поиске арбитражных возможностей для CS2: {error_detail}", exc_info=True)
            return [{"error": "general_error", 
                    "message": f"Произошла ошибка при поиске арбитражных возможностей для CS2: {error_detail}", 
                    "game_id": "cs2"}]
    
    def _get_dummy_market_data(self, game_id: str) -> Dict[str, Any]:
        """Возвращает тестовые данные рынка."""
        return {
            "game_id": game_id,
            "timestamp": 1619099722,
            "items": [
                {"id": "item1", "name": "AWP | Asiimov", "price": 100.0, "market": "DMarket"},
                {"id": "item2", "name": "AK-47 | Redline", "price": 50.0, "market": "DMarket"},
                {"id": "item3", "name": "AWP | Asiimov", "price": 90.0, "market": "Steam"},
                {"id": "item4", "name": "AK-47 | Redline", "price": 55.0, "market": "Steam"}
            ]
        }
    
    def _get_dummy_cs2_market_data(self) -> Dict[str, Any]:
        """Возвращает тестовые данные рынка CS2."""
        return {
            "game_id": "cs2",
            "timestamp": 1619099722,
            "items": [
                {"id": "cs2_item1", "name": "AWP | Neo-Noir", "price": 120.0, "market": "Steam", "category": "sniper", "wear": "Factory New", "rarity": "Covert", "listings": 25},
                {"id": "cs2_item2", "name": "AK-47 | Slate", "price": 20.0, "market": "Steam", "category": "rifle", "wear": "Field-Tested", "rarity": "Mil-Spec", "listings": 120},
                {"id": "cs2_item3", "name": "Butterfly Knife | Doppler", "price": 1500.0, "market": "Steam", "category": "knife", "wear": "Factory New", "rarity": "Covert", "listings": 5},
                {"id": "cs2_item4", "name": "M4A4 | Desolate Space", "price": 45.0, "market": "Steam", "category": "rifle", "wear": "Minimal Wear", "rarity": "Classified", "listings": 50},
                {"id": "cs2_item5", "name": "AWP | Neo-Noir", "price": 110.0, "market": "DMarket", "category": "sniper", "wear": "Factory New", "rarity": "Covert", "listings": 12},
                {"id": "cs2_item6", "name": "AK-47 | Slate", "price": 18.0, "market": "DMarket", "category": "rifle", "wear": "Field-Tested", "rarity": "Mil-Spec", "listings": 80},
                {"id": "cs2_item7", "name": "Butterfly Knife | Doppler", "price": 1450.0, "market": "DMarket", "category": "knife", "wear": "Factory New", "rarity": "Covert", "listings": 3},
                {"id": "cs2_item8", "name": "M4A4 | Desolate Space", "price": 42.0, "market": "DMarket", "category": "rifle", "wear": "Minimal Wear", "rarity": "Classified", "listings": 35}
            ]
        }
    
    def _get_dummy_arbitrage_opportunities(self, game_id: str) -> List[Dict[str, Any]]:
        """Возвращает тестовые арбитражные возможности."""
        return [
            {
                "item_name": "AWP | Asiimov",
                "buy_market": "Steam",
                "buy_price": 90.0,
                "sell_market": "DMarket",
                "sell_price": 100.0,
                "profit_amount": 10.0,
                "profit_percent": 11.11
            },
            {
                "item_name": "AK-47 | Redline",
                "buy_market": "DMarket",
                "buy_price": 50.0,
                "sell_market": "Steam",
                "sell_price": 55.0,
                "profit_amount": 5.0,
                "profit_percent": 10.0
            }
        ]
        
    def _get_dummy_cs2_arbitrage_opportunities(self) -> List[Dict[str, Any]]:
        """Возвращает тестовые арбитражные возможности для CS2."""
        return [
            {
                "item_name": "AWP | Neo-Noir (Factory New)",
                "buy_market": "DMarket",
                "buy_price": 110.0,
                "sell_market": "Steam",
                "sell_price": 120.0,
                "profit_amount": 10.0,
                "profit_percent": 9.09,
                "category": "sniper",
                "rarity": "Covert",
                "liquidity": "Medium"
            },
            {
                "item_name": "AK-47 | Slate (Field-Tested)",
                "buy_market": "DMarket",
                "buy_price": 18.0,
                "sell_market": "Steam",
                "sell_price": 20.0,
                "profit_amount": 2.0,
                "profit_percent": 11.11,
                "category": "rifle",
                "rarity": "Mil-Spec",
                "liquidity": "High"
            },
            {
                "item_name": "M4A4 | Desolate Space (Minimal Wear)",
                "buy_market": "DMarket",
                "buy_price": 42.0,
                "sell_market": "Steam",
                "sell_price": 45.0,
                "profit_amount": 3.0,
                "profit_percent": 7.14,
                "category": "rifle",
                "rarity": "Classified",
                "liquidity": "Medium"
            }
        ]

class DummyAPIWrapper:
    """Заглушка для API-wrapper."""
    async def initialize(self):
        """Инициализация заглушки."""
        logger.info("Инициализирована заглушка для API-wrapper")
        
    async def get_market_data(self, game_id: str) -> Dict[str, Any]:
        """Возвращает тестовые данные рынка."""
        logger.info(f"Заглушка API-wrapper: запрошены данные рынка для игры {game_id}")
        return {
            "game_id": game_id,
            "timestamp": 1619099722,
            "items": [
                {"id": "item1", "name": "AWP | Asiimov", "price": 100.0, "market": "DMarket"},
                {"id": "item2", "name": "AK-47 | Redline", "price": 50.0, "market": "DMarket"},
                {"id": "item3", "name": "AWP | Asiimov", "price": 90.0, "market": "Steam"},
                {"id": "item4", "name": "AK-47 | Redline", "price": 55.0, "market": "Steam"}
            ]
        }

def get_trading_service() -> TradingFacade:
    """
    Возвращает глобальный экземпляр торгового сервиса.
    
    Returns:
        TradingFacade: Экземпляр торгового фасада
    """
    global _trading_service
    
    if _trading_service is None:
        _trading_service = TradingFacade()
        # Примечание: инициализация должна быть выполнена вызывающей стороной
        # с помощью await _trading_service.initialize()
    
    return _trading_service 