"""
Модуль api_wrapper для обратной совместимости.
Направляет импорты в новое местоположение модуля.
"""

# Выводим предупреждение при импорте
import warnings
import sys
import importlib.util

warnings.warn(
    "Importing from api_wrapper.py at project root is deprecated. "
    "Use 'from src.api import api_wrapper' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Проверяем, есть ли уже модуль src.api.api_wrapper в кэше
api_module = None
try:
    # Пытаемся импортировать модуль напрямую
    spec = importlib.util.find_spec('src.api.api_wrapper')
    if spec:
        api_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api_module)
        
        # Копируем все атрибуты в текущий модуль
        for attr_name in dir(api_module):
            if not attr_name.startswith('__'):
                globals()[attr_name] = getattr(api_module, attr_name)
except Exception as e:
    warnings.warn(f"Failed to import from src.api.api_wrapper: {e}")
    # Заглушки основных классов и функций в случае ошибки
    class DMarketAPI:
        def __init__(self, *args, **kwargs): pass
        async def initialize(self): return True
        async def get_market_data(self, *args, **kwargs): return {"items": []}
    
    class APIError(Exception): pass
    class RateLimitError(APIError): pass
    class AuthenticationError(APIError): pass
    class NetworkError(APIError): pass
    
# При прямом запуске выводим сообщение о переносе модуля
if __name__ == "__main__":
    print("Этот модуль был перенесен в src/api/api_wrapper.py")
    print("Пожалуйста, обновите ваши импорты.") 