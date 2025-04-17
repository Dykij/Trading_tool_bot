#!/usr/bin/env python
"""
Инструмент для программной оптимизации API-функций в коде DMarket Trading Bot.

Позволяет автоматически применять оптимизации к API в существующем коде:
- Добавление кэширования к методам API
- Добавление логирования и профилирования
- Интеллектуальная обработка ошибок и повторные попытки
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List

from src.utils.code_tools.function_optimizer import optimize_functions

logger = logging.getLogger(__name__)

DEFAULT_OPTIMIZATIONS = {
    # Методы получения данных с рынка (кэширование 30 секунд)
    "get_market_items": {
        "decorator_list": "@optimize_api_method(cache_ttl=30, enable_profiling=True)\n@timer",
        "body": None  # Не меняем тело функции
    },
    # Методы получения информации о предметах (кэширование 5 минут)
    "get_item_details": {
        "decorator_list": "@optimize_api_method(cache_ttl=300, enable_profiling=True)\n@timer",
        "body": None
    },
    # Методы поиска (короткое кэширование 15 секунд)
    "search_market_items": {
        "decorator_list": "@optimize_api_method(cache_ttl=15, enable_profiling=True)\n@timer",
        "body": None
    },
    # Важные методы не кэшируем, но добавляем профилирование и повторные попытки
    "get_user_balance": {
        "decorator_list": "@optimize_api_method(cache_ttl=0, enable_profiling=True)\n@retry(max_attempts=3)",
        "body": None
    },
    "create_offer": {
        "decorator_list": "@optimize_api_method(cache_ttl=0, enable_profiling=True)\n@retry(max_attempts=3)",
        "body": None
    },
    "cancel_offer": {
        "decorator_list": "@optimize_api_method(cache_ttl=0, enable_profiling=True)\n@retry(max_attempts=3)",
        "body": None
    },
    "buy_item": {
        "decorator_list": "@optimize_api_method(cache_ttl=0, enable_profiling=True)\n@retry(max_attempts=3)",
        "body": None
    }
}

def apply_api_optimizations(source_code: str, methods_to_optimize: Dict[str, Dict[str, Any]] = None) -> str:
    """
    Применяет оптимизации API к исходному коду.
    
    Args:
        source_code: Исходный код Python
        methods_to_optimize: Словарь с методами для оптимизации и их параметрами
            
    Returns:
        Оптимизированный исходный код
    """
    if methods_to_optimize is None:
        methods_to_optimize = DEFAULT_OPTIMIZATIONS
    
    # Добавляем импорты, если их нет
    imports_to_add = [
        "from src.utils.api_optimizer import optimize_api_method",
        "from src.utils.function_optimizer import optimizer"
    ]
    
    # Проверяем, есть ли уже импорты
    for import_line in imports_to_add:
        if import_line not in source_code:
            module_name = import_line.split("import ")[1].split(".")[0]
            if f"import {module_name}" not in source_code and f"from {module_name}" not in source_code:
                source_code = import_line + "\n" + source_code
    
    # Применяем оптимизации
    optimized_code = optimize_functions(source_code, methods_to_optimize)
    
    return optimized_code

def main():
    """
    Основная функция CLI-интерфейса для оптимизации API-функций.
    """
    parser = argparse.ArgumentParser(description="Оптимизация API-функций в исходном коде")
    parser.add_argument("source_file", help="Путь к исходному файлу Python с API-функциями")
    parser.add_argument("--output", "-o", help="Путь для сохранения результата (по умолчанию перезаписывает исходный файл)")
    parser.add_argument("--config", "-c", help="Путь к JSON-файлу с настройками оптимизации")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    args = parser.parse_args()
    
    # Настройка логирования
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")
    
    try:
        # Чтение исходного файла
        source_path = Path(args.source_file)
        logger.info(f"Чтение исходного файла: {source_path}")
        with open(source_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Чтение настроек оптимизации из JSON, если указан
        optimizations = DEFAULT_OPTIMIZATIONS
        if args.config:
            config_path = Path(args.config)
            logger.info(f"Чтение настроек оптимизации из: {config_path}")
            with open(config_path, 'r', encoding='utf-8') as f:
                optimizations.update(json.load(f))
        
        logger.info(f"Найдено {len(optimizations)} методов для оптимизации")
        
        # Применение оптимизаций
        optimized_code = apply_api_optimizations(source_code, optimizations)
        
        # Сохранение результата
        output_path = args.output if args.output else source_path
        logger.info(f"Сохранение результата в: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(optimized_code)
        
        logger.info(f"Оптимизация успешно завершена")
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 