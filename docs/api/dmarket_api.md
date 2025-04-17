# DMarket API Documentation

## Overview

DMarket предоставляет RESTful API для покупки, продажи и обмена игровыми предметами. API позволяет интегрировать функциональность торговой площадки в сторонние приложения.

Базовый URL API: `https://api.dmarket.com`

## Авторизация

DMarket использует JWT токены для авторизации запросов.

### Получение токена

1. Создайте API-ключ и Secret key в личном кабинете DMarket
2. Сгенерируйте JWT токен, используя ваш API-ключ и Secret key

### Заголовки авторизации

Для авторизованных запросов необходимо передавать следующие заголовки:
- `X-Api-Key`: ваш API-ключ
- `Authorization`: Bearer {jwt_token}

## Основные методы API

### Получение баланса

```
GET /account/v1/balance
```

#### Заголовки:
- `X-Api-Key` (обязательно) - ваш API-ключ
- `Authorization` (обязательно) - Bearer {jwt_token}

#### Пример ответа:
```json
{
  "usd": {
    "amount": "175.64",
    "currency": "USD"
  },
  "dmc": {
    "amount": "0",
    "currency": "DMC"
  }
}
```

### Поиск предметов на рынке

```
GET /exchange/v1/market/items
```

#### Параметры:
- `gameId` (обязательно) - ID игры (например, "a8db")
- `limit` (опционально) - количество предметов на странице
- `offset` (опционально) - смещение для пагинации
- `title` (опционально) - название предмета для поиска
- `priceFrom` (опционально) - минимальная цена
- `priceTo` (опционально) - максимальная цена

#### Пример ответа:
```json
{
  "objects": [
    {
      "itemId": "00429b15-71db-5611-9c7d-e9f1c2d98713",
      "title": "★ Karambit | Doppler (Factory New)",
      "image": "https://cdn.dmarket.com/items/karambit_doppler.png",
      "price": {
        "amount": "380.00",
        "currency": "USD"
      },
      "extra": {
        "floatValue": "0.03237918"
      }
    }
  ],
  "total": 1,
  "cursor": "eyJza2lwIjo1MH0="
}
```

### Получение информации о конкретном предмете

```
GET /exchange/v1/items/{itemId}
```

#### Заголовки:
- `X-Api-Key` (обязательно) - ваш API-ключ
- `Authorization` (обязательно) - Bearer {jwt_token}

#### Пример ответа:
```json
{
  "item": {
    "itemId": "00429b15-71db-5611-9c7d-e9f1c2d98713",
    "title": "★ Karambit | Doppler (Factory New)",
    "image": "https://cdn.dmarket.com/items/karambit_doppler.png",
    "price": {
      "amount": "380.00",
      "currency": "USD"
    },
    "extra": {
      "floatValue": "0.03237918",
      "phase": "Phase 2"
    }
  }
}
```

### Создание целевого ордера

```
POST /exchange/v1/target-order/create
```

#### Заголовки:
- `X-Api-Key` (обязательно) - ваш API-ключ
- `Authorization` (обязательно) - Bearer {jwt_token}
- `Content-Type`: application/json

#### Тело запроса:
```json
{
  "gameId": "a8db",
  "price": {
    "amount": "350.00",
    "currency": "USD"
  },
  "attributes": {
    "gameId": "a8db",
    "title": "★ Karambit | Doppler (Factory New)",
    "category": "knife",
    "float": {
      "min": 0.01,
      "max": 0.05
    }
  }
}
```

#### Пример ответа:
```json
{
  "targetOrder": {
    "targetOrderId": "f839b123-5678-9101-a1b2-c3d4e5f67890",
    "price": {
      "amount": "350.00",
      "currency": "USD"
    },
    "attributes": {
      "gameId": "a8db",
      "title": "★ Karambit | Doppler (Factory New)",
      "category": "knife",
      "float": {
        "min": 0.01,
        "max": 0.05
      }
    },
    "status": "ACTIVE",
    "createdAt": "2023-04-01T15:32:47Z"
  }
}
```

### Получение списка целевых ордеров

```
GET /exchange/v1/target-orders
```

#### Заголовки:
- `X-Api-Key` (обязательно) - ваш API-ключ
- `Authorization` (обязательно) - Bearer {jwt_token}

#### Параметры:
- `limit` (опционально) - количество ордеров на странице
- `offset` (опционально) - смещение для пагинации
- `status` (опционально) - статус ордеров (ACTIVE, COMPLETED, CANCELED)

#### Пример ответа:
```json
{
  "targetOrders": [
    {
      "targetOrderId": "f839b123-5678-9101-a1b2-c3d4e5f67890",
      "price": {
        "amount": "350.00",
        "currency": "USD"
      },
      "attributes": {
        "gameId": "a8db",
        "title": "★ Karambit | Doppler (Factory New)",
        "category": "knife",
        "float": {
          "min": 0.01,
          "max": 0.05
        }
      },
      "status": "ACTIVE",
      "createdAt": "2023-04-01T15:32:47Z"
    }
  ],
  "total": 1
}
```

### Отмена целевого ордера

```
DELETE /exchange/v1/target-orders/{targetOrderId}
```

#### Заголовки:
- `X-Api-Key` (обязательно) - ваш API-ключ
- `Authorization` (обязательно) - Bearer {jwt_token}

#### Пример ответа:
```json
{
  "success": true
}
```

### Покупка предмета

```
POST /exchange/v1/offers/{offerId}/buy
```

#### Заголовки:
- `X-Api-Key` (обязательно) - ваш API-ключ
- `Authorization` (обязательно) - Bearer {jwt_token}
- `Content-Type`: application/json

#### Тело запроса:
```json
{
  "price": {
    "amount": "380.00",
    "currency": "USD"
  }
}
```

#### Пример ответа:
```json
{
  "transactionId": "1234567890",
  "status": "SUCCESS"
}
```

## Коды ошибок

| Код | Описание |
|-----|----------|
| 400 | Bad Request - неверные параметры запроса |
| 401 | Unauthorized - ошибка авторизации |
| 403 | Forbidden - недостаточно прав для выполнения операции |
| 404 | Not Found - запрашиваемый ресурс не найден |
| 409 | Conflict - конфликт при выполнении операции |
| 429 | Too Many Requests - превышен лимит запросов |
| 500 | Internal Server Error - внутренняя ошибка сервера |

## Интеграция с проектом

В нашем проекте API DMarket используется для:
1. Автоматического поиска и анализа предметов на рынке
2. Создания и управления целевыми ордерами для автоматической покупки
3. Получения исторических данных о ценах для анализа тенденций
4. Реализации арбитражных стратегий между различными платформами

### Пример интеграции создания целевого ордера:

```python
async def create_target_order(self, item_name: str, price: float, float_min: float = 0, float_max: float = 1) -> Dict[str, Any]:
    """
    Создает целевой ордер на покупку предмета.
    
    Args:
        item_name: Название предмета
        price: Цена покупки
        float_min: Минимальное значение float
        float_max: Максимальное значение float
        
    Returns:
        Dict[str, Any]: Информация о созданном ордере
    """
    endpoint = "/exchange/v1/target-order/create"
    
    data = {
        "gameId": "a8db",  # CS:GO/CS2
        "price": {
            "amount": str(price),
            "currency": "USD"
        },
        "attributes": {
            "gameId": "a8db",
            "title": item_name,
            "float": {
                "min": float_min,
                "max": float_max
            }
        }
    }
    
    response = await self._make_authenticated_request("POST", endpoint, json=data)
    return response.get("targetOrder", {})
```

## Ограничения API

- Лимит запросов: 300 запросов в минуту
- Максимальный размер тела запроса: 10 МБ
- Максимальное количество активных целевых ордеров: зависит от уровня аккаунта 