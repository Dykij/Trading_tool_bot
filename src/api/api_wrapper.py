"""
Модуль для взаимодействия с API DMarket.

Этот модуль предоставляет обертку над API DMarket, обеспечивая простой
и надежный способ взаимодействия с платформой. Поддерживает
как синхронные, так и асинхронные операции.

Документация API: https://docs.dmarket.com
"""

from typing import Dict, Any, Optional, Union, cast, List, TypedDict, Literal, Iterable, Tuple
import logging
import time
import hashlib
import hmac
import json
from datetime import datetime
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
import aiohttp
from aiohttp import ClientSession, ClientError, ClientConnectionError, ClientTimeout
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncio
from itertools import islice

from config import config
from schemas.schemas import ItemPrice
from utils.api_retry import APIRetryManager, retry_async, retry_sync, retry_batch_async


class PriceInfo(TypedDict):
    """Информация о цене в API."""
    amount: str
    currency: str


class APIError(Exception):
    """
    Базовый класс для исключений API DMarket.
    
    Базовый класс исключений для работы с API DMarket, от которого 
    наследуются все специализированные исключения. Содержит информацию
    о сообщении ошибки, HTTP-статусе и теле ответа.
    
    Attributes:
        message (str): Сообщение об ошибке
        status_code (Optional[int]): HTTP-статус код ответа (если доступен)
        response (Optional[str]): Тело ответа от API (если доступно)
    """
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None, 
        response: Optional[str] = None
    ):
        """
        Инициализирует исключение APIError.
        
        Args:
            message: Сообщение, описывающее ошибку
            status_code: HTTP-статус код ответа (опционально)
            response: Тело ответа от API (опционально)
        """
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(f"{message} (status={status_code}): {response}")


class AuthenticationError(APIError):
    """
    Ошибка аутентификации в API DMarket.
    
    Возникает при проблемах с авторизацией: неверные API-ключи,
    истекший токен, отсутствие или некорректная подпись запроса.
    
    Обычно соответствует HTTP-статусам 401 Unauthorized или 403 Forbidden.
    """


class RateLimitError(APIError):
    """
    Ошибка превышения лимита запросов к API DMarket.
    
    Возникает при превышении количества разрешенных запросов в единицу времени.
    Обычно соответствует HTTP-статусу 429 Too Many Requests.
    
    Note:
        При получении этой ошибки рекомендуется сделать паузу и повторить
        запрос позже с экспоненциальной задержкой.
    """


class NetworkError(APIError):
    """
    Ошибка сети при взаимодействии с API DMarket.
    
    Возникает при проблемах с сетевым соединением: таймаут, обрыв соединения,
    невозможность установить соединение с сервером API и т.п.
    
    Note:
        При получении этой ошибки рекомендуется проверить интернет-соединение
        и повторить запрос с механизмом автоматических повторных попыток.
    """


class ValidationError(APIError):
    """
    Ошибка валидации данных при отправке запроса к API DMarket.
    
    Возникает при отправке некорректных данных: неверный формат, недопустимые
    значения параметров, отсутствие обязательных полей и т.п.
    
    Обычно соответствует HTTP-статусу 400 Bad Request или 422 Unprocessable Entity.
    
    Note:
        При получении этой ошибки необходимо проверить и исправить формат
        и содержимое отправляемых данных.
    """


class DMarketAPI:
    """
    Класс для взаимодействия с API DMarket.

    Документация API DMarket: https://docs.dmarket.com
    
    Примеры:
        >>> # Синхронное использование
        >>> api = DMarketAPI(api_key="your_key", api_secret="your_secret")
        >>> items = api.get_market_items(limit=10)
        >>> 
        >>> # Асинхронное использование
        >>> async def fetch_data():
        ...     items = await api.get_market_items_async(limit=10)
        ...     return items
    """

    def __init__(
        self,
        api_key: str,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        max_concurrent_requests: int = 5  # Добавляем лимит на параллельные запросы
    ) -> None:
        """
        Инициализация клиента DMarket API.
        
        Args:
            api_key: API-ключ для авторизации запросов к DMarket
            api_secret: API-секрет для подписи запросов (опционально)
            base_url: Базовый URL API (опционально)
            timeout: Таймаут для запросов в секундах
            max_retries: Максимальное количество повторных попыток при сбоях
            max_concurrent_requests: Максимальное количество одновременных запросов
        """
        self.base_url = base_url or "https://api.dmarket.com"
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "User-Agent": "DMarketTradingBot/1.0"
        }
        self.logger = logging.getLogger("DMarketAPI")
        
        # Добавляем семафор для ограничения количества одновременных запросов
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # Добавляем отслеживание времени последнего запроса для ограничения частоты
        self.last_request_time = time.time()
        self.min_request_interval = 0.1  # Минимальный интервал между запросами в секундах

        # Проверим API-ключ на валидность формата
        if not api_key or len(api_key) < 10:
            self.logger.warning("API-ключ слишком короткий или отсутствует")

    def _generate_signature(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Генерирует подпись для запроса к API DMarket.
        
        Создает HMAC SHA-256 подпись для авторизации запросов к API DMarket
        согласно требованиям документации. Подпись формируется на основе HTTP-метода, 
        конечной точки, данных запроса и текущей временной метки.
        
        Алгоритм генерации подписи:
        1. Формируется строка `METHOD + ENDPOINT + [JSON_DATA] + TIMESTAMP`
        2. Вычисляется HMAC-SHA256 хеш этой строки с использованием API-секрета как ключа
        3. Результат возвращается вместе с временной меткой в виде HTTP-заголовков

        Args:
            method: HTTP-метод запроса (GET, POST и т.д.)
            endpoint: Конечная точка API (путь без базового URL)
            data: Словарь с данными для отправки (опционально)

        Returns:
            Словарь с HTTP-заголовками для авторизации:
                - X-Sign-Date: Временная метка (UNIX timestamp)
                - X-Request-Sign: HMAC SHA-256 подпись запроса
                
        Note:
            Если API-секрет не задан, возвращает пустой словарь.
            Метод используется внутри класса и не предназначен для прямого вызова.
        """
        if not self.api_secret:
            return {}

        # Создаем текущую временную метку (UNIX timestamp)
        timestamp = str(int(time.time()))
        
        # Формируем строку для подписи согласно документации DMarket
        string_to_sign = f"{method.upper()}{endpoint}"

        # Добавляем данные запроса, если они есть
        if data:
            string_to_sign += json.dumps(data, separators=(',', ':'))

        # Добавляем временную метку
        string_to_sign += timestamp

        # Создаем HMAC SHA-256 подпись
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Возвращаем заголовки для авторизации
        return {
            "X-Sign-Date": timestamp,
            "X-Request-Sign": signature
        }

    def _get_auth_headers(self, method: str, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Получает заголовки для аутентификации запроса.
        
        Args:
            method: HTTP метод (GET, POST, и т.д.)
            url: Полный URL запроса
            params: Параметры запроса
            
        Returns:
            Словарь с заголовками для аутентификации
        """
        # Получаем endpoint из полного URL
        endpoint = url.replace(self.base_url, "")
        
        # Копируем базовые заголовки
        headers = self.headers.copy()
        
        # Добавляем подпись, если есть API-секрет
        if self.api_secret:
            # Для GET-запросов данные передаются через params
            data = None
            if method.upper() == "GET" and params:
                data = params
                
            signature_headers = self._generate_signature(method, endpoint, data)
            headers.update(signature_headers)
            
        return headers

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((RequestException, RateLimitError, NetworkError))
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет HTTP-запрос к API DMarket.
        
        Args:
            method: HTTP-метод (GET, POST, PUT, DELETE)
            endpoint: Конечная точка API (без базового URL)
            data: Данные для отправки в теле запроса (опционально)
            
        Returns:
            Словарь с данными ответа от API
            
        Raises:
            AuthenticationError: При ошибках авторизации (401, 403)
            ValidationError: При ошибках валидации данных (400, 422)
            RateLimitError: При превышении лимита запросов (429)
            NetworkError: При проблемах с сетью или таймаутах
            APIError: При других ошибках API
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.headers.copy()
        
        # Добавляем заголовки авторизации
        auth_headers = self._get_auth_headers(method, endpoint, data)
        if auth_headers:
            headers.update(auth_headers)
            
        json_data = json.dumps(data) if data else None
        
        self.logger.debug(f"Sending {method} request to {url}")
        if data:
            self.logger.debug(f"Request data: {json.dumps(data, indent=2)[:1000]}")
        
        start_time = time.time()
        retry_count = 0
        max_retries = self.max_retries
        
        while retry_count <= max_retries:
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=json_data,
                    timeout=self.timeout
                )
                
                # Логируем детали ответа
                elapsed_time = time.time() - start_time
                self.logger.debug(f"Response from {url} received in {elapsed_time:.2f}s, status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        self.logger.error(f"Failed to parse response as JSON: {response.text[:1000]}")
                        raise APIError("Failed to parse response as JSON", response.status_code, response.text)
                
                # Обработка ошибок на основе статус-кода
                if response.status_code == 401 or response.status_code == 403:
                    self.logger.error(f"Authentication error: {response.text}")
                    raise AuthenticationError("Authentication failed", response.status_code, response.text)
                
                elif response.status_code == 400 or response.status_code == 422:
                    self.logger.error(f"Validation error: {response.text}")
                    raise ValidationError("Validation failed", response.status_code, response.text)
                
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    self.logger.warning(f"Rate limit exceeded. Retry after {retry_after} seconds.")
                    # Если это не последняя попытка, делаем паузу и повторяем
                    if retry_count < max_retries:
                        retry_count += 1
                        wait_time = min(int(retry_after), 60) * (2 ** (retry_count - 1))  # Экспоненциальная задержка
                        self.logger.info(f"Retrying in {wait_time} seconds (attempt {retry_count}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RateLimitError("Rate limit exceeded", response.status_code, response.text)
                
                # Другие ошибки
                error_message = f"API error: {response.status_code}"
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict) and "message" in error_data:
                        error_message = f"API error: {error_data['message']}"
                except (json.JSONDecodeError, KeyError):
                    error_message = f"API error: {response.text[:200]}"
                
                self.logger.error(f"{error_message} (status={response.status_code})")
                raise APIError(error_message, response.status_code, response.text)
                
            except (ConnectionError, Timeout) as e:
                # Если это не последняя попытка, повторяем
                if retry_count < max_retries:
                    retry_count += 1
                    wait_time = 2 ** retry_count  # Экспоненциальная задержка
                    self.logger.warning(f"Network error: {str(e)}. Retrying in {wait_time} seconds (attempt {retry_count}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"Network error after {max_retries} retries: {str(e)}")
                    raise NetworkError(f"Network error: {str(e)}")
            except RequestException as e:
                self.logger.error(f"Request error: {str(e)}")
                raise NetworkError(f"Request failed: {str(e)}")
            except Exception as e:
                self.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                raise APIError(f"Unexpected error: {str(e)}")
                
        # Этот код никогда не должен выполняться, но добавлен для полноты
        raise APIError("Maximum retries exceeded")

    async def _respect_rate_limit(self) -> None:
        """
        Соблюдает ограничение частоты запросов к API.
        
        Убеждается, что между запросами соблюдается минимальный интервал времени,
        чтобы избежать превышения лимитов API.
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - elapsed)
        
        self.last_request_time = time.time()

    async def _make_async_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет асинхронный запрос к API DMarket с контролем частоты и параллельности.
        
        Args:
            method: HTTP метод запроса (GET, POST, и т.д.)
            endpoint: Конечная точка API (путь без базового URL)
            data: Данные для отправки в запросе (опционально)
            
        Returns:
            Словарь с ответом API
            
        Raises:
            APIError: При ошибке в запросе или ответе API
        """
        url = f"{self.base_url}{endpoint}"
        
        # Ожидаем доступности семафора для контроля параллельности
        async with self.semaphore:
            # Соблюдаем минимальный интервал между запросами
            await self._respect_rate_limit()
            
            # Получаем заголовки аутентификации
            auth_headers = self._get_auth_headers(method, endpoint, data)
            headers = {**self.headers, **auth_headers}
            
            # Логируем запрос с маскированием чувствительных данных
            safe_data = "***" if data and any(k in str(data).lower() for k in ["secret", "password", "token"]) else data
            self.logger.debug(f"Запрос: {method} {url} - Данные: {safe_data}")
            
            # Настраиваем таймаут
            timeout = ClientTimeout(total=self.timeout)
            
            try:
                async with ClientSession(timeout=timeout) as session:
                    http_method = getattr(session, method.lower())
                    
                    start_time = time.time()
                    async with http_method(url, json=data, headers=headers) as response:
                        request_time = time.time() - start_time
                        
                        # Получаем и обрабатываем ответ
                        status_code = response.status
                        response_text = await response.text()
                        
                        self.logger.debug(f"Ответ: {status_code} - Время: {request_time:.2f}с - Размер: {len(response_text)}")
                        
                        # Обрабатываем ошибки HTTP
                        if status_code >= 400:
                            return await self._handle_async_error_response(response, 0, self.max_retries)
                        
                        # Парсим JSON
                        try:
                            return json.loads(response_text)
                        except json.JSONDecodeError:
                            self.logger.error(f"Ошибка декодирования JSON: {response_text[:200]}")
                            raise APIError("Невозможно декодировать ответ JSON", status_code, response_text)
                            
            except asyncio.TimeoutError:
                self.logger.error(f"Таймаут запроса: {method} {url}")
                raise NetworkError("Таймаут запроса", None, None)
                
            except ClientConnectionError as e:
                self.logger.error(f"Ошибка соединения: {method} {url} - {str(e)}")
                raise NetworkError(f"Ошибка соединения: {str(e)}", None, None)
                
            except ClientError as e:
                self.logger.error(f"Ошибка клиента aiohttp: {method} {url} - {str(e)}")
                raise APIError(f"Ошибка HTTP-клиента: {str(e)}", None, None)
                
            except Exception as e:
                self.logger.error(f"Неожиданная ошибка: {method} {url} - {str(e)}")
                raise APIError(f"Неожиданная ошибка: {str(e)}", None, None)

    async def _handle_async_error_response(self, response, retry_count, max_retries):
        """
        Обрабатывает ошибочные ответы от API при асинхронных запросах.
        
        Args:
            response: Объект ответа aiohttp
            retry_count: Текущее количество попыток
            max_retries: Максимальное количество попыток
            
        Returns:
            None - только если требуется повторная попытка
            
        Raises:
            AuthenticationError: При ошибках авторизации
            ValidationError: При ошибках валидации данных
            RateLimitError: При превышении лимита запросов
            APIError: При других ошибках API
        """
        text = await response.text()
                
        if response.status == 401 or response.status == 403:
            self.logger.error(f"Async authentication error: {text}")
            raise AuthenticationError("Authentication failed", response.status, text)
        
        elif response.status == 400 or response.status == 422:
            self.logger.error(f"Async validation error: {text}")
            raise ValidationError("Validation failed", response.status, text)
        
        elif response.status == 429:
            retry_after = response.headers.get("Retry-After", "60")
            self.logger.warning(f"Async rate limit exceeded. Retry after {retry_after} seconds.")
            # Если это не последняя попытка, делаем паузу и повторяем
            if retry_count < max_retries:
                retry_count += 1
                wait_time = min(int(retry_after), 60) * (2 ** (retry_count - 1))  # Экспоненциальная задержка
                self.logger.info(f"Async retrying in {wait_time} seconds (attempt {retry_count}/{max_retries})")
                await asyncio.sleep(wait_time)
                return None  # Сигнализируем о необходимости повторной попытки
            else:
                raise RateLimitError("Rate limit exceeded", response.status, text)
        
        # Другие ошибки
        error_message = f"API error: {response.status}"
        try:
            error_data = await response.json()
            if isinstance(error_data, dict) and "message" in error_data:
                error_message = f"API error: {error_data['message']}"
        except (json.JSONDecodeError, KeyError):
            error_message = f"API error: {text[:200]}"
        
        self.logger.error(f"{error_message} (status={response.status})")
        raise APIError(error_message, response.status, text)

    def get_market_items(
        self,
        game_id: str = "csgo",
        limit: int = 100,
        offset: int = 0,
        currency: str = "USD",
        order_by: str = "price",
        order_dir: Literal["asc", "desc"] = "asc",
        title: Optional[str] = None,
        category: Optional[str] = None,
        price_from: Optional[float] = None,
        price_to: Optional[float] = None,
        rarity: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получает список предметов на рынке.

        Args:
            game_id: Идентификатор игры (по умолчанию "csgo")
            limit: Максимальное количество предметов (по умолчанию 100)
            offset: Смещение для пагинации
            currency: Валюта для цен
            order_by: Поле для сортировки
            order_dir: Направление сортировки ("asc" или "desc")
            title: Фильтр по названию предмета
            category: Фильтр по категории предмета
            price_from: Минимальная цена для фильтрации
            price_to: Максимальная цена для фильтрации
            rarity: Фильтр по редкости предметов

        Returns:
            Словарь с информацией о предметах на рынке
        """
        params = {
            "gameId": game_id,
            "limit": limit,
            "offset": offset,
            "currency": currency,
            "orderBy": order_by,
            "orderDir": order_dir
        }

        if title:
            params["title"] = title
            
        if category:
            params["category"] = category
            
        if price_from is not None:
            params["priceFrom"] = price_from
            
        if price_to is not None:
            params["priceTo"] = price_to
            
        if rarity:
            params["rarity"] = rarity

        endpoint = "/exchange/v1/market/items"
        return self._make_request("GET", endpoint, params)

    async def get_market_items_async(
        self,
        game_id: str = "a8db",  # CS2 по умолчанию
        limit: int = 100,
        offset: int = 0,
        currency: str = "USD",
        price_from: Optional[float] = None,
        price_to: Optional[float] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        rarity: Optional[str] = None,
        exterior: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Асинхронно получает список предметов с рынка DMarket.
        
        Args:
            game_id: Идентификатор игры
            limit: Максимальное количество предметов в ответе
            offset: Смещение для пагинации
            currency: Валюта для цен
            price_from: Минимальная цена для фильтрации
            price_to: Максимальная цена для фильтрации
            title: Фильтр по названию предмета
            category: Фильтр по категории
            rarity: Фильтр по редкости
            exterior: Фильтр по состоянию (Factory New, и т.д.)
            
        Returns:
            Словарь с результатами запроса к API
        """
        # Создаем параметры запроса
        params = {
            "gameId": game_id,
            "limit": limit,
            "offset": offset,
            "currency": currency,
            "orderBy": "price",
            "orderDir": "asc"
        }
        
        # Добавляем опциональные параметры, если они указаны
        if price_from is not None:
            params["priceFrom"] = price_from
        if price_to is not None:
            params["priceTo"] = price_to
        if title:
            params["title"] = title
        if category:
            params["category"] = category
        if rarity:
            params["rarity"] = rarity
        if exterior:
            params["exterior"] = exterior
        
        # Формируем строку запроса
        query_params = "&".join(f"{k}={v}" for k, v in params.items())
        endpoint = f"/exchange/v1/market/items?{query_params}"
        
        # Выполняем запрос
        return await self._make_async_request("GET", endpoint)

    def get_user_inventory(
        self,
        game_id: str = "csgo",
        in_market: bool = False
    ) -> Dict[str, Any]:
        """
        Получает информацию об инвентаре пользователя.

        Args:
            game_id: Идентификатор игры (по умолчанию "csgo")
            in_market: Фильтровать только предметы, выставленные на рынок

        Returns:
            Словарь с информацией об инвентаре пользователя
        """
        params = {"gameId": game_id}
        if in_market:
            params["inMarket"] = "true"
            
        endpoint = "/inventory/v1/user/items"
        return self._make_request("GET", endpoint, params)

    async def get_user_inventory_async(
        self,
        game_id: str = "csgo",
        in_market: bool = False
    ) -> Dict[str, Any]:
        """
        Асинхронно получает информацию об инвентаре пользователя.

        Args:
            game_id: Идентификатор игры (по умолчанию "csgo")
            in_market: Фильтровать только предметы, выставленные на рынок

        Returns:
            Словарь с информацией об инвентаре пользователя
        """
        params = {"gameId": game_id}
        if in_market:
            params["inMarket"] = "true"
            
        endpoint = "/inventory/v1/user/items"
        return await self._make_async_request("GET", endpoint, params)

    def get_item_history(
        self,
        item_id: str,
        limit: int = 100,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Получает историю конкретного предмета.

        Args:
            item_id: Идентификатор предмета
            limit: Максимальное количество записей в истории (по умолчанию 100)
            offset: Смещение для пагинации
            date_from: Начальная дата для фильтрации истории
            date_to: Конечная дата для фильтрации истории

        Returns:
            Словарь с историей предмета
        """
        params = {
            "itemId": item_id,
            "limit": limit,
            "offset": offset
        }

        if date_from:
            params["dateFrom"] = int(date_from.timestamp())

        if date_to:
            params["dateTo"] = int(date_to.timestamp())

        endpoint = "/exchange/v1/market/items/history"
        return self._make_request("GET", endpoint, params)
        
    async def get_item_history_async(
        self,
        item_id: str,
        limit: int = 100,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Асинхронно получает историю конкретного предмета.

        Args:
            item_id: Идентификатор предмета
            limit: Максимальное количество записей в истории (по умолчанию 100)
            offset: Смещение для пагинации
            date_from: Начальная дата для фильтрации истории
            date_to: Конечная дата для фильтрации истории

        Returns:
            Словарь с историей предмета
        """
        params = {
            "itemId": item_id,
            "limit": limit,
            "offset": offset
        }

        if date_from:
            params["dateFrom"] = int(date_from.timestamp())

        if date_to:
            params["dateTo"] = int(date_to.timestamp())

        endpoint = "/exchange/v1/market/items/history"
        return await self._make_async_request("GET", endpoint, params)

    def buy_item(
        self,
        item_id: str,
        price: Union[int, float, ItemPrice],
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Покупает предмет на рынке.

        Args:
            item_id: Идентификатор предмета
            price: Цена покупки (число или объект ItemPrice)
            currency: Валюта для цены (используется, если price - число)

        Returns:
            Результат операции покупки
        """
        if isinstance(price, (int, float)):
            price_data = {
                "amount": str(price),
                "currency": currency
            }
        else:
            # Если передан объект ItemPrice
            price_data = {
                "amount": str(price.USD),
                "currency": "USD"
            }

        data = {
            "itemId": item_id,
            "price": price_data
        }
        
        self.logger.info(
            f"Выполняется покупка предмета {item_id} за "
            f"{price_data['amount']} {price_data['currency']}"
        )
        endpoint = "/exchange/v1/offers/buy"
        return self._make_request("POST", endpoint, data)

    async def buy_item_async(
        self,
        item_id: str,
        price: Union[int, float, ItemPrice],
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Асинхронно покупает предмет на рынке.

        Args:
            item_id: Идентификатор предмета
            price: Цена покупки (число или объект ItemPrice)
            currency: Валюта для цены (используется, если price - число)

        Returns:
            Результат операции покупки
        """
        if isinstance(price, (int, float)):
            price_data = {
                "amount": str(price),
                "currency": currency
            }
        else:
            # Если передан объект ItemPrice
            price_data = {
                "amount": str(price.USD),
                "currency": "USD"
            }

        data = {
            "itemId": item_id,
            "price": price_data
        }
        
        self.logger.info(
            f"Асинхронно выполняется покупка предмета {item_id} за "
            f"{price_data['amount']} {price_data['currency']}"
        )
        endpoint = "/exchange/v1/offers/buy"
        return await self._make_async_request("POST", endpoint, data)

    def sell_item(
        self,
        item_id: str,
        price: Union[int, float, ItemPrice],
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Выставляет предмет на продажу.

        Args:
            item_id: Идентификатор предмета
            price: Цена продажи (число или объект ItemPrice)
            currency: Валюта для цены (используется, если price - число)

        Returns:
            Результат операции продажи
        """
        if isinstance(price, (int, float)):
            price_data = {
                "amount": str(price),
                "currency": currency
            }
        else:
            # Если передан объект ItemPrice
            price_data = {
                "amount": str(price.USD),
                "currency": "USD"
            }

        data = {
            "itemId": item_id,
            "price": price_data
        }
        
        self.logger.info(
            f"Выставляется предмет {item_id} на продажу за "
            f"{price_data['amount']} {price_data['currency']}"
        )
        endpoint = "/exchange/v1/offers/sell"
        return self._make_request("POST", endpoint, data)

    async def sell_item_async(
        self,
        item_id: str,
        price: Union[int, float, ItemPrice],
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Асинхронно выставляет предмет на продажу.

        Args:
            item_id: Идентификатор предмета
            price: Цена продажи (число или объект ItemPrice)
            currency: Валюта для цены (используется, если price - число)

        Returns:
            Результат операции продажи
        """
        if isinstance(price, (int, float)):
            price_data = {
                "amount": str(price),
                "currency": currency
            }
        else:
            # Если передан объект ItemPrice
            price_data = {
                "amount": str(price.USD),
                "currency": "USD"
            }

        data = {
            "itemId": item_id,
            "price": price_data
        }
        
        self.logger.info(
            f"Асинхронно выставляется предмет {item_id} на продажу за "
            f"{price_data['amount']} {price_data['currency']}"
        )
        endpoint = "/exchange/v1/offers/sell"
        return await self._make_async_request("POST", endpoint, data)

    def get_available_games(self) -> List[Dict[str, Any]]:
        """
        Получает список доступных игр на платформе.

        Returns:
            Список игр с их идентификаторами и названиями
        """
        endpoint = "/exchange/v1/games"
        response = self._make_request("GET", endpoint)
        return response.get("games", [])

    async def get_available_games_async(self) -> List[Dict[str, Any]]:
        """
        Асинхронно получает список доступных игр на платформе.

        Returns:
            Список игр с их идентификаторами и названиями
        """
        endpoint = "/exchange/v1/games"
        response = await self._make_async_request("GET", endpoint)
        return response.get("games", [])

    def search_items(
        self,
        game_id: str = "csgo",
        title: str = "",
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        currency: str = "USD",
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "price",
        sort_dir: Literal["asc", "desc"] = "asc",
        exact_match: bool = False
    ) -> Dict[str, Any]:
        """
        Выполняет поиск предметов на рынке по различным параметрам.

        Args:
            game_id: Идентификатор игры
            title: Название или часть названия предмета
            category: Категория предмета
            min_price: Минимальная цена
            max_price: Максимальная цена
            currency: Валюта для цен
            limit: Максимальное количество возвращаемых предметов
            offset: Смещение для пагинации
            sort_by: Поле для сортировки
            sort_dir: Направление сортировки ("asc" или "desc")
            exact_match: Искать точное совпадение названия

        Returns:
            Результаты поиска предметов
        """
        params = {
            "gameId": game_id,
            "title": title,
            "limit": limit,
            "offset": offset,
            "currency": currency,
            "orderBy": sort_by,
            "orderDir": sort_dir
        }

        if category:
            params["category"] = category

        if min_price is not None:
            params["priceFrom"] = min_price

        if max_price is not None:
            params["priceTo"] = max_price
            
        if exact_match:
            params["titleExactMatch"] = "true"

        endpoint = "/exchange/v1/market/items"
        return self._make_request("GET", endpoint, params)
        
    async def search_items_async(
        self,
        game_id: str = "csgo",
        title: str = "",
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        currency: str = "USD",
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "price",
        sort_dir: Literal["asc", "desc"] = "asc",
        exact_match: bool = False
    ) -> Dict[str, Any]:
        """
        Асинхронно выполняет поиск предметов на рынке по различным параметрам.

        Args:
            game_id: Идентификатор игры
            title: Название или часть названия предмета
            category: Категория предмета
            min_price: Минимальная цена
            max_price: Максимальная цена
            currency: Валюта для цен
            limit: Максимальное количество возвращаемых предметов
            offset: Смещение для пагинации
            sort_by: Поле для сортировки
            sort_dir: Направление сортировки ("asc" или "desc")
            exact_match: Искать точное совпадение названия

        Returns:
            Результаты поиска предметов
        """
        params = {
            "gameId": game_id,
            "title": title,
            "limit": limit,
            "offset": offset,
            "currency": currency,
            "orderBy": sort_by,
            "orderDir": sort_dir
        }

        if category:
            params["category"] = category

        if min_price is not None:
            params["priceFrom"] = min_price

        if max_price is not None:
            params["priceTo"] = max_price
            
        if exact_match:
            params["titleExactMatch"] = "true"

        endpoint = "/exchange/v1/market/items"
        return await self._make_async_request("GET", endpoint, params)
    
    def get_balance(self) -> Dict[str, Any]:
        """
        Получает баланс пользователя в разных валютах.

        Returns:
            Словарь с информацией о балансе пользователя
        """
        endpoint = "/account/v1/balance"
        return self._make_request("GET", endpoint)
        
    async def get_balance_async(self) -> Dict[str, Any]:
        """
        Асинхронно получает баланс пользователя в разных валютах.

        Returns:
            Словарь с информацией о балансе пользователя
        """
        endpoint = "/account/v1/balance"
        return await self._make_async_request("GET", endpoint)
    
    def get_price_aggregation(
        self,
        item_name: str,
        game_id: str = "csgo",
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Получает агрегированные данные о ценах для указанного предмета.

        Args:
            item_name: Название предмета
            game_id: Идентификатор игры
            currency: Валюта для цен

        Returns:
            Агрегированные данные о ценах
        """
        params = {
            "gameId": game_id,
            "title": item_name,
            "currency": currency
        }
        
        endpoint = "/exchange/v1/market/items/aggregated"
        return self._make_request("GET", endpoint, params)
        
    async def get_price_aggregation_async(
        self,
        item_name: str,
        game_id: str = "csgo",
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Асинхронно получает агрегированные данные о ценах для указанного предмета.

        Args:
            item_name: Название предмета
            game_id: Идентификатор игры
            currency: Валюта для цен

        Returns:
            Агрегированные данные о ценах
        """
        params = {
            "gameId": game_id,
            "title": item_name,
            "currency": currency
        }
        
        endpoint = "/exchange/v1/market/items/aggregated"
        return await self._make_async_request("GET", endpoint, params)
    
    def cancel_offer(self, offer_id: str) -> Dict[str, Any]:
        """
        Отменяет предложение о продаже.

        Args:
            offer_id: Идентификатор предложения

        Returns:
            Результат операции отмены
        """
        endpoint = f"/exchange/v1/offers/{offer_id}/delete"
        return self._make_request("DELETE", endpoint)
        
    async def cancel_offer_async(self, offer_id: str) -> Dict[str, Any]:
        """
        Асинхронно отменяет предложение о продаже.

        Args:
            offer_id: Идентификатор предложения

        Returns:
            Результат операции отмены
        """
        endpoint = f"/exchange/v1/offers/{offer_id}/delete"
        return await self._make_async_request("DELETE", endpoint)
    
    async def ping_async(self) -> bool:
        """
        Проверяет соединение с API DMarket.
        
        Returns:
            True если соединение успешно, False в противном случае
        """
        try:
            # Используем простой запрос к API для проверки соединения
            result = await self.get_balance_async()
            
            # Если запрос успешен и вернул данные, значит соединение работает
            if result and isinstance(result, dict):
                self.logger.info("Соединение с DMarket API успешно установлено")
                return True
                
            self.logger.warning("Ошибка при проверке соединения: неожиданный формат ответа")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при проверке соединения с DMarket API: {e}")
            return False
    
    # ---- Методы для работы с отложенными ордерами (таргетами) ----
    
    def create_target_order(
        self,
        item_name: str,
        target_price: Dict[str, str],
        game_id: str,
        expiration_time: int,
        auto_execute: bool = True
    ) -> Dict[str, Any]:
        """
        Создает отложенный ордер (таргет) на покупку предмета по заданной цене.
        
        Args:
            item_name: Название предмета
            target_price: Целевая цена в формате {валюта: строковое представление цены}
            game_id: ID игры (a8db для CS2, 9a92 для Dota 2, tf2 для TF2)
            expiration_time: Время истечения срока действия в UNIX timestamp
            auto_execute: Автоматически выполнить ордер при достижении целевой цены
            
        Returns:
            Ответ API
            
        Raises:
            APIError: При ошибке в API
        """
        endpoint = "/v1/target-order"
        data = {
            "itemName": item_name,
            "targetPrice": target_price,
            "gameId": game_id,
            "expirationTime": expiration_time,
            "autoExecute": auto_execute
        }
        
        self.logger.info(f"Создание отложенного ордера для {item_name} с целевой ценой {target_price}")
        return self._make_request("POST", endpoint, data)
    
    async def create_target_order_async(
        self,
        item_name: str,
        target_price: Dict[str, str],
        game_id: str,
        expiration_time: int,
        auto_execute: bool = True
    ) -> Dict[str, Any]:
        """
        Асинхронно создает отложенный ордер (таргет) на покупку предмета по заданной цене.
        
        Args:
            item_name: Название предмета
            target_price: Целевая цена в формате {валюта: строковое представление цены}
            game_id: ID игры (a8db для CS2, 9a92 для Dota 2, tf2 для TF2)
            expiration_time: Время истечения срока действия в UNIX timestamp
            auto_execute: Автоматически выполнить ордер при достижении целевой цены
            
        Returns:
            Ответ API
            
        Raises:
            APIError: При ошибке в API
        """
        endpoint = "/v1/target-order"
        data = {
            "itemName": item_name,
            "targetPrice": target_price,
            "gameId": game_id,
            "expirationTime": expiration_time,
            "autoExecute": auto_execute
        }
        
        self.logger.info(f"Асинхронное создание отложенного ордера для {item_name} с целевой ценой {target_price}")
        return await self._make_async_request("POST", endpoint, data)
    
    def get_target_orders(
        self,
        game_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Получает список отложенных ордеров пользователя.
        
        Args:
            game_id: ID игры для фильтрации (опционально)
            status: Статус ордеров для фильтрации (active, completed, expired)
            limit: Максимальное количество ордеров
            offset: Смещение для пагинации
            
        Returns:
            Ответ API со списком отложенных ордеров
            
        Raises:
            APIError: При ошибке в API
        """
        endpoint = "/v1/target-orders"
        params = {"limit": limit, "offset": offset}
        
        if game_id:
            params["gameId"] = game_id
        if status:
            params["status"] = status
        
        self.logger.info(f"Получение списка отложенных ордеров с параметрами {params}")
        return self._make_request("GET", endpoint, params)
    
    async def get_target_orders_async(
        self,
        game_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Асинхронно получает список отложенных ордеров пользователя.
        
        Args:
            game_id: ID игры для фильтрации (опционально)
            status: Статус ордеров для фильтрации (active, completed, expired)
            limit: Максимальное количество ордеров
            offset: Смещение для пагинации
            
        Returns:
            Ответ API со списком отложенных ордеров
            
        Raises:
            APIError: При ошибке в API
        """
        endpoint = "/v1/target-orders"
        params = {"limit": limit, "offset": offset}
        
        if game_id:
            params["gameId"] = game_id
        if status:
            params["status"] = status
        
        self.logger.info(f"Асинхронное получение списка отложенных ордеров с параметрами {params}")
        return await self._make_async_request("GET", endpoint, params)
    
    def cancel_target_order(self, target_id: str) -> Dict[str, Any]:
        """
        Отменяет отложенный ордер по его ID.
        
        Args:
            target_id: ID отложенного ордера
            
        Returns:
            Ответ API с результатом отмены
            
        Raises:
            APIError: При ошибке в API
        """
        endpoint = f"/v1/target-order/{target_id}"
        
        self.logger.info(f"Отмена отложенного ордера с ID {target_id}")
        return self._make_request("DELETE", endpoint)
    
    async def cancel_target_order_async(self, target_id: str) -> Dict[str, Any]:
        """
        Асинхронно отменяет отложенный ордер по его ID.
        
        Args:
            target_id: ID отложенного ордера
            
        Returns:
            Ответ API с результатом отмены
            
        Raises:
            APIError: При ошибке в API
        """
        endpoint = f"/v1/target-order/{target_id}"
        
        self.logger.info(f"Асинхронная отмена отложенного ордера с ID {target_id}")
        return await self._make_async_request("DELETE", endpoint)
    
    def execute_target_order(self, target_id: str) -> Dict[str, Any]:
        """
        Немедленно выполняет отложенный ордер, не дожидаясь достижения целевой цены.
        
        Args:
            target_id: ID отложенного ордера
            
        Returns:
            Ответ API с результатом выполнения
            
        Raises:
            APIError: При ошибке в API
        """
        endpoint = f"/v1/target-order/{target_id}/execute"
        
        self.logger.info(f"Выполнение отложенного ордера с ID {target_id}")
        return self._make_request("POST", endpoint)
    
    async def execute_target_order_async(self, target_id: str) -> Dict[str, Any]:
        """
        Асинхронно выполняет отложенный ордер, не дожидаясь достижения целевой цены.
        
        Args:
            target_id: ID отложенного ордера
            
        Returns:
            Ответ API с результатом выполнения
            
        Raises:
            APIError: При ошибке в API
        """
        endpoint = f"/v1/target-order/{target_id}/execute"
        
        self.logger.info(f"Асинхронное выполнение отложенного ордера с ID {target_id}")
        return await self._make_async_request("POST", endpoint)

    async def get_inventory_items(self):
        """
        Получает список предметов из инвентаря пользователя.
        
        Returns:
            List[Dict[str, Any]]: Список предметов в инвентаре с детальной информацией
            
        Raises:
            AuthenticationError: При ошибке аутентификации
            RateLimitError: При превышении лимита запросов API
            NetworkError: При проблемах с сетевым соединением
            APIError: При других ошибках API
        """
        try:
            url = f"{self.base_url}/user-items"
            params = {
                "gameId": "a8db", # CS2 GameID
                "limit": 100,
                "offset": 0,
                "currency": "USD"
            }
            
            response = await self._make_async_request("GET", "/user-items", params=params)
            
            if response and "items" in response and isinstance(response["items"], list):
                self.logger.info(f"Успешно получены {len(response['items'])} предметов из инвентаря")
                return response["items"]
            else:
                error_msg = "Не удалось получить предметы из инвентаря: неверный формат ответа"
                self.logger.warning(error_msg)
                if response:
                    self.logger.debug(f"Полученный ответ: {response}")
                raise ValidationError(error_msg, response=str(response))
        except AuthenticationError as auth_err:
            self.logger.error(f"Ошибка аутентификации при получении инвентаря: {auth_err}")
            raise
        except RateLimitError as rate_err:
            self.logger.error(f"Превышен лимит запросов при получении инвентаря: {rate_err}")
            raise
        except (ClientConnectionError, ConnectionError, Timeout) as conn_err:
            error_msg = f"Ошибка соединения при получении инвентаря: {conn_err}"
            self.logger.error(error_msg)
            raise NetworkError(error_msg) from conn_err
        except Exception as e:
            error_msg = f"Непредвиденная ошибка при получении предметов из инвентаря: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise APIError(error_msg) from e

    async def get_account_info(self):
        """
        Получает информацию об аккаунте пользователя.
        
        Returns:
            Dict[str, Any]: Словарь с информацией об аккаунте в структурированном формате
            
        Raises:
            AuthenticationError: При ошибке аутентификации
            RateLimitError: При превышении лимита запросов API
            NetworkError: При проблемах с сетевым соединением
            APIError: При других ошибках API
        """
        try:
            response = await self._make_async_request("GET", "/account")
            
            if response and isinstance(response, dict):
                self.logger.info("Успешно получена информация об аккаунте")
                
                # Преобразуем данные в более удобный формат
                account_info = {
                    "username": response.get("username", ""),
                    "verified": response.get("isVerified", False),
                    "trade_level": response.get("tradeLevel", 0),
                    "email": response.get("email", ""),
                    "created_at": response.get("createdAt", ""),
                    "status": response.get("status", ""),
                    "limits": {}
                }
                
                # Добавляем информацию о лимитах, если она есть
                if "tradeLimits" in response and isinstance(response["tradeLimits"], dict):
                    limits = response["tradeLimits"]
                    account_info["limits"]["daily_limit"] = limits.get("daily", 0)
                    account_info["limits"]["monthly_limit"] = limits.get("monthly", 0)
                    account_info["limits"]["used_daily"] = limits.get("usedDaily", 0)
                    account_info["limits"]["used_monthly"] = limits.get("usedMonthly", 0)
                
                return account_info
            else:
                error_msg = "Не удалось получить информацию об аккаунте: неверный формат ответа"
                self.logger.warning(error_msg)
                if response:
                    self.logger.debug(f"Полученный ответ: {response}")
                raise ValidationError(error_msg, response=str(response))
        except AuthenticationError as auth_err:
            self.logger.error(f"Ошибка аутентификации при получении информации об аккаунте: {auth_err}")
            raise
        except RateLimitError as rate_err:
            self.logger.error(f"Превышен лимит запросов при получении информации об аккаунте: {rate_err}")
            raise
        except (ClientConnectionError, ConnectionError, Timeout) as conn_err:
            error_msg = f"Ошибка соединения при получении информации об аккаунте: {conn_err}"
            self.logger.error(error_msg)
            raise NetworkError(error_msg) from conn_err
        except Exception as e:
            error_msg = f"Непредвиденная ошибка при получении информации об аккаунте: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise APIError(error_msg) from e

    async def batch_async_requests(
        self, 
        requests: List[Dict[str, Any]],
        batch_size: int = 5,
        interval_between_batches: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Выполняет пакетную обработку асинхронных запросов к API.
        
        Разделяет большое количество запросов на батчи для соблюдения
        лимитов API и выполняет их асинхронно в пределах каждой группы.
        
        Args:
            requests: Список словарей с параметрами запросов, каждый должен содержать:
                - 'method': HTTP метод запроса
                - 'endpoint': конечная точка API
                - 'data': (опционально) данные для отправки
            batch_size: Размер группы запросов для одновременного выполнения
            interval_between_batches: Интервал между группами запросов в секундах
            
        Returns:
            Список ответов от API в том же порядке, что и запросы
        """
        # Импортируем декоратор retry_batch_async из utils.api_retry
        from utils.api_retry import retry_batch_async
        
        # Внутренняя функция для выполнения пакета запросов
        # Декорируем функцию для обработки ошибок и повторов
        @retry_batch_async(
            max_retries=self.max_retries,
            base_delay=1.0,
            max_delay=10.0,
            batch_param='batch_requests',
            id_field='endpoint'  # Используем endpoint как идентификатор
        )
        async def _execute_batch(batch_requests: List[Dict[str, Any]]) -> List[Any]:
            # Создаем задачи для всех запросов в пакете
            tasks = []
            for req in batch_requests:
                method = req.get('method', 'GET')
                endpoint = req.get('endpoint', '')
                data = req.get('data')
                
                task = asyncio.create_task(self._make_async_request(method, endpoint, data))
                tasks.append(task)
            
            # Выполняем все задачи одновременно
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        results = []
        total_requests = len(requests)
        
        self.logger.info(f"Запуск пакетной обработки {total_requests} запросов, "
                         f"размер группы: {batch_size}, интервал: {interval_between_batches}с")
        
        # Разбиваем все запросы на группы по batch_size
        for i in range(0, total_requests, batch_size):
            batch = requests[i:i+batch_size]
            batch_start = time.time()
            
            self.logger.debug(f"Обработка группы {i//batch_size + 1}/{(total_requests+batch_size-1)//batch_size}, "
                              f"запросов: {len(batch)}")
            
            # Выполняем пакет запросов с обработкой ошибок
            batch_results = await _execute_batch(batch_requests=batch)
            results.extend(batch_results)
            
            batch_time = time.time() - batch_start
            self.logger.debug(f"Группа {i//batch_size + 1} завершена за {batch_time:.2f}с")
            
            # Ждем указанный интервал перед следующей группой, если это не последняя группа
            if i + batch_size < total_requests and batch_time < interval_between_batches:
                await asyncio.sleep(interval_between_batches - batch_time)
        
        # Обрабатываем исключения в результатах только для не перехваченных ошибок
        for i, result in enumerate(results):
            if isinstance(result, Exception) and not isinstance(result, dict) and not hasattr(result, 'get'):
                self.logger.error(f"Неперехваченная ошибка в запросе {i}: {str(result)}")
                results[i] = {"error": str(result), "success": False, "error_type": type(result).__name__}
        
        return results

    # Добавляем новый метод для получения предметов партиями
    async def get_market_items_batch(
        self,
        game_ids: List[str],
        limit: int = 100,
        price_ranges: Optional[List[Tuple[float, float]]] = None,
        currency: str = "USD",
        batch_size: int = 3
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Получает предметы с рынка для нескольких игр и ценовых диапазонов одним пакетом.
        
        Args:
            game_ids: Список идентификаторов игр
            limit: Количество предметов для каждого запроса
            price_ranges: Список кортежей (min_price, max_price) для каждой игры
            currency: Валюта для цен
            batch_size: Размер группы запросов для одновременного выполнения
            
        Returns:
            Словарь с результатами в формате {game_id: [items]}
        """
        # Проверяем, что если price_ranges указан, то его длина соответствует длине game_ids
        if price_ranges is not None and len(game_ids) != len(price_ranges):
            raise ValueError("Количество игр и ценовых диапазонов должно совпадать")
        
        # Если ценовые диапазоны не указаны, используем None для всех игр
        actual_price_ranges = price_ranges if price_ranges is not None else [(None, None)] * len(game_ids)
        
        # Подготавливаем запросы
        requests = []
        for i, game_id in enumerate(game_ids):
            min_price, max_price = actual_price_ranges[i]
            
            # Формируем параметры запроса
            params = {
                "gameId": game_id,
                "limit": limit,
                "offset": 0,
                "currency": currency,
                "orderBy": "price",
                "orderDir": "asc"
            }
            
            # Добавляем ценовые фильтры, если они указаны
            if min_price is not None:
                params["priceFrom"] = min_price
            if max_price is not None:
                params["priceTo"] = max_price
            
            # Формируем строку запроса
            query_params = "&".join(f"{k}={v}" for k, v in params.items())
            endpoint = f"/exchange/v1/market/items?{query_params}"
            
            # Добавляем запрос в список
            requests.append({
                'method': 'GET',
                'endpoint': endpoint,
                'data': None,
                'game_id': game_id  # Сохраняем game_id для последующей обработки
            })
        
        # Выполняем запросы пакетами
        batch_responses = await self.batch_async_requests(requests, batch_size=batch_size)
        
        # Обрабатываем результаты
        results = {}
        for i, response in enumerate(batch_responses):
            game_id = requests[i]['game_id']
            
            # Обрабатываем ошибки или успешные ответы
            if isinstance(response, dict) and 'error' in response:
                self.logger.error(f"Ошибка при получении предметов для {game_id}: {response['error']}")
                results[game_id] = []
            else:
                # Извлекаем предметы из ответа
                items = response.get('objects', [])
                results[game_id] = items
                self.logger.info(f"Получено {len(items)} предметов для {game_id}")
        
        return results

    # Метод для обновления цен множества предметов одним запросом
    async def get_prices_batch(
        self,
        item_ids: List[str],
        currency: str = "USD",
        batch_size: int = 20
    ) -> Dict[str, Dict[str, Any]]:
        """
        Получает актуальные цены для списка предметов одним пакетным запросом.
        
        Args:
            item_ids: Список идентификаторов предметов
            currency: Валюта для цен
            batch_size: Размер группы запросов
            
        Returns:
            Словарь с ценами предметов в формате {item_id: price_info}
        """
        if not item_ids:
            return {}
        
        self.logger.info(f"Запуск пакетного получения цен для {len(item_ids)} предметов")
        
        # Разбиваем большой список на группы по batch_size предметов
        # для оптимального использования API
        batches = [list(islice(item_ids, i, i + batch_size)) 
                   for i in range(0, len(item_ids), batch_size)]
        
        results = {}
        
        for batch_num, batch in enumerate(batches):
            self.logger.debug(f"Обработка группы цен {batch_num+1}/{len(batches)}, "
                              f"предметов: {len(batch)}")
            
            # Формируем строку идентификаторов предметов
            items_param = ",".join(batch)
            endpoint = f"/exchange/v1/market/items/prices?itemIds={items_param}&currency={currency}"
            
            try:
                # Выполняем запрос
                response = await self._make_async_request("GET", endpoint)
                
                # Обрабатываем ответ
                if 'items' in response:
                    for item in response['items']:
                        item_id = item.get('itemId')
                        if item_id:
                            results[item_id] = item
                else:
                    self.logger.warning(f"Неожиданный формат ответа для группы {batch_num+1}")
                
                # Добавляем задержку между группами для соблюдения лимитов API
                if batch_num < len(batches) - 1:
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                self.logger.error(f"Ошибка при получении цен для группы {batch_num+1}: {str(e)}")
                # Продолжаем с другими группами, даже если эта вызвала ошибку
        
        self.logger.info(f"Получены цены для {len(results)} из {len(item_ids)} предметов")
        return results

    @retry_async(
        max_retries=3,
        base_delay=1.0,
        max_delay=10.0
    )
    async def get_cached_market_items(
        self,
        game_id: str,
        title: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        currency: str = "USD",
        price_from: Optional[float] = None,
        price_to: Optional[float] = None,
        cache_ttl: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Получает предметы с рынка с использованием умного кэширования.
        
        Реализует интеллектуальное кэширование с учетом волатильности данных:
        - Часто изменяющиеся данные кэшируются на короткое время
        - Стабильные данные кэшируются на более долгий срок
        - Дорогие предметы имеют меньшее время кэширования
        
        Args:
            game_id: Идентификатор игры
            title: Фильтр по названию (опционально)
            category: Фильтр по категории (опционально)
            limit: Максимальное количество предметов
            offset: Смещение для пагинации
            currency: Валюта для цен
            price_from: Минимальная цена (опционально)
            price_to: Максимальная цена (опционально)
            cache_ttl: Время жизни кэша в секундах (опционально)
            force_refresh: Принудительно обновить кэш
            
        Returns:
            Результаты запроса с рынка
        """
        # Импортируем SmartCache
        from utils.smart_cache import SmartCache
        
        # Генерируем ключ для кэша на основе параметров запроса
        cache_key_parts = [
            f"market_items:{game_id}",
            f"limit:{limit}",
            f"offset:{offset}",
            f"currency:{currency}"
        ]
        
        if title:
            cache_key_parts.append(f"title:{title}")
        if category:
            cache_key_parts.append(f"category:{category}")
        if price_from is not None:
            cache_key_parts.append(f"price_from:{price_from}")
        if price_to is not None:
            cache_key_parts.append(f"price_to:{price_to}")
            
        cache_key = ":".join(cache_key_parts)
        
        # Определяем время жизни кэша в зависимости от параметров
        if cache_ttl is None:
            # Базовое время кэширования - 5 минут
            base_ttl = 300
            
            # Корректируем TTL в зависимости от параметров
            
            # 1. Дорогие предметы обновляются чаще
            if price_from is not None and price_from > 100:
                base_ttl = int(base_ttl * 0.7)  # 70% от базового времени
            
            # 2. Предметы с низкой ценой обновляются реже
            if price_to is not None and price_to < 10:
                base_ttl = int(base_ttl * 1.5)  # 150% от базового времени
                
            # 3. Конкретные предметы (с указанным названием) обновляются чаще
            if title:
                base_ttl = int(base_ttl * 0.8)  # 80% от базового времени
                
            # 4. Запросы с большим лимитом кэшируются дольше
            if limit > 50:
                base_ttl = int(base_ttl * 1.2)  # 120% от базового времени
                
            cache_ttl = base_ttl
        
        # Определяем волатильность для ключа
        # Волатильность влияет на частоту обновления кэша (0-1)
        volatility = 0.0
        
        # Дорогие предметы более волатильны
        if price_from is not None and price_from > 50:
            volatility += 0.2
            
        # Конкретные предметы более волатильны
        if title:
            volatility += 0.3
            
        # Категории обычно стабильны
        if category:
            volatility -= 0.1
            
        # Нормализуем волатильность
        volatility = max(0.0, min(1.0, volatility))
        
        # Получаем глобальный экземпляр кэша
        cache = SmartCache("market_items_cache", default_ttl=300, max_memory_mb=100)
        
        # Проверяем кэш, если не требуется принудительное обновление
        if not force_refresh:
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                self.logger.debug(f"Данные для {cache_key} найдены в кэше")
                return cached_result
        
        # Если данных нет в кэше или требуется обновление, выполняем запрос
        self.logger.debug(f"Получение данных с рынка для {cache_key}")
        
        result = await self.get_market_items_async(
            game_id=game_id,
            title=title,
            category=category,
            limit=limit,
            offset=offset,
            currency=currency,
            price_from=price_from,
            price_to=price_to
        )
        
        # Сохраняем результат в кэш с учетом волатильности
        cache.set(cache_key, result, ttl=cache_ttl, volatility=volatility)
        
        return result

    async def get_item_history_safe(self, item_id: str, limit: int = 10, max_retries: int = 3, retry_delay: float = 1.0) -> Dict[str, Any]:
        """
        Безопасное получение истории предмета с обработкой ошибок и повторными попытками.
        
        Args:
            item_id: Идентификатор предмета
            limit: Лимит количества записей истории
            max_retries: Максимальное количество повторных попыток
            retry_delay: Задержка между повторными попытками (в секундах)
            
        Returns:
            История продаж предмета или пустой результат в случае ошибки
        """
        endpoint = f'/exchange/v1/item-history/{item_id}'
        params = {'limit': limit}
        
        for attempt in range(max_retries):
            try:
                result = await self._make_request('GET', endpoint, params=params)
                if result and 'history' in result:
                    return result
                
                # Если нет истории, возвращаем пустой результат
                if attempt == max_retries - 1:
                    logger.warning(f"История для предмета {item_id} недоступна после {max_retries} попыток")
                    return {"history": []}
                    
                # Ожидаем перед следующей попыткой
                await asyncio.sleep(retry_delay)
                
            except Exception as e:
                # Если это последняя попытка, записываем ошибку и возвращаем пустой результат
                if attempt == max_retries - 1:
                    logger.error(f"Не удалось получить историю предмета {item_id}: {e}")
                    return {"history": []}
                
                # Если ошибка связана с 404, пробуем альтернативные пути получения информации
                if "404" in str(e):
                    try:
                        # Альтернативный путь - получаем обычную информацию о предмете
                        # и извлекаем цены из неё
                        item_info = await self.get_market_item(item_id)
                        if item_info:
                            # Создаем синтетическую историю на основе текущих цен
                            price = item_info.get('price', {}).get('USD', 0)
                            if price:
                                synthetic_history = [
                                    {
                                        "date": datetime.now().isoformat(),
                                        "price": {
                                            "USD": price
                                        },
                                        "type": "synthetic"
                                    }
                                ]
                                logger.info(f"Создана синтетическая история для предмета {item_id}")
                                return {"history": synthetic_history}
                    except Exception as sub_e:
                        logger.warning(f"Не удалось создать синтетическую историю для {item_id}: {sub_e}")
                
                # Ожидаем перед следующей попыткой
                await asyncio.sleep(retry_delay * (attempt + 1))  # Увеличиваем задержку с каждой попыткой
        
        # Если все попытки не удались
        return {"history": []}

    async def get_market_item(self, item_id: str) -> Dict[str, Any]:
        """
        Получает информацию о конкретном предмете на рынке.
        
        Args:
            item_id: Идентификатор предмета
            
        Returns:
            Информация о предмете
        """
        endpoint = f'/exchange/v1/market-items/{item_id}'
        try:
            return await self._make_request('GET', endpoint)
        except Exception as e:
            logger.error(f"Ошибка при получении информации о предмете {item_id}: {e}")
            return {}
