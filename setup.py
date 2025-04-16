#!/usr/bin/env python
"""
Скрипт для настройки и установки DMarket Trading Bot.

Этот скрипт автоматизирует процесс установки зависимостей, настройки конфигурации
и проверки компонентов, необходимых для работы DMarket Trading Bot.
Основные функции:
- Проверка версии Python
- Создание виртуального окружения
- Установка зависимостей
- Настройка переменных окружения
- Инициализация базы данных
- Создание скриптов запуска

Использование:
    python setup.py
"""

import os
import sys
import subprocess
import shutil
import platform
import logging
from typing import Dict, List, Optional, Tuple, Any
import json
import datetime
from setuptools import setup, find_packages

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('setup_log.txt')
    ]
)
logger = logging.getLogger('setup')

# Настройка пакета для установки
setup(
    name="dmarket_trading_bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "numpy",
        "scikit-learn",
        "matplotlib",
        "requests",
        "aiohttp",
        "joblib",
        "pyyaml",
        "python-dotenv",
        "python-telegram-bot",
        "redis",
        "cryptography",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "pytest-cov",
            "autopep8",
            "flake8",
            "black",
            "isort",
            "mypy",
        ],
    },
    entry_points={
        "console_scripts": [
            "dmarket-bot=src.cli.cli:main",
        ],
    },
    python_requires=">=3.8",
    author="DMarket Bot Team",
    description="Trading bot for DMarket platform with ML-based price prediction",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
    ],
)

def check_python_version() -> bool:
    """
    Проверяет соответствие текущей версии Python минимальным требованиям.
    
    Минимальная поддерживаемая версия: Python 3.7+
    
    Returns:
        bool: True если версия соответствует требованиям, False в противном случае
    """
    python_version = sys.version_info
    min_version = (3, 7)
    
    if python_version < min_version:
        logger.error(f"Установлена версия Python {python_version.major}.{python_version.minor}, "
                     f"требуется минимум {min_version[0]}.{min_version[1]}")
        return False
        
    logger.info(f"Версия Python: {python_version.major}.{python_version.minor}.{python_version.micro}")
    return True

def install_dependencies() -> bool:
    """
    Устанавливает зависимости из requirements.txt.
    
    Использует pip для установки всех необходимых пакетов, 
    перечисленных в файле requirements.txt.
    
    Returns:
        bool: True если установка успешна, False в противном случае
    
    Raises:
        subprocess.CalledProcessError: Если возникла ошибка при вызове pip
    """
    try:
        logger.info("Установка зависимостей...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        logger.info("Зависимости успешно установлены")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при установке зависимостей: {e}")
        return False

def create_env_file() -> bool:
    """
    Создает файл .env на основе .env.example, запрашивая у пользователя необходимые значения.
    
    Файл .env содержит конфиденциальные настройки, такие как API ключи и токены.
    Пользователю будет предложено ввести значения для ключевых переменных.
    
    Returns:
        bool: True если создание успешно, False в противном случае
    """
    if not os.path.exists('.env.example'):
        logger.error("Файл .env.example не найден")
        return False
        
    if os.path.exists('.env') and not _confirm_overwrite('.env'):
        logger.info("Создание .env отменено пользователем")
        return False
        
    try:
        logger.info("Создание файла .env...")
        with open('.env.example', 'r', encoding='utf-8') as example_file:
            example_content = example_file.read()
            
        # Запрашиваем у пользователя значения для ключевых переменных
        env_content = example_content
        
        # Список ключевых переменных, которые нужно запросить у пользователя
        key_variables = [
            ('DMARKET_API_KEY', 'Введите API ключ DMarket (оставьте пустым для пропуска): '),
            ('DMARKET_API_SECRET', 'Введите API секрет DMarket (оставьте пустым для пропуска): '),
            ('TELEGRAM_BOT_TOKEN', 'Введите токен Telegram бота (оставьте пустым для пропуска): '),
            ('ADMIN_CHAT_ID', 'Введите Chat ID администратора (оставьте пустым для пропуска): ')
        ]
        
        for var_name, prompt in key_variables:
            value = input(prompt).strip()
            if value:
                env_content = env_content.replace(f"{var_name}=", f"{var_name}={value}")
                
        with open('.env', 'w', encoding='utf-8') as env_file:
            env_file.write(env_content)
            
        logger.info("Файл .env успешно создан")
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании файла .env: {e}")
        return False

def _confirm_overwrite(filename: str) -> bool:
    """
    Запрашивает у пользователя подтверждение на перезапись файла.
    
    Args:
        filename (str): Имя файла, который будет перезаписан
        
    Returns:
        bool: True если пользователь подтвердил перезапись (ввел 'y', 'yes' или 'да'),
              False в противном случае
    """
    response = input(f"Файл {filename} уже существует. Перезаписать? (y/n): ").strip().lower()
    return response in ('y', 'yes', 'да')

def create_virtual_environment() -> bool:
    """
    Создает виртуальное окружение Python для изоляции зависимостей.
    
    Создает виртуальное окружение в директории .venv и устанавливает в него
    все зависимости из файла requirements.txt.
    
    Returns:
        bool: True если создание успешно, False в противном случае
    
    Raises:
        subprocess.CalledProcessError: Если возникла ошибка при создании
                                     виртуального окружения или установке зависимостей
    """
    venv_dir = '.venv'
    
    if os.path.exists(venv_dir):
        logger.info(f"Виртуальное окружение {venv_dir} уже существует")
        return True
        
    try:
        logger.info(f"Создание виртуального окружения в {venv_dir}...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        
        # Определение пути к pip в виртуальном окружении
        if platform.system() == 'Windows':
            pip_path = os.path.join(venv_dir, 'Scripts', 'pip')
        else:
            pip_path = os.path.join(venv_dir, 'bin', 'pip')
            
        # Установка зависимостей в виртуальное окружение
        subprocess.check_call([pip_path, "install", "-r", "requirements.txt"])
        
        logger.info(f"Виртуальное окружение создано в {venv_dir}")
        logger.info(f"Для активации окружения выполните:")
        if platform.system() == 'Windows':
            logger.info(f".\\{venv_dir}\\Scripts\\activate")
        else:
            logger.info(f"source {venv_dir}/bin/activate")
            
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при создании виртуального окружения: {e}")
        return False

def check_database() -> bool:
    """
    Проверяет и инициализирует базу данных при необходимости.
    
    Если файл базы данных не существует, выполняет скрипт init_db.py
    для создания и инициализации базы данных.
    
    Returns:
        bool: True если проверка/инициализация успешна, False в противном случае
    
    Raises:
        subprocess.CalledProcessError: Если возникла ошибка при инициализации базы данных
    """
    db_file = 'database.db'
    
    try:
        if not os.path.exists(db_file):
            logger.info("База данных не найдена, выполняется инициализация...")
            subprocess.check_call([sys.executable, "init_db.py"])
            logger.info("База данных успешно инициализирована")
        else:
            logger.info("База данных найдена")
            
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке/инициализации базы данных: {e}")
        return False

def run_tests() -> bool:
    """
    Запускает тесты для проверки работоспособности бота.
    
    Выполняет базовые тесты инициализации для проверки корректности
    настройки и работоспособности основных компонентов.
    
    Returns:
        bool: True если тесты выполнены успешно, False в противном случае
    
    Raises:
        subprocess.CalledProcessError: Если возникла ошибка при запуске тестов
    """
    try:
        logger.info("Запуск тестов...")
        if platform.system() == 'Windows':
            # Избегаем проблем с кодировкой на Windows
            test_env = os.environ.copy()
            test_env['PYTHONIOENCODING'] = 'utf-8'
            process = subprocess.run(
                [sys.executable, "-m", "pytest", "-xvs", "tests/test_bot_init.py"],
                env=test_env,
                capture_output=True,
                text=True
            )
        else:
            process = subprocess.run(
                [sys.executable, "-m", "pytest", "-xvs", "tests/test_bot_init.py"],
                capture_output=True,
                text=True
            )
            
        if process.returncode == 0:
            logger.info("Тесты выполнены успешно")
            return True
        else:
            logger.error(f"Ошибка при выполнении тестов: {process.stderr}")
            logger.info(f"Вывод тестов: {process.stdout}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при запуске тестов: {e}")
        return False

def create_run_script() -> bool:
    """
    Создает скрипты для удобного запуска бота.
    
    Создает скрипты запуска в зависимости от операционной системы:
    - run_bot.bat/run_bot.sh для запуска Telegram-бота
    - find_arbitrage.bat/find_arbitrage.sh для поиска арбитражных возможностей
    
    Returns:
        bool: True если скрипты созданы успешно, False в противном случае
    """
    try:
        logger.info("Создание скриптов запуска...")
        
        # Создаем скрипт для запуска Telegram бота
        if platform.system() == 'Windows':
            with open('run_bot.bat', 'w', encoding='utf-8') as f:
                f.write('@echo off\n')
                f.write('echo Запуск DMarket Trading Bot...\n')
                f.write('python telegram_bot.py\n')
                f.write('pause\n')
                
            logger.info("Создан скрипт run_bot.bat для Windows")
        else:
            with open('run_bot.sh', 'w', encoding='utf-8') as f:
                f.write('#!/bin/bash\n')
                f.write('echo "Запуск DMarket Trading Bot..."\n')
                f.write('python telegram_bot.py\n')
                
            # Делаем скрипт исполняемым
            os.chmod('run_bot.sh', 0o755)
            logger.info("Создан скрипт run_bot.sh для Unix/Linux")
            
        # Создаем скрипт для поиска арбитражных возможностей
        if platform.system() == 'Windows':
            with open('find_arbitrage.bat', 'w', encoding='utf-8') as f:
                f.write('@echo off\n')
                f.write('echo Поиск арбитражных возможностей...\n')
                f.write('python main.py --analyze --min_profit 1.0 --game cs2 --output results\n')
                f.write('pause\n')
                
            logger.info("Создан скрипт find_arbitrage.bat для Windows")
        else:
            with open('find_arbitrage.sh', 'w', encoding='utf-8') as f:
                f.write('#!/bin/bash\n')
                f.write('echo "Поиск арбитражных возможностей..."\n')
                f.write('python main.py --analyze --min_profit 1.0 --game cs2 --output results\n')
                
            # Делаем скрипт исполняемым
            os.chmod('find_arbitrage.sh', 0o755)
            logger.info("Создан скрипт find_arbitrage.sh для Unix/Linux")
            
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании скриптов запуска: {e}")
        return False

def generate_setup_report() -> None:
    """
    Генерирует JSON-отчет о процессе настройки системы.
    
    Создает отчет со следующей информацией:
    - Время выполнения настройки
    - Информация об операционной системе
    - Версия Python
    - Статус компонентов (наличие .env, базы данных, виртуального окружения, скриптов)
    
    Отчет сохраняется в файл setup_report.json.
    """
    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "system": {
            "os": platform.system(),
            "python_version": platform.python_version(),
            "processor": platform.processor()
        },
        "components": {
            "env_file": os.path.exists('.env'),
            "database": os.path.exists('database.db'),
            "virtual_env": os.path.exists('.venv'),
            "run_scripts": os.path.exists('run_bot.bat') or os.path.exists('run_bot.sh')
        }
    }
    
    # Сохраняем отчет в файл
    with open('setup_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"Отчет о настройке сохранен в файл setup_report.json")

def main() -> int:
    """
    Основная функция скрипта установки.
    
    Выполняет последовательно все шаги настройки:
    1. Проверка версии Python
    2. Создание виртуального окружения
    3. Установка зависимостей
    4. Создание .env файла
    5. Проверка базы данных
    6. Запуск тестов
    7. Создание скриптов запуска
    8. Генерация отчета
    
    Returns:
        int: Код завершения (0 - успех, 1 - ошибка)
    """
    logger.info("Начало процесса настройки DMarket Trading Bot")
    
    # Проверка версии Python
    if not check_python_version():
        logger.error("Требуется Python 3.7 или выше")
        return 1
        
    # Создание виртуального окружения
    if not create_virtual_environment():
        logger.warning("Не удалось создать виртуальное окружение")
    
    # Установка зависимостей
    if not install_dependencies():
        logger.error("Не удалось установить зависимости")
        return 1
        
    # Создание .env файла
    if not create_env_file():
        logger.warning("Не удалось создать файл .env")
    
    # Проверка базы данных
    if not check_database():
        logger.warning("Не удалось инициализировать базу данных")
    
    # Запуск тестов
    if not run_tests():
        logger.warning("Тесты завершились с ошибками")
    
    # Создание скриптов запуска
    if not create_run_script():
        logger.warning("Не удалось создать скрипты запуска")
    
    # Генерация отчета
    generate_setup_report()
    
    logger.info("Настройка DMarket Trading Bot завершена")
    print("\nНастройка DMarket Trading Bot завершена")
    print("Для запуска бота выполните:")
    if platform.system() == 'Windows':
        print("run_bot.bat")
    else:
        print("./run_bot.sh")
        
    return 0

if __name__ == "__main__":
    sys.exit(main()) 