"""
Модульные тесты для CLI интерфейса бота.

Тестирует команды CLI, связанные с функциональностью машинного обучения.
"""

import unittest
import sys
import os
import tempfile
import shutil
import asyncio
import functools
import logging  # Add missing import
from unittest.mock import patch, MagicMock, AsyncMock
from io import StringIO

# Добавляем корневую директорию проекта в sys.path
# Assuming the test file is in tests/, the project root is one level up.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)


# Импортируем модули для тестирования
# Примечание: E402 (import not at top) игнорируется для тестов
from src.cli.cli import parse_args, main  # noqa: E402 # pylint: disable=wrong-import-position


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


class TestCLI(AsyncTestCase):
    """Тесты CLI интерфейса."""

    async def async_setUp(self):
        """Асинхронная настройка тестового окружения."""
        # Создаем временную директорию для тестовых файлов
        self.temp_dir = tempfile.mkdtemp()
        # Define results and logs dir within the temp dir
        self.results_dir = os.path.join(self.temp_dir, 'results')
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

        # Patch os.path.join to redirect 'results' and 'logs'
        # Need to store original os.path.join to avoid recursion in side_effect
        self.original_os_path_join = os.path.join

        def patched_join(*args):
            if args[0] == 'results' and len(args) > 1:
                # Construct path inside the temp results directory
                return self.original_os_path_join(self.results_dir, *args[1:])
            elif args[0] == 'logs' and len(args) > 1:
                # Construct path inside the temp logs directory
                return self.original_os_path_join(self.logs_dir, *args[1:])
            # Fallback to original join for other paths
            return self.original_os_path_join(*args)

        self.patcher_join = patch('src.cli.cli.os.path.join', side_effect=patched_join)
        # Patch FileHandler to use the temp logs directory
        self.patcher_filehandler = patch(
            'src.cli.cli.logging.FileHandler',
            lambda path, mode: logging.FileHandler(
                os.path.join(self.logs_dir, os.path.basename(path)), mode
            )
        )
        # Patch makedirs to avoid creating real 'logs'/'results' dirs outside temp
        self.patcher_makedirs = patch('src.cli.cli.os.makedirs', return_value=None)

        self.patcher_join.start()
        self.patcher_filehandler.start()
        self.patcher_makedirs.start()

        # Создаем тестовую конфигурацию (Not used directly by cli.py anymore)
        # self.test_config = { ... }
        # self.config_file = os.path.join(self.temp_dir, 'config.json')
        # with open(self.config_file, 'w') as f:
        #     json.dump(self.test_config, f)

        # Создаем временный файл .env
        self.env_file = os.path.join(self.temp_dir, '.env')
        with open(self.env_file, 'w') as f:
            f.write("DMARKET_API_KEY=test_public_key\\n")
            f.write("DMARKET_API_SECRET=test_secret_key\\n")

        # Патчим load_dotenv, чтобы он загружал наш временный файл
        # Also patch getenv to simulate loading from .env
        self.patcher_dotenv = patch('src.cli.cli.load_dotenv', return_value=True)
        self.patcher_getenv = patch('src.cli.cli.os.getenv', side_effect=lambda key, default=None: {
            'DMARKET_API_KEY': 'test_public_key',
            'DMARKET_API_SECRET': 'test_secret_key'
        }.get(key, default))
        # Patch load_config as it's called but not essential for these tests
        self.patcher_load_config = patch('src.cli.cli.load_config', return_value=MagicMock())

        self.patcher_dotenv.start()
        self.patcher_getenv.start()
        self.patcher_load_config.start()

    async def async_tearDown(self):
        """Асинхронная очистка тестового окружения."""
        # Stop patchers in reverse order
        self.patcher_load_config.stop()
        self.patcher_getenv.stop()
        self.patcher_dotenv.stop()
        self.patcher_makedirs.stop()
        self.patcher_filehandler.stop()
        self.patcher_join.stop()

        # Удаляем временную директорию
        # Use ignore_errors=True for robustness
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_args(self):
        """Тест парсинга аргументов командной строки."""
        # Тестируем команду run с ML
        with patch.object(sys, 'argv', ['cli.py', 'run', '--use-ml']):
            args = parse_args()
            self.assertEqual(args.command, 'run')
            # self.assertEqual(args.config, self.config_file)  # Config file arg removed
            self.assertTrue(args.use_ml)

        # Тестируем команду analyze с ML
        # Game arg removed from analyze
        with patch.object(sys, 'argv', ['cli.py', 'analyze', '--use-ml', '--limit', '50']):
            args = parse_args()
            self.assertEqual(args.command, 'analyze')
            # self.assertEqual(args.config, self.config_file)  # Config file arg removed
            self.assertTrue(args.use_ml)
            # self.assertEqual(args.game, 'csgo')  # Game arg removed
            self.assertEqual(args.limit, 50)

        # Тестируем команду train
        with patch.object(sys, 'argv', [
            'cli.py', 'train',  # '--config', self.config_file, # Config file arg removed
            '--game', 'csgo',
            '--item', 'AWP | Asiimov', '--days', '30'
        ]):
            args = parse_args()
            self.assertEqual(args.command, 'train')
            # self.assertEqual(args.config, self.config_file)  # Config file arg removed
            self.assertEqual(args.game, 'csgo')
            self.assertEqual(args.item, 'AWP | Asiimov')
            self.assertEqual(args.days, 30)

        # Тестируем команду predict
        with patch.object(sys, 'argv', [
            'cli.py', 'predict',  # '--config', self.config_file, # Config file arg removed
            '--item', 'AWP | Asiimov',
            '--model', 'random_forest'
        ]):
            args = parse_args()
            self.assertEqual(args.command, 'predict')
            # self.assertEqual(args.config, self.config_file)  # Config file arg removed
            self.assertEqual(args.item, 'AWP | Asiimov')
            self.assertEqual(args.model, 'random_forest')

        # Тестируем команду invest
        with patch.object(sys, 'argv', [
            'cli.py', 'invest',  # '--config', self.config_file, # Config file arg removed
            '--min-price', '10',
            '--max-price', '200', '--min-roi', '20'
        ]):
            args = parse_args()
            self.assertEqual(args.command, 'invest')
            # self.assertEqual(args.config, self.config_file)  # Config file arg removed
            self.assertEqual(args.min_price, 10)
            self.assertEqual(args.max_price, 200)
            self.assertEqual(args.min_roi, 20)

    @async_test
    async def test_main_run_with_ml(self):
        """Тест запуска бота с ML через main."""
        # Настраиваем моки
        # Removed mock_get_keys, mock_api, mock_ml_predictor as they are implicitly tested
        # via IntegrationManager
        with patch('src.cli.cli.IntegrationManager') as mock_integration:

            # Настраиваем поведение моков
            # mock_get_keys handled by patcher_getenv
            # mock_api_instance = MagicMock()
            # mock_api.return_value = mock_api_instance
            # mock_ml_instance = MagicMock()
            # mock_ml_predictor.return_value = mock_ml_instance
            mock_integration_instance = AsyncMock()
            mock_integration.return_value = mock_integration_instance
            # Simulate successful run by returning None or a success dict if expected
            mock_integration_instance.run_trading_bot_workflow = AsyncMock(return_value=None)
            # mock_integration_instance.run_trading_bot_workflow.return_value = {
            #     'status': 'success',
            #     'trades': 5
            # }  # This return value is not used by main()

            # Перенаправляем stdout для проверки вывода
            stdout_backup = sys.stdout
            sys.stdout = StringIO()

            try:
                # Запускаем main с командой run
                # Config file arg removed
                sys.argv = ['cli.py', 'run', '--use-ml']
                # Создаем корутину и выполняем ее
                exit_code = await main()  # main now returns exit code

                # Проверяем, что интеграционный менеджер был создан и запущен
                mock_integration.assert_called_once()

                # Проверяем, что метод был вызван с правильными параметрами
                mock_integration_instance.run_trading_bot_workflow.assert_called_once()
                args, kwargs = mock_integration_instance.run_trading_bot_workflow.call_args
                # Check API keys from patched get_api_keys (via os.getenv)
                self.assertEqual(kwargs.get('api_key'), 'test_public_key')
                self.assertEqual(kwargs.get('api_secret'), 'test_secret_key')
                self.assertTrue(kwargs.get('use_ml', False))
                # Check default values from parse_args
                self.assertEqual(kwargs.get('update_interval'), 3600)
                self.assertEqual(kwargs.get('max_trades_per_run'), 3)
                self.assertEqual(exit_code, 0)  # Check exit code for success

                # Проверяем вывод
                output = sys.stdout.getvalue()
                self.assertIn('Running trading bot', output)
                # self.assertIn('success', output)  # Output depends on workflow result
            finally:
                # Восстанавливаем stdout
                sys.stdout = stdout_backup

    @async_test
    async def test_main_train(self):
        """Тест обучения модели через main."""
        # Настраиваем моки
        # Removed mock_get_keys, mock_api
        # Patch MLPredictor directly as it's used by the 'train' command
        with patch('src.cli.cli.MLPredictor') as mock_ml_predictor, \
             patch('src.cli.cli.save_result_to_file') as mock_save:  # Patch save_result_to_file

            # Настраиваем поведение моков
            # mock_get_keys handled by patcher_getenv
            # mock_api_instance = MagicMock()
            # mock_api.return_value = mock_api_instance
            mock_ml_instance = MagicMock()  # Use MagicMock for synchronous class
            mock_ml_predictor.return_value = mock_ml_instance
            # train_model is async
            mock_ml_instance.train_model = AsyncMock()
            # Simulate successful training result structure from cli.py
            mock_ml_instance.train_model.return_value = {
                'success': True,  # Changed from 'status'
                'model_path': 'models/csgo/AWP | Asiimov_predictor.pkl',  # Adjusted name
                'metrics': {'accuracy': 0.95}  # Nested metrics dict
            }
            # Mock save_result_to_file return value
            mock_save.return_value = os.path.join(
                self.results_dir, "train_result_csgo_random_forest.json"
            )

            # Перенаправляем stdout для проверки вывода
            stdout_backup = sys.stdout
            sys.stdout = StringIO()

            try:
                # Запускаем main с командой train
                # Config file arg removed
                sys.argv = [
                    'cli.py', 'train',
                    # '--config', self.config_file,
                    '--game', 'csgo',
                    '--item', 'AWP | Asiimov',
                    '--days', '30',
                    '--model-type', 'random_forest'
                ]
                # Создаем корутину и выполняем ее
                exit_code = await main()  # main now returns exit code

                # Проверяем, что ML предиктор был создан и вызван правильно
                mock_ml_predictor.assert_called_once()

                # Проверяем, что метод был вызван с правильными параметрами
                mock_ml_instance.train_model.assert_called_once()
                args, kwargs = mock_ml_instance.train_model.call_args
                self.assertEqual(kwargs.get('game_id'), 'csgo')
                # Check model name construction based on item presence
                self.assertEqual(kwargs.get('model_name'), 'AWP | Asiimov_predictor')
                self.assertEqual(kwargs.get('history_days'), 30)
                self.assertEqual(kwargs.get('model_type'), 'random_forest')
                # Check default values
                self.assertEqual(kwargs.get('items_limit'), 500)
                self.assertEqual(kwargs.get('force_retrain'), False)
                self.assertEqual(exit_code, 0)  # Check exit code for success

                # Check that save_result_to_file was called
                mock_save.assert_called_once()
                # Check the filename passed to save_result_to_file
                save_args, save_kwargs = mock_save.call_args
                self.assertEqual(
                    save_kwargs.get('filename'), "train_result_csgo_random_forest.json"
                )

                # Проверяем вывод
                output = sys.stdout.getvalue()
                self.assertIn('Model training completed successfully. Metrics:', output)
                self.assertIn('accuracy: 0.95', output)  # Check metric output
                # Check save file log message
                self.assertIn(f"Результат сохранен в файл: {mock_save.return_value}", output)

            finally:
                # Восстанавливаем stdout
                sys.stdout = stdout_backup

    @async_test
    async def test_main_predict(self):
        """Тест предсказания цены через main."""
        # Настраиваем моки
        with patch('src.cli.cli.MLPredictor') as mock_ml_predictor, \
             patch('src.cli.cli.save_result_to_file') as mock_save:

            # Настраиваем поведение моков
            # mock_get_keys handled by patcher_getenv
            # mock_api_instance = MagicMock()
            # mock_api.return_value = mock_api_instance
            mock_ml_instance = MagicMock()
            mock_ml_predictor.return_value = mock_ml_instance
            mock_ml_instance.predict_price = AsyncMock()
            # Simulate prediction result structure from cli.py
            mock_ml_instance.predict_price.return_value = {
                'current_price': 100.50,  # Use float
                'forecast': [
                    {'date': '2025-04-18', 'price': 120.75, 'change': 20.15}
                ],  # List of dicts
                'trend': 'up',  # Added trend
                'confidence': 0.85,
                # 'recommendation': 'buy'  # Not used in cli.py output
            }
            # Mock save_result_to_file return value
            mock_save.return_value = os.path.join(
                self.results_dir, "prediction_cs2_AWP_|_Asiimov.json"
            )

            # Перенаправляем stdout для проверки вывода
            stdout_backup = sys.stdout
            sys.stdout = StringIO()

            try:
                # Запускаем main с командой predict
                # Config file arg removed
                sys.argv = [
                    'cli.py', 'predict',
                    # '--config', self.config_file,
                    '--item', 'AWP | Asiimov',
                    '--model', 'random_forest'  # Corresponds to default in cli.py
                ]
                # Создаем корутину и выполняем ее
                exit_code = await main()  # main now returns exit code

                # Проверяем, что ML предиктор был создан и вызван правильно
                mock_ml_predictor.assert_called_once()

                # Проверяем, что метод был вызван с правильными параметрами
                mock_ml_instance.predict_price.assert_called_once()
                args, kwargs = mock_ml_instance.predict_price.call_args
                self.assertEqual(kwargs.get('game_id'), 'cs2')  # Check default game
                self.assertEqual(kwargs.get('item_name'), 'AWP | Asiimov')
                self.assertEqual(kwargs.get('model_type'), 'random_forest')
                self.assertEqual(kwargs.get('days_ahead'), 7)  # Check default days
                self.assertEqual(exit_code, 0)  # Check exit code for success

                # Check that save_result_to_file was called
                mock_save.assert_called_once()
                # Check the filename passed to save_result_to_file
                save_args, save_kwargs = mock_save.call_args
                # Filename includes game and sanitized item name
                self.assertEqual(save_kwargs.get('filename'), "prediction_cs2_AWP_|_Asiimov.json")

                # Проверяем вывод
                output = sys.stdout.getvalue()
                self.assertIn('Price prediction results for AWP | Asiimov:', output)
                self.assertIn('Current price: $100.50', output)  # Check formatted price
                self.assertIn('Price trend: up', output)  # Check trend output
                self.assertIn('Prediction confidence: 0.85', output)  # Check confidence output
                # Check forecast output
                self.assertIn('Price forecast:', output)
                self.assertIn('2025-04-18: $120.75 (+20.15%)', output)
                # Check save file log message
                self.assertIn(f"Результат сохранен в файл: {mock_save.return_value}", output)

            finally:
                # Восстанавливаем stdout
                sys.stdout = stdout_backup

    @async_test
    async def test_main_invest(self):
        """Тест поиска инвестиционных возможностей через main."""
        # Настраиваем моки
        with patch('src.cli.cli.MLPredictor') as mock_ml_predictor, \
             patch('src.cli.cli.save_result_to_file') as mock_save:

            # Настраиваем поведение моков
            # mock_get_keys handled by patcher_getenv
            # mock_api_instance = MagicMock()
            # mock_api.return_value = mock_api_instance
            mock_ml_instance = MagicMock()
            mock_ml_predictor.return_value = mock_ml_instance
            # find_investments is async, renamed from find_investment_opportunities
            mock_ml_instance.find_investments = AsyncMock()
            # Simulate investment result structure from cli.py
            mock_ml_instance.find_investments.return_value = [
                {
                    'title': 'AWP | Asiimov',  # Changed from item_name
                    'current_price': 100,
                    'predicted_price': 150,
                    'percent_change': 50.0,  # Changed from predicted_roi
                    'confidence': 0.9
                },
                {
                    'title': 'AK-47 | Redline',  # Changed from item_name
                    'current_price': 50,
                    'predicted_price': 70,
                    'percent_change': 40.0,  # Changed from predicted_roi
                    'confidence': 0.85
                }
            ]
            # Mock save_result_to_file return value
            mock_save.return_value = os.path.join(self.results_dir, "investments_cs2.json")

            # Перенаправляем stdout для проверки вывода
            stdout_backup = sys.stdout
            sys.stdout = StringIO()

            try:
                # Запускаем main с командой invest
                # Config file arg removed
                sys.argv = [
                    'cli.py', 'invest',
                    # '--config', self.config_file,
                    '--min-price', '10',
                    '--max-price', '200',
                    '--min-roi', '20',  # Corresponds to min_percent_gain
                    '--min-confidence', '0.8'
                ]
                # Создаем корутину и выполняем ее
                exit_code = await main()  # main now returns exit code

                # Проверяем, что ML предиктор был создан и вызван правильно
                mock_ml_predictor.assert_called_once()

                # Проверяем, что метод был вызван с правильными параметрами
                mock_ml_instance.find_investments.assert_called_once()
                args, kwargs = mock_ml_instance.find_investments.call_args
                self.assertEqual(kwargs.get('game_id'), 'cs2')  # Check default game
                self.assertEqual(
                    kwargs.get('price_range'), (10.0, 200.0)
                )  # Check price range tuple
                self.assertEqual(kwargs.get('min_percent_gain'), 20)  # Check min ROI mapping
                self.assertEqual(kwargs.get('min_confidence'), 0.8)
                self.assertEqual(kwargs.get('limit'), 20)  # Check default limit
                self.assertEqual(exit_code, 0)  # Check exit code for success

                # Check that save_result_to_file was called
                mock_save.assert_called_once()
                # Check the filename passed to save_result_to_file
                save_args, save_kwargs = mock_save.call_args
                self.assertEqual(mock_save.return_value, save_kwargs.get('filename'))

                # Проверяем вывод
                output = sys.stdout.getvalue()
                self.assertIn('Found 2 investment opportunities:', output)  # Check count in log
                # Check details for first opportunity
                self.assertIn('1. AWP | Asiimov', output)
                self.assertIn('Current price: $100.00', output)
                # Check formatted predicted price and percentage
                self.assertIn('Predicted price: $150.00 (+50.00%)', output)
                self.assertIn('Confidence: 0.90', output)  # Check formatted confidence
                # Check details for second opportunity
                self.assertIn('2. AK-47 | Redline', output)
                self.assertIn('Current price: $50.00', output)
                self.assertIn('Predicted price: $70.00 (+40.00%)', output)
                self.assertIn('Confidence: 0.85', output)
                # Check save file log message
                self.assertIn(f"Результат сохранен в файл: {mock_save.return_value}", output)

            finally:
                # Восстанавливаем stdout
                sys.stdout = stdout_backup

    @async_test
    async def test_main_analyze_with_ml(self):
        """Тест анализа арбитражных возможностей с ML через main."""
        # Настраиваем моки
        # Patch IntegrationManager and its methods used by 'analyze'
        with patch('src.cli.cli.IntegrationManager') as mock_integration:
            # No save_result_to_file in analyze command in cli.py

            # Настраиваем поведение моков
            # mock_get_keys handled by patcher_getenv
            # mock_api_instance = MagicMock()
            # mock_api.return_value = mock_api_instance
            # mock_ml_instance = MagicMock()  # MLPredictor not directly used by analyze
            # mock_ml_predictor.return_value = mock_ml_instance
            mock_integration_instance = AsyncMock()  # IntegrationManager is used
            mock_integration.return_value = mock_integration_instance
            # Mock collect_market_data used by analyze
            mock_integration_instance.collect_market_data = MagicMock(
                return_value={'items': {'item1': {}, 'item2': {}}}  # Simulate some market data
            )
            # Mock analyze_arbitrage_opportunities used by analyze
            mock_integration_instance.analyze_arbitrage_opportunities = MagicMock(
                return_value=[  # Returns a list directly in cli.py
                    {
                        'item_name': 'AWP | Asiimov',
                        'buy_price': 90,
                        'sell_price': 100,
                        'profit': 10,
                        'profit_percent': 11.11,
                        # 'confidence': 0.95  # Confidence not present in example return
                    }
                ]
                # 'total_count': 1  # Not in the return value in cli.py
            )
            # Mock the stat_arbitrage object and its export method
            mock_stat_arbitrage = MagicMock()
            mock_integration_instance.stat_arbitrage = mock_stat_arbitrage
            mock_stat_arbitrage.export_opportunities.return_value = os.path.join(
                self.results_dir, "arbitrage_results.json"
            )

            # Перенаправляем stdout для проверки вывода
            stdout_backup = sys.stdout
            sys.stdout = StringIO()

            try:
                # Запускаем main с командой analyze
                # Config file, game, min-profit, output args removed from cli.py analyze command
                sys.argv = [
                    'cli.py', 'analyze',
                    # '--config', self.config_file,
                    '--use-ml',
                    # '--game', 'csgo',  # Removed
                    # '--min-profit', '5',  # Removed
                    # '--output', os.path.join(self.temp_dir, 'arbitrage_results.json')  # Removed
                    '--limit', '50'  # Keep limit as it's parsed
                ]
                # Создаем корутину и выполняем ее
                exit_code = await main()  # main now returns exit code

                # Проверяем, что интеграционный менеджер был создан и запущен
                mock_integration.assert_called_once()
                # Check that collect_market_data was called
                mock_integration_instance.collect_market_data.assert_called_once()

                # Проверяем, что метод analyze_arbitrage_opportunities был вызван
                mock_integration_instance.analyze_arbitrage_opportunities.assert_called_once()
                args, kwargs = mock_integration_instance.analyze_arbitrage_opportunities.call_args
                self.assertTrue(kwargs.get('use_ml', False))
                # Check other args passed to analyze_arbitrage_opportunities (none in this case)
                # self.assertEqual(kwargs.get('game_id'), 'csgo')  # Removed
                # self.assertEqual(kwargs.get('min_profit'), 5)  # Removed
                self.assertEqual(exit_code, 0)  # Check exit code for success

                # Check that export_opportunities was called
                mock_stat_arbitrage.export_opportunities.assert_called_once_with(
                    mock_integration_instance.analyze_arbitrage_opportunities.return_value
                )

                # Проверяем вывод
                output = sys.stdout.getvalue()
                self.assertIn('Analyzing market opportunities', output)
                # Check item count log based on mocked market data
                self.assertIn('Collected data for 2 items', output)
                # Check opportunity count log based on mocked analysis result
                self.assertIn('Found 1 arbitrage opportunities', output)
                # Check export log message
                export_path = mock_stat_arbitrage.export_opportunities.return_value
                self.assertIn(f"Opportunities exported to {export_path}", output)
                # self.assertIn('AWP | Asiimov', output)  # Not logged by default

            finally:
                # Восстанавливаем stdout
                sys.stdout = stdout_backup


if __name__ == '__main__':
    unittest.main()