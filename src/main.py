#!/usr/bin/env python
"""
Основная точка входа для DMarket Trading Bot с новой структурой проекта.

Этот скрипт запускает основные компоненты приложения в зависимости от переданных параметров.
"""

import sys
import argparse
import logging
import asyncio
import os
import shutil
from pathlib import Path
from typing import Callable, Any, Dict, List, Tuple, Optional

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Добавляем DM директорию в PYTHONPATH (старая структура)
dm_path = project_root / "DM"
if dm_path.exists():
    sys.path.insert(0, str(dm_path))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('application.log')
    ]
)
logger = logging.getLogger('run')

# Исправляем возможные ошибки с булевыми значениями в переменных окружения
def fix_boolean_env_vars():
    """
    Исправляет булевы значения в переменных окружения, преобразуя строки 'true'/'false' в '1'/'0'.
    """
    boolean_vars = ['USE_WEBHOOK', 'DB_ECHO', 'LOG_TO_FILE', 'USE_PARALLEL_PROCESSING']
    
    for var in boolean_vars:
        if var in os.environ:
            value = os.environ[var].lower()
            if value in ('true', 't', 'yes', 'y'):
                os.environ[var] = '1'
            elif value in ('false', 'f', 'no', 'n'):
                os.environ[var] = '0'
    
    # Исправляем .env файл, если он существует
    env_file = project_root / ".env"
    dm_env_file = project_root / "DM" / ".env"
    
    if not env_file.exists() and dm_env_file.exists():
        # Копируем конфиг из DM в корень проекта
        shutil.copy(dm_env_file, env_file)
        logger.info("Скопирован .env файл из DM в корень проекта")
    
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                env_content = f.read()
            
            modified = False
            for var in boolean_vars:
                if f"{var}=true" in env_content:
                    env_content = env_content.replace(f"{var}=true", f"{var}=1")
                    modified = True
                elif f"{var}=false" in env_content:
                    env_content = env_content.replace(f"{var}=false", f"{var}=0")
                    modified = True
            
            if modified:
                with open(env_file, "w", encoding="utf-8") as f:
                    f.write(env_content)
                logger.info("Исправлены булевы значения в .env файле")
        except Exception as e:
            logger.warning(f"Не удалось исправить .env файл: {e}")

# Настраиваем псевдонимы модулей для совместимости со старым кодом
def setup_module_aliases() -> Tuple[int, int]:
    """
    Создает псевдонимы для модулей, чтобы старый код мог работать с новой структурой.
    
    Returns:
        Tuple[int, int]: (количество успешно настроенных псевдонимов, общее количество псевдонимов)
    """
    modules_to_alias = {
        'api_wrapper': ['src.api.api_wrapper', 'DM.api_wrapper'],
        'bellman_ford': ['src.arbitrage.bellman_ford', 'DM.bellman_ford'],
        'linear_programming': ['src.arbitrage.linear_programming', 'DM.linear_programming'],
        'ml_predictor': ['src.ml.ml_predictor', 'DM.ml_predictor'],
        'config': ['src.config.config', 'DM.config'],
        'db_funcs': ['src.db.db_funcs', 'DM.db_funcs']
    }
    
    success_count = 0
    total_count = len(modules_to_alias)
    
    try:
        # Сначала пробуем импортировать из новой структуры
        try:
            from src.utils.module_aliases import setup_module_aliases as setup_aliases
            success_count, total_count = setup_aliases()
            logger.info(f"Настроено {success_count}/{total_count} псевдонимов модулей через utils.module_aliases")
            return success_count, total_count
        except ImportError:
            # Если не получилось, настраиваем вручную базовые псевдонимы
            logger.warning("Не удалось найти модуль настройки псевдонимов. Настраиваем базовые псевдонимы вручную.")
            
            # Настраиваем псевдонимы для всех модулей в списке
            for alias, paths in modules_to_alias.items():
                created = False
                for path in paths:
                    try:
                        module_parts = path.split('.')
                        if len(module_parts) > 1:
                            # Импортируем модуль
                            exec(f"import {path}")
                            # Создаем псевдоним
                            exec(f"sys.modules['{alias}'] = sys.modules['{path}']")
                            logger.info(f"Настроен псевдоним: {path} -> {alias}")
                            success_count += 1
                            created = True
                            break
                    except ImportError as e:
                        logger.debug(f"Не удалось импортировать {path}: {e}")
                
                if not created:
                    logger.warning(f"Не удалось создать псевдоним для {alias}, создаем заглушку")
                    # Создаем заглушку
                    import types
                    dummy_module = types.ModuleType(alias)
                    sys.modules[alias] = dummy_module
            
            # Проверяем, нужно ли добавить функцию-заглушку find_all_arbitrage_opportunities_async
            if 'bellman_ford' in sys.modules and not hasattr(sys.modules['bellman_ford'], 'find_all_arbitrage_opportunities_async'):
                logger.warning("Добавляем в bellman_ford отсутствующую функцию find_all_arbitrage_opportunities_async")
                
                # Создаем функцию-заглушку
                async def find_all_arbitrage_opportunities_async(*args, **kwargs):
                    logger.warning("Вызвана функция-заглушка find_all_arbitrage_opportunities_async")
                    return []
                
                # Добавляем функцию в модуль
                sys.modules['bellman_ford'].find_all_arbitrage_opportunities_async = find_all_arbitrage_opportunities_async
            
            return success_count, total_count
            
    except Exception as e:
        logger.error(f"Ошибка при настройке псевдонимов модулей: {e}")
        return 0, total_count

def run_component(component_main: Callable[[], Any]) -> int:
    """
    Запускает компонент приложения с учетом того, является ли он асинхронным.
    
    Args:
        component_main: Основная функция компонента
        
    Returns:
        int: Код возврата
    """
    try:
        if asyncio.iscoroutinefunction(component_main):
            return asyncio.run(component_main())
        else:
            return component_main()
    except Exception as e:
        logger.error(f"Ошибка выполнения компонента: {e}")
        return 1

def install_missing_dependencies():
    """
    Устанавливает отсутствующие зависимости, необходимые для работы приложения.
    
    Returns:
        bool: True, если все необходимые зависимости установлены или успешно установлены
    """
    required_packages = {
        'aiogram': 'Telegram бот',
        'aiohttp': 'API клиент', 
        'python-dotenv': 'Работа с переменными окружения',
        'pandas': 'Анализ данных',
        'numpy': 'Математические вычисления',
        'scikit-learn': 'Машинное обучение'
    }
    
    missing_packages = []
    
    for package, description in required_packages.items():
        try:
            if package == 'python-dotenv':
                # Специальная обработка python-dotenv
                import dotenv
                logger.debug(f"Найден пакет dotenv")
            elif package == 'scikit-learn':
                # Специальная обработка scikit-learn
                import sklearn
                version = getattr(sklearn, '__version__', 'unknown')
                logger.debug(f"Найден пакет sklearn версии {version}")
            else:
                # Общий случай импорта
                module_name = package.replace('-', '_')
                module = __import__(module_name)
                version = getattr(module, '__version__', 'unknown')
                logger.debug(f"Найден пакет {package} версии {version}")
        except (ImportError, ModuleNotFoundError):
            missing_packages.append(package)
    
    if missing_packages:
        logger.warning(f"Отсутствуют необходимые зависимости: {', '.join(missing_packages)}")
        
        try:
            # Спрашиваем пользователя, хочет ли он установить зависимости
            print(f"Отсутствуют необходимые зависимости: {', '.join(missing_packages)}")
            response = input("Установить недостающие зависимости? (y/n): ")
            
            if response.lower() in ('y', 'yes', 'да'):
                import subprocess
                logger.info("Устанавливаем недостающие зависимости...")
                
                # Устанавливаем каждую зависимость отдельно
                for package in missing_packages:
                    print(f"Установка {package}...")
                    try:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                        logger.info(f"Зависимость {package} успешно установлена")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Не удалось установить {package}: {e}")
                        print(f"Ошибка установки {package}. Попробуйте установить вручную: pip install {package}")
                
                # Проверяем, все ли зависимости теперь установлены
                still_missing = []
                for package in missing_packages:
                    try:
                        if package == 'python-dotenv':
                            import dotenv
                        elif package == 'scikit-learn':
                            import sklearn
                        else:
                            module_name = package.replace('-', '_')
                            __import__(module_name)
                    except (ImportError, ModuleNotFoundError):
                        still_missing.append(package)
                
                if still_missing:
                    logger.warning(f"После установки все еще отсутствуют: {', '.join(still_missing)}")
                    print(f"После установки все еще отсутствуют: {', '.join(still_missing)}")
                    print("Установите их вручную: pip install " + " ".join(still_missing))
                    return False
                else:
                    logger.info("Все зависимости успешно установлены")
                    return True
            else:
                logger.warning("Пользователь отказался от установки зависимостей")
                print("Без необходимых зависимостей некоторые функции не будут работать.")
                return False
        except Exception as e:
            logger.error(f"Ошибка при установке зависимостей: {e}")
            print(f"Ошибка при установке зависимостей: {e}")
            print(f"Установите их вручную: pip install {' '.join(missing_packages)}")
            return False
    
    return True

def check_dependencies() -> bool:
    """
    Проверяет наличие необходимых зависимостей для работы приложения.
    
    Returns:
        bool: True, если все необходимые зависимости установлены
    """
    required_packages = {
        'aiogram': 'Telegram бот',
        'aiohttp': 'API клиент',
        'pandas': 'Анализ данных',
        'numpy': 'Математические вычисления',
        'scikit-learn': 'Машинное обучение',
        'python-dotenv': 'Работа с переменными окружения'
    }
    
    missing_packages = []
    
    for package, description in required_packages.items():
        try:
            if package == 'python-dotenv':
                # Специальная обработка python-dotenv
                import dotenv
                # dotenv не имеет атрибута __version__
                logger.debug(f"Найден пакет dotenv")
            elif package == 'scikit-learn':
                # Специальная обработка scikit-learn
                import sklearn
                version = getattr(sklearn, '__version__', 'unknown')
                logger.debug(f"Найден пакет sklearn версии {version}")
            else:
                # Общий случай импорта
                module_name = package.replace('-', '_')
                module = __import__(module_name)
                version = getattr(module, '__version__', 'unknown')
                logger.debug(f"Найден пакет {package} версии {version}")
        except (ImportError, ModuleNotFoundError):
            missing_packages.append(f"{package} ({description})")
    
    if missing_packages:
        logger.warning(f"Отсутствуют необходимые зависимости: {', '.join(missing_packages)}")
        logger.warning("Установите зависимости: pip install -r requirements.txt")
        return False
    
    return True

def main() -> int:
    """
    Основная функция запуска приложения.
    Обрабатывает аргументы командной строки и запускает соответствующий компонент.
    
    Returns:
        int: Код возврата (0 - успех, 1 - ошибка)
    """
    parser = argparse.ArgumentParser(description='DMarket Trading Bot')
    
    parser.add_argument('--component', choices=['trading', 'telegram', 'arbitrage', 'ml', 'keyboards', 'simple-telegram'], 
                        default='trading', help='Компонент для запуска')
    
    parser.add_argument('--debug', action='store_true', help='Включить режим отладки')
    
    parser.add_argument('--install-deps', action='store_true', help='Установить недостающие зависимости')
    
    args = parser.parse_args()
    
    # Установка уровня логирования
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Включен режим отладки")
    
    try:
        # Исправляем булевы значения в переменных окружения
        fix_boolean_env_vars()
        
        # Проверяем наличие .env файла
        env_file = Path(project_root) / ".env"
        if not env_file.exists():
            logger.warning("Файл .env не найден. Возможны проблемы с конфигурацией.")
        
        # Проверяем и устанавливаем недостающие зависимости если запрошено
        if args.install_deps:
            install_missing_dependencies()
        elif not check_dependencies():
            logger.warning("Приложение запущено с отсутствующими зависимостями. Используйте --install-deps для установки.")
        
        # Настраиваем псевдонимы модулей
        success_count, total_count = setup_module_aliases()
        if success_count < total_count:
            logger.warning(f"Настроено только {success_count} из {total_count} псевдонимов модулей. Некоторые компоненты могут не работать.")
        
        # Запускаем нужный компонент
        if args.component == 'trading':
            try:
                from src.core.main import main as trading_main
                return run_component(trading_main)
            except ImportError:
                logger.error("Не удалось импортировать модуль trading_main")
                return 1
                
        elif args.component in ('telegram', 'simple-telegram'):
            # Если запрошен simple-telegram или в случае ошибки с обычным telegram, используем простую версию
            if args.component == 'simple-telegram' or not os.path.exists('src/telegram/telegram_bot.py'):
                try:
                    # Сначала проверяем, есть ли файл simple_telegram_bot.py
                    if not os.path.exists('simple_telegram_bot.py'):
                        logger.warning("Файл simple_telegram_bot.py не найден, создаем его")
                        # Если файла нет, создаем его с базовой реализацией
                        from run_create_simple_bot import create_simple_bot_file
                        create_simple_bot_file()
                    
                    # Импортируем и запускаем простую версию бота
                    logger.info("Запуск Telegram бота (простая версия)...")
                    from simple_telegram_bot import create_simple_telegram_bot
                    
                    def start_simple_bot():
                        success, bot, dp = create_simple_telegram_bot()
                        if success:
                            logger.info("Telegram бот успешно запущен")
                            from aiogram import executor
                            executor.start_polling(dp, skip_updates=True)
                            return 0
                        else:
                            logger.error("Не удалось создать Telegram бота")
                            return 1
                    
                    return run_component(start_simple_bot)
                except Exception as e:
                    logger.error(f"Ошибка при запуске простой версии бота: {e}")
                    return 1
            else:
                try:
                    # Запускаем полноценную версию бота
                    logger.info("Запуск полноценного Telegram бота...")
                    from src.telegram.telegram_bot import start_bot
                    return run_component(start_bot)
                except ImportError as e:
                    logger.error(f"Не удалось импортировать модуль telegram_bot: {e}")
                    logger.info("Пробуем запустить простую версию бота...")
                    
                    # Пробуем запустить простую версию при ошибке
                    try:
                        from simple_telegram_bot import create_simple_telegram_bot
                        
                        def start_simple_bot():
                            success, bot, dp = create_simple_telegram_bot()
                            if success:
                                from aiogram import executor
                                executor.start_polling(dp, skip_updates=True)
                                return 0
                            else:
                                return 1
                        
                        return run_component(start_simple_bot)
                    except Exception as sub_e:
                        logger.error(f"Не удалось запустить ни простую, ни полную версию бота: {sub_e}")
                        return 1
                
        elif args.component == 'arbitrage':
            try:
                from src.arbitrage.dmarket_arbitrage_finder import main as arbitrage_main
                return run_component(arbitrage_main)
            except ImportError:
                try:
                    from DM.dmarket_arbitrage_finder import main as arbitrage_main
                    return run_component(arbitrage_main)
                except ImportError:
                    logger.error("Не удалось импортировать модуль dmarket_arbitrage_finder")
                    return 1
                
        elif args.component == 'ml':
            try:
                from src.analytics.ml_predictor import main as ml_main
                return run_component(ml_main)
            except ImportError:
                try:
                    from src.ml.ml_predictor import main as ml_main
                    return run_component(ml_main)
                except ImportError:
                    try:
                        from DM.ml_predictor import main as ml_main
                        return run_component(ml_main)
                    except ImportError:
                        logger.error("Не удалось импортировать модуль ml_predictor")
                        return 1
                
        elif args.component == 'keyboards':
            # Тестовый режим для проверки клавиатур
            try:
                logger.info("Запуск теста клавиатур...")
                from src.telegram.keyboards_test import test_keyboards
                return run_component(test_keyboards)
            except ImportError:
                logger.error("Не удалось импортировать модуль keyboards_test")
                return 1
    except ImportError as e:
        logger.error(f"Ошибка импорта модуля: {e}")
        logger.error("Убедитесь, что структура проекта корректна и все зависимости установлены.")
        return 1
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
        return 1
    
    return 0

# Дополнительный модуль для создания простого бота
class RunCreateSimpleBot:
    """
    Класс для создания файла простого Telegram бота при необходимости.
    """
    
    @staticmethod
    def create_simple_bot_file():
        """Создает файл simple_telegram_bot.py с базовой реализацией бота"""
        bot_code = '''#!/usr/bin/env python
"""
Простой скрипт для запуска Telegram бота без зависимостей от других модулей.
"""

import os
import sys
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('simple_telegram.log')
    ]
)
logger = logging.getLogger('simple_telegram_bot')

# Получаем абсолютный путь к директории проекта
project_root = Path(__file__).parent.absolute()

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(project_root))

# Добавляем DM директорию в PYTHONPATH (старая структура)
dm_path = project_root / "DM"
if dm_path.exists():
    sys.path.insert(0, str(dm_path))
    logger.info(f"Добавлен {dm_path} в Python path")

# Убедимся, что конфигурационные файлы существуют
env_file = project_root / ".env"
if not env_file.exists():
    env_file = project_root / "DM" / ".env"
    if env_file.exists():
        # Копируем конфиг из DM в корень проекта
        with open(env_file, "r", encoding="utf-8") as src:
            env_content = src.read()
        with open(project_root / ".env", "w", encoding="utf-8") as dest:
            dest.write(env_content)
        logger.info("Скопирован .env файл из DM в корень проекта")

def create_simple_telegram_bot():
    """
    Создает простой Telegram бот, используя только необходимые зависимости.
    """
    try:
        # Обрабатываем булевы значения в переменных окружения перед загрузкой
        if "USE_WEBHOOK" in os.environ:
            if os.environ["USE_WEBHOOK"].lower() in ("false", "f", "no", "n", "0"):
                os.environ["USE_WEBHOOK"] = "0"
            elif os.environ["USE_WEBHOOK"].lower() in ("true", "t", "yes", "y", "1"):
                os.environ["USE_WEBHOOK"] = "1"
        
        # Импортируем только необходимые библиотеки
        from aiogram import Bot, Dispatcher, executor, types
        from dotenv import load_dotenv
        
        # Загружаем переменные окружения
        load_dotenv()
        
        # Повторно обрабатываем переменные после load_dotenv
        if "USE_WEBHOOK" in os.environ:
            if os.environ["USE_WEBHOOK"].lower() in ("false", "f", "no", "n"):
                os.environ["USE_WEBHOOK"] = "0"
            elif os.environ["USE_WEBHOOK"].lower() in ("true", "t", "yes", "y"):
                os.environ["USE_WEBHOOK"] = "1"
        
        # Получаем токен из переменных окружения
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            token = os.getenv("BOT_TOKEN")
        
        if not token:
            logger.error("Токен бота не найден. Проверьте переменные TELEGRAM_BOT_TOKEN или BOT_TOKEN в .env файле")
            return False, None, None
        
        # Создаем экземпляр бота и диспетчера
        bot = Bot(token=token)
        dp = Dispatcher(bot)
        
        # Обработчик команды /start
        @dp.message_handler(commands=['start'])
        async def cmd_start(message: types.Message):
            await message.answer(
                "👋 Привет! Я бот для торговли на DMarket.\\n\\n"
                "Я могу помочь тебе с:\\n"
                "• Анализом предметов\\n"
                "• Поиском выгодных сделок\\n"
                "• Отслеживанием цен\\n\\n"
                "Используй /help чтобы узнать больше о доступных командах."
            )
        
        # Обработчик команды /help
        @dp.message_handler(commands=['help'])
        async def cmd_help(message: types.Message):
            await message.answer(
                "📋 Доступные команды:\\n\\n"
                "/start - Начать работу с ботом\\n"
                "/help - Показать эту справку\\n"
                "/status - Проверить статус бота\\n\\n"
                "❗️ Это упрощенная версия бота. Полная функциональность будет доступна позже."
            )
        
        # Обработчик команды /status
        @dp.message_handler(commands=['status'])
        async def cmd_status(message: types.Message):
            await message.answer(
                "✅ Бот работает нормально\\n\\n"
                f"• Версия: 1.0.0\\n"
                f"• ID чата: {message.chat.id}\\n"
                f"• Время запуска: {bot.get_me()}\\n"
            )
        
        # Обработчик для всех остальных сообщений
        @dp.message_handler()
        async def echo(message: types.Message):
            await message.answer(
                f"Получено сообщение: {message.text}\\n\\n"
                "Используйте /help для просмотра списка команд."
            )
        
        logger.info("Бот успешно создан и готов к запуску")
        return True, bot, dp
    except Exception as e:
        logger.error(f"Ошибка при создании бота: {e}")
        return False, None, None

if __name__ == "__main__":
    print("Запуск простого Telegram бота...")
    success, bot, dp = create_simple_telegram_bot()
    
    if success:
        print(f"Бот успешно создан. Запуск...")
        try:
            # Запускаем бота
            from aiogram import executor
            executor.start_polling(dp, skip_updates=True)
        except Exception as e:
            print(f"Ошибка при запуске бота: {e}")
            logger.error(f"Ошибка при запуске бота: {e}")
            sys.exit(1)
    else:
        print("Не удалось создать бота. Проверьте логи.")
        logger.error("Не удалось создать Telegram бота")
        sys.exit(1)
'''
        with open('simple_telegram_bot.py', 'w', encoding='utf-8') as f:
            f.write(bot_code)
        logger.info("Создан файл simple_telegram_bot.py")

# Создаем модуль с функцией для создания простого бота
if not os.path.exists('run_create_simple_bot.py'):
    with open('run_create_simple_bot.py', 'w', encoding='utf-8') as f:
        f.write('''
import logging
logger = logging.getLogger('run_create_simple_bot')

def create_simple_bot_file():
    """Создает файл simple_telegram_bot.py с базовой реализацией бота"""
    from run import RunCreateSimpleBot
    RunCreateSimpleBot.create_simple_bot_file()
    
if __name__ == "__main__":
    create_simple_bot_file()
''')

if __name__ == "__main__":
    sys.exit(main()) 