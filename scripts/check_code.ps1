# Скрипт для запуска проверок кода в проекте dmarket_trading_bot
# Запуск: .\check_code.ps1 [-StyleChecks] [-StaticAnalysis] [-Tests] [-Coverage] [-Fix] [-GenerateHTML] [-InstallMissing] [-CheckImports] [-CommonErrors] [-AdvancedErrors]

# --- Блок параметров должен быть первым исполняемым кодом ---
param (
    [switch]$StyleChecks,
    [switch]$StaticAnalysis,
    [switch]$Tests,
    [switch]$Coverage,
    [switch]$Fix,
    [switch]$GenerateHTML,
    [switch]$InstallMissing,
    [switch]$CheckImports,
    [switch]$CommonErrors,
    [switch]$AdvancedErrors,
    [switch]$ChangedOnly,
    [switch]$CI,
    [switch]$Parallel,
    [switch]$CompareResults,
    [switch]$EnableCache,
    [string]$PytestArgs # Переименован параметр из $Args в $PytestArgs
)

# --- Проверка версии PowerShell ---
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Write-Host "Ошибка: Требуется PowerShell 5.1 или выше. Текущая версия: $($PSVersionTable.PSVersion)" -ForegroundColor Red
    exit 1
}

# --- Установка кодировки ПЕРЕМЕЩЕНА СЮДА ---
# Устанавливаем кодировку для корректного отображения кириллицы в консоли
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# Устанавливаем кодировку по умолчанию для вывода в файлы
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
# --- КОНЕЦ ПЕРЕМЕЩЕНИЯ ---


# --- Глобальные переменные и настройки ---
$scriptRoot = $PSScriptRoot # Сохраняем путь к директории скрипта
$logDateTime = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"

# --- Функция Write-Log ---
function Write-Log {
    param (
        [string]$Message,
        [ConsoleColor]$Color = "White",
        [switch]$NoNewline = $false,
        [switch]$NoTimestamp = $false
    )

    # Добавляем метку времени к сообщению для лога
    $timestamp = if (-not $NoTimestamp) { "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] " } else { "" }
    $logMessage = "${timestamp}${Message}"
    
    # Выводим на консоль с цветом
    if ($NoNewline) {
        Write-Host $Message -ForegroundColor $Color -NoNewline
    } else {
        Write-Host $Message -ForegroundColor $Color
    }
    
    # Записываем в лог-файл
    if (-not [string]::IsNullOrEmpty($logFile)) {
        $logMessage | Out-File -FilePath $logFile -Append
    }
}

# --- Функция чтения конфигурации --- 
function Read-Config {
    # Путь к конфигурационному файлу
    $configPath = Join-Path -Path $scriptRoot -ChildPath "check_code_config.json"
    # Значения по умолчанию
    $defaultConfig = @{
        exclude_dirs = @("dmarket_bot_env", "venv", ".venv", "__pycache__", ".git", ".mypy_cache", ".pytest_cache", "build", "dist", "*.egg-info", "logs", "reports", "docs", "tmp", "temp_fix", "tmp_dir")
        timeout_seconds = 600
        cache_enabled = $true # По умолчанию включено
        cache_max_age_days = 1
        report_formats = @("markdown") # По умолчанию только markdown
        log_dir = "logs"
        report_dir = "reports"
        tools = @{} # Для пользовательских настроек инструментов (например, аргументов)
        venv_path = "dmarket_bot_env" # Путь к виртуальному окружению
    }

    if (Test-Path $configPath) {
        try {
            Write-Log "Чтение конфигурации из $configPath" -Color Gray
            # ИСПРАВЛЕНИЕ: Удален параметр -AsHashtable для совместимости с PS 5.1
            $loadedConfig = Get-Content $configPath -Raw | ConvertFrom-Json 
            # Объединяем загруженную конфигурацию с дефолтной
            foreach ($key in $loadedConfig.Keys) {
                if ($defaultConfig.ContainsKey($key) -and $loadedConfig[$key] -is [hashtable] -and $defaultConfig[$key] -is [hashtable]) {
                    # Глубокое слияние для вложенных хеш-таблиц (например, tools)
                    foreach ($subKey in $loadedConfig[$key].Keys) {
                        $defaultConfig[$key][$subKey] = $loadedConfig[$key][$subKey]
                    }
                } else {
                    $defaultConfig[$key] = $loadedConfig[$key]
                }
            }
            return $defaultConfig
        } catch {
            # ИСПРАВЛЕНИЕ: Используем ${} для переменной перед :
            Write-Log "Ошибка чтения или разбора конфигурационного файла ${configPath}: $_" -Color Red
            Write-Log "Используются значения по умолчанию." -Color Yellow
            return $defaultConfig
        }
    } else {
        Write-Log "Конфигурационный файл $configPath не найден. Используются значения по умолчанию." -Color Gray
        return $defaultConfig
    }
}

# Загружаем конфигурацию
$config = Read-Config

# Переопределяем значения из конфига флагами командной строки
if ($PSBoundParameters.ContainsKey('EnableCache')) { $config.cache_enabled = $EnableCache }
if ($PSBoundParameters.ContainsKey('GenerateHTML')) { 
    # Флаг GenerateHTML включает форматы из конфига + markdown + html
    if ($config.report_formats -notcontains "markdown") { $config.report_formats += "markdown" }
    if ($config.report_formats -notcontains "html") { $config.report_formats += "html" } 
    if ($config.report_formats -notcontains "json") { $config.report_formats += "json" } # Добавляем JSON
}

# Используем пути из конфигурации, делая их абсолютными
$logDir = Join-Path -Path $scriptRoot -ChildPath $config.log_dir
$reportDir = Join-Path -Path $scriptRoot -ChildPath $config.report_dir
$logFile = Join-Path -Path $logDir -ChildPath "check_code_$logDateTime.log"
$cacheFile = Join-Path -Path $scriptRoot -ChildPath ".check_cache.json" # Кэш пока в корне
$venvPath = Join-Path -Path $scriptRoot -ChildPath $config.venv_path # Путь к venv из конфига

# --- Режим CI --- 
if ($CI) {
    $GenerateHTML = $true # Включаем генерацию отчетов
    # Добавляем JSON и HTML форматы, если их нет
    if ($config.report_formats -notcontains "json") { $config.report_formats += "json" }
    if ($config.report_formats -notcontains "html") { $config.report_formats += "html" }
    $Fix = $false  # В CI обычно только отчеты без исправлений
    $InstallMissing = $true # В CI обычно нужно устанавливать зависимости
    $EnableCache = $false # В CI обычно кэш не используется или управляется самой CI системой
    $config.cache_enabled = $false
    Write-Log "Запуск в режиме CI: отчеты ($($config.report_formats -join ', ')), без исправлений, с установкой зависимостей, кэш отключен." -Color Yellow
}

# --- Выбор проверок по умолчанию ---
if (-not ($StyleChecks -or $StaticAnalysis -or $Tests -or $Coverage -or $CheckImports -or $CommonErrors -or $AdvancedErrors)) {
    $StyleChecks = $true
    $StaticAnalysis = $true
    $Tests = $true
    $CheckImports = $true
    $CommonErrors = $true
    $AdvancedErrors = $true  # Включаем расширенную проверку ошибок по умолчанию
}

# --- Создание директорий --- 
if (-not (Test-Path -Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    Write-Log "Создана директория $logDir для хранения логов"
}
if (-not (Test-Path -Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    Write-Log "Создана директория $reportDir для хранения отчетов" -ForegroundColor Green
}

# --- Кэш --- 
$cache = @{}
if ($config.cache_enabled -and (Test-Path $cacheFile)) {
    try {
        # ИСПРАВЛЕНИЕ: Удален параметр -AsHashtable для совместимости с PS 5.1
        $cache = Get-Content $cacheFile -Raw | ConvertFrom-Json 
        # Если результат не хеш-таблица, попробуем преобразовать
        if ($cache -isnot [hashtable] -and $cache -is [psobject]) {
            $tempCache = @{
            }
            try {
                $cache.PSObject.Properties | ForEach-Object { $tempCache[$_.Name] = $_.Value }
                $cache = $tempCache
            } catch {
                Write-Log "Не удалось преобразовать загруженный кэш PSCustomObject в Hashtable. Кэш будет проигнорирован." -Color Yellow
                $cache = @{
                }
            }
        } elseif ($cache -isnot [hashtable]) {
             # Если это не PSCustomObject и не Hashtable, сбрасываем
             Write-Log "Загруженный кэш имеет неожиданный тип ($($cache.GetType().Name)). Кэш будет проигнорирован." -Color Yellow
             # ИСПРАВЛЕНИЕ: Закрывающая скобка для Hashtable
             $cache = @{
             }
        }
        Write-Log "Кэш загружен из $cacheFile" -ForegroundColor Green
    }
    catch {
        Write-Log "Ошибка при загрузке или разборе кэша: $_" -ForegroundColor Red
        # ИСПРАВЛЕНИЕ: Закрывающая скобка для Hashtable
        $cache = @{
        }
    }
}

# --- Функция Test-Environment ---
function Test-Environment {
    Write-Log "--- Проверка основного окружения ---" -Color Cyan
    $envOk = $true

    # Проверка Python
    Write-Log "Проверка Python..." -Color Gray -NoNewline
    $pythonExe = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonExe) {
        Write-Log " ОШИБКА: Команда \'python\' не найдена. Убедитесь, что Python установлен и добавлен в PATH." -Color Red
        $envOk = $false
    } else {
        $pythonVersion = try { (python --version 2>&1).Trim() } catch { "Не удалось получить версию" }
        Write-Log " OK ($pythonVersion, Путь: $($pythonExe.Source))" -Color Green
    }

    # Проверка Git (если используется ChangedOnly)
    if ($ChangedOnly) {
        Write-Log "Проверка Git..." -Color Gray -NoNewline
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            Write-Log " ОШИБКА: Команда \'git\' не найдена. Флаг -ChangedOnly не будет работать." -Color Red
            $envOk = $false
        } else {
            Write-Log " OK" -Color Green
        }
    }

    # Проверка Pandoc (если используется HTML отчет)
    if ($config.report_formats -contains "html") {
         Write-Log "Проверка Pandoc (для HTML отчетов)..." -Color Gray -NoNewline
         if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
             Write-Log " НЕ НАЙДЕН. HTML отчеты не будут сгенерированы. Установите Pandoc." -Color Yellow
         } else {
             Write-Log " OK" -Color Green
         }
    }

    return $envOk
}

# --- Функция Start-VirtualEnv ---
function Start-VirtualEnv {
    # Используем путь из $config
    # $envPath = "dmarket_bot_env" 
    $envPath = $script:venvPath # Используем переменную из внешней области видимости

    # Проверяем, существует ли директория виртуального окружения
    if (-not (Test-Path $envPath)) {
        Write-Log "Виртуальное окружение не найдено в $envPath" -Color Red
        # Запрашиваем у пользователя разрешение на создание
        $createEnv = Read-Host "Создать виртуальное окружение сейчас? (y/n)"
        if ($createEnv -eq "y") {
            Write-Log "Создание виртуального окружения..." -Color Cyan
            try {
                # Выполняем команду создания виртуального окружения
                python -m venv $envPath
                if ($LASTEXITCODE -ne 0) {
                    throw "Ошибка при выполнении python -m venv"
                }
                Write-Log "Виртуальное окружение '$envPath' успешно создано." -Color Green
            } catch {
                Write-Log "Ошибка при создании виртуального окружения: $_" -Color Red
                Write-Log "Убедитесь, что Python установлен и доступен в PATH." -Color Yellow
                exit 1
            }
        } else {
            # Если пользователь отказался, выходим, так как окружение необходимо
            Write-Log "Виртуальное окружение необходимо для работы скрипта. Выход." -Color Red
            exit 1
        }
    }

    # Проверяем наличие файла активации (дополнительная проверка)
    # Используем Join-Path для корректного формирования пути
    $activateScriptPath = Join-Path -Path $envPath -ChildPath "Scripts\\Activate.ps1"
    if (-not (Test-Path -Path $activateScriptPath)) {
        Write-Host "Ошибка: Файл активации виртуального окружения не найден в $activateScriptPath" -ForegroundColor Red
        Write-Host "Возможно, виртуальное окружение повреждено или создано некорректно." -ForegroundColor Yellow
        exit 1
    }

    try {
        Write-Log "Активация виртуального окружения..." -Color Cyan
        # Выполняем скрипт активации
        & $activateScriptPath

        # Проверяем успешность выполнения скрипта активации
        if (-not $?) {
            throw "Неудачная активация виртуального окружения (ошибка выполнения Activate.ps1)"
        }

        # Проверяем, установлена ли переменная окружения VIRTUAL_ENV
        if (-not (Test-Path env:VIRTUAL_ENV)) {
            throw "Виртуальное окружение не было активировано корректно (переменная VIRTUAL_ENV не установлена)"
        }

        Write-Log "Виртуальное окружение успешно активировано ($($env:VIRTUAL_ENV))" -ForegroundColor Green
    } catch {
        Write-Log "Ошибка при активации виртуального окружения: $_" -ForegroundColor Red
        Write-Host "Проверьте права доступа к файлу активации и целостность виртуального окружения." -ForegroundColor Yellow
        exit 1
    }
}

# --- Функция Test-Tools ---
function Test-Tools {
    # Список необходимых инструментов
    # ИЗМЕНЕНИЕ: Добавлены radon и safety
    $requiredTools = @("flake8", "pylint", "mypy", "bandit", "black", "isort", "autoflake", "pytest", "radon", "safety")
    $notInstalled = @()

    Write-Log "Проверка наличия необходимых инструментов..." -Color Cyan

    try {
        # Получаем список всех установленных пакетов с помощью pip freeze
        # Этот формат более стабилен для парсинга, чем pip list
        $installedPackagesOutput = python -m pip freeze 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Не удалось получить список установленных пакетов с помощью 'pip freeze'. Убедитесь, что pip доступен и работает."
        }
        # Преобразуем вывод в массив строк
        $installedPackages = $installedPackagesOutput -split [Environment]::NewLine | Where-Object { $_ }


        # Преобразуем список пакетов в хеш-таблицу для быстрой проверки
        $installedHash = @{
        }
        foreach ($packageLine in $installedPackages) {
            # pip freeze выводит в формате package==version или package @ file:///...
            $packageName = ($packageLine -split '==| @ ')[0].Trim()
            if (-not [string]::IsNullOrEmpty($packageName)) {
                $installedHash[$packageName.ToLower()] = $true
            }
        }

        # Проверяем наличие требуемых инструментов
        foreach ($tool in $requiredTools) {
            Write-Log "Проверка наличия $tool..." -Color Gray -NoNewline
            if ($installedHash.ContainsKey($tool.ToLower())) {
                Write-Log "OK" -Color Green
            } else {
                Write-Log "не найден!" -Color Red
                $notInstalled += $tool
            }
        }

        # Устанавливаем отсутствующие инструменты при необходимости
        if ($notInstalled.Count -gt 0) {
            Write-Log "Следующие инструменты не установлены: $($notInstalled -join ', ')" -Color Yellow

            if ($InstallMissing -or (Read-Host "Установить их сейчас? (y/n)") -eq "y") {
                Write-Log "Установка необходимых инструментов..." -Color Cyan

                # Устанавливаем инструменты с выводом прогресса и улучшенной обработкой ошибок
                foreach ($tool in $notInstalled) {
                    try {
                        Write-Log "Установка $tool..." -Color Gray
                        $pipOutput = python -m pip install $tool 2>&1 # Захватываем весь вывод
                        if ($LASTEXITCODE -ne 0) {
                            # ИСПРАВЛЕНИЕ: Добавляем вывод pip в сообщение об ошибке
                            throw "Команда \'pip install $tool\' завершилась с ошибкой (код выхода: $LASTEXITCODE). Вывод: $pipOutput"
                        }
                        Write-Log "Установлен $tool" -Color Green
                    } catch {
                        # Выводим сообщение об ошибке установки конкретного пакета
                        Write-Log "Ошибка при установке ${tool}: $($_.Exception.Message)" -Color Red
                        Write-Log "Попробуйте установить вручную: pip install $tool" -Color Yellow
                    }
                }

                # Дополнительная проверка после попытки установки
                Write-Log "Проверка установки завершена. Перепроверьте список инструментов." -Color Cyan

            } else {
                Write-Log "Продолжение без установки инструментов. Некоторые проверки могут не выполниться." -Color Yellow
                Write-Log "Для полноценной работы скрипта рекомендуется установить все инструменты." -Color Yellow
            }
        } else {
            Write-Log "Все необходимые инструменты установлены." -Color Green
        }
    } catch {
        Write-Log "Критическая ошибка при проверке или установке инструментов: $_" -Color Red
        Write-Log "Проверьте подключение к интернету, права доступа и корректность установки Python/pip." -Color Yellow
        return $false # Возвращаем $false при критической ошибке
    }

    return $true # Возвращаем $true, если проверка прошла успешно (даже если не все установлено, но без критических ошибок)
}

# --- Функция Get-FilesHash (Новая) ---
# Вычисляет комбинированный хеш для набора файлов
function Get-FilesHash {
    param (
        [string]$Path = ".",
        [string[]]$ExcludePatterns, # Получаем из $config
        [string]$Filter = "*.py",
        [string[]]$SpecificFiles = $null # Для хеширования конкретных файлов
    )
    
    $filesToHash = @()
    try {
        if ($SpecificFiles) {
            # Хешируем только указанные файлы
            $filesToHash = $SpecificFiles | Where-Object { Test-Path $_ -PathType Leaf } # Проверяем, что файл существует
            if ($filesToHash.Count -eq 0) {
                # Write-Log "Get-FilesHash: Не найдено указанных файлов для хеширования." -Color Gray
                return "no_specific_files_found"
            }
        } else {
            # Хешируем файлы в директории с исключениями
            # Строим регулярное выражение для исключения
            $excludeRegex = ($ExcludePatterns | ForEach-Object { [regex]::Escape($_).Replace('\\*', '.*') }) -join "|"
            $excludeRegex = $excludeRegex.Replace('/', '\\\\') # Для Windows

            # Получаем все файлы рекурсивно
            $allFiles = Get-ChildItem -Path $Path -Recurse -Filter $Filter -File -ErrorAction SilentlyContinue
            # Фильтруем по исключениям
            $filesToHash = $allFiles | Where-Object { $_.FullName -notmatch $excludeRegex }

            if ($filesToHash.Count -eq 0) {
                # Write-Log "Get-FilesHash: Не найдено файлов для хеширования (Путь: $Path, Фильтр: $Filter)" -Color Gray
                return "no_files_found_in_path"
            }
        }

        # Вычисляем хеши и объединяем
        $hashes = $filesToHash | Get-FileHash -Algorithm SHA256 | Select-Object -ExpandProperty Hash
        # Сортируем хеши для консистентности и объединяем
        $combinedHash = ($hashes | Sort-Object) -join ""
        # Возвращаем короткий хеш для ключа кэша
        return $combinedHash.Substring(0, [System.Math]::Min($combinedHash.Length, 40)) # Ограничиваем длину хеша

    } catch {
        Write-Log "Ошибка при вычислении хеша файлов: $_" -Color Red
        return "error_hashing_files_$(Get-Random)" # Возвращаем уникальное значение при ошибке
    }
}

# --- Функция Start-ParallelChecks ---
# Позволяет выполнять несколько задач одновременно, ускоряя общую проверку.
# param:
#   [array]$Tasks - Массив хеш-таблиц, каждая из которых описывает задачу ({Name, Command, Arguments})
#   [int]$MaxParallel - Максимальное количество одновременно выполняемых задач (по умолчанию - количество ядер процессора)
#   [int]$TimeoutSeconds - Тайм-аут для каждой задачи в секундах
function Start-ParallelChecks {
    param (
        [array]$Tasks,
        # Динамическое определение MaxParallel
        [int]$MaxParallel = ([System.Environment]::ProcessorCount - 1), 
        [int]$TimeoutSeconds = 600 # Таймаут из конфига используется по умолчанию
    )
    # Ограничиваем минимальное количество потоков до 1
    if ($MaxParallel -lt 1) { $MaxParallel = 1 }

    Write-Log "Запуск параллельных проверок (максимум $MaxParallel одновременно, таймаут $TimeoutSeconds сек)..." -Color Cyan

    # Создаем пул потоков (Runspace Pool)
    $RunspacePool = [RunspaceFactory]::CreateRunspacePool(1, $MaxParallel)
    $RunspacePool.Open()

    $Jobs = @()
    $Results = @{
    }
    # Скриптблок, который будет выполняться в каждом потоке
    $ScriptBlock = {
        param($taskInfo, $logFile, $scriptRoot, $timeoutSecondsParam) # Передаем необходимые параметры

        # Функция для логирования из потока (опционально, может замедлить)
        # function Write-ThreadLog { param([string]$Msg) "$([DateTime]::Now) [Thread $([System.Threading.Thread]::CurrentThread.ManagedThreadId)] $Msg" | Out-File -FilePath $logFile -Append -Encoding utf8 }

        $taskName = $taskInfo.Name
        $command = $taskInfo.Command
        $arguments = $taskInfo.Arguments
        $startTime = Get-Date

        $output = @()
        $exitCode = 0
        $success = $false
        $errorMessage = $null
        $fullCommand = "$command $arguments"

        try {
            # Write-ThreadLog "Запуск задачи $taskName: $fullCommand"
            # Используем Start-Process для запуска внешних команд
            $processInfo = New-Object System.Diagnostics.ProcessStartInfo
            $processInfo.FileName = $command
            $processInfo.Arguments = $arguments
            $processInfo.RedirectStandardError = $true
            $processInfo.RedirectStandardOutput = $true
            $processInfo.UseShellExecute = $false
            $processInfo.CreateNoWindow = $true
            $processInfo.WorkingDirectory = $scriptRoot # Устанавливаем рабочую директорию

            $process = New-Object System.Diagnostics.Process
            $process.StartInfo = $processInfo
            $process.Start() | Out-Null

            # Асинхронное чтение вывода, чтобы избежать блокировок
            $stdoutReader = $process.StandardOutput
            $stderrReader = $process.StandardError
            $stdoutOutput = $stdoutReader.ReadToEndAsync()
            $stderrOutput = $stderrReader.ReadToEndAsync()

            # Ожидание завершения процесса с тайм-аутом
            if (-not $process.WaitForExit($timeoutSecondsParam * 1000)) {
                # Процесс не завершился за отведенное время
                try {
                    # Write-ThreadLog "Задача '$taskName' превысила тайм-аут ($timeoutSecondsParam сек). Попытка завершения..."
                    $process.Kill()
                    # Write-ThreadLog "Процесс '$taskName' завершен принудительно."
                } catch {
                    # Write-ThreadLog "Ошибка при попытке остановить процесс '$taskName' после тайм-аута: $($_.Exception.Message)"
                }
                throw "Задача '$taskName' превысила тайм-аут ($timeoutSecondsParam сек)."
            }

            # Получаем результаты асинхронного чтения
            $stdout = $stdoutOutput.Result
            $stderr = $stderrOutput.Result
            # Объединяем и убираем пустые строки, нормализуем переносы строк
            $output = ($stdout + $stderr).Split([Environment]::NewLine) | Where-Object { $_ }

            $exitCode = $process.ExitCode
            $success = ($exitCode -eq 0)

            # Write-ThreadLog "Задача $taskName завершена с кодом $exitCode"

        } catch {
            # Write-ThreadLog "Ошибка выполнения задачи $taskName: $($_.Exception.Message)"
            $errorMessage = $_.Exception.Message
            $output += "Критическая ошибка: $errorMessage"
            $exitCode = -1 # Указываем на ошибку выполнения
            $success = $false
        }

        $endTime = Get-Date
        $duration = $endTime - $startTime

        # Возвращаем результат в виде хеш-таблицы
        return @{
            Name        = $taskName
            Command     = $fullCommand
            Output      = $output
            ExitCode    = $exitCode
            Success     = $success
            StartTime   = $startTime
            EndTime     = $endTime
            Duration    = $duration
            Error       = $errorMessage
            Timestamp   = Get-Date # Для кэширования
        }
    }

    # Запускаем задачи в пуле потоков
    $totalTasks = $Tasks.Count
    $completedCount = 0
    $startTime = Get-Date

    foreach ($task in $Tasks) {
        # Создаем объект PowerShell для выполнения скриптблока
        $JobInstance = [powershell]::Create().AddScript($ScriptBlock).AddArgument($task).AddArgument($logFile).AddArgument($PSScriptRoot).AddArgument($TimeoutSeconds) # Передаем параметры
        $JobInstance.RunspacePool = $RunspacePool
        # Сохраняем объект PowerShell, задачу и асинхронный результат
        $Jobs += @{
            Pipe = $JobInstance
            Task = $task
            Result = $JobInstance.BeginInvoke()
        }
        # Не логируем добавление в очередь, чтобы не засорять вывод
        # Write-Log "Задача $($task.Name) добавлена в очередь" -Color Gray
    }

    # Ожидаем завершения всех задач и собираем результаты
    Write-Log "Ожидание завершения параллельных задач..." -Color Cyan
    while ($Jobs.Count -gt 0) {
        $completedJobs = @()
        foreach ($JobInfo in $Jobs) {
            # Проверяем, завершилась ли задача
            if ($JobInfo.Result.IsCompleted) {
                try {
                    # Получаем результат выполнения
                    $taskResult = $JobInfo.Pipe.EndInvoke($JobInfo.Result)
                    $Results[$taskResult.Name] = $taskResult # Сохраняем результат по имени задачи
                    $completedCount++
                    $percent = if ($totalTasks -gt 0) { [math]::Round(($completedCount / $totalTasks) * 100, 0) } else { 0 }
                    $status = if ($taskResult.Success) { "Успешно" } else { "Ошибка (код $($taskResult.ExitCode))" }
                    # Выводим прогресс в лог
                    Write-Log "Прогресс: $completedCount/$totalTasks ($percent%) - Завершена $($taskResult.Name) - $status" -Color $(if ($taskResult.Success) { "Green" } else { "Red" })

                } catch {
                    # Ошибка при получении результата задачи (возможно, из-за прерывания или внутренней ошибки PowerShell)
                    $taskName = $JobInfo.Task.Name
                    $errorMessage = $_.Exception.Message
                    $Results[$taskName] = @{
                        Name = $taskName; Command = "$($JobInfo.Task.Command) $($JobInfo.Task.Arguments)"; Output = @("Ошибка получения результата: $errorMessage"); ExitCode = -1; Success = $false; Error = $errorMessage; Timestamp = Get-Date
                    }
                    $completedCount++
                    $percent = if ($totalTasks -gt 0) { [math]::Round(($completedCount / $totalTasks) * 100, 0) } else { 0 }
                    Write-Log "Прогресс: $completedCount/$totalTasks ($percent%) - Ошибка получения результата $($taskName): $errorMessage" -Color Red
                } finally {
                    # Освобождаем ресурсы PowerShell объекта
                    $JobInfo.Pipe.Dispose()
                    $completedJobs += $JobInfo # Добавляем в список для удаления из $Jobs
                }
            }
        }

        # Удаляем завершенные задачи из списка ожидания
        if ($completedJobs.Count -gt 0) {
            $Jobs = $Jobs | Where-Object { $completedJobs -notcontains $_ }
        }


        # Небольшая пауза, чтобы не загружать процессор в цикле ожидания
        Start-Sleep -Milliseconds 200
    }

    # Закрываем пул потоков
    $RunspacePool.Close()
    $RunspacePool.Dispose()

    $endTime = Get-Date
    $totalDuration = $endTime - $startTime

    # Выводим итоговую статистику
    $successCount = ($Results.Values | Where-Object { $_.Success }).Count
    $failedCount = $totalTasks - $successCount

    Write-Log "`nПараллельное выполнение завершено:" -Color Cyan
    Write-Log "- Успешно: $successCount задач" -Color Green
    Write-Log "- С ошибками: $failedCount задач" -Color $(if ($failedCount -gt 0) { "Red" } else { "Green" })
    Write-Log "- Общее время: $("{0:hh\\:mm\\:ss}" -f $totalDuration)" -Color Cyan

    # Проверяем наличие ошибок в результатах и выводим детали, если они есть
    if ($failedCount -gt 0) {
        Write-Log "Обнаружены ошибки в следующих задачах:" -Color Red
        foreach ($taskName in $Results.Keys | Sort-Object) {
            if (-not $Results[$taskName].Success) {
                Write-Log "- $taskName (Код выхода: $($Results[$taskName].ExitCode))" -Color Yellow
                # Выводим часть вывода ошибки для диагностики
                if ($Results[$taskName].Output -and $Results[$taskName].Output.Count -gt 0) {
                     # Ищем строки с ошибками/предупреждениями
                     $errorLines = $Results[$taskName].Output | Where-Object { $_ -match "error|warning|fail|traceback" -or $_ -match "^\s*E\s+" } | Select-Object -First 5
                     if ($errorLines.Count -gt 0) {
                         Write-Log "  Вывод (ошибки): $($errorLines -join "`n  ") ..." -Color Gray -NoTimestamp
                     } else {
                         # Если нет явных ошибок, выводим начало вывода
                         Write-Log "  Вывод (начало): $($Results[$taskName].Output | Select-Object -First 5 -Join "`n  ") ..." -Color Gray -NoTimestamp
                     }
                }
                if ($Results[$taskName].Error) {
                     Write-Log "  Ошибка выполнения: $($Results[$taskName].Error)" -Color Gray -NoTimestamp
                }
            }
        }
    }

    return $Results
}

# --- Функция Compare-Results ---
# Сравнивает текущий и предыдущий отчеты, выводит различия.
# param:
#   [string]$CurrentReport - Путь к текущему отчету.
#   [string]$PreviousReport - Путь к предыдущему отчету для сравнения.
function Compare-Results {
    param (
        [string]$CurrentReport,
        [string]$PreviousReport
    )
    
    if (-not (Test-Path $PreviousReport)) {
        Write-Log "Предыдущий отчет $PreviousReport не найден. Сравнение невозможно." -Color Yellow
        return $false
    }
    
    Write-Log "Сравнение с предыдущим отчетом: $PreviousReport" -Color Cyan
    
    $currentContent = Get-Content $CurrentReport
    $previousContent = Get-Content $PreviousReport
    
    # Анализируем изменения
    $diff = Compare-Object -ReferenceObject $previousContent -DifferenceObject $currentContent
    
    if ($null -eq $diff) {
        Write-Log "Изменений не обнаружено" -Color Green
        return $true
    }
    
    # Подсчитываем статистику изменений
    $additions = ($diff | Where-Object { $_.SideIndicator -eq "=>" }).Count
    $removals = ($diff | Where-Object { $_.SideIndicator -eq "<=" }).Count
    
    Write-Log "Изменения: +$additions, -$removals" -Color Magenta
    
    # Формируем отчет о различиях
    $diffReport = Join-Path -Path $reportDir -ChildPath "diff_report_$logDateTime.txt"
    "Сравнение отчетов: $CurrentReport и $PreviousReport" | Out-File -FilePath $diffReport
    "Добавлено строк: $additions" | Out-File -FilePath $diffReport -Append
    "Удалено строк: $removals" | Out-File -FilePath $diffReport -Append
    
    if ($additions -gt 0) {
        "`nНовые проблемы:" | Out-File -FilePath $diffReport -Append
        $diff | Where-Object { $_.SideIndicator -eq "=>" } | ForEach-Object {
            "  + $($_.InputObject)" | Out-File -FilePath $diffReport -Append
        }
    }
    
    if ($removals -gt 0) {
        "`nИсправленные проблемы:" | Out-File -FilePath $diffReport -Append
        $diff | Where-Object { $_.SideIndicator -eq "<=" } | ForEach-Object {
            "  - $($_.InputObject)" | Out-File -FilePath $diffReport -Append
        }
    }
    
    Write-Log "Отчет о различиях сохранен в $diffReport" -Color Green
    
    return $true
}

# --- Функция New-JUnitReport ---
function New-JUnitReport {
    param (
        [hashtable]$Results, 
        [string]$ReportDir, 
        [string]$LogDateTime
    )
    $xmlPath = Join-Path -Path $ReportDir -ChildPath "junit_report_$LogDateTime.xml"
    
    # Используем XmlWriter для более надежного создания XML
    $settings = New-Object System.Xml.XmlWriterSettings
    $settings.Indent = $true
    $writer = [System.Xml.XmlWriter]::Create($xmlPath, $settings)

    $writer.WriteStartDocument()
    $writer.WriteStartElement("testsuites")
    $writer.WriteStartElement("testsuite")
    $writer.WriteAttributeString("name", "CodeQuality")
    $writer.WriteAttributeString("tests", $Results.Count.ToString())
    
    $failures = 0
    $totalTime = [TimeSpan]::Zero
    
    foreach ($key in $Results.Keys) {
        $result = $Results[$key]
        $durationSeconds = $result.Duration.TotalSeconds.ToString("F3", [System.Globalization.CultureInfo]::InvariantCulture) # Формат с точкой
        $totalTime += $result.Duration

        $writer.WriteStartElement("testcase")
        $writer.WriteAttributeString("name", $key)
        $writer.WriteAttributeString("classname", "CodeQuality.$key") # Добавляем classname
        $writer.WriteAttributeString("time", $durationSeconds)

        if (-not $result.Success) {
            $failures++
            $writer.WriteStartElement("failure")
            $writer.WriteAttributeString("message", "Check failed with exit code $($result.ExitCode)")
            # Экранируем недопустимые символы в CDATA
            $failureOutput = $result.Output -join "`n"
            $failureOutput = $failureOutput -replace ']]>', ']]&gt;' # Экранируем закрытие CDATA
            $writer.WriteCData($failureOutput)
            $writer.WriteEndElement() # failure
        }
        $writer.WriteEndElement() # testcase
    }

    $writer.WriteAttributeString("failures", $failures.ToString())
    $writer.WriteAttributeString("time", $totalTime.TotalSeconds.ToString("F3", [System.Globalization.CultureInfo]::InvariantCulture))
    
    $writer.WriteEndElement() # testsuite
    $writer.WriteEndElement() # testsuites
    $writer.WriteEndDocument()
    $writer.Close()

    Write-Log "JUnit XML отчет сохранен в $xmlPath" -Color Green
    return $xmlPath
}

# --- Функция New-Report (Markdown) ---
function New-Report {
    param (
        [hashtable]$Results, 
        [string]$ReportDir, 
        [string]$LogDateTime
    )
    $reportPath = Join-Path -Path $ReportDir -ChildPath "check_report_$LogDateTime.md"
    $report = "# Отчет о проверке кода ($logDateTime)`n`n"
    $totalDuration = [TimeSpan]::Zero
    $failedChecks = 0

    foreach ($key in $Results.Keys | Sort-Object) {
        $result = $Results[$key]
        $status = if ($result.Success) { "✅ Успешно" } else { "❌ Ошибка" }
        $report += "## $key`n"
        $report += "- Статус: $status`n"
        $report += "- Время выполнения: $($result.Duration.TotalSeconds.ToString('F2')) сек`n" # Добавлено время выполнения
        $report += "- Код выхода: $($result.ExitCode)`n"
        if (-not $result.Success) {
            $failedChecks++
            $report += "- Вывод:`n````n"
            # Ограничиваем вывод в Markdown отчете
            $outputToShow = $result.Output | Select-Object -First 30 
            $report += ($outputToShow -join "`n")
            if ($result.Output.Count -gt 30) {
                $report += "`n... (вывод сокращен)"
            }
            $report += "`n````n"
        }
        $report += "`n"
        $totalDuration += $result.Duration
    }
    
    $report += "---\n"
    $report += "**Общая статистика:**`n" # Добавлена статистика
    $report += "- Всего проверок: $($Results.Count)`n"
    $report += "- Успешно: $($Results.Count - $failedChecks)`n"
    $report += "- С ошибками: $failedChecks`n"
    $report += "- Общее время: $($totalDuration.TotalSeconds.ToString('F2')) сек`n"

    $report | Out-File -FilePath $reportPath -Encoding utf8
    Write-Log "Markdown отчет сохранен в $reportPath" -Color Green
    return $reportPath
}

# --- Функция New-JsonReport ---
function New-JsonReport {
    param (
        [hashtable]$Results, 
        [string]$ReportDir, 
        [string]$LogDateTime
    )
    $reportPath = Join-Path -Path $ReportDir -ChildPath "check_report_$LogDateTime.json"
    $reportData = @{
        metadata = @{
            report_time = $logDateTime
            total_checks = $Results.Count
            total_duration_seconds = 0.0 
            failed_checks = 0
        }
        checks = @{
        } # Инициализируем пустым
    }
    $totalDuration = [TimeSpan]::Zero
    $failedChecks = 0

    foreach ($key in $Results.Keys | Sort-Object) {
        $result = $Results[$key]
        $durationSeconds = $result.Duration.TotalSeconds # Сохраняем как число
        $reportData.checks[$key] = @{
            success = $result.Success
            exit_code = $result.ExitCode
            duration_seconds = $durationSeconds # Добавлено время
            output = $result.Output # Полный вывод в JSON
        }
        $totalDuration += $result.Duration
        if (-not $result.Success) { $failedChecks++ }
    }
    
    $reportData.metadata.total_duration_seconds = $totalDuration.TotalSeconds
    $reportData.metadata.failed_checks = $failedChecks

    $reportData | ConvertTo-Json -Depth 5 | Out-File -FilePath $reportPath -Encoding utf8
    Write-Log "JSON отчет сохранен в $reportPath" -Color Green
    return $reportPath
}

# --- Функция Invoke-Tool ---
# Добавляем кэширование на уровне инструмента и очистку старого кэша
function Invoke-Tool {
    param (
        [string]$Name,
        [string]$Command,
        [string]$Arguments,
        [switch]$NoCache = $false,
        [array]$FilesToCheck = $null # Принимаем список файлов
    )

    $startTime = Get-Date
    $result = @{ Success = $false; Output = @(); Duration = New-TimeSpan; ExitCode = -1 }
    
    # --- Кэширование ---
    $filesHash = ""
    if ($FilesToCheck) {
        $filesHash = Get-FilesHash -FilePaths $FilesToCheck
    } else {
        # Если файлы не указаны, хешируем все .py файлы в проекте (кроме исключенных)
        # Это может быть медленно, лучше передавать $filesToCheck, если возможно
        $allPyFiles = Get-ChildItem -Path $scriptRoot -Recurse -Filter *.py | Where-Object { 
            $_.FullName -notmatch ($config.exclude_dirs -join '|') 
        }
        $filesHash = Get-FilesHash -FilePaths ($allPyFiles.FullName)
    }

    # Ключ кэша теперь включает имя инструмента и хеш файлов
    $cacheKey = "$Name-$filesHash" 
    
    if (-not $NoCache -and $config.cache_enabled -and $script:cache.ContainsKey($cacheKey)) {
        # Проверка возраста кэша
        $cachedItem = $script:cache[$cacheKey]
        if (((Get-Date) - $cachedItem.Timestamp).TotalDays -lt $config.cache_max_age_days) {
            Write-Log "[$Name] Используется кэшированный результат от $($cachedItem.Timestamp)." -Color DarkGray
            $cachedItem.Duration = [System.TimeSpan]::Parse($cachedItem.DurationString) # Восстанавливаем TimeSpan
            return $cachedItem
        } else {
            Write-Log "[$Name] Кэшированный результат устарел, выполняем команду..." -Color DarkGray
            $script:cache.Remove($cacheKey) # Удаляем устаревшую запись
        }
    }
    # --- Конец Кэширования ---

    Write-Log "[$Name] Запуск: $Command $Arguments" -Color Yellow
    
    try {
        # Перенаправляем stderr в stdout (2>&1) чтобы поймать ошибки
        $process = Start-Process $Command -ArgumentList $Arguments -NoNewWindow -PassThru -RedirectStandardOutput "$scriptRoot\\temp_stdout.log" -RedirectStandardError "$scriptRoot\\temp_stderr.log" -Wait
        
        $result.ExitCode = $process.ExitCode
        
        # Читаем stdout и stderr из временных файлов
        $stdoutContent = Get-Content "$scriptRoot\\temp_stdout.log" -Raw -ErrorAction SilentlyContinue
        $stderrContent = Get-Content "$scriptRoot\\temp_stderr.log" -Raw -ErrorAction SilentlyContinue
        
        # Объединяем вывод
        $result.Output = @()
        if (-not [string]::IsNullOrEmpty($stdoutContent)) { $result.Output += $stdoutContent.Split([Environment]::NewLine) }
        if (-not [string]::IsNullOrEmpty($stderrContent)) { $result.Output += $stderrContent.Split([Environment]::NewLine) }

        # Удаляем временные файлы
        Remove-Item "$scriptRoot\\temp_stdout.log" -ErrorAction SilentlyContinue
        Remove-Item "$scriptRoot\\temp_stderr.log" -ErrorAction SilentlyContinue

        $result.Success = ($result.ExitCode -eq 0)
        
        if ($result.Success) {
            Write-Log "[$Name] Успешно завершено (Код: $($result.ExitCode))." -Color Green
        } else {
            Write-Log "[$Name] Завершено с ошибкой (Код: $($result.ExitCode)). Вывод:" -Color Red
            # Выводим только первые N строк ошибки для краткости
            $result.Output | Select-Object -First 15 | ForEach-Object { Write-Log $_ -Color Red -NoTimestamp }
        }
    } catch {
        Write-Log "[$Name] Критическая ошибка при выполнении: $_" -Color Magenta
        $result.Output = $_.Exception.Message.Split([Environment]::NewLine)
        $result.Success = $false
        $result.ExitCode = -1 # Указываем код ошибки для критических сбоев
    }
    
    $endTime = Get-Date
    $result.Duration = $endTime - $startTime
    
    # --- Сохранение в кэш ---
    if (-not $NoCache -and $config.cache_enabled) {
        $cacheEntry = $result.PSObject.Copy() # Копируем результат
        $cacheEntry | Add-Member -NotePropertyName Timestamp -NotePropertyValue (Get-Date)
        # TimeSpan не сериализуется в JSON корректно, сохраняем как строку
        $cacheEntry | Add-Member -NotePropertyName DurationString -NotePropertyValue ($result.Duration.ToString()) 
        $cacheEntry.PSObject.Properties.Remove('Duration') # Удаляем исходный TimeSpan
        
        $script:cache[$cacheKey] = $cacheEntry
        Write-Log "[$Name] Результат сохранен в кэш." -Color DarkGray
    }
    # --- Конец Сохранения в кэш ---

    return $result
}

# --- Функция Get-ChangedFiles (Новая) ---
function Get-ChangedFiles {
    param(
        [string]$CompareTarget = "HEAD", # С чем сравнивать (HEAD, main, etc.)
        [string]$Filter = "*.py"
    )
    Write-Log "Получение измененных файлов ($Filter) относительно $CompareTarget..." -Color Gray
    try {
        # Проверяем, что мы в Git репозитории
        git rev-parse --is-inside-work-tree 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Предупреждение: Текущая директория не является Git репозиторием. Флаг -ChangedOnly не будет работать." -Color Yellow
            return @()
        }

        # Получаем список измененных (M) и добавленных (A) файлов относительно CompareTarget
        $gitOutput = git diff --name-only --diff-filter=AM $CompareTarget -- $Filter 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Ошибка выполнения git diff: $gitOutput"
        }
        $changedFilesRelative = $gitOutput -split [Environment]::NewLine | Where-Object { $_ }
        
        if ($changedFilesRelative.Count -gt 0) {
             Write-Log "Найдено измененных файлов: $($changedFilesRelative.Count)" -Color Gray
        } else {
             Write-Log "Измененные файлы ($Filter) не найдены." -Color Gray
        }
        # Возвращаем полные пути
        return $changedFilesRelative | ForEach-Object { Join-Path -Path $scriptRoot -ChildPath $_ }
    } catch {
        Write-Log "Ошибка при получении измененных файлов из Git: $_" -Color Red
        return @() # Возвращаем пустой массив при ошибке
    }
}

# === Основной блок выполнения ===

# Проверяем окружение
if (-not (Test-Environment)) {
    Write-Log "Обнаружены проблемы с окружением. Выход." -Color Red
    exit 1
}

# Активируем виртуальное окружение
Start-VirtualEnv

# Проверяем наличие инструментов
if (-not (Test-Tools)) {
    Write-Log "Проверка инструментов не удалась. Выход." -Color Red
    exit 1
}

# --- Секция проверок --- 
$allResults = @{
}
$tasksToRun = @()
$filesToCheck = $null

# ИСПРАВЛЕНИЕ: Логика для -ChangedOnly
if ($ChangedOnly) {
    $filesToCheck = Get-ChangedFiles -Filter "*.py"
    if ($filesToCheck.Count -eq 0) {
        Write-Log "Флаг -ChangedOnly указан, но измененные Python файлы не найдены. Проверки не будут запущены." -Color Yellow
        exit 0 # Выходим успешно
    }
    Write-Log "Запуск проверок только для измененных файлов: $($filesToCheck -join ', ')" -Color Cyan
}

# Собираем задачи для выполнения
# Используем $config для настройки
# Формируем строки исключений для разных инструментов
# ИСПРАВЛЕНИЕ: Удалена неиспользуемая переменная $excludeDirsForArgs
# $excludeDirsForArgs = $config.exclude_dirs | ForEach-Object { [regex]::Escape($_).Replace('\\*', '.*').Replace('/', '\\') } # Готовим для regex или прямого exclude
# $excludeArgsStringGeneric = ($config.exclude_dirs | ForEach-Object { "--exclude=$_" }) -join " " # Общий формат для многих инструментов
# $excludeArgsStringPylint = ($config.exclude_dirs | ForEach-Object { "--ignore=$_" }) -join " " # Pylint использует --ignore
# $excludeArgsStringMypy = ($config.exclude_dirs | ForEach-Object { "--exclude=$_" }) -join " " # Используем $excludeArgsStringGeneric
# $excludeArgsStringBandit = ($config.exclude_dirs | ForEach-Object { "--exclude=$_" }) -join " " # Используем $excludeArgsStringGeneric

# Аргумент для файлов: либо список измененных (экранированных), либо ".":
# ИСПРАВЛЕНИЕ: Удалена неиспользуемая переменная $filesArgumentForToolsAcceptingList
# $filesArgumentForToolsAcceptingList = if ($filesToCheck) { ($filesToCheck | ForEach-Object { "'$_'" }) -join " " } else { "." } # Экранируем пути с пробелами
$targetArgument = if ($filesToCheck) { ($filesToCheck | ForEach-Object { if ($_ -match '\\s') { "'$_'" } else { $_ } }) -join " " } else { "." } # Экранируем пути с пробелами, если нужно

if ($StyleChecks) {
    # Используем $targetArgument вместо "." или списка файлов
    # Используем --config для flake8
    $tasksToRun += @{ Name = "flake8"; Command = "python"; Arguments = "-m flake8 --config=.flake8 $targetArgument" }
    # Black и isort обычно используют pyproject.toml, оставляем как есть или добавляем --config если нужно
    $tasksToRun += @{ Name = "black (check)"; Command = "python"; Arguments = "-m black --check --diff $targetArgument" }
    $tasksToRun += @{ Name = "isort (check)"; Command = "python"; Arguments = "-m isort --check-only --diff $targetArgument" }
}
if ($StaticAnalysis) {
    # Используем --rcfile для pylint
    # Используем --config-file для mypy
    $tasksToRun += @{ Name = "pylint"; Command = "python"; Arguments = "-m pylint --rcfile=.pylintrc $targetArgument" }
    $tasksToRun += @{ Name = "mypy"; Command = "python"; Arguments = "-m mypy --config-file=mypy.ini $targetArgument" }
    # Bandit и Radon не требуют явного конфига здесь, если он не указан
    $tasksToRun += @{ Name = "bandit"; Command = "python"; Arguments = "-m bandit -r $targetArgument" }
    $tasksToRun += @{ Name = "radon cc"; Command = "python"; Arguments = "-m radon cc -a -s $targetArgument" } # Цикломатическая сложность
    $tasksToRun += @{ Name = "radon mi"; Command = "python"; Arguments = "-m radon mi -s $targetArgument" } # Индекс поддерживаемости
    $tasksToRun += @{ Name = "safety"; Command = "python"; Arguments = "-m safety check" } # Проверка зависимостей
}
if ($Tests) {
    # Получаем базовые аргументы из конфига, если они есть
    $pytestBaseArgs = if ($config.tools.ContainsKey('pytest')) { $config.tools['pytest'].args } else { "" }
    # Собираем все аргументы вместе
    $pytestFinalArgs = $pytestBaseArgs
    if (-not [string]::IsNullOrEmpty($PytestArgs)) { # Используем $PytestArgs
        $pytestFinalArgs += " $PytestArgs" # Добавляем аргументы из командной строки
    }
    # Добавляем задачу pytest с финальными аргументами
    $tasksToRun += @{ Name = "pytest"; Command = "python"; Arguments = "-m pytest $pytestFinalArgs $targetArgument" } # Добавляем $targetArgument для возможности запуска на измененных файлах
}
if ($Coverage) {
    # Аналогично для coverage, если нужно передавать аргументы
    $pytestBaseArgs = if ($config.tools.ContainsKey('pytest')) { $config.tools['pytest'].args } else { "" }
    $pytestFinalArgs = $pytestBaseArgs
    if (-not [string]::IsNullOrEmpty($PytestArgs)) { # Используем $PytestArgs
        $pytestFinalArgs += " $PytestArgs" 
    }
    # Добавляем --cov аргументы
    $coverageArgs = "--cov=. --cov-report=term-missing" # Базовые аргументы для покрытия
    if ($GenerateHTML) { $coverageArgs += " --cov-report=html:$reportDir/coverage_report" } # HTML отчет, если нужно
    
    $tasksToRun += @{ Name = "pytest (coverage)"; Command = "python"; Arguments = "-m pytest $coverageArgs $pytestFinalArgs $targetArgument" }
}
if ($CheckImports) {
    # ИСПРАВЛЕНИЕ: Указываем путь к скриптам в DM
    $tasksToRun += @{ Name = "check_imports.py"; Command = "python"; Arguments = "DM/check_imports.py" }
    $tasksToRun += @{ Name = "check_dependencies.py"; Command = "python"; Arguments = "DM/check_dependencies.py" }
}
if ($CommonErrors) {
    # ИСПРАВЛЕНИЕ: Указываем путь к скрипту в DM
    $commonErrorsArgs = "DM/check_common_errors.py"
    if ($Fix) {
        # В режиме Fix отчет не нужен, так как будет запущен скрипт исправления
        # $commonErrorsArgs += " --output=common_errors_report.txt"
    } else {
         $commonErrorsArgs += " --output=reports/common_errors_report.txt" # Сохраняем отчет, если не исправляем
    }
    $tasksToRun += @{ Name = "check_common_errors.py"; Command = "python"; Arguments = $commonErrorsArgs }
}
if ($AdvancedErrors) {
    # ИСПРАВЛЕНИЕ: Указываем путь к скрипту в DM
    $tasksToRun += @{ Name = "check_errors.py"; Command = "python"; Arguments = "DM/check_errors.py" }
}

# Выполняем задачи
if ($Parallel -and $tasksToRun.Count -gt 1) {
    # Разделение на быстрые и медленные задачи (пример)
    $fastTaskNames = "flake8", "black (check)", "isort (check)" # Пример быстрых
    $fastTasks = $tasksToRun | Where-Object { $fastTaskNames -contains $_.Name }
    $slowTasks = $tasksToRun | Where-Object { $fastTaskNames -notcontains $_.Name }

    Write-Log "Разделение на быстрые ($($fastTasks.Count)) и медленные ($($slowTasks.Count)) задачи." -Color Cyan
    
    # Запускаем сначала быстрые, потом медленные (можно настроить MaxParallel для каждой группы)
    $resultsFast = @{}
    $resultsSlow = @{}
    if ($fastTasks.Count -gt 0) {
        # Можно задать больше потоков для быстрых задач
        $resultsFast = Start-ParallelChecks -Tasks $fastTasks -MaxParallel $MaxParallel -TimeoutSeconds $config.timeout_seconds 
    }
    if ($slowTasks.Count -gt 0) {
         # Можно задать меньше потоков для медленных задач, если они ресурсоемкие
        $resultsSlow = Start-ParallelChecks -Tasks $slowTasks -MaxParallel ([Math]::Max(1, $MaxParallel / 2)) -TimeoutSeconds $config.timeout_seconds 
    }
    # Объединяем результаты
    $allResults = @{}
    $resultsFast.GetEnumerator() | ForEach-Object { $allResults[$_.Name] = $_.Value }
    $resultsSlow.GetEnumerator() | ForEach-Object { $allResults[$_.Name] = $_.Value }

} else {
    # Последовательное выполнение
    Write-Log "Запуск проверок последовательно..." -Color Cyan
    foreach ($task in $tasksToRun) {
        $allResults[$task.Name] = Invoke-Tool -Name $task.Name -Command $task.Command -Arguments $task.Arguments -FilesToCheck $filesToCheck # Передаем $filesToCheck
    }
}

# --- Секция автоматического исправления (если указан флаг -Fix) ---
if ($Fix) {
    Write-Log "--- Запуск автоматического исправления ---" -Color Cyan
    $fixTasks = @()
    if ($StyleChecks) {
        # Black и isort исправляют стиль
        $fixTasks += @{ Name = "black (fix)"; Command = "python"; Arguments = "-m black $targetArgument"; NoCache = $true }
        $fixTasks += @{ Name = "isort (fix)"; Command = "python"; Arguments = "-m isort $targetArgument"; NoCache = $true }
        # Autoflake для удаления неиспользуемых импортов/переменных
        $autoflakeArgs = "--remove-all-unused-imports --remove-unused-variables --in-place --recursive"
        # Исключаем __init__.py, так как там часто бывают "unused" импорты для экспорта
        $autoflakeExclude = "--exclude=__init__.py" 
        $fixTasks += @{ Name = "autoflake (fix)"; Command = "python"; Arguments = "-m autoflake $autoflakeArgs $autoflakeExclude $targetArgument"; NoCache = $true }
    }
    # Добавляем исправления для MyPy и Pylint (через autopep8)
    if ($AdvancedErrors -and $Fix) {
        # MyPy: установка типов
        $fixTasks += @{ Name = "mypy (install types)"; Command = "python"; Arguments = "-m mypy --install-types --non-interactive $targetArgument"; NoCache = $true }
    } # <-- Добавлена закрывающая скобка
    if ($StaticAnalysis -and $Fix) {
        # Pylint: используем autopep8 для исправления некоторых проблем стиля
        # Исправлен синтаксис -match и экранирование кавычек
        $autopep8Target = if ($filesToCheck) { ($filesToCheck | ForEach-Object { if ($_ -match '\\s') { "'$_'" } else { $_ } }) -join " " } else { "." }
        $fixTasks += @{ Name = "autopep8 (fix)"; Command = "python"; Arguments = "-m autopep8 --in-place --aggressive --recursive $autopep8Target"; NoCache = $true }
    } # <-- Добавлена закрывающая скобка

    if ($fixTasks.Count -gt 0) {
        # Выполняем задачи исправления последовательно
        $totalFixTasks = $fixTasks.Count
        $currentFixTask = 0
        Write-Log "Запуск задач автоматического исправления..." -Color Magenta
        foreach ($task in $fixTasks) {
            $currentFixTask++
            # ИСПРАВЛЕНИЕ: Проверка деления на ноль и экранирование процента
            $percent = if ($totalFixTasks -gt 0) { [math]::Round(($currentFixTask / $totalFixTasks) * 100, 0) } else { 0 }
            Write-Progress -Activity "Исправление кода" -Status "Задача: $($task.Name) ($currentFixTask/$totalFixTasks)" -PercentComplete $percent
            # ИСПРАВЛЕНИЕ: Экранируем знак процента для Write-Log с помощью {0}
            $fixProgressMessage = "Прогресс исправления: $currentFixTask/$totalFixTasks ({0}%%) - Выполняется $($task.Name)..." -f $percent
            Write-Log $fixProgressMessage -Color Magenta -NoNewline
            
            # ИСПРАВЛЕНИЕ: Используем Splatting для передачи параметров в Invoke-Tool (для секции Fix)
            $invokeFixToolParams = @{
                Name = $task.Name
                Command = $task.Command
                Arguments = $task.Arguments
            }
            if ($task.ContainsKey('InputFiles') -and $task.InputFiles) {
                $invokeFixToolParams.InputFiles = $task.InputFiles
            }
            if ($task.ContainsKey('NoCache') -and $task.NoCache) {
                $invokeFixToolParams.NoCache = $true
            }
            
            Invoke-Tool @invokeFixToolParams # Вызов с использованием splatting
            
            Write-Host ""
        }
        Write-Progress -Activity "Исправление кода" -Completed
        Write-Log "Автоматическое исправление завершено. Рекомендуется проверить изменения." -Color Green
    } else {
        Write-Log "Нет задач для автоматического исправления." -Color Gray
    }
} # <-- Добавлена закрывающая скобка

# --- Сохранение кэша ---
if ($config.cache_enabled) {
    try {
        # Убедимся, что директория для кэша существует (если она не в корне)
        $cacheDir = Split-Path -Path $cacheFile -Parent
        if ($cacheDir -and (-not (Test-Path -Path $cacheDir))) {
            New-Item -Path $cacheDir -ItemType Directory -Force | Out-Null
        }
        # ИСПРАВЛЕНИЕ: Используем .NET метод для записи в UTF8 (стандартный для JSON)
        # Хотя Out-File -Encoding 'utf8' должен работать, используем .NET для единообразия и надежности
        [System.IO.File]::WriteAllText($cacheFile, ($cache | ConvertTo-Json -Depth 10), [System.Text.Encoding]::UTF8)
        # $cache | ConvertTo-Json -Depth 10 | Out-File -FilePath $cacheFile -Encoding 'utf8' # Альтернатива, если .NET метод вызовет проблемы
        Write-Log "Кэш сохранен в $cacheFile" -Color Green
    } catch {
        Write-Log "Ошибка при сохранении кэша: $_" -ForegroundColor Red
    }
}

# --- Генерация отчетов --- 
$markdownReportPath = $null
$htmlReportPath = $null

if ($GenerateHTML -or ($config.report_formats.Count -gt 0)) { # Генерируем, если есть флаг или форматы в конфиге
    Write-Log "--- Генерация отчетов ---" -Color Cyan
    
    # Используем $config.report_formats для определения, какие отчеты генерировать
    if ($config.report_formats -contains "markdown") {
        $markdownReportPath = New-Report -Results $allResults -ReportDir $reportDir -LogDateTime $logDateTime
    }
    if ($config.report_formats -contains "json") {
        # Вызываем функцию и отбрасываем результат
        New-JsonReport -Results $allResults -ReportDir $reportDir -LogDateTime $logDateTime | Out-Null
    }
    if ($config.report_formats -contains "junit") { # Добавлена генерация JUnit
        # Вызываем функцию и отбрасываем результат
        New-JUnitReport -Results $allResults -ReportDir $reportDir -LogDateTime $logDateTime | Out-Null
    }
    if ($config.report_formats -contains "html" -and $markdownReportPath -and (Get-Command pandoc -ErrorAction SilentlyContinue)) {
        # Генерация HTML из Markdown с помощью Pandoc
        $htmlReportPath = Join-Path -Path $reportDir -ChildPath "check_report_$logDateTime.html"
        try {
            pandoc $markdownReportPath -o $htmlReportPath --metadata title="Отчет о проверке кода $logDateTime" --standalone --toc
            Write-Log "HTML отчет сохранен в $htmlReportPath" -Color Green
        } catch {
            Write-Log "Ошибка при генерации HTML отчета с помощью Pandoc: $_" -Color Red
            $htmlReportPath = $null # Сбрасываем путь, если генерация не удалась
        }
    } elseif ($config.report_formats -contains "html" -and -not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
         Write-Log "Pandoc не найден. HTML отчет не будет сгенерирован." -Color Yellow
    }
}

# --- Сравнение результатов (если требуется) ---
if ($CompareResults -and $markdownReportPath) {
    # Находим предыдущий отчет
    $previousReports = Get-ChildItem -Path $reportDir -Filter "code_quality_report_*.md" |
    Where-Object { $_.FullName -ne $markdownReportPath } | # Исключаем текущий отчет
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

    if ($previousReports) {
        $previousReportPath = $previousReports.FullName
        Compare-Results -CurrentReport $markdownReportPath -PreviousReport $previousReportPath
    }
    else {
        Write-Log "Предыдущие отчеты не найдены для сравнения" -Color Yellow
    }
}

Write-Log "Все проверки завершены. Подробные результаты в $logFile" -Color Cyan

# --- Краткое резюме --- 
if ($allResults.Count -gt 0) {
    Write-Log "`n--- Краткое резюме проверок ---" -Color Cyan
    $summary = $allResults.Values | Select-Object Name, @{Name="Status";Expression={if($_.Success){"✅ Success"}else{"❌ Failed"}}}, @{Name="Duration (s)";Expression={if($_.Duration){"{0:N2}" -f $_.Duration.TotalSeconds}else{"N/A"}}}
    $summary | Format-Table -AutoSize
}

# --- Деактивация виртуального окружения ---
if (Get-Command deactivate -ErrorAction SilentlyContinue) {
    deactivate
    Write-Host "Виртуальное окружение деактивировано" -ForegroundColor Cyan
} else {
    Write-Log "Не удалось деактивировать виртуальное окружение" -Color Red
}

# --- Завершение скрипта --- 
$failedChecksCount = 0
if ($allResults.Values) {
    # Убедимся, что проверяем только корректные результаты
    $failedChecksCount = ($allResults.Values | Where-Object { $_ -and $_.PSObject.Properties.Name -contains 'Success' -and -not $_.Success }).Count
}

if ($failedChecksCount -gt 0) {
    Write-Log "Обнаружено ошибок: $failedChecksCount. Скрипт завершается с кодом $failedChecksCount." -Color Red
    exit $failedChecksCount # Выход с количеством ошибок для CI/CD
} else {
    Write-Log "Все проверки успешно завершены. Скрипт завершается с кодом 0." -Color Green
    exit 0 # Успешный выход
}