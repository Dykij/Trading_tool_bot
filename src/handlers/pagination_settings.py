from typing import Dict, Optional

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from handlers.pagination_handler import set_page_size
from utils.user_settings import UserSettings

router = Router()

# Стандартные размеры страниц для выбора
DEFAULT_PAGE_SIZES = [5, 10, 20, 50, 100]

# Настройки по умолчанию
DEFAULT_SETTINGS = {
    "page_size": 10,
    "use_infinite_scroll": False,
    "show_loading_indicator": True,
    "compact_mode": False
}


class PaginationSettingsState(StatesGroup):
    """Состояния для настройки пагинации."""
    waiting_for_page_size = State()
    waiting_for_scroll_type = State()


# Хранилище пользовательских настроек пагинации
user_pagination_settings: Dict[int, Dict[str, Dict]] = {}


def get_user_settings(user_id: int, list_type: Optional[str] = None) -> Dict:
    """
    Получает настройки пагинации для пользователя.
    
    Args:
        user_id: ID пользователя
        list_type: Тип списка (опционально)
        
    Returns:
        Словарь с настройками пагинации
    """
    # Получаем глобальные настройки пользователя
    if user_id not in user_pagination_settings:
        user_pagination_settings[user_id] = {}
    
    # Для конкретного типа списка
    if list_type:
        if list_type not in user_pagination_settings[user_id]:
            # Копируем глобальные настройки или значения по умолчанию
            global_settings = user_pagination_settings[user_id].get("global", DEFAULT_SETTINGS.copy())
            user_pagination_settings[user_id][list_type] = global_settings.copy()
        
        return user_pagination_settings[user_id][list_type]
    
    # Для глобальных настроек
    if "global" not in user_pagination_settings[user_id]:
        user_pagination_settings[user_id]["global"] = DEFAULT_SETTINGS.copy()
    
    return user_pagination_settings[user_id]["global"]


def create_pagination_settings_keyboard():
    """
    Создает клавиатуру для настроек пагинации.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура настроек пагинации
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки для размера страницы
    builder.row(
        InlineKeyboardButton(text="Размер страницы", callback_data="page_settings:size")
    )
    
    # Кнопки для типа прокрутки
    builder.row(
        InlineKeyboardButton(text="Тип прокрутки", callback_data="page_settings:scroll_type")
    )
    
    # Кнопка для компактного режима
    builder.row(
        InlineKeyboardButton(text="Компактный режим", callback_data="page_settings:compact")
    )
    
    # Кнопка для сброса настроек
    builder.row(
        InlineKeyboardButton(text="Сбросить настройки", callback_data="page_settings:reset")
    )
    
    # Кнопка "Назад"
    builder.row(
        InlineKeyboardButton(text="Назад", callback_data="settings:main")
    )
    
    return builder.as_markup()


def create_page_size_keyboard():
    """
    Создает клавиатуру для выбора размера страницы.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора размера страницы
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки с размерами страниц
    buttons = []
    for size in DEFAULT_PAGE_SIZES:
        buttons.append(
            InlineKeyboardButton(
                text=str(size), 
                callback_data=f"page_size:{size}"
            )
        )
    
    # Размещаем кнопки по 3 в ряд
    for i in range(0, len(buttons), 3):
        row = buttons[i:i+3]
        builder.row(*row)
    
    # Кнопка для пользовательского размера
    builder.row(
        InlineKeyboardButton(
            text="Другой размер", 
            callback_data="page_size:custom"
        )
    )
    
    # Кнопка "Назад"
    builder.row(
        InlineKeyboardButton(
            text="Назад", 
            callback_data="page_settings:main"
        )
    )
    
    return builder.as_markup()


def create_scroll_type_keyboard():
    """
    Создает клавиатуру для выбора типа прокрутки.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора типа прокрутки
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки типов прокрутки
    builder.row(
        InlineKeyboardButton(
            text="Стандартная пагинация", 
            callback_data="scroll_type:standard"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="Бесконечная прокрутка", 
            callback_data="scroll_type:infinite"
        )
    )
    
    # Кнопка "Назад"
    builder.row(
        InlineKeyboardButton(
            text="Назад", 
            callback_data="page_settings:main"
        )
    )
    
    return builder.as_markup()


@router.callback_query(F.data == "settings:pagination")
async def show_pagination_settings(callback_query: CallbackQuery):
    """Показывает настройки пагинации."""
    keyboard = create_pagination_settings_keyboard()
    await callback_query.message.edit_text(
        "Настройки пагинации:\n\n"
        "Выберите параметры отображения списков и пагинации.",
        reply_markup=keyboard
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("page_settings:"))
async def handle_pagination_settings(callback_query: CallbackQuery, state: FSMContext):
    """Обрабатывает действия в меню настроек пагинации."""
    action = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    
    # Получаем текущие настройки пользователя
    settings = get_user_settings(user_id)
    
    if action == "main":
        # Возвращаемся в главное меню настроек пагинации
        keyboard = create_pagination_settings_keyboard()
        await callback_query.message.edit_text(
            "Настройки пагинации:\n\n"
            "Выберите параметры отображения списков и пагинации.",
            reply_markup=keyboard
        )
    
    elif action == "size":
        # Показываем меню выбора размера страницы
        keyboard = create_page_size_keyboard()
        await callback_query.message.edit_text(
            f"Выберите размер страницы:\n\n"
            f"Текущий размер: {settings['page_size']} элементов",
            reply_markup=keyboard
        )
    
    elif action == "scroll_type":
        # Показываем меню выбора типа прокрутки
        keyboard = create_scroll_type_keyboard()
        
        scroll_type = "Бесконечная прокрутка" if settings.get('use_infinite_scroll', False) else "Стандартная пагинация"
        
        await callback_query.message.edit_text(
            f"Выберите тип прокрутки:\n\n"
            f"Текущий тип: {scroll_type}",
            reply_markup=keyboard
        )
    
    elif action == "compact":
        # Переключаем компактный режим
        settings['compact_mode'] = not settings.get('compact_mode', False)
        
        # Обновляем сообщение
        keyboard = create_pagination_settings_keyboard()
        compact_status = "Включен" if settings['compact_mode'] else "Выключен"
        
        await callback_query.message.edit_text(
            f"Настройки пагинации:\n\n"
            f"Компактный режим: {compact_status}",
            reply_markup=keyboard
        )
        
        await callback_query.answer(f"Компактный режим: {compact_status}")
    
    elif action == "reset":
        # Сбрасываем настройки пользователя на значения по умолчанию
        user_pagination_settings[user_id]["global"] = DEFAULT_SETTINGS.copy()
        
        # Обновляем сообщение
        keyboard = create_pagination_settings_keyboard()
        await callback_query.message.edit_text(
            "Настройки пагинации сброшены на значения по умолчанию.",
            reply_markup=keyboard
        )
        
        await callback_query.answer("Настройки сброшены")
    
    else:
        await callback_query.answer("Неизвестное действие")


@router.callback_query(F.data.startswith("page_size:"))
async def handle_page_size_selection(callback_query: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор размера страницы."""
    choice = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    
    if choice == "custom":
        # Переходим в режим ожидания пользовательского ввода
        await state.set_state(PaginationSettingsState.waiting_for_page_size)
        
        await callback_query.message.edit_text(
            "Введите желаемый размер страницы (от 1 до 100):"
        )
        
        await callback_query.answer()
        return
    
    # Устанавливаем выбранный размер страницы
    try:
        page_size = int(choice)
        if 1 <= page_size <= 100:
            # Обновляем настройки пользователя
            settings = get_user_settings(user_id)
            settings['page_size'] = page_size
            
            # Применяем настройки ко всем пагинаторам
            # Здесь можно добавить логику для применения к конкретным пагинаторам
            
            # Возвращаемся в главное меню настроек пагинации
            keyboard = create_pagination_settings_keyboard()
            await callback_query.message.edit_text(
                f"Размер страницы установлен: {page_size} элементов.",
                reply_markup=keyboard
            )
            
            await callback_query.answer(f"Размер страницы: {page_size}")
        else:
            await callback_query.answer("Размер страницы должен быть от 1 до 100")
    except ValueError:
        await callback_query.answer("Некорректное значение")


@router.callback_query(F.data.startswith("scroll_type:"))
async def handle_scroll_type_selection(callback_query: CallbackQuery):
    """Обрабатывает выбор типа прокрутки."""
    choice = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    
    # Получаем настройки пользователя
    settings = get_user_settings(user_id)
    
    if choice == "standard":
        settings['use_infinite_scroll'] = False
        scroll_type = "Стандартная пагинация"
    elif choice == "infinite":
        settings['use_infinite_scroll'] = True
        scroll_type = "Бесконечная прокрутка"
    else:
        await callback_query.answer("Неизвестный тип прокрутки")
        return
    
    # Возвращаемся в главное меню настроек пагинации
    keyboard = create_pagination_settings_keyboard()
    await callback_query.message.edit_text(
        f"Тип прокрутки установлен: {scroll_type}",
        reply_markup=keyboard
    )
    
    await callback_query.answer(f"Тип прокрутки: {scroll_type}")


@router.message(PaginationSettingsState.waiting_for_page_size)
async def process_custom_page_size(message: Message, state: FSMContext):
    """Обрабатывает пользовательский ввод размера страницы."""
    try:
        page_size = int(message.text.strip())
        
        if 1 <= page_size <= 100:
            # Получаем настройки пользователя
            user_id = message.from_user.id
            settings = get_user_settings(user_id)
            
            # Обновляем размер страницы
            settings['page_size'] = page_size
            
            # Возвращаемся в обычное состояние
            await state.clear()
            
            # Отправляем подтверждение
            keyboard = create_pagination_settings_keyboard()
            await message.answer(
                f"Размер страницы установлен: {page_size} элементов.",
                reply_markup=keyboard
            )
        else:
            # Размер страницы вне допустимого диапазона
            await message.answer(
                "Размер страницы должен быть от 1 до 100. Попробуйте еще раз:"
            )
    except ValueError:
        # Некорректный ввод
        await message.answer(
            "Пожалуйста, введите целое число от 1 до 100:"
        ) 