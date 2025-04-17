"""
Базовый класс для всех скраперов, предоставляющий общую функциональность.
"""

import logging
import aiohttp
import asyncio
import time
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta

logger = logging.getLogger('scrapers.base')

class BaseScraper:
    """
    Базовый класс для всех скраперов.
    Предоставляет общие методы для выполнения HTTP-запросов, кэширования и обработки ошибок.
    """
    
    def __init__(self,
                name: str,
                base_url: str,
                cache_ttl: int = 3600,
                request_delay: float = 0.5,
                max_retries: int = 3,
                proxy: Optional[str] = None,
                headers: Optional[Dict[str, str]] = None):
        """
        Инициализирует базовый скрапер.
        
        Args:
            name: Имя скрапера для идентификации
            base_url: Базовый URL для API или сайта
            cache_ttl: Время жизни кэша в секундах (по умолчанию 1 час)
            request_delay: Минимальная задержка между запросами в секундах
            max_retries: Максимальное количество повторных попыток при ошибке
            proxy: URL прокси-сервера (если требуется)
            headers: Заголовки HTTP-запросов
        """
        self.name = name
        self.base_url = base_url
        self.cache_ttl = cache_ttl
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.proxy = proxy
        
        # Устанавливаем заголовки по умолчанию, если не предоставлены
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Кэш для результатов запросов
        self._cache = {}
        self._last_request_time = 0
        
        logger.info(f"Инициализирован базовый скрапер {self.name} с URL {self.base_url}")
    
    async def _make_request(self, path: str, method: str = 'GET', params: Optional[Dict[str, Any]] = None, 
                          data: Optional[Any] = None, headers: Optional[Dict[str, str]] = None,
                          use_cache: bool = True) -> Any:
        """
        Выполняет HTTP-запрос к API или веб-сайту.
        
        Args:
            path: Путь для запроса (будет добавлен к base_url)
            method: HTTP-метод (GET, POST и т.д.)
            params: Параметры запроса
            data: Данные для отправки в теле запроса
            headers: Дополнительные заголовки для запроса
            use_cache: Использовать ли кэширование
            
        Returns:
            Результат запроса (обычно JSON или HTML)
            
        Raises:
            Exception: В случае ошибки запроса
        """
        url = f"{self.base_url}{path}" if not path.startswith('http') else path
        cache_key = f"{method}:{url}:{str(params)}:{str(data)}"
        
        # Проверка кэша
        if use_cache and cache_key in self._cache:
            cache_item = self._cache[cache_key]
            if datetime.now() < cache_item['expires']:
                logger.debug(f"Данные получены из кэша для {url}")
                return cache_item['data']
        
        # Задержка между запросами
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        
        # Объединяем заголовки
        request_headers = {**self.headers}
        if headers:
            request_headers.update(headers)
        
        # Выполняем запрос с повторными попытками
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    logger.debug(f"Выполняется {method} запрос к {url}")
                    
                    proxy = self.proxy
                    
                    async with session.request(
                        method=method,
                        url=url,
                        params=params,
                        json=data if isinstance(data, dict) else None,
                        data=data if not isinstance(data, dict) else None,
                        headers=request_headers,
                        proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        self._last_request_time = time.time()
                        
                        if response.status >= 400:
                            logger.warning(f"Ошибка запроса {url}: {response.status}")
                            if retry_count < self.max_retries:
                                retry_count += 1
                                await asyncio.sleep(retry_count * 2)  # Экспоненциальная задержка
                                continue
                            return None
                        
                        # Определяем тип ответа
                        content_type = response.headers.get('Content-Type', '')
                        
                        if 'application/json' in content_type:
                            result = await response.json()
                        else:
                            result = await response.text()
                        
                        # Кэшируем результат
                        if use_cache:
                            self._cache[cache_key] = {
                                'data': result,
                                'expires': datetime.now() + timedelta(seconds=self.cache_ttl)
                            }
                        
                        return result
                        
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе {url}: {str(e)}")
                if retry_count < self.max_retries:
                    retry_count += 1
                    await asyncio.sleep(retry_count * 2)
                else:
                    logger.error(f"Превышено максимальное количество попыток для {url}")
                    return None
            except Exception as e:
                logger.error(f"Необработанная ошибка при запросе {url}: {str(e)}")
                return None
    
    def clear_cache(self, pattern: Optional[str] = None):
        """
        Очищает кэш скрапера.
        
        Args:
            pattern: Если указан, очищает только ключи, содержащие pattern
        """
        if pattern:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"Очищено {len(keys_to_remove)} записей кэша по шаблону '{pattern}'")
        else:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Очищено {count} записей кэша")
    
    def set_proxy(self, proxy: Optional[str]):
        """
        Устанавливает или сбрасывает прокси для запросов.
        
        Args:
            proxy: URL прокси-сервера или None для отключения
        """
        self.proxy = proxy
        logger.info(f"Установлен прокси {proxy if proxy else 'отключен'} для скрапера {self.name}")
    
    def set_request_delay(self, delay: float):
        """
        Устанавливает задержку между запросами.
        
        Args:
            delay: Задержка в секундах
        """
        self.request_delay = max(0.1, delay)  # Минимальная задержка 0.1 секунды
        logger.info(f"Установлена задержка {self.request_delay} сек для скрапера {self.name}")
    
    async def test_connection(self) -> bool:
        """
        Проверяет соединение с сервером.
        
        Returns:
            True, если соединение успешно, иначе False
        """
        try:
            result = await self._make_request("/", use_cache=False)
            return result is not None
        except Exception as e:
            logger.error(f"Ошибка при проверке соединения с {self.base_url}: {str(e)}")
            return False
    
    def __str__(self) -> str:
        """
        Строковое представление скрапера.
        
        Returns:
            Строка с информацией о скрапере
        """
        return f"{self.name} Scraper ({self.base_url})" 