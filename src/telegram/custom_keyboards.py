"""
Модуль с клавиатурами для Telegram бота.

Этот модуль содержит функции для создания различных типов клавиатур
для взаимодействия с пользователем через Telegram бота.
"""
from typing import List, Dict, Any, Union, Optional
import pkg_resources
import logging

# Определяем версию aiogram
try:
    aiogram_version = pkg_resources.get_distribution("aiogram").version
    IS_AIOGRAM_V2 = aiogram_version.startswith("2.")
    print(f"Используем aiogram версии: {'v2' if IS_AIOGRAM_V2 else 'v3'}")
except Exception as e:
    print(f"Ошибка при определении версии aiogram: {e}")
    IS_AIOGRAM_V2 = True  # По умолчанию используем v2

# Импортируем необходимые компоненты в зависимости от версии
if IS_AIOGRAM_V2:
    from aiogram.types import (
        ReplyKeyboardMarkup, KeyboardButton, 
        InlineKeyboardMarkup, InlineKeyboardButton
    )
    from aiogram.utils.callback_data import CallbackData
else:
    from aiogram.types import (
        ReplyKeyboardMarkup, KeyboardButton, 
        InlineKeyboardMarkup, InlineKeyboardButton
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder

# Инициализируем логгер
logger = logging.getLogger("keyboards")

# Определяем CallbackData или его аналог в зависимости от версии
if IS_AIOGRAM_V2:
    action_cb = CallbackData("action", "command", "param")
else:
    # В aiogram v3 используем функции для формирования callback_data
    def create_callback_data(command: str, param: str = "") -> str:
        return f"action:{command}:{param}"

# Класс для создания клавиатур с поддержкой разных версий aiogram
class KeyboardFactory:
    @staticmethod
    def create_reply_keyboard(buttons: List[List[str]], resize_keyboard: bool = True) -> ReplyKeyboardMarkup:
        """
        Создает клавиатуру с обычными кнопками.
        
        Args:
            buttons: Список списков с текстами кнопок
            resize_keyboard: Нужно ли изменять размер клавиатуры
            
        Returns:
            Объект клавиатуры
        """
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for button_text in row:
                keyboard_row.append(KeyboardButton(text=button_text))
            keyboard.append(keyboard_row)
        
        return ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=resize_keyboard
        )
    
    @staticmethod
    def create_inline_keyboard_v2(buttons: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
        """
        Создает инлайн-клавиатуру для aiogram v2.
        
        Args:
            buttons: Список списков с параметрами кнопок (text, callback_data, url)
            
        Returns:
            Объект инлайн-клавиатуры
        """
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for button in row:
                # Проверяем наличие необходимых параметров
                text = button.get("text", "")
                command = button.get("command", "")
                param = button.get("param", "")
                url = button.get("url", None)
                callback_data = button.get("callback_data", None)
                
                if url:
                    keyboard_row.append(InlineKeyboardButton(text=text, url=url))
                elif callback_data:
                    # Используем готовый callback_data, если он предоставлен
                    keyboard_row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
                else:
                    # Иначе формируем callback_data через CallbackData
                    callback_data = action_cb.new(command=command, param=param)
                    keyboard_row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
            
            keyboard.append(keyboard_row)
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def create_inline_keyboard_v3(buttons: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
        """
        Создает инлайн-клавиатуру для aiogram v3.
        
        Args:
            buttons: Список списков с параметрами кнопок (text, command, param, url)
            
        Returns:
            Объект инлайн-клавиатуры
        """
        builder = InlineKeyboardBuilder()
        
        for row in buttons:
            row_buttons = []
            for button in row:
                # Проверяем наличие необходимых параметров
                text = button.get("text", "")
                command = button.get("command", "")
                param = button.get("param", "")
                url = button.get("url", None)
                callback_data = button.get("callback_data", None)
                
                if url:
                    row_buttons.append(InlineKeyboardButton(text=text, url=url))
                elif callback_data:
                    # Используем готовый callback_data, если он предоставлен
                    row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))
                else:
                    # Иначе формируем callback_data через функцию
                    callback_data = create_callback_data(command, param)
                    row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))
            
            builder.row(*row_buttons)
        
        return builder.as_markup()
    
    @staticmethod
    def create_inline_keyboard(buttons: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
        """
        Создает инлайн-клавиатуру в зависимости от версии aiogram.
        
        Args:
            buttons: Список списков с параметрами кнопок
            
        Returns:
            Объект инлайн-клавиатуры
        """
        if IS_AIOGRAM_V2:
            return KeyboardFactory.create_inline_keyboard_v2(buttons)
        else:
            return KeyboardFactory.create_inline_keyboard_v3(buttons)

# Основные функции из keyboards.py, адаптированные для custom_keyboards.py

def get_main_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру главного меню.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура главного меню
    """
    buttons = [
        [
            {"text": "📊 Арбитраж", "callback_data": "menu:arbitrage"},
            {"text": "🎮 Мои предметы", "callback_data": "menu:items"}
        ],
        [
            {"text": "📈 Инвестиции", "callback_data": "menu:investments"},
            {"text": "🤖 ML-анализ", "callback_data": "ml:default"}
        ],
        [
            {"text": "⚙️ Настройки", "callback_data": "menu:settings"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_menu_kb() -> InlineKeyboardMarkup:
    """
    Синоним для get_main_keyboard для обратной совместимости.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура главного меню
    """
    return get_main_keyboard()

def get_game_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру выбора игры для арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора игры
    """
    buttons = [
        [
            {"text": "🔫 CS2", "callback_data": "arbitrage:game_a8db"},
            {"text": "🗡️ Dota 2", "callback_data": "arbitrage:game_9a92"}
        ],
        [
            {"text": "🎮 Team Fortress 2", "callback_data": "arbitrage:game_tf2"},
            {"text": "⚔️ Rust", "callback_data": "arbitrage:game_rust"}
        ],
        [
            {"text": "« Назад", "callback_data": "back"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_mode_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру выбора режима арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора режима арбитража
    """
    buttons = [
        [
            {"text": "🔄 Автоматический", "callback_data": "arbitrage:mode_auto"},
            {"text": "👨‍💻 Ручной", "callback_data": "arbitrage:mode_manual"}
        ],
        [
            {"text": "⚡ Быстрый", "callback_data": "arbitrage:mode_quick"},
            {"text": "🧠 Умный", "callback_data": "arbitrage:mode_smart"}
        ],
        [
            {"text": "⚙️ Параметры поиска", "callback_data": "arbitrage:settings"}
        ],
        [
            {"text": "« Назад", "callback_data": "back"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_item_actions_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для работы с предметами.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура действий с предметами
    """
    buttons = [
        [
            {"text": "🧰 Мой инвентарь", "callback_data": "item:inventory"},
            {"text": "🔍 Поиск предметов", "callback_data": "item:search"}
        ],
        [
            {"text": "👁️ Отслеживание цен", "callback_data": "item:track"},
            {"text": "📊 Статистика", "callback_data": "item:stats"}
        ],
        [
            {"text": "« Назад", "callback_data": "back"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру настроек.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура настроек
    """
    buttons = [
        [
            {"text": "🔑 API ключи", "callback_data": "settings:api"},
            {"text": "🔔 Уведомления", "callback_data": "settings:notifications"}
        ],
        [
            {"text": "🧮 Торговля", "callback_data": "settings:trading"},
            {"text": "📝 Профиль", "callback_data": "settings:profile"}
        ],
        [
            {"text": "« Назад", "callback_data": "back"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_cancel_kb() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой отмены.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой отмены
    """
    buttons = [
        [
            {"text": "❌ Отмена", "callback_data": "back"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_budget_input_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для ввода бюджета арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура для ввода бюджета
    """
    buttons = [
        [
            {"text": "$10", "callback_data": "budget:10"},
            {"text": "$50", "callback_data": "budget:50"},
            {"text": "$100", "callback_data": "budget:100"}
        ],
        [
            {"text": "$200", "callback_data": "budget:200"},
            {"text": "$500", "callback_data": "budget:500"},
            {"text": "$1000", "callback_data": "budget:1000"}
        ],
        [
            {"text": "Ввести вручную", "callback_data": "budget:custom"}
        ],
        [
            {"text": "« Назад", "callback_data": "back"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_confirmation_kb(confirm_data: str = "confirm", cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    """
    Создает клавиатуру подтверждения действия.
    
    Args:
        confirm_data: callback_data для кнопки подтверждения
        cancel_data: callback_data для кнопки отмены
    
    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    """
    buttons = [
        [
            {"text": "✅ Подтвердить", "callback_data": confirm_data},
            {"text": "❌ Отмена", "callback_data": cancel_data}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

# Функции для создания стандартных клавиатур
def get_main_keyboard_v2() -> ReplyKeyboardMarkup:
    """
    Создает главную клавиатуру бота (Reply версия).
    
    Returns:
        ReplyKeyboardMarkup: Главная клавиатура бота
    """
    buttons = [
        ["📊 Анализ", "💰 Торговля"],
        ["⚙️ Настройки", "📝 Таргет-ордера"],
        ["🔍 Арбитраж скинов", "📈 Мониторинг цен"]
    ]
    return KeyboardFactory.create_reply_keyboard(buttons)

def get_settings_keyboard_v2() -> ReplyKeyboardMarkup:
    """Создаёт клавиатуру настроек (Reply версия)."""
    buttons = [
        ["🔑 API ключи"],
        ["🔔 Уведомления", "🌍 Языки"],
        ["👤 Профиль", "📌 Лимиты"],
        ["🌐 Маркетплейсы", "⚡ Арбитраж"],
        ["◀️ Назад"]
    ]
    return KeyboardFactory.create_reply_keyboard(buttons)

def get_analysis_menu_keyboard() -> ReplyKeyboardMarkup:
    """Создаёт клавиатуру анализа рынка."""
    buttons = [
        ["📊 Популярные предметы"],
        ["🔍 Поиск предмета", "🎯 Арбитраж"],
        ["📉 Тренды цен", "⏱️ История"],
        ["🔄 Кросс-платформа", "💡 Рекомендации"],
        ["◀️ Назад"]
    ]
    return KeyboardFactory.create_reply_keyboard(buttons)

def get_trading_menu_keyboard() -> ReplyKeyboardMarkup:
    """Создаёт клавиатуру торговли."""
    buttons = [
        ["🛒 Купить", "💵 Продать"],
        ["📋 Активные заказы", "📜 История сделок"],
        ["🔖 Целевые ордера", "📊 Мониторинг"],
        ["🔄 Обмен", "💎 Избранное"],
        ["◀️ Назад"]
    ]
    return KeyboardFactory.create_reply_keyboard(buttons)

def get_target_orders_keyboard() -> ReplyKeyboardMarkup:
    """Создаёт клавиатуру для целевых ордеров."""
    buttons = [
        ["🔖 Создать ордер", "📋 Мои ордера"],
        ["🔍 Найти ордер", "❌ Отменить ордер"],
        ["📊 Мониторинг", "⚙️ Настройки ордеров"],
        ["◀️ Назад"]
    ]
    return KeyboardFactory.create_reply_keyboard(buttons)

# Функции для создания инлайн-клавиатур
def get_item_actions_keyboard_v2(item_id: str) -> InlineKeyboardMarkup:
    """
    Создаёт инлайн-клавиатуру с действиями для предмета.
    
    Args:
        item_id: Идентификатор предмета
        
    Returns:
        Инлайн-клавиатура с действиями
    """
    buttons = [
        [
            {"text": "🛒 Купить", "command": "buy", "param": item_id},
            {"text": "💰 Продать", "command": "sell", "param": item_id}
        ],
        [
            {"text": "📊 Анализ цены", "command": "price_analysis", "param": item_id}
        ],
        [
            {"text": "📈 История", "command": "history", "param": item_id},
            {"text": "⭐ В избранное", "command": "favorite", "param": item_id}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_confirmation_keyboard(action: str, item_id: str) -> InlineKeyboardMarkup:
    """
    Создаёт инлайн-клавиатуру для подтверждения действия.
    
    Args:
        action: Действие для подтверждения
        item_id: Идентификатор предмета
        
    Returns:
        Инлайн-клавиатура для подтверждения
    """
    buttons = [
        [
            {"text": "✅ Да", "command": f"confirm_{action}", "param": item_id},
            {"text": "❌ Нет", "command": "cancel", "param": ""}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_pagination_keyboard(page: int, total_pages: int, command: str) -> InlineKeyboardMarkup:
    """
    Создаёт инлайн-клавиатуру для пагинации.
    
    Args:
        page: Текущая страница
        total_pages: Общее количество страниц
        command: Команда для обработки нажатия
        
    Returns:
        Инлайн-клавиатура для пагинации
    """
    buttons = [[]]
    
    # Добавляем кнопку "Назад", если это не первая страница
    if page > 1:
        buttons[0].append({"text": "◀️", "command": command, "param": str(page - 1)})
    
    # Добавляем информацию о текущей странице
    buttons[0].append({"text": f"{page}/{total_pages}", "command": "noop", "param": ""})
    
    # Добавляем кнопку "Вперед", если это не последняя страница
    if page < total_pages:
        buttons[0].append({"text": "▶️", "command": command, "param": str(page + 1)})
    
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_item_type_keyboard(game_id: str = "cs2"):
    """
    Создает клавиатуру для выбора типа предмета.
    
    Args:
        game_id: Идентификатор игры (cs2, dota2, tf2)
        
    Returns:
        InlineKeyboardMarkup: Клавиатура для выбора типа предмета
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    if game_id == "cs2":
        keyboard.add(
            InlineKeyboardButton("🔪 Ножи", callback_data="item_type:knife"),
            InlineKeyboardButton("🧤 Перчатки", callback_data="item_type:gloves"),
            InlineKeyboardButton("🔫 Винтовки", callback_data="item_type:rifle"),
            InlineKeyboardButton("🔫 Пистолеты", callback_data="item_type:pistol"),
            InlineKeyboardButton("🏷️ Стикеры", callback_data="item_type:sticker"),
            InlineKeyboardButton("📦 Контейнеры", callback_data="item_type:container"),
            InlineKeyboardButton("🔍 Другое", callback_data="item_type:other"),
            InlineKeyboardButton("🌟 Все типы", callback_data="item_type:all")
        )
    elif game_id == "dota2":
        keyboard.add(
            InlineKeyboardButton("👑 Аркана", callback_data="item_type:arcana"),
            InlineKeyboardButton("🗡️ Бессмертные", callback_data="item_type:immortal"),
            InlineKeyboardButton("🧙 Курьеры", callback_data="item_type:courier"),
            InlineKeyboardButton("🎭 Сеты", callback_data="item_type:set"),
            InlineKeyboardButton("🔍 Другое", callback_data="item_type:other"),
            InlineKeyboardButton("🌟 Все типы", callback_data="item_type:all")
        )
    elif game_id == "tf2":
        keyboard.add(
            InlineKeyboardButton("🎩 Шляпы", callback_data="item_type:hat"),
            InlineKeyboardButton("🔫 Оружие", callback_data="item_type:weapon"),
            InlineKeyboardButton("🎭 Необычные", callback_data="item_type:unusual"),
            InlineKeyboardButton("🔍 Другое", callback_data="item_type:other"),
            InlineKeyboardButton("🌟 Все типы", callback_data="item_type:all")
        )
    
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data=f"back:game_selection"))
    
    return keyboard

def get_analysis_inline_keyboard():
    """
    Создает клавиатуру для меню анализа.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура для меню анализа
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton("🔍 Найти арбитраж", callback_data="analysis:find_arbitrage"),
        InlineKeyboardButton("📊 Анализ рынка", callback_data="analysis:market_analysis"),
        InlineKeyboardButton("🎮 Выбрать игру", callback_data="analysis:select_game"),
        InlineKeyboardButton("⚙️ Параметры анализа", callback_data="analysis:settings"),
        InlineKeyboardButton("📦 Выбрать тип предмета", callback_data="analysis:select_item_type"),
        InlineKeyboardButton("💰 Настроить бюджет", callback_data="analysis:set_budget"),
        InlineKeyboardButton("📈 История цен", callback_data="analysis:price_history"),
        InlineKeyboardButton("◀️ Назад", callback_data="back:main")
    )
    
    return keyboard

def get_trading_inline_keyboard():
    """
    Создает клавиатуру для меню торговли.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура для меню торговли
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton("🔍 Найти предмет", callback_data="trading:search_item"),
        InlineKeyboardButton("💰 Купить предмет", callback_data="trading:buy_item"),
        InlineKeyboardButton("📦 Инвентарь", callback_data="trading:inventory"),
        InlineKeyboardButton("🏷️ Выставить на продажу", callback_data="trading:sell_item"),
        InlineKeyboardButton("❌ Снять с продажи", callback_data="trading:cancel_sale"),
        InlineKeyboardButton("💱 Арбитраж в DMarket", callback_data="trading:dmarket_arbitrage"),
        InlineKeyboardButton("🎮 Выбрать игру", callback_data="trading:select_game"),
        InlineKeyboardButton("◀️ Назад", callback_data="back:main")
    )
    
    return keyboard

def get_dmarket_arbitrage_keyboard():
    """
    Создает клавиатуру для меню арбитража в DMarket.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура для меню арбитража в DMarket
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton("🔍 Найти арбитраж в CS2", callback_data="dmarket_arbitrage:cs2"),
        InlineKeyboardButton("🔍 Найти арбитраж в Dota 2", callback_data="dmarket_arbitrage:dota2"),
        InlineKeyboardButton("🔍 Найти арбитраж в TF2", callback_data="dmarket_arbitrage:tf2"),
        InlineKeyboardButton("⚙️ Настройки арбитража", callback_data="dmarket_arbitrage:settings"),
        InlineKeyboardButton("💰 Настроить бюджет", callback_data="dmarket_arbitrage:budget"),
        InlineKeyboardButton("📊 Отчет по арбитражу", callback_data="dmarket_arbitrage:report"),
        InlineKeyboardButton("◀️ Назад", callback_data="back:trading")
    )
    
    return keyboard

def get_arbitrage_params_keyboard():
    """
    Создает клавиатуру для настройки параметров арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура для настройки параметров арбитража
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton("💵 Мин. прибыль: 1%", callback_data="arbitrage_settings:profit:1"),
        InlineKeyboardButton("💵 Мин. прибыль: 3%", callback_data="arbitrage_settings:profit:3"),
        InlineKeyboardButton("💵 Мин. прибыль: 5%", callback_data="arbitrage_settings:profit:5"),
        InlineKeyboardButton("💵 Мин. прибыль: 10%", callback_data="arbitrage_settings:profit:10"),
        InlineKeyboardButton("💰 Мин. цена: $1", callback_data="arbitrage_settings:min_price:1"),
        InlineKeyboardButton("💰 Мин. цена: $5", callback_data="arbitrage_settings:min_price:5"),
        InlineKeyboardButton("💰 Макс. цена: $100", callback_data="arbitrage_settings:max_price:100"),
        InlineKeyboardButton("💰 Макс. цена: $500", callback_data="arbitrage_settings:max_price:500"),
        InlineKeyboardButton("🔢 Лимит: 50", callback_data="arbitrage_settings:limit:50"),
        InlineKeyboardButton("🔢 Лимит: 100", callback_data="arbitrage_settings:limit:100"),
        InlineKeyboardButton("🔢 Лимит: 200", callback_data="arbitrage_settings:limit:200"),
        InlineKeyboardButton("◀️ Назад", callback_data="back:dmarket_arbitrage")
    )
    
    return keyboard

def get_rarity_keyboard(game_id: str = "cs2"):
    """
    Создает клавиатуру для выбора редкости предмета.
    
    Args:
        game_id: Идентификатор игры (cs2, dota2, tf2)
        
    Returns:
        InlineKeyboardMarkup: Клавиатура для выбора редкости предмета
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    if game_id == "cs2":
        keyboard.add(
            InlineKeyboardButton("🟥 Тайное", callback_data="rarity:covert"),
            InlineKeyboardButton("🟪 Засекреченное", callback_data="rarity:classified"),
            InlineKeyboardButton("🟦 Запрещенное", callback_data="rarity:restricted"),
            InlineKeyboardButton("🟩 Промышленное", callback_data="rarity:industrial"),
            InlineKeyboardButton("🟨 Ширпотреб", callback_data="rarity:consumer"),
            InlineKeyboardButton("🌟 Все редкости", callback_data="rarity:all")
        )
    elif game_id == "dota2":
        keyboard.add(
            InlineKeyboardButton("🔴 Аркана", callback_data="rarity:arcana"),
            InlineKeyboardButton("🟠 Древнее", callback_data="rarity:ancient"),
            InlineKeyboardButton("🟡 Легендарное", callback_data="rarity:legendary"),
            InlineKeyboardButton("🟢 Мифическое", callback_data="rarity:mythical"),
            InlineKeyboardButton("🔵 Редкое", callback_data="rarity:rare"),
            InlineKeyboardButton("🟣 Необычное", callback_data="rarity:uncommon"),
            InlineKeyboardButton("⚪ Обычное", callback_data="rarity:common"),
            InlineKeyboardButton("🌟 Все редкости", callback_data="rarity:all")
        )
    elif game_id == "tf2":
        keyboard.add(
            InlineKeyboardButton("🟣 Необычное", callback_data="rarity:unusual"),
            InlineKeyboardButton("🟡 Аутентичное", callback_data="rarity:genuine"),
            InlineKeyboardButton("🟠 Странное", callback_data="rarity:strange"),
            InlineKeyboardButton("🔵 Уникальное", callback_data="rarity:unique"),
            InlineKeyboardButton("🌟 Все редкости", callback_data="rarity:all")
        )
    
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="back:item_type"))
    
    return keyboard

# Специализированные клавиатуры
def get_price_range_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру выбора диапазона цен.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура диапазона цен
    """
    buttons = [
        [
            {"text": "$0-10", "command": "price", "param": "0_10"},
            {"text": "$10-50", "command": "price", "param": "10_50"}
        ],
        [
            {"text": "$50-100", "command": "price", "param": "50_100"},
            {"text": "$100-500", "command": "price", "param": "100_500"}
        ],
        [
            {"text": "$500+", "command": "price", "param": "500_0"},
            {"text": "Любая", "command": "price", "param": "any"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_time_period_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру выбора временного периода.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура временного периода
    """
    buttons = [
        [
            {"text": "24 часа", "command": "period", "param": "24h"},
            {"text": "7 дней", "command": "period", "param": "7d"},
            {"text": "30 дней", "command": "period", "param": "30d"}
        ],
        [
            {"text": "3 месяца", "command": "period", "param": "3m"},
            {"text": "Год", "command": "period", "param": "1y"},
            {"text": "Все время", "command": "period", "param": "all"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_target_order_actions_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру действий с целевым ордером.
    
    Args:
        order_id: Идентификатор ордера
        
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура действий с ордером
    """
    buttons = [
        [
            {"text": "✅ Выполнить", "command": "execute_order", "param": order_id},
            {"text": "❌ Отменить", "command": "cancel_order", "param": order_id}
        ],
        [
            {"text": "📊 Статистика", "command": "stats_order", "param": order_id},
            {"text": "⏱️ История", "command": "history_order", "param": order_id}
        ],
        [
            {"text": "📋 Подробности", "command": "details_order", "param": order_id}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_target_order_create_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для создания целевого ордера.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура создания ордера
    """
    buttons = [
        [
            {"text": "💰 По цене", "command": "create_order", "param": "price"},
            {"text": "📊 По тренду", "command": "create_order", "param": "trend"}
        ],
        [
            {"text": "🔄 Из арбитража", "command": "create_order", "param": "arbitrage"},
            {"text": "⚡ Быстрый ордер", "command": "create_order", "param": "quick"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_target_order_monitor_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для мониторинга целевых ордеров.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура мониторинга
    """
    buttons = [
        [
            {"text": "▶️ Запустить", "command": "monitor", "param": "start"},
            {"text": "⏹️ Остановить", "command": "monitor", "param": "stop"}
        ],
        [
            {"text": "⚙️ Настройки", "command": "monitor", "param": "settings"},
            {"text": "📊 Статистика", "command": "monitor", "param": "stats"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

# Клавиатуры для работы с кросс-платформенным арбитражем
def get_marketplace_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру выбора торговой площадки.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура выбора площадки
    """
    buttons = [
        [
            {"text": "🟪 DMarket", "command": "market", "param": "dmarket"},
            {"text": "🟥 Bitskins", "command": "market", "param": "bitskins"}
        ],
        [
            {"text": "🟦 Backpack.tf", "command": "market", "param": "backpack"},
            {"text": "🟩 Total CS", "command": "market", "param": "totalcs"}
        ],
        [
            {"text": "🟨 CS.Money", "command": "market", "param": "csmoney"},
            {"text": "🟧 Все площадки", "command": "market", "param": "all"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_auto_trade_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для автоматического трейдинга.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура автотрейдинга
    """
    buttons = [
        [
            {"text": "▶️ Запустить", "command": "autotrade", "param": "start"},
            {"text": "⏹️ Остановить", "command": "autotrade", "param": "stop"}
        ],
        [
            {"text": "📊 Статистика", "command": "autotrade", "param": "stats"},
            {"text": "⚙️ Настройки", "command": "autotrade", "param": "settings"}
        ],
        [
            {"text": "📈 История", "command": "autotrade", "param": "history"},
            {"text": "📋 Отчет", "command": "autotrade", "param": "report"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

# Справочная информация о доступных API
API_DOCS = {
    "bitskins": "https://bitskins.com/ru/docs/api",
    "totalcs": "https://totalcsgo.com/launch-options",
    "backpack": "https://backpack.tf/api/index.html", 
    "dmarket": "https://docs.dmarket.com/v1/swagger.html",
    "telegram": "https://core.telegram.org/bots/api"
}

def get_arbitrage_main_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для главного меню арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура для главного меню арбитража
    """
    buttons = [
        [
            {"text": "🎮 Выбрать игру (Режим 1)", "command": "arbitrage", "param": "mode1_game"}
        ],
        [
            {"text": "🌐 Все игры (Режим 2)", "command": "arbitrage", "param": "mode2_all"}
        ],
        [
            {"text": "💰 Установить бюджет", "command": "arbitrage", "param": "set_budget"}
        ],
        [
            {"text": "⚙️ Настройки арбитража", "command": "arbitrage", "param": "settings"}
        ],
        [
            {"text": "📊 Статистика арбитража", "command": "arbitrage", "param": "stats"}
        ],
        [
            {"text": "◀️ Назад", "command": "back", "param": "main"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_game_selection_for_arbitrage() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру выбора игры для арбитража (Режим 1).
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора игры для арбитража
    """
    buttons = [
        [
            {"text": "🎮 CS2", "command": "arbitrage_game", "param": "a8db"}
        ],
        [
            {"text": "🏆 Dota 2", "command": "arbitrage_game", "param": "9a92"}
        ],
        [
            {"text": "🎯 TF2", "command": "arbitrage_game", "param": "tf2"}
        ],
        [
            {"text": "◀️ Назад", "command": "back", "param": "arbitrage_main"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_profit_range_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру выбора диапазона прибыли для арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора диапазона прибыли
    """
    buttons = [
        [
            {"text": "$1-$5", "command": "profit_range", "param": "low"}
        ],
        [
            {"text": "$5-$10", "command": "profit_range", "param": "medium"}
        ],
        [
            {"text": "$10-$20", "command": "profit_range", "param": "high"}
        ],
        [
            {"text": "$20-$50", "command": "profit_range", "param": "very_high"}
        ],
        [
            {"text": "$50-$100", "command": "profit_range", "param": "extreme"}
        ],
        [
            {"text": "🔙 Назад", "command": "back", "param": "arbitrage_menu"}
        ]
    ]
    
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_game_selection_for_arbitrage_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру выбора игры для арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора игры
    """
    buttons = [
        [
            {"text": "🎮 CS2", "command": "arbitrage_game", "param": "cs2"}
        ],
        [
            {"text": "🧙‍♂️ Dota 2", "command": "arbitrage_game", "param": "dota2"}
        ],
        [
            {"text": "🎭 TF2", "command": "arbitrage_game", "param": "tf2"}
        ],
        [
            {"text": "🔄 Все игры", "command": "arbitrage_game", "param": "all"}
        ],
        [
            {"text": "🔙 Назад", "command": "back", "param": "arbitrage_menu"}
        ]
    ]
    
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_mode_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру выбора режима арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора режима арбитража
    """
    buttons = [
        [
            {"text": "🎯 Одна игра", "command": "arbitrage_mode", "param": "single_game"}
        ],
        [
            {"text": "🔍 Все игры", "command": "arbitrage_mode", "param": "all_games"}
        ],
        [
            {"text": "🔙 Назад", "command": "back", "param": "main_menu"}
        ]
    ]
    
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_control_keyboard(is_running: bool = False) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру управления процессом арбитражной торговли.
    
    Args:
        is_running: Флаг, указывающий, запущен ли процесс арбитража
        
    Returns:
        InlineKeyboardMarkup: Клавиатура управления арбитражем
    """
    buttons = [
        [
            {"text": "⏹️ Остановить" if is_running else "▶️ Запустить", 
             "command": "arbitrage_control", 
             "param": "stop" if is_running else "start"}
        ],
        [
            {"text": "📊 Текущий статус", "command": "arbitrage_control", "param": "status"}
        ],
        [
            {"text": "📜 Отчет о прибыли", "command": "arbitrage_control", "param": "profit_report"}
        ],
        [
            {"text": "◀️ Назад", "command": "back", "param": "arbitrage_main"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_games_selection_keyboard(selected_games: list = None) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру выбора игр для арбитража с возможностью выделения уже выбранных игр.
    
    Args:
        selected_games: Список идентификаторов уже выбранных игр
        
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора игр с отмеченными выбранными играми
    """
    if selected_games is None:
        selected_games = []
    
    # Словарь доступных игр и их emoji
    games = {
        "cs2": "🎮 CS2",
        "dota2": "🧙‍♂️ Dota 2",
        "tf2": "🎭 TF2",
        "rust": "⚔️ Rust"
    }
    
    buttons = []
    
    # Добавляем кнопки выбора игр
    for game_id, game_name in games.items():
        # Если игра уже выбрана, добавляем отметку
        prefix = "✅ " if game_id in selected_games else ""
        buttons.append([
            {"text": f"{prefix}{game_name}", "command": "toggle_game", "param": game_id}
        ])
    
    # Добавляем кнопки для выбора/отмены всех игр и сохранения выбора
    buttons.append([
        {"text": "✅ Выбрать все", "command": "select_all_games", "param": "all"}
    ])
    
    buttons.append([
        {"text": "💾 Сохранить выбор", "command": "save_game_selection", "param": "save"}
    ])
    
    # Добавляем кнопку возврата
    buttons.append([
        {"text": "◀️ Назад", "command": "back", "param": "arbitrage_main"}
    ])
    
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_execution_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для запуска процесса арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура запуска арбитража
    """
    buttons = [
        [
            {"text": "▶️ Запустить поиск", "command": "arbitrage_exec", "param": "start"}
        ],
        [
            {"text": "🔧 Изменить бюджет", "command": "arbitrage_exec", "param": "budget"}
        ],
        [
            {"text": "🎮 Изменить игры", "command": "arbitrage_exec", "param": "games"}
        ],
        [
            {"text": "⚙️ Изменить режим", "command": "arbitrage_exec", "param": "mode"}
        ],
        [
            {"text": "◀️ Назад", "command": "back", "param": "arbitrage_main"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_results_keyboard(current_page: int = 1, total_pages: int = 1) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для просмотра результатов арбитража.
    
    Args:
        current_page: Текущая страница результатов
        total_pages: Общее количество страниц
        
    Returns:
        InlineKeyboardMarkup: Клавиатура результатов арбитража
    """
    buttons = [
        [
            {"text": "📊 Подробная статистика", "command": "arbitrage_results", "param": "stats"}
        ]
    ]
    
    # Добавляем навигацию по страницам только если есть больше одной страницы
    if total_pages > 1:
        pagination_buttons = []
        
        # Добавляем кнопку предыдущей страницы, если не на первой странице
        if current_page > 1:
            pagination_buttons.append(
                {"text": "⏪ Предыдущая", "command": "arbitrage_page", "param": "prev"}
            )
        
        # Добавляем кнопку следующей страницы, если не на последней странице
        if current_page < total_pages:
            pagination_buttons.append(
                {"text": "⏩ Следующая", "command": "arbitrage_page", "param": "next"}
            )
        
        # Информация о текущей странице
        page_info = [{"text": f"📄 {current_page}/{total_pages}", "command": "none", "param": "none"}]
        
        # Добавляем кнопки пагинации
        buttons.append(pagination_buttons)
        buttons.append(page_info)
    
    # Добавляем кнопки действий
    buttons.append([
        {"text": "▶️ Запустить новый поиск", "command": "arbitrage_exec", "param": "start"}
    ])
    
    buttons.append([
        {"text": "◀️ Назад", "command": "back", "param": "arbitrage_main"}
    ])
    
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру настроек арбитража.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура настроек арбитража
    """
    buttons = [
        [
            {"text": "🔄 Автоматический режим", "command": "arbitrage_setting", "param": "auto_mode"}
        ],
        [
            {"text": "⏱️ Интервал проверки (5 мин)", "command": "arbitrage_setting", "param": "check_interval"}
        ],
        [
            {"text": "📦 Макс. количество сделок (10)", "command": "arbitrage_setting", "param": "max_trades"}
        ],
        [
            {"text": "💵 Мин. ликвидность (0.5)", "command": "arbitrage_setting", "param": "min_liquidity"}
        ],
        [
            {"text": "📈 Включить уведомления", "command": "arbitrage_setting", "param": "notifications"}
        ],
        [
            {"text": "◀️ Назад", "command": "back", "param": "arbitrage_main"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons) 