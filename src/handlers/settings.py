def get_settings_keyboard():
    """
    Создает инлайн-клавиатуру для меню настроек.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками настроек
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки основных настроек
    builder.row(
        InlineKeyboardButton(text="🌐 Язык интерфейса", callback_data="settings:language")
    )
    
    builder.row(
        InlineKeyboardButton(text="💵 Валюта", callback_data="settings:currency")
    )
    
    builder.row(
        InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings:notifications")
    )
    
    # Добавляем кнопку настроек пагинации
    builder.row(
        InlineKeyboardButton(text="📄 Настройки пагинации", callback_data="settings:pagination")
    )
    
    # Кнопки дополнительных настроек
    builder.row(
        InlineKeyboardButton(text="⚙️ API-ключи", callback_data="settings:api_keys")
    )
    
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить данные", callback_data="settings:refresh_data")
    )
    
    # Кнопка возврата
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup() 