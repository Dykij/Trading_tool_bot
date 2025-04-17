"""
Модуль инициализации Telegram бота.

Содержит функции для инициализации зависимостей бота, настройки
окружения и запуска бота в правильном порядке.
"""

import os
import sys
import logging
import types
import shutil
import glob
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# Настройка логирования
logger = logging.getLogger(__name__)

def setup_environment():
    """
    Настраивает окружение для работы бота.
    
    - Определяет корневую директорию проекта
    - Загружает переменные окружения из .env файла
    - Добавляет директорию проекта в sys.path для импорта модулей
    
    Returns:
        Path: Путь к корневой директории проекта
    """
    # Получаем корневую директорию проекта (2 уровня вверх от текущего файла)
    # src/telegram/bot_initializer.py -> src/ -> project_root/
    project_root = Path(__file__).parent.parent.parent.absolute()
    
    # Загружаем переменные окружения из .env файла
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"Загружены переменные окружения из {env_file}")
    else:
        logger.warning(f"Файл .env не найден по пути {env_file}")
    
    # Добавляем корневую директорию проекта в sys.path, если её там ещё нет
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        logger.info(f"Добавлен {project_root} в Python path")
    
    # Выводим информацию об окружении для отладки
    logger.info(f"Версия Python: {sys.version}")
    logger.info(f"Текущая рабочая директория: {os.getcwd()}")
    
    return project_root

def clean_cache():
    """
    Очищает кэш Python перед запуском бота
    для предотвращения проблем с перезагрузкой модулей.
    """
    # Удаляем все файлы .pyc и очищаем директории __pycache__
    try:
        # Очищаем кэш Python - сначала удаляем все .pyc файлы
        for pyc_file in glob.glob("**/*.pyc", recursive=True):
            try:
                os.remove(pyc_file)
                logger.debug(f"Удален файл {pyc_file}")
            except Exception as e:
                logger.warning(f"Не удалось удалить файл {pyc_file}: {e}")
        
        # Затем удаляем все директории __pycache__
        for pycache_dir in glob.glob("**/__pycache__", recursive=True):
            try:
                shutil.rmtree(pycache_dir)
                logger.info(f"Очищена директория {pycache_dir}")
            except Exception as e:
                logger.warning(f"Не удалось очистить директорию {pycache_dir}: {e}")
        
        logger.info("Очистка кэша Python успешно завершена")
    except Exception as e:
        logger.error(f"Ошибка при очистке кэша: {e}")

def clean_modules():
    """
    Удаляет проблемные модули из sys.modules перед импортом.
    """
    modules_to_reload = [
        'src.telegram.decorators', 
        'src.telegram.callbacks', 
        'src.bot.handlers.commands',
        'src.telegram.telegram_bot'
    ]
    
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            logger.info(f"Удаление модуля {module_name} из sys.modules")
            del sys.modules[module_name]

def setup_module_aliases():
    """
    Настраивает псевдонимы модулей для удобства импорта.
    
    Пытается импортировать модули из разных источников 
    и создает псевдонимы для них в sys.modules.
    
    Returns:
        bool: True если все необходимые модули найдены, False в противном случае
    """
    try:
        # Пробуем импортировать необходимые модули из src
        import_src_modules()
        
        # Проверяем наличие необходимых модулей
        required_modules = ['api_wrapper', 'ml_predictor']
        missing_modules = [module for module in required_modules if module not in sys.modules]
        
        # Если есть отсутствующие модули, возвращаем False
        if missing_modules:
            logger.warning(f"Отсутствуют необходимые модули: {', '.join(missing_modules)}")
            return False
        
        return True
        
    except ImportError as e:
        # В случае ошибки импорта, пробуем запасной вариант
        logger.error(f"Ошибка при настройке псевдонимов модулей: {e}")
        try:
            # Пробуем импортировать из DM
            import_dm_modules()
            
            # Проверяем наличие необходимых модулей
            required_modules = ['api_wrapper', 'ml_predictor']
            missing_modules = [module for module in required_modules if module not in sys.modules]
            
            # Если есть отсутствующие модули, возвращаем False
            if missing_modules:
                logger.warning(f"Отсутствуют необходимые модули: {', '.join(missing_modules)}")
                return False
            
            return True
            
        except ImportError as e:
            logger.error(f"Не удалось настроить псевдонимы модулей: {e}")
            return False

def import_src_modules():
    """
    Импортирует модули из директории src и создает для них псевдонимы.
    """
    # API Wrapper
    import src.api.api_wrapper
    sys.modules['api_wrapper'] = sys.modules['src.api.api_wrapper']
    logger.info("Добавлен псевдоним для src.api.api_wrapper как api_wrapper")
    
    # Bellman-Ford
    try:
        # Сначала пытаемся импортировать из корня проекта
        import bellman_ford
        logger.info("Импортирован модуль bellman_ford из корня проекта")
    except ImportError:
        try:
            # Затем пытаемся импортировать из src.arbitrage
            import src.arbitrage.bellman_ford
            sys.modules['bellman_ford'] = sys.modules['src.arbitrage.bellman_ford']
            logger.info("Добавлен псевдоним для src.arbitrage.bellman_ford как bellman_ford")
        except ImportError as e:
            logger.warning(f"Не удалось импортировать bellman_ford: {e}")
            # Создаем пустой модуль-заглушку
            sys.modules['bellman_ford'] = types.ModuleType('bellman_ford')
            logger.warning("Создан пустой модуль-заглушка bellman_ford")
    
    # Linear Programming - импорт не требуется, так как модуль уже установлен в корне проекта
    try:
        # Пробуем импортировать из корня проекта
        import linear_programming
        logger.info("Импортирован модуль linear_programming из корня проекта")
    except ImportError:
        try:
            # Затем пытаемся импортировать из src.arbitrage
            import src.arbitrage.linear_programming
            sys.modules['linear_programming'] = sys.modules['src.arbitrage.linear_programming']
            logger.info("Добавлен псевдоним для src.arbitrage.linear_programming как linear_programming")
        except ImportError as e:
            logger.warning(f"Не удалось импортировать linear_programming: {e}")
            # Создаем пустой модуль-заглушку если нужно
            if 'linear_programming' not in sys.modules:
                sys.modules['linear_programming'] = types.ModuleType('linear_programming')
                logger.warning("Создан пустой модуль-заглушка linear_programming")
    
    # ML Predictor
    try:
        import src.ml.ml_predictor
        sys.modules['ml_predictor'] = sys.modules['src.ml.ml_predictor']
        logger.info("Добавлен псевдоним для src.ml.ml_predictor как ml_predictor")
    except ImportError as e:
        logger.warning(f"Не удалось импортировать src.ml.ml_predictor: {e}")
        try:
            import src.ml
            sys.modules['ml_predictor'] = types.ModuleType('ml_predictor')
            sys.modules['ml_predictor'].MLPredictor = src.ml.MLPredictor
            logger.info("Создан псевдоним ml_predictor с MLPredictor из src.ml")
        except ImportError as e:
            logger.warning(f"Не удалось импортировать src.ml: {e}")

def import_dm_modules():
    """
    Импортирует модули из пакета DM, если он доступен.
    
    Returns:
        bool: True если импорт успешен, иначе False
    """
    # API Wrapper
    import DM.api_wrapper
    sys.modules['api_wrapper'] = sys.modules['DM.api_wrapper']
    logger.info("Добавлен псевдоним для DM.api_wrapper как api_wrapper")
    
    # Bellman-Ford
    import DM.bellman_ford
    sys.modules['bellman_ford'] = sys.modules['DM.bellman_ford']
    logger.info("Добавлен псевдоним для DM.bellman_ford как bellman_ford")
    
    # Linear Programming
    import DM.linear_programming
    sys.modules['linear_programming'] = sys.modules['DM.linear_programming']
    logger.info("Добавлен псевдоним для DM.linear_programming как linear_programming")
    
    # ML Predictor
    try:
        import DM.ml_predictor
        sys.modules['ml_predictor'] = sys.modules['DM.ml_predictor']
        logger.info("Добавлен псевдоним для DM.ml_predictor как ml_predictor")
    except ImportError as e:
        logger.warning(f"Не удалось импортировать DM.ml_predictor: {e}")

async def initialize_bot() -> Tuple:
    """
    Инициализирует бота и все необходимые компоненты.
    
    Returns:
        Tuple: Экземпляр бота и диспетчера или также URL и путь вебхука
    """
    try:
        # Настройка окружения
        setup_environment()
        
        # Очистка кэша Python
        clean_cache()
        
        # Импорт модулей из src
        import_src_modules()
        
        # Импорт модулей из DM (если есть)
        import_dm_modules()
        
        # Импортируем необходимые модули
        from aiogram import Bot, Dispatcher
        from aiogram.contrib.fsm_storage.memory import MemoryStorage
        from aiogram.contrib.middlewares.logging import LoggingMiddleware
        import aiogram
        
        # Получаем токен бота из переменных окружения
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN не указан в переменных окружения")
            raise ValueError("TELEGRAM_BOT_TOKEN не указан в переменных окружения")
        
        # Создаем экземпляр бота
        bot = Bot(token=bot_token)
        
        # Выбираем хранилище состояний
        use_redis = os.getenv("USE_REDIS", "false").lower() in ["true", "1", "t", "yes", "y"]
        
        if use_redis:
            try:
                from aiogram.contrib.fsm_storage.redis import RedisStorage2
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                storage = RedisStorage2.from_url(redis_url, prefix="dmarket_bot_fsm")
                logger.info(f"Используется Redis для хранения состояний: {redis_url}")
            except Exception as e:
                logger.warning(f"Ошибка при подключении к Redis: {e}")
                storage = MemoryStorage()
                logger.warning("Используется хранилище состояний в памяти из-за ошибки Redis")
        else:
            storage = MemoryStorage()
            logger.info("Используется хранение состояний в памяти")
        
        # Создаем диспетчер
        dp = Dispatcher(bot, storage=storage)
        
        # Добавляем middleware для логирования
        dp.middleware.setup(LoggingMiddleware())
        logger.info("Добавлен middleware для логирования")
        
        # Печатаем версию aiogram
        logger.info(f"Используем aiogram версии: {aiogram.__version__}")
        
        # Проверяем, нужно ли использовать вебхуки
        use_webhook = os.getenv("USE_WEBHOOK", "false").lower() in ["true", "1", "t", "yes", "y"]
        
        if use_webhook:
            # Получаем параметры для вебхуков
            webhook_host = os.getenv("WEBHOOK_HOST")
            webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
            
            if not webhook_host:
                logger.warning("USE_WEBHOOK=true, но WEBHOOK_HOST не указан. Вебхуки не будут использоваться.")
                return bot, dp
            
            webhook_url = f"{webhook_host}{webhook_path}"
            logger.info(f"Бот будет использовать вебхуки. URL: {webhook_url}")
            
            return bot, dp, webhook_url, webhook_path
        
        return bot, dp
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации бота: {e}", exc_info=True)
        raise

async def start_bot(bot, dp, webhook_url=None, webhook_path=None, webapp_host="0.0.0.0", webapp_port=8443):
    """
    Запускает бота на долгосрочную работу.
    
    Args:
        bot: Экземпляр бота
        dp: Экземпляр диспетчера
        webhook_url: URL для вебхука (если используются вебхуки)
        webhook_path: Путь для вебхука (если используются вебхуки)
        webapp_host: Хост для веб-приложения (если используются вебхуки)
        webapp_port: Порт для веб-приложения (если используются вебхуки)
    """
    from aiogram import executor
    
    # Устанавливаем обработчики запуска и остановки
    from src.telegram.telegram_bot import on_startup, on_shutdown
    
    # Запускаем бота с использованием вебхуков или long polling
    if webhook_url and webhook_path:
        logger.info(f"Запуск бота в режиме вебхуков: {webhook_url}")
        # Устанавливаем все необходимые обработчики
        await executor.start_webhook(
            dispatcher=dp,
            webhook_path=webhook_path,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            skip_updates=False,
            host=webapp_host,
            port=webapp_port,
        )
    else:
        logger.info("Запуск бота в режиме long polling")
        
        # Убедимся, что нет активных вебхуков и других экземпляров бота
        try:
            # Явно сбрасываем вебхук перед запуском polling
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Вебхук успешно сброшен перед началом polling")
        except Exception as e:
            logger.error(f"Ошибка при сбросе вебхука: {e}", exc_info=True)
        
        # Вызываем обработчик запуска
        await on_startup(dp)
        
        try:
            # Запускаем поллинг вручную без использования executor
            logger.info("Начинаем поллинг сообщений...")
            # Используем timeout и limite_rate для устранения проблем с несколькими экземплярами
            await dp.start_polling(reset_webhook=True, timeout=30, relax=0.5)
            
            # Держим бота запущенным, пока не будет прерывания
            logger.info("Бот запущен и ожидает сообщения...")
            # Используем бесконечный цикл чтобы бот не завершался
            while True:
                await asyncio.sleep(3600)  # Ожидание 1 час, чтобы не нагружать CPU
        except asyncio.CancelledError:
            # Обработка отмены задачи
            logger.info("Получен сигнал остановки бота")
        except Exception as e:
            logger.error(f"Ошибка в процессе работы бота: {e}", exc_info=True)
        finally:
            # Вызываем обработчик остановки
            await on_shutdown(dp)
            
            # Явно закрываем сессию для освобождения ресурсов
            session = await bot.get_session()
            if session and not session.closed:
                await session.close()
                logger.info("Сессия бота успешно закрыта")

def restart_bot():
    """
    Функция для безопасного перезапуска бота.
    
    Запускает новый процесс и завершает текущий.
    """
    import subprocess
    import signal
    import psutil
    
    logger.info("Начинаем процедуру перезапуска бота...")
    
    # Получаем путь к скрипту запуска
    script_path = Path(__file__).parent.parent.parent / "src" / "telegram" / "run_bot.py"
    
    try:
        # Проверяем, есть ли другие экземпляры бота и завершаем их
        current_pid = os.getpid()
        current_process = psutil.Process(current_pid)
        
        # Находим имя текущего питон-скрипта
        current_script = current_process.cmdline()[-1]
        
        # Ищем другие процессы, которые запускают те же скрипты
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Проверяем, является ли это процессом Python и не текущим процессом
                if proc.pid != current_pid and proc.name().lower().startswith('python'):
                    cmdline = proc.cmdline()
                    # Проверяем, запускает ли процесс наш скрипт бота
                    if any('telegram' in cmd.lower() and 'bot' in cmd.lower() for cmd in cmdline):
                        logger.info(f"Найден другой процесс бота (PID: {proc.pid}). Завершаем его...")
                        try:
                            # Отправляем сигнал SIGTERM для корректного завершения
                            os.kill(proc.pid, signal.SIGTERM)
                            # Даем процессу время на корректное завершение
                            proc.wait(timeout=5)
                            logger.info(f"Процесс {proc.pid} успешно завершен")
                        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                            # Если процесс не завершился корректно, завершаем принудительно
                            try:
                                os.kill(proc.pid, signal.SIGKILL)
                                logger.info(f"Процесс {proc.pid} принудительно завершен")
                            except ProcessLookupError:
                                logger.info(f"Процесс {proc.pid} уже завершен")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Игнорируем процессы, к которым нет доступа
                pass
        
        logger.info(f"Запуск нового экземпляра бота с помощью скрипта {script_path}")
        
        # Запускаем новый процесс с указанием отдельного окружения
        env = os.environ.copy()
        env["BOT_RESTART_INITIATED"] = "1"  # Добавляем маркер перезапуска
        
        # Запускаем новый процесс
        subprocess.Popen([sys.executable, str(script_path)], env=env)
        logger.info("Новый процесс бота запущен")
        
        # Небольшая задержка перед завершением
        time.sleep(2)
        
        # Выходим из текущего процесса
        logger.info("Текущий процесс завершается...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Ошибка при перезапуске бота: {e}", exc_info=True)
        raise Exception(f"Не удалось перезапустить бота: {e}") 