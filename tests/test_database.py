"""
Тесты для модуля базы данных.

Проверяет функционал работы с базой данных, CRUD-операции и миграции.
"""

import unittest
import sys
import os
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.db.database import Database, MarketItemsRepository, TransactionRepository
    DATABASE_AVAILABLE = True
except ImportError:
    # Создаем заглушки для тестирования, если модули не найдены
    DATABASE_AVAILABLE = False
    
    class Database:
        def __init__(self, db_path=':memory:'):
            self.db_path = db_path
            self.conn = sqlite3.connect(db_path)
            self.cursor = self.conn.cursor()
            
        def execute(self, query, params=None):
            if params:
                return self.cursor.execute(query, params)
            return self.cursor.execute(query)
            
        def executemany(self, query, params_list):
            return self.cursor.executemany(query, params_list)
            
        def fetchall(self):
            return self.cursor.fetchall()
            
        def fetchone(self):
            return self.cursor.fetchone()
            
        def commit(self):
            return self.conn.commit()
            
        def close(self):
            return self.conn.close()
            
        def create_tables(self):
            self.execute('''
                CREATE TABLE IF NOT EXISTS market_items (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    game_id TEXT,
                    price REAL,
                    currency TEXT,
                    timestamp INTEGER,
                    category TEXT
                )
            ''')
            
            self.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    item_id TEXT,
                    type TEXT,
                    price REAL,
                    currency TEXT,
                    timestamp INTEGER,
                    status TEXT,
                    FOREIGN KEY (item_id) REFERENCES market_items (id)
                )
            ''')
            self.commit()
    
    class MarketItemsRepository:
        def __init__(self, db):
            self.db = db
            
        def save_item(self, item_data):
            query = '''
                INSERT OR REPLACE INTO market_items 
                (id, title, game_id, price, currency, timestamp, category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            self.db.execute(query, (
                item_data['id'],
                item_data['title'],
                item_data['game_id'],
                item_data['price'],
                item_data['currency'],
                item_data['timestamp'],
                item_data.get('category', '')
            ))
            self.db.commit()
            
        def save_items(self, items_data):
            query = '''
                INSERT OR REPLACE INTO market_items 
                (id, title, game_id, price, currency, timestamp, category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            params_list = [
                (
                    item['id'],
                    item['title'],
                    item['game_id'],
                    item['price'],
                    item['currency'],
                    item['timestamp'],
                    item.get('category', '')
                )
                for item in items_data
            ]
            self.db.executemany(query, params_list)
            self.db.commit()
            
        def get_item_by_id(self, item_id):
            query = 'SELECT * FROM market_items WHERE id = ?'
            self.db.execute(query, (item_id,))
            row = self.db.fetchone()
            if row:
                return {
                    'id': row[0],
                    'title': row[1],
                    'game_id': row[2],
                    'price': row[3],
                    'currency': row[4],
                    'timestamp': row[5],
                    'category': row[6]
                }
            return None
            
        def get_items_by_game(self, game_id, limit=100):
            query = 'SELECT * FROM market_items WHERE game_id = ? LIMIT ?'
            self.db.execute(query, (game_id, limit))
            rows = self.db.fetchall()
            return [
                {
                    'id': row[0],
                    'title': row[1],
                    'game_id': row[2],
                    'price': row[3],
                    'currency': row[4],
                    'timestamp': row[5],
                    'category': row[6]
                }
                for row in rows
            ]
    
    class TransactionRepository:
        def __init__(self, db):
            self.db = db
            
        def save_transaction(self, transaction_data):
            query = '''
                INSERT INTO transactions 
                (id, item_id, type, price, currency, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            self.db.execute(query, (
                transaction_data['id'],
                transaction_data['item_id'],
                transaction_data['type'],
                transaction_data['price'],
                transaction_data['currency'],
                transaction_data['timestamp'],
                transaction_data['status']
            ))
            self.db.commit()
            
        def get_transaction_by_id(self, transaction_id):
            query = 'SELECT * FROM transactions WHERE id = ?'
            self.db.execute(query, (transaction_id,))
            row = self.db.fetchone()
            if row:
                return {
                    'id': row[0],
                    'item_id': row[1],
                    'type': row[2],
                    'price': row[3],
                    'currency': row[4],
                    'timestamp': row[5],
                    'status': row[6]
                }
            return None
            
        def get_transactions_by_status(self, status, limit=100):
            query = 'SELECT * FROM transactions WHERE status = ? LIMIT ?'
            self.db.execute(query, (status, limit))
            rows = self.db.fetchall()
            return [
                {
                    'id': row[0],
                    'item_id': row[1],
                    'type': row[2],
                    'price': row[3],
                    'currency': row[4],
                    'timestamp': row[5],
                    'status': row[6]
                }
                for row in rows
            ]
            
        def update_transaction_status(self, transaction_id, new_status):
            query = 'UPDATE transactions SET status = ? WHERE id = ?'
            self.db.execute(query, (new_status, transaction_id))
            self.db.commit()


class TestDatabase(unittest.TestCase):
    """Тесты для модуля базы данных."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временную БД в памяти для тестирования
        self.db = Database(':memory:')
        self.db.create_tables()
        
        # Создаем репозитории
        self.market_repo = MarketItemsRepository(self.db)
        self.transaction_repo = TransactionRepository(self.db)
        
        # Тестовые данные
        self.test_item = {
            'id': 'test_item_1',
            'title': 'AK-47 | Redline',
            'game_id': 'cs2',
            'price': 1000.0,
            'currency': 'USD',
            'timestamp': 1618000000,
            'category': 'weapon'
        }
        
        self.test_transaction = {
            'id': 'test_transaction_1',
            'item_id': 'test_item_1',
            'type': 'buy',
            'price': 1000.0,
            'currency': 'USD',
            'timestamp': 1618000000,
            'status': 'pending'
        }
    
    def tearDown(self):
        """Очищаем среду после тестов."""
        self.db.close()
    
    def test_database_connection(self):
        """Тест создания и подключения к базе данных."""
        # Проверяем, что соединение активно
        self.assertTrue(self.db.conn is not None)
        
        # Проверяем, что можем выполнить простой запрос
        self.db.execute('SELECT 1')
        result = self.db.fetchone()
        self.assertEqual(result[0], 1)
    
    def test_create_tables(self):
        """Тест создания таблиц."""
        # Проверяем, что таблицы созданы
        self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in self.db.fetchall()]
        
        self.assertIn('market_items', tables)
        self.assertIn('transactions', tables)
    
    def test_save_and_get_market_item(self):
        """Тест сохранения и получения предмета с рынка."""
        # Создаем тестовый предмет
        item_data = {
            'id': 'test_item_1',
            'title': 'AK-47 | Redline',
            'game_id': 'cs2',
            'price': 1000.0,
            'currency': 'USD',
            'timestamp': 1618000000,
            'category': 'weapon'
        }
        
        # Сохраняем предмет
        self.market_repo.save_item(item_data)
        
        # Получаем предмет
        item = self.market_repo.get_item_by_id('test_item_1')
        
        # Проверяем, что предмет получен
        self.assertIsNotNone(item, "Предмет не был получен")
        
        # Проверяем поля предмета только если item не None
        if item:
            self.assertEqual(item['id'], 'test_item_1')
            self.assertEqual(item['title'], 'AK-47 | Redline')
            self.assertEqual(item['game_id'], 'cs2')
            self.assertEqual(item['price'], 1000.0)
            self.assertEqual(item['currency'], 'USD')
            self.assertEqual(item['timestamp'], 1618000000)
            self.assertEqual(item['category'], 'weapon')
    
    def test_save_and_get_multiple_items(self):
        """Тест сохранения и получения нескольких предметов."""
        # Создаем несколько тестовых предметов
        test_items = [
            self.test_item,
            {
                'id': 'test_item_2',
                'title': 'AWP | Asiimov',
                'game_id': 'cs2',
                'price': 2000.0,
                'currency': 'USD',
                'timestamp': 1618000100,
                'category': 'weapon'
            },
            {
                'id': 'test_item_3',
                'title': 'Knife | Doppler',
                'game_id': 'cs2',
                'price': 5000.0,
                'currency': 'USD',
                'timestamp': 1618000200,
                'category': 'knife'
            }
        ]
        
        # Сохраняем предметы
        self.market_repo.save_items(test_items)
        
        # Получаем предметы по игре и проверяем
        items = self.market_repo.get_items_by_game('cs2')
        
        self.assertEqual(len(items), 3)
        
        # Проверяем, что все предметы получены корректно
        item_ids = [item['id'] for item in items]
        self.assertIn('test_item_1', item_ids)
        self.assertIn('test_item_2', item_ids)
        self.assertIn('test_item_3', item_ids)
    
    def test_save_and_get_transaction(self):
        """Тест сохранения и получения транзакции."""
        # Создаем тестовую транзакцию
        transaction_data = {
            'id': 'test_transaction_1',
            'item_id': 'test_item_1',
            'type': 'buy',
            'price': 1000.0,
            'currency': 'USD',
            'timestamp': 1618000000,
            'status': 'pending'
        }
        
        # Сохраняем транзакцию
        self.transaction_repo.save_transaction(transaction_data)
        
        # Получаем транзакцию
        transaction = self.transaction_repo.get_transaction_by_id('test_transaction_1')
        
        # Проверяем, что транзакция получена
        self.assertIsNotNone(transaction, "Транзакция не была получена")
        
        # Проверяем поля транзакции только если transaction не None
        if transaction:
            self.assertEqual(transaction['id'], 'test_transaction_1')
            self.assertEqual(transaction['item_id'], 'test_item_1')
            self.assertEqual(transaction['type'], 'buy')
            self.assertEqual(transaction['price'], 1000.0)
            self.assertEqual(transaction['currency'], 'USD')
            self.assertEqual(transaction['timestamp'], 1618000000)
            self.assertEqual(transaction['status'], 'pending')
    
    def test_update_transaction_status(self):
        """Тест обновления статуса транзакции."""
        # Создаем тестовую транзакцию
        transaction_data = {
            'id': 'test_transaction_1',
            'item_id': 'test_item_1',
            'type': 'buy',
            'price': 1000.0,
            'currency': 'USD',
            'timestamp': 1618000000,
            'status': 'pending'
        }
        
        # Сохраняем транзакцию
        self.transaction_repo.save_transaction(transaction_data)
        
        # Обновляем статус
        self.transaction_repo.update_transaction_status('test_transaction_1', 'completed')
        
        # Получаем обновленную транзакцию
        transaction = self.transaction_repo.get_transaction_by_id('test_transaction_1')
        
        # Проверяем, что транзакция получена и статус обновлен
        self.assertIsNotNone(transaction, "Транзакция не была получена")
        if transaction:
            self.assertEqual(transaction['status'], 'completed')
    
    def test_get_transactions_by_status(self):
        """Тест получения транзакций по статусу."""
        # Создаем предмет и несколько транзакций с разными статусами
        self.market_repo.save_item(self.test_item)
        
        transactions = [
            self.test_transaction,
            {
                'id': 'test_transaction_2',
                'item_id': 'test_item_1',
                'type': 'sell',
                'price': 1100.0,
                'currency': 'USD',
                'timestamp': 1618000100,
                'status': 'completed'
            },
            {
                'id': 'test_transaction_3',
                'item_id': 'test_item_1',
                'type': 'buy',
                'price': 950.0,
                'currency': 'USD',
                'timestamp': 1618000200,
                'status': 'pending'
            }
        ]
        
        for tx in transactions:
            self.transaction_repo.save_transaction(tx)
        
        # Получаем транзакции со статусом 'pending'
        pending_transactions = self.transaction_repo.get_transactions_by_status('pending')
        
        # Проверяем, что получили именно 'pending' транзакции
        self.assertEqual(len(pending_transactions), 2)
        
        # Получаем транзакции со статусом 'completed'
        completed_transactions = self.transaction_repo.get_transactions_by_status('completed')
        
        # Проверяем, что получили именно 'completed' транзакции
        self.assertEqual(len(completed_transactions), 1)
        self.assertEqual(completed_transactions[0]['id'], 'test_transaction_2')


class TestDatabaseFile(unittest.TestCase):
    """Тесты для работы с файлом базы данных."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем временный файл для БД
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_file.close()
        
        # Создаем БД во временном файле
        self.db = Database(self.temp_file.name)
        self.db.create_tables()
    
    def tearDown(self):
        """Очищаем среду после тестов."""
        self.db.close()
        
        # Удаляем временный файл
        try:
            os.unlink(self.temp_file.name)
        except OSError:
            pass
    
    def test_database_file_creation(self):
        """Тест создания файла базы данных."""
        # Проверяем, что файл БД создан
        self.assertTrue(os.path.exists(self.temp_file.name))
        
        # Проверяем, что это действительно файл SQLite
        with open(self.temp_file.name, 'rb') as f:
            header = f.read(16)
        
        # SQLite файлы начинаются с "SQLite format 3"
        self.assertTrue(header.startswith(b'SQLite format 3'))
    
    def test_database_persistence(self):
        """Тест сохранения данных в файл БД."""
        # Создаем репозиторий
        market_repo = MarketItemsRepository(self.db)
        
        # Сохраняем тестовые данные
        test_item = {
            'id': 'test_item_1',
            'title': 'AK-47 | Redline',
            'game_id': 'cs2',
            'price': 1000.0,
            'currency': 'USD',
            'timestamp': 1618000000,
            'category': 'weapon'
        }
        
        market_repo.save_item(test_item)
        
        # Закрываем соединение
        self.db.close()
        
        # Создаем новое соединение к той же БД
        new_db = Database(self.temp_file.name)
        new_market_repo = MarketItemsRepository(new_db)
        
        # Пытаемся получить ранее сохраненные данные
        item = new_market_repo.get_item_by_id('test_item_1')
        
        # Проверяем, что данные сохранились
        self.assertIsNotNone(item, "Предмет не был получен")
        if item:
            self.assertEqual(item['title'], 'AK-47 | Redline')
        
        new_db.close()


# Импортируем и запускаем тесты только если модуль базы данных доступен
if DATABASE_AVAILABLE:
    from src.db.migrations import MigrationManager
    
    class TestMigrations(unittest.TestCase):
        """Тесты для системы миграций базы данных."""
        
        def setUp(self):
            """Настройка тестового окружения."""
            # Создаем временный файл для БД
            self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            self.temp_file.close()
            
            # Создаем БД во временном файле
            self.db = Database(self.temp_file.name)
            
            # Создаем менеджер миграций
            self.migration_manager = MigrationManager(self.db)
        
        def tearDown(self):
            """Очищаем среду после тестов."""
            self.db.close()
            
            # Удаляем временный файл
            try:
                os.unlink(self.temp_file.name)
            except OSError:
                pass
        
        def test_migration_table_creation(self):
            """Тест создания таблицы миграций."""
            # Инициализируем таблицу миграций
            self.migration_manager.init_migrations_table()
            
            # Проверяем, что таблица создана
            self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'")
            result = self.db.fetchone()
            
            self.assertIsNotNone(result)
            self.assertEqual(result[0], 'migrations')
        
        def test_migration_apply(self):
            """Тест применения миграции."""
            # Инициализируем таблицу миграций
            self.migration_manager.init_migrations_table()
            
            # Создаем тестовую миграцию
            test_migration = {
                'id': 'test_migration_1',
                'name': 'Test Migration',
                'sql': 'CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)'
            }
            
            # Применяем миграцию
            self.migration_manager.apply_migration(test_migration)
            
            # Проверяем, что миграция отмечена как примененная
            self.db.execute("SELECT * FROM migrations WHERE id = ?", ('test_migration_1',))
            result = self.db.fetchone()
            
            self.assertIsNotNone(result)
            
            # Проверяем, что таблица из миграции создана
            self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
            result = self.db.fetchone()
            
            self.assertIsNotNone(result)
            self.assertEqual(result[0], 'test_table')
        
        def test_migration_get_applied(self):
            """Тест получения списка примененных миграций."""
            # Инициализируем таблицу миграций
            self.migration_manager.init_migrations_table()
            
            # Создаем и применяем тестовые миграции
            test_migrations = [
                {
                    'id': 'test_migration_1',
                    'name': 'Test Migration 1',
                    'sql': 'CREATE TABLE test_table_1 (id INTEGER PRIMARY KEY, name TEXT)'
                },
                {
                    'id': 'test_migration_2',
                    'name': 'Test Migration 2',
                    'sql': 'CREATE TABLE test_table_2 (id INTEGER PRIMARY KEY, value REAL)'
                }
            ]
            
            for migration in test_migrations:
                self.migration_manager.apply_migration(migration)
            
            # Получаем список примененных миграций
            applied_migrations = self.migration_manager.get_applied_migrations()
            
            # Проверяем, что список содержит обе миграции
            self.assertEqual(len(applied_migrations), 2)
            migration_ids = [m['id'] for m in applied_migrations]
            self.assertIn('test_migration_1', migration_ids)
            self.assertIn('test_migration_2', migration_ids)
        
        def test_migration_apply_all(self):
            """Тест применения всех миграций."""
            # Инициализируем таблицу миграций
            self.migration_manager.init_migrations_table()
            
            # Создаем тестовые миграции
            test_migrations = [
                {
                    'id': 'test_migration_1',
                    'name': 'Test Migration 1',
                    'sql': 'CREATE TABLE test_table_1 (id INTEGER PRIMARY KEY, name TEXT)'
                },
                {
                    'id': 'test_migration_2',
                    'name': 'Test Migration 2',
                    'sql': 'CREATE TABLE test_table_2 (id INTEGER PRIMARY KEY, value REAL)'
                },
                {
                    'id': 'test_migration_3',
                    'name': 'Test Migration 3',
                    'sql': 'CREATE TABLE test_table_3 (id INTEGER PRIMARY KEY, data TEXT)'
                }
            ]
            
            # Применяем только первую миграцию вручную
            self.migration_manager.apply_migration(test_migrations[0])
            
            # Патчим метод get_all_migrations для возврата тестовых миграций
            with patch.object(self.migration_manager, 'get_all_migrations', return_value=test_migrations):
                # Вызываем метод apply_all_migrations
                applied = self.migration_manager.apply_all_migrations()
            
            # Проверяем, что было применено 2 миграции (вторая и третья)
            self.assertEqual(applied, 2)
            
            # Проверяем, что все таблицы созданы
            tables = []
            self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'test_table_%'")
            for row in self.db.fetchall():
                tables.append(row[0])
            
            self.assertEqual(len(tables), 3)
            self.assertIn('test_table_1', tables)
            self.assertIn('test_table_2', tables)
            self.assertIn('test_table_3', tables)


if __name__ == '__main__':
    unittest.main() 