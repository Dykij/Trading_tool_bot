"""
Модуль callback-обработчиков для телеграм-бота DMarket Trading Bot.

Этот модуль содержит определения классов callback-данных, которые используются
для обработки интерактивных действий пользователя через кнопки встроенной
клавиатуры в Telegram. Каждый класс соответствует определенному типу действия
и содержит необходимые для этого действия атрибуты.
"""

from aiogram.filters.callback_data import CallbackData
from typing import Optional, Literal, Union


class MenuCallback(CallbackData, prefix="menu"):
    """
    Callback для основного меню.

    Используется для навигации по главному меню бота и выбора
    основных функций (мои предметы, поиск, настройки и т.д.).

    Attributes:
        action: Действие для выполнения (например, "items", "search", "settings").
        item_id: Опциональный ID предмета (если действие связано с конкретным предметом).

    Examples:
        >>> MenuCallback(action="items").pack()
        'menu:items:'
        >>> MenuCallback(action="view", item_id=42).pack()
        'menu:view:42'
    """
    action: str
    item_id: Optional[Union[int, str]] = None


class CancelCallback(CallbackData):
    """
    Callback для отмены действия.

    Используется для отмены текущей операции или выхода из режима ввода.

    Attributes:
        action: Тип отмены (например, "add_item", "search", "dialog").

    Examples:
        >>> CancelCallback(action="add_item").pack()
        'cancel:add_item'
    """
    prefix = "cancel"
    action: str
    state_to_return: Optional[str] = None


class ItemBuyCallback(CallbackData):
    """
    Callback для выбора предмета из списка.

    Используется, когда пользователь выбирает предмет из списка отслеживаемых
    или найденных предметов для выполнения действия с ним.

    Attributes:
        item_id: ID предмета.
        action: Опциональное действие, которое нужно выполнить с предметом.
    """
    prefix = "item"
    item_id: Union[int, str]
    action: Optional[str] = None


class BuyingCallback(CallbackData):
    """
    Callback для процесса покупки.

    Используется для обработки действий, связанных с покупкой предметов.

    Attributes:
        item_id: ID предмета, который пользователь хочет купить.
        quantity: Количество предметов для покупки.
    """
    prefix = "buy"
    item_id: Union[int, str]
    quantity: Optional[int] = 1


class DeleteCallback(CallbackData):
    """
    Callback для удаления предмета из отслеживаемых.

    Используется при удалении предмета из списка отслеживаемых, с возможностью
    запроса подтверждения для предотвращения случайных удалений.

    Attributes:
        item_id: ID предмета для удаления.
        confirm: Флаг подтверждения удаления.
    """
    prefix = "delete"
    item_id: Union[int, str]
    confirm: bool = False


class RestartCallback(CallbackData):
    """
    Callback для перезапуска процесса.

    Используется для перезапуска различных процессов, таких как добавление
    предмета или поиск, в случае если пользователь хочет начать заново.

    Attributes:
        process: Опциональное название процесса для перезапуска.
    """
    prefix = "restart"
    process: Optional[str] = None


class PaginationCallback(CallbackData):
    """
    Callback для пагинации списка предметов.

    Используется для навигации по страницам при отображении длинных списков
    предметов (например, результатов поиска или истории сделок).

    Attributes:
        page: Номер страницы.
        list_type: Тип списка, по которому осуществляется навигация (опционально).
    """
    prefix = "page"
    page: int
    list_type: Optional[str] = None


class ChartCallback(CallbackData):
    """
    Callback для отображения графика цен.

    Используется для запроса графиков цен на предметы с возможностью
    выбора различных временных периодов для анализа.

    Attributes:
        item_id: ID предмета.
        period: Период отображения (день, неделя, месяц, год).
        chart_type: Тип графика (например, "line", "candle").

    Examples:
        >>> ChartCallback(item_id=123, period="week").pack()
        'chart:123:week:None'
        >>> ChartCallback(item_id=123, period="month", chart_type="candle").pack()
        'chart:123:month:candle'
    """
    prefix = "chart"
    item_id: Union[int, str]
    period: Literal["day", "week", "month", "year"] = "week"
    chart_type: Optional[str] = None


class SettingsCallback(CallbackData):
    """
    Callback для изменения настроек пользователя.

    Используется для навигации по меню настроек и изменения различных
    параметров пользователя, таких как валюта, частота уведомлений и др.

    Attributes:
        action: Действие в настройках ("currency", "notifications", "theme" и т.д.).
        value: Значение для установки (зависит от типа действия).

    Examples:
        >>> SettingsCallback(action="currency").pack()
        'settings:currency:None'
        >>> SettingsCallback(action="currency", value="USD").pack()
        'settings:currency:USD'
    """
    prefix = "settings"
    action: str
    value: Optional[str] = None


class FilterCallback(CallbackData):
    """
    Callback для фильтрации списков предметов.

    Используется для установки и применения фильтров при просмотре списков
    предметов или результатов поиска.

    Attributes:
        filter_type: Тип фильтра ("price", "condition", "category" и т.д.).
        value: Значение фильтра.
        apply: Флаг применения фильтра (True) или сброса фильтра (False).

    Examples:
        >>> FilterCallback(filter_type="price", value="<100", apply=True).pack()
        'filter:price:<100:True'
    """
    prefix = "filter"
    filter_type: str
    value: str
    apply: bool = True
