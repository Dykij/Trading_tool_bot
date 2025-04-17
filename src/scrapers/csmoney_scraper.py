"""
Модуль для скрапинга данных с CS.Money Wiki.
Позволяет получать информацию о ценах на скины CS:GO, включая редкие паттерны и наклейки.
"""

import logging
import re
from typing import Dict, List, Any, Optional

from src.scrapers.base_scraper import BaseScraper

logger = logging.getLogger('scrapers.csmoney')

class CSMoneyWikiScraper(BaseScraper):
    """
    Скрапер для CS.Money Wiki API.
    Извлекает информацию о ценах на скины CS:GO, включая редкие паттерны, наклейки и износ.
    """
    
    def __init__(self, 
                 cache_ttl: int = 3600,
                 request_delay: float = 0.5,
                 max_retries: int = 3,
                 proxy: Optional[str] = None):
        """
        Инициализирует скрапер CS.Money Wiki.
        
        Args:
            cache_ttl: Время жизни кэша в секундах (по умолчанию 1 час)
            request_delay: Минимальная задержка между запросами в секундах
            max_retries: Максимальное количество повторных попыток при ошибке
            proxy: URL прокси-сервера (если требуется)
        """
        super().__init__(
            name="CSMoneyWiki",
            base_url="https://wiki.cs.money/api/v2",
            cache_ttl=cache_ttl,
            request_delay=request_delay,
            max_retries=max_retries,
            proxy=proxy,
            headers={
                'Accept': 'application/json',
                'Referer': 'https://wiki.cs.money/'
            }
        )
        
        # Маппинг категорий для запросов
        self.categories = {
            'knife': 'knife',
            'gloves': 'gloves',
            'pistol': 'pistols',
            'rifle': 'rifles',
            'sniper': 'snipers',
            'smg': 'smgs',
            'shotgun': 'shotguns',
            'machinegun': 'machineguns',
            'container': 'containers',
            'sticker': 'stickers',
            'agent': 'agents',
            'graffiti': 'graffiti',
            'musickit': 'music_kits',
            'pin': 'pins',
            'patch': 'patches',
            'collectible': 'collectibles'
        }
        
        logger.info(f"Инициализирован скрапер {self.name}")
    
    async def get_item_prices(self, game: str = 'csgo', limit: int = 500) -> List[Dict[str, Any]]:
        """
        Получает список предметов CS:GO с ценами.
        
        Args:
            game: Идентификатор игры (поддерживается только 'csgo')
            limit: Максимальное количество предметов (не более 500)
            
        Returns:
            Список предметов с ценами
            
        Raises:
            ValueError: Если игра не поддерживается
        """
        if game.lower() != 'csgo':
            raise ValueError("CSMoneyWiki поддерживает только скины CS:GO")
        
        # Ограничиваем количество предметов до 500 (ограничение API)
        if limit > 500:
            logger.warning(f"Ограничение количества предметов изменено с {limit} до 500 (ограничение API)")
            limit = 500
        
        items = []
        
        # Получаем предметы для каждой категории
        for category_name, category_id in self.categories.items():
            try:
                logger.info(f"Получение предметов категории {category_name} из CS.Money Wiki")
                
                # Запрашиваем данные по категории
                url = f"/items/category/{category_id}"
                params = {
                    'limit': min(limit, 100),  # API ограничивает 100 предметов на запрос
                    'offset': 0
                }
                
                result = await self._make_request(url, params=params)
                category_items = result.get('items', [])
                
                # Получаем детали для каждого предмета
                for item in category_items:
                    try:
                        item_data = await self._get_item_market_data(item.get('id'))
                        
                        # Объединяем базовую информацию с рыночными данными
                        processed_item = self._process_item(item, item_data)
                        items.append(processed_item)
                        
                        # Если достигли лимита, прекращаем сбор
                        if len(items) >= limit:
                            logger.info(f"Достигнут лимит в {limit} предметов")
                            return items
                        
                    except Exception as e:
                        logger.error(f"Ошибка при обработке предмета {item.get('name')}: {str(e)}")
            
            except Exception as e:
                logger.error(f"Ошибка при получении предметов категории {category_name}: {str(e)}")
        
        logger.info(f"Всего получено {len(items)} предметов из CS.Money Wiki")
        return items
    
    async def get_item_details(self, game: str, item_name: str) -> Dict[str, Any]:
        """
        Получает детальную информацию о конкретном предмете CS:GO.
        
        Args:
            game: Идентификатор игры (поддерживается только 'csgo')
            item_name: Название предмета
            
        Returns:
            Словарь с детальной информацией о предмете
            
        Raises:
            ValueError: Если игра не поддерживается
            KeyError: Если предмет не найден
        """
        if game.lower() != 'csgo':
            raise ValueError("CSMoneyWiki поддерживает только скины CS:GO")
        
        # Подготавливаем название предмета для URL
        item_name_url = self._prepare_item_name_for_url(item_name)
        
        try:
            # Сначала ищем предмет по названию
            url = "/items/search"
            params = {
                'name': item_name,
                'limit': 10
            }
            
            search_results = await self._make_request(url, params=params)
            items = search_results.get('items', [])
            
            if not items:
                raise KeyError(f"Предмет '{item_name}' не найден в CS.Money Wiki")
            
            # Ищем точное соответствие или наиболее близкое
            exact_match = None
            for item in items:
                if self.normalize_item_name(item.get('name', '')) == self.normalize_item_name(item_name):
                    exact_match = item
                    break
            
            # Если точного соответствия нет, берем первый результат
            item_data = exact_match or items[0]
            item_id = item_data.get('id')
            
            # Получаем рыночные данные
            market_data = await self._get_item_market_data(item_id)
            
            # Объединяем информацию
            result = self._process_item(item_data, market_data)
            
            # Получаем дополнительные данные о паттернах (если есть)
            if 'pattern' in item_name.lower() or 'fade' in item_name.lower():
                pattern_data = await self._get_item_patterns(item_id)
                if pattern_data:
                    result['patterns'] = pattern_data
            
            logger.info(f"Получены детальные данные для предмета '{item_name}'")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о предмете '{item_name}': {str(e)}")
            raise
    
    async def _get_item_market_data(self, item_id: int) -> Dict[str, Any]:
        """
        Получает рыночные данные для предмета по его ID.
        
        Args:
            item_id: ID предмета в CS.Money Wiki
            
        Returns:
            Словарь с рыночными данными
        """
        url = f"/items/{item_id}/trading-data"
        try:
            result = await self._make_request(url)
            
            # Извлекаем данные о продажах и ценах
            sales_data = result.get('sales', {})
            market_prices = result.get('marketPrices', {})
            
            # Нормализуем данные
            return {
                'steam_price': market_prices.get('steam', {}).get('price'),
                'steam_volume': market_prices.get('steam', {}).get('volume'),
                'csmoney_price': result.get('price'),
                'average_price': sales_data.get('averagePrice'),
                'sales_volume': sales_data.get('totalSales'),
                'price_trend': sales_data.get('priceTrend'),
                'marketplaces': {
                    name: data.get('price')
                    for name, data in market_prices.items()
                }
            }
        
        except Exception as e:
            logger.warning(f"Не удалось получить рыночные данные для предмета ID {item_id}: {str(e)}")
            return {}
    
    async def _get_item_patterns(self, item_id: int) -> List[Dict[str, Any]]:
        """
        Получает информацию о паттернах предмета.
        
        Args:
            item_id: ID предмета в CS.Money Wiki
            
        Returns:
            Список паттернов с ценами и редкостью
        """
        url = f"/items/{item_id}/patterns"
        try:
            result = await self._make_request(url)
            patterns = result.get('patterns', [])
            
            return [{
                'pattern_id': pattern.get('patternId'),
                'name': pattern.get('name'),
                'rarity': pattern.get('rarity'),
                'price_multiplier': pattern.get('priceMultiplier'),
                'image_url': pattern.get('imageUrl')
            } for pattern in patterns]
            
        except Exception as e:
            logger.warning(f"Не удалось получить информацию о паттернах для предмета ID {item_id}: {str(e)}")
            return []
    
    def _process_item(self, item: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает и объединяет данные о предмете.
        
        Args:
            item: Базовая информация о предмете
            market_data: Рыночные данные
            
        Returns:
            Объединенный словарь с информацией о предмете
        """
        result = {
            'id': item.get('id'),
            'name': item.get('name', ''),
            'market_name': item.get('market_name', item.get('name', '')),
            'category': item.get('category', {}).get('name', ''),
            'type': item.get('type', {}).get('name', ''),
            'collection': item.get('collection', {}).get('name', ''),
            'rarity': item.get('rarity', {}).get('name', ''),
            'quality': item.get('quality', ''),
            'exterior': item.get('exterior', {}).get('name', ''),
            'image_url': item.get('imageUrl', ''),
            'prices': {
                'steam': market_data.get('steam_price', 0),
                'csmoney': market_data.get('csmoney_price', 0),
                'average': market_data.get('average_price', 0),
                'marketplaces': market_data.get('marketplaces', {})
            },
            'volume': market_data.get('sales_volume', 0),
            'trend': market_data.get('price_trend', 0)
        }
        
        # Добавляем информацию о наклейках (если есть)
        if 'stickers' in item:
            result['stickers'] = [{
                'name': sticker.get('name', ''),
                'price': sticker.get('price', 0),
                'rarity': sticker.get('rarity', {}).get('name', ''),
                'image_url': sticker.get('imageUrl', '')
            } for sticker in item.get('stickers', [])]
        
        # Добавляем информацию о паттерне (если есть)
        if 'pattern' in item:
            result['pattern'] = {
                'id': item.get('pattern', {}).get('patternId'),
                'name': item.get('pattern', {}).get('name', ''),
                'rarity': item.get('pattern', {}).get('rarity', ''),
                'price_multiplier': item.get('pattern', {}).get('priceMultiplier', 1.0)
            }
        
        # Добавляем информацию о плавании (float)
        if 'float' in item:
            result['float'] = item.get('float')
        
        return result
    
    def _prepare_item_name_for_url(self, item_name: str) -> str:
        """
        Подготавливает название предмета для использования в URL.
        
        Args:
            item_name: Исходное название предмета
            
        Returns:
            Подготовленное для URL название
        """
        # Нормализуем название
        name = self.normalize_item_name(item_name)
        
        # Заменяем пробелы на дефисы
        name = name.replace(' ', '-')
        
        # Удаляем все символы, кроме букв, цифр и дефисов
        name = re.sub(r'[^a-z0-9-]', '', name)
        
        # Обрабатываем специальные случаи
        name = name.replace('stattrak', 'st')
        name = name.replace('factory-new', 'fn')
        name = name.replace('minimal-wear', 'mw')
        name = name.replace('field-tested', 'ft')
        name = name.replace('well-worn', 'ww')
        name = name.replace('battle-scarred', 'bs')
        
        return name 