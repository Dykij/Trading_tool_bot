"""Type stubs for api_wrapper module."""

from typing import Dict, Any, Optional, Union, List, Literal, TypedDict
from datetime import datetime
import requests
import aiohttp
from aiohttp import ClientSession, ClientError, ClientConnectionError, ClientTimeout
from schemas.schemas import ItemPrice

class PriceInfo(TypedDict):
    amount: str
    currency: str

class APIError(Exception):
    message: str
    status_code: Optional[int]
    response: Optional[str]
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[str] = None) -> None: ...

class AuthenticationError(APIError): ...
class RateLimitError(APIError): ...
class NetworkError(APIError): ...
class ValidationError(APIError): ...

class DMarketAPI:
    base_url: str
    api_key: str
    api_secret: Optional[str]
    timeout: int
    max_retries: int
    headers: Dict[str, str]
    logger: Any

    def __init__(
        self,
        api_key: str,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ) -> None: ...
    
    def _generate_signature(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]: ...

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]: ...

    async def _make_async_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]: ...

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
    ) -> Dict[str, Any]: ...

    async def get_market_items_async(
        self,
        game_id: str = "csgo",
        limit: int = 100,
        offset: int = 0,
        currency: str = "USD",
        order_by: str = "price",
        order_dir: Literal["asc", "desc"] = "asc",
        title: Optional[str] = None
    ) -> Dict[str, Any]: ...

    def get_user_inventory(
        self,
        game_id: str = "csgo",
        in_market: bool = False
    ) -> Dict[str, Any]: ...

    async def get_user_inventory_async(
        self,
        game_id: str = "csgo",
        in_market: bool = False
    ) -> Dict[str, Any]: ...

    def get_item_history(
        self,
        item_id: str,
        limit: int = 100,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]: ...

    async def get_item_history_async(
        self,
        item_id: str,
        limit: int = 100,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]: ...

    def buy_item(
        self,
        item_id: str,
        price: Union[int, float, ItemPrice],
        currency: str = "USD"
    ) -> Dict[str, Any]: ...

    async def buy_item_async(
        self,
        item_id: str,
        price: Union[int, float, ItemPrice],
        currency: str = "USD"
    ) -> Dict[str, Any]: ...

    def sell_item(
        self,
        item_id: str,
        price: Union[int, float, ItemPrice],
        currency: str = "USD"
    ) -> Dict[str, Any]: ...

    async def sell_item_async(
        self,
        item_id: str,
        price: Union[int, float, ItemPrice],
        currency: str = "USD"
    ) -> Dict[str, Any]: ...

    def get_available_games(self) -> List[Dict[str, Any]]: ...
    async def get_available_games_async(self) -> List[Dict[str, Any]]: ...

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
    ) -> Dict[str, Any]: ...

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
    ) -> Dict[str, Any]: ...

    def get_balance(self) -> Dict[str, Any]: ...
    async def get_balance_async(self) -> Dict[str, Any]: ...

    def get_price_aggregation(
        self,
        item_name: str,
        game_id: str = "csgo",
        currency: str = "USD"
    ) -> Dict[str, Any]: ...

    async def get_price_aggregation_async(
        self,
        item_name: str,
        game_id: str = "csgo",
        currency: str = "USD"
    ) -> Dict[str, Any]: ...

    def cancel_offer(self, offer_id: str) -> Dict[str, Any]: ...
    async def cancel_offer_async(self, offer_id: str) -> Dict[str, Any]: ...
    def ping(self) -> bool: ... 