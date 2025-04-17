#!/usr/bin/env python
"""
Инструмент для программной модификации функций в коде DMarket Trading Bot.

Использование:
    python -m src.utils.code_tools.optimize_script файл.py обновления.json
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from .function_optimizer import optimize_functions

def main():
    """
    Основная функция CLI-интерфейса для оптимизации функций.
    """
    parser = argparse.ArgumentParser(description="Оптимизация функций в исходном коде")
    parser.add_argument("source_file", help="Путь к исходному файлу Python")
    parser.add_argument("updates_file", help="Путь к JSON-файлу с обновлениями функций")
    parser.add_argument("--output", "-o", help="Путь для сохранения результата (по умолчанию перезаписывает исходный файл)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    args = parser.parse_args()
    
    # Настройка логирования
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")
    logger = logging.getLogger("optimize_script")
    
    try:
        # Чтение исходного файла
        source_path = Path(args.source_file)
        logger.info(f"Чтение исходного файла: {source_path}")
        with open(source_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Чтение обновлений из JSON
        updates_path = Path(args.updates_file)
        logger.info(f"Чтение обновлений из: {updates_path}")
        with open(updates_path, 'r', encoding='utf-8') as f:
            function_updates = json.load(f)
        
        logger.info(f"Найдено {len(function_updates)} функций для оптимизации")
        
        # Применение обновлений
        optimized_code = optimize_functions(source_code, function_updates)
        
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
