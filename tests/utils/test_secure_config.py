"""
Тестирование модуля безопасного хранения конфигурации.

Проверяет основные функции модуля secure_config:
- Шифрование и дешифрование данных
- Хранение и загрузка API-ключей
- Работу с различными паролями и директориями
"""

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Generator, Tuple

import pytest

from src.utils.error_handling import ConfigError
from src.utils.secure_config import (
    SecureConfig, add_api_key, get_config_instance, get_dmarket_keys,
    get_steam_key, has_api_keys, load_api_keys, save_api_keys
)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Создает временную директорию для тестирования."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def test_password() -> str:
    """Возвращает тестовый пароль."""
    return "test_password_123"


@pytest.fixture
def test_api_keys() -> Dict[str, Dict[str, str]]:
    """Возвращает тестовые API-ключи."""
    return {
        "dmarket": {
            "public_key": "test_public_key",
            "secret_key": "test_secret_key"
        },
        "steam": {
            "api_key": "test_steam_api_key"
        }
    }


@pytest.fixture
def config_instance(temp_dir: Path, test_password: str) -> SecureConfig:
    """Создает экземпляр SecureConfig с тестовым паролем."""
    return SecureConfig(
        config_dir=str(temp_dir),
        password=test_password,
        auto_create=True
    )


def test_encryption_decryption(config_instance: SecureConfig) -> None:
    """Тестирует шифрование и дешифрование данных."""
    test_data = "Тестовые данные для шифрования 123"
    
    # Шифруем данные
    encrypted = config_instance.encrypt(test_data)
    assert encrypted != test_data.encode()
    
    # Дешифруем данные
    decrypted = config_instance.decrypt(encrypted)
    assert decrypted == test_data


def test_save_load_api_keys(
    config_instance: SecureConfig, 
    test_api_keys: Dict[str, Dict[str, str]]
) -> None:
    """Тестирует сохранение и загрузку API-ключей."""
    # Сохраняем ключи
    config_instance.save_api_keys(test_api_keys)
    
    # Загружаем ключи
    loaded_keys = config_instance.load_api_keys()
    
    # Проверяем, что загруженные ключи соответствуют сохраненным
    assert loaded_keys == test_api_keys
    assert loaded_keys["dmarket"]["public_key"] == test_api_keys["dmarket"]["public_key"]
    assert loaded_keys["dmarket"]["secret_key"] == test_api_keys["dmarket"]["secret_key"]
    assert loaded_keys["steam"]["api_key"] == test_api_keys["steam"]["api_key"]


def test_wrong_password(
    config_instance: SecureConfig, 
    test_api_keys: Dict[str, Dict[str, str]]
) -> None:
    """Тестирует обработку неверного пароля."""
    # Сохраняем ключи с одним паролем
    config_instance.save_api_keys(test_api_keys)
    
    # Пытаемся загрузить с другим паролем
    wrong_password = "wrong_password"
    
    # Должна быть ошибка при загрузке
    with pytest.raises(ConfigError) as excinfo:
        config_instance.load_api_keys(wrong_password)
    
    # Проверяем сообщение об ошибке
    assert "Не удалось расшифровать данные" in str(excinfo.value)


def test_add_api_key_method(
    config_instance: SecureConfig
) -> None:
    """Тестирует добавление ключа методом класса."""
    # Добавляем ключ
    config_instance.add_api_key("test_service", "test_key_type", "test_key_value")
    
    # Загружаем ключи и проверяем
    loaded_keys = config_instance.load_api_keys()
    assert "test_service" in loaded_keys
    assert "test_key_type" in loaded_keys["test_service"]
    assert loaded_keys["test_service"]["test_key_type"] == "test_key_value"


def test_remove_api_key(
    config_instance: SecureConfig,
    test_api_keys: Dict[str, Dict[str, str]]
) -> None:
    """Тестирует удаление API-ключа."""
    # Сохраняем ключи
    config_instance.save_api_keys(test_api_keys)
    
    # Удаляем ключ
    result = config_instance.remove_api_key("dmarket", "public_key")
    assert result is True
    
    # Загружаем ключи и проверяем, что ключ удален
    loaded_keys = config_instance.load_api_keys()
    assert "dmarket" in loaded_keys
    assert "public_key" not in loaded_keys["dmarket"]
    assert "secret_key" in loaded_keys["dmarket"]
    
    # Удаляем весь сервис
    result = config_instance.remove_api_key("steam")
    assert result is True
    
    # Загружаем ключи и проверяем, что сервис удален
    loaded_keys = config_instance.load_api_keys()
    assert "steam" not in loaded_keys


def test_has_api_keys(
    config_instance: SecureConfig,
    test_api_keys: Dict[str, Dict[str, str]]
) -> None:
    """Тестирует проверку наличия файла с API-ключами."""
    # Изначально файла нет
    assert config_instance.has_api_keys() is False
    
    # Сохраняем ключи
    config_instance.save_api_keys(test_api_keys)
    
    # Теперь файл должен быть
    assert config_instance.has_api_keys() is True


def test_helper_functions(
    temp_dir: Path,
    test_password: str,
    test_api_keys: Dict[str, Dict[str, str]]
) -> None:
    """Тестирует вспомогательные функции для работы с API-ключами."""
    # Получаем экземпляр конфигурации
    config = get_config_instance(str(temp_dir), test_password)
    assert isinstance(config, SecureConfig)
    
    # Проверяем функцию has_api_keys
    assert has_api_keys(str(temp_dir)) is False
    
    # Сохраняем API-ключи
    save_api_keys(test_api_keys, test_password, str(temp_dir))
    
    # Проверяем, что ключи сохранены
    assert has_api_keys(str(temp_dir)) is True
    
    # Загружаем API-ключи
    loaded_keys = load_api_keys(test_password, str(temp_dir))
    assert loaded_keys == test_api_keys
    
    # Добавляем новый ключ
    add_api_key("new_service", "new_key", "new_value", test_password, str(temp_dir))
    
    # Загружаем ключи и проверяем, что новый ключ добавлен
    loaded_keys = load_api_keys(test_password, str(temp_dir))
    assert "new_service" in loaded_keys
    assert loaded_keys["new_service"]["new_key"] == "new_value"
    
    # Получаем ключи DMarket
    public_key, secret_key = get_dmarket_keys(test_password, str(temp_dir))
    assert public_key == test_api_keys["dmarket"]["public_key"]
    assert secret_key == test_api_keys["dmarket"]["secret_key"]
    
    # Получаем ключ Steam
    steam_key = get_steam_key(test_password, str(temp_dir))
    assert steam_key == test_api_keys["steam"]["api_key"]


def test_different_config_dirs(
    temp_dir: Path,
    test_password: str,
    test_api_keys: Dict[str, Dict[str, str]]
) -> None:
    """Тестирует работу с разными директориями конфигурации."""
    # Создаем две разные директории
    dir1 = temp_dir / "config1"
    dir2 = temp_dir / "config2"
    
    # Сохраняем разные ключи в разные директории
    keys1 = test_api_keys.copy()
    keys2 = {
        "other_service": {
            "key1": "value1",
            "key2": "value2"
        }
    }
    
    save_api_keys(keys1, test_password, str(dir1))
    save_api_keys(keys2, test_password, str(dir2))
    
    # Загружаем ключи из разных директорий
    loaded_keys1 = load_api_keys(test_password, str(dir1))
    loaded_keys2 = load_api_keys(test_password, str(dir2))
    
    # Проверяем, что ключи не перемешались
    assert loaded_keys1 == keys1
    assert loaded_keys2 == keys2
    assert loaded_keys1 != loaded_keys2


def test_error_handling(
    temp_dir: Path,
    test_password: str
) -> None:
    """Тестирует обработку ошибок."""
    nonexistent_dir = str(temp_dir / "nonexistent")
    
    # Загрузка из несуществующего файла
    with pytest.raises(ConfigError) as excinfo:
        load_api_keys(test_password, nonexistent_dir)
    assert "не найден" in str(excinfo.value)
    
    # Получение ключей DMarket из пустой конфигурации
    save_api_keys({}, test_password, str(temp_dir))
    with pytest.raises(ConfigError) as excinfo:
        get_dmarket_keys(test_password, str(temp_dir))
    assert "не найдены" in str(excinfo.value)
    
    # Получение ключа Steam из пустой конфигурации
    with pytest.raises(ConfigError) as excinfo:
        get_steam_key(test_password, str(temp_dir))
    assert "не найден" in str(excinfo.value)


def test_file_corruption_handling(
    temp_dir: Path,
    test_password: str,
    test_api_keys: Dict[str, Dict[str, str]]
) -> None:
    """Тестирует обработку поврежденных файлов."""
    # Создаем экземпляр конфигурации
    config = SecureConfig(str(temp_dir), test_password)
    
    # Сохраняем ключи
    config.save_api_keys(test_api_keys)
    
    # Намеренно повреждаем файл
    with open(config._keys_path, "wb") as f:
        f.write(b"corrupted data")
    
    # Попытка загрузки должна вызвать ошибку
    with pytest.raises(ConfigError):
        config.load_api_keys()


if __name__ == "__main__":
    # Ручное тестирование
    test_dir = tempfile.mkdtemp()
    test_password = "test123"
    
    print(f"Using test directory: {test_dir}")
    
    # Создаем экземпляр конфигурации
    config = SecureConfig(test_dir, test_password)
    
    # Тестовые ключи
    test_keys = {
        "dmarket": {
            "public_key": "test_public_key",
            "secret_key": "test_secret_key"
        },
        "steam": {
            "api_key": "test_steam_api_key"
        }
    }
    
    # Сохраняем ключи
    config.save_api_keys(test_keys)
    print("Keys saved successfully!")
    
    # Загружаем ключи
    loaded_keys = config.load_api_keys()
    print("Keys loaded successfully!")
    
    # Проверяем, что ключи загружены корректно
    assert loaded_keys == test_keys
    print("Keys verified successfully!")
    
    # Очистка
    print(f"Cleaning up test directory: {test_dir}")
    import shutil
    shutil.rmtree(test_dir) 