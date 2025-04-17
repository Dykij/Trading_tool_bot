"""
Тесты для модуля multi_source_market_provider.

Тестирует основную функциональность расширенного провайдера рыночных данных
для нескольких источников.
"""

import unittest
import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

# Добавляем родительскую директорию в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.multi_source_market_provider import (
    MultiSourceMarketProvider, 
    get_multi_source_provider,
    find_arbitrage_opportunities,
    MarketItemStatistics,
    SearchResults
)


class TestMultiSourceMarketProvider(unittest.TestCase):
    """Тесты для класса MultiSourceMarketProvider."""
    
    def setUp(self):
        """Подготовка к тестам."""
        # Создаем мок для MarketDataAggregator
        self.mock_aggregator = MagicMock()
        
        # Создаем мок для провайдеров
        self.mock_dmarket_provider = AsyncMock()
        self.mock_steam_provider = AsyncMock()
        
        # Настраиваем возвращаемое значение для get_provider
        self.mock_aggregator.get_provider.side_effect = lambda source: {
            "dmarket": self.mock_dmarket_provider,
            "steam": self.mock_steam_provider
        }.get(source)
        
        # Создаем экземпляр провайдера с моком агрегатора
        self.provider = MultiSourceMarketProvider(cache_ttl=60)
        self.provider.aggregator = self.mock_aggregator
        self.provider.default_sources = ["dmarket", "steam"]
    
    def test_init(self):
        """Тест инициализации."""
        provider = MultiSourceMarketProvider(cache_ttl=120, concurrency_limit=5)
        self.assertEqual(provider.cache_ttl, 120)
        self.assertEqual(provider.default_sources, ["dmarket", "steam"])
        self.assertIsInstance(provider.semaphore, asyncio.Semaphore)
        self.assertEqual(provider.semaphore._value, 5)
    
    async def async_setup(self):
        """Асинхронная настройка тестов."""
        # Настраиваем моки для асинхронных методов
        
        # Mock для get_item_info
        self.mock_aggregator.get_item_info.return_value = {
            "dmarket": {
                "itemId": "dm_item_1",
                "title": "Test Item",
                "price": {"USD": 50.0},
                "game": "a8db"
            },
            "steam": {
                "itemId": "steam_item_1",
                "title": "Test Item",
                "price": {"USD": 55.0},
                "game": "a8db"
            }
        }
        
        # Mock для get_item_price_history
        self.mock_aggregator.get_item_price_history.return_value = {
            "dmarket": [
                {"date": "2023-07-01T00:00:00", "price": 49.0, "volume": 100},
                {"date": "2023-07-02T00:00:00", "price": 50.0, "volume": 120}
            ],
            "steam": [
                {"date": "2023-07-01T00:00:00", "price": 54.0, "volume": 80},
                {"date": "2023-07-02T00:00:00", "price": 55.0, "volume": 90}
            ]
        }
        
        # Mock для search_items
        self.mock_dmarket_provider.search_items.return_value = [
            {"itemId": "dm_item_1", "title": "Test Item 1", "price": {"USD": 50.0}},
            {"itemId": "dm_item_2", "title": "Test Item 2", "price": {"USD": 60.0}}
        ]
        
        self.mock_steam_provider.search_items.return_value = [
            {"itemId": "steam_item_1", "title": "Test Item 1", "price": {"USD": 55.0}},
            {"itemId": "steam_item_3", "title": "Test Item 3", "price": {"USD": 70.0}}
        ]
        
        # Mock для get_popular_items
        self.mock_dmarket_provider.get_popular_items.return_value = [
            {"itemId": "dm_item_1", "title": "Popular Item 1", "price": {"USD": 50.0}},
            {"itemId": "dm_item_2", "title": "Popular Item 2", "price": {"USD": 60.0}}
        ]
        
        # Mock для get_price_comparison
        self.mock_aggregator.get_price_comparison.return_value = {
            "item_name": "Popular Item 1",
            "game": "a8db",
            "prices": {
                "dmarket": 50.0,
                "steam": 55.0
            },
            "min_price": 50.0,
            "max_price": 55.0,
            "avg_price": 52.5,
            "best_source": "dmarket",
            "price_difference": 5.0,
            "price_difference_percent": 10.0
        }
    
    async def test_get_item_details(self):
        """Тест метода get_item_details."""
        await self.async_setup()
        
        # Выполняем тест
        result = await self.provider.get_item_details("a8db", "Test Item")
        
        # Проверяем вызовы методов
        self.mock_aggregator.get_item_info.assert_called_once_with(
            "a8db", "Test Item", ["dmarket", "steam"]
        )
        self.mock_aggregator.get_item_price_history.assert_called_once_with(
            "a8db", "Test Item", days=30, sources=["dmarket", "steam"]
        )
        
        # Проверяем результат
        self.assertEqual(result["item_name"], "Test Item")
        self.assertEqual(result["game"], "a8db")
        self.assertEqual(result["sources"], ["dmarket", "steam"])
        self.assertEqual(result["info"], self.mock_aggregator.get_item_info.return_value)
        self.assertEqual(result["price_history"], self.mock_aggregator.get_item_price_history.return_value)
        self.assertIn("stats", result)
        self.assertIn("timestamp", result)
        
        # Проверяем кэширование
        # Вызываем повторно - должен использоваться кэш
        self.mock_aggregator.get_item_info.reset_mock()
        self.mock_aggregator.get_item_price_history.reset_mock()
        
        result2 = await self.provider.get_item_details("a8db", "Test Item")
        
        # Проверяем, что запросы к API не выполнялись (использован кэш)
        self.mock_aggregator.get_item_info.assert_not_called()
        self.mock_aggregator.get_item_price_history.assert_not_called()
        
        # Проверяем принудительное обновление кэша
        self.mock_aggregator.get_item_info.reset_mock()
        self.mock_aggregator.get_item_price_history.reset_mock()
        
        result3 = await self.provider.get_item_details("a8db", "Test Item", force_refresh=True)
        
        # Проверяем, что запросы к API выполнялись (кэш обновлен)
        self.mock_aggregator.get_item_info.assert_called_once()
        self.mock_aggregator.get_item_price_history.assert_called_once()
    
    async def test_search_across_sources(self):
        """Тест метода search_across_sources."""
        await self.async_setup()
        
        # Тест с объединением результатов
        result = await self.provider.search_across_sources(
            "a8db", "Test", merge_results=True
        )
        
        # Проверяем вызовы методов
        self.mock_dmarket_provider.search_items.assert_called_once_with("a8db", "Test", 20)
        self.mock_steam_provider.search_items.assert_called_once_with("a8db", "Test", 20)
        
        # Проверяем результат
        self.assertEqual(result["query"], "Test")
        self.assertEqual(result["game"], "a8db")
        self.assertEqual(set(result["sources"]), {"dmarket", "steam"})
        
        # Проверяем объединение результатов
        self.assertEqual(len(result["items"]), 3)  # 3 уникальных предмета
        
        # Тест без объединения результатов
        self.mock_dmarket_provider.search_items.reset_mock()
        self.mock_steam_provider.search_items.reset_mock()
        
        result = await self.provider.search_across_sources(
            "a8db", "Test", merge_results=False
        )
        
        # Проверяем результат
        self.assertEqual(result["query"], "Test")
        self.assertEqual(result["game"], "a8db")
        self.assertEqual(set(result["sources"]), {"dmarket", "steam"})
        
        # Проверяем, что результаты не объединены
        self.assertIsInstance(result["items"], dict)
        self.assertEqual(len(result["items"]["dmarket"]), 2)
        self.assertEqual(len(result["items"]["steam"]), 2)
    
    async def test_get_arbitrage_opportunities(self):
        """Тест метода get_arbitrage_opportunities."""
        await self.async_setup()
        
        # Выполняем тест
        result = await self.provider.get_arbitrage_opportunities("a8db", 5.0, 5)
        
        # Проверяем вызовы методов
        self.mock_dmarket_provider.get_popular_items.assert_called_once_with("a8db", limit=100)
        self.mock_aggregator.get_price_comparison.assert_called_once_with(
            "a8db", "Popular Item 1"
        )
        
        # Проверяем результат
        self.assertEqual(len(result), 1)  # Одна арбитражная возможность
        opportunity = result[0]
        self.assertEqual(opportunity["item_name"], "Popular Item 1")
        self.assertEqual(opportunity["buy_from"], "dmarket")
        self.assertEqual(opportunity["buy_price"], 50.0)
        self.assertEqual(opportunity["sell_to"], "steam")
        self.assertEqual(opportunity["sell_price"], 55.0)
        self.assertEqual(opportunity["price_diff"], 5.0)
        self.assertEqual(opportunity["price_diff_percent"], 10.0)
        self.assertEqual(opportunity["profit_potential"], "medium")
    
    async def test_calculate_market_statistics(self):
        """Тест метода _calculate_market_statistics."""
        await self.async_setup()
        
        # Подготавливаем тестовые данные
        item_info = {
            "dmarket": {
                "itemId": "dm_item_1",
                "title": "Test Item",
                "price": {"USD": 50.0},
                "game": "a8db"
            },
            "steam": {
                "itemId": "steam_item_1",
                "title": "Test Item",
                "price": {"USD": 55.0},
                "game": "a8db"
            }
        }
        
        price_history = {
            "dmarket": [
                {"date": (datetime.now() - datetime.timedelta(days=10)).isoformat(), "price": 45.0},
                {"date": (datetime.now() - datetime.timedelta(days=5)).isoformat(), "price": 48.0},
                {"date": datetime.now().isoformat(), "price": 50.0}
            ],
            "steam": [
                {"date": (datetime.now() - datetime.timedelta(days=10)).isoformat(), "price": 50.0},
                {"date": (datetime.now() - datetime.timedelta(days=5)).isoformat(), "price": 52.0},
                {"date": datetime.now().isoformat(), "price": 55.0}
            ]
        }
        
        # Выполняем тест
        stats = await self.provider._calculate_market_statistics(item_info, price_history)
        
        # Проверяем результат
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats["mean_price"], 52.5)  # (50 + 55) / 2
        self.assertEqual(stats["median_price"], 52.5)  # median of [50, 55]
        self.assertEqual(stats["min_price"], 50.0)
        self.assertEqual(stats["max_price"], 55.0)
        self.assertEqual(stats["best_source"], "dmarket")
        self.assertEqual(stats["price_trend"], "up")  # цены растут
        self.assertGreaterEqual(stats["data_completeness"], 0)
        self.assertLessEqual(stats["data_completeness"], 1)
        self.assertGreaterEqual(stats["confidence_score"], 0)
        self.assertLessEqual(stats["confidence_score"], 1)


class TestGlobalFunctions(unittest.TestCase):
    """Тесты для глобальных функций модуля."""
    
    @patch('src.api.multi_source_market_provider._multi_source_provider', None)
    @patch('src.api.multi_source_market_provider.MultiSourceMarketProvider')
    def test_get_multi_source_provider(self, mock_provider_class):
        """Тест функции get_multi_source_provider."""
        # Первый вызов должен создать новый экземпляр
        provider1 = get_multi_source_provider()
        mock_provider_class.assert_called_once()
        
        # Второй вызов должен вернуть тот же экземпляр
        mock_provider_class.reset_mock()
        provider2 = get_multi_source_provider()
        mock_provider_class.assert_not_called()
        self.assertEqual(provider1, provider2)
    
    @patch('src.api.multi_source_market_provider.get_multi_source_provider')
    async def test_find_arbitrage_opportunities(self, mock_get_provider):
        """Тест функции find_arbitrage_opportunities."""
        mock_provider = AsyncMock()
        mock_get_provider.return_value = mock_provider
        mock_provider.get_arbitrage_opportunities.return_value = [
            {"item_name": "Test Item", "price_diff_percent": 10.0}
        ]
        
        # Выполняем тест
        result = await find_arbitrage_opportunities("a8db", 5.0, 10)
        
        # Проверяем вызовы
        mock_get_provider.assert_called_once()
        mock_provider.get_arbitrage_opportunities.assert_called_once_with("a8db", 5.0, 10)
        
        # Проверяем результат
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["item_name"], "Test Item")
        self.assertEqual(result[0]["price_diff_percent"], 10.0)


if __name__ == '__main__':
    unittest.main() 