"""
Модуль для безопасного управления API-ключами.

Модуль предоставляет функциональность для шифрования, хранения и
получения API-ключей и других чувствительных данных для приложения
DMarket Trading Bot.
"""

import os
import json
import base64
import logging
from typing import Dict, Any, Optional, Tuple, Union
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.utils.error_handling import BaseBotError, ensure, ensure_not_none


class KeyError(BaseBotError):
    """Исключение, связанное с операциями с API-ключами."""
    pass


class ApiKeyManager:
    """
    Класс для безопасного управления API-ключами.
    
    Класс обеспечивает шифрование API-ключей и других чувствительных данных,
    их хранение и получение. Используется для защиты API-ключей от
    несанкционированного доступа.
    """
    
    def __init__(
        self, 
        keys_file: Union[str, Path],
        password: Optional[str] = None,
        auto_create: bool = True
    ):
        """
        Инициализация менеджера API-ключей.
        
        Args:
            keys_file: Путь к файлу с ключами.
            password: Пароль для шифрования/дешифрования данных.
                     Если не указан, будет использован пароль из переменной окружения.
            auto_create: Если True, автоматически создает файл с ключами.
        
        Raises:
            KeyError: Если файл не существует и auto_create=False.
        """
        self.logger = logging.getLogger(__name__)
        self.keys_file = Path(keys_file)
        
        # Получаем пароль из переменной окружения или используем переданный
        self.password = password or os.environ.get("DMARKET_CRYPTO_KEY")
        ensure(self.password, "Пароль для шифрования не указан")
        
        # Генерируем ключ на основе пароля
        self.fernet = self._create_cipher()
        
        # Создаем файл с ключами, если его нет
        if not self.keys_file.exists():
            if auto_create:
                self.logger.info(f"Создание нового файла ключей: {self.keys_file}")
                self.keys_file.parent.mkdir(parents=True, exist_ok=True)
                self.save_keys({})
            else:
                raise KeyError(f"Файл с ключами не существует: {self.keys_file}")
    
    def _create_cipher(self) -> Fernet:
        """
        Создает объект шифрования на основе пароля.
        
        Returns:
            Объект Fernet для шифрования/дешифрования.
        """
        # Соль для генерации ключа
        salt = b'dmarket_trading_bot_salt'
        
        # Генерируем ключ из пароля
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(self.password.encode()))
        return Fernet(key)
    
    def load_keys(self) -> Dict[str, Any]:
        """
        Загружает и дешифрует данные ключей из файла.
        
        Returns:
            Словарь с ключами и их значениями.
        
        Raises:
            KeyError: Если файл не существует или возникла ошибка дешифрования.
        """
        try:
            if not self.keys_file.exists():
                return {}
            
            with open(self.keys_file, 'rb') as f:
                encrypted_data = f.read()
                
            if not encrypted_data:
                return {}
                
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке ключей: {e}")
            raise KeyError(f"Не удалось загрузить ключи: {e}")
    
    def save_keys(self, keys_data: Dict[str, Any]) -> None:
        """
        Шифрует и сохраняет данные ключей в файл.
        
        Args:
            keys_data: Словарь с ключами и их значениями.
        
        Raises:
            KeyError: Если возникла ошибка при сохранении.
        """
        try:
            # Шифруем данные
            json_data = json.dumps(keys_data).encode()
            encrypted_data = self.fernet.encrypt(json_data)
            
            # Создаем директорию, если она не существует
            self.keys_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем зашифрованные данные
            with open(self.keys_file, 'wb') as f:
                f.write(encrypted_data)
                
            self.logger.debug(f"Ключи успешно сохранены в {self.keys_file}")
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении ключей: {e}")
            raise KeyError(f"Не удалось сохранить ключи: {e}")
    
    def get_api_key(self, service: str, key_name: str) -> str:
        """
        Получает значение API-ключа.
        
        Args:
            service: Название сервиса (например, 'dmarket', 'steam').
            key_name: Название ключа (например, 'api_key', 'secret_key').
        
        Returns:
            Значение ключа.
        
        Raises:
            KeyError: Если ключ не найден.
        """
        keys_data = self.load_keys()
        
        # Проверяем наличие сервиса
        ensure(service in keys_data, f"Сервис {service} не найден")
        
        # Проверяем наличие ключа
        ensure(key_name in keys_data[service], f"Ключ {key_name} не найден для сервиса {service}")
        
        return keys_data[service][key_name]
    
    def set_api_key(self, service: str, key_name: str, key_value: str) -> None:
        """
        Устанавливает значение API-ключа.
        
        Args:
            service: Название сервиса (например, 'dmarket', 'steam').
            key_name: Название ключа (например, 'api_key', 'secret_key').
            key_value: Значение ключа.
        """
        keys_data = self.load_keys()
        
        # Создаем словарь для сервиса, если его нет
        if service not in keys_data:
            keys_data[service] = {}
        
        # Устанавливаем значение ключа
        keys_data[service][key_name] = key_value
        
        # Сохраняем обновленные данные
        self.save_keys(keys_data)
        self.logger.info(f"Ключ {key_name} для сервиса {service} успешно установлен")
    
    def delete_api_key(self, service: str, key_name: str) -> bool:
        """
        Удаляет API-ключ.
        
        Args:
            service: Название сервиса.
            key_name: Название ключа.
        
        Returns:
            True, если ключ успешно удален, иначе False.
        """
        keys_data = self.load_keys()
        
        # Проверяем наличие сервиса и ключа
        if service not in keys_data or key_name not in keys_data[service]:
            return False
        
        # Удаляем ключ
        del keys_data[service][key_name]
        
        # Если нет больше ключей для сервиса, удаляем и сервис
        if not keys_data[service]:
            del keys_data[service]
        
        # Сохраняем обновленные данные
        self.save_keys(keys_data)
        self.logger.info(f"Ключ {key_name} для сервиса {service} успешно удален")
        
        return True
    
    def get_all_keys(self, service: Optional[str] = None) -> Dict[str, Any]:
        """
        Получает все ключи или ключи для указанного сервиса.
        
        Args:
            service: Название сервиса. Если не указано, возвращаются все ключи.
        
        Returns:
            Словарь с ключами.
        """
        keys_data = self.load_keys()
        
        if service:
            return keys_data.get(service, {})
        
        return keys_data
    
    def has_service(self, service: str) -> bool:
        """
        Проверяет наличие сервиса в данных ключей.
        
        Args:
            service: Название сервиса.
        
        Returns:
            True, если сервис существует, иначе False.
        """
        keys_data = self.load_keys()
        return service in keys_data
    
    def has_key(self, service: str, key_name: str) -> bool:
        """
        Проверяет наличие ключа для указанного сервиса.
        
        Args:
            service: Название сервиса.
            key_name: Название ключа.
        
        Returns:
            True, если ключ существует, иначе False.
        """
        keys_data = self.load_keys()
        return service in keys_data and key_name in keys_data[service]


def get_default_key_manager() -> ApiKeyManager:
    """
    Создает и возвращает экземпляр ApiKeyManager с настройками по умолчанию.
    
    Returns:
        Экземпляр ApiKeyManager.
    """
    # Определяем директорию для ключей
    app_dir = Path.home() / '.dmarket_trading_bot'
    keys_file = app_dir / 'keys.enc'
    
    # Получаем пароль из переменной окружения
    password = os.environ.get("DMARKET_CRYPTO_KEY")
    
    # Если пароль не указан, используем значение по умолчанию (только для разработки)
    if not password:
        logging.warning(
            "DMARKET_CRYPTO_KEY не установлен. "
            "Используется значение по умолчанию (небезопасно для продакшена)."
        )
        password = "development_only_insecure_key"
    
    return ApiKeyManager(keys_file, password=password)


def set_api_keys_from_env() -> None:
    """
    Устанавливает API-ключи из переменных окружения.
    
    Эта функция читает ключи из переменных окружения и сохраняет их
    в зашифрованном файле. Поддерживаемые переменные окружения:
    - DMARKET_API_KEY - API-ключ DMarket
    - DMARKET_API_SECRET - секретный ключ DMarket
    - STEAM_API_KEY - API-ключ Steam
    """
    key_manager = get_default_key_manager()
    
    # Устанавливаем ключи DMarket
    dmarket_api_key = os.environ.get("DMARKET_API_KEY")
    dmarket_api_secret = os.environ.get("DMARKET_API_SECRET")
    
    if dmarket_api_key:
        key_manager.set_api_key("dmarket", "api_key", dmarket_api_key)
    
    if dmarket_api_secret:
        key_manager.set_api_key("dmarket", "api_secret", dmarket_api_secret)
    
    # Устанавливаем ключ Steam
    steam_api_key = os.environ.get("STEAM_API_KEY")
    
    if steam_api_key:
        key_manager.set_api_key("steam", "api_key", steam_api_key)


if __name__ == "__main__":
    # Пример использования
    logging.basicConfig(level=logging.INFO)
    
    # Создаем экземпляр ApiKeyManager
    key_manager = get_default_key_manager()
    
    # Устанавливаем ключи из переменных окружения
    set_api_keys_from_env()
    
    # Выводим список сервисов и ключей
    keys_data = key_manager.get_all_keys()
    for service, keys in keys_data.items():
        print(f"Сервис: {service}")
        for key_name in keys:
            print(f"  - {key_name}: {'*' * 10}") 