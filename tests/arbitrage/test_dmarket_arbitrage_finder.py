"""
Тесты для модуля dmarket_arbitrage_finder.

Проверяет функциональность:
- Получение и обработка данных о рынке
- Создание графа для поиска арбитража
- Поиск арбитражных возможностей
- Интеграция с ML для фильтрации и оценки результатов
"""

import unittest
import os
import sys
import json
import tempfile
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, List, Any, Optional

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from src.arbitrage.dmarket_arbitrage_finder import DMarketArbitrageFinder
    from src.arbitrage.bellman_ford import ArbitrageResult
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    # Создаем заглушки для тестов в случае ошибки импорта
    class DMarketArbitrageFinder:
        def __init__(self, api_key, api_secret=None, use_parallel=True, use_ml=False):
            pass
            
    class ArbitrageResult:
        def __init__(self, cycles=None, edges=None):
            self.negative_cycles = cycles or []
            self.edges = edges or []


def async_test(coro):
    """Декоратор для запуска асинхронных тестов."""
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


class TestDMarketArbitrageFinder(unittest.TestCase):
    """Тесты для класса DMarketArbitrageFinder."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Параметры для инициализации
        self.api_key = "test_api_key"
        self.api_secret = "test_api_secret"
        
        # Создаем mock для DMarketAPI
        self.api_patcher = patch('src.arbitrage.dmarket_arbitrage_finder.DMarketAPI')
        self.mock_api = self.api_patcher.start()
        
        # Создаем mock для SmartCache
        self.cache_patcher = patch('src.arbitrage.dmarket_arbitrage_finder.SmartCache')
        self.mock_cache = self.cache_patcher.start()
        
        # Создаем mock для MLPredictor
        self.ml_patcher = patch('src.arbitrage.dmarket_arbitrage_finder.MLPredictor')
        self.mock_ml = self.ml_patcher.start()
        
        # Создаем mock для bellman_ford функций
        self.bf_patcher = patch('src.arbitrage.dmarket_arbitrage_finder.find_arbitrage_advanced')
        self.mock_bf = self.bf_patcher.start()
        
    def tearDown(self):
        """Очистка тестового окружения."""
        # Останавливаем все patchers
        self.api_patcher.stop()
        self.cache_patcher.stop()
        self.ml_patcher.stop()
        self.bf_patcher.stop()
    
    def test_initialization(self):
        """Тест инициализации DMarketArbitrageFinder."""
        # Создаем экземпляр класса
        finder = DMarketArbitrageFinder(
            api_key=self.api_key,
            api_secret=self.api_secret,
            use_parallel=True,
            use_ml=True
        )
        
        # Проверяем, что API был инициализирован с правильными параметрами
        self.mock_api.assert_called_once_with(self.api_key, self.api_secret)
        
        # Проверяем, что параметры установлены правильно
        self.assertTrue(finder.use_parallel)
        self.assertTrue(finder.use_ml)
        
        # Проверяем, что ML предиктор был инициализирован
        self.mock_ml.assert_called_once()
    
    @async_test
    async def test_respect_rate_limit(self):
        """Тест метода _respect_rate_limit."""
        # Создаем экземпляр класса
        finder = DMarketArbitrageFinder(api_key=self.api_key)
        
        # Устанавливаем начальное время для последнего запроса
        finder.last_request_time = None
        
        # Вызываем метод и проверяем, что он не вызывает исключений
        await finder._respect_rate_limit(min_interval=0.1)
        
        # Проверяем, что last_request_time был обновлен
        self.assertIsNotNone(finder.last_request_time)
    
    @patch('asyncio.sleep')
    @async_test
    async def test_respect_rate_limit_with_delay(self, mock_sleep):
        """Тест метода _respect_rate_limit с задержкой."""
        import datetime
        
        # Создаем экземпляр класса
        finder = DMarketArbitrageFinder(api_key=self.api_key)
        
        # Устанавливаем время для последнего запроса (текущее время)
        finder.last_request_time = datetime.datetime.now()
        
        # Вызываем метод
        await finder._respect_rate_limit(min_interval=1.0)
        
        # Проверяем, что asyncio.sleep был вызван
        mock_sleep.assert_called_once()
    
    @async_test
    async def test_get_market_items(self):
        """Тест метода get_market_items."""
        # Настраиваем mock для API метода
        api_instance = self.mock_api.return_value
        api_instance.get_market_items.return_value = [
            {"itemId": "item1", "title": "AWP | Asiimov", "price": {"USD": 100}},
            {"itemId": "item2", "title": "AK-47 | Redline", "price": {"USD": 50}}
        ]
        
        # Настраиваем mock для SmartCache
        cache_instance = self.mock_cache.return_value
        cache_instance.get.return_value = None  # Нет в кэше
        
        # Создаем экземпляр класса
        finder = DMarketArbitrageFinder(api_key=self.api_key)
        
        # Вызываем метод
        result = await finder.get_market_items(
            game_id="csgo",
            limit=10,
            price_from=10.0,
            price_to=100.0
        )
        
        # Проверяем результат
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["itemId"], "item1")
        
        # Проверяем, что API метод был вызван с правильными параметрами
        api_instance.get_market_items.assert_called_once()
        call_args = api_instance.get_market_items.call_args[0][0]
        self.assertEqual(call_args["gameId"], "csgo")
        self.assertEqual(call_args["limit"], 10)
        self.assertEqual(call_args["priceFrom"], 10.0)
        self.assertEqual(call_args["priceTo"], 100.0)
    
    @async_test
    async def test_get_market_items_cached(self):
        """Тест метода get_market_items с кэшированными данными."""
        # Настраиваем mock для SmartCache
        cached_data = [
            {"itemId": "cached1", "title": "Cached Item 1", "price": {"USD": 75}},
            {"itemId": "cached2", "title": "Cached Item 2", "price": {"USD": 25}}
        ]
        cache_instance = self.mock_cache.return_value
        cache_instance.get.return_value = cached_data  # Есть в кэше
        
        # Создаем экземпляр класса
        finder = DMarketArbitrageFinder(api_key=self.api_key)
        
        # Вызываем метод
        result = await finder.get_market_items(
            game_id="csgo",
            limit=10
        )
        
        # Проверяем результат
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["itemId"], "cached1")
        
        # Проверяем, что API метод НЕ был вызван
        api_instance = self.mock_api.return_value
        api_instance.get_market_items.assert_not_called()
    
    @async_test
    async def test_find_arbitrage_opportunities(self):
        """Тест метода find_arbitrage_opportunities."""
        # Настраиваем mock для get_all_market_items
        with patch.object(DMarketArbitrageFinder, 'get_all_market_items', new_callable=AsyncMock) as mock_get_items:
            mock_get_items.return_value = [
                {"itemId": "item1", "title": "AWP | Asiimov", "price": {"USD": 100}},
                {"itemId": "item2", "title": "AK-47 | Redline", "price": {"USD": 50}}
            ]
            
            # Настраиваем mock для prepare_graph_data
            with patch.object(DMarketArbitrageFinder, 'prepare_graph_data', new_callable=AsyncMock) as mock_prepare:
                mock_prepare.return_value = {
                    "USD": {
                        "item1": {"item2": 0.5},  # Коэффициент обмена USD->item1->item2
                        "item2": {"item1": 1.9}   # Коэффициент обмена USD->item2->item1 (прибыльный)
                    }
                }
                
                # Настраиваем mock для bellman_ford.find_arbitrage_advanced
                self.mock_bf.return_value = ArbitrageResult(
                    cycles=[[("USD", "item2"), ("item2", "item1"), ("item1", "USD")]],
                    edges={
                        ("USD", "item2"): 0.02,  # Комиссия/стоимость ребра
                        ("item2", "item1"): 0.05,
                        ("item1", "USD"): 0.03
                    }
                )
                
                # Создаем экземпляр класса
                finder = DMarketArbitrageFinder(api_key=self.api_key)
                
                # Вызываем метод
                opportunities = await finder.find_arbitrage_opportunities(
                    game_id="csgo",
                    price_from=10.0,
                    price_to=100.0,
                    min_profit_percent=5.0
                )
                
                # Проверяем результат
                self.assertIsInstance(opportunities, list)
                self.assertGreater(len(opportunities), 0)
                
                # Проверяем, что методы были вызваны с правильными параметрами
                mock_get_items.assert_called_once_with(
                    game_id="csgo",
                    price_from=10.0,
                    price_to=100.0,
                    max_items=1000,
                    category=None
                )
                mock_prepare.assert_called_once()
                self.mock_bf.assert_called_once()
    
    @async_test
    async def test_prepare_graph_data_sequential(self):
        """Тест метода _prepare_graph_data_sequential."""
        # Создаем тестовые данные
        items = [
            {
                "itemId": "item1",
                "title": "AWP | Asiimov",
                "price": {"USD": 100},
                "suggestedPrice": {"USD": 95}
            },
            {
                "itemId": "item2",
                "title": "AK-47 | Redline",
                "price": {"USD": 50},
                "suggestedPrice": {"USD": 55}
            }
        ]
        
        # Создаем экземпляр класса
        finder = DMarketArbitrageFinder(api_key=self.api_key)
        
        # Вызываем метод
        graph_data = await finder._prepare_graph_data_sequential(items)
        
        # Проверяем результат
        self.assertIsInstance(graph_data, dict)
        self.assertIn("USD", graph_data)
        self.assertEqual(len(graph_data["USD"]), 2)
        self.assertIn("item1", graph_data["USD"])
        self.assertIn("item2", graph_data["USD"])
    
    @patch('src.arbitrage.dmarket_arbitrage_finder.MLPredictor')
    @async_test
    async def test_enrich_items_with_ml_predictions(self, mock_ml_predictor):
        """Тест метода _enrich_items_with_ml_predictions."""
        # Настраиваем mock для ML предиктора
        ml_instance = mock_ml_predictor.return_value
        ml_instance.predict_price.return_value = {
            "current_price": 50.0,
            "predicted_price": 65.0,
            "confidence": 0.8
        }
        
        # Создаем тестовые данные
        items = [
            {
                "itemId": "item1",
                "title": "AWP | Asiimov",
                "price": {"USD": 100}
            },
            {
                "itemId": "item2",
                "title": "AK-47 | Redline",
                "price": {"USD": 50}
            }
        ]
        
        # Создаем экземпляр класса с ML
        finder = DMarketArbitrageFinder(api_key=self.api_key, use_ml=True)
        finder.ml_predictor = ml_instance
        
        # Вызываем метод
        await finder._enrich_items_with_ml_predictions(items)
        
        # Проверяем результат
        self.assertIn("ml_prediction", items[0])
        self.assertIn("ml_prediction", items[1])
        self.assertEqual(items[0]["ml_prediction"]["predicted_price"], 65.0)
        self.assertEqual(items[0]["ml_prediction"]["confidence"], 0.8)
        
        # Проверяем, что ML предиктор был вызван для каждого предмета
        self.assertEqual(ml_instance.predict_price.call_count, 2)


if __name__ == '__main__':
    unittest.main() 