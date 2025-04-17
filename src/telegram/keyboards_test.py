"""
Модуль для тестирования клавиатур Telegram бота.

Этот скрипт позволяет протестировать клавиатуры без запуска бота.
"""

import sys
import logging
import json
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('keyboards_test')

def print_keyboard_info(keyboard, keyboard_name):
    """
    Выводит информацию о клавиатуре в консоль.
    
    Args:
        keyboard: Объект клавиатуры
        keyboard_name: Название клавиатуры
    """
    print(f"\n=== {keyboard_name} ===")
    
    # Для aiogram v2
    if hasattr(keyboard, 'to_python'):
        # Получаем JSON представление клавиатуры 
        keyboard_dict = keyboard.to_python()
    else:
        # Резервный вариант, если метод to_python не доступен
        keyboard_json = str(keyboard)
        print(f"Клавиатура (текстовое представление): {keyboard_json}")
        print(f"Тип клавиатуры: {type(keyboard)}")
        print("=" * (len(keyboard_name) + 8))
        print()
        return
    
    # Проверяем тип клавиатуры
    if "inline_keyboard" in keyboard_dict:
        print("Тип: Inline Keyboard")
        rows = keyboard_dict["inline_keyboard"]
        
        for i, row in enumerate(rows):
            print(f"Ряд {i+1}:")
            for button in row:
                text = button.get("text", "Без текста")
                if "callback_data" in button:
                    print(f"  - Кнопка: '{text}', callback_data: '{button['callback_data']}'")
                elif "url" in button:
                    print(f"  - Кнопка: '{text}', url: '{button['url']}'")
                elif "web_app" in button:
                    print(f"  - Кнопка: '{text}', web_app: '{button['web_app']['url']}'")
                else:
                    print(f"  - Кнопка: '{text}', тип: неизвестный")
                    
    elif "keyboard" in keyboard_dict:
        print("Тип: Reply Keyboard")
        rows = keyboard_dict["keyboard"]
        
        for i, row in enumerate(rows):
            print(f"Ряд {i+1}:")
            for button in row:
                text = button.get("text", "Без текста")
                print(f"  - Кнопка: '{text}'")
    else:
        print(f"Неизвестный тип клавиатуры, структура: {keyboard_dict}")
    
    print("=" * (len(keyboard_name) + 8))
    print()

def test_keyboards():
    """
    Тестирует все доступные клавиатуры.
    """
    logger.info("Начинаю тестирование клавиатур...")
    
    try:
        # Импортируем клавиатуры из src/telegram
        from src.telegram.keyboards import (
            get_main_keyboard,
            get_menu_kb,
            get_cancel_kb,
            get_confirmation_kb,
            get_game_selection_keyboard,
            get_item_actions_keyboard,
            get_settings_keyboard
        )
        
        # Пробуем импортировать клавиатуры из keyboards
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from keyboards.keyboards import (
                get_analysis_keyboard,
                get_trading_keyboard,
                get_price_range_keyboard
            )
            
            logger.info("Импортированы клавиатуры из директории keyboards")
            
            # Тестируем клавиатуры из keyboards
            print_keyboard_info(get_analysis_keyboard(), "Анализ")
            print_keyboard_info(get_trading_keyboard(), "Торговля")
            print_keyboard_info(get_price_range_keyboard(), "Диапазон цен")
        except ImportError as e:
            logger.warning(f"Не удалось импортировать клавиатуры из keyboards: {e}")
        
        # Тестируем клавиатуры из src/telegram
        logger.info("Тестирую клавиатуры из src/telegram")
        print_keyboard_info(get_main_keyboard(), "Основная клавиатура")
        print_keyboard_info(get_menu_kb(), "Меню")
        print_keyboard_info(get_cancel_kb(), "Кнопка отмены")
        print_keyboard_info(get_confirmation_kb("test"), "Подтверждение")
        print_keyboard_info(get_game_selection_keyboard(), "Выбор игры")
        print_keyboard_info(get_item_actions_keyboard("test_item_id"), "Действия с предметом")
        print_keyboard_info(get_settings_keyboard(), "Настройки")
        
        logger.info("Тестирование клавиатур завершено успешно")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при тестировании клавиатур: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(test_keyboards()) 