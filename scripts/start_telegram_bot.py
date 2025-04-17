#!/usr/bin/env python
"""
Скрипт для запуска и перезапуска Telegram бота DMarket Trading.

Этот файл содержит простой интерфейс для управления ботом.
"""

import os
import sys
import argparse
from time import sleep
import logging

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("bot_launcher")

def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(description="Запуск и управление Telegram ботом DMarket Trading")
    
    # Добавляем аргументы командной строки
    parser.add_argument('--restart', action='store_true', help='Перезапустить бота, если он уже запущен')
    parser.add_argument('--clean', action='store_true', help='Очистить кэш и временные файлы перед запуском')
    parser.add_argument('--debug', action='store_true', help='Запустить бота в режиме отладки')
    parser.add_argument('--webhook', action='store_true', help='Включить режим работы с вебхуками')
    parser.add_argument('--host', help='Хост для вебхуков')
    parser.add_argument('--path', help='Путь для вебхуков')
    parser.add_argument('--port', type=int, help='Порт для вебхуков')
    
    return parser.parse_args()

def main():
    """Основная функция запуска бота"""
    args = parse_arguments()
    
    # Импортируем функции из src.telegram.run_bot
    try:
        from src.telegram.run_bot import main as run_main, restart_bot, clean_bot_state
        
        # Если указан аргумент --debug, включаем режим отладки
        if args.debug:
            os.environ["DEBUG"] = "1"
            logger.setLevel(logging.DEBUG)
            logger.info("Включен режим отладки")
        
        # Если указан аргумент --clean, очищаем кэш
        if args.clean:
            logger.info("Очистка кэша и временных файлов...")
            clean_bot_state()
        
        # Если указан аргумент --restart, перезапускаем бота
        if args.restart:
            logger.info("Перезапуск бота...")
            restart_bot()
            return 0
        
        # Если указан аргумент --webhook, включаем режим работы с вебхуками
        if args.webhook:
            if not args.host:
                logger.error("При использовании --webhook необходимо указать --host")
                return 1
            os.environ["USE_WEBHOOK"] = "true"
            os.environ["WEBHOOK_HOST"] = args.host
            if args.path:
                os.environ["WEBHOOK_PATH"] = args.path
            if args.port:
                os.environ["WEBAPP_PORT"] = str(args.port)
            logger.info(f"Включен режим вебхуков: {args.host}")
        
        # Запускаем бота
        return run_main()
        
    except ImportError as e:
        logger.error(f"Ошибка импорта модулей: {e}")
        logger.error("Убедитесь, что структура проекта корректна и запускайте скрипт из корневой директории проекта.")
        return 1
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 