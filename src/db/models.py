"""
Модели данных для базы данных.

Этот модуль содержит классы моделей данных, используемые для представления 
сущностей в базе данных (пользователи, настройки, отслеживаемые предметы).
"""

import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from src.db.init_db import get_connection

logger = logging.getLogger(__name__)

@dataclass
class ArbitrageResult:
    """Модель результата поиска арбитражных возможностей."""
    item_name: str
    buy_price: float
    sell_price: float
    profit: float
    profit_percent: float
    game_id: str
    confidence: Optional[float] = None
    market_hash_name: Optional[str] = None
    volume_24h: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    @property
    def is_profitable(self) -> bool:
        """Проверяет, является ли арбитраж прибыльным."""
        return self.profit > 0 and self.profit_percent > 0

@dataclass
class User:
    """Модель пользователя."""
    chat_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row: tuple) -> 'User':
        """Создает модель пользователя из строки результата запроса."""
        return cls(
            id=row[0],
            chat_id=row[1],
            username=row[2],
            first_name=row[3],
            last_name=row[4],
            created_at=datetime.fromisoformat(row[5]) if row[5] else None,
            updated_at=datetime.fromisoformat(row[6]) if row[6] else None
        )
    
    @classmethod
    def get_by_chat_id(cls, chat_id: int) -> Optional['User']:
        """Получает пользователя по его chat_id."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            
            if row:
                return cls.from_row(row)
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя с chat_id {chat_id}: {e}")
            return None
    
    @classmethod
    def create_or_update(cls, user: 'User') -> Optional['User']:
        """Создает или обновляет пользователя в базе данных."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Проверяем, существует ли пользователь
            cursor.execute(
                "SELECT id FROM users WHERE chat_id = ?", 
                (user.chat_id,)
            )
            existing_user = cursor.fetchone()
            
            if existing_user:
                # Обновляем существующего пользователя
                cursor.execute(
                    """
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE chat_id = ?
                    """,
                    (user.username, user.first_name, user.last_name, user.chat_id)
                )
                user.id = existing_user[0]
            else:
                # Создаем нового пользователя
                cursor.execute(
                    """
                    INSERT INTO users (chat_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user.chat_id, user.username, user.first_name, user.last_name)
                )
                user.id = cursor.lastrowid
            
            conn.commit()
            return user
        except Exception as e:
            logger.error(f"Ошибка при создании/обновлении пользователя: {e}")
            if conn:
                conn.rollback()
            return None

@dataclass
class UserSetting:
    """Модель настройки пользователя."""
    user_id: int
    setting_key: str
    setting_value: str
    id: Optional[int] = None
    
    @classmethod
    def from_row(cls, row: tuple) -> 'UserSetting':
        """Создает модель настройки пользователя из строки результата запроса."""
        return cls(
            id=row[0],
            user_id=row[1],
            setting_key=row[2],
            setting_value=row[3]
        )
    
    @classmethod
    def get_settings(cls, user_id: int) -> Dict[str, str]:
        """Получает все настройки пользователя."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_settings WHERE user_id = ?", 
                (user_id,)
            )
            rows = cursor.fetchall()
            
            return {row[2]: row[3] for row in rows}
        except Exception as e:
            logger.error(f"Ошибка при получении настроек пользователя {user_id}: {e}")
            return {}
    
    @classmethod
    def set_setting(cls, user_id: int, key: str, value: str) -> bool:
        """Устанавливает настройку пользователя."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO user_settings (user_id, setting_key, setting_value)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, setting_key) 
                DO UPDATE SET setting_value = excluded.setting_value
                """,
                (user_id, key, value)
            )
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка при установке настройки {key} для пользователя {user_id}: {e}")
            if conn:
                conn.rollback()
            return False

@dataclass
class TrackedItem:
    """Модель отслеживаемого предмета."""
    user_id: int
    item_name: str
    market_hash_name: str
    target_price: Optional[float] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row: tuple) -> 'TrackedItem':
        """Создает модель отслеживаемого предмета из строки результата запроса."""
        return cls(
            id=row[0],
            user_id=row[1],
            item_name=row[2],
            market_hash_name=row[3],
            target_price=row[4],
            created_at=datetime.fromisoformat(row[5]) if row[5] else None
        )
    
    @classmethod
    def get_items_by_user(cls, user_id: int) -> List['TrackedItem']:
        """Получает все отслеживаемые предметы пользователя."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tracked_items WHERE user_id = ?", 
                (user_id,)
            )
            rows = cursor.fetchall()
            
            return [cls.from_row(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка при получении отслеживаемых предметов пользователя {user_id}: {e}")
            return []
    
    @classmethod
    def add_item(cls, item: 'TrackedItem') -> Optional['TrackedItem']:
        """Добавляет предмет для отслеживания."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO tracked_items (user_id, item_name, market_hash_name, target_price)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, market_hash_name) 
                DO UPDATE SET target_price = excluded.target_price
                """,
                (item.user_id, item.item_name, item.market_hash_name, item.target_price)
            )
            
            item.id = cursor.lastrowid
            conn.commit()
            return item
        except Exception as e:
            logger.error(f"Ошибка при добавлении предмета для отслеживания: {e}")
            if conn:
                conn.rollback()
            return None
    
    @classmethod
    def remove_item(cls, user_id: int, market_hash_name: str) -> bool:
        """Удаляет предмет из отслеживаемых."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM tracked_items WHERE user_id = ? AND market_hash_name = ?",
                (user_id, market_hash_name)
            )
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка при удалении предмета из отслеживаемых: {e}")
            if conn:
                conn.rollback()
            return False 