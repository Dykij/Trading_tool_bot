"""
Модуль для инициализации базы данных.

Этот модуль содержит функции для создания и настройки базы данных SQL,
а также для установления и закрытия соединения с базой данных.
"""

import os
import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from src.config.config import Config

logger = logging.getLogger(__name__)

# Глобальная переменная для соединения с базой данных
_db_connection: Optional[sqlite3.Connection] = None

async def init_db() -> None:
    """
    Инициализирует соединение с базой данных и создает необходимые таблицы,
    если они еще не существуют.
    """
    global _db_connection
    
    try:
        # Проверяем, существует ли директория для файла базы данных
        db_path = Path(Config.DB_PATH)
        if not db_path.parent.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Устанавливаем соединение с базой данных
        _db_connection = sqlite3.connect(str(db_path))
        
        # Настраиваем соединение
        _db_connection.execute("PRAGMA foreign_keys = ON")
        
        # Создаем необходимые таблицы
        _db_connection.executescript("""
            -- Таблица пользователей
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Таблица настроек пользователей
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, setting_key)
            );
            
            -- Таблица для отслеживания предметов
            CREATE TABLE IF NOT EXISTS tracked_items (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                market_hash_name TEXT NOT NULL,
                target_price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, market_hash_name)
            );
        """)
        
        logger.info(f"База данных инициализирована: {Config.DB_PATH}")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        raise

async def close_db() -> None:
    """Закрывает соединение с базой данных."""
    global _db_connection
    
    if _db_connection:
        _db_connection.close()
        _db_connection = None
        logger.info("Соединение с базой данных закрыто")

def get_connection() -> sqlite3.Connection:
    """
    Возвращает соединение с базой данных.
    
    Returns:
        sqlite3.Connection: Соединение с базой данных
        
    Raises:
        RuntimeError: Если соединение не инициализировано
    """
    if _db_connection is None:
        raise RuntimeError("Соединение с базой данных не инициализировано. Вызовите init_db() сначала.")
    
    return _db_connection

# Если файл запускается напрямую, инициализируем базу данных
if __name__ == "__main__":
    asyncio.run(init_db())
    logger.info("База данных успешно инициализирована") 