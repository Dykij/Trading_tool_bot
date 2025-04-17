"""
Модуль безопасного хранения конфигурации для торгового бота.

Предоставляет методы для:
- Шифрования и дешифрования чувствительных данных
- Безопасного хранения и загрузки API-ключей
- Управления конфигурационными директориями и файлами

Использует Fernet (симметричное шифрование) и PBKDF2 для генерации ключа из пароля.
"""

import base64
import getpass
import hashlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

# Добавляем попытку импорта зависимостей и предлагаем установить их, если они отсутствуют
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    print("Отсутствуют необходимые зависимости. Установите их с помощью:")
    print("pip install cryptography")
    sys.exit(1)

# Импортируем модуль обработки ошибок
from src.utils.error_handling import (
    BotError, ConfigError, ErrorSeverity, handle_errors, log_execution, retry
)

# Настройка логирования
logger = logging.getLogger("secure_config")


class SecureConfig:
    """
    Класс для безопасного хранения и управления конфигурацией.
    
    Обеспечивает:
    - Шифрование и дешифрование чувствительных данных
    - Управление конфигурационными файлами
    - Защиту API-ключей и других секретов
    """
    
    # Константы
    DEFAULT_CONFIG_DIR = ".dmarket_bot"
    DEFAULT_KEYS_FILE = "api_keys.enc"
    DEFAULT_SETTINGS_FILE = "settings.yaml"
    DEFAULT_ITERATIONS = 100000  # Количество итераций для PBKDF2
    DEFAULT_SALT_SIZE = 16  # Размер соли в байтах
    
    def __init__(
        self,
        config_dir: Optional[str] = None,
        password: Optional[str] = None,
        salt: Optional[bytes] = None,
        auto_create: bool = True
    ):
        """
        Инициализация конфигурации.
        
        Args:
            config_dir: Путь к директории конфигурации (по умолчанию используется домашняя директория пользователя)
            password: Пароль для шифрования (если None, будет запрошен при необходимости)
            salt: Соль для генерации ключа (если None, будет создана случайная соль)
            auto_create: Автоматически создавать конфигурационную директорию, если она не существует
        """
        # Инициализация путей
        self._config_path = self._init_config_path(config_dir)
        self._keys_path = self._config_path / self.DEFAULT_KEYS_FILE
        self._settings_path = self._config_path / self.DEFAULT_SETTINGS_FILE
        
        # Создание директории конфигурации при необходимости
        if auto_create and not self._config_path.exists():
            self._config_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Создана директория конфигурации: {self._config_path}")
        
        # Инициализация шифрования
        self._password = password
        self._salt = salt or os.urandom(self.DEFAULT_SALT_SIZE)
        self._key = None  # Ключ шифрования будет создан при необходимости
    
    @staticmethod
    def _init_config_path(config_dir: Optional[str] = None) -> Path:
        """Инициализирует путь к директории конфигурации."""
        if config_dir:
            # Используем предоставленный путь
            return Path(config_dir).expanduser().resolve()
        else:
            # Используем директорию по умолчанию в домашней директории пользователя
            return Path.home() / SecureConfig.DEFAULT_CONFIG_DIR
    
    def _ensure_keys_dir_exists(self) -> None:
        """Убеждается, что директория для ключей существует."""
        if not self._config_path.exists():
            self._config_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Создана директория для ключей: {self._config_path}")
    
    def _get_encryption_key(self, password: Optional[str] = None) -> bytes:
        """
        Получает ключ шифрования из пароля.
        
        Args:
            password: Пароль (если None, используется сохраненный пароль или запрашивается интерактивно)
            
        Returns:
            Ключ шифрования
        
        Raises:
            ConfigError: Если не удается получить пароль
        """
        if self._key is not None:
            return self._key
        
        # Получаем пароль
        used_password = password or self._password
        if used_password is None:
            try:
                used_password = getpass.getpass("Введите пароль для доступа к конфигурации: ")
                if not used_password:
                    raise ConfigError(
                        "Пароль не может быть пустым",
                        severity=ErrorSeverity.HIGH
                    )
            except Exception as e:
                raise ConfigError(
                    "Не удалось получить пароль", 
                    {"error": str(e)},
                    ErrorSeverity.HIGH
                )
        
        # Сохраняем пароль для повторного использования
        self._password = used_password
        
        # Генерируем ключ из пароля с использованием PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=self.DEFAULT_ITERATIONS,
        )
        
        # Генерируем ключ и создаем объект Fernet
        key_material = kdf.derive(used_password.encode())
        self._key = base64.urlsafe_b64encode(key_material)
        
        return self._key
    
    def _get_fernet(self, password: Optional[str] = None) -> Fernet:
        """
        Создает объект Fernet для шифрования/дешифрования.
        
        Args:
            password: Пароль для генерации ключа
            
        Returns:
            Объект Fernet
        """
        key = self._get_encryption_key(password)
        return Fernet(key)
    
    @log_execution(log_level=logging.DEBUG)
    def encrypt(self, data: str, password: Optional[str] = None) -> bytes:
        """
        Шифрует строковые данные.
        
        Args:
            data: Строка для шифрования
            password: Пароль для шифрования (если None, используется сохраненный или запрашивается)
            
        Returns:
            Зашифрованные данные в виде байтов
        """
        fernet = self._get_fernet(password)
        return fernet.encrypt(data.encode())
    
    @log_execution(log_level=logging.DEBUG)
    @handle_errors(error_types=[InvalidToken], default_error_type=ConfigError)
    def decrypt(self, encrypted_data: bytes, password: Optional[str] = None) -> str:
        """
        Дешифрует данные.
        
        Args:
            encrypted_data: Зашифрованные данные
            password: Пароль для дешифрования (если None, используется сохраненный или запрашивается)
            
        Returns:
            Расшифрованная строка
            
        Raises:
            ConfigError: При ошибке дешифрования (например, неверный пароль)
        """
        fernet = self._get_fernet(password)
        try:
            decrypted_data = fernet.decrypt(encrypted_data)
            return decrypted_data.decode()
        except InvalidToken:
            raise ConfigError(
                "Не удалось расшифровать данные. Возможно, неверный пароль.",
                severity=ErrorSeverity.HIGH
            )
    
    @log_execution(log_level=logging.INFO)
    @handle_errors(default_error_type=ConfigError)
    def save_api_keys(
        self,
        api_keys: Dict[str, Dict[str, str]],
        password: Optional[str] = None,
        file_path: Optional[Union[str, Path]] = None
    ) -> None:
        """
        Сохраняет API-ключи в зашифрованный файл.
        
        Args:
            api_keys: Словарь с API-ключами в формате {service_name: {key_type: key_value, ...}, ...}
            password: Пароль для шифрования
            file_path: Путь к файлу для сохранения (если None, используется путь по умолчанию)
            
        Example:
            {
                "dmarket": {
                    "public_key": "your_public_key",
                    "secret_key": "your_secret_key"
                },
                "steam": {
                    "api_key": "your_steam_api_key"
                }
            }
        """
        # Убеждаемся, что директория существует
        self._ensure_keys_dir_exists()
        
        # Определяем путь к файлу
        target_path = Path(file_path) if file_path else self._keys_path
        
        # Преобразуем словарь в JSON
        json_data = json.dumps(api_keys, indent=2)
        
        # Шифруем данные
        encrypted_data = self.encrypt(json_data, password)
        
        # Записываем в файл
        with open(target_path, "wb") as f:
            f.write(self._salt)  # Сохраняем соль в начале файла
            f.write(encrypted_data)
        
        logger.info(f"API ключи успешно сохранены в {target_path}")
    
    @log_execution(log_level=logging.INFO)
    @retry(max_attempts=3, delay=1.0, retry_on=ConfigError)
    @handle_errors(default_error_type=ConfigError)
    def load_api_keys(
        self,
        password: Optional[str] = None,
        file_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Dict[str, str]]:
        """
        Загружает API-ключи из зашифрованного файла.
        
        Args:
            password: Пароль для дешифрования
            file_path: Путь к файлу (если None, используется путь по умолчанию)
            
        Returns:
            Словарь с API-ключами
            
        Raises:
            ConfigError: Если файл не существует или при ошибке дешифрования
        """
        # Определяем путь к файлу
        target_path = Path(file_path) if file_path else self._keys_path
        
        # Проверяем существование файла
        if not target_path.exists():
            raise ConfigError(
                f"Файл с API-ключами не найден: {target_path}",
                severity=ErrorSeverity.MEDIUM
            )
        
        try:
            # Читаем файл
            with open(target_path, "rb") as f:
                file_content = f.read()
                
                # Извлекаем соль и зашифрованные данные
                if len(file_content) <= self.DEFAULT_SALT_SIZE:
                    raise ConfigError(
                        "Поврежденный файл с API-ключами",
                        severity=ErrorSeverity.HIGH
                    )
                
                self._salt = file_content[:self.DEFAULT_SALT_SIZE]
                encrypted_data = file_content[self.DEFAULT_SALT_SIZE:]
            
            # Дешифруем данные
            json_data = self.decrypt(encrypted_data, password)
            
            # Преобразуем JSON в словарь
            api_keys = json.loads(json_data)
            
            logger.info(f"API ключи успешно загружены из {target_path}")
            return api_keys
            
        except json.JSONDecodeError:
            raise ConfigError(
                "Ошибка формата данных API-ключей",
                severity=ErrorSeverity.HIGH
            )
        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(
                f"Ошибка при загрузке API-ключей: {str(e)}",
                {"error": str(e)},
                severity=ErrorSeverity.HIGH
            )
    
    @log_execution(log_level=logging.INFO)
    def add_api_key(
        self,
        service: str,
        key_type: str,
        key_value: str,
        password: Optional[str] = None,
        file_path: Optional[Union[str, Path]] = None
    ) -> None:
        """
        Добавляет новый API-ключ в конфигурацию.
        
        Args:
            service: Название сервиса (например, 'dmarket', 'steam')
            key_type: Тип ключа (например, 'public_key', 'secret_key', 'api_key')
            key_value: Значение ключа
            password: Пароль для шифрования/дешифрования
            file_path: Путь к файлу с ключами
        """
        try:
            # Пытаемся загрузить существующие ключи
            api_keys = self.load_api_keys(password, file_path)
        except ConfigError:
            # Если файл не существует или поврежден, начинаем с пустого словаря
            api_keys = {}
        
        # Добавляем или обновляем ключ
        if service not in api_keys:
            api_keys[service] = {}
        
        api_keys[service][key_type] = key_value
        
        # Сохраняем обновленные ключи
        self.save_api_keys(api_keys, password, file_path)
        logger.info(f"Добавлен ключ {key_type} для сервиса {service}")
    
    def has_api_keys(self, file_path: Optional[Union[str, Path]] = None) -> bool:
        """
        Проверяет, существует ли файл с API-ключами.
        
        Args:
            file_path: Путь к файлу (если None, используется путь по умолчанию)
            
        Returns:
            True, если файл существует и не пустой, иначе False
        """
        target_path = Path(file_path) if file_path else self._keys_path
        return target_path.exists() and target_path.stat().st_size > 0
    
    @log_execution(log_level=logging.DEBUG)
    def remove_api_key(
        self,
        service: str,
        key_type: Optional[str] = None,
        password: Optional[str] = None,
        file_path: Optional[Union[str, Path]] = None
    ) -> bool:
        """
        Удаляет API-ключ из конфигурации.
        
        Args:
            service: Название сервиса
            key_type: Тип ключа (если None, удаляются все ключи сервиса)
            password: Пароль для шифрования/дешифрования
            file_path: Путь к файлу с ключами
            
        Returns:
            True, если ключ был успешно удален, иначе False
        """
        try:
            # Загружаем существующие ключи
            api_keys = self.load_api_keys(password, file_path)
            
            # Проверяем, существует ли сервис
            if service not in api_keys:
                logger.warning(f"Сервис {service} не найден в API-ключах")
                return False
            
            # Удаляем конкретный ключ или весь сервис
            if key_type is None:
                # Удаляем все ключи сервиса
                del api_keys[service]
                logger.info(f"Удалены все ключи для сервиса {service}")
            else:
                # Удаляем конкретный ключ
                if key_type in api_keys[service]:
                    del api_keys[service][key_type]
                    logger.info(f"Удален ключ {key_type} для сервиса {service}")
                    
                    # Если у сервиса не осталось ключей, удаляем его
                    if not api_keys[service]:
                        del api_keys[service]
                else:
                    logger.warning(f"Ключ {key_type} не найден для сервиса {service}")
                    return False
            
            # Сохраняем обновленные ключи
            self.save_api_keys(api_keys, password, file_path)
            return True
            
        except ConfigError as e:
            logger.error(f"Ошибка при удалении API-ключа: {e}")
            return False


# Функции для удобного доступа к API-ключам

def get_config_instance(
    config_dir: Optional[str] = None,
    password: Optional[str] = None
) -> SecureConfig:
    """
    Получает экземпляр SecureConfig.
    
    Args:
        config_dir: Путь к директории конфигурации
        password: Пароль для шифрования/дешифрования
        
    Returns:
        Экземпляр SecureConfig
    """
    return SecureConfig(config_dir=config_dir, password=password, auto_create=True)


@log_execution(log_level=logging.INFO)
@handle_errors(default_error_type=ConfigError)
def save_api_keys(
    api_keys: Dict[str, Dict[str, str]],
    password: Optional[str] = None,
    config_dir: Optional[str] = None
) -> None:
    """
    Сохраняет API-ключи в зашифрованный файл.
    
    Args:
        api_keys: Словарь с API-ключами
        password: Пароль для шифрования
        config_dir: Путь к директории конфигурации
    """
    config = get_config_instance(config_dir, password)
    config.save_api_keys(api_keys, password)


@log_execution(log_level=logging.INFO)
@handle_errors(default_error_type=ConfigError)
def load_api_keys(
    password: Optional[str] = None,
    config_dir: Optional[str] = None
) -> Dict[str, Dict[str, str]]:
    """
    Загружает API-ключи из зашифрованного файла.
    
    Args:
        password: Пароль для дешифрования
        config_dir: Путь к директории конфигурации
        
    Returns:
        Словарь с API-ключами
    """
    config = get_config_instance(config_dir, password)
    return config.load_api_keys(password)


@log_execution(log_level=logging.INFO)
def add_api_key(
    service: str,
    key_type: str,
    key_value: str,
    password: Optional[str] = None,
    config_dir: Optional[str] = None
) -> None:
    """
    Добавляет новый API-ключ в конфигурацию.
    
    Args:
        service: Название сервиса
        key_type: Тип ключа
        key_value: Значение ключа
        password: Пароль для шифрования/дешифрования
        config_dir: Путь к директории конфигурации
    """
    config = get_config_instance(config_dir, password)
    config.add_api_key(service, key_type, key_value, password)


def has_api_keys(config_dir: Optional[str] = None) -> bool:
    """
    Проверяет, существует ли файл с API-ключами.
    
    Args:
        config_dir: Путь к директории конфигурации
        
    Returns:
        True, если файл существует и не пустой, иначе False
    """
    config = get_config_instance(config_dir)
    return config.has_api_keys()


@log_execution(log_level=logging.INFO)
def get_dmarket_keys(
    password: Optional[str] = None,
    config_dir: Optional[str] = None
) -> Tuple[str, str]:
    """
    Получает ключи для DMarket API.
    
    Args:
        password: Пароль для дешифрования
        config_dir: Путь к директории конфигурации
        
    Returns:
        Кортеж (public_key, secret_key)
        
    Raises:
        ConfigError: Если ключи не найдены или неполные
    """
    api_keys = load_api_keys(password, config_dir)
    
    if "dmarket" not in api_keys:
        raise ConfigError(
            "Ключи DMarket не найдены. Добавьте их с помощью add_api_key()",
            severity=ErrorSeverity.HIGH
        )
    
    dmarket_keys = api_keys["dmarket"]
    
    if "public_key" not in dmarket_keys or "secret_key" not in dmarket_keys:
        raise ConfigError(
            "Неполные ключи DMarket. Требуются public_key и secret_key",
            severity=ErrorSeverity.HIGH
        )
    
    return dmarket_keys["public_key"], dmarket_keys["secret_key"]


@log_execution(log_level=logging.INFO)
def get_steam_key(
    password: Optional[str] = None,
    config_dir: Optional[str] = None
) -> str:
    """
    Получает ключ для Steam API.
    
    Args:
        password: Пароль для дешифрования
        config_dir: Путь к директории конфигурации
        
    Returns:
        API-ключ Steam
        
    Raises:
        ConfigError: Если ключ не найден
    """
    api_keys = load_api_keys(password, config_dir)
    
    if "steam" not in api_keys or "api_key" not in api_keys["steam"]:
        raise ConfigError(
            "Ключ Steam API не найден. Добавьте его с помощью add_api_key()",
            severity=ErrorSeverity.HIGH
        )
    
    return api_keys["steam"]["api_key"]


# Функции для миграции конфигурации

@log_execution(log_level=logging.INFO)
def migrate_plain_keys_to_secure(
    plain_file_path: Union[str, Path],
    password: Optional[str] = None,
    config_dir: Optional[str] = None
) -> bool:
    """
    Мигрирует ключи из обычного файла в зашифрованный.
    
    Args:
        plain_file_path: Путь к файлу с незашифрованными ключами в формате JSON
        password: Пароль для шифрования
        config_dir: Путь к директории конфигурации
        
    Returns:
        True в случае успешной миграции, иначе False
    """
    try:
        plain_path = Path(plain_file_path)
        if not plain_path.exists():
            logger.error(f"Файл {plain_path} не существует")
            return False
        
        # Читаем незашифрованные ключи
        with open(plain_path, "r") as f:
            api_keys = json.load(f)
        
        # Сохраняем ключи в зашифрованном виде
        save_api_keys(api_keys, password, config_dir)
        
        # Делаем резервную копию исходного файла
        backup_path = plain_path.with_suffix(".bak")
        plain_path.rename(backup_path)
        
        logger.info(f"Ключи успешно мигрированы в зашифрованный формат. "
                   f"Резервная копия сохранена в {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при миграции ключей: {e}")
        return False


@log_execution(log_level=logging.INFO)
def create_sample_api_keys(
    password: Optional[str] = None,
    config_dir: Optional[str] = None,
    overwrite: bool = False
) -> None:
    """
    Создает образец файла с API-ключами.
    
    Args:
        password: Пароль для шифрования
        config_dir: Путь к директории конфигурации
        overwrite: Перезаписать существующий файл, если он есть
    """
    config = get_config_instance(config_dir, password)
    
    # Проверяем, существует ли уже файл с ключами
    if config.has_api_keys() and not overwrite:
        logger.warning("Файл с API-ключами уже существует. Используйте overwrite=True для перезаписи.")
        return
    
    # Создаем образец ключей
    sample_keys = {
        "dmarket": {
            "public_key": "YOUR_DMARKET_PUBLIC_KEY",
            "secret_key": "YOUR_DMARKET_SECRET_KEY"
        },
        "steam": {
            "api_key": "YOUR_STEAM_API_KEY"
        }
    }
    
    # Сохраняем образец
    config.save_api_keys(sample_keys, password)
    logger.info("Создан образец файла с API-ключами")


# Проверка, запущен ли модуль как скрипт
if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO, 
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Пример использования
    print("Пример работы с модулем безопасной конфигурации")
    
    # Создаем образец файла с API-ключами
    password = getpass.getpass("Введите пароль для шифрования: ")
    
    # Получаем путь к конфигурации
    config_dir = input("Введите путь к директории конфигурации (Enter для значения по умолчанию): ")
    if not config_dir:
        config_dir = None
    
    # Создаем образец
    create_sample_api_keys(password, config_dir, overwrite=True)
    
    # Выводим справку
    print("\nФайл с API-ключами создан. Для использования в своем коде:")
    print("from src.utils.secure_config import load_api_keys, get_dmarket_keys")
    print("api_keys = load_api_keys(password)")
    print("public_key, secret_key = get_dmarket_keys(password)") 