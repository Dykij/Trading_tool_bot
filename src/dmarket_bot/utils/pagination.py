from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from aiogram.types import InlineKeyboardMarkup

T = TypeVar('T')

class PaginationResult(Generic[T]):
    """Результат пагинации с метаданными."""
    
    def __init__(self, items: List[T], total: int, page: int, page_size: int):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size
        self.total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    @property
    def has_next(self) -> bool:
        """Есть ли следующая страница."""
        return self.page < self.total_pages
    
    @property
    def has_prev(self) -> bool:
        """Есть ли предыдущая страница."""
        return self.page > 1


class Paginator(ABC, Generic[T]):
    """Абстрактный класс для реализации пагинации."""
    
    def __init__(self, page_size: int = 10):
        self.page_size = page_size
    
    @abstractmethod
    async def get_page(self, page: int) -> PaginationResult[T]:
        """Получить страницу с данными."""
        pass
    
    def set_page_size(self, page_size: int) -> None:
        """Установить размер страницы."""
        if page_size < 1:
            raise ValueError("Размер страницы должен быть положительным числом")
        self.page_size = page_size


class MemoryPaginator(Paginator[T]):
    """Реализация пагинатора для данных в памяти."""
    
    def __init__(self, items: List[T], page_size: int = 10):
        super().__init__(page_size)
        self.items = items
    
    async def get_page(self, page: int) -> PaginationResult[T]:
        if page < 1:
            page = 1
        
        start_idx = (page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        
        page_items = self.items[start_idx:end_idx]
        return PaginationResult(
            items=page_items,
            total=len(self.items),
            page=page,
            page_size=self.page_size
        )


class APIPaginator(Paginator[T]):
    """Реализация пагинатора для API запросов с offset/limit."""
    
    def __init__(self, fetch_func, page_size: int = 10, cache_ttl: int = 300):
        """
        Инициализирует API пагинатор.
        
        Args:
            fetch_func: Асинхронная функция, принимающая offset, limit и возвращающая кортеж (items, total)
            page_size: Размер страницы
            cache_ttl: Время жизни кэша в секундах
        """
        super().__init__(page_size)
        self.fetch_func = fetch_func
        self.cache_ttl = cache_ttl
        self.cache = {}
    
    async def get_page(self, page: int) -> PaginationResult[T]:
        if page < 1:
            page = 1
        
        cache_key = f"page_{page}_{self.page_size}"
        
        # Проверяем кэш
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Вычисляем offset
        offset = (page - 1) * self.page_size
        
        try:
            # Получаем данные через функцию-провайдер
            items, total = await self.fetch_func(offset, self.page_size)
            
            result = PaginationResult(
                items=items,
                total=total,
                page=page,
                page_size=self.page_size
            )
            
            # Кэшируем результат
            self.cache[cache_key] = result
            
            return result
        except Exception as e:
            # Обработка ошибок с возможностью повторной попытки
            import logging
            logging.error(f"Ошибка при получении страницы {page}: {str(e)}")
            
            # В случае ошибки возвращаем пустой результат
            return PaginationResult(
                items=[],
                total=0,
                page=page,
                page_size=self.page_size
            )


def create_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
    compact: bool = False
) -> InlineKeyboardMarkup:
    """
    Создает унифицированную клавиатуру для пагинации.
    
    Args:
        current_page: Текущая страница
        total_pages: Общее количество страниц
        callback_prefix: Префикс для callback данных
        compact: Компактный режим клавиатуры (без кнопок "В начало"/"В конец")
        
    Returns:
        InlineKeyboardMarkup: Клавиатура пагинации
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    buttons = []
    
    # Кнопка "Назад"
    if current_page > 1:
        buttons.append(InlineKeyboardButton(
            text="◀️", callback_data=f"{callback_prefix}:{current_page - 1}"
        ))
    
    if not compact:
        # Кнопка "В начало"
        if current_page > 2:
            buttons.append(InlineKeyboardButton(
                text="1", callback_data=f"{callback_prefix}:1"
            ))
        
        # Кнопка "..."
        if current_page > 3:
            buttons.append(InlineKeyboardButton(
                text="...", callback_data="noop"
            ))
    
    # Текущая страница
    buttons.append(InlineKeyboardButton(
        text=f"{current_page}/{total_pages}", callback_data="noop"
    ))
    
    if not compact:
        # Кнопка "..."
        if current_page < total_pages - 2:
            buttons.append(InlineKeyboardButton(
                text="...", callback_data="noop"
            ))
        
        # Кнопка "В конец"
        if current_page < total_pages - 1:
            buttons.append(InlineKeyboardButton(
                text=f"{total_pages}", callback_data=f"{callback_prefix}:{total_pages}"
            ))
    
    # Кнопка "Вперед"
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(
            text="▶️", callback_data=f"{callback_prefix}:{current_page + 1}"
        ))
    
    builder.row(*buttons)
    
    return builder.as_markup()


# Функция для обработки callback-данных пагинации
async def process_pagination_callback(callback_data: str) -> Dict[str, Any]:
    """
    Обрабатывает callback данные пагинации.
    
    Args:
        callback_data: Строка callback данных в формате "prefix:page"
        
    Returns:
        Dict с параметрами:
            - prefix: Префикс callback
            - page: Номер страницы
    """
    parts = callback_data.split(":")
    if len(parts) < 2:
        raise ValueError("Неверный формат callback данных для пагинации")
    
    prefix = parts[0]
    page = int(parts[1])
    
    return {
        "prefix": prefix,
        "page": page
    }


def create_infinite_scroll_keyboard(
    current_page: int,
    has_more: bool,
    callback_prefix: str
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для бесконечной прокрутки.
    
    Args:
        current_page: Текущая страница
        has_more: Есть ли еще данные
        callback_prefix: Префикс для callback данных
        
    Returns:
        InlineKeyboardMarkup: Клавиатура для бесконечной прокрутки
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    # Кнопка "Загрузить еще"
    if has_more:
        builder.row(
            InlineKeyboardButton(
                text="⬇️ Загрузить еще", 
                callback_data=f"{callback_prefix}:{current_page + 1}"
            )
        )
    
    # Кнопка "Обновить"
    builder.row(
        InlineKeyboardButton(
            text="🔄 Обновить", 
            callback_data=f"{callback_prefix}:1"
        )
    )
    
    return builder.as_markup()


class InfiniteScrollPaginator(Paginator[T]):
    """Пагинатор с бесконечной прокруткой, сохраняющий все загруженные данные."""
    
    def __init__(self, data_provider, page_size: int = 10, cache_ttl: int = 300):
        """
        Инициализирует пагинатор с бесконечной прокруткой.
        
        Args:
            data_provider: Функция, возвращающая данные для страницы
            page_size: Размер страницы
            cache_ttl: Время жизни кеша в секундах
        """
        super().__init__(page_size)
        self.data_provider = data_provider
        self.cache_ttl = cache_ttl
        self.cache = {}
        self.all_items = []
        self.total_items = 0
        self.last_updated = 0
        
    async def get_page(self, page: int) -> PaginationResult[T]:
        """
        Получает страницу данных с накоплением всех предыдущих данных.
        
        Args:
            page: Номер страницы (начиная с 1)
            
        Returns:
            PaginationResult с данными
        """
        if page < 1:
            page = 1
        
        # Проверяем необходимость сброса кеша
        import time
        current_time = time.time()
        if (current_time - self.last_updated) > self.cache_ttl:
            # Сбрасываем кеш если истекло время
            self.all_items = []
            self.total_items = 0
        
        if page == 1:
            # Для первой страницы всегда загружаем свежие данные
            self.all_items = []
            self.total_items = 0
        
        # Если запрошенная страница уже загружена ранее, возвращаем из кеша
        if len(self.all_items) >= page * self.page_size:
            start_idx = 0
            end_idx = page * self.page_size
            
            items = self.all_items[:end_idx]
            return PaginationResult(
                items=items,
                total=self.total_items,
                page=page,
                page_size=self.page_size
            )
        
        # Загружаем новые данные
        try:
            # Рассчитываем, сколько страниц нужно загрузить
            pages_to_load = page - (len(self.all_items) // self.page_size)
            if len(self.all_items) % self.page_size > 0:
                pages_to_load += 1
            
            new_items = []
            for i in range(pages_to_load):
                current_offset = len(self.all_items)
                items, total = await self.data_provider(current_offset, self.page_size)
                
                if total > self.total_items:
                    self.total_items = total
                
                if not items:
                    break
                
                new_items.extend(items)
                
                # Если получили меньше предметов, чем запрашивали, значит достигли конца
                if len(items) < self.page_size:
                    break
            
            # Добавляем новые элементы к существующим
            self.all_items.extend(new_items)
            
            # Обновляем время последнего обновления
            self.last_updated = current_time
            
            return PaginationResult(
                items=self.all_items,
                total=self.total_items,
                page=page,
                page_size=self.page_size
            )
        except Exception as e:
            import logging
            logging.error(f"Ошибка при загрузке данных для бесконечной прокрутки: {str(e)}")
            
            # В случае ошибки возвращаем то, что уже загружено
            return PaginationResult(
                items=self.all_items,
                total=self.total_items,
                page=page,
                page_size=self.page_size
            )
    
    def reset(self):
        """Сбрасывает все загруженные данные."""
        self.all_items = []
        self.total_items = 0
        self.last_updated = 0 