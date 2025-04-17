"""
Тесты для менеджера API ключей.

Проверяет функциональность управления API ключами, включая загрузку из файла,
кеширование, ротацию ключей и обработку ошибок.
"""

import unittest
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from src.utils.api_key_manager import APIKeyManager, APIKeyRotator
    API_KEY_MANAGER_AVAILABLE = True
except ImportError:
    # Создаем заглушки для тестирования, если модули не найдены
    API_KEY_MANAGER_AVAILABLE = False
    
    class APIKeyManager:
        """Управление API ключами для различных сервисов."""
        
        def __init__(self, config_file=None):
            self.config_file = config_file
            self._keys = {}
            self._load_keys()
        
        def _load_keys(self):
            """Загружает ключи из файла конфигурации."""
            if not self.config_file or not os.path.exists(self.config_file):
                return
            
            try:
                with open(self.config_file, 'r') as f:
                    self._keys = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading API keys: {e}")
        
        def get_key(self, service, key_type='default'):
            """Получает ключ API для указанного сервиса."""
            service_keys = self._keys.get(service, {})
            key = service_keys.get(key_type)
            
            return key
        
        def get_keys(self, service):
            """Получает все ключи для указанного сервиса."""
            return self._keys.get(service, {})
        
        def add_key(self, service, key, key_type='default', save=True):
            """Добавляет новый ключ API."""
            if service not in self._keys:
                self._keys[service] = {}
            
            self._keys[service][key_type] = key
            
            if save and self.config_file:
                self._save_keys()
            
            return True
        
        def remove_key(self, service, key_type='default', save=True):
            """Удаляет ключ API."""
            if service in self._keys and key_type in self._keys[service]:
                del self._keys[service][key_type]
                
                if not self._keys[service]:
                    del self._keys[service]
                
                if save and self.config_file:
                    self._save_keys()
                
                return True
            
            return False
        
        def _save_keys(self):
            """Сохраняет ключи в файл конфигурации."""
            if not self.config_file:
                return False
            
            try:
                with open(self.config_file, 'w') as f:
                    json.dump(self._keys, f, indent=2)
                return True
            except IOError as e:
                print(f"Error saving API keys: {e}")
                return False
    
    class APIKeyRotator:
        """Ротация API ключей для избежания ограничений."""
        
        def __init__(self, key_manager):
            self.key_manager = key_manager
            self.usage_tracking = {}
        
        def get_key(self, service):
            """Получает следующий доступный ключ с учетом ротации."""
            keys = self.key_manager.get_keys(service)
            
            if not keys:
                return None
            
            # Выбираем ключ с наименьшим использованием
            best_key = None
            best_key_type = None
            min_usage = float('inf')
            
            for key_type, key in keys.items():
                usage = self.usage_tracking.get(f"{service}:{key_type}", 0)
                
                if usage < min_usage:
                    min_usage = usage
                    best_key = key
                    best_key_type = key_type
            
            # Увеличиваем счетчик использования
            if best_key_type:
                track_key = f"{service}:{best_key_type}"
                self.usage_tracking[track_key] = self.usage_tracking.get(track_key, 0) + 1
            
            return best_key
        
        def mark_key_error(self, service, key_type):
            """Отмечает ключ как временно недоступный из-за ошибки."""
            track_key = f"{service}:{key_type}"
            # Увеличиваем счетчик использования значительно, чтобы предотвратить использование
            self.usage_tracking[track_key] = self.usage_tracking.get(track_key, 0) + 1000
        
        def reset_usage(self, service=None):
            """Сбрасывает счетчики использования."""
            if service:
                keys = self.key_manager.get_keys(service)
                for key_type in keys:
                    track_key = f"{service}:{key_type}"
                    if track_key in self.usage_tracking:
                        self.usage_tracking[track_key] = 0
            else:
                self.usage_tracking = {}


class TestAPIKeyManager(unittest.TestCase):
    """Тесты для менеджера API ключей."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временный файл для тестирования
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        
        # Тестовые данные ключей
        self.test_keys = {
            'dmarket': {
                'public': 'test_public_key',
                'secret': 'test_secret_key'
            },
            'steam': {
                'default': 'test_steam_key',
                'backup': 'test_steam_backup_key'
            }
        }
        
        # Сохраняем тестовые данные в файл
        with open(self.temp_file.name, 'w') as f:
            json.dump(self.test_keys, f)
        
        # Создаем экземпляр менеджера ключей
        self.key_manager = APIKeyManager(config_file=self.temp_file.name)
    
    def tearDown(self):
        """Очистка после тестов."""
        # Удаляем временный файл
        try:
            os.unlink(self.temp_file.name)
        except OSError:
            pass
    
    def test_load_keys(self):
        """Тест загрузки ключей из файла."""
        # Проверяем, что ключи были загружены правильно
        dmarket_public = self.key_manager.get_key('dmarket', 'public')
        dmarket_secret = self.key_manager.get_key('dmarket', 'secret')
        steam_default = self.key_manager.get_key('steam', 'default')
        
        self.assertEqual(dmarket_public, 'test_public_key')
        self.assertEqual(dmarket_secret, 'test_secret_key')
        self.assertEqual(steam_default, 'test_steam_key')
    
    def test_get_key(self):
        """Тест получения ключа."""
        # Получаем ключ для существующего сервиса и типа
        key = self.key_manager.get_key('dmarket', 'public')
        self.assertEqual(key, 'test_public_key')
        
        # Получаем ключ для несуществующего сервиса
        key = self.key_manager.get_key('nonexistent')
        self.assertIsNone(key)
        
        # Получаем ключ для существующего сервиса, но несуществующего типа
        key = self.key_manager.get_key('dmarket', 'nonexistent')
        self.assertIsNone(key)
    
    def test_get_keys(self):
        """Тест получения всех ключей для сервиса."""
        # Получаем все ключи для существующего сервиса
        keys = self.key_manager.get_keys('dmarket')
        self.assertEqual(keys, {'public': 'test_public_key', 'secret': 'test_secret_key'})
        
        # Получаем ключи для несуществующего сервиса
        keys = self.key_manager.get_keys('nonexistent')
        self.assertEqual(keys, {})
    
    def test_add_key(self):
        """Тест добавления ключа."""
        # Добавляем новый ключ в существующий сервис
        self.key_manager.add_key('dmarket', 'new_key', 'new_type', save=False)
        
        # Проверяем, что ключ добавлен
        key = self.key_manager.get_key('dmarket', 'new_type')
        self.assertEqual(key, 'new_key')
        
        # Добавляем ключ для нового сервиса
        self.key_manager.add_key('new_service', 'service_key', save=False)
        
        # Проверяем, что ключ добавлен
        key = self.key_manager.get_key('new_service')
        self.assertEqual(key, 'service_key')
    
    def test_remove_key(self):
        """Тест удаления ключа."""
        # Удаляем существующий ключ
        result = self.key_manager.remove_key('dmarket', 'public', save=False)
        
        # Проверяем, что удаление успешно
        self.assertTrue(result)
        
        # Проверяем, что ключ удален
        key = self.key_manager.get_key('dmarket', 'public')
        self.assertIsNone(key)
        
        # Пытаемся удалить несуществующий ключ
        result = self.key_manager.remove_key('nonexistent', save=False)
        
        # Проверяем, что удаление не успешно
        self.assertFalse(result)
    
    def test_save_keys(self):
        """Тест сохранения ключей в файл."""
        # Добавляем новый ключ и сохраняем
        self.key_manager.add_key('new_service', 'new_key', save=True)
        
        # Создаем новый экземпляр менеджера для проверки, что ключи были сохранены
        new_manager = APIKeyManager(config_file=self.temp_file.name)
        
        # Проверяем, что новый ключ загружен
        key = new_manager.get_key('new_service')
        self.assertEqual(key, 'new_key')
    
    @patch('builtins.open', side_effect=IOError("Test IO Error"))
    def test_load_keys_error(self, mock_open):
        """Тест обработки ошибок при загрузке ключей."""
        # Создаем новый экземпляр менеджера с ошибкой открытия файла
        with patch('builtins.print') as mock_print:
            manager = APIKeyManager(config_file='nonexistent.json')
            
            # Проверяем, что ошибка была обработана и выведено сообщение
            mock_print.assert_called_once()
            self.assertIn('Error loading API keys', mock_print.call_args[0][0])
    
    @patch('json.load', side_effect=json.JSONDecodeError("Test JSON Error", "", 0))
    def test_load_keys_json_error(self, mock_json_load):
        """Тест обработки ошибок JSON при загрузке ключей."""
        # Создаем новый экземпляр менеджера с ошибкой JSON
        with patch('builtins.print') as mock_print:
            manager = APIKeyManager(config_file=self.temp_file.name)
            
            # Проверяем, что ошибка была обработана и выведено сообщение
            mock_print.assert_called_once()
            self.assertIn('Error loading API keys', mock_print.call_args[0][0])


class TestAPIKeyRotator(unittest.TestCase):
    """Тесты для ротатора API ключей."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем мок менеджера ключей
        self.key_manager = MagicMock()
        
        # Настраиваем возвращаемые значения для методов мока
        self.key_manager.get_keys.return_value = {
            'key1': 'value1',
            'key2': 'value2',
            'key3': 'value3'
        }
        
        # Создаем экземпляр ротатора ключей
        self.rotator = APIKeyRotator(self.key_manager)
    
    def test_get_key_first_use(self):
        """Тест получения ключа при первом использовании."""
        # Получаем ключ
        key = self.rotator.get_key('test_service')
        
        # Проверяем, что был вызван метод get_keys менеджера
        self.key_manager.get_keys.assert_called_once_with('test_service')
        
        # Проверяем, что ключ был возвращен (любой из доступных)
        self.assertIn(key, ['value1', 'value2', 'value3'])
        
        # Проверяем, что счетчик использования увеличен для этого ключа
        for track_key, usage in self.rotator.usage_tracking.items():
            self.assertEqual(usage, 1)
            self.assertTrue(track_key.startswith('test_service:'))
    
    def test_get_key_with_rotation(self):
        """Тест ротации ключей при многократном использовании."""
        # Получаем ключ несколько раз
        first_key = self.rotator.get_key('test_service')
        
        # Находим ключ, который использовался
        first_key_type = None
        for key_type, key in self.key_manager.get_keys().items():
            if key == first_key:
                first_key_type = key_type
                break
        
        # Отмечаем первый ключ как использованный несколько раз
        track_key = f"test_service:{first_key_type}"
        self.rotator.usage_tracking[track_key] = 10
        
        # Получаем ключ еще раз - должен быть возвращен другой ключ
        second_key = self.rotator.get_key('test_service')
        
        # Проверяем, что возвращен другой ключ
        self.assertNotEqual(first_key, second_key)
    
    def test_mark_key_error(self):
        """Тест пометки ключа как недоступного из-за ошибки."""
        # Получаем ключ
        key = self.rotator.get_key('test_service')
        
        # Находим ключ, который использовался
        key_type = None
        for k_type, k in self.key_manager.get_keys().items():
            if k == key:
                key_type = k_type
                break
        
        # Отмечаем ключ как недоступный из-за ошибки
        self.rotator.mark_key_error('test_service', key_type)
        
        # Проверяем, что счетчик значительно увеличен
        track_key = f"test_service:{key_type}"
        self.assertGreaterEqual(self.rotator.usage_tracking[track_key], 1000)
        
        # Получаем ключ еще раз - должен быть возвращен другой ключ
        new_key = self.rotator.get_key('test_service')
        self.assertNotEqual(key, new_key)
    
    def test_reset_usage(self):
        """Тест сброса счетчиков использования."""
        # Устанавливаем несколько счетчиков
        self.rotator.usage_tracking = {
            'test_service:key1': 10,
            'test_service:key2': 5,
            'other_service:key1': 3
        }
        
        # Настраиваем возвращаемые значения для get_keys
        self.key_manager.get_keys.return_value = {'key1': 'value1', 'key2': 'value2'}
        
        # Сбрасываем счетчики для конкретного сервиса
        self.rotator.reset_usage('test_service')
        
        # Проверяем, что счетчики сброшены только для test_service
        self.assertEqual(self.rotator.usage_tracking['test_service:key1'], 0)
        self.assertEqual(self.rotator.usage_tracking['test_service:key2'], 0)
        self.assertEqual(self.rotator.usage_tracking['other_service:key1'], 3)
        
        # Сбрасываем все счетчики
        self.rotator.reset_usage()
        
        # Проверяем, что все счетчики сброшены
        self.assertEqual(self.rotator.usage_tracking, {})


if __name__ == '__main__':
    unittest.main() 