#!/usr/bin/env python
"""
Модуль для управления административными функциями Telegram бота.

Этот модуль содержит функции для:
- Проверки административных прав пользователей
- Получения списка администраторов
- Обработки административных запросов
- Мониторинга доступа к административным функциям
"""

import os
import logging
import time
import json
import hashlib
from functools import lru_cache, wraps
from typing import List, Tuple, Optional, Dict, Union, Any, Set, Callable
from datetime import datetime, timedelta

# Настройка логгера
logger = logging.getLogger(__name__)

# Константы для настройки безопасности
MAX_FAILED_AUTH_ATTEMPTS = 5  # Максимальное количество неудачных попыток аутентификации
LOCKOUT_PERIOD = 300  # Период блокировки в секундах (5 минут)
ADMIN_ACCESS_LOG_FILE = "logs/admin_access.log"  # Файл журнала доступа

class AdminManager:
    """
    Класс для управления административными функциями бота.
    Реализует проверку прав доступа, кэширование списка администраторов,
    мониторинг попыток доступа и другие функции администрирования.
    """
    
    def __init__(self):
        """Инициализация менеджера администраторов."""
        # Время последнего обновления кэша админов
        self._last_admin_cache_update = 0
        # Кэш списка ID администраторов
        self._admin_ids_cache: List[int] = []
        # Время жизни кэша в секундах (10 минут)
        self._cache_ttl = 600
        # Счетчик неудачных попыток аутентификации по user_id
        self._failed_auth_attempts: Dict[int, int] = {}
        # Время последней неудачной попытки по user_id
        self._last_failed_attempt: Dict[int, float] = {}
        # Заблокированные пользователи (user_id -> время разблокировки)
        self._locked_users: Dict[int, float] = {}
        # Журнал доступа к административным функциям
        self._access_log: List[Dict[str, Any]] = []
        # Список защищенных функций, требующих административных прав
        self._protected_functions: Set[str] = set()
        # Обновляем кэш сразу при инициализации
        self._update_admin_cache()
        # Создаем директорию для логов, если её нет
        os.makedirs(os.path.dirname(ADMIN_ACCESS_LOG_FILE), exist_ok=True)
    
    def _update_admin_cache(self) -> None:
        """
        Обновляет кэш списка администраторов из переменных окружения.
        """
        current_time = time.time()
        
        # Обновляем кэш только если истек срок его жизни
        if current_time - self._last_admin_cache_update < self._cache_ttl and self._admin_ids_cache:
            return
            
        # Получаем список админских ID из переменных окружения
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        
        # Очищаем текущий кэш
        self._admin_ids_cache = []
        
        # Если список не задан, логируем предупреждение
        if not admin_ids_str:
            logger.warning("ADMIN_IDS не задан, доступ к административным функциям будет запрещен")
            return
            
        # Преобразуем строку с ID в список
        for id_str in admin_ids_str.split(','):
            id_str = id_str.strip()
            try:
                if id_str:
                    self._admin_ids_cache.append(int(id_str))
            except ValueError:
                logger.warning(f"Некорректный ID администратора: {id_str}")
        
        # Обновляем время последнего обновления кэша
        self._last_admin_cache_update = current_time
        logger.debug(f"Обновлен кэш списка администраторов: {self._admin_ids_cache}")
    
    def _check_lockout(self, user_id: int) -> bool:
        """
        Проверяет, не заблокирован ли пользователь из-за превышения 
        максимального количества неудачных попыток аутентификации.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            bool: True если пользователь заблокирован, иначе False
        """
        current_time = time.time()
        
        # Проверяем, есть ли пользователь в списке заблокированных
        if user_id in self._locked_users:
            lockout_until = self._locked_users[user_id]
            # Если время блокировки прошло, разблокируем пользователя
            if current_time > lockout_until:
                del self._locked_users[user_id]
                self._failed_auth_attempts[user_id] = 0
                logger.info(f"Пользователь {user_id} разблокирован")
                return False
            # Иначе сообщаем, что пользователь всё ещё заблокирован
            remaining_time = int(lockout_until - current_time)
            logger.warning(f"Попытка доступа от заблокированного пользователя {user_id}, осталось {remaining_time} секунд")
            return True
        
        return False
    
    def _record_failed_attempt(self, user_id: int) -> None:
        """
        Записывает неудачную попытку аутентификации и блокирует пользователя,
        если превышено максимальное количество попыток.
        
        Args:
            user_id: ID пользователя Telegram
        """
        current_time = time.time()
        
        # Инициализируем счетчик, если это первая попытка
        if user_id not in self._failed_auth_attempts:
            self._failed_auth_attempts[user_id] = 0
        
        # Увеличиваем счетчик неудачных попыток
        self._failed_auth_attempts[user_id] += 1
        self._last_failed_attempt[user_id] = current_time
        
        # Проверяем, не превышено ли максимальное количество попыток
        if self._failed_auth_attempts[user_id] >= MAX_FAILED_AUTH_ATTEMPTS:
            # Блокируем пользователя на указанное время
            lockout_until = current_time + LOCKOUT_PERIOD
            self._locked_users[user_id] = lockout_until
            logger.warning(f"Пользователь {user_id} заблокирован на {LOCKOUT_PERIOD} секунд из-за превышения лимита попыток")
            
            # Логируем попытку взлома
            self._log_access_attempt(user_id, "AUTH_LOCKOUT", False, 
                                    details=f"Превышен лимит неудачных попыток: {MAX_FAILED_AUTH_ATTEMPTS}")
    
    def _reset_failed_attempts(self, user_id: int) -> None:
        """
        Сбрасывает счетчик неудачных попыток для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
        """
        if user_id in self._failed_auth_attempts:
            self._failed_auth_attempts[user_id] = 0
    
    def _log_access_attempt(self, user_id: int, action: str, success: bool, details: Optional[str] = None) -> None:
        """
        Записывает попытку доступа к административным функциям в журнал.
        
        Args:
            user_id: ID пользователя Telegram
            action: Тип действия или запрашиваемая функция
            success: Результат попытки (успех/неудача)
            details: Дополнительные детали о попытке
        """
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "user_id": user_id,
            "action": action,
            "success": success,
            "details": details
        }
        
        # Добавляем запись в кэш журнала
        self._access_log.append(log_entry)
        
        # Ограничиваем размер кэша журнала
        if len(self._access_log) > 1000:
            self._access_log = self._access_log[-1000:]
        
        # Записываем в файл журнала
        try:
            with open(ADMIN_ACCESS_LOG_FILE, 'a') as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Не удалось записать в журнал доступа: {e}")
    
    def is_admin(self, user_id: int) -> bool:
        """
        Проверяет, является ли пользователь администратором бота.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            bool: True если пользователь является администратором, иначе False
        """
        # Проверяем, не заблокирован ли пользователь
        if self._check_lockout(user_id):
            self._log_access_attempt(user_id, "ADMIN_CHECK", False, "Пользователь заблокирован")
            return False
        
        # Обновляем кэш, если необходимо
        self._update_admin_cache()
        
        # Проверяем наличие ID в списке администраторов
        is_admin_user = user_id in self._admin_ids_cache
        
        # Логируем результат проверки 
        if is_admin_user:
            logger.debug(f"Пользователь {user_id} имеет права администратора")
            self._reset_failed_attempts(user_id)
            self._log_access_attempt(user_id, "ADMIN_CHECK", True)
        else:
            logger.warning(f"Пользователь {user_id} не имеет прав администратора")
            self._record_failed_attempt(user_id)
            self._log_access_attempt(user_id, "ADMIN_CHECK", False, "Не найден в списке администраторов")
            
        return is_admin_user
    
    def protect(self, func: Callable) -> Callable:
        """
        Декоратор для защиты функций, требующих административные права.
        
        Args:
            func: Функция, которую нужно защитить
            
        Returns:
            Callable: Защищенная функция
        """
        @wraps(func)
        async def wrapper(message, *args, **kwargs):
            user_id = message.from_user.id if hasattr(message, 'from_user') else None
            
            if not user_id:
                logger.warning(f"Попытка доступа к {func.__name__} без идентификации пользователя")
                return None
                
            if not self.is_admin(user_id):
                logger.warning(f"Отказ в доступе к {func.__name__} для пользователя {user_id}")
                # Отправляем сообщение о недостаточных правах
                await message.answer("⚠️ У вас недостаточно прав для доступа к этой функции.")
                return None
                
            logger.info(f"Доступ к {func.__name__} разрешен для пользователя {user_id}")
            return await func(message, *args, **kwargs)
            
        # Регистрируем функцию как защищенную
        self._protected_functions.add(func.__name__)
        return wrapper
    
    def get_access_log(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Возвращает журнал доступа к административным функциям за указанный период.
        
        Args:
            hours: Период в часах, за который нужно вернуть журнал
            
        Returns:
            List[Dict[str, Any]]: Список записей журнала
        """
        if not self._access_log:
            return []
            
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        return [entry for entry in self._access_log if entry["timestamp"] >= cutoff_time]
    
    @property
    def admin_ids(self) -> List[int]:
        """
        Возвращает список ID администраторов.
        
        Returns:
            List[int]: Список ID администраторов
        """
        # Обновляем кэш, если необходимо
        self._update_admin_cache()
        return self._admin_ids_cache.copy()
    
    def force_update_cache(self) -> None:
        """
        Принудительно обновляет кэш списка администраторов.
        Полезно после изменения переменных окружения.
        """
        # Сбрасываем время последнего обновления
        self._last_admin_cache_update = 0
        # Обновляем кэш
        self._update_admin_cache()
        logger.info("Кэш списка администраторов принудительно обновлен")
    
    def get_security_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику безопасности.
        
        Returns:
            Dict[str, Any]: Статистика безопасности
        """
        return {
            "locked_users": len(self._locked_users),
            "failed_attempts": sum(self._failed_auth_attempts.values()),
            "access_attempts": len(self._access_log),
            "protected_functions": list(self._protected_functions),
            "last_cache_update": datetime.fromtimestamp(self._last_admin_cache_update).isoformat()
        }
    
    def reset_security(self) -> None:
        """
        Сбрасывает все блокировки и счетчики неудачных попыток.
        """
        self._failed_auth_attempts = {}
        self._last_failed_attempt = {}
        self._locked_users = {}
        logger.info("Сброшены все блокировки и счетчики неудачных попыток")
    
    def verify_admin_token(self, token: str) -> bool:
        """
        Проверяет административный токен для альтернативного способа аутентификации.
        
        Args:
            token: Административный токен
            
        Returns:
            bool: True если токен верный, иначе False
        """
        admin_token = os.getenv("ADMIN_TOKEN", "")
        if not admin_token:
            logger.warning("ADMIN_TOKEN не задан, аутентификация по токену невозможна")
            return False
        
        # Хешируем токен для сравнения (лучше хранить токен в хешированном виде)
        hashed_input = hashlib.sha256(token.encode()).hexdigest()
        hashed_token = hashlib.sha256(admin_token.encode()).hexdigest()
        
        return hashed_input == hashed_token

# Создаем глобальный экземпляр AdminManager для использования во всем приложении
admin_manager = AdminManager()

# Функция-обертка для проверки админских прав (для удобства использования)
def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором бота.
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        bool: True если пользователь является администратором, иначе False
    """
    return admin_manager.is_admin(user_id)

# Функция для получения списка ID администраторов
def get_admin_ids() -> List[int]:
    """
    Возвращает список ID администраторов.
    
    Returns:
        List[int]: Список ID администраторов
    """
    return admin_manager.admin_ids

# Функция для принудительного обновления кэша
def update_admin_cache() -> None:
    """
    Принудительно обновляет кэш списка администраторов.
    """
    admin_manager.force_update_cache()

# Декоратор для защиты функций, требующих административные права
def admin_required(func: Callable) -> Callable:
    """
    Декоратор для защиты функций, требующих административные права.
    
    Args:
        func: Функция, которую нужно защитить
        
    Returns:
        Callable: Защищенная функция
    """
    return admin_manager.protect(func)

# Функция для получения журнала доступа
def get_admin_access_log(hours: int = 24) -> List[Dict[str, Any]]:
    """
    Возвращает журнал доступа к административным функциям за указанный период.
    
    Args:
        hours: Период в часах, за который нужно вернуть журнал
        
    Returns:
        List[Dict[str, Any]]: Список записей журнала
    """
    return admin_manager.get_access_log(hours)

# Функция для получения статистики безопасности
def get_security_stats() -> Dict[str, Any]:
    """
    Возвращает статистику безопасности.
    
    Returns:
        Dict[str, Any]: Статистика безопасности
    """
    return admin_manager.get_security_stats()

# Функция для сброса блокировок и счетчиков
def reset_security() -> None:
    """
    Сбрасывает все блокировки и счетчики неудачных попыток.
    """
    admin_manager.reset_security() 