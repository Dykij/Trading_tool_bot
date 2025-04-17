# Тестирование асинхронного кода

Многие методы в проекте DMarket Trading Bot являются асинхронными (используют `async/await`). 
При тестировании таких методов важно правильно настроить среду тестирования для предотвращения 
предупреждений вида `RuntimeWarning: coroutine was never awaited`.

## Проблема

При использовании стандартного модуля `unittest` для тестирования асинхронных методов возникают предупреждения:

```
RuntimeWarning: coroutine 'TestMLPredictor.test_find_investment_opportunities' was never awaited
```

Это происходит, потому что методы тестов, которые вызывают асинхронные функции, сами должны быть асинхронными, 
и их выполнение должно происходить в цикле событий asyncio.

## Решение

### 1. Установка pytest и pytest-asyncio

```bash
pip install pytest pytest-asyncio
```

### 2. Модификация тестов

Пример модификации теста с использованием unittest:

```python
# Раньше
def test_find_investment_opportunities(self):
    # Вызов асинхронного метода без await
    result = self.predictor.find_investment_opportunities()
    # Проверки...

# Правильно (использование asyncio.run)
def test_find_investment_opportunities(self):
    # Использование asyncio.run для запуска асинхронного метода
    import asyncio
    result = asyncio.run(self.predictor.find_investment_opportunities())
    # Проверки...
```

Пример модификации теста с использованием pytest-asyncio:

```python
import pytest

# Добавляем декоратор и делаем метод асинхронным
@pytest.mark.asyncio
async def test_find_investment_opportunities(self):
    # Просто используем await
    result = await self.predictor.find_investment_opportunities()
    # Проверки...
```

### 3. Запуск тестов с pytest

```bash
# Запуск всех тестов
python -m pytest tests/

# Запуск конкретного теста
python -m pytest tests/ml/test_ml_predictor.py::TestMLPredictor::test_find_investment_opportunities -v
```

## Преимущества использования pytest-asyncio

1. **Чистый код** - тесты становятся более читаемыми с явным использованием `await`
2. **Нет предупреждений** - отсутствуют предупреждения о незавершенных корутинах
3. **Поддержка фикстур** - асинхронные фикстуры для настройки и очистки тестового окружения
4. **Улучшенный отладчик** - более точная информация о месте ошибки
5. **Параллельное выполнение** - возможность запуска тестов параллельно

## Пример полного теста

```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
class TestMLPredictor:
    async def setup_method(self):
        # Асинхронная настройка перед каждым тестом
        self.predictor = MLPredictor(api_client=MockDMarketAPI())
        
    @patch('src.ml.ml_predictor.MLPredictor.predict_price')
    async def test_find_investment_opportunities(self, mock_predict_price):
        # Устанавливаем возвращаемые значения для мока
        mock_predict_price.side_effect = [
            {'current_price': 100, 'predicted_price': 120, 'confidence': 0.8},
            {'current_price': 50, 'predicted_price': 55, 'confidence': 0.7}
        ]
        
        # Асинхронный вызов с await
        opportunities = await self.predictor.find_investment_opportunities(
            min_price=10,
            max_price=150,
            min_roi=5,
            min_confidence=0.7,
            limit=10
        )
        
        # Стандартные проверки
        assert len(opportunities) == 2
        assert opportunities[0]['item_name'] == 'AWP | Asiimov'
        assert opportunities[0]['roi'] == 20
```

## Миграция существующих тестов

Для постепенной миграции существующих тестов можно начать с изменения наиболее критичных тестов, 
которые вызывают предупреждения, а затем перейти к остальным. Pytest поддерживает смешивание стилей 
тестирования, что позволяет постепенно переходить на новый подход. 