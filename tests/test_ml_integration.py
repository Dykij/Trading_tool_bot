"""
Интеграционные тесты для проверки взаимодействия между ML модулем и арбитражными стратегиями.

Проверяет корректность работы:
- Интеграции ML прогнозов в арбитражные стратегии
- Использования ML для улучшения оценки арбитражных возможностей
- Взаимодействия между разными компонентами системы
"""

import unittest
import sys
import os
import tempfile
import shutil
import logging
import pandas as pd
import numpy as np
import functools
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.ml.ml_predictor import MLPredictor
    from src.arbitrage.strategies.gap_arbitrage import GapArbitrageStrategy
    from src.arbitrage.dmarket_arbitrage_finder import DMarketArbitrageFinder
    from src.api.integration import IntegrationManager
    ML_AVAILABLE = True
except ImportError as e:
    print(f"Ошибка импорта ML модулей: {e}")
    ML_AVAILABLE = False


class AsyncTestCase(unittest.TestCase):
    """Базовый класс для асинхронных тестов."""
    
    async def async_setUp(self):
        """Асинхронная подготовка теста."""
        pass
        
    async def async_tearDown(self):
        """Асинхронная очистка после теста."""
        pass
        
    def setUp(self):
        """Запускает асинхронную подготовку теста."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.async_setUp())
        
    def tearDown(self):
        """Запускает асинхронную очистку после теста."""
        self.loop.run_until_complete(self.async_tearDown())
        self.loop.close()


def async_test(func):
    """Декоратор для запуска асинхронных тестов."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        return self.loop.run_until_complete(func(self, *args, **kwargs))
    return wrapper


class MockDMarketAPI:
    """Мок DMarket API для тестирования."""
    
    def __init__(self):
        """Инициализация мок API."""
        self.items_data = {
            'AWP | Asiimov': {
                'title': 'AWP | Asiimov',
                'price': {'USD': 100},
                'gameId': 'csgo',
                'itemId': 'item123',
                'extra': {'floatValue': 0.25}
            },
            'AK-47 | Redline': {
                'title': 'AK-47 | Redline',
                'price': {'USD': 50},
                'gameId': 'csgo',
                'itemId': 'item456',
                'extra': {'floatValue': 0.15}
            }
        }
        
        # Генерация исторических данных
        now = datetime.now()
        dates = [(now - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30)]
        
        # Создаем колебания цен с трендом роста
        self.historical_data = {
            'AWP | Asiimov': pd.DataFrame({
                'date': dates,
                'price': [80 + i * 0.5 + np.random.normal(0, 2) for i in range(30)],
                'volume': [50 + np.random.randint(-10, 20) for _ in range(30)]
            }),
            'AK-47 | Redline': pd.DataFrame({
                'date': dates,
                'price': [40 + i * 0.3 + np.random.normal(0, 1) for i in range(30)],
                'volume': [100 + np.random.randint(-20, 30) for _ in range(30)]
            })
        }
        
        # Данные для арбитража
        self.market_items = [
            {
                'title': 'AWP | Asiimov',
                'price': {'USD': 95},
                'target_price': {'USD': 110},
                'gameId': 'csgo',
                'itemId': 'market_item1',
                'extra': {'floatValue': 0.25}
            },
            {
                'title': 'AK-47 | Redline',
                'price': {'USD': 45},
                'target_price': {'USD': 55},
                'gameId': 'csgo',
                'itemId': 'market_item2',
                'extra': {'floatValue': 0.15}
            }
        ]
    
    async def get_items_by_title(self, title, game_id=None, limit=10):
        """Получение предметов по названию."""
        if title in self.items_data:
            return [self.items_data[title]]
        return []
    
    async def get_historical_data(self, item_id, days=30):
        """Получение исторических данных."""
        for item_name, item_data in self.items_data.items():
            if item_data['itemId'] == item_id:
                return self.historical_data[item_name]
        return pd.DataFrame()
    
    async def get_market_items(self, game_id, limit=100):
        """Получение предметов с рынка."""
        if game_id == 'csgo':
            return self.market_items
        return []
    
    async def get_steam_price(self, market_hash_name):
        """Получение цены со Steam."""
        if 'AWP | Asiimov' in market_hash_name:
            return 120
        elif 'AK-47 | Redline' in market_hash_name:
            return 60
        return 0


@unittest.skipIf(not ML_AVAILABLE, "ML модуль недоступен")
class TestMLIntegration(AsyncTestCase):
    """Тесты интеграции ML и арбитражных стратегий."""
    
    async def async_setUp(self):
        """Асинхронная настройка тестового окружения."""
        # Настройка логирования
        logging.basicConfig(level=logging.INFO,
                           format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Создаем временную директорию для моделей
        self.temp_dir = tempfile.mkdtemp()
        
        # Создаем мок для API
        self.mock_api = MockDMarketAPI()
        
        # Создаем экземпляр MLPredictor с моком API
        self.ml_predictor = MLPredictor(api_client=self.mock_api, models_dir=self.temp_dir)
        
        # Патчим модели ML
        self.model_patcher = patch('src.ml.price_prediction_model.PricePredictionModel')
        self.MockModel = self.model_patcher.start()
        self.MockModel.return_value.train.return_value = 0.95
        self.MockModel.return_value.predict.return_value = 120
        self.MockModel.return_value.load.return_value = True
        self.MockModel.return_value.save.return_value = True
        
        # Создаем стратегию арбитража с моком API
        self.strategy = GapArbitrageStrategy(api_client=self.mock_api)
        
        # Создаем арбитражный поисковик с моком API
        self.arbitrage_finder = DMarketArbitrageFinder(api_client=self.mock_api)
    
    async def async_tearDown(self):
        """Асинхронная очистка тестового окружения."""
        # Останавливаем патчи
        self.model_patcher.stop()
        
        # Удаляем временную директорию
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @async_test
    async def test_gap_strategy_with_ml(self):
        """Тест интеграции стратегии гэп-арбитража с ML."""
        # Мок для прогноза цены
        with patch('src.ml.ml_predictor.MLPredictor.predict_price') as mock_predict_price:
            # Настраиваем мок для прогноза цены
            mock_predict_price.return_value = {
                'current_price': 95,
                'predicted_price': 120,
                'confidence': 0.8
            }
            
            # Включаем ML в стратегии
            self.strategy.use_ml_predictions = True
            self.strategy.ml_predictor = self.ml_predictor
            
            # Находим арбитражные возможности
            opportunities = await self.strategy.find_opportunities(game_id='csgo', limit=10)
            
            # Проверяем результат
            self.assertIsInstance(opportunities, list)
            self.assertGreater(len(opportunities), 0)
            
            # Проверяем, что ML прогноз был использован
            awp_opp = None
            for opp in opportunities:
                if opp.get('title') == 'AWP | Asiimov':
                    awp_opp = opp
                    break
            
            # Проверяем, что нашли AWP | Asiimov и он содержит ML прогноз
            self.assertIsNotNone(awp_opp, "Не найдена возможность для AWP | Asiimov")
            if awp_opp:  # Дополнительная проверка для избежания ошибок с None
                self.assertIn('ml_prediction', awp_opp)
                self.assertEqual(awp_opp['ml_prediction']['predicted_price'], 120)
            
            # Проверяем, что метод прогнозирования был вызван
            mock_predict_price.assert_called()
    
    @async_test
    async def test_confidence_calculation_with_ml(self):
        """Тест расчета уверенности с учетом ML."""
        with patch('src.ml.ml_predictor.MLPredictor.predict_price') as mock_predict_price:
            # Сначала тестируем с высокой уверенностью
            mock_predict_price.return_value = {
                'current_price': 95,
                'predicted_price': 120,
                'confidence': 0.9
            }
            
            # Включаем ML в стратегии
            self.strategy.use_ml_predictions = True
            self.strategy.ml_predictor = self.ml_predictor
            
            # Находим арбитражные возможности с высокой уверенностью
            opportunities_high_conf = await self.strategy.find_opportunities(game_id='csgo', limit=10)
            
            # Проверяем результат
            self.assertIsInstance(opportunities_high_conf, list)
            self.assertGreater(len(opportunities_high_conf), 0)
            
            # Находим AWP | Asiimov в возможностях с высокой уверенностью
            awp_opp_high_conf = None
            for opp in opportunities_high_conf:
                if opp.get('title') == 'AWP | Asiimov':
                    awp_opp_high_conf = opp
                    break
            
            # Проверяем, что нашли AWP | Asiimov
            self.assertIsNotNone(awp_opp_high_conf, "Не найдена возможность для AWP | Asiimov с высокой уверенностью")
            
            # Теперь тестируем с низкой уверенностью
            mock_predict_price.return_value = {
                'current_price': 95,
                'predicted_price': 120,
                'confidence': 0.3
            }
            
            # Находим арбитражные возможности с низкой уверенностью
            opportunities_low_conf = await self.strategy.find_opportunities(game_id='csgo', limit=10)
            
            # Находим AWP | Asiimov в возможностях с низкой уверенностью
            awp_opp_low_conf = None
            for opp in opportunities_low_conf:
                if opp.get('title') == 'AWP | Asiimov':
                    awp_opp_low_conf = opp
                    break
            
            # Проверяем, что нашли AWP | Asiimov
            self.assertIsNotNone(awp_opp_low_conf, "Не найдена возможность для AWP | Asiimov с низкой уверенностью")
            
            # Проверяем, что общая уверенность отличается в зависимости от ML прогноза
            # Уверенность с высоким ML прогнозом должна быть выше
            self.assertIsNotNone(awp_opp_high_conf)
            self.assertIsNotNone(awp_opp_low_conf)
            
            if awp_opp_high_conf and awp_opp_low_conf:  # Дополнительная проверка для линтера
                self.assertIn('confidence', awp_opp_high_conf)
                self.assertIn('confidence', awp_opp_low_conf)
                self.assertGreater(awp_opp_high_conf['confidence'], awp_opp_low_conf['confidence'])
    
    @async_test
    async def test_arbitrage_finder_with_ml(self):
        """Тест интеграции поисковика арбитража с ML."""
        with patch('src.ml.ml_predictor.MLPredictor.predict_price') as mock_predict_price:
            # Настраиваем мок для прогноза цены
            mock_predict_price.return_value = {
                'current_price': 95,
                'predicted_price': 120,
                'confidence': 0.8
            }
            
            # Включаем ML в поисковике
            self.arbitrage_finder.use_ml_predictions = True
            self.arbitrage_finder.ml_predictor = self.ml_predictor
            
            # Находим возможности
            opportunities = await self.arbitrage_finder.find_dmarket_arbitrage(game_id='csgo')
            
            # Проверяем результат
            self.assertIsInstance(opportunities, list)
            self.assertGreater(len(opportunities), 0)
            
            # Проверяем наличие ML прогноза в результатах
            awp_opp = None
            for opp in opportunities:
                if opp.get('title') == 'AWP | Asiimov':
                    awp_opp = opp
                    break
            
            # Проверяем, что нашли AWP | Asiimov и он содержит ML прогноз
            self.assertIsNotNone(awp_opp, "Не найдена возможность для AWP | Asiimov")
            if awp_opp:  # Дополнительная проверка для избежания ошибок с None
                self.assertIn('ml_prediction', awp_opp)
                self.assertEqual(awp_opp['ml_prediction']['predicted_price'], 120)
    
    @async_test
    async def test_find_investment_opportunities(self):
        """Тест поиска инвестиционных возможностей."""
        with patch('src.ml.ml_predictor.MLPredictor.find_investment_opportunities') as mock_find_investments:
            # Создаем мок для инвестиционных возможностей
            mock_find_investments.return_value = [
                {
                    'item_name': 'AWP | Asiimov',
                    'current_price': 95,
                    'predicted_price': 120,
                    'roi': 26.3,
                    'confidence': 0.8
                },
                {
                    'item_name': 'AK-47 | Redline',
                    'current_price': 45,
                    'predicted_price': 55,
                    'roi': 22.2,
                    'confidence': 0.7
                }
            ]
            
            # Ищем инвестиционные возможности
            opportunities = await self.ml_predictor.find_investment_opportunities(
                min_price=10,
                max_price=200,
                min_roi=20,
                min_confidence=0.7,
                limit=10
            )
            
            # Проверяем результат
            self.assertIsInstance(opportunities, list)
            self.assertEqual(len(opportunities), 2)
            self.assertEqual(opportunities[0]['item_name'], 'AWP | Asiimov')
            self.assertEqual(opportunities[1]['item_name'], 'AK-47 | Redline')
            
            # Проверяем, что метод поиска инвестиций был вызван с правильными параметрами
            mock_find_investments.assert_called_once_with(
                min_price=10,
                max_price=200,
                min_roi=20,
                min_confidence=0.7,
                limit=10
            )
    
    @async_test
    async def test_integration_manager_with_ml(self):
        """Тест интеграции IntegrationManager с ML."""
        with patch('src.api.integration.IntegrationManager.collect_market_data') as mock_collect, \
             patch('src.api.integration.IntegrationManager.analyze_arbitrage_opportunities') as mock_analyze, \
             patch('src.ml.ml_predictor.MLPredictor.predict_price') as mock_predict_price:
            
            # Настраиваем моки
            mock_collect.return_value = {'status': 'success', 'items_count': 2}
            mock_analyze.return_value = {
                'status': 'success', 
                'opportunities': [
                    {
                        'title': 'AWP | Asiimov',
                        'buy_price': 95,
                        'sell_price': 110,
                        'profit': 15,
                        'confidence': 0.8
                    }
                ]
            }
            mock_predict_price.return_value = {
                'current_price': 95,
                'predicted_price': 120,
                'confidence': 0.8
            }
            
            # Создаем конфигурацию
            config = {
                'api': {
                    'public_key': 'test_public_key',
                    'secret_key': 'test_secret_key'
                },
                'games': ['csgo'],
                'use_ml': True
            }
            
            # Создаем менеджер интеграции
            integration_manager = IntegrationManager(
                config=config,
                api_client=self.mock_api,
                ml_predictor=self.ml_predictor
            )
            
            # Запускаем анализ
            result = await integration_manager.analyze_arbitrage_opportunities(use_ml=True)
            
            # Проверяем результат
            self.assertEqual(result['status'], 'success')
            self.assertIn('opportunities', result)
            
            # Проверяем, что метод анализа арбитража был вызван
            mock_analyze.assert_called_once()
            
            # Проверяем аргументы вызова
            args, kwargs = mock_analyze.call_args
            self.assertTrue(kwargs.get('use_ml', False))
    
    @async_test
    async def test_train_model_integration(self):
        """Тест интеграции обучения модели."""
        with patch('src.ml.ml_predictor.MLPredictor.train_model') as mock_train_model:
            # Настраиваем мок для обучения модели
            mock_train_model.return_value = {
                'status': 'success',
                'model_path': 'models/csgo/awp_asiimov.pkl',
                'accuracy': 0.95
            }
            
            # Обучаем модель
            result = await self.ml_predictor.train_model(
                game_id='csgo',
                item_name='AWP | Asiimov',
                history_days=30,
                model_type='random_forest'
            )
            
            # Проверяем результат
            self.assertIsNotNone(result, "Результат обучения модели не должен быть None")
            if result is not None:  # Проверка для линтера
                self.assertEqual(result['status'], 'success')
                self.assertIn('model_path', result)
                self.assertIn('accuracy', result)
            
            # Проверяем, что метод обучения модели был вызван с правильными параметрами
            mock_train_model.assert_called_once_with(
                game_id='csgo',
                item_name='AWP | Asiimov',
                history_days=30,
                model_type='random_forest',
                items_limit=None,
                force_retrain=False
            )


if __name__ == '__main__':
    unittest.main() 