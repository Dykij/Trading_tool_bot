"""
Модуль для сбора данных с торговой площадки DMarket.

Этот модуль предоставляет класс DataCollector, который инкапсулирует
функциональность для сбора рыночных данных, информации об инвентаре
пользователя и истории цен предметов с использованием API DMarket.
"""

from typing import Dict, Any, List, Optional, Literal, Union, Callable
import logging
import time
import asyncio
from datetime import datetime
from api_wrapper import DMarketAPI


# Настройка логгера для модуля
logger = logging.getLogger("data_collector")

# Определение переменной GAME_ID
GAME_ID = "csgo"  # Изменено на конкретное значение для Counter-Strike: Global Offensive


class DataCollector:
    """
    Класс для сбора данных с торговой площадки DMarket.

    Предоставляет методы для получения рыночных данных, инвентаря и истории предметов.
    Реализует логику для агрегации данных и их предварительной обработки перед
    использованием в аналитических алгоритмах и торговых стратегиях.

    Attributes:
        api: Экземпляр класса DMarketAPI для выполнения запросов к API.
        game_id: Идентификатор игры, для которой собираются данные.
        last_request_time: Время последнего запроса для контроля частоты запросов.
    """

    def __init__(self, api_key: str, api_secret: Optional[str] = None,
                 game_id: str = GAME_ID) -> None:
        """
        Инициализация коллектора данных.

        Args:
            api_key: API-ключ для авторизации запросов к DMarket
            api_secret: API-секрет для подписи запросов (опционально)
            game_id: Идентификатор игры (по умолчанию используется GAME_ID)
        """
        self.api = DMarketAPI(api_key, api_secret)
        self.game_id = game_id
        self.last_request_time = datetime.now()
        logger.info("Инициализирован DataCollector для игры %s", game_id)

    def _respect_rate_limit(self, min_interval: float = 0.5) -> None:
        """
        Соблюдает ограничения API, задерживая запрос при необходимости.
        
        Args:
            min_interval: Минимальный интервал между запросами в секундах
        """
        current_time = datetime.now()
        elapsed = (current_time - self.last_request_time).total_seconds()

        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug("Соблюдение ограничений API: ожидание %.2f сек", sleep_time)
            # Упрощаем логику - в синхронном методе всегда используем time.sleep
            time.sleep(sleep_time)

        self.last_request_time = datetime.now()
        
    async def _respect_rate_limit_async(self, min_interval: float = 0.5) -> None:
        """
        Асинхронная версия метода соблюдения ограничений API.
        
        Args:
            min_interval: Минимальный интервал между запросами в секундах
        """
        current_time = datetime.now()
        elapsed = (current_time - self.last_request_time).total_seconds()

        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug("Соблюдение ограничений API (асинхронно): ожидание %.2f сек", sleep_time)
            await asyncio.sleep(sleep_time)
            
        self.last_request_time = datetime.now()

    def fetch_market_data(
        self,
        limit: int = 100,
        offset: int = 0,
        currency: str = "USD",
        order_by: str = "price",
        order_dir: Literal['asc', 'desc'] = 'asc',
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получает данные о предметах на рынке.

        Выполняет запрос к API DMarket для получения списка предметов,
        доступных на рынке с указанными параметрами фильтрации.

        Args:
            limit: Максимальное количество возвращаемых предметов
            offset: Смещение для пагинации
            currency: Валюта для цен (по умолчанию USD)
            order_by: Поле для сортировки (по умолчанию "price")
            order_dir: Направление сортировки ('asc' или 'desc')
            title: Фильтр по названию предмета (опционально)

        Returns:
            Dict[str, Any]: Словарь с данными о предметах на рынке

        Raises:
            ValueError, IOError, KeyError: При ошибках связи с API или обработки ответа
        """
        self._respect_rate_limit()
        logger.info("Запрос рыночных данных: game_id=%s, limit=%s, offset=%s",
                    self.game_id, limit, offset)

        # Убедимся, что order_dir имеет правильное значение
        if order_dir not in ('asc', 'desc'):
            order_dir = 'asc'  # По умолчанию используем 'asc', если передано некорректное значение

        try:
            result = self.api.get_market_items(
                game_id=self.game_id,
                limit=limit,
                offset=offset,
                currency=currency,
                order_by=order_by,
                order_dir=order_dir,
                title=title
            )
            logger.info("Получено %s предметов с рынка",
                        len(result.get('objects', [])))
            return result
        except (ValueError, IOError, KeyError) as e:
            logger.error("Ошибка при получении рыночных данных: %s", str(e))
            raise

    def fetch_inventory(self) -> Dict[str, Any]:
        """
        Получает информацию об инвентаре пользователя.

        Выполняет запрос к API DMarket для получения списка предметов,
        находящихся в инвентаре авторизованного пользователя.

        Returns:
            Dict[str, Any]: Словарь с информацией об инвентаре пользователя

        Raises:
            ValueError, IOError, KeyError: При ошибках связи с API или обработки ответа
        """
        self._respect_rate_limit()
        logger.info("Запрос данных инвентаря для game_id=%s", self.game_id)

        try:
            result = self.api.get_user_inventory(game_id=self.game_id)
            logger.info("Получено %s предметов из инвентаря",
                        len(result.get('objects', [])))
            return result
        except (ValueError, IOError, KeyError) as e:
            logger.error("Ошибка при получении данных инвентаря: %s", str(e))
            raise

    def fetch_item_history(
        self,
        item_id: str,
        limit: int = 100,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Получает историю конкретного предмета.

        Выполняет запрос к API DMarket для получения исторических данных
        о цене и продажах конкретного предмета.

        Args:
            item_id: Идентификатор предмета
            limit: Максимальное количество записей истории (по умолчанию 100)
            offset: Смещение для пагинации
            date_from: Начальная дата для фильтрации истории (опционально)
            date_to: Конечная дата для фильтрации истории (опционально)

        Returns:
            Dict[str, Any]: Словарь с историей цен и продаж предмета

        Raises:
            ValueError, IOError, KeyError: При ошибках связи с API или обработки ответа
        """
        self._respect_rate_limit()
        logger.info("Запрос истории для предмета %s", item_id)

        try:
            result = self.api.get_item_history(
                item_id=item_id,
                limit=limit,
                offset=offset,
                date_from=date_from,
                date_to=date_to
            )
            logger.info("Получено %s записей истории",
                       len(result.get('history', [])))
            return result
        except (ValueError, IOError, KeyError) as e:
            logger.error("Ошибка при получении истории предмета: %s", str(e))
            raise

    def fetch_multiple_items_history(self, item_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Получает историю для нескольких предметов.

        Последовательно запрашивает историю для каждого предмета из списка
        и объединяет результаты в один словарь.

        Args:
            item_ids: Список идентификаторов предметов

        Returns:
            Dict[str, Dict[str, Any]]: Словарь с историями предметов,
            где ключ - идентификатор предмета, значение - его история
        """
        result = {}
        logger.info(f"Запрос истории для {len(item_ids)} предметов")

        for item_id in item_ids:
            try:
                item_history = self.fetch_item_history(item_id)
                result[item_id] = item_history
            except Exception as e:
                logger.warning(f"Не удалось получить историю для предмета {item_id}: {str(e)}")
                result[item_id] = {"error": str(e)}

        return result

    def search_items(
        self,
        title: str = "",
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        currency: str = "USD",
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Выполняет поиск предметов на рынке по различным параметрам.

        Args:
            title: Название или часть названия предмета
            category: Категория предмета (опционально)
            min_price: Минимальная цена (опционально)
            max_price: Максимальная цена (опционально)
            currency: Валюта для цен (по умолчанию USD)
            limit: Максимальное количество результатов

        Returns:
            Dict[str, Any]: Результаты поиска предметов
        """
        self._respect_rate_limit()
        logger.info(f"Поиск предметов: title='{title}', category={category}, min_price={min_price}, max_price={max_price}")

        try:
            result = self.api.search_items(
                game_id=self.game_id,
                title=title,
                category=category,
                min_price=min_price,
                max_price=max_price,
                currency=currency,
                limit=limit
            )
            logger.info(f"Найдено {len(result.get('objects', []))} предметов")
            return result
        except Exception as e:
            logger.error(f"Ошибка при поиске предметов: {str(e)}")
            raise
