"""
Тесты для модуля trading_bot.

Проверяет функциональность:
- Загрузка и сохранение конфигурации
- Инициализация и запуск торгового бота
- Обработка рыночных данных
- Логирование
"""

import unittest
import os
import json
import asyncio
import tempfile
import shutil
from unittest.mock import patch, MagicMock, AsyncMock
import logging
from datetime import datetime, timedelta
import sys

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from src.trading.trading_bot import TradingBotConfig, TradingBot, Logger
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    # Создаем заглушки для тестов в случае импорта
    class TradingBotConfig:
        CONFIG_FILE = 'config/config.json'
        LOG_FILE = 'logs/trading_bot.log'
        
        @classmethod
        def load_from_file(cls, file_path=None):
            return {}
            
        @classmethod
        def save_to_file(cls, config, file_path=None):
            return True
    
    class TradingBot:
        def __init__(self, api_key=None, api_secret=None, config_path=None, simulation_mode=True, log_level=logging.INFO):
            pass
            
        def start(self):
            pass
            
        def stop(self):
            pass
    
    class Logger:
        def __init__(self, log_file=None, log_level=logging.INFO, name="trading_bot"):
            pass


class TestTradingBotConfig(unittest.TestCase):
    """Тесты для класса TradingBotConfig."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временную директорию для тестов
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.json')
        
        # Сохраняем оригинальное значение CONFIG_FILE
        self.original_config_file = TradingBotConfig.CONFIG_FILE
        
    def tearDown(self):
        """Очистка после тестов."""
        # Восстанавливаем оригинальное значение CONFIG_FILE
        TradingBotConfig.CONFIG_FILE = self.original_config_file
        
        # Удаляем временную директорию
        shutil.rmtree(self.temp_dir)
    
    def test_load_from_nonexistent_file(self):
        """Тест загрузки конфигурации из несуществующего файла."""
        # Должны получить значения по умолчанию
        config = TradingBotConfig.load_from_file(self.config_file)
        
        # Проверяем, что возвращаемое значение является словарем
        self.assertIsInstance(config, dict)
        
        # Проверяем, что файл был создан
        self.assertTrue(os.path.exists(self.config_file))
        
        # Проверяем, что словарь содержит ожидаемые ключи
        self.assertIn('API_BASE_URL', config)
        self.assertIn('HEADERS', config)
        self.assertIn('SIMULATION_MODE', config)
    
    def test_save_and_load_config(self):
        """Тест сохранения и загрузки конфигурации."""
        # Создаем тестовую конфигурацию
        test_config = {
            'API_BASE_URL': 'https://test.api.com',
            'MAX_DEPTH': 5,
            'SIMULATION_MODE': False
        }
        
        # Сохраняем конфигурацию
        result = TradingBotConfig.save_to_file(test_config, self.config_file)
        self.assertTrue(result)
        
        # Загружаем конфигурацию
        loaded_config = TradingBotConfig.load_from_file(self.config_file)
        
        # Проверяем, что загруженная конфигурация соответствует сохраненной
        self.assertEqual(loaded_config['API_BASE_URL'], test_config['API_BASE_URL'])
        self.assertEqual(loaded_config['MAX_DEPTH'], test_config['MAX_DEPTH'])
        self.assertEqual(loaded_config['SIMULATION_MODE'], test_config['SIMULATION_MODE'])


class TestLogger(unittest.TestCase):
    """Тесты для класса Logger."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'test.log')
    
    def tearDown(self):
        """Очистка после тестов."""
        shutil.rmtree(self.temp_dir)
    
    def test_logger_initialization(self):
        """Тест инициализации логгера."""
        logger = Logger(self.log_file, logging.DEBUG, "test_logger")
        
        # Проверяем, что атрибуты установлены правильно
        self.assertEqual(logger.log_file, self.log_file)
        self.assertEqual(logger.logger.name, "test_logger")
        self.assertEqual(logger.logger.level, logging.DEBUG)
        
        # Проверяем, что хендлеры были добавлены
        self.assertTrue(logger.logger.handlers)
        
        # Один для консоли, один для файла
        self.assertEqual(len(logger.logger.handlers), 2)
    
    def test_logging_methods(self):
        """Тест методов логирования."""
        logger = Logger(self.log_file, logging.DEBUG, "test_logger")
        
        # Логируем сообщения разных уровней
        with patch('logging.Logger.debug') as mock_debug, \
             patch('logging.Logger.info') as mock_info, \
             patch('logging.Logger.warning') as mock_warning, \
             patch('logging.Logger.error') as mock_error, \
             patch('logging.Logger.critical') as mock_critical:
             
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")
            
            # Проверяем, что соответствующие методы были вызваны
            mock_debug.assert_called_once_with("Debug message")
            mock_info.assert_called_once_with("Info message")
            mock_warning.assert_called_once_with("Warning message")
            mock_error.assert_called_once_with("Error message")
            mock_critical.assert_called_once_with("Critical message")


class TestTradingBot(unittest.TestCase):
    """Тесты для класса TradingBot."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временную директорию для тестов
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.json')
        
        # Создаем тестовую конфигурацию
        self.test_config = {
            'API_BASE_URL': 'https://test.api.com',
            'MAX_DEPTH': 5,
            'SIMULATION_MODE': True,
            'API_KEY_FILE': os.path.join(self.temp_dir, 'api_key.txt'),
            'API_SECRET_FILE': os.path.join(self.temp_dir, 'api_secret.txt'),
            'LOG_FILE': os.path.join(self.temp_dir, 'test.log'),
            'TRADING_ENABLED': False
        }
        
        # Сохраняем конфигурацию
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
            
        # Сохраняем тестовые API ключи
        with open(self.test_config['API_KEY_FILE'], 'w', encoding='utf-8') as f:
            f.write('test_api_key')
        with open(self.test_config['API_SECRET_FILE'], 'w', encoding='utf-8') as f:
            f.write('test_api_secret')
    
    def tearDown(self):
        """Очистка после тестов."""
        # Удаляем временную директорию
        shutil.rmtree(self.temp_dir)
    
    @patch('src.trading.trading_bot.DMarketAPI')
    def test_initialization(self, mock_api):
        """Тест инициализации торгового бота."""
        # Создаем бота с тестовой конфигурацией
        bot = TradingBot(
            api_key='test_api_key',
            api_secret='test_api_secret',
            config_path=self.config_file,
            simulation_mode=True
        )
        
        # Проверяем, что API был инициализирован с правильными параметрами
        mock_api.assert_called_once_with('test_api_key', 'test_api_secret')
        
        # Проверяем, что атрибуты установлены правильно
        self.assertTrue(bot.simulation_mode)
        self.assertIsNotNone(bot.logger)
        self.assertFalse(bot.trading_enabled)  # Из тестовой конфигурации
    
    @patch('src.trading.trading_bot.DMarketAPI')
    def test_start_and_stop(self, mock_api):
        """Тест запуска и остановки бота."""
        bot = TradingBot(
            api_key='test_api_key',
            api_secret='test_api_secret',
            config_path=self.config_file,
            simulation_mode=True
        )
        
        # Патчим метод _check_api_connection
        with patch.object(bot, '_check_api_connection', return_value=True):
            # Запускаем бота
            bot.start()
            
            # Проверяем, что бот запущен
            self.assertTrue(bot.running)
            
            # Останавливаем бота
            bot.stop()
            
            # Проверяем, что бот остановлен
            self.assertFalse(bot.running)
    
    @patch('src.trading.trading_bot.DMarketAPI')
    def test_update_market_data(self, mock_api):
        """Тест обновления рыночных данных."""
        # Создаем мок для API
        mock_instance = mock_api.return_value
        mock_instance.get_market_items.return_value = [
            {'itemId': 'item1', 'title': 'Item 1', 'price': {'USD': 100}},
            {'itemId': 'item2', 'title': 'Item 2', 'price': {'USD': 50}}
        ]
        
        # Создаем бота
        bot = TradingBot(
            api_key='test_api_key',
            api_secret='test_api_secret',
            config_path=self.config_file,
            simulation_mode=True
        )
        
        # Вызываем метод обновления данных
        bot._update_market_data()
        
        # Проверяем, что API вызван
        mock_instance.get_market_items.assert_called_once()
        
        # Проверяем, что данные обновлены
        self.assertEqual(len(bot.market_data), 2)


if __name__ == '__main__':
    unittest.main() 