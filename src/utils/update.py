#!/usr/bin/env python
"""
Скрипт для обновления DMarket Trading Bot из репозитория GitHub.

Этот скрипт автоматизирует процесс получения обновлений из удаленного репозитория,
сохраняя при этом пользовательские настройки и данные.

Функциональность:
- Проверка установки Git
- Создание резервных копий пользовательских файлов
- Получение обновлений из удаленного репозитория
- Применение обновлений с сохранением пользовательских настроек
- Обновление зависимостей
- Формирование отчета об обновлении

Использование:
    python update.py [--force] [--set-repo REPO_URL]

Аргументы:
    --force: Принудительно применить обновления
    --set-repo REPO_URL: Установить URL репозитория
"""

import os
import sys
import subprocess
import shutil
import logging
import json
import time
import tempfile
import argparse
from typing import Dict, List, Optional, Tuple, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('update_log.txt')
    ]
)
logger = logging.getLogger('update')

# URL репозитория GitHub
GITHUB_REPO = "https://github.com/your-username/dmarket-trading-bot.git"

def check_git_installed() -> bool:
    """
    Проверяет, установлен ли Git в системе.
    
    Выполняет команду 'git --version' для проверки наличия Git в системе.
    В случае ошибки или если команда не найдена, возвращает False.
    
    Returns:
        bool: True если Git установлен, False в противном случае
    
    Raises:
        subprocess.SubprocessError: Если возникла ошибка при выполнении команды
        FileNotFoundError: Если Git не найден в системе
    """
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        logger.info("Git установлен")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("Git не установлен. Пожалуйста, установите Git: https://git-scm.com/downloads")
        return False

def is_git_repository() -> bool:
    """
    Проверяет, является ли текущая директория Git-репозиторием.
    
    Проверяет наличие директории .git в текущей рабочей директории.
    
    Returns:
        bool: True если директория является Git-репозиторием, False в противном случае
    """
    return os.path.exists(".git")

def initialize_repository() -> bool:
    """
    Инициализирует Git-репозиторий и добавляет удаленный источник.
    
    Выполняет команды 'git init' и 'git remote add origin GITHUB_REPO'
    для создания нового репозитория и настройки удаленного источника.
    
    Returns:
        bool: True если инициализация успешна, False в противном случае
    
    Raises:
        subprocess.SubprocessError: Если возникла ошибка при выполнении Git-команд
    """
    try:
        # Инициализация репозитория
        subprocess.run(["git", "init"], check=True, capture_output=True)
        
        # Добавление удаленного источника
        subprocess.run(["git", "remote", "add", "origin", GITHUB_REPO], check=True, capture_output=True)
        
        logger.info("Git-репозиторий инициализирован")
        return True
    except subprocess.SubprocessError as e:
        logger.error(f"Ошибка при инициализации репозитория: {e}")
        return False

def backup_user_data() -> str:
    """
    Создает резервную копию пользовательских данных перед обновлением.
    
    Создает временную директорию и копирует в нее файлы настроек,
    базу данных и конфигурационные файлы, чтобы сохранить пользовательские
    данные на случай проблем с обновлением.
    
    Returns:
        str: Путь к временной директории с резервной копией. Пустая строка в случае ошибки.
    
    Raises:
        Exception: Любые исключения при создании резервной копии
    """
    try:
        # Создаем временную директорию для бэкапа
        backup_dir = tempfile.mkdtemp(prefix="dmarket_backup_")
        logger.info(f"Создание резервной копии в {backup_dir}")
        
        # Файлы, которые нужно сохранить
        files_to_backup = [
            ".env",
            "database.db",
            "config.json",
            "user_settings.json"
        ]
        
        # Создаем резервные копии
        for file_path in files_to_backup:
            if os.path.exists(file_path):
                shutil.copy2(file_path, os.path.join(backup_dir, os.path.basename(file_path)))
                logger.info(f"Создана резервная копия: {file_path}")
        
        return backup_dir
    except Exception as e:
        logger.error(f"Ошибка при создании резервной копии: {e}")
        return ""

def restore_user_data(backup_dir: str) -> bool:
    """
    Восстанавливает пользовательские данные из резервной копии.
    
    Копирует файлы из директории резервной копии обратно в рабочую директорию,
    перезаписывая существующие файлы.
    
    Args:
        backup_dir (str): Путь к директории с резервной копией
        
    Returns:
        bool: True если восстановление успешно, False в противном случае
    
    Raises:
        Exception: Любые исключения при восстановлении данных
    """
    try:
        if not backup_dir or not os.path.exists(backup_dir):
            logger.error(f"Директория с резервной копией не существует: {backup_dir}")
            return False
        
        # Восстанавливаем файлы
        for file_name in os.listdir(backup_dir):
            source_path = os.path.join(backup_dir, file_name)
            dest_path = os.path.join(os.getcwd(), file_name)
            
            # Если это файл, копируем его
            if os.path.isfile(source_path):
                shutil.copy2(source_path, dest_path)
                logger.info(f"Восстановлен файл: {file_name}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при восстановлении данных: {e}")
        return False

def fetch_latest_changes() -> Tuple[bool, str]:
    """
    Получает последние изменения из удаленного репозитория и проверяет наличие обновлений.
    
    Выполняет команды Git для получения последних изменений из удаленного репозитория
    и проверяет, есть ли изменения, которые нужно применить.
    
    Returns:
        Tuple[bool, str]: Кортеж из:
            - bool: Статус операции (True - успешно, False - ошибка)
            - str: Сообщение о результате:
                - "already_updated" - обновления не требуются
                - "updates_available" - доступны обновления
                - сообщение об ошибке в случае проблемы
    
    Raises:
        subprocess.SubprocessError: Если возникла ошибка при выполнении Git-команд
    """
    try:
        # Получаем изменения
        fetch_result = subprocess.run(["git", "fetch", "origin", "main"], capture_output=True, text=True)
        if fetch_result.returncode != 0:
            logger.error(f"Ошибка при получении изменений: {fetch_result.stderr}")
            return False, fetch_result.stderr
        
        # Смотрим, есть ли изменения
        diff_result = subprocess.run(["git", "diff", "HEAD", "origin/main", "--name-only"], capture_output=True, text=True)
        
        if not diff_result.stdout.strip():
            logger.info("Обновления не требуются. У вас уже установлена последняя версия.")
            return True, "already_updated"
        
        # Получаем список измененных файлов
        changed_files = diff_result.stdout.strip().split("\n")
        logger.info(f"Доступны обновления. Изменены следующие файлы: {', '.join(changed_files[:5])}")
        
        if len(changed_files) > 5:
            logger.info(f"...и еще {len(changed_files) - 5} файлов")
        
        return True, "updates_available"
    except subprocess.SubprocessError as e:
        logger.error(f"Ошибка при проверке обновлений: {e}")
        return False, str(e)

def apply_updates(backup_dir: str) -> bool:
    """
    Применяет обновления из удаленного репозитория.
    
    Сохраняет текущие изменения, переключается на нужную ветку,
    выполняет обновление через git pull, восстанавливает пользовательские данные
    и локальные изменения.
    
    Args:
        backup_dir (str): Путь к директории с резервной копией
        
    Returns:
        bool: True если обновление успешно, False в противном случае
    
    Raises:
        subprocess.SubprocessError: Если возникла ошибка при выполнении Git-команд
    """
    try:
        # Получаем текущую ветку
        branch_result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
        current_branch = branch_result.stdout.strip() or "main"
        
        # Сохраняем любые локальные изменения
        stash_result = subprocess.run(["git", "stash"], capture_output=True, text=True)
        stashed = "No local changes to save" not in stash_result.stdout
        
        # Переключаемся на ветку main, если еще не на ней
        if current_branch != "main":
            subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)
        
        # Применяем обновления (используем pull с опцией --rebase)
        logger.info("Применение обновлений...")
        pull_result = subprocess.run(["git", "pull", "--rebase", "origin", "main"], capture_output=True, text=True)
        
        if pull_result.returncode != 0:
            logger.error(f"Ошибка при применении обновлений: {pull_result.stderr}")
            # Восстанавливаем данные из резервной копии
            restore_user_data(backup_dir)
            return False
        
        # Восстанавливаем пользовательские данные
        restore_user_data(backup_dir)
        
        # Восстанавливаем сохраненные локальные изменения
        if stashed:
            subprocess.run(["git", "stash", "pop"], capture_output=True)
        
        logger.info("Обновления успешно применены")
        return True
    except subprocess.SubprocessError as e:
        logger.error(f"Ошибка при применении обновлений: {e}")
        # Восстанавливаем данные из резервной копии
        restore_user_data(backup_dir)
        return False

def check_dependencies() -> bool:
    """
    Проверяет и устанавливает зависимости после обновления.
    
    Проверяет наличие файла requirements.txt и выполняет установку
    зависимостей с помощью pip.
    
    Returns:
        bool: True если все зависимости установлены успешно, 
              False если файл не найден или возникла ошибка
    
    Raises:
        subprocess.SubprocessError: Если возникла ошибка при установке зависимостей
    """
    try:
        if os.path.exists("requirements.txt"):
            logger.info("Обновление зависимостей...")
            result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Ошибка при обновлении зависимостей: {result.stderr}")
                return False
            
            logger.info("Зависимости успешно обновлены")
        else:
            logger.warning("Файл requirements.txt не найден, зависимости не обновлены")
        
        return True
    except subprocess.SubprocessError as e:
        logger.error(f"Ошибка при обновлении зависимостей: {e}")
        return False

def generate_update_report(status: bool, details: Dict[str, Any]) -> None:
    """
    Генерирует отчет об обновлении и сохраняет его в JSON-файл.
    
    Создает структурированный отчет с информацией о времени обновления,
    статусе операций и деталях процесса.
    
    Args:
        status (bool): Общий статус обновления (True - успешно, False - ошибка)
        details (Dict[str, Any]): Детали процесса обновления, включая статусы
                                отдельных этапов
    
    Returns:
        None
    
    Raises:
        Exception: При возникновении ошибок во время создания отчета
    """
    try:
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "success" if status else "failed",
            "details": details
        }
        
        with open("update_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        
        logger.info("Отчет об обновлении сохранен в файл update_report.json")
    except Exception as e:
        logger.error(f"Ошибка при создании отчета: {e}")

def update_bot(force: bool = False) -> int:
    """
    Обновляет бота из удаленного репозитория.
    
    Основная функция, которая выполняет весь процесс обновления:
    1. Проверяет установку Git
    2. Проверяет/инициализирует репозиторий
    3. Создает резервную копию пользовательских данных
    4. Получает и применяет обновления
    5. Обновляет зависимости
    6. Генерирует отчет
    
    Args:
        force (bool): Принудительно применить обновления даже если
                    версия уже актуальна. По умолчанию False.
        
    Returns:
        int: Код завершения (0 - успех, 1 - ошибка)
    """
    logger.info("=== Запуск процесса обновления DMarket Trading Bot ===")
    
    update_details = {
        "backup_created": False,
        "updates_available": False,
        "updates_applied": False,
        "dependencies_updated": False
    }
    
    # Проверяем, установлен ли Git
    if not check_git_installed():
        generate_update_report(False, update_details)
        return 1
    
    # Проверяем, является ли текущая директория Git-репозиторием
    if not is_git_repository():
        logger.warning("Текущая директория не является Git-репозиторием")
        
        if not initialize_repository():
            generate_update_report(False, update_details)
            return 1
    
    # Создаем резервную копию пользовательских данных
    backup_dir = backup_user_data()
    update_details["backup_created"] = bool(backup_dir)
    
    # Проверяем наличие обновлений
    update_status, update_message = fetch_latest_changes()
    
    if not update_status:
        logger.error("Не удалось проверить наличие обновлений")
        generate_update_report(False, update_details)
        return 1
    
    update_details["updates_available"] = (update_message == "updates_available")
    
    # Если обновления доступны или принудительное обновление
    if update_message == "updates_available" or force:
        # Применяем обновления
        if apply_updates(backup_dir):
            update_details["updates_applied"] = True
            
            # Обновляем зависимости
            update_details["dependencies_updated"] = check_dependencies()
        else:
            logger.error("Не удалось применить обновления")
            generate_update_report(False, update_details)
            return 1
    
    # Очищаем временную директорию
    if backup_dir and os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    
    # Генерируем отчет
    generate_update_report(True, update_details)
    
    logger.info("=== Процесс обновления DMarket Trading Bot завершен ===")
    
    if update_details["updates_applied"]:
        print("\nБот успешно обновлен до последней версии!")
    else:
        print("\nОбновления не требуются. У вас уже установлена последняя версия.")
    
    return 0

def main() -> int:
    """
    Основная функция скрипта обновления.
    
    Обрабатывает аргументы командной строки и запускает процесс обновления
    с указанными параметрами.
    
    Returns:
        int: Код завершения (0 - успех, 1 - ошибка)
    """
    parser = argparse.ArgumentParser(description="Обновление DMarket Trading Bot")
    parser.add_argument("--force", action="store_true", help="Принудительно применить обновления")
    parser.add_argument("--set-repo", help="Установить URL репозитория")
    
    args = parser.parse_args()
    
    # Если нужно установить URL репозитория
    if args.set_repo:
        global GITHUB_REPO
        GITHUB_REPO = args.set_repo
        logger.info(f"Установлен URL репозитория: {GITHUB_REPO}")
    
    return update_bot(force=args.force)

if __name__ == "__main__":
    sys.exit(main()) 