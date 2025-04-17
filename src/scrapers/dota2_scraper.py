"""
Скрапер для сбора данных о предметах Dota 2, включая цены, редкость и другие характеристики.
Поддерживает получение данных с сайта prices.tf и Steam Community Market.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from .base_scraper import BaseScraper

logger = logging.getLogger('scrapers.dota2')

class Dota2Scraper(BaseScraper):
    """
    Скрапер для получения данных о предметах Dota 2.
    Собирает информацию о ценах, редкости, категориях и других характеристиках предметов.
    """
    
    # Маппинг категорий предметов
    ITEM_CATEGORIES = {
        'courier': 'Курьер',
        'ward': 'Вард',
        'weapon': 'Оружие',
        'armor': 'Броня',
        'head': 'Голова',
        'misc': 'Разное',
        'set': 'Набор',
        'taunt': 'Насмешка',
        'treasure': 'Сундук',
        'emblem': 'Эмблема',
        'hud': 'HUD',
        'music': 'Музыка',
        'announcer': 'Диктор'
    }
    
    # Маппинг героев Dota 2
    HEROES = {
        'axe': 'Акс',
        'antimage': 'Антимаг',
        'ancient_apparition': 'Древний апарат',
        'crystal_maiden': 'Кристальная дева',
        'drow_ranger': 'Дроу рейнджер',
        'invoker': 'Инвокер',
        'juggernaut': 'Джаггернаут',
        'pudge': 'Пудж',
        'rubick': 'Рубик',
        'shadow_fiend': 'Шадоу финд',
        'sven': 'Свен',
        'techies': 'Минёры',
        'templar_assassin': 'Темплар ассасин',
        'terrorblade': 'Террорблейд',
        'windrunner': 'Виндранер',
        'zuus': 'Зевс'
    }
    
    # Маппинг редкости предметов
    ITEM_RARITIES = {
        'common': 'Обычный',
        'uncommon': 'Необычный',
        'rare': 'Редкий',
        'mythical': 'Мифический',
        'legendary': 'Легендарный',
        'immortal': 'Бессмертный',
        'arcana': 'Аркана',
        'ancient': 'Древний'
    }
    
    def __init__(self, 
                api_key: Optional[str] = None,
                cache_ttl: int = 3600,
                request_delay: float = 0.5,
                max_retries: int = 3,
                proxy: Optional[str] = None):
        """
        Инициализация скрапера Dota 2.
        
        Args:
            api_key: API ключ (если требуется)
            cache_ttl: Время жизни кэша в секундах (по умолчанию 1 час)
            request_delay: Задержка между запросами в секундах
            max_retries: Максимальное количество повторных попыток при ошибке
            proxy: URL прокси-сервера (если требуется)
        """
        super().__init__(
            name='Dota2PricesScraper',
            base_url='https://prices.tf',
            cache_ttl=cache_ttl,
            request_delay=request_delay,
            max_retries=max_retries,
            proxy=proxy
        )
        
        self.api_key = api_key
        self.steam_base_url = 'https://steamcommunity.com/market/listings/570'
        self.api_base_url = 'https://api.prices.tf'
        
        # Настраиваем заголовки для API запросов
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'
            
        logger.info(f"Инициализирован скрапер {self.name} с базовым URL {self.base_url}")
    
    async def get_item_prices(self, limit: int = 100, hero: Optional[str] = None, 
                              category: Optional[str] = None, rarity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получает список предметов Dota 2 с ценами.
        
        Args:
            limit: Максимальное количество предметов для получения
            hero: Фильтр по герою (опционально)
            category: Фильтр по категории (опционально)
            rarity: Фильтр по редкости (опционально)
            
        Returns:
            Список предметов с ценами и дополнительной информацией
        """
        logger.info(f"Получение списка предметов Dota 2 (лимит: {limit}, герой: {hero}, категория: {category}, редкость: {rarity})")
        
        items = []
        page = 1
        per_page = min(50, limit)  # Обычный размер страницы для API
        
        while len(items) < limit:
            try:
                # Формируем параметры запроса
                params = {
                    'page': page,
                    'limit': per_page,
                    'game': 'dota2'
                }
                
                # Добавляем фильтры, если они указаны
                if hero:
                    params['hero'] = hero
                
                if category:
                    params['category'] = category
                
                if rarity:
                    params['rarity'] = rarity
                
                # Выполняем запрос
                if self.api_key:
                    # Используем API, если есть ключ
                    response = await self._make_request(
                        path=f"{self.api_base_url}/items",
                        params=params
                    )
                    
                    if not response or 'items' not in response:
                        logger.warning(f"Некорректный ответ API: {response}")
                        break
                    
                    page_items = response.get('items', [])
                else:
                    # Парсим HTML страницу
                    url_params = []
                    if hero:
                        url_params.append(f"hero={hero}")
                    if category:
                        url_params.append(f"category={category}")
                    if rarity:
                        url_params.append(f"rarity={rarity}")
                    if page > 1:
                        url_params.append(f"page={page}")
                    
                    url_suffix = f"?{'&'.join(url_params)}" if url_params else ""
                    
                    html = await self._make_request(
                        path=f"/dota2/items{url_suffix}"
                    )
                    
                    if not html:
                        logger.warning("Не удалось получить HTML-страницу")
                        break
                    
                    # Здесь должен быть парсинг HTML
                    # В реальной реализации используем BeautifulSoup или другую библиотеку
                    # Для примера просто вернем пустой список
                    page_items = []
                
                if not page_items:
                    logger.info(f"Страница {page} не содержит предметов, завершаем")
                    break
                
                # Обрабатываем полученные предметы
                for item_data in page_items:
                    processed_item = self._process_item(item_data)
                    if processed_item:
                        items.append(processed_item)
                        
                        # Проверяем, достигли ли мы лимита
                        if len(items) >= limit:
                            break
                
                # Увеличиваем номер страницы для следующего запроса
                page += 1
                
                # Добавляем задержку, чтобы не перегружать сервер
                await asyncio.sleep(self.request_delay)
                
            except Exception as e:
                logger.error(f"Ошибка при получении списка предметов: {str(e)}")
                break
        
        logger.info(f"Получено {len(items)} предметов Dota 2")
        return items[:limit]
    
    async def get_item_details(self, item_name: str) -> Dict[str, Any]:
        """
        Получает детальную информацию о конкретном предмете Dota 2.
        
        Args:
            item_name: Название предмета
            
        Returns:
            Словарь с детальной информацией о предмете
            
        Raises:
            ValueError: Если предмет не найден
        """
        logger.info(f"Получение информации о предмете Dota 2: {item_name}")
        
        try:
            # Сначала ищем предмет
            if self.api_key:
                # Используем API если есть ключ
                response = await self._make_request(
                    path=f"{self.api_base_url}/search",
                    params={'query': item_name, 'game': 'dota2', 'limit': 10}
                )
                
                if not response or 'items' not in response:
                    logger.warning(f"Некорректный ответ API при поиске: {response}")
                    raise ValueError(f"Предмет '{item_name}' не найден")
                
                search_results = response.get('items', [])
            else:
                # Парсим страницу поиска
                html = await self._make_request(
                    path=f"/search?q={item_name}&game=dota2"
                )
                
                if not html:
                    logger.warning("Не удалось получить HTML-страницу поиска")
                    raise ValueError(f"Предмет '{item_name}' не найден")
                
                # Здесь должен быть парсинг HTML
                # В реальной реализации используем BeautifulSoup или другую библиотеку
                # Для примера просто вернем пустой список
                search_results = []
            
            if not search_results:
                logger.warning(f"Предмет '{item_name}' не найден")
                raise ValueError(f"Предмет '{item_name}' не найден")
            
            # Находим наиболее похожий предмет
            best_match = None
            best_score = -1
            
            for item in search_results:
                item_name_normalized = item.get('name', '').lower()
                score = self._calculate_similarity(item_name.lower(), item_name_normalized)
                
                if score > best_score:
                    best_score = score
                    best_match = item
            
            if not best_match or best_score < 0.5:
                logger.warning(f"Не найдено подходящего совпадения для '{item_name}'")
                raise ValueError(f"Не найдено подходящего совпадения для '{item_name}'")
            
            # Получаем детальную информацию о выбранном предмете
            item_id = best_match.get('id')
            
            if not item_id:
                logger.warning(f"Не удалось получить ID предмета '{item_name}'")
                raise ValueError(f"Не удалось получить детальную информацию о предмете '{item_name}'")
            
            # Получаем детальную информацию о предмете
            if self.api_key:
                # Используем API если есть ключ
                item_details = await self._make_request(
                    path=f"{self.api_base_url}/items/{item_id}"
                )
                
                if not item_details:
                    logger.warning(f"Не удалось получить детали предмета (ID: {item_id})")
                    raise ValueError(f"Не удалось получить детальную информацию о предмете '{item_name}'")
                
                # Получаем историю цен
                price_history = await self._make_request(
                    path=f"{self.api_base_url}/items/{item_id}/history"
                )
                
                market_data = await self._get_market_data(item_id)
                
                # Объединяем всю информацию
                result = {
                    **best_match,
                    **item_details,
                    'price_history': price_history.get('history', []) if price_history else [],
                    'market_data': market_data
                }
            else:
                # Парсим страницу с деталями предмета
                html = await self._make_request(
                    path=f"/dota2/item/{item_id}"
                )
                
                if not html:
                    logger.warning(f"Не удалось получить HTML-страницу с деталями предмета (ID: {item_id})")
                    raise ValueError(f"Не удалось получить детальную информацию о предмете '{item_name}'")
                
                # Здесь должен быть парсинг HTML
                # В реальной реализации используем BeautifulSoup или другую библиотеку
                # Для примера возвращаем заглушку
                result = {
                    'id': item_id,
                    'name': item_name,
                    'price': 10.0,
                    'rarity': 'rare',
                    'category': 'weapon',
                    'hero': 'juggernaut',
                    'marketable': True,
                    'tradable': True,
                    'price_history': [],
                    'market_data': {
                        'listings': [],
                        'recent_sales': [],
                        'average_price': 10.0
                    }
                }
            
            # Добавляем русские названия
            result['hero_ru'] = self.HEROES.get(result.get('hero', '').lower(), 'Неизвестно')
            result['category_ru'] = self.ITEM_CATEGORIES.get(result.get('category', '').lower(), 'Разное')
            result['rarity_ru'] = self.ITEM_RARITIES.get(result.get('rarity', '').lower(), 'Неизвестно')
            
            logger.info(f"Успешно получена информация о предмете '{item_name}'")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о предмете '{item_name}': {str(e)}")
            raise ValueError(f"Ошибка при получении информации о предмете: {str(e)}")
    
    async def get_hero_items(self, hero: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получает список предметов для конкретного героя Dota 2.
        
        Args:
            hero: Название героя
            limit: Максимальное количество предметов
            
        Returns:
            Список предметов для героя
            
        Raises:
            ValueError: Если герой не найден
        """
        logger.info(f"Получение предметов для героя Dota 2: {hero}")
        
        # Нормализуем название героя
        hero_normalized = hero.lower().replace(' ', '_')
        
        # Проверяем, существует ли такой герой
        if hero_normalized not in self.HEROES and hero not in self.HEROES.values():
            logger.warning(f"Герой '{hero}' не найден")
            raise ValueError(f"Герой '{hero}' не найден")
        
        # Получаем предметы с фильтром по герою
        return await self.get_item_prices(limit=limit, hero=hero_normalized)
    
    async def get_category_items(self, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получает список предметов для конкретной категории.
        
        Args:
            category: Название категории
            limit: Максимальное количество предметов
            
        Returns:
            Список предметов для категории
            
        Raises:
            ValueError: Если категория не найдена
        """
        logger.info(f"Получение предметов для категории: {category}")
        
        # Нормализуем название категории
        category_normalized = category.lower()
        
        # Проверяем, существует ли такая категория
        if category_normalized not in self.ITEM_CATEGORIES and category not in self.ITEM_CATEGORIES.values():
            logger.warning(f"Категория '{category}' не найдена")
            raise ValueError(f"Категория '{category}' не найдена")
        
        # Получаем предметы с фильтром по категории
        return await self.get_item_prices(limit=limit, category=category_normalized)
    
    async def get_market_stats(self) -> Dict[str, Any]:
        """
        Получает общую статистику рынка Dota 2.
        
        Returns:
            Словарь со статистикой рынка
        """
        logger.info("Получение статистики рынка Dota 2")
        
        try:
            if self.api_key:
                # Используем API если есть ключ
                response = await self._make_request(
                    path=f"{self.api_base_url}/stats/dota2"
                )
                
                if not response:
                    logger.warning("Некорректный ответ API при получении статистики")
                    return self._get_default_stats()
                
                return {
                    'total_items': response.get('total_items', 0),
                    'total_listings': response.get('total_listings', 0),
                    'average_price': response.get('average_price', 0.0),
                    'median_price': response.get('median_price', 0.0),
                    'total_value': response.get('total_value', 0.0),
                    'updated_at': datetime.now().isoformat()
                }
            else:
                # Парсим HTML-страницу со статистикой
                html = await self._make_request(path="/stats/dota2")
                
                if not html:
                    logger.warning("Не удалось получить HTML-страницу со статистикой")
                    return self._get_default_stats()
                
                # Здесь должен быть парсинг HTML
                # В реальной реализации используем BeautifulSoup или другую библиотеку
                # Для примера возвращаем заглушку
                return {
                    'total_items': 25000,
                    'total_listings': 150000,
                    'average_price': 8.5,
                    'median_price': 4.25,
                    'total_value': 1275000.0,
                    'updated_at': datetime.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"Ошибка при получении статистики рынка: {str(e)}")
            return self._get_default_stats()
    
    def _get_default_stats(self) -> Dict[str, Any]:
        """
        Возвращает заглушку для статистики рынка в случае ошибки.
        
        Returns:
            Словарь со статистикой по умолчанию
        """
        return {
            'total_items': 0,
            'total_listings': 0,
            'average_price': 0.0,
            'median_price': 0.0,
            'total_value': 0.0,
            'updated_at': datetime.now().isoformat(),
            'error': 'Не удалось получить статистику'
        }
    
    async def _get_market_data(self, item_id: Union[str, int]) -> Dict[str, Any]:
        """
        Получает рыночные данные для конкретного предмета.
        
        Args:
            item_id: ID предмета
            
        Returns:
            Словарь с рыночными данными предмета
        """
        logger.debug(f"Получение рыночных данных для предмета с ID {item_id}")
        
        try:
            if self.api_key:
                # Используем API если есть ключ
                response = await self._make_request(
                    path=f"{self.api_base_url}/items/{item_id}/market"
                )
                
                if not response:
                    logger.warning(f"Некорректный ответ API для предмета {item_id}")
                    return {}
                
                return {
                    'lowest_price': response.get('lowest_price', 0.0),
                    'highest_price': response.get('highest_price', 0.0),
                    'median_price': response.get('median_price', 0.0),
                    'average_price': response.get('average_price', 0.0),
                    'volume': response.get('volume', 0),
                    'listings': response.get('listings', []),
                    'recent_sales': response.get('recent_sales', []),
                    'updated_at': datetime.now().isoformat()
                }
            else:
                # Парсим HTML-страницу с рыночными данными
                html = await self._make_request(
                    path=f"/dota2/item/{item_id}/market"
                )
                
                if not html:
                    logger.warning(f"Не удалось получить HTML-страницу для предмета {item_id}")
                    return {}
                
                # Здесь должен быть парсинг HTML
                # В реальной реализации используем BeautifulSoup или другую библиотеку
                # Для примера возвращаем заглушку
                return {
                    'lowest_price': 9.0,
                    'highest_price': 12.0,
                    'median_price': 10.0,
                    'average_price': 10.5,
                    'volume': 100,
                    'listings': [{'price': 9.0, 'seller': 'user1'}, {'price': 10.0, 'seller': 'user2'}],
                    'recent_sales': [{'price': 9.5, 'date': '2023-05-01'}, {'price': 10.0, 'date': '2023-05-02'}],
                    'updated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении рыночных данных для предмета {item_id}: {str(e)}")
            return {}
    
    def _process_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает сырые данные о предмете, полученные от API или веб-страницы.
        
        Args:
            item_data: Сырые данные о предмете
            
        Returns:
            Обработанный словарь с информацией о предмете
        """
        try:
            # Получаем базовую информацию
            item_id = item_data.get('id', '')
            name = item_data.get('name', '')
            price = item_data.get('price', 0.0)
            
            if not name:
                logger.warning(f"Предмет с ID {item_id} не имеет имени, пропускаем")
                return None
            
            # Получаем категорию и нормализуем её
            category = item_data.get('category', '').lower()
            category_ru = self.ITEM_CATEGORIES.get(category, 'Разное')
            
            # Получаем героя и нормализуем его
            hero = item_data.get('hero', '').lower()
            hero_ru = self.HEROES.get(hero, 'Неизвестно')
            
            # Получаем редкость и нормализуем её
            rarity = item_data.get('rarity', '').lower()
            rarity_ru = self.ITEM_RARITIES.get(rarity, 'Неизвестно')
            
            # Создаем структурированный словарь с информацией о предмете
            processed_item = {
                'id': item_id,
                'name': name,
                'price': float(price),
                'currency': item_data.get('currency', 'USD'),
                'category': category,
                'category_ru': category_ru,
                'hero': hero,
                'hero_ru': hero_ru,
                'rarity': rarity,
                'rarity_ru': rarity_ru,
                'quality': item_data.get('quality', ''),
                'image_url': item_data.get('image_url', ''),
                'steam_url': f"{self.steam_base_url}/{item_id}" if item_id else '',
                'tradable': item_data.get('tradable', False),
                'marketable': item_data.get('marketable', False),
                'commodity': item_data.get('commodity', False),
                'updated_at': datetime.now().isoformat()
            }
            
            # Добавляем дополнительные поля, если они есть
            if 'min_price' in item_data:
                processed_item['min_price'] = float(item_data.get('min_price', 0.0))
            
            if 'max_price' in item_data:
                processed_item['max_price'] = float(item_data.get('max_price', 0.0))
            
            if 'average_price' in item_data:
                processed_item['average_price'] = float(item_data.get('average_price', 0.0))
            
            if 'median_price' in item_data:
                processed_item['median_price'] = float(item_data.get('median_price', 0.0))
            
            if 'volume' in item_data:
                processed_item['volume'] = int(item_data.get('volume', 0))
            
            if 'listings_count' in item_data:
                processed_item['listings_count'] = int(item_data.get('listings_count', 0))
            
            # Проверяем, есть ли информация о странности предмета
            if 'strange' in item_data:
                processed_item['strange'] = bool(item_data.get('strange', False))
            
            # Проверяем, есть ли информация о сокетах (гнездах) предмета
            if 'sockets' in item_data:
                processed_item['sockets'] = item_data.get('sockets', 0)
            
            # Добавляем ярлыки для фильтрации
            processed_item['tags'] = []
            
            if hero:
                processed_item['tags'].append(f"hero:{hero}")
            
            if category:
                processed_item['tags'].append(f"category:{category}")
            
            if rarity:
                processed_item['tags'].append(f"rarity:{rarity}")
            
            # Добавляем информацию о диапазоне цен
            processed_item['price_range'] = self._calculate_price_range(processed_item)
            
            return processed_item
            
        except Exception as e:
            logger.error(f"Ошибка при обработке предмета: {str(e)}")
            return None
    
    def _calculate_price_range(self, item: Dict[str, Any]) -> str:
        """
        Определяет диапазон цен для предмета.
        
        Args:
            item: Обработанный словарь с информацией о предмете
            
        Returns:
            Диапазон цен (Low, Medium, High, Premium)
        """
        price = item.get('price', 0.0)
        
        if price < 1.0:
            return 'Low'
        elif price < 5.0:
            return 'Medium'
        elif price < 20.0:
            return 'High'
        else:
            return 'Premium'
    
    def _calculate_similarity(self, query: str, item_name: str) -> float:
        """
        Рассчитывает степень сходства между запросом и названием предмета.
        
        Args:
            query: Запрос пользователя
            item_name: Название предмета
            
        Returns:
            Степень сходства (0.0 - 1.0)
        """
        # Нормализуем строки
        query = query.lower().strip()
        item_name = item_name.lower().strip()
        
        # Точное совпадение
        if query == item_name:
            return 1.0
        
        # Частичное совпадение
        if query in item_name:
            return 0.9
        
        if item_name in query:
            return 0.8
        
        # Проверка на совпадение слов
        query_words = set(query.split())
        item_words = set(item_name.split())
        
        common_words = query_words.intersection(item_words)
        
        if not common_words:
            return 0.0
        
        # Рассчитываем похожесть на основе общих слов
        similarity = len(common_words) / max(len(query_words), len(item_words))
        
        return similarity 