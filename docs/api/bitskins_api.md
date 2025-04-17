# Bitskins API Documentation

## Overview

Bitskins предоставляет RESTful API для взаимодействия с их торговой площадкой для скинов CS:GO, Dota 2 и других игр.

Базовый URL API: `https://bitskins.com/api/v1/`

## Авторизация

Для доступа к API необходимо:
1. API-ключ из профиля Bitskins
2. Двухфакторный код авторизации

### Параметры аутентификации

В каждом запросе необходимо передавать следующие параметры:
- `api_key` - ваш API-ключ
- `code` - код двухфакторной аутентификации

## Основные методы API

### Получение баланса аккаунта

```
GET /get_account_balance
```

#### Параметры:
- `api_key` (обязательно) - ваш API-ключ
- `code` (обязательно) - код двухфакторной аутентификации

#### Пример ответа:
```json
{
  "status": "success",
  "data": {
    "available_balance": "175.64",
    "pending_withdrawals": "0.00",
    "withdrawable_balance": "175.64",
    "coupon_balance": "0.00"
  }
}
```

### Получение цен на предметы

```
GET /get_price_data_for_items_on_sale
```

#### Параметры:
- `api_key` (обязательно) - ваш API-ключ
- `code` (обязательно) - код двухфакторной аутентификации
- `app_id` (опционально) - ID приложения в Steam (730 для CS:GO)
- `names` (опционально) - список названий предметов через запятую

#### Пример ответа:
```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "market_hash_name": "★ Karambit | Doppler (Factory New)",
        "lowest_price": "350.00",
        "highest_price": "420.00",
        "recent_sales_info": {
          "hours": 24,
          "average_price": "380.56"
        }
      }
    ]
  }
}
```

### Получение истории цен предмета

```
GET /get_sales_info
```

#### Параметры:
- `api_key` (обязательно) - ваш API-ключ
- `code` (обязательно) - код двухфакторной аутентификации
- `market_hash_name` (обязательно) - название предмета
- `page` (опционально) - номер страницы
- `app_id` (опционально) - ID приложения в Steam

#### Пример ответа:
```json
{
  "status": "success",
  "data": {
    "sales": [
      {
        "market_hash_name": "★ Karambit | Doppler (Factory New)",
        "price": "380.00",
        "wear_value": "0.03237918",
        "sold_at": "2023-04-01T15:32:47Z"
      }
    ]
  }
}
```

### Покупка предмета

```
POST /buy_item
```

#### Параметры:
- `api_key` (обязательно) - ваш API-ключ
- `code` (обязательно) - код двухфакторной аутентификации
- `item_ids` (обязательно) - ID предмета или список через запятую
- `prices` (обязательно) - Цена или список цен через запятую

#### Пример ответа:
```json
{
  "status": "success",
  "data": {
    "bought_items": [
      {
        "item_id": "12345678",
        "market_hash_name": "★ Karambit | Doppler (Factory New)",
        "price": "380.00",
        "wear_value": "0.03237918"
      }
    ]
  }
}
```

### Выставление предмета на продажу

```
POST /list_item_for_sale
```

#### Параметры:
- `api_key` (обязательно) - ваш API-ключ
- `code` (обязательно) - код двухфакторной аутентификации
- `item_ids` (обязательно) - ID предмета или список через запятую
- `prices` (обязательно) - Цена или список цен через запятую

#### Пример ответа:
```json
{
  "status": "success",
  "data": {
    "listed_items": [
      {
        "item_id": "12345678",
        "market_hash_name": "★ Karambit | Doppler (Factory New)",
        "price": "400.00",
        "wear_value": "0.03237918"
      }
    ]
  }
}
```

## Коды ошибок

| Код | Описание |
|-----|----------|
| 401 | Unauthorized - неверный API-ключ или код двухфакторной аутентификации |
| 403 | Forbidden - недостаточно прав для совершения операции |
| 404 | Not Found - ресурс не найден |
| 429 | Too Many Requests - превышен лимит запросов |
| 500 | Internal Server Error - внутренняя ошибка сервера |

## Интеграция с проектом

В нашем проекте API Bitskins используется для:
1. Получения актуальных цен на предметы для арбитражного анализа
2. Сравнения цен между различными торговыми площадками
3. Автоматического поиска предметов для арбитража
4. Создания целевых ордеров на основе данных с Bitskins

### Пример интеграции:

```python
async def get_bitskins_price(self, item_name: str) -> float:
    """
    Получает текущую цену предмета на Bitskins.
    
    Args:
        item_name: Название предмета
        
    Returns:
        float: Текущая цена предмета
    """
    endpoint = "/get_price_data_for_items_on_sale"
    params = {
        "api_key": self.api_key,
        "code": self.generate_2fa_code(),
        "names": item_name,
        "app_id": 730
    }
    
    response = await self._make_request("GET", endpoint, params=params)
    
    if response.get("status") == "success":
        items = response.get("data", {}).get("items", [])
        if items:
            return float(items[0].get("lowest_price", 0))
    
    return 0.0
```

## Ограничения API

- Максимум 60 запросов в минуту
- Максимум 5 предметов за один запрос в методах покупки и продажи
- Торговое ограничение в 7 дней для новых предметов из CS:GO 