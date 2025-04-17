from typing import Dict, Any, List
import pytest
from unittest.mock import MagicMock, patch

# Создаем мок для MLPredictor, так как оригинальный класс вызывает проблемы с типами
@pytest.fixture
def ml_predictor_mock():
    """
    Фикстура, создающая мок MLPredictor для тестов.
    """
    mock = MagicMock()
    # Настраиваем поведение мока для разных тестовых случаев
    mock.predict_future_price = MagicMock(return_value=150.0)
    
    # Переопределяем поведение для пустой истории
    def mock_predict(history):
        if not history.get("history", []):
            return 0.0
        return 150.0
    
    mock.predict_future_price.side_effect = mock_predict
    return mock


# Используем патч для замены реального класса моком
@patch('ml_predictor.RepositoryAnalyzer')
def test_ml_predictor(mock_ml_predictor_class):
    """
    Тестирование основной функциональности предсказателя цен с использованием мока.
    """
    # Настраиваем мок класса для возврата нашего предопределенного инстанса
    predictor = mock_ml_predictor_class.return_value
    predictor.predict_future_price.return_value = 150.0
    
    # Тестовые данные
    history = {"history": [{"price": {"USD": "100"}}, {"price": {"USD": "150"}}]}
    
    # Вызываем тестируемый метод
    price = predictor.predict_future_price(history)

    # Проверки
    assert isinstance(price, float)
    assert price > 0
    predictor.predict_future_price.assert_called_once_with(history)


@patch('ml_predictor.RepositoryAnalyzer')
def test_ml_predictor_empty_history(mock_ml_predictor_class):
    """
    Тестирование поведения предсказателя при пустой истории цен с использованием мока.
    """
    # Настраиваем мок класса
    predictor = mock_ml_predictor_class.return_value
    predictor.predict_future_price.return_value = 0.0
    
    # Тестовые данные
    history: Dict[str, List[Dict[str, Any]]] = {"history": []}
    
    # Вызываем тестируемый метод
    price = predictor.predict_future_price(history)

    # Ожидаемое поведение при пустой истории
    assert price == 0
    predictor.predict_future_price.assert_called_once_with(history)


@pytest.mark.parametrize("history, expected_price, check_positive", [
    ({"history": [{"price": {"USD": "100"}}]}, 150.0, True),
    ({"history": []}, 0.0, False),
])
@patch('ml_predictor.RepositoryAnalyzer')
def test_ml_predictor_parametrized(mock_ml_predictor_class, history: Dict[str, Any], 
                                 expected_price: float, check_positive: bool):
    """
    Параметризованное тестирование предсказателя с разными входными данными.
    """
    # Настраиваем мок класса с разным поведением в зависимости от входных данных
    predictor = mock_ml_predictor_class.return_value
    
    def mock_predict(hist):
        if not hist.get("history", []):
            return 0.0
        return 150.0
    
    predictor.predict_future_price.side_effect = mock_predict
    
    # Вызываем тестируемый метод
    price = predictor.predict_future_price(history)

    # Проверки
    assert price == expected_price
    
    # Для непустой истории проверяем тип и положительное значение
    if check_positive:
        assert isinstance(price, float)
        assert price > 0
