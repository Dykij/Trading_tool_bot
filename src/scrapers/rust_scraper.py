"""
Скрапер для сайта rustmarket.site, который собирает информацию о скинах Rust.
Поддерживает получение цен, категорий, коллекций и редкости предметов.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union

from .base_scraper import BaseScraper

logger = logging.getLogger('scrapers.rust')

class RustMarketScraper(BaseScraper):
    """
    Скрапер для сайта rustmarket.site.
    Позволяет получать информацию о ценах и деталях скинов Rust.
    """
    
    # Маппинг категорий предметов на русские названия
    ITEM_CATEGORIES = {
        'weapon': 'Оружие',
        'clothing': 'Одежда',
        'misc': 'Разное',
        'tool': 'Инструменты',
        'resource': 'Ресурсы',
        'ammunition': 'Боеприпасы',
        'construction': 'Строительство',
        'component': 'Компоненты',
        'armor': 'Броня',
        'trap': 'Ловушки',
        'decoration': 'Декорации'
    }
    
    # Маппинг редкости предметов на русские названия
    ITEM_RARITIES = {
        'common': 'Обычный',
        'uncommon': 'Необычный',
        'rare': 'Редкий',
        'epic': 'Эпический',
        'legendary': 'Легендарный',
        'mythical': 'Мифический'
    }
    
    def __init__(self, 
                api_key: Optional[str] = None,
                cache_ttl: int = 3600,
                request_delay: float = 0.5,
                max_retries: int = 3,
                proxy: Optional[str] = None):
        """
        Инициализация скрапера RustMarket.
        
        Args:
            api_key: API ключ для доступа к API сайта (если требуется)
            cache_ttl: Время жизни кэша в секундах (по умолчанию 1 час)
            request_delay: Задержка между запросами в секундах
            max_retries: Максимальное количество повторных попыток при ошибке
            proxy: URL прокси-сервера (если требуется)
        """
        super().__init__(
            name='RustMarket',
            base_url='https://rustmarket.site',
            cache_ttl=cache_ttl,
            request_delay=request_delay,
            max_retries=max_retries,
            proxy=proxy
        )
        
        self.api_key = api_key
        
        # API URL
        self.api_url = 'https://api.rustmarket.site'
        
        # Заголовки для API запросов
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'
        
        logger.info(f"Инициализирован скрапер RustMarket с базовым URL {self.base_url}")
    
    async def get_item_prices(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получает список предметов Rust с ценами.
        
        Args:
            limit: Максимальное количество предметов (по умолчанию 100)
            
        Returns:
            Список предметов с ценами и дополнительной информацией
        """
        logger.info(f"Получение списка цен предметов Rust (лимит: {limit})")
        
        items = []
        page = 1
        per_page = min(100, limit)  # API ограничивает выдачу 100 предметами на страницу
        
        while len(items) < limit:
            try:
                logger.debug(f"Запрос страницы {page} (по {per_page} предметов)")
                
                # Запрос к API или парсинг страницы
                if self.api_key:
                    # Используем API если есть ключ
                    response = await self._make_request(
                        path=f"{self.api_url}/v1/items",
                        params={'page': page, 'per_page': per_page}
                    )
                    
                    if not response or 'items' not in response:
                        logger.warning(f"Некорректный ответ API: {response}")
                        break
                    
                    page_items = response['items']
                else:
                    # Парсим страницу, если нет API ключа
                    html = await self._make_request(
                        path=f"/market/rust?page={page}&limit={per_page}"
                    )
                    
                    if not html:
                        logger.warning("Не удалось получить HTML-страницу")
                        break
                    
                    # Здесь должен быть парсинг HTML с помощью BeautifulSoup
                    # Но для примера просто вернем пустой список
                    page_items = []
                
                if not page_items:
                    logger.info(f"Страница {page} не содержит предметов, завершаем")
                    break
                
                # Обрабатываем каждый предмет
                for item_data in page_items:
                    item = self._process_item(item_data)
                    if item:
                        items.append(item)
                        
                        if len(items) >= limit:
                            break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Ошибка при получении списка предметов: {str(e)}")
                break
        
        logger.info(f"Получено {len(items)} предметов Rust")
        return items[:limit]
    
    async def get_item_details(self, item_name: str) -> Dict[str, Any]:
        """
        Получает детальную информацию о конкретном предмете Rust.
        
        Args:
            item_name: Название предмета
            
        Returns:
            Словарь с детальной информацией о предмете
            
        Raises:
            ValueError: Если предмет не найден
        """
        logger.info(f"Получение информации о предмете: {item_name}")
        
        # Сначала ищем предмет по имени
        try:
            # Запрос к API или парсинг страницы поиска
            if self.api_key:
                # Используем API если есть ключ
                response = await self._make_request(
                    path=f"{self.api_url}/v1/search",
                    params={'query': item_name, 'limit': 10}
                )
                
                if not response or 'items' not in response:
                    logger.warning(f"Некорректный ответ API при поиске: {response}")
                    raise ValueError(f"Предмет '{item_name}' не найден")
                
                items = response['items']
            else:
                # Парсим страницу, если нет API ключа
                html = await self._make_request(
                    path=f"/market/rust/search?query={item_name}"
                )
                
                if not html:
                    logger.warning("Не удалось получить HTML-страницу поиска")
                    raise ValueError(f"Предмет '{item_name}' не найден")
                
                # Здесь должен быть парсинг HTML с помощью BeautifulSoup
                # Но для примера просто вернем пустой список
                items = []
            
            if not items:
                logger.warning(f"Предмет '{item_name}' не найден")
                raise ValueError(f"Предмет '{item_name}' не найден")
            
            # Находим наиболее похожий предмет
            best_match = None
            best_score = -1
            
            for item in items:
                item_name_normalized = item.get('name', '').lower()
                score = self._calculate_similarity(item_name.lower(), item_name_normalized)
                
                if score > best_score:
                    best_score = score
                    best_match = item
            
            if best_match:
                # Получаем детальную информацию о выбранном предмете
                item_id = best_match.get('id')
                if not item_id:
                    logger.warning(f"Не удалось получить ID предмета '{item_name}'")
                    raise ValueError(f"Предмет '{item_name}' не найден")
                
                item_details = await self._get_item_market_data(item_id)
                
                if not item_details:
                    logger.warning(f"Не удалось получить детали предмета '{item_name}'")
                    raise ValueError(f"Детали предмета '{item_name}' не найдены")
                
                # Объединяем данные из поиска и детальной информации
                result = {**best_match, **item_details}
                
                logger.info(f"Успешно получена информация о предмете '{item_name}'")
                return result
            else:
                logger.warning(f"Подходящий предмет для '{item_name}' не найден")
                raise ValueError(f"Предмет '{item_name}' не найден")
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о предмете '{item_name}': {str(e)}")
            raise ValueError(f"Ошибка при получении информации о предмете: {str(e)}")
    
    async def get_market_stats(self) -> Dict[str, Any]:
        """
        Получает общую статистику рынка Rust.
        
        Returns:
            Словарь со статистикой рынка
        """
        logger.info("Получение статистики рынка Rust")
        
        try:
            # Запрос к API или парсинг страницы статистики
            if self.api_key:
                # Используем API если есть ключ
                response = await self._make_request(
                    path=f"{self.api_url}/v1/stats"
                )
                
                if not response:
                    logger.warning("Некорректный ответ API при получении статистики")
                    return {
                        'total_items': 0,
                        'total_sales': 0,
                        'active_listings': 0,
                        'avg_price': 0.0,
                        'market_volume': 0.0
                    }
                
                return {
                    'total_items': response.get('total_items', 0),
                    'total_sales': response.get('total_sales', 0),
                    'active_listings': response.get('active_listings', 0),
                    'avg_price': response.get('avg_price', 0.0),
                    'market_volume': response.get('market_volume', 0.0),
                    'updated_at': datetime.now().isoformat()
                }
            else:
                # Парсим страницу, если нет API ключа
                html = await self._make_request(path="/stats")
                
                if not html:
                    logger.warning("Не удалось получить HTML-страницу статистики")
                    return {
                        'total_items': 0,
                        'total_sales': 0,
                        'active_listings': 0,
                        'avg_price': 0.0,
                        'market_volume': 0.0
                    }
                
                # Здесь должен быть парсинг HTML с помощью BeautifulSoup
                # Но для примера просто вернем заглушку
                return {
                    'total_items': 10000,
                    'total_sales': 50000,
                    'active_listings': 25000,
                    'avg_price': 12.5,
                    'market_volume': 625000.0,
                    'updated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики рынка: {str(e)}")
            return {
                'total_items': 0,
                'total_sales': 0,
                'active_listings': 0,
                'avg_price': 0.0,
                'market_volume': 0.0,
                'error': str(e)
            }
    
    async def _get_item_market_data(self, item_id: Union[str, int]) -> Dict[str, Any]:
        """
        Получает рыночные данные для конкретного предмета.
        
        Args:
            item_id: ID предмета
            
        Returns:
            Словарь с рыночными данными предмета
        """
        logger.debug(f"Получение рыночных данных для предмета с ID {item_id}")
        
        try:
            # Запрос к API или парсинг страницы
            if self.api_key:
                # Используем API если есть ключ
                response = await self._make_request(
                    path=f"{self.api_url}/v1/items/{item_id}/market"
                )
                
                if not response:
                    logger.warning(f"Некорректный ответ API для предмета {item_id}")
                    return {}
                
                # Обработка данных о цене и истории
                price_history = response.get('price_history', [])
                current_listings = response.get('listings', [])
                recent_sales = response.get('sales', [])
                
                return {
                    'current_price': response.get('current_price', 0.0),
                    'min_price': response.get('min_price', 0.0),
                    'max_price': response.get('max_price', 0.0),
                    'avg_price': response.get('avg_price', 0.0),
                    'price_history': price_history,
                    'current_listings': current_listings,
                    'recent_sales': recent_sales,
                    'volatility': response.get('volatility', 0.0),
                    'updated_at': datetime.now().isoformat()
                }
            else:
                # Парсим страницу, если нет API ключа
                html = await self._make_request(
                    path=f"/market/rust/item/{item_id}"
                )
                
                if not html:
                    logger.warning(f"Не удалось получить HTML-страницу для предмета {item_id}")
                    return {}
                
                # Здесь должен быть парсинг HTML с помощью BeautifulSoup
                # Но для примера просто вернем заглушку
                return {
                    'current_price': 15.0,
                    'min_price': 10.0,
                    'max_price': 20.0,
                    'avg_price': 15.0,
                    'price_history': [{'date': '2023-05-01', 'price': 14.0}, {'date': '2023-05-02', 'price': 15.0}],
                    'current_listings': [{'price': 15.0, 'seller': 'user1'}, {'price': 16.0, 'seller': 'user2'}],
                    'recent_sales': [{'price': 14.5, 'date': '2023-05-01'}, {'price': 15.0, 'date': '2023-05-02'}],
                    'volatility': 0.1,
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
            
            # Обрабатываем категорию
            category = item_data.get('category', '').lower()
            category_ru = self.ITEM_CATEGORIES.get(category, 'Другое')
            
            # Обрабатываем редкость
            rarity = item_data.get('rarity', '').lower()
            rarity_ru = self.ITEM_RARITIES.get(rarity, 'Неизвестно')
            
            # Создаем структурированный словарь
            processed_item = {
                'id': item_id,
                'name': name,
                'name_en': item_data.get('name_en', name),  # Английское название, если доступно
                'price': float(price),
                'currency': item_data.get('currency', 'USD'),
                'category': category,
                'category_ru': category_ru,
                'rarity': rarity,
                'rarity_ru': rarity_ru,
                'collection': item_data.get('collection', ''),
                'image_url': item_data.get('image_url', ''),
                'description': item_data.get('description', ''),
                'can_trade': item_data.get('can_trade', False),
                'can_market': item_data.get('can_market', False),
                'marketable': item_data.get('marketable', False),
                'tradable': item_data.get('tradable', False),
                'updated_at': datetime.now().isoformat()
            }
            
            # Добавляем дополнительные поля, если они есть
            if 'min_price' in item_data:
                processed_item['min_price'] = float(item_data.get('min_price', 0))
            
            if 'max_price' in item_data:
                processed_item['max_price'] = float(item_data.get('max_price', 0))
            
            if 'avg_price' in item_data:
                processed_item['avg_price'] = float(item_data.get('avg_price', 0))
            
            if 'volume' in item_data:
                processed_item['volume'] = int(item_data.get('volume', 0))
            
            # Добавляем собственные поля для удобства использования
            processed_item['collection_type'] = self._extract_collection_type(name, item_data.get('collection', ''))
            processed_item['price_range'] = self._calculate_price_range(processed_item)
            processed_item['popularity'] = self._calculate_popularity(item_data)
            
            return processed_item
            
        except Exception as e:
            logger.error(f"Ошибка при обработке предмета: {str(e)}")
            return None
    
    def _extract_collection_type(self, name: str, collection: str) -> str:
        """
        Извлекает тип коллекции из названия предмета или указанной коллекции.
        
        Args:
            name: Название предмета
            collection: Название коллекции (если доступно)
            
        Returns:
            Тип коллекции
        """
        if collection:
            return collection
        
        # Извлекаем коллекцию из названия
        collections = {
            'OG': ['OG', 'Original'],
            'Glowing': ['Glowing', 'Glow'],
            'Neon': ['Neon'],
            'Army': ['Army', 'Military', 'Camo'],
            'Digital': ['Digital', 'Digit'],
            'Urban': ['Urban'],
            'Snow': ['Snow', 'Winter'],
            'Desert': ['Desert', 'Sand'],
            'Forest': ['Forest', 'Wood'],
            'Night': ['Night', 'Dark'],
        }
        
        for collection_name, keywords in collections.items():
            for keyword in keywords:
                if keyword.lower() in name.lower():
                    return collection_name
        
        return 'Unknown'
    
    def _calculate_price_range(self, item: Dict[str, Any]) -> str:
        """
        Определяет диапазон цен для предмета.
        
        Args:
            item: Обработанный словарь с информацией о предмете
            
        Returns:
            Диапазон цен (Low, Medium, High, Premium)
        """
        price = item.get('price', 0)
        
        # Пороговые значения для диапазонов
        if price < 1:
            return 'Low'
        elif price < 5:
            return 'Medium'
        elif price < 20:
            return 'High'
        else:
            return 'Premium'
    
    def _calculate_popularity(self, item_data: Dict[str, Any]) -> int:
        """
        Рассчитывает популярность предмета по объему продаж и количеству листингов.
        
        Args:
            item_data: Сырые данные о предмете
            
        Returns:
            Оценка популярности (1-10)
        """
        volume = int(item_data.get('volume', 0))
        listings = int(item_data.get('listings_count', 0))
        
        # Простая формула для оценки популярности
        popularity = min(10, max(1, (volume + listings // 2) // 10))
        
        return popularity
    
    def _calculate_similarity(self, query: str, item_name: str) -> float:
        """
        Рассчитывает степень сходства между запросом и названием предмета.
        
        Args:
            query: Запрос пользователя
            item_name: Название предмета
            
        Returns:
            Степень сходства (0.0 - 1.0)
        """
        # Наивная реализация, на практике лучше использовать алгоритмы вроде Левенштейна или TF-IDF
        
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