#!/usr/bin/env python
"""
Скрипт для принудительного завершения всех запущенных экземпляров бота.
Находит и завершает все процессы Python, которые запускают Telegram бота.
"""

import os
import sys
import json
import logging
import signal
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kill_bot")

def find_bot_processes():
    """
    Находит все запущенные процессы бота.
    
    Returns:
        list: Список процессов бота (объекты psutil.Process)
    """
    try:
        import psutil
    except ImportError:
        logger.error("Необходима библиотека psutil. Установите её с помощью 'pip install psutil'")
        return []
    
    bot_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Проверяем только процессы Python
            if not proc.name().lower().startswith('python'):
                continue
            
            # Получаем командную строку процесса
            cmdline = proc.cmdline()
            if len(cmdline) <= 1:
                continue
            
            cmd_str = ' '.join(cmdline)
            
            # Ищем процессы бота по ключевым словам в командной строке
            if "run_bot.py" in cmd_str and "telegram" in cmd_str:
                bot_processes.append(proc)
                logger.info(f"Найден процесс бота: PID={proc.pid}, командная строка: {cmd_str}")
        except Exception:
            # Пропускаем недоступные процессы
            continue
    
    return bot_processes

def kill_bot_processes(bot_processes):
    """
    Завершает все найденные процессы бота.
    
    Args:
        bot_processes (list): Список процессов бота
    
    Returns:
        int: Количество завершенных процессов
    """
    if not bot_processes:
        logger.info("Запущенных экземпляров бота не найдено")
        return 0
    
    killed_count = 0
    
    for proc in bot_processes:
        try:
            logger.info(f"Завершение процесса бота (PID: {proc.pid})...")
            
            # Завершаем процесс
            if sys.platform == 'win32':
                proc.kill()
            else:
                # В Unix можно использовать более мягкий сигнал SIGTERM сначала
                os.kill(proc.pid, signal.SIGTERM)
                
                # Даем процессу время на завершение
                import time
                time.sleep(1)
                
                # Если процесс все еще работает, используем SIGKILL
                if proc.is_running():
                    os.kill(proc.pid, signal.SIGKILL)
            
            logger.info(f"Процесс бота (PID: {proc.pid}) успешно завершен")
            killed_count += 1
        except Exception as e:
            logger.error(f"Ошибка при завершении процесса бота (PID: {proc.pid}): {e}")
    
    return killed_count

def clear_bot_locks():
    """
    Очищает файлы блокировок бота.
    
    Returns:
        bool: True, если операция успешна, иначе False
    """
    try:
        # Получаем путь к файлам блокировок
        project_root = Path(__file__).parent.absolute()
        pid_file = project_root / "tmp" / "bot.pid"
        status_file = project_root / "tmp" / "bot_status.json"
        
        # Удаляем файл PID
        if pid_file.exists():
            pid_file.unlink()
            logger.info(f"Удален файл блокировки PID: {pid_file}")
        
        # Обновляем файл статуса
        if status_file.exists():
            try:
                with open(status_file, 'r') as f:
                    status = json.load(f)
            except:
                status = {}
            
            status.update({
                "locks_reset": True,
                "killed_time": __import__('time').time()
            })
            
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)
            logger.info(f"Обновлен файл статуса: {status_file}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при очистке файлов блокировок: {e}")
        return False

def main():
    """
    Главная функция скрипта.
    """
    logger.info("Поиск и завершение запущенных экземпляров бота...")
    
    # Находим процессы бота
    bot_processes = find_bot_processes()
    
    # Завершаем найденные процессы
    killed_count = kill_bot_processes(bot_processes)
    
    # Очищаем файлы блокировок
    locks_cleared = clear_bot_locks()
    
    result = {
        "found_processes": len(bot_processes),
        "killed_processes": killed_count,
        "locks_cleared": locks_cleared
    }
    
    logger.info(f"Итоги операции: {json.dumps(result, indent=2)}")
    print(f"Результат: найдено {len(bot_processes)}, завершено {killed_count}, блокировки очищены: {locks_cleared}")
    
    return result

if __name__ == "__main__":
    main() 