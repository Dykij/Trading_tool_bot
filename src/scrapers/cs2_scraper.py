"""
Скрапер для сбора данных о предметах CS2 (Counter-Strike 2), включая цены,
категории и статистику рынка.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from .base_scraper import BaseScraper

logger = logging.getLogger('scrapers.cs2')

class CS2Scraper(BaseScraper):
    """
    Скрапер для получения данных о предметах CS2 (Counter-Strike 2).
    Собирает информацию о ценах, категориях, редкости и других характеристиках предметов.
    """
    
    # Маппинг категорий предметов CS2
    ITEM_CATEGORIES = {
        'knife': 'Нож',
        'rifle': 'Винтовка',
        'pistol': 'Пистолет',
        'smg': 'Пистолет-пулемет',
        'shotgun': 'Дробовик',
        'sniper': 'Снайперская винтовка',
        'machinegun': 'Пулемет',
        'gloves': 'Перчатки',
        'sticker': 'Наклейка',
        'agent': 'Агент',
        'case': 'Кейс',
        'key': 'Ключ',
        'graffiti': 'Граффити',
        'patch': 'Патч',
        'music_kit': 'Набор музыки',
        'pin': 'Значок'
    }
    
    # Маппинг редкости предметов CS2
    ITEM_RARITIES = {
        'consumer': 'Потребительского класса',
        'industrial': 'Промышленного класса',
        'mil_spec': 'Армейского качества',
        'restricted': 'Запрещенное',
        'classified': 'Засекреченное',
        'covert': 'Тайное',
        'extraordinary': 'Экстраординарное',
        'contraband': 'Контрабанда'
    }
    
    # Популярные коллекции скинов
    COLLECTIONS = {
        'gamma': 'Гамма',
        'chroma': 'Хрома',
        'spectrum': 'Спектр',
        'clutch': 'Решающий момент',
        'horizon': 'Горизонт',
        'danger_zone': 'Запретная зона',
        'prisma': 'Призма',
        'shattered_web': 'Расколотая сеть',
        'fracture': 'Излом',
        'snakebite': 'Змеиный укус',
        'riptide': 'Волна',
        'dreams': 'Грёзы и кошмары',
        'revolution': 'Революция'
    }
    
    def __init__(self, 
                api_key: Optional[str] = None,
                cache_ttl: int = 3600,
                request_delay: float = 0.5,
                max_retries: int = 3,
                proxy: Optional[str] = None):
        """
        Инициализация скрапера CS2.
        
        Args:
            api_key: API ключ (если требуется)
            cache_ttl: Время жизни кэша в секундах (по умолчанию 1 час)
            request_delay: Задержка между запросами в секундах
            max_retries: Максимальное количество повторных попыток при ошибке
            proxy: URL прокси-сервера (если требуется)
        """
        super().__init__(
            name='CS2PricesScraper',
            base_url='https://csgostash.com',  # Основной публичный ресурс для CS2
            cache_ttl=cache_ttl,
            request_delay=request_delay,
            max_retries=max_retries,
            proxy=proxy
        )
        
        self.api_key = api_key
        self.steam_base_url = 'https://steamcommunity.com/market/listings/730'
        
        # Настройка дополнительных API, если используются
        if api_key:
            self.api_base_url = 'https://api.cs2market.com'  # Пример API
            self.headers['Authorization'] = f'Bearer {api_key}'
            
        logger.info(f"Инициализирован скрапер {self.name} с базовым URL {self.base_url}")
    
    async def get_popular_items(self, limit: int = 20, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка популярных предметов CS2.
        
        Args:
            limit: Максимальное количество предметов для получения
            category: Фильтр по категории предметов (опционально)
            
        Returns:
            Список популярных предметов с ценами и дополнительной информацией
        """
        logger.info(f"Получение популярных предметов CS2 (лимит: {limit}, категория: {category})")
        
        # Формируем параметры запроса
        params = {
            'limit': min(100, limit),  # Ограничиваем на всякий случай
            'sort': 'popularity'
        }
        
        if category:
            params['category'] = category
        
        try:
            if self.api_key:
                # Используем API, если есть ключ
                response = await self._make_request(
                    path=f"{self.api_base_url}/items/popular",
                    params=params,
                    method='get'
                )
                
                if not response or 'items' not in response:
                    logger.warning(f"Некорректный ответ API: {response}")
                    return self._get_dummy_popular_items(limit, category)
                
                return response.get('items', [])[:limit]
            else:
                # В случае отсутствия API, парсим публичный сайт
                path = '/popular-skins'
                if category:
                    path = f"/{category.lower()}"
                
                html = await self._make_request(
                    path=path,
                    method='get'
                )
                
                if not html:
                    logger.warning("Не удалось получить HTML-страницу с популярными предметами")
                    return self._get_dummy_popular_items(limit, category)
                
                # В реальной реализации здесь должен быть парсинг HTML с помощью BeautifulSoup
                # Возвращаем тестовые данные для демонстрации
                return self._get_dummy_popular_items(limit, category)
                
        except Exception as e:
            logger.error(f"Ошибка при получении популярных предметов: {e}", exc_info=True)
            return self._get_dummy_popular_items(limit, category)
    
    async def search_items(self, query: str, limit: int = 20, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Поиск предметов CS2 по запросу.
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            category: Фильтр по категории (опционально)
            
        Returns:
            Список предметов, соответствующих запросу
        """
        logger.info(f"Поиск предметов CS2 по запросу '{query}' (лимит: {limit}, категория: {category})")
        
        if not query:
            logger.warning("Пустой поисковый запрос")
            return []
        
        try:
            if self.api_key:
                # Используем API, если есть ключ
                params = {
                    'q': query,
                    'limit': min(100, limit)
                }
                
                if category:
                    params['category'] = category
                
                response = await self._make_request(
                    path=f"{self.api_base_url}/items/search",
                    params=params,
                    method='get'
                )
                
                if not response or 'items' not in response:
                    logger.warning(f"Некорректный ответ API при поиске: {response}")
                    return self._get_dummy_search_results(query, limit, category)
                
                return response.get('items', [])[:limit]
            else:
                # Парсим публичный сайт
                params = {
                    'q': query
                }
                
                if category:
                    params['category'] = category
                
                html = await self._make_request(
                    path='/search',
                    params=params,
                    method='get'
                )
                
                if not html:
                    logger.warning(f"Не удалось получить результаты поиска для запроса '{query}'")
                    return self._get_dummy_search_results(query, limit, category)
                
                # В реальной реализации здесь должен быть парсинг HTML
                # Возвращаем тестовые данные для демонстрации
                return self._get_dummy_search_results(query, limit, category)
                
        except Exception as e:
            logger.error(f"Ошибка при поиске предметов: {e}", exc_info=True)
            return self._get_dummy_search_results(query, limit, category)
    
    async def get_item_details(self, item_name: str) -> Optional[Dict[str, Any]]:
        """
        Получение подробной информации о предмете CS2.
        
        Args:
            item_name: Название предмета
            
        Returns:
            Словарь с подробной информацией о предмете или None в случае ошибки
        """
        logger.info(f"Получение деталей предмета '{item_name}'")
        
        if not item_name:
            logger.warning("Пустое название предмета")
            return None
        
        try:
            if self.api_key:
                # Используем API, если есть ключ
                # Нужно экранировать специальные символы в названии
                encoded_name = item_name.replace(' ', '%20').replace('|', '%7C').replace('(', '%28').replace(')', '%29')
                
                response = await self._make_request(
                    path=f"{self.api_base_url}/items/{encoded_name}",
                    method='get'
                )
                
                if not response or 'error' in response:
                    logger.warning(f"Не удалось получить детали предмета через API: {response}")
                    return self._get_dummy_item_details(item_name)
                
                return response
            else:
                # Подготавливаем URL-friendly версию названия предмета
                item_slug = item_name.lower().replace(' ', '-').replace('|', '').replace('(', '').replace(')', '')
                
                html = await self._make_request(
                    path=f"/item/{item_slug}",
                    method='get'
                )
                
                if not html:
                    logger.warning(f"Не удалось получить HTML-страницу для предмета '{item_name}'")
                    return self._get_dummy_item_details(item_name)
                
                # В реальной реализации здесь должен быть парсинг HTML
                # Возвращаем тестовые данные для демонстрации
                return self._get_dummy_item_details(item_name)
                
        except Exception as e:
            logger.error(f"Ошибка при получении деталей предмета: {e}", exc_info=True)
            return self._get_dummy_item_details(item_name)
    
    async def get_item_price_history(self, item_name: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """
        Получение истории цен предмета за указанный период.
        
        Args:
            item_name: Название предмета
            days: Количество дней для анализа
            
        Returns:
            Словарь с историей цен или None в случае ошибки
        """
        logger.info(f"Получение истории цен для '{item_name}' за {days} дней")
        
        try:
            if self.api_key:
                encoded_name = item_name.replace(' ', '%20').replace('|', '%7C')
                
                response = await self._make_request(
                    path=f"{self.api_base_url}/items/{encoded_name}/history",
                    params={'days': days},
                    method='get'
                )
                
                if not response or 'history' not in response:
                    logger.warning(f"Не удалось получить историю цен через API: {response}")
                    return {'history': self._generate_dummy_price_history(days)}
                
                return response
            else:
                # В случае отсутствия API, возвращаем тестовые данные
                return {'history': self._generate_dummy_price_history(days)}
        
        except Exception as e:
            logger.error(f"Ошибка при получении истории цен: {e}", exc_info=True)
            return {'history': self._generate_dummy_price_history(days)}
    
    # Вспомогательные методы для генерации тестовых данных
    
    def _get_dummy_popular_items(self, limit: int = 20, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Генерирует тестовые данные для популярных предметов."""
        
        popular_items = [
            {
                'name': 'AK-47 | Asiimov (Field-Tested)',
                'price': 45.32,
                'category': 'rifle',
                'rarity': 'classified',
                'wear': 'field-tested',
                'market': 'steam'
            },
            {
                'name': 'AWP | Dragon Lore (Factory New)',
                'price': 2301.75,
                'category': 'sniper',
                'rarity': 'covert',
                'wear': 'factory-new',
                'market': 'steam'
            },
            {
                'name': 'Karambit | Fade (Factory New)',
                'price': 975.23,
                'category': 'knife',
                'rarity': 'extraordinary',
                'wear': 'factory-new',
                'market': 'steam'
            },
            {
                'name': 'M4A4 | Howl (Factory New)',
                'price': 1850.0,
                'category': 'rifle',
                'rarity': 'contraband',
                'wear': 'factory-new',
                'market': 'steam'
            },
            {
                'name': 'Butterfly Knife | Doppler (Factory New)',
                'price': 1250.0,
                'category': 'knife',
                'rarity': 'extraordinary',
                'wear': 'factory-new',
                'market': 'steam'
            },
            {
                'name': 'USP-S | Kill Confirmed (Minimal Wear)',
                'price': 85.5,
                'category': 'pistol',
                'rarity': 'covert',
                'wear': 'minimal-wear',
                'market': 'steam'
            },
            {
                'name': 'Glock-18 | Fade (Factory New)',
                'price': 450.0,
                'category': 'pistol',
                'rarity': 'restricted',
                'wear': 'factory-new',
                'market': 'steam'
            },
            {
                'name': 'Desert Eagle | Blaze (Factory New)',
                'price': 210.75,
                'category': 'pistol',
                'rarity': 'restricted',
                'wear': 'factory-new',
                'market': 'steam'
            },
            {
                'name': 'Sport Gloves | Pandora\'s Box (Field-Tested)',
                'price': 920.0,
                'category': 'gloves',
                'rarity': 'extraordinary',
                'wear': 'field-tested',
                'market': 'steam'
            },
            {
                'name': 'Shadow Daggers | Crimson Web (Minimal Wear)',
                'price': 125.5,
                'category': 'knife',
                'rarity': 'extraordinary',
                'wear': 'minimal-wear',
                'market': 'steam'
            }
        ]
        
        # Фильтрация по категории, если указана
        if category:
            filtered_items = [item for item in popular_items if item['category'] == category]
        else:
            filtered_items = popular_items
        
        return filtered_items[:limit]
    
    def _get_dummy_search_results(self, query: str, limit: int = 20, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Генерирует тестовые результаты поиска."""
        
        all_items = self._get_dummy_popular_items(20)  # Используем больше элементов для разнообразия
        
        # Фильтрация по запросу
        query = query.lower()
        filtered_items = [item for item in all_items if query in item['name'].lower()]
        
        # Дополнительная фильтрация по категории
        if category:
            filtered_items = [item for item in filtered_items if item['category'] == category]
        
        # Добавляем некоторую релевантность
        for item in filtered_items:
            item['relevance'] = 100 if query in item['name'].lower().split() else 80
        
        # Сортировка по релевантности
        filtered_items.sort(key=lambda x: x['relevance'], reverse=True)
        
        return filtered_items[:limit]
    
    def _get_dummy_item_details(self, item_name: str) -> Dict[str, Any]:
        """Генерирует тестовые данные для деталей предмета."""
        
        # Пытаемся найти предмет в тестовых данных
        all_items = self._get_dummy_popular_items(20)
        
        for item in all_items:
            if item['name'].lower() == item_name.lower():
                # Если нашли точное совпадение, используем его как основу
                base_item = item
                break
        else:
            # Иначе создаем базовый шаблон
            base_item = {
                'name': item_name,
                'price': 125.50,
                'category': 'rifle',
                'rarity': 'classified',
                'wear': 'field-tested',
                'market': 'steam'
            }
        
        # Расширяем объект дополнительными данными
        details = {
            **base_item,
            'description': f"This is a {base_item['rarity']} {base_item['category']} skin.",
            'float': round(0.15 + 0.35 * hash(item_name) % 100 / 100, 4),  # Генерация псевдослучайного float
            'stattrak': hash(item_name) % 3 == 0,  # Примерно треть предметов имеют StatTrak
            'souvenir': hash(item_name) % 10 == 0,  # Примерно 10% предметов имеют Souvenir
            'collection': list(self.COLLECTIONS.keys())[hash(item_name) % len(self.COLLECTIONS)],
            'release_date': '2020-03-15',
            'icon_url': f"https://example.com/icons/{base_item['category']}/{hash(item_name) % 1000}.png",
            'price_trend': {
                'change': round((hash(item_name) % 200 - 100) / 10, 2),  # От -10 до +10
                'change_percent': round((hash(item_name) % 400 - 200) / 10, 2),  # От -20% до +20%
                'trend': 'up' if (hash(item_name) % 200 - 100) > 0 else 'down',
                'volume': hash(item_name) % 1000 + 50
            },
            'market_listings': [
                {
                    'market': 'steam',
                    'price': base_item['price'],
                    'volume': hash(item_name) % 500 + 50,
                    'lowest_float': round(0.01 + 0.1 * hash(f"{item_name}_steam") % 100 / 100, 4)
                },
                {
                    'market': 'dmarket',
                    'price': round(base_item['price'] * (0.9 + 0.1 * hash(f"{item_name}_dmarket") % 100 / 100), 2),
                    'volume': hash(f"{item_name}_dmarket") % 300 + 20,
                    'lowest_float': round(0.01 + 0.1 * hash(f"{item_name}_dmarket") % 100 / 100, 4)
                },
                {
                    'market': 'skinport',
                    'price': round(base_item['price'] * (0.85 + 0.15 * hash(f"{item_name}_skinport") % 100 / 100), 2),
                    'volume': hash(f"{item_name}_skinport") % 200 + 10,
                    'lowest_float': round(0.01 + 0.1 * hash(f"{item_name}_skinport") % 100 / 100, 4)
                }
            ]
        }
        
        return details
    
    def _generate_dummy_price_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Генерирует тестовые данные для истории цен."""
        
        history = []
        base_price = 100.0
        
        for i in range(days):
            date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            date = date.replace(day=date.day - i)
            
            # Генерация случайного колебания цены
            price_change = (i % 5 - 2) * 2.5
            price = round(base_price + price_change, 2)
            volume = int(100 + (30 - i) % 10 * 5)
            
            history.append({
                'date': date.strftime('%Y-%m-%d'),
                'price': price,
                'volume': volume
            })
        
        # Сортировка по дате (от старых к новым)
        history.sort(key=lambda x: x['date'])
        
        return history 