# Руководство по тестированию DMarket Trading Bot

Этот документ содержит информацию о структуре тестов, их запуске и поддержке.

## Структура тестов

Тесты организованы в следующие каталоги:

- `tests/` - Корневой каталог тестов
  - `api/` - Тесты для API-интеграций
  - `cli/` - Тесты для командной строки (CLI)
  - `ml/` - Тесты для модулей машинного обучения
  - `utils/` - Тесты для утилит

## Запуск тестов

### Запуск всех тестов

```bash
python -m unittest discover -s tests
```

### Запуск конкретной группы тестов

```bash
python -m unittest discover -s tests/api
python -m unittest discover -s tests/cli
python -m unittest discover -s tests/ml
python -m unittest discover -s tests/utils
```

### Запуск отдельного теста

```bash
python -m unittest tests/cli/test_cli.py
```

## Настройка тестового окружения

Для тестирования необходимо создать правильное окружение:

1. Установите зависимости для тестирования:
   ```bash
   pip install -r requirements-test.txt
   ```

2. Настройте тестовую конфигурацию:
   ```bash
   cp config/config.example.json config/config.test.json
   # Отредактируйте config/config.test.json для тестового окружения
   ```

## Мокирование внешних зависимостей

В тестах используются моки для внешних зависимостей:

### Мокирование API

```python
class MockDMarketAPI:
    """Мок для DMarket API."""
    
    async def get_items_by_title(self, title, game_id=None, limit=10):
        """Получение предметов по названию."""
        # Реализация мока...
```

### Мокирование файловой системы

```python
# Патчим методы, которые взаимодействуют с файловой системой
self.file_patcher = patch('builtins.open', mock_open())
self.file_patcher.start()

# Патчим os.path.exists для имитации существования файлов
self.path_exists_patcher = patch('os.path.exists', return_value=True)
self.path_exists_patcher.start()

# Не забудьте остановить патчи после теста
self.file_patcher.stop()
self.path_exists_patcher.stop()
```

## Работа с асинхронными функциями

Для тестирования асинхронных функций есть несколько подходов:

1. Использование `asyncio.run()` в обычных тестах:

```python
def test_async_function(self):
    import asyncio
    result = asyncio.run(my_async_function())
    self.assertEqual(result, expected_value)
```

2. Использование асинхронных тестов в unittest:

```python
async def test_async_function(self):
    result = await my_async_function()
    self.assertEqual(result, expected_value)
```

**Подробная информация и рекомендуемые практики для тестирования асинхронного кода доступны в [руководстве по асинхронному тестированию](async_testing.md).**

## Проверка ошибок

При тестировании обработки ошибок используйте контекстный менеджер `self.assertRaises`:

```python
with self.assertRaises(ValueError):
    function_that_should_raise_error()
```

## Директории для временных файлов

Используйте `tempfile` для создания временных каталогов и файлов в тестах:

```python
# Создаем временную директорию
self.temp_dir = tempfile.mkdtemp()

# Создаем временный файл
self.temp_file = tempfile.NamedTemporaryFile(delete=False)

# Не забудьте очистить после теста
shutil.rmtree(self.temp_dir, ignore_errors=True)
os.unlink(self.temp_file.name)
```

## Советы по написанию тестов

1. **Изолируйте тесты**: Каждый тест должен быть независимым от других.
2. **Используйте setUp и tearDown**: Подготовка и очистка должны быть в соответствующих методах.
3. **Документируйте тесты**: Каждый тестовый класс и метод должен иметь понятную документацию.
4. **Тестируйте граничные условия**: Проверяйте крайние случаи и обработку ошибок.
5. **Используйте моки и патчи**: Изолируйте код от внешних зависимостей.

## Покрытие кода тестами

Для проверки покрытия кода тестами используйте `coverage`:

```bash
coverage run -m unittest discover
coverage report
coverage html  # Создает HTML-отчет в каталоге htmlcov/
``` 