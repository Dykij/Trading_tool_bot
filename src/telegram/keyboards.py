"""
DEPRECATED: Этот модуль сохранен для обратной совместимости.
Все функции перенесены в модуль custom_keyboards.py.
"""

# Импортируем все необходимые функции из custom_keyboards.py для обратной совместимости
from src.telegram.custom_keyboards import (
    get_main_keyboard,
    get_menu_kb,
    get_game_selection_keyboard,
    get_arbitrage_mode_keyboard,
    get_item_actions_keyboard,
    get_settings_keyboard,
    get_cancel_kb,
    get_budget_input_keyboard,
    get_confirmation_kb
)

# Для логгирования, что файл устарел
import logging
logger = logging.getLogger(__name__)
logger.warning("Модуль keyboards.py устарел и будет удален в будущих версиях. Используйте custom_keyboards.py") 