"""
Интеграционные тесты для модулей многоисточникового провайдера и трейдера.

Тестирует взаимодействие между компонентами, обеспечивая корректную работу
системы в целом.
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# Добавляем родительскую директорию в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.multi_source_market_provider import (
    get_multi_source_provider, find_arbitrage_opportunities
)
from src.api.multi_source_trading import (
    get_multi_source_trader, find_and_execute_trades, MultiSourceTrader
)
from src.api.multi_source_provider import (
    MarketDataAggregator, MarketDataProvider
)


class MockMarketDataProvider(AsyncMock):
    """Мок для провайдера данных о рынке."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Настраиваем возвращаемые значения для методов
        self.get_item_info.return_value = {
            "itemId": "test_item_1",
            "title": "Test Item 1",
            "price": {"USD": 100.0},
            "game": "a8db",
            "category": "Оружие",
            "rarity": "Тайное"
        }
        
        self.get_item_price_history.return_value = [
            {"date": datetime.now().isoformat(), "price": 100.0, "volume": 10},
            {"date": datetime.now().isoformat(), "price": 98.0, "volume": 15}
        ]
        
        self.get_popular_items.return_value = [
            {
                "itemId": "test_item_1",
                "title": "Popular Item 1",
                "price": {"USD": 100.0},
                "game": "a8db"
            },
            {
                "itemId": "test_item_2",
                "title": "Popular Item 2",
                "price": {"USD": 200.0},
                "game": "a8db"
            }
        ]
        
        self.search_items.return_value = [
            {
                "itemId": "test_item_1",
                "title": "Test Item 1",
                "price": {"USD": 100.0},
                "game": "a8db"
            }
        ]


class IntegrationTest(unittest.TestCase):
    """Интеграционные тесты для провайдера и трейдера."""
    
    def setUp(self):
        """Подготовка к тестам."""
        # Очищаем глобальные экземпляры
        import src.api.multi_source_market_provider
        import src.api.multi_source_trading
        
        src.api.multi_source_market_provider._multi_source_provider = None
        src.api.multi_source_trading._multi_source_trader = None
        
        # Создаем моки для провайдеров
        self.mock_dmarket_provider = MockMarketDataProvider()
        self.mock_steam_provider = MockMarketDataProvider()
        
        # Настраиваем различные цены для разных источников
        self.mock_dmarket_provider.get_item_info.return_value["price"]["USD"] = 100.0
        self.mock_steam_provider.get_item_info.return_value["price"]["USD"] = 110.0
        
        # Создаем мок для агрегатора
        self.mock_aggregator = MagicMock()
        self.mock_aggregator.get_provider.side_effect = lambda source: {
            "dmarket": self.mock_dmarket_provider,
            "steam": self.mock_steam_provider
        }.get(source)
        
        # Настраиваем мок для get_item_info
        self.mock_aggregator.get_item_info.return_value = {
            "dmarket": self.mock_dmarket_provider.get_item_info.return_value,
            "steam": self.mock_steam_provider.get_item_info.return_value
        }
        
        # Настраиваем мок для get_item_price_history
        self.mock_aggregator.get_item_price_history.return_value = {
            "dmarket": self.mock_dmarket_provider.get_item_price_history.return_value,
            "steam": self.mock_steam_provider.get_item_price_history.return_value
        }
        
        # Настраиваем мок для get_price_comparison
        self.mock_aggregator.get_price_comparison.return_value = {
            "item_name": "Popular Item 1",
            "game": "a8db",
            "prices": {
                "dmarket": 100.0,
                "steam": 110.0
            },
            "min_price": 100.0,
            "max_price": 110.0,
            "avg_price": 105.0,
            "best_source": "dmarket",
            "price_difference": 10.0,
            "price_difference_percent": 10.0
        }
    
    @patch('src.api.multi_source_provider.get_market_aggregator')
    @patch('src.api.multi_source_market_provider.get_market_aggregator')
    async def test_market_provider_and_trader_integration(self, mock_get_market_aggregator, mock_get_market_aggregator2):
        """Тест интеграции провайдера и трейдера."""
        # Настраиваем моки
        mock_get_market_aggregator.return_value = self.mock_aggregator
        mock_get_market_aggregator2.return_value = self.mock_aggregator
        
        # Получаем экземпляр провайдера
        provider = get_multi_source_provider()
        
        # Тестируем получение деталей о предмете
        item_details = await provider.get_item_details("a8db", "Test Item 1")
        
        # Проверяем результат
        self.assertEqual(item_details["item_name"], "Test Item 1")
        self.assertEqual(item_details["game"], "a8db")
        self.assertEqual(set(item_details["sources"]), {"dmarket", "steam"})
        self.assertIn("stats", item_details)
        
        # Тестируем поиск арбитражных возможностей
        opportunities = await find_arbitrage_opportunities("a8db", 5.0, 10)
        
        # Проверяем результат
        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0]["item_name"], "Popular Item 1")
        self.assertEqual(opportunities[0]["buy_from"], "dmarket")
        self.assertEqual(opportunities[0]["sell_to"], "steam")
        
        # Получаем экземпляр трейдера
        trader = get_multi_source_trader(min_profit_percent=5.0, auto_execute=True)
        
        # Тестируем сканирование рынка
        scan_result = await trader.scan_for_opportunities("a8db")
        
        # Проверяем результат
        self.assertEqual(len(scan_result), 1)
        self.assertEqual(scan_result[0]["item_name"], "Popular Item 1")
        self.assertIn("risk_score", scan_result[0])
        self.assertIn("risk_level", scan_result[0])
        
        # Тестируем выполнение сделки
        trade_result = await trader.execute_trade(scan_result[0])
        
        # Проверяем результат
        self.assertEqual(trade_result["item_name"], "Popular Item 1")
        self.assertEqual(trade_result["buy_source"], "dmarket")
        self.assertEqual(trade_result["sell_source"], "steam")
        self.assertEqual(trade_result["status"], "simulated")
        self.assertIsNone(trade_result["error"])
        
        # Тестируем получение статистики
        stats = await trader.get_trading_statistics()
        
        # Проверяем результат
        self.assertEqual(stats["total_trades"], 1)
        self.assertEqual(stats["successful_trades"], 1)
        self.assertEqual(stats["success_rate"], 100.0)
        
        # Тестируем интегрированную функцию поиска и выполнения сделок
        with patch('src.api.multi_source_trading.get_multi_source_trader', return_value=trader):
            # Подменяем метод _can_execute_trade, чтобы разрешить еще одну сделку
            original_can_execute = trader._can_execute_trade
            trader._can_execute_trade = lambda: True
            
            trade_results = await find_and_execute_trades(
                game_code="a8db",
                min_profit=5.0,
                max_trades=1,
                auto_execute=True
            )
            
            # Возвращаем оригинальный метод
            trader._can_execute_trade = original_can_execute
            
            # Проверяем результат
            self.assertEqual(len(trade_results), 1)
            self.assertEqual(trade_results[0]["item_name"], "Popular Item 1")
            self.assertEqual(trade_results[0]["status"], "simulated")
    
    @patch('src.api.multi_source_provider.get_market_aggregator')
    @patch('src.api.multi_source_market_provider.get_market_aggregator')
    async def test_error_handling(self, mock_get_market_aggregator, mock_get_market_aggregator2):
        """Тест обработки ошибок."""
        # Настраиваем моки
        mock_get_market_aggregator.return_value = self.mock_aggregator
        mock_get_market_aggregator2.return_value = self.mock_aggregator
        
        # Получаем экземпляры
        provider = get_multi_source_provider()
        trader = get_multi_source_trader(min_profit_percent=5.0, auto_execute=True)
        
        # Настраиваем мок для генерации ошибки
        self.mock_aggregator.get_price_comparison.side_effect = Exception("Test error")
        
        # Тестируем обработку ошибок при поиске арбитражных возможностей
        opportunities = await find_arbitrage_opportunities("a8db", 5.0, 10)
        
        # Проверяем результат - должен быть пустой список из-за ошибки
        self.assertEqual(len(opportunities), 0)
        
        # Исправляем мок
        self.mock_aggregator.get_price_comparison.side_effect = None
        self.mock_aggregator.get_price_comparison.return_value = {
            "item_name": "Popular Item 1",
            "game": "a8db",
            "prices": {
                "dmarket": 100.0,
                "steam": 110.0
            },
            "min_price": 100.0,
            "max_price": 110.0,
            "avg_price": 105.0,
            "best_source": "dmarket",
            "price_difference": 10.0,
            "price_difference_percent": 10.0
        }
        
        # Получаем возможности для следующего теста
        opportunities = await find_arbitrage_opportunities("a8db", 5.0, 10)
        
        # Настраиваем мок для генерации ошибки при проверке актуальности цены
        self.mock_aggregator.get_price_comparison.side_effect = lambda game, item: {
            "item_name": item,
            "game": game,
            "prices": {},  # Пустые цены вызовут ошибку
            "min_price": None,
            "max_price": None
        }
        
        # Тестируем обработку ошибок при выполнении сделки
        trade_result = await trader.execute_trade(opportunities[0])
        
        # Проверяем результат - должен содержать информацию об ошибке
        self.assertEqual(trade_result["status"], "failed")
        self.assertIsNotNone(trade_result["error"])


if __name__ == '__main__':
    # Для запуска тестов
    unittest.main() 