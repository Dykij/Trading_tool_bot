import sys
from pathlib import Path
import pytest
from typing import Dict, Any


# Добавляем корневую директорию проекта в путь поиска модулей
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """
    Фикстура для тестового конфигурационного объекта.

    Returns:
        Dict[str, Any]: Словарь с тестовыми настройками конфигурации.
    """
    return {
        "api_key": "test_key",
        "api_secret": "test_secret",
        "timeout": 5,
        "max_retries": 1
    }
