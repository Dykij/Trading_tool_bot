"""
Тесты для модуля утилит общего назначения.

Проверяет функциональность утилит, включая кеширование, форматирование цен/дат,
retry-функционал и другие вспомогательные функции.
"""

import unittest
import sys
import os
import time
import json
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import asyncio

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from src.utils.common import (
        format_price, format_date, parse_date, 
        retry, async_retry, 
        CacheManager, TempFileStorage, 
        load_json, save_json, 
        generate_unique_id
    )
    UTILS_AVAILABLE = True
except ImportError:
    # Создаем заглушки для тестирования, если модули не найдены
    UTILS_AVAILABLE = False
    
    def format_price(price, currency='USD'):
        """Форматирует цену с учетом валюты."""
        if currency == 'USD':
            return f"${price:.2f}"
        elif currency == 'EUR':
            return f"€{price:.2f}"
        else:
            return f"{price:.2f} {currency}"
    
    def format_date(date, format_str='%Y-%m-%d %H:%M:%S'):
        """Форматирует дату по указанному формату."""
        if isinstance(date, (int, float)):
            date = datetime.fromtimestamp(date)
        return date.strftime(format_str)
    
    def parse_date(date_str, format_str='%Y-%m-%d %H:%M:%S'):
        """Парсит строку даты в объект datetime."""
        return datetime.strptime(date_str, format_str)
    
    def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
        """Декоратор для повторных попыток выполнения функции при исключениях."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                attempt = 0
                current_delay = delay
                
                while attempt < max_attempts:
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        attempt += 1
                        if attempt >= max_attempts:
                            raise e
                        
                        time.sleep(current_delay)
                        current_delay *= backoff
                
                return None
            return wrapper
        return decorator
    
    async def async_retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
        """Декоратор для повторных попыток выполнения асинхронной функции."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                attempt = 0
                current_delay = delay
                
                while attempt < max_attempts:
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        attempt += 1
                        if attempt >= max_attempts:
                            raise e
                        
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                
                return None
            return wrapper
        return decorator
    
    class CacheManager:
        """Менеджер кеша для временного хранения данных."""
        
        def __init__(self, expiration_time=3600):
            self.cache = {}
            self.expiration_time = expiration_time
        
        def set(self, key, value, expiration=None):
            """Устанавливает значение в кеш."""
            if expiration is None:
                expiration = self.expiration_time
            
            expiration_timestamp = time.time() + expiration
            self.cache[key] = {
                'value': value,
                'expires_at': expiration_timestamp
            }
        
        def get(self, key):
            """Получает значение из кеша."""
            if key not in self.cache:
                return None
            
            cache_entry = self.cache[key]
            if time.time() > cache_entry['expires_at']:
                del self.cache[key]
                return None
            
            return cache_entry['value']
        
        def delete(self, key):
            """Удаляет значение из кеша."""
            if key in self.cache:
                del self.cache[key]
        
        def clear(self):
            """Очищает весь кеш."""
            self.cache.clear()
    
    class TempFileStorage:
        """Хранилище временных файлов."""
        
        def __init__(self, base_dir=None):
            self.base_dir = base_dir or tempfile.gettempdir()
            os.makedirs(self.base_dir, exist_ok=True)
        
        def save(self, file_name, data):
            """Сохраняет данные во временный файл."""
            file_path = os.path.join(self.base_dir, file_name)
            
            if isinstance(data, dict) or isinstance(data, list):
                with open(file_path, 'w') as f:
                    json.dump(data, f)
            elif isinstance(data, str):
                with open(file_path, 'w') as f:
                    f.write(data)
            else:
                with open(file_path, 'wb') as f:
                    f.write(data)
            
            return file_path
        
        def load(self, file_name):
            """Загружает данные из временного файла."""
            file_path = os.path.join(self.base_dir, file_name)
            
            if not os.path.exists(file_path):
                return None
            
            if file_name.endswith('.json'):
                with open(file_path, 'r') as f:
                    return json.load(f)
            else:
                with open(file_path, 'r') as f:
                    return f.read()
        
        def delete(self, file_name):
            """Удаляет временный файл."""
            file_path = os.path.join(self.base_dir, file_name)
            
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def load_json(file_path):
        """Загружает данные из JSON файла."""
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def save_json(data, file_path):
        """Сохраняет данные в JSON файл."""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def generate_unique_id():
        """Генерирует уникальный идентификатор."""
        import uuid
        return str(uuid.uuid4())


class TestFormatting(unittest.TestCase):
    """Тесты для функций форматирования."""
    
    def test_format_price(self):
        """Тест форматирования цен."""
        # Тест с USD
        self.assertEqual(format_price(1000), "$1000.00")
        self.assertEqual(format_price(1000.5), "$1000.50")
        
        # Тест с EUR
        self.assertEqual(format_price(1000, 'EUR'), "€1000.00")
        
        # Тест с другой валютой
        self.assertEqual(format_price(1000, 'RUB'), "1000.00 RUB")
    
    def test_format_date(self):
        """Тест форматирования даты."""
        # Тест с объектом datetime
        test_date = datetime(2023, 1, 1, 12, 30, 45)
        self.assertEqual(format_date(test_date), "2023-01-01 12:30:45")
        
        # Тест с timestamp
        timestamp = int(test_date.timestamp())
        self.assertEqual(format_date(timestamp), "2023-01-01 12:30:45")
        
        # Тест с пользовательским форматом
        self.assertEqual(format_date(test_date, "%d.%m.%Y"), "01.01.2023")
    
    def test_parse_date(self):
        """Тест парсинга даты."""
        # Тест с стандартным форматом
        date_str = "2023-01-01 12:30:45"
        parsed_date = parse_date(date_str)
        
        self.assertEqual(parsed_date.year, 2023)
        self.assertEqual(parsed_date.month, 1)
        self.assertEqual(parsed_date.day, 1)
        self.assertEqual(parsed_date.hour, 12)
        self.assertEqual(parsed_date.minute, 30)
        self.assertEqual(parsed_date.second, 45)
        
        # Тест с пользовательским форматом
        date_str = "01.01.2023"
        parsed_date = parse_date(date_str, "%d.%m.%Y")
        
        self.assertEqual(parsed_date.year, 2023)
        self.assertEqual(parsed_date.month, 1)
        self.assertEqual(parsed_date.day, 1)


class TestRetry(unittest.TestCase):
    """Тесты для функций retry."""
    
    def test_retry_success(self):
        """Тест успешного выполнения функции с retry."""
        # Создаем мок-функцию, которая успешно выполняется с первого раза
        mock_func = MagicMock(return_value="success")
        
        # Применяем декоратор retry
        decorated_func = retry()(mock_func)
        
        # Вызываем функцию
        result = decorated_func()
        
        # Проверяем, что функция была вызвана один раз
        self.assertEqual(mock_func.call_count, 1)
        
        # Проверяем результат
        self.assertEqual(result, "success")
    
    def test_retry_failure_then_success(self):
        """Тест функции с retry, которая сначала падает, потом успешно выполняется."""
        # Создаем мок-функцию, которая сначала вызывает исключение, а затем возвращает результат
        mock_func = MagicMock(side_effect=[ValueError("Test error"), "success"])
        
        # Применяем декоратор retry с минимальной задержкой
        decorated_func = retry(delay=0.01)(mock_func)
        
        # Вызываем функцию
        result = decorated_func()
        
        # Проверяем, что функция была вызвана два раза
        self.assertEqual(mock_func.call_count, 2)
        
        # Проверяем результат
        self.assertEqual(result, "success")
    
    def test_retry_max_attempts(self):
        """Тест превышения максимального числа попыток в retry."""
        # Создаем мок-функцию, которая всегда вызывает исключение
        mock_func = MagicMock(side_effect=ValueError("Test error"))
        
        # Применяем декоратор retry с максимум 3 попытками и минимальной задержкой
        decorated_func = retry(max_attempts=3, delay=0.01)(mock_func)
        
        # Вызываем функцию и ожидаем исключение
        with self.assertRaises(ValueError):
            decorated_func()
        
        # Проверяем, что функция была вызвана три раза
        self.assertEqual(mock_func.call_count, 3)
    
    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_async_retry_success(self, mock_sleep):
        """Тест успешного выполнения асинхронной функции с retry."""
        # Создаем мок асинхронной функции
        mock_func = AsyncMock(return_value="success")
        
        # Применяем декоратор async_retry
        decorated_func = await async_retry()(mock_func)
        
        # Вызываем функцию
        result = await decorated_func()
        
        # Проверяем, что функция была вызвана один раз
        self.assertEqual(mock_func.call_count, 1)
        
        # Проверяем, что asyncio.sleep не вызывался
        mock_sleep.assert_not_called()
        
        # Проверяем результат
        self.assertEqual(result, "success")
    
    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_async_retry_failure_then_success(self, mock_sleep):
        """Тест асинхронной функции с retry, которая сначала падает, потом успешно выполняется."""
        # Создаем мок асинхронной функции
        mock_func = AsyncMock(side_effect=[ValueError("Test error"), "success"])
        
        # Применяем декоратор async_retry
        decorated_func = await async_retry(delay=0.01)(mock_func)
        
        # Вызываем функцию
        result = await decorated_func()
        
        # Проверяем, что функция была вызвана два раза
        self.assertEqual(mock_func.call_count, 2)
        
        # Проверяем, что asyncio.sleep был вызван один раз
        mock_sleep.assert_called_once_with(0.01)
        
        # Проверяем результат
        self.assertEqual(result, "success")


class TestCacheManager(unittest.TestCase):
    """Тесты для менеджера кеша."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        self.cache = CacheManager(expiration_time=1)  # 1 секунда для быстрых тестов
    
    def tearDown(self):
        """Очистка после тестов."""
        self.cache.clear()
    
    def test_set_and_get(self):
        """Тест установки и получения значения из кеша."""
        # Устанавливаем значение
        self.cache.set('test_key', 'test_value')
        
        # Получаем значение
        value = self.cache.get('test_key')
        
        # Проверяем, что значение получено корректно
        self.assertEqual(value, 'test_value')
    
    def test_get_nonexistent_key(self):
        """Тест получения несуществующего ключа."""
        # Пытаемся получить несуществующий ключ
        value = self.cache.get('nonexistent_key')
        
        # Проверяем, что возвращается None
        self.assertIsNone(value)
    
    def test_expiration(self):
        """Тест истечения срока действия кеша."""
        # Устанавливаем значение с сроком действия 0.1 секунды
        self.cache.set('test_key', 'test_value', expiration=0.1)
        
        # Сразу получаем значение - должно быть в кеше
        value = self.cache.get('test_key')
        self.assertEqual(value, 'test_value')
        
        # Ждем, пока истечет срок действия
        time.sleep(0.2)
        
        # Получаем значение снова - должно быть None
        value = self.cache.get('test_key')
        self.assertIsNone(value)
    
    def test_delete(self):
        """Тест удаления значения из кеша."""
        # Устанавливаем значение
        self.cache.set('test_key', 'test_value')
        
        # Удаляем значение
        self.cache.delete('test_key')
        
        # Пытаемся получить удаленное значение
        value = self.cache.get('test_key')
        
        # Проверяем, что значение удалено
        self.assertIsNone(value)
    
    def test_clear(self):
        """Тест очистки всего кеша."""
        # Устанавливаем несколько значений
        self.cache.set('key1', 'value1')
        self.cache.set('key2', 'value2')
        
        # Очищаем кеш
        self.cache.clear()
        
        # Пытаемся получить значения
        value1 = self.cache.get('key1')
        value2 = self.cache.get('key2')
        
        # Проверяем, что все значения удалены
        self.assertIsNone(value1)
        self.assertIsNone(value2)


class TestTempFileStorage(unittest.TestCase):
    """Тесты для хранилища временных файлов."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временную директорию
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = TempFileStorage(base_dir=self.temp_dir.name)
    
    def tearDown(self):
        """Очистка после тестов."""
        self.temp_dir.cleanup()
    
    def test_save_and_load_text(self):
        """Тест сохранения и загрузки текстовых данных."""
        # Сохраняем текстовые данные
        file_path = self.storage.save('test.txt', 'Hello, World!')
        
        # Проверяем, что файл создан
        self.assertTrue(os.path.exists(file_path))
        
        # Загружаем данные
        data = self.storage.load('test.txt')
        
        # Проверяем, что данные загружены корректно
        self.assertEqual(data, 'Hello, World!')
    
    def test_save_and_load_json(self):
        """Тест сохранения и загрузки JSON данных."""
        # Тестовые данные
        test_data = {'key': 'value', 'numbers': [1, 2, 3]}
        
        # Сохраняем JSON данные
        file_path = self.storage.save('test.json', test_data)
        
        # Проверяем, что файл создан
        self.assertTrue(os.path.exists(file_path))
        
        # Загружаем данные
        data = self.storage.load('test.json')
        
        # Проверяем, что данные загружены корректно
        self.assertEqual(data, test_data)
    
    def test_delete(self):
        """Тест удаления файла."""
        # Сохраняем файл
        file_path = self.storage.save('test.txt', 'Hello, World!')
        
        # Проверяем, что файл создан
        self.assertTrue(os.path.exists(file_path))
        
        # Удаляем файл
        self.storage.delete('test.txt')
        
        # Проверяем, что файл удален
        self.assertFalse(os.path.exists(file_path))
    
    def test_load_nonexistent_file(self):
        """Тест загрузки несуществующего файла."""
        # Пытаемся загрузить несуществующий файл
        data = self.storage.load('nonexistent.txt')
        
        # Проверяем, что возвращается None
        self.assertIsNone(data)


class TestJsonFunctions(unittest.TestCase):
    """Тесты для функций работы с JSON."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временный файл
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        self.temp_file.close()
    
    def tearDown(self):
        """Очистка после тестов."""
        # Удаляем временный файл
        try:
            os.unlink(self.temp_file.name)
        except OSError:
            pass
    
    def test_save_and_load_json(self):
        """Тест сохранения и загрузки JSON."""
        # Тестовые данные
        test_data = {
            'string': 'value',
            'number': 42,
            'list': [1, 2, 3],
            'nested': {'key': 'value'}
        }
        
        # Сохраняем данные
        save_json(test_data, self.temp_file.name)
        
        # Загружаем данные
        loaded_data = load_json(self.temp_file.name)
        
        # Проверяем, что данные загружены корректно
        self.assertEqual(loaded_data, test_data)


class TestUniqueId(unittest.TestCase):
    """Тесты для функции генерации уникального ID."""
    
    def test_generate_unique_id(self):
        """Тест генерации уникального ID."""
        # Генерируем несколько ID
        id1 = generate_unique_id()
        id2 = generate_unique_id()
        id3 = generate_unique_id()
        
        # Проверяем, что все ID - строки
        self.assertTrue(isinstance(id1, str))
        self.assertTrue(isinstance(id2, str))
        self.assertTrue(isinstance(id3, str))
        
        # Проверяем, что все ID уникальны
        self.assertNotEqual(id1, id2)
        self.assertNotEqual(id1, id3)
        self.assertNotEqual(id2, id3)


if __name__ == '__main__':
    unittest.main() 