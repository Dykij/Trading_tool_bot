#!/usr/bin/env python
"""
Скрипт для ручного перезапуска Telegram бота.
Полностью очищает кэш Python и перезапускает бота.
"""

import os
import sys
import shutil
import glob
import time
import logging
import subprocess
from pathlib import Path

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("restart_bot")

def clean_python_cache():
    """
    Полностью очищает кэш Python, удаляя все .pyc файлы и директории __pycache__
    """
    logger.info("Очистка кэша Python...")
    
    # Удаляем все .pyc файлы
    pyc_count = 0
    for pyc_file in glob.glob("**/*.pyc", recursive=True):
        try:
            os.remove(pyc_file)
            pyc_count += 1
        except Exception as e:
            logger.warning(f"Не удалось удалить {pyc_file}: {e}")
    
    logger.info(f"Удалено {pyc_count} .pyc файлов")
    
    # Удаляем все директории __pycache__
    pycache_count = 0
    for pycache_dir in glob.glob("**/__pycache__", recursive=True):
        try:
            shutil.rmtree(pycache_dir)
            pycache_count += 1
        except Exception as e:
            logger.warning(f"Не удалось удалить {pycache_dir}: {e}")
    
    logger.info(f"Удалено {pycache_count} директорий __pycache__")

def kill_existing_bot():
    """
    Останавливает существующие процессы бота, если они запущены.
    Только для Windows.
    """
    try:
        # На Windows используем tasklist и taskkill
        if os.name == 'nt':
            # Ищем процессы Python, которые запущены с telegram_bot.py или run_bot.py
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # Пропускаем заголовок
                if len(lines) > 1:
                    for line in lines[1:]:
                        # Парсим вывод в формате CSV
                        parts = line.strip('"').split('","')
                        if len(parts) >= 2:
                            pid = parts[1]
                            # Проверяем, это процесс нашего бота или нет
                            process_info = subprocess.run(
                                ['wmic', 'process', 'where', f'ProcessId={pid}', 'get', 'CommandLine'],
                                capture_output=True, 
                                text=True
                            )
                            
                            # Если это наш бот, останавливаем его
                            if 'telegram_bot.py' in process_info.stdout or 'run_bot.py' in process_info.stdout:
                                logger.info(f"Останавливаем процесс бота с PID {pid}")
                                subprocess.run(['taskkill', '/F', '/PID', pid])
        
        # Даем некоторое время для завершения процессов
        time.sleep(2)
        logger.info("Остановка существующих процессов бота завершена")
    except Exception as e:
        logger.error(f"Ошибка при остановке процессов бота: {e}")

def restart_bot():
    """
    Перезапускает Telegram бота
    """
    # Получаем путь к скрипту запуска бота
    project_dir = Path(__file__).parent.parent.parent
    run_bot_script = project_dir / "src" / "telegram" / "run_bot.py"
    
    # Проверяем, что скрипт существует
    if not run_bot_script.exists():
        logger.error(f"Скрипт запуска бота не найден по пути {run_bot_script}")
        return False
    
    try:
        # Останавливаем существующие процессы бота
        kill_existing_bot()
        
        # Очищаем кэш Python
        clean_python_cache()
        
        # Запускаем бота
        logger.info(f"Запуск бота из {run_bot_script}")
        
        # Изменяем текущую директорию на корневую директорию проекта
        os.chdir(project_dir)
        
        # Запускаем процесс бота
        bot_process = subprocess.Popen([sys.executable, str(run_bot_script)])
        
        logger.info(f"Бот запущен с PID {bot_process.pid}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при перезапуске бота: {e}")
        return False

if __name__ == "__main__":
    print("Перезапуск Telegram бота...")
    if restart_bot():
        print("Бот успешно перезапущен!")
    else:
        print("Не удалось перезапустить бота. Проверьте логи.") 