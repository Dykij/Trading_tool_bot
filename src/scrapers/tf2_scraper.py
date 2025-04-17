"""
Модуль для скрапинга данных о предметах Team Fortress 2 с Backpack.tf.
Предоставляет информацию о ценах на предметы TF2, включая необычные эффекты и качество предметов.
"""

import logging
import re
import json
from typing import Dict, List, Any, Optional, Union

from src.scrapers.base_scraper import BaseScraper

logger = logging.getLogger('scrapers.tf2')

class BackpackTFScraper(BaseScraper):
    """
    Скрапер для получения данных о предметах Team Fortress 2 с Backpack.tf.
    Извлекает информацию о ценах на предметы, редкие эффекты и качество.
    """
    
    def __init__(self, 
                api_key: Optional[str] = None, 
                cache_ttl: int = 3600,
                request_delay: float = 1.0,
                max_retries: int = 3,
                proxy: Optional[str] = None):
        """
        Инициализирует скрапер Backpack.tf.
        
        Args:
            api_key: API ключ Backpack.tf (если нужен доступ к API)
            cache_ttl: Время жизни кэша в секундах (по умолчанию 1 час)
            request_delay: Минимальная задержка между запросами в секундах
            max_retries: Максимальное количество повторных попыток при ошибке
            proxy: URL прокси-сервера (если требуется)
        """
        super().__init__(
            name="BackpackTF",
            base_url="https://backpack.tf",
            cache_ttl=cache_ttl,
            request_delay=request_delay,
            max_retries=max_retries,
            proxy=proxy,
            headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Referer': 'https://backpack.tf/prices',
                'X-Requested-With': 'XMLHttpRequest'
            }
        )
        
        self.api_key = api_key
        self.api_base_url = "https://api.backpack.tf/api"
        
        # Маппинг качества предметов
        self.quality_map = {
            0: "Normal",
            1: "Genuine",
            3: "Vintage",
            5: "Unusual",
            6: "Unique",
            7: "Community",
            8: "Valve",
            9: "Self-Made",
            11: "Strange",
            13: "Haunted",
            14: "Collector's",
            15: "Decorated"
        }
        
        # Маппинг редкости предметов
        self.rarity_map = {
            0: "Stock",
            1: "Common",
            2: "Uncommon",
            3: "Rare",
            4: "Mythical",
            5: "Legendary",
            6: "Ancient"
        }
        
        logger.info(f"Инициализирован скрапер {self.name}")
    
    async def get_item_prices(self, game: str = 'tf2', limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Получает список предметов TF2 с ценами.
        
        Args:
            game: Идентификатор игры (поддерживается только 'tf2')
            limit: Максимальное количество предметов
            
        Returns:
            Список предметов с ценами
            
        Raises:
            ValueError: Если игра не поддерживается
        """
        if game.lower() != 'tf2':
            raise ValueError("Backpack.tf поддерживает только предметы TF2")
        
        items = []
        try:
            if self.api_key:
                # Получаем данные через API, если есть ключ
                items = await self._get_prices_from_api(limit)
            else:
                # Используем парсинг сайта, если ключа нет
                items = await self._get_prices_from_web(limit)
            
            logger.info(f"Получено {len(items)} предметов из Backpack.tf")
            return items
            
        except Exception as e:
            logger.error(f"Ошибка при получении цен с Backpack.tf: {str(e)}")
            return []
    
    async def get_item_details(self, game: str, item_name: str) -> Dict[str, Any]:
        """
        Получает детальную информацию о конкретном предмете TF2.
        
        Args:
            game: Идентификатор игры (поддерживается только 'tf2')
            item_name: Название предмета
            
        Returns:
            Словарь с детальной информацией о предмете
            
        Raises:
            ValueError: Если игра не поддерживается
            KeyError: Если предмет не найден
        """
        if game.lower() != 'tf2':
            raise ValueError("Backpack.tf поддерживает только предметы TF2")
        
        try:
            # Ищем предмет на странице поиска
            url = "/search"
            params = {
                'text': item_name,
                'page': 1
            }
            
            search_page = await self._make_request(url, params=params, parse_json=False)
            
            # Извлекаем URL предмета из результатов поиска
            item_url = self._extract_item_url(search_page, item_name)
            
            if not item_url:
                raise KeyError(f"Предмет '{item_name}' не найден на Backpack.tf")
            
            # Получаем страницу предмета
            item_page = await self._make_request(item_url, parse_json=False)
            
            # Извлекаем информацию о предмете
            item_data = self._extract_item_details(item_page)
            
            if not item_data:
                raise KeyError(f"Не удалось извлечь информацию о предмете '{item_name}'")
            
            # Получаем ценовые данные с API или страницы цен
            price_data = await self._get_item_price_data(item_name, item_data)
            
            # Объединяем данные предмета с ценами
            result = {**item_data, 'prices': price_data}
            
            logger.info(f"Получены детальные данные для предмета '{item_name}'")
            return result
            
        except KeyError as e:
            logger.error(f"Предмет не найден: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении информации о предмете '{item_name}': {str(e)}")
            raise
    
    async def _get_prices_from_api(self, limit: int) -> List[Dict[str, Any]]:
        """
        Получает цены предметов через API Backpack.tf.
        
        Args:
            limit: Максимальное количество предметов
            
        Returns:
            Список предметов с ценами
        """
        url = f"{self.api_base_url}/prices/v4/all"
        
        params = {
            'key': self.api_key,
            'appid': 440,  # AppID для TF2
            'limit': limit
        }
        
        response = await self._make_request(url, params=params)
        
        items = []
        if not response or 'response' not in response:
            logger.error("Не удалось получить данные через API Backpack.tf")
            return items
        
        # Обрабатываем данные из API
        raw_items = response.get('response', {}).get('items', {})
        
        for item_name, item_data in raw_items.items():
            qualities = item_data.get('prices', {})
            
            for quality_id, quality_data in qualities.items():
                tradable = quality_data.get('Tradable', {})
                craftable = tradable.get('Craftable', {})
                
                for priceindex, price_data in craftable.items():
                    try:
                        processed_item = {
                            'name': item_name,
                            'quality': self.quality_map.get(int(quality_id), "Unknown"),
                            'price_index': priceindex,
                            'tradable': True,
                            'craftable': True,
                            'last_update': price_data.get('last_update'),
                            'currency': price_data.get('currency'),
                            'price': price_data.get('value')
                        }
                        
                        # Добавляем информацию о необычном эффекте, если он есть
                        if quality_id == '5' and priceindex != '0':
                            processed_item['unusual_effect'] = self._get_unusual_effect(priceindex)
                        
                        items.append(processed_item)
                        
                        if len(items) >= limit:
                            return items
                    
                    except Exception as e:
                        logger.error(f"Ошибка при обработке предмета {item_name}: {str(e)}")
        
        return items
    
    async def _get_prices_from_web(self, limit: int) -> List[Dict[str, Any]]:
        """
        Получает цены предметов через парсинг веб-страницы Backpack.tf.
        
        Args:
            limit: Максимальное количество предметов
            
        Returns:
            Список предметов с ценами
        """
        url = "/prices"
        
        items = []
        page = 1
        
        while len(items) < limit:
            try:
                params = {'page': page}
                response = await self._make_request(url, params=params, parse_json=False)
                
                # Извлекаем данные из HTML-страницы
                page_items = self._extract_items_from_html(response)
                
                if not page_items:
                    break
                
                items.extend(page_items)
                
                if len(page_items) < 50:  # Обычно 50 предметов на странице
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Ошибка при получении страницы {page} с Backpack.tf: {str(e)}")
                break
        
        # Ограничиваем количество предметов до запрошенного лимита
        return items[:limit]
    
    def _extract_items_from_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Извлекает информацию о предметах из HTML-страницы.
        
        Args:
            html_content: HTML-содержимое страницы
            
        Returns:
            Список предметов с извлеченной информацией
        """
        items = []
        
        try:
            # Ищем скрипт с JSON-данными предметов
            match = re.search(r'var pricelist = (\{.*?\}});', html_content, re.DOTALL)
            if not match:
                logger.warning("Не удалось найти данные о ценах на странице")
                return items
            
            # Парсим JSON
            price_json = match.group(1)
            price_data = json.loads(price_json)
            
            # Извлекаем данные о предметах
            for item_id, item_data in price_data.items():
                try:
                    if 'prices' not in item_data:
                        continue
                    
                    name = item_data.get('name', '')
                    
                    # Обрабатываем каждый вариант предмета (по качеству и т.д.)
                    for quality_id, quality_variants in item_data.get('prices', {}).items():
                        for tradable_status, tradable_variants in quality_variants.items():
                            for craftable_status, craftable_variants in tradable_variants.items():
                                for price_index, price_info in craftable_variants.items():
                                    try:
                                        # Получаем цену
                                        price_value = 0
                                        price_currency = 'metal'
                                        
                                        if 'value' in price_info:
                                            price_value = price_info.get('value', 0)
                                            price_currency = price_info.get('currency', 'metal')
                                        elif 'value_raw' in price_info:
                                            price_raw = price_info.get('value_raw', {})
                                            price_value = price_raw.get('value', 0)
                                            price_currency = price_raw.get('currency', 'metal')
                                        
                                        processed_item = {
                                            'name': name,
                                            'quality': self.quality_map.get(int(quality_id), "Unknown"),
                                            'tradable': tradable_status == 'Tradable',
                                            'craftable': craftable_status == 'Craftable',
                                            'price_index': price_index,
                                            'price': price_value,
                                            'currency': price_currency,
                                            'last_update': price_info.get('last_update', '')
                                        }
                                        
                                        # Добавляем информацию о необычном эффекте
                                        if quality_id == '5' and price_index != '0':
                                            processed_item['unusual_effect'] = self._get_unusual_effect(price_index)
                                        
                                        items.append(processed_item)
                                    
                                    except Exception as e:
                                        logger.error(f"Ошибка при обработке варианта предмета {name}: {str(e)}")
                
                except Exception as e:
                    logger.error(f"Ошибка при обработке предмета ID {item_id}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении данных из HTML: {str(e)}")
        
        return items
    
    def _extract_item_url(self, html_content: str, item_name: str) -> str:
        """
        Извлекает URL предмета из страницы результатов поиска.
        
        Args:
            html_content: HTML-содержимое страницы поиска
            item_name: Название искомого предмета
            
        Returns:
            URL страницы предмета или пустая строка, если предмет не найден
        """
        try:
            # Ищем ссылки на предметы
            item_links = re.findall(r'<a href="(/item/[^"]+)"[^>]*>([^<]+)</a>', html_content)
            
            # Нормализуем имя искомого предмета
            normalized_search = self.normalize_item_name(item_name)
            
            # Ищем наиболее подходящий предмет
            best_match = None
            best_score = 0
            
            for link, name in item_links:
                normalized_name = self.normalize_item_name(name)
                
                # Точное совпадение
                if normalized_name == normalized_search:
                    return link
                
                # Частичное совпадение (содержит искомое название)
                if normalized_search in normalized_name:
                    score = len(normalized_search) / len(normalized_name)
                    if score > best_score:
                        best_score = score
                        best_match = link
            
            # Возвращаем лучшее совпадение или пустую строку
            return best_match or ""
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении URL предмета: {str(e)}")
            return ""
    
    def _extract_item_details(self, html_content: str) -> Dict[str, Any]:
        """
        Извлекает детальную информацию о предмете из HTML-страницы.
        
        Args:
            html_content: HTML-содержимое страницы предмета
            
        Returns:
            Словарь с информацией о предмете
        """
        item_data = {}
        
        try:
            # Извлекаем имя предмета
            name_match = re.search(r'<h1 class="item-header">([^<]+)</h1>', html_content)
            if name_match:
                item_data['name'] = name_match.group(1).strip()
            
            # Извлекаем изображение
            image_match = re.search(r'<meta property="og:image" content="([^"]+)"', html_content)
            if image_match:
                item_data['image_url'] = image_match.group(1)
            
            # Извлекаем данные о качестве
            quality_match = re.search(r'<div class="item-quality[^"]*">([^<]+)</div>', html_content)
            if quality_match:
                item_data['quality'] = quality_match.group(1).strip()
            
            # Извлекаем данные о типе предмета
            type_match = re.search(r'<div class="card-title">Item Details</div>.*?<div class="card-content">.*?Type: ([^<]+)<', html_content, re.DOTALL)
            if type_match:
                item_data['type'] = type_match.group(1).strip()
            
            # Извлекаем особый эффект (если есть)
            effect_match = re.search(r'<span class="unusual-effect"[^>]*>([^<]+)</span>', html_content)
            if effect_match:
                item_data['unusual_effect'] = effect_match.group(1).strip()
            
            # Извлекаем информацию о возможности обмена
            tradable_match = re.search(r'Tradable: ([^<]+)<', html_content)
            if tradable_match:
                item_data['tradable'] = tradable_match.group(1).strip() == 'Yes'
            
            # Извлекаем информацию о возможности крафта
            craftable_match = re.search(r'Craftable: ([^<]+)<', html_content)
            if craftable_match:
                item_data['craftable'] = craftable_match.group(1).strip() == 'Yes'
            
            # Извлекаем дополнительные атрибуты
            attributes = re.findall(r'<div class="attribute">([^<]+)</div>', html_content)
            if attributes:
                item_data['attributes'] = [attr.strip() for attr in attributes]
            
            return item_data
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении данных о предмете: {str(e)}")
            return item_data
    
    async def _get_item_price_data(self, item_name: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Получает ценовые данные для предмета.
        
        Args:
            item_name: Название предмета
            item_data: Информация о предмете
            
        Returns:
            Словарь с ценовыми данными
        """
        price_data = {}
        
        try:
            quality = item_data.get('quality', '')
            effect = item_data.get('unusual_effect', '')
            
            # Подготавливаем параметры запроса
            search_params = {
                'name': item_name,
                'quality': quality
            }
            
            if effect:
                search_params['effect'] = effect
            
            if self.api_key:
                # Получаем цены через API
                url = f"{self.api_base_url}/prices/items/440"
                params = {
                    'key': self.api_key,
                    'item': item_name,
                    'quality': self._get_quality_id(quality),
                    'tradable': 1,
                    'craftable': item_data.get('craftable', True) and 1 or 0
                }
                
                if effect:
                    params['priceindex'] = self._get_effect_id(effect)
                
                api_data = await self._make_request(url, params=params)
                
                if api_data and 'response' in api_data:
                    response = api_data['response']
                    
                    for item_info in response.get('items', []):
                        price_data = {
                            'value': item_info.get('value'),
                            'currency': item_info.get('currency', 'metal'),
                            'last_update': item_info.get('last_update'),
                            'difference': item_info.get('difference')
                        }
            else:
                # Получаем цены через парсинг веб-страницы
                url = "/classifieds/search"
                params = {
                    'item': item_name,
                    'quality': quality,
                    'tradable': 1,
                    'craftable': item_data.get('craftable', True) and 1 or 0
                }
                
                if effect:
                    params['unusual': effect]
                
                page = await self._make_request(url, params=params, parse_json=False)
                
                # Извлекаем данные о ценах из страницы
                price_data = self._extract_price_from_listings(page)
            
            return price_data
            
        except Exception as e:
            logger.error(f"Ошибка при получении ценовых данных для {item_name}: {str(e)}")
            return price_data
    
    def _extract_price_from_listings(self, html_content: str) -> Dict[str, Any]:
        """
        Извлекает информацию о ценах из страницы листингов.
        
        Args:
            html_content: HTML-содержимое страницы листингов
            
        Returns:
            Словарь с ценовыми данными
        """
        price_data = {
            'buy': {
                'min': None,
                'max': None,
                'average': None,
                'listings': 0
            },
            'sell': {
                'min': None,
                'max': None,
                'average': None,
                'listings': 0
            }
        }
        
        try:
            # Извлекаем данные о ценах из скрипта с JSON
            json_match = re.search(r'var enums = (.*?);', html_content, re.DOTALL)
            if not json_match:
                return price_data
            
            # Извлекаем листинги покупки
            buy_listings = re.findall(r'<div class="listing buy">(.*?)</div>\s*</div>', html_content, re.DOTALL)
            buy_prices = []
            
            for listing in buy_listings:
                price_match = re.search(r'data-listing_price="([^"]+)"', listing)
                if price_match:
                    price = self.parse_price(price_match.group(1))
                    if price:
                        buy_prices.append(price)
            
            # Извлекаем листинги продажи
            sell_listings = re.findall(r'<div class="listing sell">(.*?)</div>\s*</div>', html_content, re.DOTALL)
            sell_prices = []
            
            for listing in sell_listings:
                price_match = re.search(r'data-listing_price="([^"]+)"', listing)
                if price_match:
                    price = self.parse_price(price_match.group(1))
                    if price:
                        sell_prices.append(price)
            
            # Обрабатываем цены покупки
            if buy_prices:
                price_data['buy']['min'] = min(buy_prices)
                price_data['buy']['max'] = max(buy_prices)
                price_data['buy']['average'] = sum(buy_prices) / len(buy_prices)
                price_data['buy']['listings'] = len(buy_prices)
            
            # Обрабатываем цены продажи
            if sell_prices:
                price_data['sell']['min'] = min(sell_prices)
                price_data['sell']['max'] = max(sell_prices)
                price_data['sell']['average'] = sum(sell_prices) / len(sell_prices)
                price_data['sell']['listings'] = len(sell_prices)
            
            return price_data
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении цен из листингов: {str(e)}")
            return price_data
    
    def _get_unusual_effect(self, effect_id: str) -> str:
        """
        Возвращает название необычного эффекта по его ID.
        
        Args:
            effect_id: ID эффекта
            
        Returns:
            Название эффекта или "Unknown"
        """
        # Маппинг ID эффектов к их названиям
        effect_map = {
            '1': 'Burning Flames',
            '2': 'Purple Confetti',
            '3': 'Green Confetti',
            '4': 'Haunted Ghosts',
            '5': 'Green Energy',
            '6': 'Purple Energy',
            '7': 'Circling TF Logo',
            '8': 'Massed Flies',
            '9': 'Scorching Flames',
            '10': 'Searing Plasma',
            '11': 'Vivid Plasma',
            '12': 'Sunbeams',
            '13': 'Circling Peace Sign',
            '14': 'Circling Heart',
            # Можно добавить остальные эффекты
        }
        
        return effect_map.get(effect_id, f"Effect #{effect_id}")
    
    def _get_quality_id(self, quality_name: str) -> int:
        """
        Возвращает ID качества по его названию.
        
        Args:
            quality_name: Название качества
            
        Returns:
            ID качества или 6 (Unique) по умолчанию
        """
        quality_map_reversed = {v.lower(): k for k, v in self.quality_map.items()}
        return quality_map_reversed.get(quality_name.lower(), 6)
    
    def _get_effect_id(self, effect_name: str) -> str:
        """
        Возвращает ID эффекта по его названию.
        
        Args:
            effect_name: Название эффекта
            
        Returns:
            ID эффекта или "0" по умолчанию
        """
        effect_map_reversed = {
            'burning flames': '1',
            'purple confetti': '2',
            'green confetti': '3',
            'haunted ghosts': '4',
            'green energy': '5',
            'purple energy': '6',
            'circling tf logo': '7',
            'massed flies': '8',
            'scorching flames': '9',
            'searing plasma': '10',
            'vivid plasma': '11',
            'sunbeams': '12',
            'circling peace sign': '13',
            'circling heart': '14',
            # Можно добавить остальные эффекты
        }
        
        return effect_map_reversed.get(effect_name.lower(), "0") 