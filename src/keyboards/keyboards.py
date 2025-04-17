from typing import List, Dict, Optional, Union, Any
import logging

# Try to import aiogram
try:
    from aiogram.types import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        KeyboardButton,
        ReplyKeyboardMarkup,
        WebAppInfo,
        ReplyKeyboardRemove
    )
    
    # Try to detect aiogram version
    import pkg_resources
    try:
        aiogram_version = pkg_resources.get_distribution("aiogram").version
        IS_AIOGRAM_V2 = aiogram_version.startswith("2.")
        print(f"Используем aiogram версии: {'v2' if IS_AIOGRAM_V2 else 'v3'}")
    except Exception as e:
        print(f"Ошибка при определении версии aiogram: {e}")
        IS_AIOGRAM_V2 = True  # По умолчанию используем v2
    
except ImportError:
    print("Ошибка: модуль aiogram не установлен.")
    IS_AIOGRAM_V2 = True  # По умолчанию используем v2

try:
    from handlers.callbacks import (
        BuyingCallback,
        CancelCallback,
        DeleteCallback,
        ItemBuyCallback,
        MenuCallback,
        PaginationCallback
    )
except ImportError:
    print("Предупреждение: модуль handlers.callbacks не найден.")

# Инициализируем логгер
logger = logging.getLogger("keyboards")

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
            buttons: Список списков с параметрами кнопок (text, command, param, url)
            
        Returns:
            Объект инлайн-клавиатуры
        """
        keyboard = InlineKeyboardMarkup()
        
        for row in buttons:
            row_buttons = []
            for button in row:
                # Проверяем наличие необходимых параметров
                text = button.get("text", "")
                command = button.get("command", "")
                param = button.get("param", "")
                url = button.get("url", None)
                
                if url:
                    row_buttons.append(InlineKeyboardButton(text=text, url=url))
                else:
                    # Используем современный формат callback_data: "command:param"
                    callback_data = f"{command}:{param}" if param else command
                    row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))
            
            keyboard.add(*row_buttons)
        
        return keyboard
    
    @staticmethod
    def create_inline_keyboard(buttons: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
        """
        Создает инлайн-клавиатуру в зависимости от версии aiogram.
        
        Args:
            buttons: Список списков с параметрами кнопок
            
        Returns:
            Объект инлайн-клавиатуры
        """
        # Всегда используем версию v2, так как мы установили IS_AIOGRAM_V2 = True
        return KeyboardFactory.create_inline_keyboard_v2(buttons)

# Оригинальные клавиатуры из keyboards/keyboards.py
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает и возвращает основную клавиатуру с кнопками меню.

    Returns:
        ReplyKeyboardMarkup: Клавиатура с основными командами.
    """
    buttons = [
        [
            KeyboardButton(text="📋 Мои предметы"),
            KeyboardButton(text="📝 Добавить предмет")
        ],
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="❓ Помощь")
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие"
    )


def get_menu_kb() -> InlineKeyboardMarkup:
    """
    Создает и возвращает инлайн клавиатуру с меню.

    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура с меню.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📝 Добавить предметы",
            callback_data="menu:add_items"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📋 Мои предметы",
            callback_data="menu:my_items"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data="menu:statistics"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🌐 Открыть DMarket",
            web_app=WebAppInfo(url="https://dmarket.com")
        )
    )

    return builder.as_markup()


def get_cancel_kb() -> InlineKeyboardMarkup:
    """
    Создает и возвращает инлайн-клавиатуру для отмены действия.

    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура с кнопкой отмены.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_action"
        )
    )

    return builder.as_markup()


def get_my_items_kb(items: List[Dict], page: int = 0, items_per_page: int = 5) -> InlineKeyboardMarkup:
    """
    Создает и возвращает инлайн клавиатуру со списком предметов пользователя с поддержкой пагинации.

    Args:
        items: Список предметов пользователя.
        page: Текущая страница (начиная с 0).
        items_per_page: Количество предметов на странице.

    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура со списком предметов.
    """
    builder = InlineKeyboardBuilder()

    # Вычисляем начальный и конечный индексы для текущей страницы
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(items))

    # Добавляем кнопки для предметов на текущей странице
    for item in items[start_idx:end_idx]:
        builder.row(
            InlineKeyboardButton(
                text=f"{item['name']} | ${item['price']}",
                callback_data=ItemBuyCallback(item_id=item['id']).pack()
            )
        )

    # Добавляем кнопки навигации, если необходимо
    navigation_buttons = []

    # Добавляем кнопку "Назад", если мы не на первой странице
    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=PaginationCallback(action="prev", page=page-1).pack()
            )
        )

    # Добавляем кнопку "Вперёд", если есть следующая страница
    if end_idx < len(items):
        navigation_buttons.append(
            InlineKeyboardButton(
                text="Вперёд ▶️",
                callback_data=PaginationCallback(action="next", page=page+1).pack()
            )
        )

    # Добавляем кнопки навигации, если они есть
    if navigation_buttons:
        builder.row(*navigation_buttons)

    # Добавляем кнопку "Назад в меню"
    builder.row(
        InlineKeyboardButton(
            text="↩️ В меню",
            callback_data=CancelCallback(action="cancel").pack()
        )
    )

    return builder.as_markup()


def get_item_kb(item_id: Union[int, str]) -> InlineKeyboardMarkup:
    """
    Создает и возвращает инлайн клавиатуру для управления предметом.

    Args:
        item_id: Идентификатор предмета (целое число или строка).

    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура для управления предметом.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🛒 Купить",
            callback_data=BuyingCallback(item_id=item_id).pack()
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📊 График цен",
            callback_data=MenuCallback(action="price_chart", item_id=item_id).pack()
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="❌ Удалить",
            callback_data=DeleteCallback(item_id=item_id).pack()
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data=MenuCallback(action="my_items").pack()
        )
    )

    return builder.as_markup()


def get_confirmation_kb(action: str, item_id: Optional[Union[int, str]] = None) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру подтверждения действия.
    
    Args:
        action: Действие, которое нужно подтвердить
        item_id: Идентификатор предмета (если применимо)
        
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура подтверждения
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:yes"),
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"confirm:no")
    )
    
    return builder.as_markup()

# Дополнительные клавиатуры из DM/keyboards.py и DM/custom_keyboards.py
def get_dmarket_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает основную клавиатуру для DMarket бота.
    
    Returns:
        ReplyKeyboardMarkup: Основная клавиатура
    """
    buttons = [
        ["📊 Анализ", "💰 Торговля"],
        ["⚙️ Настройки", "📝 Таргет-ордера"],
        ["🔍 Арбитраж скинов", "📈 Мониторинг цен"]
    ]
    return KeyboardFactory.create_reply_keyboard(buttons)

def get_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру с настройками.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура с настройками
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings:notifications")
    )
    
    builder.row(
        InlineKeyboardButton(text="⏱️ Частота проверки", callback_data="settings:frequency")
    )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()

def get_analysis_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру анализа рынка.
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура анализа рынка
    """
    buttons = [
        ["📊 Популярные предметы"],
        ["🔍 Поиск предмета", "🎯 Арбитраж"],
        ["📉 Тренды цен", "⏱️ История"],
        ["🔄 Кросс-платформа", "💡 Рекомендации"],
        ["◀️ Назад"]
    ]
    return KeyboardFactory.create_reply_keyboard(buttons)

def get_trading_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру торговли.
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура торговли
    """
    buttons = [
        ["🛒 Купить", "💵 Продать"],
        ["📋 Активные заказы", "📜 История сделок"],
        ["🔖 Целевые ордера", "📊 Мониторинг"],
        ["🔄 Обмен", "💎 Избранное"],
        ["◀️ Назад"]
    ]
    return KeyboardFactory.create_reply_keyboard(buttons)

def get_item_actions_keyboard(item_id: str) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру с действиями для предмета.
    
    Args:
        item_id: Идентификатор предмета
        
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура с действиями
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="💰 Купить", callback_data=f"item:buy:{item_id}"),
        InlineKeyboardButton(text="💵 Продать", callback_data=f"item:sell:{item_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="📊 Анализ цены", callback_data=f"item:analyze:{item_id}"),
        InlineKeyboardButton(text="📈 История", callback_data=f"item:history:{item_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="⭐ В избранное", callback_data=f"item:favorite:{item_id}"),
        InlineKeyboardButton(text="❌ Удалить", callback_data=f"item:delete:{item_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()

def get_game_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру выбора игры.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура выбора игры
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔫 CS2", callback_data="game:cs2"),
        InlineKeyboardButton(text="🗡️ Dota 2", callback_data="game:dota2")
    )
    
    builder.row(
        InlineKeyboardButton(text="🏝️ RUST", callback_data="game:rust"),
        InlineKeyboardButton(text="🎯 Team Fortress 2", callback_data="game:tf2")
    )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()

def get_price_range_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру выбора диапазона цен.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура диапазона цен
    """
    buttons = [
        [
            {"text": "< $1", "command": "price_range", "param": "0_1"},
            {"text": "$1-$5", "command": "price_range", "param": "1_5"},
            {"text": "$5-$10", "command": "price_range", "param": "5_10"}
        ],
        [
            {"text": "$10-$50", "command": "price_range", "param": "10_50"},
            {"text": "$50-$100", "command": "price_range", "param": "50_100"},
            {"text": "$100+", "command": "price_range", "param": "100_999999"}
        ],
        [
            {"text": "Свой диапазон", "command": "price_range", "param": "custom"}
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
            {"text": "7 дней", "command": "period", "param": "7d"}
        ],
        [
            {"text": "30 дней", "command": "period", "param": "30d"},
            {"text": "3 месяца", "command": "period", "param": "90d"}
        ],
        [
            {"text": "За всё время", "command": "period", "param": "all"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_target_orders_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру для целевых ордеров.
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура целевых ордеров
    """
    buttons = [
        ["🔖 Создать ордер", "📋 Мои ордера"],
        ["🔍 Найти ордер", "❌ Отменить ордер"],
        ["📊 Мониторинг", "⚙️ Настройки ордеров"],
        ["◀️ Назад"]
    ]
    return KeyboardFactory.create_reply_keyboard(buttons)

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
            {"text": "📝 Изменить", "command": "edit_order", "param": order_id}
        ],
        [
            {"text": "❌ Отменить", "command": "cancel_order", "param": order_id},
            {"text": "📊 Статус", "command": "order_status", "param": order_id}
        ],
        [
            {"text": "🔔 Уведомления", "command": "order_notify", "param": order_id}
        ],
        [
            {"text": "◀️ Назад", "command": "orders_list", "param": ""}
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
            {"text": "🛒 Лимитный ордер на покупку", "command": "create_buy_limit", "param": ""}
        ],
        [
            {"text": "💰 Лимитный ордер на продажу", "command": "create_sell_limit", "param": ""}
        ],
        [
            {"text": "⏱️ Отложенный ордер", "command": "create_delayed", "param": ""}
        ],
        [
            {"text": "◀️ Назад", "command": "target_orders", "param": ""}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_marketplace_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру выбора маркетплейса.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура выбора маркетплейса
    """
    buttons = [
        [
            {"text": "🌐 DMarket", "command": "marketplace", "param": "dmarket"}
        ],
        [
            {"text": "🎮 Steam", "command": "marketplace", "param": "steam"},
            {"text": "🎯 CS.Money", "command": "marketplace", "param": "csmoney"}
        ],
        [
            {"text": "💎 BitSkins", "command": "marketplace", "param": "bitskins"},
            {"text": "💵 Skinport", "command": "marketplace", "param": "skinport"}
        ],
        [
            {"text": "🔄 Сравнить все", "command": "marketplace", "param": "compare_all"}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_mode_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру выбора режима арбитража.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура режима арбитража
    """
    buttons = [
        [
            {"text": "🚀 Быстрый", "command": "arb_mode", "param": "fast"}
        ],
        [
            {"text": "⚖️ Сбалансированный", "command": "arb_mode", "param": "balanced"}
        ],
        [
            {"text": "🛡️ Безопасный", "command": "arb_mode", "param": "safe"}
        ],
        [
            {"text": "⚙️ Ручной", "command": "arb_mode", "param": "manual"}
        ],
        [
            {"text": "◀️ Назад", "command": "arbitrage_settings", "param": ""}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_auto_trade_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для автоматической торговли.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура автоматической торговли
    """
    buttons = [
        [
            {"text": "✅ Включить автоторговлю", "command": "auto_trade", "param": "on"}
        ],
        [
            {"text": "⏱️ Настройка расписания", "command": "auto_trade", "param": "schedule"}
        ],
        [
            {"text": "💰 Лимиты автоторговли", "command": "auto_trade", "param": "limits"}
        ],
        [
            {"text": "🔔 Уведомления", "command": "auto_trade", "param": "notifications"}
        ],
        [
            {"text": "◀️ Назад", "command": "arbitrage_settings", "param": ""}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру настроек арбитража.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура настроек арбитража
    """
    buttons = [
        [
            {"text": "🎮 Игра", "command": "arb_settings", "param": "game"}
        ],
        [
            {"text": "💲 Диапазон цен", "command": "arb_settings", "param": "price_range"}
        ],
        [
            {"text": "📈 Мин. профит", "command": "arb_settings", "param": "min_profit"}
        ],
        [
            {"text": "🌐 Маркетплейсы", "command": "arb_settings", "param": "marketplaces"}
        ],
        [
            {"text": "⏱️ Интервал проверки", "command": "arb_settings", "param": "interval"}
        ],
        [
            {"text": "🔄 Режим", "command": "arb_settings", "param": "mode"}
        ],
        [
            {"text": "◀️ Назад", "command": "arbitrage_main", "param": ""}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_main_keyboard() -> InlineKeyboardMarkup:
    """
    Создает главную инлайн-клавиатуру для арбитража.
    
    Returns:
        InlineKeyboardMarkup: Главная инлайн-клавиатура арбитража
    """
    buttons = [
        [
            {"text": "🚀 Запустить поиск", "command": "arb_start", "param": ""}
        ],
        [
            {"text": "⚙️ Настройки", "command": "arb_settings", "param": ""}
        ],
        [
            {"text": "📊 Статистика", "command": "arb_stats", "param": ""}
        ],
        [
            {"text": "📜 История", "command": "arb_history", "param": ""}
        ],
        [
            {"text": "❓ Помощь", "command": "arb_help", "param": ""}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_profit_range_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру выбора диапазона прибыли.
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура диапазона прибыли
    """
    buttons = [
        [
            {"text": "> 5%", "command": "profit_range", "param": "5"},
            {"text": "> 10%", "command": "profit_range", "param": "10"}
        ],
        [
            {"text": "> 15%", "command": "profit_range", "param": "15"},
            {"text": "> 20%", "command": "profit_range", "param": "20"}
        ],
        [
            {"text": "> 30%", "command": "profit_range", "param": "30"},
            {"text": "> 50%", "command": "profit_range", "param": "50"}
        ],
        [
            {"text": "Свой %", "command": "profit_range", "param": "custom"}
        ],
        [
            {"text": "◀️ Назад", "command": "arbitrage_settings", "param": ""}
        ]
    ]
    return KeyboardFactory.create_inline_keyboard(buttons)

def get_arbitrage_control_keyboard(is_running: bool = False) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру управления арбитражем.
    
    Args:
        is_running: Запущен ли поиск арбитража
        
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура управления арбитражем
    """
    buttons = []
    
    if is_running:
        buttons.append([
            {"text": "⏹️ Остановить поиск", "command": "arb_stop", "param": ""}
        ])
    else:
        buttons.append([
            {"text": "▶️ Запустить поиск", "command": "arb_start", "param": ""}
        ])
    
    buttons.append([
        {"text": "🔄 Обновить результаты", "command": "arb_refresh", "param": ""}
    ])
    
    buttons.append([
        {"text": "⚙️ Настройки", "command": "arb_settings", "param": ""}
    ])
    
    buttons.append([
        {"text": "📊 Статистика", "command": "arb_stats", "param": ""},
        {"text": "📜 История", "command": "arb_history", "param": ""}
    ])
    
    return KeyboardFactory.create_inline_keyboard(buttons)
