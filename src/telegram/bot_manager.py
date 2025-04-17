#!/usr/bin/env python
"""
Модуль для управления жизненным циклом Telegram бота.

Этот модуль содержит функции для:
- Проверки запущенных экземпляров бота
- Очистки кэша и временных файлов
- Запуска и перезапуска бота
- Обработки процессов завершения
"""

import os
import sys
import logging
from pathlib import Path
import shutil
import glob
import asyncio
import socket
import time
import json
import atexit
from src.telegram.bot_status import BotStatus

# Настройка базового логгера
def setup_logging():
    """Настраивает логгер для модуля управления ботом."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger("bot_manager")
    
    # Добавляем флаг отладки
    if os.getenv("BOT_DEBUG", "0") == "1":
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Уровень логирования изменен на DEBUG")
    
    return logger

logger = setup_logging()

# Добавляем флаг отладки
DEBUG_MODE = os.getenv("BOT_DEBUG", "0") == "1"

def clean_bot_state():
    """
    Очищает кэш Python и временные файлы бота перед запуском.
    
    Удаляет:
    - .pyc файлы
    - директории __pycache__
    - временные файлы состояний бота
    """
    logger.info("Начинаю очистку кэша и временных файлов...")
    
    # Очистка .pyc файлов и директорий __pycache__
    try:
        # Получаем корневую директорию проекта
        project_root = Path(__file__).parent.parent.parent.absolute()
        
        # Удаляем все .pyc файлы
        for pyc_file in glob.glob(str(project_root / "**/*.pyc"), recursive=True):
            try:
                os.remove(pyc_file)
                logger.debug(f"Удален файл {pyc_file}")
            except Exception as e:
                logger.warning(f"Не удалось удалить файл {pyc_file}: {e}")
        
        # Удаляем все директории __pycache__
        for pycache_dir in glob.glob(str(project_root / "**/__pycache__"), recursive=True):
            try:
                shutil.rmtree(pycache_dir)
                logger.debug(f"Удалена директория {pycache_dir}")
            except Exception as e:
                logger.warning(f"Не удалось удалить директорию {pycache_dir}: {e}")
        
        # Очистка временных файлов состояний, если используется хранилище в файлах
        try:
            temp_state_dir = project_root / "tmp" / "bot_states"
            if temp_state_dir.exists():
                shutil.rmtree(temp_state_dir)
                logger.info(f"Удалена директория временных состояний {temp_state_dir}")
        except Exception as e:
            logger.warning(f"Не удалось удалить директорию временных состояний: {e}")
        
        logger.info("Очистка кэша и временных файлов завершена успешно")
    except Exception as e:
        logger.error(f"Ошибка при очистке кэша и временных файлов: {e}")

def restart_bot():
    """
    Перезапускает текущий бот, используя BotStatus.
    """
    logger.info("Инициирован перезапуск бота")
    try:
        bot_status = BotStatus()
        bot_status.force_restart_bot()
    except Exception as e:
        logger.error(f"Ошибка при перезапуске бота: {e}")
        # Запасной вариант - используем прямую установку переменной окружения
        os.environ["BOT_RESTART_INITIATED"] = "1"
        os.system(f"python {sys.argv[0]}")
    finally:
        sys.exit(0)

def is_bot_already_running():
    """
    Проверяет, есть ли уже запущенный экземпляр бота.
    
    Использует класс BotStatus для управления состоянием бота.
    
    Returns:
        bool: True, если обнаружен другой экземпляр бота, иначе False
    """
    # Если включен режим отладки, пропускаем проверку
    if DEBUG_MODE:
        logger.warning("Включен режим отладки, пропускаем проверку наличия других экземпляров")
        return False
    
    # Используем BotStatus для проверки и управления состоянием бота
    bot_status = BotStatus()
    
    # Проверяем флаги перезапуска и игнорирования
    if os.getenv("BOT_RESTART_INITIATED") == "1" or os.getenv("BOT_IGNORE_RUNNING") == "1":
        logger.info("Обнаружен флаг перезапуска или игнорирования, пропускаем проверку наличия других экземпляров")
        return False
    
    # Получаем текущий PID и путь к скрипту
    current_pid = bot_status.get_current_pid()
    current_script = os.path.abspath(sys.argv[0]) if len(sys.argv) > 0 else ""
    
    logger.debug(f"Текущий процесс: PID={current_pid}, скрипт={current_script}")
    
    # Проверяем PID из файла
    existing_pid = bot_status.get_bot_pid_from_file()
    
    if existing_pid and existing_pid != current_pid:
        if bot_status.is_process_running(existing_pid):
            logger.warning(f"Найден работающий экземпляр бота (PID: {existing_pid})")
            
            # Запрашиваем состояние здоровья бота для логирования
            health = bot_status.get_bot_health()
            logger.debug(f"Состояние бота: {json.dumps(health, indent=2)}")
            
            return True
    
    # Записываем информацию о текущем процессе
    try:
        with open(bot_status.pid_file, 'w') as f:
            json.dump({
                'pid': current_pid,
                'start_time': time.time(),
                'script_path': current_script
            }, f)
        logger.debug(f"Создан PID-файл для текущего процесса (PID: {current_pid})")
    except Exception as e:
        logger.error(f"Не удалось создать PID-файл: {e}")
    
    # Дополнительная проверка через psutil для поиска других экземпляров
    try:
        import psutil
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Пропускаем текущий процесс
                if proc.pid == current_pid:
                    continue
                
                # Проверяем только процессы Python
                if not proc.name().lower().startswith('python'):
                    continue
                
                # Получаем командную строку процесса
                proc_cmdline = proc.cmdline()
                if len(proc_cmdline) <= 1:
                    continue
                
                # Проверяем, содержит ли командная строка ключевые слова нашего бота
                proc_cmd_str = ' '.join(proc_cmdline)
                if "run_bot.py" in proc_cmd_str and "telegram" in proc_cmd_str:
                    # Проверяем, запущен ли процесс слишком давно (более 1 часа)
                    if (time.time() - proc.create_time()) > 3600:  # 1 час
                        logger.warning(f"Найден процесс бота (PID: {proc.pid}), но он запущен более 1 часа назад. Считаем его зависшим.")
                        continue
                    
                    # Логируем информацию о найденном процессе
                    logger.warning(f"Найден работающий экземпляр бота (PID: {proc.pid})")
                    return True
            except Exception:
                # Пропускаем недоступные процессы
                continue
    except ImportError:
        logger.warning("Не удалось импортировать psutil для проверки других экземпляров")
    except Exception as e:
        logger.error(f"Ошибка при проверке наличия других экземпляров бота: {e}")
    
    logger.debug("Других экземпляров бота не обнаружено")
    return False

# Обработчик выхода для очистки PID-файла при завершении
def cleanup_on_exit():
    """Очищает PID-файл при завершении работы бота."""
    try:
        bot_status = BotStatus()
        bot_status.clear_pid_file()
        logger.debug("PID-файл удален при завершении работы")
    except Exception as e:
        logger.error(f"Ошибка при удалении PID-файла: {e}")

# Регистрируем обработчик выхода
atexit.register(cleanup_on_exit)

async def initialize_and_start_bot():
    """
    Инициализирует и запускает бота.
    
    Returns:
        int: Код завершения (0 - успех, 1 - ошибка)
    """
    try:
        # Проверяем наличие других экземпляров бота
        if is_bot_already_running():
            logger.warning("Обнаружен другой работающий экземпляр бота. Завершаем текущий процесс.")
            return 1
            
        # Импортируем модуль инициализации бота
        from src.telegram.bot_initializer import initialize_bot, start_bot
        
        logger.info("Начинаем инициализацию бота...")
        
        # Инициализируем бота и получаем необходимые объекты
        result = await initialize_bot()
        
        # Проверяем, вернул ли initialize_bot информацию о вебхуках
        if len(result) == 4:
            bot, dp, webhook_url, webhook_path = result
            # Получаем параметры для веб-приложения
            webapp_host = os.getenv("WEBAPP_HOST", "0.0.0.0")
            webapp_port = int(os.getenv("WEBAPP_PORT", "8443"))
            
            # Проверяем подключение к Telegram API
            logger.debug("Проверка подключения к Telegram API...")
            try:
                me = await bot.get_me()
                logger.info(f"Подключение к Telegram API успешно. Имя бота: {me.first_name}, username: @{me.username}")
            except Exception as e:
                logger.error(f"Ошибка подключения к Telegram API: {e}")
                return 1
                
            # Запускаем бота с вебхуками
            await start_bot(bot, dp, webhook_url, webhook_path, webapp_host, webapp_port)
        else:
            bot, dp = result
            
            # Проверяем подключение к Telegram API
            logger.debug("Проверка подключения к Telegram API...")
            try:
                me = await bot.get_me()
                logger.info(f"Подключение к Telegram API успешно. Имя бота: {me.first_name}, username: @{me.username}")
            except Exception as e:
                logger.error(f"Ошибка подключения к Telegram API: {e}")
                return 1
                
            # Запускаем бота без вебхуков
            await start_bot(bot, dp)
        
        return 0
    except ImportError as e:
        logger.exception(f"Ошибка импорта модулей бота: {e}")
        print(f"Ошибка импорта модулей бота: {e}")
        print("Проверьте структуру проекта и наличие всех необходимых файлов.")
        return 1

def setup_environment():
    """
    Настраивает окружение для запуска бота.
    
    Добавляет корневую директорию проекта в Python path.
    """
    # Добавляем корневую директорию проекта в sys.path
    project_root = Path(__file__).parent.parent.parent.absolute()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        logger.info(f"Добавлен {project_root} в Python path")

def run_bot():
    """
    Основная функция для запуска бота.
    Настраивает окружение и запускает бота.
    
    Returns:
        int: Код завершения (0 - успех, 1 - ошибка)
    """
    try:
        # Настраиваем окружение
        setup_environment()
        
        # Получаем текущий цикл событий вместо создания нового
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(initialize_and_start_bot())
        
    except Exception as e:
        logger.exception(f"Критическая ошибка при запуске бота: {e}")
        return 1 