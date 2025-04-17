"""
Модуль обработчиков команд для Telegram-бота DMarket Trading Bot.

Документация Telegram API: https://core.telegram.org/
"""

from typing import List, Dict, Any, Optional, Union
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Исправление импортов
from keyboards import get_main_keyboard  # Импортируем из пакета keyboards

# Определим недостающие функции
def get_items_keyboard(items: List[Dict]) -> Any:
    """
    Создает клавиатуру со списком предметов пользователя.

    Args:
        items: Список предметов пользователя

    Returns:
        InlineKeyboardMarkup: Клавиатура с предметами пользователя
    """
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()

    for i, item in enumerate(items):
        builder.row(
            InlineKeyboardButton(
                text=f"{item['name']} - ${item['price']:.2f}",
                callback_data=f"item_{item.get('id', i)}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="Назад", callback_data="back_to_main")
    )

    return builder.as_markup()

def get_settings_keyboard() -> Any:
    """
    Создает клавиатуру с настройками пользователя.

    Returns:
        InlineKeyboardMarkup: Клавиатура с настройками
    """
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="Уведомления", callback_data="settings_notifications")
    )
    builder.row(
        InlineKeyboardButton(text="Частота проверки", callback_data="settings_frequency")
    )
    builder.row(
        InlineKeyboardButton(text="Назад", callback_data="back_to_main")
    )

    return builder.as_markup()

def db_remove_item(user_id: int, item_id: Union[int, str]) -> None:
    """
    Удаляет предмет из базы данных.

    Args:
        user_id: ID пользователя
        item_id: ID предмета
    """
    # Реализация будет добавлена позже
    print(f"Удаление предмета {item_id} для пользователя {user_id}")

def db_get_all_items(user_id: int) -> List[Dict[str, Any]]:
    """
    Получает все предметы пользователя из базы данных.

    Args:
        user_id: ID пользователя

    Returns:
        Список предметов пользователя
    """
    # Пример реализации
    return [
        {"id": 1, "name": "AK-47 | Redline", "price": 10.50},
        {"id": 2, "name": "AWP | Asiimov", "price": 45.00}
    ]

def db_add_item(user_id: int, item_data: Dict[str, Any]) -> None:
    """
    Добавляет предмет в базу данных.

    Args:
        user_id: ID пользователя
        item_data: Данные предмета
    """
    # Реализация будет добавлена позже
    print(f"Добавление предмета {item_data['name']} для пользователя {user_id}")

# Убедитесь, что в файле config.py определено необходимое содержимое


# Настройка логгера для модуля
logger = logging.getLogger("bot_handlers")

# Создаём объект Router
router = Router()


class AddItemStates(StatesGroup):
    """Состояния для FSM при добавлении нового предмета."""
    waiting_for_name = State()        # Ожидание ввода названия предмета
    waiting_for_price = State()       # Ожидание ввода целевой цены
    waiting_for_condition = State()   # Ожидание ввода состояния предмета (опционально)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """
    Обработчик команды /start.

    Отправляет приветственное сообщение и отображает главное меню бота.

    Args:
        message: Объект сообщения от пользователя.
    """
    if message.from_user is None:
        user_id = 0
        username = "пользователь"
    else:
        user_id = message.from_user.id
        username = message.from_user.username or "пользователь"
    logger.info(f"Пользователь {user_id} ({username}) запустил бота")

    await message.answer(
        f"Добро пожаловать в бота для торговли на DMarket, {username}!\n\n"
        "Этот бот поможет вам отслеживать цены на предметы и находить выгодные предложения.",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """
    Обработчик команды /help.

    Отображает справочную информацию о доступных командах и функциях бота.

    Args:
        message: Объект сообщения от пользователя.
    """
    user_id = 0 if message.from_user is None else message.from_user.id
    logger.debug(f"Пользователь {user_id} запросил справку")

    help_text = (
        "Этот бот помогает отслеживать цены на предметы DMarket и искать арбитражные возможности.\n\n"
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/items - Показать ваши отслеживаемые предметы\n"
        "/add_item - Добавить новый предмет для отслеживания\n"
        "/settings - Настройки уведомлений и торговых параметров\n"
        "/stats - Статистика вашей торговой активности\n"
        "/search - Поиск предметов на рынке\n\n"
        "Для получения дополнительной информации о конкретной команде введите /help <команда>"
    )
    await message.answer(help_text)


@router.message(Command("items"))
async def cmd_items(message: Message) -> None:
    """
    Обработчик команды /items. Показывает список отслеживаемых предметов.

    Извлекает из базы данных все предметы, которые отслеживает пользователь,
    и отображает их с информацией о целевых ценах.

    Args:
        message: Объект сообщения от пользователя.
    """
    user_id = 0 if message.from_user is None else message.from_user.id
    logger.info(f"Пользователь {user_id} запросил список отслеживаемых предметов")

    items = db_get_all_items(user_id)

    if not items:
        await message.answer(
            "У вас пока нет отслеживаемых предметов.\n"
            "Используйте команду /add_item, чтобы добавить предмет для отслеживания.",
            reply_markup=get_main_keyboard()
        )
        return

    items_text = "Ваши отслеживаемые предметы:\n\n"
    for i, item in enumerate(items, 1):
        target_price = f"${item['price']:.2f}"
        condition = f" | {item['target_condition']}" if item.get('target_condition') else ""
        items_text += f"{i}. {item['name']}{condition} - Целевая цена: {target_price}\n"

    await message.answer(
        items_text,
        reply_markup=get_items_keyboard(items)
    )


@router.message(Command("add_item"))
async def cmd_add_item(message: Message, state: FSMContext) -> None:
    """
    Обработчик команды /add_item. Начинает процесс добавления нового предмета.

    Запускает конечный автомат состояний (FSM) для последовательного сбора
    информации о новом предмете для отслеживания.

    Args:
        message: Объект сообщения от пользователя.
        state: Контекст FSM для хранения состояния диалога.
    """
    user_id = 0 if message.from_user is None else message.from_user.id
    logger.info(f"Пользователь {user_id} начал процесс добавления нового предмета")

    await message.answer(
        "Введите название предмета, который вы хотите отслеживать.\n"
        "Например: 'AK-47 | Redline' или 'Karambit | Fade'"
    )
    await state.set_state(AddItemStates.waiting_for_name)


@router.message(AddItemStates.waiting_for_name)
async def process_item_name(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод названия предмета пользователем.

    Сохраняет введенное название и запрашивает у пользователя целевую цену.

    Args:
        message: Объект сообщения от пользователя.
        state: Контекст FSM для хранения состояния диалога.
    """
    item_name = "" if message.text is None else message.text.strip()

    if not item_name or len(item_name) < 3:
        await message.answer("Название предмета должно содержать не менее 3 символов. Пожалуйста, попробуйте еще раз.")
        return

    await state.update_data(item_name=item_name)

    await message.answer(
        f"Вы выбрали предмет: {item_name}\n\n"
        "Теперь введите целевую цену в USD (например, 42.50):"
    )
    await state.set_state(AddItemStates.waiting_for_price)


@router.message(AddItemStates.waiting_for_price)
async def process_item_price(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод целевой цены предмета пользователем.

    Проверяет корректность введенной цены, сохраняет ее и запрашивает
    дополнительную информацию о состоянии предмета.

    Args:
        message: Объект сообщения от пользователя.
        state: Контекст FSM для хранения состояния диалога.
    """
    try:
        text = "" if message.text is None else message.text.strip().replace(',', '.')
        price = float(text)

        if price <= 0:
            await message.answer("Цена должна быть положительным числом. Пожалуйста, попробуйте еще раз.")
            return

        await state.update_data(price=price)

        await message.answer(
            f"Вы указали целевую цену: ${price:.2f}\n\n"
            "Если вам важно состояние предмета (например, 'Factory New'), "
            "введите его сейчас или нажмите \"Пропустить\":",
            reply_markup=get_skip_keyboard()
        )
        await state.set_state(AddItemStates.waiting_for_condition)

    except ValueError:
        await message.answer("Пожалуйста, введите корректное числовое значение для цены.")


@router.callback_query(F.data == "skip_condition")
async def skip_item_condition(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает нажатие кнопки "Пропустить" при вводе состояния предмета.

    Завершает процесс добавления предмета без указания конкретного состояния.

    Args:
        callback: Объект обратного вызова от нажатия на кнопку.
        state: Контекст FSM для хранения состояния диалога.
    """
    # Убираем явный вызов save_new_item и обрабатываем непосредственно здесь
    if callback.message is None:
        await callback.answer("Произошла ошибка. Попробуйте еще раз.")
        return

    user_id = 0 if callback.from_user is None else callback.from_user.id
    data = await state.get_data()

    item_data = {
        "name": data.get("item_name", ""),
        "price": data.get("price", 0.0),
        "target_condition": None
    }

    # Добавляем предмет в базу данных
    db_add_item(user_id, item_data)

    logger.info(f"Пользователь {user_id} добавил предмет: {item_data['name']}, цена: {item_data['price']}")

    await callback.message.answer(
        f"Предмет успешно добавлен для отслеживания!\n\n"
        f"• {item_data['name']}\n"
        f"• Целевая цена: ${item_data['price']:.2f}",
        reply_markup=get_main_keyboard()
    )

    # Сбрасываем состояние FSM
    await state.clear()
    await callback.answer()


@router.message(AddItemStates.waiting_for_condition)
async def process_item_condition(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод состояния предмета пользователем.

    Сохраняет указанное состояние и завершает процесс добавления предмета.

    Args:
        message: Объект сообщения от пользователя.
        state: Контекст FSM для хранения состояния диалога.
    """
    condition = "" if message.text is None else message.text.strip()
    
    # Напрямую вызываем код обработки без использования save_new_item
    user_id = 0 if message.from_user is None else message.from_user.id
    data = await state.get_data()

    item_data = {
        "name": data.get("item_name", ""),
        "price": data.get("price", 0.0),
        "target_condition": condition
    }

    # Добавляем предмет в базу данных
    db_add_item(user_id, item_data)

    logger.info(f"Пользователь {user_id} добавил предмет: {item_data['name']}, цена: {item_data['price']}")

    condition_text = f", состояние: {condition}" if condition else ""
    await message.answer(
        f"Предмет успешно добавлен для отслеживания!\n\n"
        f"• {item_data['name']}\n"
        f"• Целевая цена: ${item_data['price']:.2f}{condition_text}",
        reply_markup=get_main_keyboard()
    )

    # Сбрасываем состояние FSM
    await state.clear()


def get_skip_keyboard():
    """
    Создает клавиатуру с кнопкой "Пропустить".

    Returns:
        InlineKeyboardMarkup: Объект клавиатуры с кнопкой "Пропустить".
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="skip_condition")]]
    )
