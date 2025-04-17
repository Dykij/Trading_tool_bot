# Тестирование DMarket Trading Bot

Этот документ содержит подробную информацию о тестировании проекта DMarket Trading Bot, включая организацию тестов, инструкции по запуску и интерпретации результатов.

## Содержание

- [Структура тестов](#структура-тестов)
- [Запуск тестов](#запуск-тестов)
- [Покрытие кода](#покрытие-кода)
- [Автоматизация тестирования](#автоматизация-тестирования)
- [Виды тестов](#виды-тестов)
- [Написание новых тестов](#написание-новых-тестов)
- [Тестирование взаимодействия с API](#тестирование-взаимодействия-с-api)
- [Общие проблемы и их решения](#общие-проблемы-и-их-решения)

## Структура тестов

Тесты располагаются в директории `tests/`:

```
tests/
├── conftest.py             # Конфигурация и фикстуры для pytest
├── test_api.py             # Тесты для API-обертки
├── test_bellman.py         # Тесты для алгоритма Беллмана-Форда
├── test_integration.py     # Интеграционные тесты
└── test_ml.py              # Тесты для ML-предиктора
```

Основные компоненты для тестирования:

- **API Wrapper**: Проверка корректности запросов к DMarket API
- **Алгоритм Беллмана-Форда**: Проверка поиска арбитражных возможностей
- **ML Predictor**: Проверка точности прогнозирования цен
- **Интеграционные тесты**: Проверка взаимодействия между компонентами

## Запуск тестов

В проекте предусмотрено несколько способов запуска тестов:

### Через командную строку

```bash
# Запуск всех тестов
pytest

# Запуск конкретного модуля тестов
pytest tests/test_api.py

# Запуск конкретного теста
pytest tests/test_api.py::test_api_authentication

# Запуск с подробным выводом
pytest -v

# Запуск с показом вывода print() и логов
pytest -v --capture=no
```

### Через задачи VS Code

В проекте настроены задачи VS Code для удобного запуска тестов:

1. Нажмите `Ctrl+Shift+P` (или `Cmd+Shift+P` на Mac)
2. Введите `Run Task` и выберите одну из задач:
   - `Run Tests`: Запуск всех тестов
   - `Run Tests with Coverage`: Запуск тестов с анализом покрытия кода

### Через скрипт PowerShell

Можно использовать включенный скрипт PowerShell для запуска тестов:

```bash
# Запуск тестов
powershell -ExecutionPolicy Bypass -File "check_code.ps1" -Tests

# Запуск тестов с покрытием
powershell -ExecutionPolicy Bypass -File "check_code.ps1" -Coverage

# Запуск тестов с покрытием и генерацией HTML-отчета
powershell -ExecutionPolicy Bypass -File "check_code.ps1" -Coverage -GenerateHTML
```

## Покрытие кода

Для анализа покрытия кода тестами используется библиотека `coverage`.

### Запуск тестов с покрытием

```bash
# Через pytest
pytest --cov=. --cov-report=term

# Через скрипт PowerShell
powershell -ExecutionPolicy Bypass -File "check_code.ps1" -Coverage

# Генерация HTML-отчета
powershell -ExecutionPolicy Bypass -File "check_code.ps1" -Coverage -GenerateHTML
```

После запуска с флагом `-GenerateHTML` будет создана директория `htmlcov/` с HTML-отчетом о покрытии. Откройте `htmlcov/index.html` в браузере для просмотра детального отчета.

### Интерпретация результатов покрытия

После выполнения тестов с покрытием вы увидите отчет, подобный этому:

```
---------- coverage: platform win32, python 3.11.0-final-0 -----------
Name                      Stmts   Miss  Cover
---------------------------------------------
api_wrapper.py             352     42    88%
bellman_ford.py            126     18    86%
data_collector.py          102     31    70%
ml_predictor.py             98     16    84%
trading_bot.py             215     53    75%
...
---------------------------------------------
TOTAL                     1243    258    79%
```

Обратите внимание на следующие показатели:

- **Stmts**: Общее количество исполняемых строк
- **Miss**: Количество непокрытых строк
- **Cover**: Процент покрытия кода

Цель проекта - поддерживать покрытие на уровне не менее 80% для ключевых модулей.

## Автоматизация тестирования

### Pre-commit хуки

Проект настроен для автоматического запуска тестов при каждом коммите с помощью pre-commit хуков:

```bash
# Установка pre-commit
pip install pre-commit

# Настройка хуков
pre-commit install
```

После установки хуков тесты будут запускаться автоматически перед каждым коммитом. Если тесты не проходят, коммит будет отклонен.

### Интеграция с задачами VS Code

VS Code автоматически распознает тесты pytest и отображает их в панели тестирования:

1. Откройте панель тестирования в VS Code (иконка колбы)
2. Вы увидите все доступные тесты
3. Запустите отдельные тесты или все тесты сразу

## Виды тестов

### Модульные тесты

Тесты для отдельных компонентов проекта:

```python
# Пример теста для API Wrapper
def test_api_get_market_items():
    """Тест для метода get_market_items."""
    api = create_test_api()
    items = api.get_market_items(limit=10)
    assert isinstance(items, dict)
    assert "objects" in items
    assert len(items["objects"]) <= 10
```

### Интеграционные тесты

Тесты для проверки взаимодействия между компонентами:

```python
# Пример интеграционного теста
def test_trading_bot_integration():
    """Проверка взаимодействия компонентов торгового бота."""
    api = create_test_api()
    collector = DataCollector(api_client=api)
    predictor = MLPredictor()
    bot = TradingBot(api_client=api, data_collector=collector, predictor=predictor)
    
    # Проверка полного цикла работы
    bot.start()
    opportunities = bot.get_opportunities()
    bot.stop()
    
    assert isinstance(opportunities, list)
```

### Нагрузочные тесты

Проверка производительности и стабильности при высокой нагрузке:

```python
# Пример нагрузочного теста
@pytest.mark.slow
def test_api_load():
    """Тест производительности API при большом количестве запросов."""
    api = create_test_api()
    start_time = time.time()
    
    for _ in range(100):
        api.get_market_items(limit=10)
        
    duration = time.time() - start_time
    assert duration < 60  # Все запросы должны выполниться менее чем за 60 секунд
```

## Написание новых тестов

### Фикстуры и мокинг

Проект использует `pytest.fixture` для создания общих объектов для тестов:

```python
# В conftest.py
@pytest.fixture
def test_api():
    """Фикстура для создания тестового API-клиента."""
    api = DMarketAPI(
        api_key="test_key",
        api_secret="test_secret",
        base_url="https://test-api.example.com"
    )
    return api

@pytest.fixture
def mock_market_data():
    """Фикстура для создания мока рыночных данных."""
    return [
        {"itemId": "item1", "price": {"amount": "100", "currency": "USD"}},
        {"itemId": "item2", "price": {"amount": "200", "currency": "USD"}},
        # ...
    ]
```

Для имитации внешних зависимостей используется `unittest.mock`:

```python
from unittest.mock import patch, MagicMock

def test_api_with_mock():
    """Тест с использованием мока."""
    # Создаем мок для requests.get
    with patch('api_wrapper.requests.get') as mock_get:
        # Настраиваем возвращаемое значение
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"objects": []}
        mock_get.return_value = mock_response
        
        # Вызываем тестируемую функцию
        api = DMarketAPI(api_key="test_key")
        result = api.get_market_items()
        
        # Проверяем результат
        assert "objects" in result
        # Проверяем, что запрос был выполнен с правильными параметрами
        mock_get.assert_called_once()
```

### Структура тестов

Следуйте шаблону AAA (Arrange-Act-Assert) при написании тестов:

```python
def test_something():
    # Arrange (подготовка)
    api = create_test_api()
    expected_data = {"objects": []}
    
    # Act (действие)
    result = api.get_market_items()
    
    # Assert (проверка)
    assert result == expected_data
```

## Тестирование взаимодействия с API

### Моки и стабы

Для тестирования взаимодействия с API используйте моки, чтобы избежать реальных запросов:

```python
@patch('api_wrapper.requests.get')
def test_get_market_items(mock_get):
    """Тест для метода get_market_items с моком requests.get."""
    # Настройка мока
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "objects": [
            {"itemId": "1", "title": "Test Item", "price": {"amount": "10", "currency": "USD"}}
        ]
    }
    mock_get.return_value = mock_response
    
    # Вызов тестируемого метода
    api = DMarketAPI(api_key="test_key")
    result = api.get_market_items()
    
    # Проверка результата
    assert "objects" in result
    assert len(result["objects"]) == 1
    assert result["objects"][0]["title"] == "Test Item"
```

### Тестирование обработки ошибок

Проверяйте корректную обработку различных ошибок API:

```python
@patch('api_wrapper.requests.get')
def test_api_error_handling(mock_get):
    """Тест обработки ошибок API."""
    # Настройка мока для возврата ошибки
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Too Many Requests"
    mock_get.return_value = mock_response
    
    # Проверка, что исключение выбрасывается корректно
    api = DMarketAPI(api_key="test_key")
    with pytest.raises(RateLimitError) as excinfo:
        api.get_market_items()
    
    # Проверка информации об ошибке
    assert excinfo.value.status_code == 429
    assert "Too Many Requests" in str(excinfo.value)
```

## Общие проблемы и их решения

### Проблема: Тесты не могут найти модули проекта

**Решение**: Убедитесь, что директория проекта добавлена в PYTHONPATH. В файле `conftest.py` добавьте:

```python
import sys
import os

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
```

### Проблема: Тесты работают слишком медленно

**Решение**: Используйте маркеры pytest для разделения тестов на быстрые и медленные:

```python
# Пометка медленных тестов
@pytest.mark.slow
def test_slow_operation():
    # ...

# Запуск только быстрых тестов
# pytest -m "not slow"
```

### Проблема: Тесты падают на CI, но работают локально

**Решение**: Проверьте зависимости от окружения и используйте фикстуры для изоляции:

```python
@pytest.fixture
def temp_environment():
    """Создает временное окружение для тестов."""
    old_env = os.environ.copy()
    os.environ["TEST_MODE"] = "True"
    yield
    os.environ.clear()
    os.environ.update(old_env)

def test_with_env(temp_environment):
    # Тест с изолированным окружением
    assert os.environ.get("TEST_MODE") == "True"
```

### Проблема: Синтаксические ошибки в тестируемых файлах

**Решение**: Запустите скрипт для исправления синтаксических ошибок:

```bash
python fix_remaining_issues.py
```

### Проблема: Некоторые тесты падают случайным образом

**Решение**: Проверьте на "утечки состояния" между тестами и используйте фикстуры для сброса состояния:

```python
@pytest.fixture(autouse=True)
def reset_global_state():
    """Автоматически сбрасывает глобальное состояние перед каждым тестом."""
    # Сброс состояния перед тестом
    reset_function()
    yield
    # Сброс состояния после теста
    reset_function()
```