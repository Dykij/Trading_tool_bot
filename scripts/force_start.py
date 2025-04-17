#!/usr/bin/env python
"""
Скрипт для принудительного запуска Telegram бота с игнорированием 
всех блокировок и проверок на запущенные экземпляры.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("force_start")

def force_start_bot():
    """
    Принудительный запуск бота с отключением всех блокировок.
    """
    logger.info("Принудительный запуск бота...")
    
    # Устанавливаем переменные окружения для игнорирования блокировок
    os.environ["BOT_DEBUG"] = "1"
    os.environ["BOT_IGNORE_RUNNING"] = "1"
    os.environ["BOT_RESTART_INITIATED"] = "0"
    
    # Очищаем файлы блокировок
    try:
        project_root = Path(__file__).parent.absolute()
        pid_file = project_root / "tmp" / "bot.pid"
        status_file = project_root / "tmp" / "bot_status.json"
        
        if pid_file.exists():
            pid_file.unlink()
            logger.info(f"Удален файл блокировки PID: {pid_file}")
        
        if status_file.exists():
            status_file.unlink()
            logger.info(f"Удален файл статуса: {status_file}")
    except Exception as e:
        logger.error(f"Ошибка при очистке файлов блокировок: {e}")
    
    # Формируем путь к скрипту бота
    bot_script = project_root / "src" / "telegram" / "run_bot.py"
    if not bot_script.exists():
        logger.error(f"Файл бота не найден по пути {bot_script}")
        return False
    
    logger.info(f"Запуск бота из {bot_script}")
    
    try:
        # Запускаем бот в отдельном процессе
        cmd = [sys.executable, str(bot_script)]
        logger.info(f"Выполняем команду: {' '.join(cmd)}")
        
        # Вариант 1: Запуск в фоновом режиме (Windows)
        if sys.platform == 'win32':
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        # Вариант 2: Запуск в фоновом режиме (Unix)
        else:
            subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
        logger.info("Бот успешно запущен в фоновом режиме")
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return False

if __name__ == "__main__":
    success = force_start_bot()
    print(f"Результат запуска: {'Успешно' if success else 'Ошибка'}") 