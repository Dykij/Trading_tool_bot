# Проверка импорта модуля utils.security
import sys
import os

print("Проверяю файл utils/security.py...")
try:
    import utils.security
    print("Файл успешно импортирован!")
except Exception as e:
    print(f"Ошибка при импорте: {e}") 