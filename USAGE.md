# Руководство пользователя DMarket Trading Bot

Это руководство поможет вам начать работу с DMarket Trading Bot и эффективно использовать его функции для автоматизированной торговли на платформе DMarket.

## Начало работы

После [установки и настройки](./INSTALLATION.md) бота, вам необходимо инициализировать его через Telegram.

1. Найдите своего бота в Telegram по имени, которое вы указали при создании
2. Отправьте команду `/start`
3. Если ваш Telegram ID указан в конфигурации как ID администратора, вы получите доступ к полному функционалу бота

## Основные команды

DMarket Trading Bot поддерживает следующие основные команды:

- `/start` - Инициализация бота и приветственное сообщение
- `/help` - Показать список доступных команд с кратким описанием
- `/status` - Показать текущий статус бота, подключения к API и активных стратегий
- `/settings` - Открыть меню настроек бота
- `/balance` - Показать текущий баланс и стоимость активов на DMarket
- `/inventory` - Показать список предметов в вашем инвентаре
- `/orders` - Показать список активных ордеров
- `/history` - Показать историю транзакций
- `/stats` - Показать статистику торговли
- `/stop` - Остановить все активные торговые стратегии
- `/resume` - Возобновить торговые стратегии

## Меню настроек

Команда `/settings` открывает интерактивное меню настроек, в котором вы можете настроить параметры работы бота:

1. **Управление рисками**
   - Максимальный лимит цены
   - Минимальный процент прибыли
   - Максимальное количество одновременных ордеров
   - Уровень риска (от 1 до 5)

2. **Торговые стратегии**
   - Выбор и настройка стратегий
   - Параметры для каждой стратегии

3. **API настройки**
   - Проверка статуса API
   - Обновление API ключей

4. **Настройки уведомлений**
   - Уведомления о сделках
   - Уведомления об ошибках
   - Ежедневные отчеты

## Торговые стратегии

DMarket Trading Bot поддерживает несколько торговых стратегий. Вы можете выбрать и настроить их через команду `/settings`.

### Арбитражная стратегия

Эта стратегия ищет разницу в ценах между разными площадками и DMarket.

```
/strategy arbitrage --enable --min-profit 7 --max-price 100
```

Параметры:
- `--min-profit` - Минимальный процент прибыли (по умолчанию: 5%)
- `--max-price` - Максимальная цена предмета в USD (по умолчанию: 50)
- `--platforms` - Платформы для сравнения (по умолчанию: steam,bitskins,csdeals)

### Стратегия отслеживания тренда

Эта стратегия анализирует тренды цен и совершает сделки на основе прогнозирования движения цены.

```
/strategy trend --enable --sensitivity 3 --period 14
```

Параметры:
- `--sensitivity` - Чувствительность к изменениям тренда (1-5, по умолчанию: 3)
- `--period` - Период анализа в днях (по умолчанию: 7)
- `--ma-type` - Тип скользящей средней (simple, exponential, по умолчанию: exponential)

### Стратегия маркет-мейкинга

Эта стратегия размещает ордера на покупку и продажу с небольшим спредом для получения прибыли от разницы.

```
/strategy market_making --enable --spread 3 --order-count 5
```

Параметры:
- `--spread` - Процентный спред между ордерами на покупку и продажу (по умолчанию: 2%)
- `--order-count` - Количество ордеров для размещения (по умолчанию: 3)
- `--refresh-time` - Время обновления ордеров в минутах (по умолчанию: 15)

### Стратегия волатильности

Эта стратегия использует рыночную волатильность для определения выгодных моментов для покупки и продажи.

```
/strategy volatility --enable --threshold 8 --window 24
```

Параметры:
- `--threshold` - Порог волатильности в процентах (по умолчанию: 5%)
- `--window` - Окно анализа в часах (по умолчанию: 12)
- `--interval` - Интервал проверки в минутах (по умолчанию: 30)

## Фильтрация предметов

Вы можете настроить фильтры для предметов, с которыми будет работать бот:

```
/filter set --game csgo --category knife,glove --min-price 10 --max-price 500 --rarity covert,classified
```

Параметры:
- `--game` - Игра (csgo, dota2, rust и т.д.)
- `--category` - Категории предметов
- `--min-price` - Минимальная цена в USD
- `--max-price` - Максимальная цена в USD
- `--rarity` - Редкость предметов
- `--wear` - Состояние предмета (для CS:GO)

Чтобы посмотреть текущие фильтры:
```
/filter show
```

Чтобы сбросить фильтры:
```
/filter reset
```

## Мониторинг и статистика

### Текущие ордера

Для просмотра активных ордеров используйте команду:
```
/orders
```

Дополнительные параметры:
- `/orders buy` - Показать только ордера на покупку
- `/orders sell` - Показать только ордера на продажу
- `/orders active` - Показать только активные ордера
- `/orders last 10` - Показать последние 10 ордеров

### История торговли

Для просмотра истории торговли используйте команду:
```
/history
```

Дополнительные параметры:
- `/history today` - Показать сделки за сегодня
- `/history week` - Показать сделки за неделю
- `/history month` - Показать сделки за месяц
- `/history last 20` - Показать последние 20 сделок

### Статистика

Для просмотра статистики торговли используйте команду:
```
/stats
```

Это покажет:
- Общую прибыль/убыток
- Количество успешных сделок
- Средний процент прибыли
- Наиболее прибыльные предметы
- Графики производительности

Дополнительные параметры:
- `/stats daily` - Ежедневная статистика
- `/stats weekly` - Еженедельная статистика
- `/stats monthly` - Ежемесячная статистика
- `/stats by-item` - Статистика по предметам
- `/stats by-strategy` - Статистика по стратегиям

## Ручные операции

Помимо автоматических стратегий, вы можете выполнять операции вручную:

### Размещение ордеров

```
/order buy --item "AK-47 | Redline (Field-Tested)" --price 12.50
/order sell --item "★ Butterfly Knife | Fade (Factory New)" --price 875.00
```

Параметры:
- `--item` - Название предмета
- `--price` - Цена в USD
- `--quantity` - Количество (по умолчанию: 1)
- `--expire` - Срок действия в часах (по умолчанию: 24)

### Отмена ордеров

```
/order cancel 1234567890
/order cancel all
/order cancel buy
/order cancel sell
```

### Поиск предметов

```
/search "AK-47 | Redline" --max-price 15 --min-float 0.15 --max-float 0.20
```

Параметры:
- `--max-price` - Максимальная цена в USD
- `--min-price` - Минимальная цена в USD
- `--min-float` - Минимальное значение Float (для CS:GO)
- `--max-float` - Максимальное значение Float (для CS:GO)
- `--limit` - Максимальное количество результатов (по умолчанию: 10)

## Уведомления

Бот отправляет уведомления о важных событиях, таких как:
- Успешное выполнение ордера
- Создание нового ордера
- Отмена ордера
- Обнаружение выгодной возможности для торговли
- Ошибки API или сети
- Ежедневные отчеты о торговле

Вы можете настроить уведомления через `/settings`:
```
/settings notifications
```

## Расширенные настройки

### Управление API ключами

```
/api update --public YOUR_NEW_PUBLIC_KEY --secret YOUR_NEW_SECRET_KEY
/api status
```

### Настройка параметров безопасности

```
/security set-limit --daily-volume 1000 --max-price 500
/security show-limits
```

### Изменение режима работы

```
/mode aggressive    # Приоритет на быстрые сделки
/mode conservative  # Приоритет на безопасность и минимизацию риска
/mode balanced      # Сбалансированный подход (по умолчанию)
```

## Резервное копирование и экспорт данных

### Экспорт статистики

```
/export stats --format csv --period month
```

Форматы:
- `csv` - CSV файл
- `json` - JSON файл
- `xlsx` - Excel файл

### Экспорт истории

```
/export history --format csv --period all
```

## Расширенный анализ рынка

### Анализ цен

```
/market analyze "AWP | Dragon Lore (Factory New)" --period 90
```

Параметры:
- `--period` - Период анализа в днях (по умолчанию: 30)
- `--chart` - Отправить график (yes/no, по умолчанию: yes)
- `--predict` - Показать прогноз цены (yes/no, по умолчанию: no)

### Рыночные тренды

```
/market trends --game csgo --category knife --period 7
```

## Администрирование

Если вы являетесь администратором бота (ваш Telegram ID указан в настройках), у вас есть доступ к дополнительным командам:

```
/admin status       # Показать системный статус бота
/admin restart      # Перезапустить бота
/admin update       # Обновить бота до последней версии
/admin logs         # Показать последние логи
/admin users        # Управление пользователями
```

## Советы и рекомендации

1. **Начните с малого** - Установите низкие лимиты и консервативные настройки, пока не освоитесь с ботом
2. **Регулярно проверяйте статистику** - Анализируйте результаты торговли для оптимизации стратегий
3. **Используйте фильтры** - Правильно настроенные фильтры помогут боту сосредоточиться на наиболее перспективных предметах
4. **Не торгуйте во время волатильности рынка** - Если не используете специальную стратегию для этого
5. **Регулярно обновляйте бота** - Для получения новых функций и исправлений ошибок

## Устранение неполадок

### Бот не отвечает

1. Проверьте, работает ли сервис: `/admin status`
2. Перезапустите бота: `/admin restart`
3. Проверьте логи: `/admin logs`

### Ошибки при создании ордеров

1. Проверьте баланс на DMarket: `/balance`
2. Проверьте статус API: `/api status`
3. Проверьте, не превышены ли лимиты: `/security show-limits`

### Неточные данные о ценах

1. Обновите рыночные данные: `/market refresh`
2. Проверьте, не устарели ли данные: `/market status`

## Часто задаваемые вопросы

**В: Как изменить валюту для отображения цен?**
О: Используйте команду `/settings currency USD` (доступные валюты: USD, EUR, RUB, GBP)

**В: Можно ли использовать бота для нескольких аккаунтов DMarket?**
О: Каждый экземпляр бота работает только с одним аккаунтом. Для работы с несколькими аккаунтами вам потребуется запустить отдельные экземпляры бота.

**В: Как добавить другого пользователя с правами администратора?**
О: Используйте команду `/admin users add 123456789`, где 123456789 - Telegram ID нового администратора.

**В: Безопасно ли использовать API ключи?**
О: Бот хранит API ключи в зашифрованном виде и использует только те разрешения, которые необходимы для торговли. Всегда создавайте отдельные API ключи для бота с ограниченными разрешениями.

**В: Что делать, если я заметил неправильное поведение бота?**
О: Немедленно остановите торговые стратегии с помощью команды `/stop`, проверьте логи через `/admin logs` и свяжитесь с разработчиками.

## Дополнительные ресурсы

- [Установка и настройка](./INSTALLATION.md)
- [Руководство разработчика](./DEVELOPMENT.md)
- [Документация по API DMarket](https://docs.dmarket.com)
- [Обсуждение бота в Telegram](https://t.me/dmarket_trading_bot_group)
- [Репозиторий проекта на GitHub](https://github.com/yourusername/dmarket-trading-bot) 