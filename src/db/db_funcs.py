"""
Модуль для работы с базой данных DMarket Trading Bot.

Содержит функции и классы для:
- Определения структуры базы данных
- Создания соединений с базой
- Добавления, обновления и извлечения данных из базы
"""

import logging
import sqlite3
import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

# Попытка импортировать конфигурацию из разных мест
try:
    from src.config.config import config
except ImportError:
    try:
        from config import config
    except ImportError:
        # Если нет доступа к конфигурации, создаем базовый объект
        import os
        
        class DefaultConfig:
            class database:
                DB_PATH = os.path.join("database.db")
                DB_ECHO = False
        
        config = DefaultConfig()
        logging.warning("Не удалось импортировать конфигурацию, используются значения по умолчанию")

# Настройка логирования
logger = logging.getLogger(__name__)

# Создание базового класса для моделей
Base = declarative_base()

# Определение моделей данных
class Item(Base):
    """Модель для хранения информации о предметах."""
    __tablename__ = 'items'
    
    id = Column(Integer, primary_key=True)
    item_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    market_hash_name = Column(String(255), nullable=False, index=True)
    game = Column(String(50), nullable=False, index=True)
    category = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Связь с ценами
    prices = relationship("ItemPrice", back_populates="item", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Item(id={self.id}, name='{self.name}', game='{self.game}')>"


class ItemPrice(Base):
    """Модель для хранения цен предметов."""
    __tablename__ = 'item_prices'
    
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False, index=True)
    price = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)
    source = Column(String(50), nullable=False, index=True)  # Источник цены (dmarket, target_site и т.д.)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    # Связь с предметом
    item = relationship("Item", back_populates="prices")
    
    def __repr__(self):
        return f"<ItemPrice(item_id={self.item_id}, price={self.price}, source='{self.source}')>"


class Trade(Base):
    """Модель для хранения информации о сделках."""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    buy_price = Column(Float, nullable=False)
    sell_price = Column(Float, nullable=False)
    profit = Column(Float, nullable=False)
    buy_source = Column(String(50), nullable=False)
    sell_source = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default='pending')  # pending, completed, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Связь с предметом
    item = relationship("Item")
    
    def __repr__(self):
        return f"<Trade(id={self.id}, profit={self.profit}, status='{self.status}')>"


class ArbitrageOpportunity(Base):
    """Модель для хранения арбитражных возможностей."""
    __tablename__ = 'arbitrage_opportunities'
    
    id = Column(Integer, primary_key=True)
    cycle = Column(String(500), nullable=False)  # Цикл обмена в формате "item1->item2->item3"
    profit_percentage = Column(Float, nullable=False)
    absolute_profit = Column(Float, nullable=False)
    detected_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<ArbitrageOpportunity(id={self.id}, profit_percentage={self.profit_percentage})>"


class Settings(Base):
    """Модель для хранения настроек приложения."""
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(500), nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<Settings(key='{self.key}', value='{self.value}')>"


# Создание подключения к БД
def get_engine():
    """
    Создает и возвращает движок SQLAlchemy для работы с базой данных.
    
    Returns:
        Engine: Движок SQLAlchemy
    """
    try:
        db_path = Path(config.database.DB_PATH)
    except (AttributeError, TypeError):
        db_path = Path("database.db")
        logger.warning(f"Не удалось получить путь к базе данных из конфигурации, используется значение по умолчанию: {db_path}")
    
    # Создание директории для БД, если она не существует
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Создаем строку подключения
    db_url = f'sqlite:///{db_path}'
    
    try:
        db_echo = config.database.DB_ECHO
    except (AttributeError, TypeError):
        db_echo = False
    
    # Создаем движок с пулом соединений
    engine = create_engine(
        db_url,
        echo=db_echo,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600
    )
    
    return engine


# Создание фабрики сессий
def get_session_factory():
    """
    Создает и возвращает фабрику сессий SQLAlchemy.
    
    Returns:
        sessionmaker: Фабрика сессий SQLAlchemy
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session


# Контекстный менеджер для работы с сессией
@contextmanager
def get_session():
    """
    Контекстный менеджер для безопасной работы с сессией SQLAlchemy.
    
    Yields:
        Session: Сессия SQLAlchemy
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при работе с БД: {e}")
        raise
    finally:
        session.close()


# Инициализация базы данных
def init_database():
    """
    Инициализирует базу данных, создавая все таблицы.
    
    Returns:
        bool: True, если инициализация успешна, иначе False
    """
    try:
        engine = get_engine()
        Base.metadata.create_all(engine)
        logger.info("База данных успешно инициализирована")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        return False


# Получение предмета по item_id
def get_item_by_item_id(item_id: str, session: Optional[Session] = None) -> Optional[Item]:
    """
    Получает предмет из базы данных по его item_id.
    
    Args:
        item_id: Идентификатор предмета
        session: Сессия SQLAlchemy (опционально)
    
    Returns:
        Item или None, если предмет не найден
    """
    created_session = session is None
    if created_session:
        session_factory = get_session_factory()
        session = session_factory()
    
    try:
        item = session.query(Item).filter(Item.item_id == item_id).first()
        return item
    except Exception as e:
        logger.error(f"Ошибка при получении предмета: {e}")
        return None
    finally:
        if created_session and session:
            session.close()


# Создание или обновление предмета
def create_or_update_item(item_data: Dict[str, Any], session: Optional[Session] = None) -> Item:
    """
    Создает новый предмет или обновляет существующий в базе данных.
    
    Args:
        item_data: Данные о предмете
        session: Сессия SQLAlchemy (опционально)
        
    Returns:
        Item: Созданный или обновленный предмет
    """
    created_session = session is None
    if created_session:
        session_factory = get_session_factory()
        session = session_factory()
    
    try:
        # Проверяем, существует ли предмет
        item = session.query(Item).filter(Item.item_id == item_data['item_id']).first()
        
        if item:
            # Обновляем существующий предмет
            for key, value in item_data.items():
                if hasattr(item, key) and key != 'id':
                    setattr(item, key, value)
            item.updated_at = datetime.datetime.utcnow()
        else:
            # Создаем новый предмет
            item = Item(**item_data)
            session.add(item)
        
        if created_session:
            session.commit()
        
        return item
    except Exception as e:
        if created_session:
            session.rollback()
        logger.error(f"Ошибка при создании/обновлении предмета: {e}")
        raise
    finally:
        if created_session and session:
            session.close()


# Добавление цены предмета
def add_item_price(
    item_id: int, 
    price: float, 
    source: str, 
    currency: str = 'USD', 
    session: Optional[Session] = None
) -> ItemPrice:
    """
    Добавляет новую цену для предмета.
    
    Args:
        item_id: ID предмета
        price: Цена предмета
        source: Источник цены (например, 'dmarket')
        currency: Валюта цены (по умолчанию 'USD')
        session: Сессия SQLAlchemy (опционально)
        
    Returns:
        ItemPrice: Созданная запись о цене предмета
    """
    created_session = session is None
    if created_session:
        session_factory = get_session_factory()
        session = session_factory()
    
    try:
        # Создаем запись о цене
        item_price = ItemPrice(
            item_id=item_id,
            price=price,
            currency=currency,
            source=source,
            timestamp=datetime.datetime.utcnow()
        )
        session.add(item_price)
        
        if created_session:
            session.commit()
            
        return item_price
    except Exception as e:
        if created_session:
            session.rollback()
        logger.error(f"Ошибка при добавлении цены предмета: {e}")
        raise
    finally:
        if created_session and session:
            session.close()


# Получение последней цены предмета
def get_latest_price(
    item_id: int, 
    source: str, 
    session: Optional[Session] = None
) -> Optional[float]:
    """
    Получает последнюю цену предмета из указанного источника.
    
    Args:
        item_id: ID предмета
        source: Источник цены
        session: Сессия SQLAlchemy (опционально)
        
    Returns:
        float: Последняя цена предмета или None, если цена не найдена
    """
    created_session = session is None
    if created_session:
        session_factory = get_session_factory()
        session = session_factory()
    
    try:
        # Получаем последнюю цену предмета
        item_price = session.query(ItemPrice).filter(
            ItemPrice.item_id == item_id,
            ItemPrice.source == source
        ).order_by(ItemPrice.timestamp.desc()).first()
        
        if item_price:
            return item_price.price
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении последней цены предмета: {e}")
        return None
    finally:
        if created_session and session:
            session.close()


# Добавление арбитражной возможности
def add_arbitrage_opportunity(
    cycle: str, 
    profit_percentage: float, 
    absolute_profit: float, 
    session: Optional[Session] = None
) -> ArbitrageOpportunity:
    """
    Добавляет новую арбитражную возможность в базу данных.
    
    Args:
        cycle: Цикл обмена в формате "item1->item2->item3"
        profit_percentage: Процент прибыли
        absolute_profit: Абсолютная прибыль
        session: Сессия SQLAlchemy (опционально)
        
    Returns:
        ArbitrageOpportunity: Созданная запись об арбитражной возможности
    """
    created_session = session is None
    if created_session:
        session_factory = get_session_factory()
        session = session_factory()
    
    try:
        # Создаем запись об арбитражной возможности
        opportunity = ArbitrageOpportunity(
            cycle=cycle,
            profit_percentage=profit_percentage,
            absolute_profit=absolute_profit,
            detected_at=datetime.datetime.utcnow(),
            is_active=True
        )
        session.add(opportunity)
        
        if created_session:
            session.commit()
            
        return opportunity
    except Exception as e:
        if created_session:
            session.rollback()
        logger.error(f"Ошибка при добавлении арбитражной возможности: {e}")
        raise
    finally:
        if created_session and session:
            session.close() 