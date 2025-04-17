#!/usr/bin/env python
"""
Скрипт для проверки целостности и согласованности API вызовов в проекте DMarket Trading Bot.
Анализирует код, чтобы убедиться, что все вызовы API соответствуют методам,
определенным в api_wrapper.py.
"""
import ast
import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


def setup_logging(verbose: bool = False) -> None:
    """
    Настраивает логирование для скрипта.

    Args:
        verbose (bool): Включить подробное логирование

    Returns:
        None
    """
    # Создаем директорию для логов, если она не существует
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'api_consistency_check.log'),
            logging.StreamHandler()
        ]
    )


def find_api_calls(file_path: str) -> List[Tuple[str, int]]:
    """
    Анализирует файл Python и находит все вызовы методов API.

    Args:
        file_path (str): Путь к анализируемому файлу

    Returns:
        List[Tuple[str, int]]: Список кортежей (название метода, номер строки)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        # Проверка на пустой файл
        if not file_content.strip():
            return []

        tree = ast.parse(file_content)

        api_calls = []

        for node in ast.walk(tree):
            # Ищем вызовы методов объекта api
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'api'):
                api_calls.append((node.func.attr, node.lineno))

        return api_calls
    except (SyntaxError, UnicodeDecodeError) as e:
        logging.error(f"Ошибка при анализе файла {file_path}: {e}")
        return []


def find_custom_api_objects(file_path: str) -> List[str]:
    """
    Находит все объекты API, которые имеют нестандартные имена (не 'api').

    Args:
        file_path (str): Путь к анализируемому файлу

    Returns:
        List[str]: Список нестандартных имен объектов API
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        tree = ast.parse(file_content)
        custom_api_objects = set()

        # Поиск импортов и создания экземпляров
        api_classes = ['DMarketAPI', 'ApiWrapper']

        # Поиск переменных, которым присваиваются экземпляры API
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Name)
                            and isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Name)
                            and node.value.func.id in api_classes):
                        custom_api_objects.add(target.id)

        return list(custom_api_objects)
    except Exception as e:
        logging.error(f"Ошибка при поиске нестандартных объектов API в {file_path}: {e}")
        return []


def extract_api_methods(api_wrapper_file: str) -> Set[str]:
    """
    Извлекает все публичные методы из файла API wrapper.

    Args:
        api_wrapper_file (str): Путь к файлу API wrapper

    Returns:
        Set[str]: Множество имен методов API
    """
    try:
        with open(api_wrapper_file, 'r', encoding='utf-8') as f:
            file_content = f.read()

        tree = ast.parse(file_content)
        api_methods = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Анализируем все методы в классах
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # Не включаем приватные методы (с префиксом _)
                        if not item.name.startswith('_'):
                            api_methods.add(item.name)

        return api_methods
    except Exception as e:
        logging.error(f"Ошибка при извлечении методов API из {api_wrapper_file}: {e}")
        return set()


def find_python_files(start_dir: str = '.', exclude_dirs: Optional[Set[str]] = None) -> List[str]:
    """
    Рекурсивно находит все Python файлы в указанной директории.

    Args:
        start_dir (str): Начальная директория для поиска
        exclude_dirs (Optional[Set[str]]): Директории для исключения

    Returns:
        List[str]: Список путей к Python файлам
    """
    if exclude_dirs is None:
        exclude_dirs = {'.git', '__pycache__', 'venv', 'env', '.venv', 'dmarket_bot_env'}

    python_files = []

    for root, dirs, files in os.walk(start_dir):
        # Исключаем указанные директории из поиска
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))

    return python_files


def generate_report(inconsistencies: Dict[str, List[Tuple[str, int]]],
                    api_wrapper_file: str,
                    output_file: Optional[str] = None) -> str:
    """
    Генерирует отчет о найденных несоответствиях в вызовах API.

    Args:
        inconsistencies (Dict[str, List[Tuple[str, int]]]): Словарь с несоответствиями
        api_wrapper_file (str): Путь к файлу API wrapper
        output_file (Optional[str]): Путь к файлу для сохранения отчета

    Returns:
        str: Отчет в текстовом формате
    """
    report = []
    report.append("=" * 80)
    report.append("Отчет о проверке согласованности API в проекте DMarket Trading Bot")
    report.append(f"API wrapper файл: {api_wrapper_file}")
    report.append("=" * 80)

    if not inconsistencies:
        report.append(
            "\nAPI проверка прошла успешно! Все вызовы API соответствуют определенным методам."
        )
    else:
        report.append("\nНайдены несоответствия в вызовах API:")
        for file, calls in inconsistencies.items():
            report.append(f"\nФайл: {file}")
            for call, line_number in sorted(calls, key=lambda x: x[1]):
                report.append(
                    f"  • Строка {line_number}: Метод '{call}' не найден в API wrapper"
                )

        report.append("\nВозможные причины:")
        report.append("1. Опечатка в имени метода")
        report.append("2. Метод был удален или переименован в API wrapper")
        report.append("3. Требуется добавить новый метод в API wrapper")

        report.append("\nРекомендации для исправления:")
        report.append("- Проверьте написание имен методов")
        report.append(
            "- Обновите вызовы API, чтобы они соответствовали текущим методам в API wrapper"
        )

    report_text = "\n".join(report)

    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            logging.info(f"Отчет сохранен в файл: {output_file}")
        except Exception as e:
            logging.error(f"Ошибка при сохранении отчета в файл {output_file}: {e}")

    return report_text


def check_api_consistency(api_wrapper_file: str,
                          files_to_check: List[str],
                          output_file: Optional[str] = None,
                          ignore_missing: Optional[List[str]] = None) -> bool:
    """
    Проверяет согласованность вызовов API с доступными методами в API wrapper.

    Args:
        api_wrapper_file (str): Путь к файлу API wrapper
        files_to_check (List[str]): Список файлов для проверки
        output_file (Optional[str]): Путь к файлу для сохранения отчета
        ignore_missing (Optional[List[str]]): Список методов, которые следует игнорировать

    Returns:
        bool: True, если все вызовы API корректны, иначе False
    """
    if not os.path.exists(api_wrapper_file):
        logging.error(f"API wrapper файл не найден: {api_wrapper_file}")
        return False

    if ignore_missing is None:
        ignore_missing = []

    # Извлекаем методы из API wrapper
    api_methods = extract_api_methods(api_wrapper_file)

    if not api_methods:
        logging.error(f"Не удалось извлечь методы из API wrapper файла: {api_wrapper_file}")
        return False

    # Анализируем вызовы API в других файлах
    inconsistencies = {}

    for file in files_to_check:
        if os.path.exists(file) and file != api_wrapper_file:
            logging.debug(f"Анализ файла: {file}")

            # Находим стандартные вызовы API
            calls = find_api_calls(file)

            # Проверяем вызовы на соответствие определенным методам
            invalid_calls = []
            for call, line_number in calls:
                if call not in api_methods and call not in ignore_missing:
                    invalid_calls.append((call, line_number))

            # Если найдены несоответствия, добавляем их в отчет
            if invalid_calls:
                inconsistencies[file] = invalid_calls

    # Генерируем отчет
    report = generate_report(inconsistencies, api_wrapper_file, output_file)

    if inconsistencies:
        print(report)
        logging.warning("Найдены несоответствия в вызовах API. Подробности в отчете.")
        return False
    else:
        logging.info(
            "API проверка прошла успешно. Все вызовы API соответствуют определенным методам."
        )
        print(report)
        return True


def parse_args() -> argparse.Namespace:
    """
    Разбирает аргументы командной строки.

    Returns:
        argparse.Namespace: Объект с аргументами
    """
    parser = argparse.ArgumentParser(
        description="Скрипт для проверки согласованности API вызовов в проекте DMarket Trading Bot"
    )

    parser.add_argument(
        "-a", "--api-wrapper",
        default="api_wrapper.py",
        help="Путь к файлу API wrapper (по умолчанию: api_wrapper.py)"
    )
    parser.add_argument(
        "-d", "--directory",
        default=".",
        help="Директория для поиска файлов (по умолчанию: текущая директория)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Путь к файлу для сохранения отчета"
    )
    parser.add_argument(
        "-i", "--ignore",
        nargs="+",
        help="Список методов, которые следует игнорировать"
    )
    parser.add_argument(
        "-e", "--exclude",
        nargs="+",
        help="Директории для исключения из проверки"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Включить подробное логирование"
    )

    return parser.parse_args()


def main() -> int:
    """
    Основная функция скрипта.

    Returns:
        int: Код завершения (0 - успех, 1 - ошибка)
    """
    args = parse_args()
    setup_logging(args.verbose)

    api_wrapper_file = os.path.abspath(args.api_wrapper)
    directory = args.directory
    output_file = args.output
    exclude_dirs = set(args.exclude) if args.exclude else None
    ignore_missing = args.ignore or []

    logging.info("Запуск проверки API согласованности")
    logging.info(f"API wrapper файл: {api_wrapper_file}")
    logging.info(f"Директория для проверки: {directory}")

    if not os.path.exists(api_wrapper_file):
        logging.error(f"API wrapper файл не найден: {api_wrapper_file}")
        return 1

    # Находим все Python файлы для проверки
    python_files = find_python_files(directory, exclude_dirs)

    if not python_files:
        logging.warning("Не найдено Python файлов для проверки.")
        return 1

    logging.info(
        f"Найдено {len(python_files)} Python файлов для проверки."
    )

    # Проверяем согласованность API
    success = check_api_consistency(
        api_wrapper_file,
        python_files,
        output_file,
        ignore_missing
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
