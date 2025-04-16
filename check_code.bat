REM filepath: d:\dmarket_trading_bot\check_code.bat
REM Скрипт для проверки качества кода в проекте dmarket_trading_bot
@echo off
setlocal enabledelayedexpansion

REM Определение лог-файла
set LOG_FILE=check_log.txt
echo Запуск проверок кода %date% %time% > %LOG_FILE%
echo ====================== >> %LOG_FILE%

REM Проверка наличия виртуальной среды
if not exist dmarket_bot_env\Scripts\activate.bat (
    echo Ошибка: Виртуальная среда не найдена. >> %LOG_FILE%
    echo Ошибка: Виртуальная среда не найдена.
    exit /b 1
)

REM Активация виртуального окружения
echo Активация виртуального окружения... >> %LOG_FILE%
call dmarket_bot_env\Scripts\activate.bat

REM Проверка установленных инструментов
echo Проверка установленных инструментов... >> %LOG_FILE%
for %%i in (flake8 pylint mypy pytest bandit) do (
    pip show %%i >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo Ошибка: Инструмент %%i не установлен. Установите: pip install %%i >> %LOG_FILE%
        echo Ошибка: Инструмент %%i не установлен. Установите: pip install %%i
        exit /b 1
    ) else (
        echo Инструмент %%i найден. >> %LOG_FILE%
    )
)

REM flake8: Проверка стиля кода на соответствие PEP 8
echo. >> %LOG_FILE%
echo Running flake8... >> %LOG_FILE%
echo Running flake8...
flake8 . >> %LOG_FILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Обнаружены проблемы со стилем кода (flake8). >> %LOG_FILE%
    echo Обнаружены проблемы со стилем кода (flake8). Подробности в %LOG_FILE%
) else (
    echo Проверка стиля кода успешно пройдена (flake8). >> %LOG_FILE%
    echo Проверка стиля кода успешно пройдена (flake8).
)

REM pylint: Статический анализ кода, обнаруживает ошибки и плохие практики
echo. >> %LOG_FILE%
echo Running pylint... >> %LOG_FILE%
echo Running pylint...
pylint *.py >> %LOG_FILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Обнаружены проблемы при статическом анализе (pylint). >> %LOG_FILE%
    echo Обнаружены проблемы при статическом анализе (pylint). Подробности в %LOG_FILE%
) else (
    echo Статический анализ успешно пройден (pylint). >> %LOG_FILE%
    echo Статический анализ успешно пройден (pylint).
)

REM mypy: Проверка аннотаций типов
echo. >> %LOG_FILE%
echo Running mypy... >> %LOG_FILE%
echo Running mypy...
mypy . >> %LOG_FILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Обнаружены проблемы с аннотациями типов (mypy). >> %LOG_FILE%
    echo Обнаружены проблемы с аннотациями типов (mypy). Подробности в %LOG_FILE%
) else (
    echo Проверка аннотаций типов успешно пройдена (mypy). >> %LOG_FILE%
    echo Проверка аннотаций типов успешно пройдена (mypy).
)

REM pytest: Запуск тестов
echo. >> %LOG_FILE%
echo Running tests... >> %LOG_FILE%
echo Running tests...
pytest tests/ >> %LOG_FILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Некоторые тесты не пройдены. >> %LOG_FILE%
    echo Некоторые тесты не пройдены. Подробности в %LOG_FILE%
) else (
    echo Все тесты успешно пройдены. >> %LOG_FILE%
    echo Все тесты успешно пройдены.
)

REM bandit: Проверка безопасности кода
echo. >> %LOG_FILE%
echo Running bandit... >> %LOG_FILE%
echo Running bandit...
bandit -r . >> %LOG_FILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Обнаружены потенциальные проблемы безопасности (bandit). >> %LOG_FILE%
    echo Обнаружены потенциальные проблемы безопасности (bandit). Подробности в %LOG_FILE%
) else (
    echo Проверка безопасности успешно пройдена (bandit). >> %LOG_FILE%
    echo Проверка безопасности успешно пройдена (bandit).
)

REM Итоговый результат
echo. >> %LOG_FILE%
echo Все проверки завершены. Подробные результаты в %LOG_FILE% >> %LOG_FILE%
echo Все проверки завершены. Подробные результаты в %LOG_FILE%

REM Деактивация виртуального окружения
call deactivate
echo. >> %LOG_FILE%
echo Виртуальное окружение деактивировано >> %LOG_FILE%
echo Виртуальное окружение деактивировано

pause
