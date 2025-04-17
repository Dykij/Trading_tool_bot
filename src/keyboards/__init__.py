"""
Пакет с модулями клавиатур для бота DMarket Trading Bot.
"""

from typing import List, Dict, Any, Optional, Union

try:
    from .keyboards import (
        get_main_keyboard,
        get_menu_kb,
        get_cancel_kb,
        get_my_items_kb,
        get_item_kb,
        get_confirmation_kb
    )
except ImportError:
    # В случае ошибки импорта из .keyboards предоставляем заглушки
    def get_main_keyboard() -> Any:
        """Заглушка для основной клавиатуры."""
        return None

    def get_menu_kb() -> Any:
        """Заглушка для клавиатуры меню."""
        return None

    def get_cancel_kb() -> Any:
        """Заглушка для клавиатуры отмены."""
        return None

    def get_my_items_kb(*args: Any, **kwargs: Any) -> Any:
        """Заглушка для клавиатуры предметов."""
        return None

    def get_item_kb(*args: Any, **kwargs: Any) -> Any:
        """Заглушка для клавиатуры предмета."""
        return None

    def get_confirmation_kb(*args: Any, **kwargs: Any) -> Any:
        """Заглушка для клавиатуры подтверждения."""
        return None

__all__ = [
    'get_main_keyboard',
    'get_menu_kb',
    'get_cancel_kb',
    'get_my_items_kb',
    'get_item_kb',
    'get_confirmation_kb'
] 