"""
Тесты для модуля машинного обучения (ML Predictor).

Проверяет функциональность модуля прогнозирования цен:
- обучение моделей
- прогнозирование цен
- поиск инвестиционных возможностей
- сезонный анализ
"""

import unittest
import sys
import os
import tempfile
import shutil
import numpy as np
import pandas as pd
from unittest import mock
from unittest.mock import patch, MagicMock, mock_open, AsyncMock
from datetime import datetime, timedelta
import random
import pytest
import matplotlib
matplotlib.use('Agg')  # Использовать не-интерактивный бэкенд для CI/CD

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Делаем ML_AVAILABLE = True для тестов
ML_AVAILABLE = True

try:
    from src.ml.ml_predictor import MLPredictor, PricePredictor, SeasonalAnalyzer, ModelManager
    from src.ml.price_prediction_model import PricePredictionModel
    from src.api.api_client import APIClient
    from src.exceptions import APIError, DataError
except ImportError:
    # Создаем заглушки для классов, если модуль не доступен
    class PricePredictionModel:
        def __init__(self, game_id=None, model_name=None, model_dir=None):
            self.game_id = game_id
            self.model_name = model_name
            self.model_dir = model_dir
            self.model = None
            
    class MLPredictor:
        def __init__(self, api_client=None, models_dir=None):
            self.api_client = api_client
            self.models_dir = models_dir
            
    class PricePredictor:
        def __init__(self, model_manager=None):
            self.model_manager = model_manager
    
    class SeasonalAnalyzer:
        def __init__(self, api_client=None):
            self.api_client = api_client
    
    class ModelManager:
        def __init__(self, models_dir=None):
            self.models_dir = models_dir


class MockDMarketAPI:
    """Мок для DMarket API."""
    
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
        result = []
        for item_name, item_data in self.items_data.items():
            if item_data['gameId'] == game_id:
                result.append(item_data)
        return result


@unittest.skipIf(not ML_AVAILABLE, "ML модуль недоступен")
class TestPricePredictionModel(unittest.TestCase):
    """Тесты для PricePredictionModel."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временную директорию для моделей
        self.temp_dir = tempfile.mkdtemp()
        
        # Создаем экземпляр модели
        self.model = PricePredictionModel(game_id='cs2', model_name='test_model', model_dir=self.temp_dir)
        
        # Тестовые данные для обучения
        self.test_data = []
        for i in range(100):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            self.test_data.append({
                'title': 'AWP | Asiimov',
                'price': 100 + i * 0.5 + np.random.normal(0, 2),
                'date': date,
                'rarity': 'Covert'
            })


@unittest.skipIf(not ML_AVAILABLE, "ML модуль недоступен")
class TestModelManager(unittest.TestCase):
    """Тесты для ModelManager."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временную директорию для моделей
        self.temp_dir = tempfile.mkdtemp()
        
        # Создаем экземпляр менеджера моделей
        self.manager = ModelManager(models_dir=self.temp_dir)
        
        # Патчим методы, которые взаимодействуют с файловой системой
        self.file_patcher = patch('builtins.open', mock_open())
        self.file_patcher.start()
        
        # Патчим os.path.exists для имитации существования файлов моделей
        self.path_exists_patcher = patch('os.path.exists', return_value=True)
        self.path_exists_patcher.start()


@unittest.skipIf(not ML_AVAILABLE, "ML модуль недоступен")
class TestMLPredictor(unittest.TestCase):
    """Тесты для MLPredictor."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временную директорию для моделей
        self.temp_dir = tempfile.mkdtemp()
        
        # Создаем мок для API
        self.mock_api = MockDMarketAPI()
        
        # Патчим методы, которые взаимодействуют с файловой системой
        self.file_patcher = patch('builtins.open', mock_open())
        self.file_patcher.start()
        
        # Патчим os.path.exists для имитации существования файлов моделей
        self.path_exists_patcher = patch('os.path.exists', return_value=True)
        self.path_exists_patcher.start()
        
        # Патчим os.makedirs для создания директорий
        self.makedirs_patcher = patch('os.makedirs')
        self.makedirs_patcher.start()
        
        # Создаем экземпляр MLPredictor с моком API
        self.predictor = MLPredictor(api_client=self.mock_api, models_dir=self.temp_dir)
    
    def tearDown(self):
        """Очистка тестового окружения."""
        # Останавливаем патчи
        self.file_patcher.stop()
        self.path_exists_patcher.stop()
        self.makedirs_patcher.stop()
        
        # Удаляем временную директорию
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.ml.price_prediction_model.PricePredictionModel.train')
    @patch('src.ml.price_prediction_model.PricePredictionModel.save')
    async def test_train_model(self, mock_save, mock_train):
        """Тест обучения модели."""
        # Устанавливаем возвращаемое значение для mock_train
        mock_train.return_value = 0.95  # R² для обученной модели
        
        # Обучаем модель
        result = await self.predictor.train_model(
            game_id='csgo',
            item_name='AWP | Asiimov',
            history_days=30,
            model_type='random_forest'
        )
        
        # Проверяем результат
        self.assertEqual(result['status'], 'success')
        self.assertIn('model_path', result)
        self.assertIn('accuracy', result)
        
        # Проверяем, что методы модели были вызваны
        mock_train.assert_called_once()
        mock_save.assert_called_once()
    
    @patch('src.ml.price_prediction_model.PricePredictionModel.predict')
    @patch('src.ml.price_prediction_model.PricePredictionModel.load')
    async def test_predict_price(self, mock_load, mock_predict):
        """Тест прогнозирования цены."""
        # Устанавливаем возвращаемое значение для mock_predict
        mock_predict.return_value = 120.0  # Прогнозируемая цена
        
        # Прогнозируем цену
        result = await self.predictor.predict_price(
            item_name='AWP | Asiimov',
            model_type='random_forest'
        )
        
        # Проверяем результат
        self.assertEqual(result['current_price'], 100)
        self.assertEqual(result['predicted_price'], 120.0)
        self.assertIn('confidence', result)
        
        # Проверяем, что методы модели были вызваны
        mock_load.assert_called_once()
        mock_predict.assert_called_once()
    
    @patch('src.ml.ml_predictor.MLPredictor.predict_price')
    async def test_find_investment_opportunities(self, mock_predict_price):
        """Тест поиска инвестиционных возможностей."""
        # Устанавливаем возвращаемое значение для mock_predict_price
        mock_predict_price.side_effect = [
            {'current_price': 100, 'predicted_price': 120, 'confidence': 0.8},
            {'current_price': 50, 'predicted_price': 55, 'confidence': 0.7}
        ]
        
        # Ищем инвестиционные возможности
        opportunities = await self.predictor.find_investment_opportunities(
            min_price=10,
            max_price=150,
            min_roi=5,
            min_confidence=0.7,
            limit=10
        )
        
        # Проверяем результат
        self.assertEqual(len(opportunities), 2)
        self.assertEqual(opportunities[0]['item_name'], 'AWP | Asiimov')
        self.assertEqual(opportunities[0]['roi'], 20)
        self.assertEqual(opportunities[1]['item_name'], 'AK-47 | Redline')
        self.assertEqual(opportunities[1]['roi'], 10)
    
    @patch('src.ml.price_prediction_model.PricePredictionModel.train')
    @patch('src.ml.price_prediction_model.PricePredictionModel.save')
    async def test_train_model_error(self, mock_save, mock_train):
        """Тест обработки ошибок при обучении модели."""
        # Устанавливаем исключение для mock_train
        mock_train.side_effect = Exception('Training error')
        
        # Обучаем модель
        result = await self.predictor.train_model(
            game_id='csgo',
            item_name='AWP | Asiimov',
            history_days=30,
            model_type='random_forest'
        )
        
        # Проверяем результат
        self.assertEqual(result['status'], 'error')
        self.assertIn('error_message', result)
    
    async def test_get_historical_data(self):
        """Тест получения исторических данных."""
        # Получаем исторические данные
        historical_data = await self.predictor.get_historical_data(
            game_id='csgo',
            item_name='AWP | Asiimov',
            days=30
        )
        
        # Проверяем результат
        self.assertIsInstance(historical_data, pd.DataFrame)
        self.assertEqual(len(historical_data), 30)
        self.assertIn('date', historical_data.columns)
        self.assertIn('price', historical_data.columns)
        self.assertIn('volume', historical_data.columns)

    @mock.patch('src.ml.ml_predictor.MLPredictor.get_historical_data')
    @mock.patch('src.api.api_client.APIClient.get_popular_items')
    async def test_detect_seasonal_events(self, mock_get_popular_items, mock_get_historical_data):
        """
        Тестирует функцию обнаружения сезонных событий и их влияния на цены
        """
        # Настраиваем мок для популярных предметов
        mock_get_popular_items.return_value = [
            {'itemId': 'item1', 'name': 'Тестовый предмет 1'},
            {'itemId': 'item2', 'name': 'Тестовый предмет 2'},
            {'itemId': 'item3', 'name': 'Тестовый предмет 3'}
        ]
        
        # Создаем тестовые данные для исторических цен
        # Имитируем данные за 12 месяцев с явным повышением цены в июне (месяц 6)
        # и снижением в ноябре (месяц 11)
        dates = pd.date_range(start='2022-01-01', end='2022-12-31', freq='D')
        prices = []
        
        for date in dates:
            # Нормальная цена около 100
            base_price = 100
            
            # Повышение на 20% в июне (летняя распродажа)
            if date.month == 6:
                price = base_price * 1.2
            # Снижение на 15% в ноябре (черная пятница)
            elif date.month == 11:
                price = base_price * 0.85
            # Повышение на 10% в марте (для CS:GO - турнир)
            elif date.month == 3:
                price = base_price * 1.1
            else:
                # Небольшой случайный шум +/- 5%
                price = base_price * (1 + (random.random() - 0.5) * 0.1)
                
            prices.append(price)
            
        test_data = pd.DataFrame({
            'timestamp': dates,
            'price': prices
        })
        
        # Настраиваем мок для исторических данных
        mock_get_historical_data.return_value = test_data
        
        # Инициализируем предиктор и вызываем метод
        predictor = MLPredictor()
        predictor.api_client = APIClient("test_key", "test_secret")
        
        result = await predictor.detect_seasonal_events('csgo', months_back=12)
        
        # Проверяем статус результата
        self.assertEqual(result['status'], 'success')
        
        # Проверяем обнаружение событий
        events = result['detected_events']
        self.assertGreater(len(events), 0, "Должны быть обнаружены сезонные события")
        
        # Проверяем, что функция правильно определила тип события (повышение или понижение)
        for event in events:
            month = event['month']
            event_type = event['type']
            
            # Проверяем соответствие месяца и типа события
            if '2022-06' in month:
                self.assertEqual(event_type, 'price_increase', 
                                "Июнь должен быть определен как повышение цены")
            elif '2022-11' in month:
                self.assertEqual(event_type, 'price_decrease', 
                                "Ноябрь должен быть определен как снижение цены")
        
        # Проверяем, что функция определяет названия событий
        event_names = [event['event_name'] for event in events]
        self.assertTrue(any('Summer Sale' in name for name in event_names), 
                      "Летняя распродажа должна быть в списке событий")
        self.assertTrue(any('Black Friday' in name for name in event_names),
                      "Черная пятница должна быть в списке событий")
                      
        # Проверяем обработку ошибок при некорректных данных
        # Тест с отсутствием популярных предметов
        mock_get_popular_items.return_value = []
        result_no_items = await predictor.detect_seasonal_events('csgo')
        self.assertEqual(result_no_items['status'], 'error')
        
        # Тест с ошибкой API
        mock_get_popular_items.side_effect = APIError("Тестовая ошибка API")
        with self.assertRaises(DataError):
            await predictor.detect_seasonal_events('csgo')
            
    @mock.patch('src.ml.ml_predictor.MLPredictor.get_historical_data')
    @mock.patch('src.api.api_client.APIClient.get_popular_items')
    async def test_get_event_name_by_month(self, mock_get_popular_items, mock_get_historical_data):
        """
        Тестирует функцию определения названия события по месяцу
        """
        predictor = MLPredictor()
        
        # Проверяем общие события для всех игр
        self.assertEqual(predictor._get_event_name_by_month(1, 'any_game'), "New Year Sales")
        self.assertEqual(predictor._get_event_name_by_month(12, 'any_game'), "Winter Sale / Christmas")
        
        # Проверяем специфичные события для CS:GO
        self.assertEqual(predictor._get_event_name_by_month(3, 'csgo'), "Major Tournament")
        self.assertEqual(predictor._get_event_name_by_month(8, 'csgo'), "Major Tournament")
        
        # Проверяем специфичные события для Dota 2
        self.assertEqual(predictor._get_event_name_by_month(5, 'dota2'), "International Battle Pass")
        self.assertEqual(predictor._get_event_name_by_month(8, 'dota2'), "The International")
        
        # Проверяем специфичные события для Rust
        self.assertEqual(predictor._get_event_name_by_month(4, 'rust'), "Spring Update")
        self.assertEqual(predictor._get_event_name_by_month(12, 'rust'), "Christmas Event")
        
        # Проверяем неизвестные месяцы
        self.assertEqual(predictor._get_event_name_by_month(9, 'any_game'), "Unknown event")

    @pytest.mark.asyncio
    async def test_visualize_seasonal_events(self):
        """Тест метода visualize_seasonal_events для создания визуализации сезонных событий"""
        # Создаем временную директорию для сохранения отчета
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создаем экземпляр MLPredictor с мок API клиентом
            api_client = MagicMock()
            ml_predictor = MLPredictor(api_client=api_client)
            
            # Мокируем метод detect_seasonal_events
            detect_mock = AsyncMock()
            detect_mock.return_value = {
                "status": "success",
                "detected_events": [
                    {
                        "month": "2023-12", 
                        "type": "price_increase", 
                        "event_name": "Рождественское событие", 
                        "confidence": 85
                    },
                    {
                        "month": "2023-08", 
                        "type": "price_increase", 
                        "event_name": "Мейджор турнир", 
                        "confidence": 78
                    }
                ],
                "confidence_level": 81.5,
                "months_analyzed": 24,
                "items_analyzed": 5
            }
            ml_predictor.detect_seasonal_events = detect_mock
            
            # Мокируем метод get_historical_data
            historical_data_mock = AsyncMock()
            
            # Создаем данные с сезонными паттернами для тестирования
            dates = pd.date_range(start='2022-01-01', end='2023-12-31', freq='D')
            prices = []
            
            # Генерируем цены с сезонными паттернами
            for date in dates:
                # Базовая цена
                price = 100
                
                # Добавляем сезонный компонент (выше в декабре, августе)
                if date.month == 12:  # Декабрь
                    price += 30
                elif date.month == 8:  # Август
                    price += 20
                
                # Добавляем небольшую случайность
                price += np.random.normal(0, 5)
                prices.append(price)
            
            df = pd.DataFrame({
                'timestamp': dates,
                'price': prices
            })
            
            historical_data_mock.return_value = df
            ml_predictor.get_historical_data = historical_data_mock
            
            # Мокируем метод get_popular_items
            api_client.get_popular_items = AsyncMock()
            api_client.get_popular_items.return_value = [
                {'itemId': '12345', 'name': 'AWP | Dragon Lore'}
            ]
            
            # Определяем выходной путь во временной директории
            output_path = os.path.join(temp_dir, "test_seasonal_events.png")
            
            # Вызываем тестируемый метод
            result_path = await ml_predictor.visualize_seasonal_events('csgo', months_back=24, output_path=output_path)
            
            # Проверяем результаты
            assert result_path == output_path
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0  # Файл не пустой
            
            # Проверяем, что мок методы были вызваны с правильными параметрами
            detect_mock.assert_called_once_with('csgo', 24)
            api_client.get_popular_items.assert_called_once_with('csgo', limit=5)
            historical_data_mock.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_visualize_seasonal_events_errors(self):
        """Тест обработки ошибок в методе visualize_seasonal_events"""
        # Создаем экземпляр MLPredictor с мок API клиентом
        api_client = MagicMock()
        ml_predictor = MLPredictor(api_client=api_client)
        
        # Тест 1: Ошибка в detect_seasonal_events
        with patch.object(ml_predictor, 'detect_seasonal_events', new_callable=AsyncMock) as detect_mock:
            detect_mock.return_value = {
                "status": "error",
                "message": "API клиент не инициализирован"
            }
            
            with pytest.raises(DataError) as excinfo:
                await ml_predictor.visualize_seasonal_events('csgo')
            
            assert "Ошибка получения данных о сезонных событиях" in str(excinfo.value)
        
        # Тест 2: API ошибка при получении популярных предметов
        with patch.object(ml_predictor, 'detect_seasonal_events', new_callable=AsyncMock) as detect_mock:
            detect_mock.return_value = {
                "status": "success",
                "detected_events": [],
                "confidence_level": 0,
                "months_analyzed": 0,
                "items_analyzed": 0
            }
            
            api_client.get_popular_items = AsyncMock()
            api_client.get_popular_items.return_value = []
            
            with pytest.raises(DataError) as excinfo:
                await ml_predictor.visualize_seasonal_events('csgo')
            
            assert "Нет популярных предметов для игры" in str(excinfo.value)
        
        # Тест 3: Нет исторических данных
        with patch.object(ml_predictor, 'detect_seasonal_events', new_callable=AsyncMock) as detect_mock:
            detect_mock.return_value = {
                "status": "success",
                "detected_events": [],
                "confidence_level": 0,
                "months_analyzed": 0,
                "items_analyzed": 0
            }
            
            api_client.get_popular_items = AsyncMock()
            api_client.get_popular_items.return_value = [
                {'itemId': '12345', 'name': 'AWP | Dragon Lore'}
            ]
            
            ml_predictor.get_historical_data = AsyncMock()
            ml_predictor.get_historical_data.return_value = pd.DataFrame()  # Пустой датафрейм
            
            with pytest.raises(DataError) as excinfo:
                await ml_predictor.visualize_seasonal_events('csgo')
            
            assert "Нет исторических данных для предмета" in str(excinfo.value)


@unittest.skipIf(not ML_AVAILABLE, "ML модуль недоступен")
class TestPricePredictor(unittest.TestCase):
    """Тесты для PricePredictor."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временную директорию для моделей
        self.temp_dir = tempfile.mkdtemp()
        
        # Создаем мок для ModelManager
        self.mock_model_manager = MagicMock(spec=ModelManager)
        
        # Создаем экземпляр PricePredictor с моком ModelManager
        self.price_predictor = PricePredictor(model_manager=self.mock_model_manager)
        
        # Создаем тестовые данные
        self.test_data = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=30),
            'price': np.random.normal(100, 10, 30),
            'volume': np.random.randint(10, 100, 30)
        })
    
    def tearDown(self):
        """Очистка тестового окружения."""
        # Удаляем временную директорию
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_prepare_features(self):
        """Тест подготовки признаков."""
        # Подготавливаем признаки
        X, y = self.price_predictor.prepare_features(self.test_data)
        
        # Проверяем результат
        self.assertIsInstance(X, pd.DataFrame)
        self.assertIsInstance(y, pd.Series)
        self.assertEqual(len(X), len(self.test_data) - 10)  # -10 из-за окна
        self.assertEqual(len(y), len(self.test_data) - 10)  # -10 из-за окна
    
    def test_calculate_confidence(self):
        """Тест расчета уверенности."""
        # Рассчитываем уверенность для разных моделей
        conf_high = self.price_predictor.calculate_confidence(r2_score=0.9, mape=5.0)
        conf_medium = self.price_predictor.calculate_confidence(r2_score=0.7, mape=10.0)
        conf_low = self.price_predictor.calculate_confidence(r2_score=0.5, mape=20.0)
        
        # Проверяем результат
        self.assertGreater(conf_high, conf_medium)
        self.assertGreater(conf_medium, conf_low)
        self.assertLessEqual(conf_high, 1.0)
        self.assertGreaterEqual(conf_low, 0.0)
    
    def test_predict_with_model(self):
        """Тест прогнозирования с моделью."""
        # Создаем мок для модели
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([120.0])
        
        # Создаем признаки
        features = pd.DataFrame({'feature1': [1.0], 'feature2': [2.0]})
        
        # Прогнозируем с моделью
        prediction = self.price_predictor.predict_with_model(mock_model, features)
        
        # Проверяем результат
        self.assertEqual(prediction, 120.0)
        mock_model.predict.assert_called_once()


@unittest.skipIf(not ML_AVAILABLE, "ML модуль недоступен")
class TestSeasonalAnalyzer(unittest.TestCase):
    """Тесты для SeasonalAnalyzer."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем мок для API
        self.mock_api = MockDMarketAPI()
        
        # Создаем экземпляр SeasonalAnalyzer с моком API
        self.seasonal_analyzer = SeasonalAnalyzer(api_client=self.mock_api)
        
        # Создаем тестовые данные с сезонностью
        # Симулируем рост в выходные дни
        dates = pd.date_range(start='2023-01-01', periods=90)
        prices = []
        for date in dates:
            base_price = 100
            # Добавляем недельную сезонность (выше в выходные)
            if date.dayofweek >= 5:  # 5 и 6 - суббота и воскресенье
                base_price += 20
            # Добавляем месячную сезонность (пик в середине месяца)
            monthly_effect = 10 * np.sin(2 * np.pi * date.day / 30)
            # Добавляем тренд и шум
            price = base_price + monthly_effect + 0.2 * date.day_of_year + np.random.normal(0, 2)
            prices.append(price)
        
        self.test_data = pd.DataFrame({
            'date': dates,
            'price': prices,
            'volume': np.random.randint(10, 100, 90)
        })
    
    async def test_analyze_weekly_patterns(self):
        """Тест анализа недельных паттернов."""
        # Проводим анализ недельных паттернов
        patterns = await self.seasonal_analyzer.analyze_weekly_patterns(self.test_data)
        
        # Проверяем результат
        self.assertIsInstance(patterns, dict)
        self.assertEqual(len(patterns), 7)  # По одному значению на каждый день недели
        
        # Проверяем, что выходные дни имеют более высокие значения
        weekday_avg = (patterns.get(0, 0) + patterns.get(1, 0) + patterns.get(2, 0) + 
                       patterns.get(3, 0) + patterns.get(4, 0)) / 5
        weekend_avg = (patterns.get(5, 0) + patterns.get(6, 0)) / 2
        
        self.assertGreater(weekend_avg, weekday_avg)
    
    async def test_analyze_monthly_patterns(self):
        """Тест анализа месячных паттернов."""
        # Проводим анализ месячных паттернов
        patterns = await self.seasonal_analyzer.analyze_monthly_patterns(self.test_data)
        
        # Проверяем результат
        self.assertIsInstance(patterns, dict)
        self.assertGreaterEqual(len(patterns), 28)  # Как минимум 28 дней в месяце
        
        # Проверяем наличие пика в середине месяца
        mid_month_avg = (patterns.get(14, 0) + patterns.get(15, 0) + patterns.get(16, 0)) / 3
        early_month_avg = (patterns.get(1, 0) + patterns.get(2, 0) + patterns.get(3, 0)) / 3
        
        self.assertNotEqual(mid_month_avg, early_month_avg)
    
    async def test_find_best_time_to_buy(self):
        """Тест поиска лучшего времени для покупки."""
        # Ищем лучшее время для покупки
        best_time = await self.seasonal_analyzer.find_best_time_to_buy(
            game_id='csgo',
            item_name='AWP | Asiimov'
        )
        
        # Проверяем результат
        self.assertIsInstance(best_time, dict)
        self.assertIn('best_day_of_week', best_time)
        self.assertIn('best_day_of_month', best_time)


if __name__ == '__main__':
    unittest.main() 