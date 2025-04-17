"""
Тесты для модуля trading_facade.

Проверяет функциональность:
- RequestHandler для обработки API запросов
- TradingFacade для интеграции компонентов системы
- Методы поиска арбитражных возможностей
- Взаимодействие с API маркетплейсов
"""

import unittest
import asyncio
import os
import sys
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, List, Any

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from src.trading.trading_facade import TradingFacade, RequestHandler, RequestResult
    from src.utils.marketplace_integrator import MarketplaceIntegrator
    from src.utils.error_reporting import ErrorReporter
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    # Создаем заглушки для тестов
    class TradingFacade:
        def __init__(self, config=None):
            pass
            
    class RequestHandler:
        def __init__(self, marketplace, error_reporter=None):
            pass
            
    class RequestResult(dict):
        pass
        
    class MarketplaceIntegrator:
        pass
        
    class ErrorReporter:
        pass


def async_test(coro):
    """Декоратор для запуска асинхронных тестов."""
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


class TestRequestHandler(unittest.TestCase):
    """Тесты для класса RequestHandler."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем мок для MarketplaceIntegrator
        self.mock_marketplace = MagicMock(spec=MarketplaceIntegrator)
        
        # Создаем мок для ErrorReporter
        self.mock_error_reporter = MagicMock(spec=ErrorReporter)
        
        # Создаем RequestHandler
        self.request_handler = RequestHandler(
            marketplace=self.mock_marketplace,
            error_reporter=self.mock_error_reporter
        )
    
    @async_test
    async def test_execute_safe_success(self):
        """Тест успешного выполнения execute_safe."""
        # Создаем асинхронную мок-функцию
        mock_operation = AsyncMock(return_value={"data": "test_data"})
        
        # Вызываем execute_safe
        result = await self.request_handler.execute_safe(
            operation_name="test_operation",
            operation=mock_operation,
            arg1="test",
            arg2=123
        )
        
        # Проверяем результат
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], {"data": "test_data"})
        self.assertIsNone(result["error"])
        
        # Проверяем, что функция была вызвана с правильными аргументами
        mock_operation.assert_called_once_with(arg1="test", arg2=123)
    
    @async_test
    async def test_execute_safe_failure(self):
        """Тест обработки ошибок в execute_safe."""
        # Создаем асинхронную мок-функцию, которая выбрасывает исключение
        mock_operation = AsyncMock(side_effect=ValueError("Test error"))
        
        # Вызываем execute_safe
        result = await self.request_handler.execute_safe(
            operation_name="test_operation",
            operation=mock_operation
        )
        
        # Проверяем результат
        self.assertFalse(result["success"])
        self.assertIsNone(result["data"])
        self.assertEqual(result["error"], "Test error")
        
        # Проверяем, что отчет об ошибке был отправлен
        self.mock_error_reporter.report_error.assert_called_once()
    
    @async_test
    async def test_get_market_items(self):
        """Тест метода get_market_items."""
        # Настраиваем мок для marketplace.get_market_items
        self.mock_marketplace.get_market_items = AsyncMock(
            return_value=[{"id": "item1"}, {"id": "item2"}]
        )
        
        # Вызываем метод
        result = await self.request_handler.get_market_items(
            game_id="csgo",
            limit=10
        )
        
        # Проверяем результат
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data"]), 2)
        
        # Проверяем, что метод marketplace был вызван с правильными аргументами
        self.mock_marketplace.get_market_items.assert_called_once_with(
            game_id="csgo",
            limit=10
        )


class TestTradingFacade(unittest.TestCase):
    """Тесты для класса TradingFacade."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем тестовую конфигурацию
        self.test_config = {
            "api": {
                "dmarket": {
                    "key": "test_key",
                    "secret": "test_secret"
                },
                "steam": {
                    "key": "steam_api_key"
                }
            },
            "games": ["csgo", "dota2", "rust"],
            "trading": {
                "min_profit_percent": 10.0,
                "max_price": 200.0,
                "simulation_mode": True
            }
        }
    
    @patch('src.trading.trading_facade.MarketplaceIntegrator')
    @patch('src.trading.trading_facade.MLPredictor')
    def test_initialization(self, mock_ml_predictor, mock_marketplace_integrator):
        """Тест инициализации TradingFacade."""
        # Создаем TradingFacade
        facade = TradingFacade(config=self.test_config)
        
        # Проверяем, что необходимые компоненты были инициализированы
        mock_marketplace_integrator.assert_called_once()
        mock_ml_predictor.assert_called_once()
        
        # Проверяем, что атрибуты установлены правильно
        self.assertIsNotNone(facade.request_handler)
        self.assertEqual(facade.config, self.test_config)
    
    @patch('src.trading.trading_facade.MarketplaceIntegrator')
    @patch('src.trading.trading_facade.MLPredictor')
    @async_test
    async def test_check_connection(self, mock_ml_predictor, mock_marketplace_integrator):
        """Тест метода check_connection."""
        # Настраиваем мок
        mock_instance = mock_marketplace_integrator.return_value
        mock_instance.check_connection = AsyncMock(return_value=True)
        
        # Создаем TradingFacade
        facade = TradingFacade(config=self.test_config)
        
        # Вызываем метод
        result = await facade.check_connection()
        
        # Проверяем результат
        self.assertTrue(result)
        mock_instance.check_connection.assert_called_once()
    
    @patch('src.trading.trading_facade.MarketplaceIntegrator')
    @patch('src.trading.trading_facade.MLPredictor')
    @async_test
    async def test_get_market_items(self, mock_ml_predictor, mock_marketplace_integrator):
        """Тест метода get_market_items."""
        # Настраиваем мок
        mock_instance = mock_marketplace_integrator.return_value
        mock_instance.get_market_items = AsyncMock(
            return_value=[{"id": "item1"}, {"id": "item2"}]
        )
        
        # Создаем TradingFacade
        facade = TradingFacade(config=self.test_config)
        
        # Вызываем метод
        result = await facade.get_market_items(game_id="csgo", limit=10)
        
        # Проверяем результат
        self.assertEqual(len(result), 2)
        mock_instance.get_market_items.assert_called_once_with(
            game_id="csgo",
            limit=10
        )
    
    @patch('src.trading.trading_facade.MarketplaceIntegrator')
    @patch('src.trading.trading_facade.MLPredictor')
    @async_test
    async def test_find_arbitrage_opportunities(self, mock_ml_predictor, mock_marketplace_integrator):
        """Тест метода find_arbitrage_opportunities."""
        # Настраиваем мок
        mock_marketplace = mock_marketplace_integrator.return_value
        mock_marketplace.find_arbitrage_opportunities = AsyncMock(
            return_value=[
                {
                    "item_name": "AWP | Asiimov",
                    "buy_price": 50.0,
                    "sell_price": 60.0,
                    "profit": 10.0,
                    "profit_percent": 20.0
                }
            ]
        )
        
        # Настраиваем мок для ML предиктора
        mock_ml = mock_ml_predictor.return_value
        mock_ml.predict_price = AsyncMock(
            return_value={
                "current_price": 50.0,
                "predicted_price": 65.0,
                "confidence": 0.8
            }
        )
        
        # Создаем TradingFacade
        facade = TradingFacade(config=self.test_config)
        facade.use_ml = True  # Включаем использование ML
        
        # Вызываем метод
        result = await facade.find_arbitrage_opportunities(
            game_id="csgo",
            min_profit=10.0,
            price_from=1.0,
            price_to=100.0
        )
        
        # Проверяем результат
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["item_name"], "AWP | Asiimov")
        self.assertEqual(result[0]["profit_percent"], 20.0)
        
        # Проверяем, что метод marketplace был вызван с правильными аргументами
        mock_marketplace.find_arbitrage_opportunities.assert_called_once()
    
    @patch('src.trading.trading_facade.MarketplaceIntegrator')
    @patch('src.trading.trading_facade.MLPredictor')
    @async_test
    async def test_predict_item_price(self, mock_ml_predictor, mock_marketplace_integrator):
        """Тест метода predict_item_price."""
        # Настраиваем мок для ML предиктора
        mock_ml = mock_ml_predictor.return_value
        mock_ml.predict_price = AsyncMock(
            return_value={
                "current_price": 50.0,
                "predicted_price": 65.0,
                "confidence": 0.8
            }
        )
        
        # Создаем TradingFacade
        facade = TradingFacade(config=self.test_config)
        
        # Вызываем метод
        price = await facade.predict_item_price(item_id="item1")
        
        # Проверяем результат
        self.assertEqual(price, 65.0)
        mock_ml.predict_price.assert_called_once_with(item_id="item1")
    
    @patch('src.trading.trading_facade.MarketplaceIntegrator')
    @patch('src.trading.trading_facade.MLPredictor')
    @async_test
    async def test_execute_trade(self, mock_ml_predictor, mock_marketplace_integrator):
        """Тест метода execute_trade."""
        # Настраиваем мок
        mock_marketplace = mock_marketplace_integrator.return_value
        mock_marketplace.execute_trade = AsyncMock(
            return_value={
                "success": True,
                "transaction_id": "tx123",
                "status": "completed"
            }
        )
        
        # Создаем TradingFacade
        facade = TradingFacade(config=self.test_config)
        
        # Вызываем метод
        result = await facade.execute_trade(
            item_id="item1",
            price=50.0,
            is_buy=True
        )
        
        # Проверяем результат
        self.assertTrue(result["success"])
        self.assertEqual(result["transaction_id"], "tx123")
        
        # Проверяем, что метод marketplace был вызван с правильными аргументами
        mock_marketplace.execute_trade.assert_called_once_with(
            item_id="item1",
            price=50.0,
            is_buy=True
        )


if __name__ == '__main__':
    unittest.main() 