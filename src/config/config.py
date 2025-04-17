"""
Модуль с конфигурацией приложения.
"""

import os
import logging
import logging.handlers
import yaml
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Any, List, Optional, Union

# Путь к корневой директории проекта и файлу конфигурации
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
CONFIG_PATH = os.path.join(PROJECT_ROOT, "src", "config", "config.yaml")

# Загрузка конфигурации из YAML
def load_yaml_config(config_path: str = CONFIG_PATH) -> Dict[str, Any]:
    """
    Загружает конфигурацию из YAML-файла
    
    Args:
        config_path: Путь к файлу конфигурации
        
    Returns:
        Dict[str, Any]: Словарь с настройками
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as config_file:
            config = yaml.safe_load(config_file)
            return config
    except FileNotFoundError:
        logging.error(f"Конфигурационный файл не найден: {config_path}")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Ошибка при парсинге YAML: {e}")
        return {}

# Загружаем конфигурацию
yaml_config = load_yaml_config()

class Config:
    """
    Класс для доступа к настройкам приложения.
    Комбинирует настройки из .env и config.yaml
    """
    
    # Общие настройки
    APP_NAME = os.getenv("APP_NAME") or yaml_config.get("app", {}).get("name", "DMarket Trading Bot")
    APP_VERSION = os.getenv("APP_VERSION") or yaml_config.get("app", {}).get("version", "1.0.0")
    DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "t") or yaml_config.get("app", {}).get("debug", True)
    LOG_LEVEL = os.getenv("LOG_LEVEL") or yaml_config.get("app", {}).get("log_level", "INFO")
    
    # Настройки Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",") if os.getenv("ADMIN_IDS") else yaml_config.get("telegram", {}).get("admin_ids", [])
    
    # Настройки API DMarket
    API_URL = os.getenv("API_URL") or yaml_config.get("api", {}).get("base_url", "https://api.dmarket.com")
    API_KEY = os.getenv("API_KEY")
    API_SECRET = os.getenv("API_SECRET")
    API_TIMEOUT = int(os.getenv("API_TIMEOUT") or yaml_config.get("api", {}).get("timeout", 30))
    API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES") or yaml_config.get("api", {}).get("max_retries", 3))
    
    # Настройки Redis
    REDIS_URL = os.getenv("REDIS_URL") or f"redis://{yaml_config.get('redis', {}).get('host', 'localhost')}:{yaml_config.get('redis', {}).get('port', 6379)}/{yaml_config.get('redis', {}).get('db', 0)}"
    
    # Настройки базы данных
    DB_PATH = os.getenv("DB_PATH") or yaml_config.get("database", {}).get("sqlite", {}).get("path", "db/dmarket_bot.db")
    
    # Настройки арбитража
    @classmethod
    def get_arbitrage_config(cls, mode: str) -> Dict[str, Any]:
        """
        Получает настройки арбитража для указанного режима
        
        Args:
            mode: Режим арбитража (balance_boost, medium_trader, trade_pro)
            
        Returns:
            Dict[str, Any]: Словарь с настройками
        """
        default_config = {
            "min_profit": 1.0,
            "max_profit": 5.0,
            "min_price": 0.5,
            "max_price": 20.0,
            "require_liquidity": False,
            "max_items": 100
        }
        
        arbitrage_config = yaml_config.get("arbitrage", {}).get(mode, {})
        if not arbitrage_config:
            return default_config
            
        return arbitrage_config
    
    # Настройки игр
    @classmethod
    def get_games_config(cls) -> List[Dict[str, Any]]:
        """
        Получает настройки для всех игр
        
        Returns:
            List[Dict[str, Any]]: Список словарей с настройками игр
        """
        return yaml_config.get("games", [])
    
    @classmethod
    def get_game_config(cls, game_code: str) -> Optional[Dict[str, Any]]:
        """
        Получает настройки для указанной игры
        
        Args:
            game_code: Код игры
            
        Returns:
            Optional[Dict[str, Any]]: Словарь с настройками игры или None
        """
        games = cls.get_games_config()
        for game in games:
            if game.get("code") == game_code:
                return game
        return None
    
    @classmethod
    def get_enabled_games(cls) -> List[str]:
        """
        Возвращает список кодов включенных игр
        
        Returns:
            List[str]: Список кодов игр
        """
        games = cls.get_games_config()
        return [game.get("code") for game in games if game.get("enabled", True)]
    
    # Пути к директориям
    @classmethod
    def get_path(cls, path_type: str) -> str:
        """
        Возвращает путь к директории указанного типа
        
        Args:
            path_type: Тип пути (logs, reports, cache, exports)
            
        Returns:
            str: Путь к директории
        """
        path = yaml_config.get("paths", {}).get(path_type)
        if not path:
            # Значения по умолчанию
            defaults = {
                "logs": "logs/",
                "reports": "reports/",
                "cache": "cache/",
                "exports": "exports/"
            }
            path = defaults.get(path_type, "")
        
        # Преобразуем в абсолютный путь
        if path:
            path = os.path.join(PROJECT_ROOT, path)
            
            # Создаем директорию, если её нет
            os.makedirs(path, exist_ok=True)
            
        return path

    # Добавляем настройки API как атрибут класса
    @property
    def api(self):
        """
        Возвращает словарь с настройками API
        """
        return {
            "dmarket": {
                "url": os.getenv("DMARKET_API_URL") or yaml_config.get("api", {}).get("dmarket", {}).get("url", "https://api.dmarket.com"),
                "version": yaml_config.get("api", {}).get("dmarket", {}).get("version", "v1"),
                "rate_limit": int(yaml_config.get("api", {}).get("dmarket", {}).get("rate_limit", 5))
            },
            "steam": {
                "url": yaml_config.get("api", {}).get("steam", {}).get("url", "https://api.steampowered.com"),
                "version": yaml_config.get("api", {}).get("steam", {}).get("version", "v2"),
                "rate_limit": int(yaml_config.get("api", {}).get("steam", {}).get("rate_limit", 1))
            }
        }

# Настройка логирования
def setup_logging() -> logging.Logger:
    """
    Настраивает систему логирования.
    
    Returns:
        logging.Logger: Настроенный логгер
    """
    # Получаем путь к директории логов
    logs_dir = Config.get_path("logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Имя файла лога включает дату
    import datetime
    log_file = os.path.join(logs_dir, f"bot_{datetime.datetime.now().strftime('%Y%m%d')}.log")
    
    # Получаем уровень логирования из конфигурации
    log_level_str = Config.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Настраиваем форматтер с явным указанием локали для корректного отображения русских символов
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    
    # Настраиваем обработчики с явным указанием кодировки UTF-8
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Настраиваем корневой логгер
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Удаляем существующие обработчики (если они есть)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Добавляем новые обработчики
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Создаем и возвращаем логгер для нашего модуля
    module_logger = logging.getLogger("telegram_bot")
    
    # Устанавливаем параметры логирования
    import sys
    import locale
    
    # Устанавливаем локаль для вывода русских символов
    locale.setlocale(locale.LC_ALL, '')
    
    # Проверяем и выводим информацию о кодировке
    console_encoding = sys.stdout.encoding
    locale_info = locale.getlocale()
    module_logger.info(f"Кодировка консоли: {console_encoding}")
    module_logger.info(f"Локаль системы: {locale_info}, кодировка: {locale.getpreferredencoding()}")
    
    if Config.DEBUG:
        module_logger.debug("Включен режим отладки")
    
    return module_logger
