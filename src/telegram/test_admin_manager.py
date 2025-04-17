#!/usr/bin/env python
"""
Тестирование модуля admin_manager.
"""

import os
import sys
import unittest
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Импортируем функции из модуля admin_manager
from src.telegram.admin_manager import (
    is_admin, 
    get_admin_ids, 
    update_admin_cache, 
    admin_manager
)

class TestAdminManager(unittest.TestCase):
    """Тесты для модуля admin_manager."""
    
    def setUp(self):
        """Подготовка тестов."""
        # Сохраняем оригинальное значение переменной окружения
        self.original_admin_ids = os.environ.get("ADMIN_IDS", "")
        
    def tearDown(self):
        """Очистка после тестов."""
        # Восстанавливаем оригинальное значение переменной окружения
        os.environ["ADMIN_IDS"] = self.original_admin_ids
        # Обновляем кэш админов
        update_admin_cache()
        
    def test_empty_admin_ids(self):
        """Тест обработки пустого списка админов."""
        # Устанавливаем пустое значение
        os.environ["ADMIN_IDS"] = ""
        # Обновляем кэш
        update_admin_cache()
        
        # Проверяем, что список админов пуст
        self.assertEqual(get_admin_ids(), [])
        # Проверяем, что никто не является админом
        self.assertFalse(is_admin(12345))
        self.assertFalse(is_admin(67890))
        
    def test_single_admin_id(self):
        """Тест обработки одного админа."""
        # Устанавливаем один ID админа
        os.environ["ADMIN_IDS"] = "12345"
        # Обновляем кэш
        update_admin_cache()
        
        # Проверяем, что список админов содержит один ID
        self.assertEqual(get_admin_ids(), [12345])
        # Проверяем корректность проверки
        self.assertTrue(is_admin(12345))
        self.assertFalse(is_admin(67890))
        
    def test_multiple_admin_ids(self):
        """Тест обработки нескольких админов."""
        # Устанавливаем несколько ID админов
        os.environ["ADMIN_IDS"] = "12345,67890,98765"
        # Обновляем кэш
        update_admin_cache()
        
        # Проверяем, что список админов содержит все ID
        self.assertEqual(set(get_admin_ids()), {12345, 67890, 98765})
        # Проверяем корректность проверки
        self.assertTrue(is_admin(12345))
        self.assertTrue(is_admin(67890))
        self.assertTrue(is_admin(98765))
        self.assertFalse(is_admin(11111))
        
    def test_invalid_admin_ids(self):
        """Тест обработки некорректных ID админов."""
        # Устанавливаем список с корректными и некорректными ID
        os.environ["ADMIN_IDS"] = "12345,invalid,67890,another_invalid"
        # Обновляем кэш
        update_admin_cache()
        
        # Проверяем, что в списке админов только корректные ID
        self.assertEqual(set(get_admin_ids()), {12345, 67890})
        # Проверяем корректность проверки
        self.assertTrue(is_admin(12345))
        self.assertTrue(is_admin(67890))
        self.assertFalse(is_admin(11111))
        
    def test_cache_update(self):
        """Тест обновления кэша."""
        # Устанавливаем начальное значение
        os.environ["ADMIN_IDS"] = "12345"
        # Обновляем кэш
        update_admin_cache()
        
        # Проверяем корректность проверки с начальным значением
        self.assertTrue(is_admin(12345))
        self.assertFalse(is_admin(67890))
        
        # Изменяем значение переменной окружения
        os.environ["ADMIN_IDS"] = "67890"
        # Явно обновляем кэш
        update_admin_cache()
        
        # Проверяем, что кэш обновился
        self.assertFalse(is_admin(12345))
        self.assertTrue(is_admin(67890))

if __name__ == "__main__":
    unittest.main() 