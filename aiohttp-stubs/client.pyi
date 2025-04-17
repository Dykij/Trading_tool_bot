"""Type stubs for aiohttp.client module."""

from typing import Any, AsyncContextManager, Awaitable, Dict, List, Optional, Union

class ClientSession:
    def __init__(self, 
                 *,
                 timeout: Optional[Any] = None,
                 headers: Optional[Dict[str, str]] = None,
                 **kwargs: Any) -> None: ...
    
    async def __aenter__(self) -> 'ClientSession': ...
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...
    
    def get(self, url: str, 
            *,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: Optional[Any] = None,
            **kwargs: Any) -> AsyncContextManager[ClientResponse]: ...
    
    def post(self, url: str, 
             *,
             json: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None,
             timeout: Optional[Any] = None,
             **kwargs: Any) -> AsyncContextManager[ClientResponse]: ...
    
    @property
    def closed(self) -> bool: ...
    
    async def close(self) -> None: ...

class ClientResponse:
    status: int
    headers: Dict[str, str]
    
    async def text(self) -> str: ...
    async def json(self) -> Any: ...
    
    def raise_for_status(self) -> None: ...

class ClientError(Exception): ...
class ClientConnectionError(ClientError): ...
class ClientTimeoutError(ClientError): ...

class ClientTimeout:
def __init__(self, total: Optional[float] = None, **kwargs: Any) -> None: ... 