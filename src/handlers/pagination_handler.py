from typing import Any, Callable, Dict, List, Optional, Union

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from utils.pagination import Paginator, PaginationResult, process_pagination_callback

router = Router()

# Хранилище пагинаторов для разных типов данных
paginators: Dict[str, Paginator] = {}

# Хранилище обработчиков для разных типов данных
handlers: Dict[str, Callable] = {}

# Хранилище состояний пагинации для разных пользователей
user_pagination_state: Dict[int, Dict[str, int]] = {}


def register_paginator(prefix: str, paginator: Paginator, handler: Callable):
    """
    Регистрирует пагинатор и обработчик для конкретного типа данных.
    
    Args:
        prefix: Префикс для callback данных
        paginator: Экземпляр пагинатора
        handler: Функция обработчик, принимающая PaginationResult и возвращающая сообщение
    """
    paginators[prefix] = paginator
    handlers[prefix] = handler


@router.callback_query(lambda c: ":" in c.data and c.data.split(":")[0] in paginators)
async def handle_pagination_callback(callback_query: CallbackQuery):
    """Обрабатывает callback запросы пагинации."""
    try:
        # Извлекаем данные пагинации
        params = await process_pagination_callback(callback_query.data)
        prefix = params["prefix"]
        page = params["page"]
        
        # Получаем пагинатор и обработчик для данного префикса
        paginator = paginators.get(prefix)
        handler = handlers.get(prefix)
        
        if not paginator or not handler:
            await callback_query.answer("Обработчик для данного типа пагинации не найден")
            return
        
        # Запоминаем состояние пагинации для пользователя
        user_id = callback_query.from_user.id
        if user_id not in user_pagination_state:
            user_pagination_state[user_id] = {}
        user_pagination_state[user_id][prefix] = page
        
        # Показываем индикатор загрузки
        await callback_query.answer("Загрузка...")
        
        # Получаем данные страницы
        result = await paginator.get_page(page)
        
        # Вызываем обработчик для отображения данных
        await handler(callback_query, result)
        
    except Exception as e:
        import logging
        logging.error(f"Ошибка при обработке пагинации: {str(e)}")
        await callback_query.answer("Произошла ошибка при загрузке страницы")


async def start_pagination(
    message: Message,
    prefix: str,
    user_id: Optional[int] = None,
    page: int = 1,
    **kwargs
):
    """
    Начинает пагинацию для указанного префикса.
    
    Args:
        message: Сообщение, на которое нужно ответить
        prefix: Префикс пагинации
        user_id: ID пользователя (по умолчанию берется из message)
        page: Начальная страница
        **kwargs: Дополнительные параметры для обработчика
    """
    if not user_id:
        user_id = message.from_user.id
    
    paginator = paginators.get(prefix)
    handler = handlers.get(prefix)
    
    if not paginator or not handler:
        await message.answer("Обработчик для данного типа пагинации не найден")
        return
    
    # Запоминаем состояние пагинации для пользователя
    if user_id not in user_pagination_state:
        user_pagination_state[user_id] = {}
    user_pagination_state[user_id][prefix] = page
    
    # Получаем данные страницы
    result = await paginator.get_page(page)
    
    # Создаем фейковый callback для обработчика
    fake_callback = type('obj', (object,), {
        'message': message,
        'from_user': type('obj', (object,), {'id': user_id}),
        'answer': message.answer
    })
    
    # Вызываем обработчик для отображения данных
    await handler(fake_callback, result, **kwargs)


def get_user_page(user_id: int, prefix: str) -> int:
    """
    Получает текущую страницу пользователя для указанного префикса.
    
    Args:
        user_id: ID пользователя
        prefix: Префикс пагинации
        
    Returns:
        Номер текущей страницы или 1, если страница не найдена
    """
    if user_id in user_pagination_state and prefix in user_pagination_state[user_id]:
        return user_pagination_state[user_id][prefix]
    return 1


def set_page_size(prefix: str, page_size: int) -> bool:
    """
    Устанавливает размер страницы для указанного префикса.
    
    Args:
        prefix: Префикс пагинации
        page_size: Новый размер страницы
        
    Returns:
        True, если размер страницы был успешно установлен, иначе False
    """
    paginator = paginators.get(prefix)
    if not paginator:
        return False
    
    try:
        paginator.set_page_size(page_size)
        return True
    except Exception:
        return False 