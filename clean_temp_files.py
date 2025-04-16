import os
import sys
import shutil
import glob
from pathlib import Path

def clean_all_temp_files():
    print("Очистка временных файлов и PID-файлов...")
    
    # Получаем корневую директорию проекта
    project_root = Path(__file__).parent.absolute()
    
    # 1. Удаляем PID-файл
    pid_file = project_root / "tmp" / "bot.pid"
    if pid_file.exists():
        try:
            os.remove(pid_file)
            print(f"Удален PID-файл: {pid_file}")
        except Exception as e:
            print(f"Ошибка при удалении PID-файла {pid_file}: {e}")
    
    # 2. Удаляем всю директорию tmp, если она существует
    tmp_dir = project_root / "tmp"
    if tmp_dir.exists():
        try:
            shutil.rmtree(tmp_dir)
            print(f"Удалена директория временных файлов: {tmp_dir}")
        except Exception as e:
            print(f"Ошибка при удалении директории {tmp_dir}: {e}")
    
    # 3. Удаляем .pyc файлы
    pyc_count = 0
    for pyc_file in glob.glob(str(project_root / "**/*.pyc"), recursive=True):
        try:
            os.remove(pyc_file)
            pyc_count += 1
        except Exception as e:
            print(f"Ошибка при удалении файла {pyc_file}: {e}")
    print(f"Удалено {pyc_count} .pyc файлов")
    
    # 4. Удаляем директории __pycache__
    pycache_count = 0
    for pycache_dir in glob.glob(str(project_root / "**/__pycache__"), recursive=True):
        try:
            shutil.rmtree(pycache_dir)
            pycache_count += 1
        except Exception as e:
            print(f"Ошибка при удалении директории {pycache_dir}: {e}")
    print(f"Удалено {pycache_count} директорий __pycache__")
    
    print("Очистка завершена")

if __name__ == "__main__":
    clean_all_temp_files() 