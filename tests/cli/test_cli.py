"""
Тесты для модуля CLI (Command Line Interface).

Проверяет функциональность командной строки для различных команд:
- запуск торгового бота
- анализ возможностей арбитража
- обучение моделей машинного обучения
- прогнозирование цен
- поиск инвестиционных возможностей
"""

import unittest
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open, AsyncMock
from io import StringIO
import asyncio

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from src.cli.cli import parse_args, save_result_to_file, get_api_keys, main
    from src.api.integration import IntegrationManager
    CLI_AVAILABLE = True
except ImportError:
    CLI_AVAILABLE = False


@unittest.skipIf(not CLI_AVAILABLE, "CLI модуль недоступен")
class TestCLI(unittest.TestCase):
    """Тесты для CLI интерфейса."""
    
    def setUp(self):
        """Настройка перед каждым тестом."""
        # Создаем временные файлы для тестов
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir.name)
        
        # Создаем файл с API ключами для тестов
        self.api_keys_file = os.path.join(self.temp_dir.name, 'api_keys.json')
        with open(self.api_keys_file, 'w') as f:
            json.dump({'dmarket': {'key': 'test_key', 'secret': 'test_secret'}}, f)
        
        # Патчим классы для создания моков
        self.integration_patcher = patch('src.cli.cli.IntegrationManager')
        self.ml_predictor_patcher = patch('src.cli.cli.MLPredictor')
        
        # Получаем мок классы
        self.mock_integration_class = self.integration_patcher.start()
        self.mock_ml_predictor_class = self.ml_predictor_patcher.start()
        
        # Создаем мок объекты для методов
        self.mock_integration_manager = MagicMock()
        self.mock_ml_predictor = MagicMock()
        
        # Настраиваем классы для возврата мок-объектов при создании экземпляров
        self.mock_integration_class.return_value = self.mock_integration_manager
        self.mock_ml_predictor_class.return_value = self.mock_ml_predictor
        
        # Настраиваем async методы на возвращение awaitable объектов
        self.mock_integration_manager.run_trading_bot_workflow = AsyncMock()
        self.mock_integration_manager.analyze_arbitrage_opportunities = AsyncMock()
        self.mock_ml_predictor.train_model = AsyncMock()
        self.mock_ml_predictor.predict_price = AsyncMock()
        self.mock_ml_predictor.find_investment_opportunities = AsyncMock()
        
        # Сохраняем оригинальные аргументы командной строки
        self.original_argv = sys.argv
    
    def tearDown(self):
        """Очистка после каждого теста."""
        # Останавливаем патчеры
        self.integration_patcher.stop()
        self.ml_predictor_patcher.stop()
        
        # Удаляем временные файлы
        if hasattr(self, 'temp_file') and os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
        
        if hasattr(self, 'api_keys_file') and os.path.exists(self.api_keys_file):
            os.unlink(self.api_keys_file)
            
        if hasattr(self, 'temp_dir'):
            self.temp_dir.cleanup()
        
        # Восстанавливаем оригинальные аргументы командной строки
        sys.argv = self.original_argv
    
    async def asyncSetUp(self):
        self.setUp()
        
    async def asyncTearDown(self):
        self.tearDown()
    
    def test_parse_args_run_command(self):
        """Тест парсинга аргументов для команды run."""
        # Устанавливаем аргументы командной строки
        sys.argv = ['cli.py', 'run', '--game', 'csgo', '--budget', '100', '--interval', '10']
        
        # Парсим аргументы
        args = parse_args()
        
        # Проверяем результаты
        self.assertEqual(args.command, 'run')
        self.assertEqual(args.game, 'csgo')
        self.assertEqual(args.budget, 100)
        self.assertEqual(args.interval, 10)
        self.assertFalse(args.use_ml)
    
    def test_parse_args_analyze_command(self):
        """Тест парсинга аргументов для команды analyze."""
        # Устанавливаем аргументы командной строки
        sys.argv = ['cli.py', 'analyze', '--game', 'csgo', '--min-profit', '5', '--output', 'results.json']
        
        # Парсим аргументы
        args = parse_args()
        
        # Проверяем результаты
        self.assertEqual(args.command, 'analyze')
        self.assertEqual(args.game, 'csgo')
        self.assertEqual(args.min_profit, 5)
        self.assertEqual(args.output, 'results.json')
        self.assertFalse(args.use_ml)
    
    def test_parse_args_train_command(self):
        """Тест парсинга аргументов для команды train."""
        # Устанавливаем аргументы командной строки
        sys.argv = ['cli.py', 'train', '--game', 'csgo', '--item', 'AWP | Asiimov', '--days', '30', '--model-type', 'random_forest']
        
        # Парсим аргументы
        args = parse_args()
        
        # Проверяем результаты
        self.assertEqual(args.command, 'train')
        self.assertEqual(args.game, 'csgo')
        self.assertEqual(args.item, 'AWP | Asiimov')
        self.assertEqual(args.days, 30)
        self.assertEqual(args.model_type, 'random_forest')
        self.assertFalse(args.force_retrain)
    
    def test_parse_args_predict_command(self):
        """Тест парсинга аргументов для команды predict."""
        # Устанавливаем аргументы командной строки
        sys.argv = ['cli.py', 'predict', '--item', 'AWP | Asiimov', '--model', 'random_forest']
        
        # Парсим аргументы
        args = parse_args()
        
        # Проверяем результаты
        self.assertEqual(args.command, 'predict')
        self.assertEqual(args.item, 'AWP | Asiimov')
        self.assertEqual(args.model, 'random_forest')
    
    def test_parse_args_invest_command(self):
        """Тест парсинга аргументов для команды invest."""
        # Устанавливаем аргументы командной строки
        sys.argv = ['cli.py', 'invest', '--min-price', '10', '--max-price', '100', '--min-roi', '5', '--min-confidence', '0.7', '--limit', '10']
        
        # Парсим аргументы
        args = parse_args()
        
        # Проверяем результаты
        self.assertEqual(args.command, 'invest')
        self.assertEqual(args.min_price, 10)
        self.assertEqual(args.max_price, 100)
        self.assertEqual(args.min_roi, 5)
        self.assertEqual(args.min_confidence, 0.7)
        self.assertEqual(args.limit, 10)
    
    def test_save_result_to_file(self):
        """Тест сохранения результата в файл."""
        # Данные для сохранения
        result = {'status': 'success', 'data': [1, 2, 3]}
        
        # Сохраняем результат
        save_result_to_file(result, self.temp_file.name)
        
        # Проверяем содержимое файла
        with open(self.temp_file.name, 'r') as f:
            saved_data = json.load(f)
        
        # Проверяем результаты
        self.assertEqual(saved_data, result)
    
    def test_get_api_keys(self):
        """Тест получения API ключей."""
        # Получаем ключи
        keys = get_api_keys(self.api_keys_file)
        
        # Проверяем результаты
        self.assertEqual(keys['public_key'], 'test_key')
        self.assertEqual(keys['secret_key'], 'test_secret')
    
    def test_get_api_keys_file_not_found(self):
        """Тест получения API ключей, когда файл не найден."""
        # Проверяем, что вызывается исключение, если файл не существует
        with self.assertRaises(FileNotFoundError):
            get_api_keys('nonexistent_file.json')
    
    @patch('sys.stdout', new_callable=StringIO)
    @patch('sys.argv', ['cli.py', 'run', '--api-keys', self.api_keys_file, '--timeout', '10'])
    async def test_main_run_command(self, mock_stdout):
        """Test for 'run' command."""
        # Подготовка
        sys.argv = ['cli.py', 'run', '--api-keys', self.api_keys_file.name, '--timeout', '10']
        
        # Вызов
        await main()
        
        # Проверка
        self.mock_integration_manager.run_trading_bot_workflow.assert_called_once()
        # Проверяем, что метод был вызван с корректными аргументами
        call_args = self.mock_integration_manager.run_trading_bot_workflow.call_args[1]
        self.assertEqual(call_args.get('timeout', None), 10)
        self.assertEqual(call_args.get('use_ml', None), False)
        
        # Проверяем результат
        output = mock_stdout.getvalue()
        self.assertIn("Trading bot run completed", output)
        self.assertIn("Executed trades: 1", output)
        self.assertIn("Total profit: 10.5", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    async def test_main_analyze_command(self, mock_stdout):
        """Test for 'analyze' command."""
        # Подготовка
        sys.argv = ['cli.py', 'analyze', '--api-keys', self.api_keys_file.name, '--game', 'csgo', '--limit', '5']
        
        # Устанавливаем ожидаемый результат для analyze_arbitrage_opportunities
        mock_result = [
            {'item_name': 'AWP | Asiimov', 'buy_price': 50.0, 'sell_price': 55.0, 'profit': 5.0},
            {'item_name': 'AK-47 | Redline', 'buy_price': 20.0, 'sell_price': 22.0, 'profit': 2.0}
        ]
        self.mock_integration_manager.analyze_arbitrage_opportunities.return_value = mock_result
        
        # Вызов
        await main()
        
        # Проверка
        self.mock_integration_manager.analyze_arbitrage_opportunities.assert_called_once()
        call_args = self.mock_integration_manager.analyze_arbitrage_opportunities.call_args[1]
        self.assertEqual(call_args.get('game', None), 'csgo')
        self.assertEqual(call_args.get('limit', None), 5)
        self.assertEqual(call_args.get('use_ml', None), False)
        
        # Проверяем результат
        output = mock_stdout.getvalue()
        self.assertIn("Found 2 arbitrage opportunities", output)
        self.assertIn("AWP | Asiimov", output)
        self.assertIn("Profit: 5.0", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    async def test_main_train_command(self, mock_stdout):
        """Test for 'train' command."""
        # Подготовка
        sys.argv = ['cli.py', 'train', '--api-keys', self.api_keys_file.name, '--game', 'csgo', 
                    '--item', 'AWP | Asiimov', '--days', '30', '--model-type', 'linear']
        
        # Устанавливаем ожидаемый результат для train_model
        mock_result = {'status': 'success', 'accuracy': 0.87, 'model_path': '/path/to/model.pkl'}
        self.mock_ml_predictor.train_model.return_value = mock_result
        
        # Вызов
        await main()
        
        # Проверка
        self.mock_ml_predictor.train_model.assert_called_once()
        call_args = self.mock_ml_predictor.train_model.call_args[1]
        self.assertEqual(call_args.get('game_id', None), 'csgo')
        self.assertEqual(call_args.get('model_name', None), 'AWP | Asiimov')
        self.assertEqual(call_args.get('model_type', None), 'linear')
        self.assertEqual(call_args.get('history_days', None), 30)
        
        # Проверяем результат
        output = mock_stdout.getvalue()
        self.assertIn("Model trained successfully!", output)
        self.assertIn("Accuracy: 0.87", output)
        self.assertIn("Model saved to: /path/to/model.pkl", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    async def test_main_predict_command(self, mock_stdout):
        """Test for 'predict' command."""
        # Подготовка
        sys.argv = ['cli.py', 'predict', '--api-keys', self.api_keys_file.name, '--item', 'AWP | Asiimov', 
                    '--game', 'csgo', '--model-type', 'linear']
        
        # Устанавливаем ожидаемый результат для predict_price
        mock_result = {
            'item_name': 'AWP | Asiimov',
            'current_price': 50.0,
            'predicted_price': 55.0,
            'confidence': 0.85,
            'prediction_date': '2023-04-15'
        }
        self.mock_ml_predictor.predict_price.return_value = mock_result
        
        # Вызов
        await main()
        
        # Проверка
        self.mock_ml_predictor.predict_price.assert_called_once()
        call_args = self.mock_ml_predictor.predict_price.call_args[1]
        self.assertEqual(call_args.get('game_id', None), 'csgo')
        self.assertEqual(call_args.get('item_name', None), 'AWP | Asiimov')
        self.assertEqual(call_args.get('model_type', None), 'linear')
        
        # Проверяем результат
        output = mock_stdout.getvalue()
        self.assertIn("Price prediction for AWP | Asiimov", output)
        self.assertIn("Current price: $50.00", output)
        self.assertIn("Predicted price: $55.00", output)
        self.assertIn("Confidence: 85%", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    async def test_main_invest_command(self, mock_stdout):
        """Test for 'invest' command."""
        # Подготовка
        sys.argv = ['cli.py', 'invest', '--api-keys', self.api_keys_file.name, '--game', 'csgo',
                   '--min-price', '10', '--max-price', '100', '--min-roi', '5', '--limit', '5']
        
        # Устанавливаем ожидаемый результат для find_investment_opportunities
        mock_result = [
            {
                'item_name': 'AWP | Asiimov',
                'current_price': 50.0,
                'predicted_price': 60.0,
                'roi': 20.0,
                'confidence': 0.90
            },
            {
                'item_name': 'AK-47 | Redline',
                'current_price': 20.0,
                'predicted_price': 25.0,
                'roi': 25.0,
                'confidence': 0.85
            }
        ]
        self.mock_ml_predictor.find_investment_opportunities.return_value = mock_result
        
        # Вызов
        await main()
        
        # Проверка
        self.mock_ml_predictor.find_investment_opportunities.assert_called_once()
        call_args = self.mock_ml_predictor.find_investment_opportunities.call_args[1]
        self.assertEqual(call_args.get('game_id', None), 'csgo')
        self.assertEqual(call_args.get('min_price', None), 10)
        self.assertEqual(call_args.get('max_price', None), 100)
        self.assertEqual(call_args.get('min_roi', None), 5)
        self.assertEqual(call_args.get('limit', None), 5)
        
        # Проверяем результат
        output = mock_stdout.getvalue()
        self.assertIn("Found 2 investment opportunities", output)
        self.assertIn("AWP | Asiimov", output)
        self.assertIn("ROI: 20.0%", output)
        self.assertIn("Confidence: 90%", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    async def test_main_run_command_with_ml(self, mock_stdout):
        """Test for 'run' command with ML enabled."""
        # Подготовка
        sys.argv = ['cli.py', 'run', '--api-keys', self.api_keys_file.name, '--use-ml', 
                   '--timeout', '60', '--game', 'csgo']
        
        # Устанавливаем ожидаемый результат для run_trading_bot_workflow
        mock_result = {
            'status': 'success',
            'executed_trades': 3,
            'total_profit': 25.75,
            'trades': [
                {'item': 'AWP | Asiimov', 'buy_price': 50.0, 'sell_price': 58.0, 'profit': 8.0},
                {'item': 'AK-47 | Redline', 'buy_price': 20.0, 'sell_price': 24.5, 'profit': 4.5},
                {'item': 'M4A4 | Desolate Space', 'buy_price': 35.0, 'sell_price': 48.25, 'profit': 13.25}
            ]
        }
        self.mock_integration_manager.run_trading_bot_workflow.return_value = mock_result
        
        # Вызов
        await main()
        
        # Проверка
        self.mock_integration_manager.run_trading_bot_workflow.assert_called_once()
        call_args = self.mock_integration_manager.run_trading_bot_workflow.call_args[1]
        self.assertEqual(call_args.get('timeout', None), 60)
        self.assertEqual(call_args.get('use_ml', None), True)
        self.assertEqual(call_args.get('game', None), 'csgo')
        
        # Проверяем результат
        output = mock_stdout.getvalue()
        self.assertIn("Trading bot run completed", output)
        self.assertIn("Executed trades: 3", output)
        self.assertIn("Total profit: $25.75", output)
        self.assertIn("AWP | Asiimov", output)
        self.assertIn("Profit: $8.00", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    async def test_main_no_command(self, mock_stdout):
        """Test for missing command."""
        # Подготовка
        sys.argv = ['cli.py', '--api-keys', self.api_keys_file.name]
        
        # Вызов
        await main()
        
        # Проверка
        output = mock_stdout.getvalue()
        self.assertIn("error: the following arguments are required: command", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    async def test_main_analyze_with_ml(self, mock_stdout):
        """Test for 'analyze' command with ML enabled."""
        # Подготовка
        sys.argv = ['cli.py', 'analyze', '--api-keys', self.api_keys_file.name, '--use-ml', 
                   '--game', 'csgo', '--limit', '5']
        
        # Устанавливаем ожидаемый результат для analyze_arbitrage_opportunities
        mock_result = [
            {
                'item_name': 'AWP | Asiimov',
                'buy_price': 50.0,
                'sell_price': 58.0,
                'profit': 8.0,
                'ml_confidence': 0.92
            },
            {
                'item_name': 'AK-47 | Redline',
                'buy_price': 20.0,
                'sell_price': 24.5,
                'profit': 4.5,
                'ml_confidence': 0.88
            }
        ]
        self.mock_integration_manager.analyze_arbitrage_opportunities.return_value = mock_result
        
        # Вызов
        await main()
        
        # Проверка
        self.mock_integration_manager.analyze_arbitrage_opportunities.assert_called_once()
        call_args = self.mock_integration_manager.analyze_arbitrage_opportunities.call_args[1]
        self.assertEqual(call_args.get('game', None), 'csgo')
        self.assertEqual(call_args.get('limit', None), 5)
        self.assertEqual(call_args.get('use_ml', None), True)
        
        # Проверяем результат
        output = mock_stdout.getvalue()
        self.assertIn("Found 2 arbitrage opportunities", output)
        self.assertIn("AWP | Asiimov", output)
        self.assertIn("Buy price: $50.00", output)
        self.assertIn("Sell price: $58.00", output)
        self.assertIn("Profit: $8.00", output)
        self.assertIn("ML confidence: 92%", output)


if __name__ == '__main__':
    unittest.main() 