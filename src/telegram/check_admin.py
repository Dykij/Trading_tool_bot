#!/usr/bin/env python
"""
Скрипт для проверки списка администраторов бота из .env файла.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Получаем корневую директорию проекта (2 уровня вверх от текущего файла)
project_root = Path(__file__).parent.parent.parent.absolute()

# Загружаем переменные окружения из .env файла
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Загружены переменные окружения из {env_file}")
else:
    print(f"Файл .env не найден по пути {env_file}")
    sys.exit(1)

# Получаем список администраторов
admin_ids_str = os.getenv("ADMIN_IDS", "")
if not admin_ids_str:
    print("ADMIN_IDS не установлен в .env файле")
    sys.exit(1)

# Парсим список администраторов
admin_ids = []
for id_str in admin_ids_str.split(','):
    id_str = id_str.strip()
    try:
        if id_str:
            admin_id = int(id_str)
            admin_ids.append(admin_id)
    except ValueError:
        print(f"Некорректный ID администратора: {id_str}")

# Выводим список администраторов
if admin_ids:
    print(f"Список ID администраторов: {admin_ids}")
else:
    print("Нет корректных ID администраторов")

# Запрашиваем ID для проверки
try:
    check_id = input("Введите ваш ID пользователя Telegram для проверки: ")
    check_id = int(check_id)
    
    if check_id in admin_ids:
        print(f"ID {check_id} найден в списке администраторов.")
        print("Вы будете получать административные уведомления при запуске бота.")
        
        # Спрашиваем, хочет ли пользователь удалить себя из списка администраторов
        remove = input("Хотите удалить себя из списка администраторов? (y/n): ")
        if remove.lower() in ('y', 'yes', 'да'):
            # Удаляем ID из списка
            admin_ids.remove(check_id)
            
            # Формируем новую строку
            new_admin_ids_str = ",".join(str(admin_id) for admin_id in admin_ids)
            
            # Пытаемся обновить .env файл
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                with open(env_file, 'w', encoding='utf-8') as f:
                    for line in lines:
                        if line.strip().startswith('ADMIN_IDS='):
                            f.write(f'ADMIN_IDS={new_admin_ids_str}\n')
                        else:
                            f.write(line)
                
                print(f"ID {check_id} удален из списка администраторов.")
                print(f"Новый список администраторов: {admin_ids}")
                print("Перезапустите бота для применения изменений.")
            except Exception as e:
                print(f"Ошибка при обновлении файла .env: {e}")
                print(f"Обновите ADMIN_IDS={new_admin_ids_str} вручную в файле .env")
    else:
        print(f"ID {check_id} не найден в списке администраторов.")
        print("Вы должны видеть стандартный интерфейс бота с кнопкой СТАРТ.")
        
        # Спрашиваем, хочет ли пользователь добавить себя в список администраторов
        add = input("Хотите добавить себя в список администраторов? (y/n): ")
        if add.lower() in ('y', 'yes', 'да'):
            # Добавляем ID в список
            admin_ids.append(check_id)
            
            # Формируем новую строку
            new_admin_ids_str = ",".join(str(admin_id) for admin_id in admin_ids)
            
            # Пытаемся обновить .env файл
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                found = False
                with open(env_file, 'w', encoding='utf-8') as f:
                    for line in lines:
                        if line.strip().startswith('ADMIN_IDS='):
                            f.write(f'ADMIN_IDS={new_admin_ids_str}\n')
                            found = True
                        else:
                            f.write(line)
                    
                    if not found:
                        f.write(f'\nADMIN_IDS={new_admin_ids_str}\n')
                
                print(f"ID {check_id} добавлен в список администраторов.")
                print(f"Новый список администраторов: {admin_ids}")
                print("Перезапустите бота для применения изменений.")
            except Exception as e:
                print(f"Ошибка при обновлении файла .env: {e}")
                print(f"Обновите ADMIN_IDS={new_admin_ids_str} вручную в файле .env")
except ValueError:
    print("Введен некорректный ID. Должно быть целое число.")
except KeyboardInterrupt:
    print("\nПроверка отменена.") 