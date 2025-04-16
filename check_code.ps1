# Скрипт для запуска проверок кода в проекте dmarket_trading_bot
# Запуск: .\check_code.ps1 [-StyleChecks] [-StaticAnalysis] [-Tests] [-Coverage] [-Fix] [-GenerateHTML] [-InstallMissing] [-CheckImports] [-CommonErrors] [-AdvancedErrors]

# Устанавливаем кодировку для корректного отображения кириллицы
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# Устанавливаем кодировку для вывода в файлы
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

param (
    [switch]$StyleChecks = $false,
    [switch]$StaticAnalysis = $false,
    [switch]$Tests = $false,
    [switch]$Coverage = $false,
    [switch]$Fix = $false,
    [switch]$GenerateHTML = $false,
    [switch]$InstallMissing = $false,
    [switch]$CheckImports = $false,
    [switch]$CommonErrors = $false,
    [switch]$AdvancedErrors = $false, # Новый параметр для расширенной проверки ошибок
    [switch]$ChangedOnly = $false, # Новый параметр для проверки только измененных файлов
    [switch]$CI = $false, # Новый параметр для режима CI
    [switch]$Parallel = $false, # Новый параметр для параллельного запуска проверок
    [switch]$Compare = $false, # Новый параметр для сравнения с предыдущими результатами
    [switch]$EnableCache = $false      # Новый параметр для кэширования результатов
)

# Если запуск в режиме CI, настраиваем соответствующие параметры
if ($CI) {
    $GenerateHTML = $true
    $Fix = $false  # В CI обычно только отчеты без исправлений
    Write-Host "Запуск в режиме CI - генерация HTML-отчетов без автоматических исправлений" -ForegroundColor Yellow
}

# Если не указаны конкретные проверки, запускаем все
if (-not ($StyleChecks -or $StaticAnalysis -or $Tests -or $Coverage -or $CheckImports -or $CommonErrors -or $AdvancedErrors)) {
    $StyleChecks = $true
    $StaticAnalysis = $true
    $Tests = $true
    $CheckImports = $true
    $CommonErrors = $true
    $AdvancedErrors = $true  # Включаем расширенную проверку ошибок по умолчанию
}

# Создаем директории для логов
if (-not (Test-Path -Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
    Write-Host "Создана директория logs для хранения логов"
}

# Директория для хранения отчетов
if (-not (Test-Path -Path "reports")) {
    New-Item -ItemType Directory -Path "reports" | Out-Null
    Write-Host "Создана директория reports для хранения отчетов" -ForegroundColor Green
}

# Кэш для ускорения повторных проверок
$cacheFile = ".check_cache.json"
$cache = @{}
if ($EnableCache -and (Test-Path $cacheFile)) {
    try {
        $cache = Get-Content $cacheFile -Raw | ConvertFrom-Json -AsHashtable
        Write-Host "Кэш загружен из $cacheFile" -ForegroundColor Green
    }
    catch {
        Write-Host "Ошибка при загрузке кэша: $_" -ForegroundColor Red
        $cache = @{}
    }
}

# Функция для активации виртуального окружения
function Start-VirtualEnv {
    $envPath = "dmarket_bot_env"
    if (-not (Test-Path -Path "$envPath\Scripts\Activate.ps1")) {
        Write-Host "Ошибка: Виртуальное окружение не найдено в $envPath" -ForegroundColor Red
        exit 1
    }

    Write-Host "Активация виртуального окружения..." -ForegroundColor Cyan
    & "$envPath\Scripts\Activate.ps1"

    if (-not $?) {
        Write-Host "Ошибка при активации виртуального окружения" -ForegroundColor Red
        exit 1
    }
}

# Функция для проверки установленных инструментов
function Test-Tools {
    $requiredTools = @("flake8", "pylint", "mypy", "bandit", "black", "isort", "autoflake", "pytest")
    $notInstalled = @()

    foreach ($tool in $requiredTools) {
        Write-Host "Проверка наличия $tool..." -NoNewline
        $null = python -m pip show $tool 2>&1

        if ($LASTEXITCODE -ne 0) {
            Write-Host "не найден!" -ForegroundColor Red
            $notInstalled += $tool
        }
        else {
            Write-Host "OK" -ForegroundColor Green
        }
    }

    if ($notInstalled.Count -gt 0) {
        Write-Host "Следующие инструменты не установлены: $($notInstalled -join ', ')" -ForegroundColor Yellow
        $install = Read-Host "Установить их сейчас? (y/n)"
        if ($install -eq "y" -or $InstallMissing) {
            Write-Host "Установка необходимых инструментов..." -ForegroundColor Cyan
            python -m pip install $notInstalled

            if ($LASTEXITCODE -ne 0) {
                Write-Host "Ошибка при установке инструментов" -ForegroundColor Red
                exit 1
            }
            Write-Host "Инструменты успешно установлены" -ForegroundColor Green
        }
        else {
            Write-Host "Продолжение без установки инструментов. Некоторые проверки могут не выполниться." -ForegroundColor Yellow
        }
    }
}

# Функция для параллельного запуска проверок
function Start-ParallelChecks {
    param (
        [array]$Tasks
    )
    
    Write-Log "Запуск параллельных проверок..." -Color Cyan
    $jobs = @()
    
    foreach ($task in $Tasks) {
        Write-Log "Запуск задачи: $($task.Name) в фоновом режиме" -Color Gray
        $jobs += Start-Job -ScriptBlock {
            param($command, $arguments)
            Invoke-Expression "$command $arguments 2>&1"
            return $LASTEXITCODE
        } -ArgumentList $task.Command, $task.Arguments
    }
    
    # Отображаем прогресс выполнения
    $completedJobs = 0
    $totalJobs = $jobs.Count
    
    while ($jobs | Where-Object { $_.State -eq "Running" }) {
        $completedJobs = ($jobs | Where-Object { $_.State -eq "Completed" }).Count
        Show-Progress -Current $completedJobs -Total $totalJobs -Activity "Выполнение параллельных проверок"
        Start-Sleep -Seconds 1
    }
    
    # Собираем результаты
    $results = @{}
    foreach ($job in $jobs) {
        $jobIndex = [array]::IndexOf($jobs, $job)
        $taskName = $Tasks[$jobIndex].Name
        
        $output = Receive-Job -Job $job
        $exitCode = $job.ChildJobs[0].Output[-1]
        
        $results[$taskName] = @{
            Output   = $output
            ExitCode = $exitCode
        }
        
        # Записываем результат в лог
        $output | Out-File -FilePath $logFile -Append
        
        if ($exitCode -eq 0) {
            Write-Log "${taskName}: Успешно" -Color Green
        }
        else {
            Write-Log "${taskName}: Обнаружены проблемы (код выхода $exitCode)" -Color Red
        }
    }
    
    # Очищаем задания
    $jobs | Remove-Job
    
    return $results
}

# Функция для отображения прогресса
function Show-Progress {
    param (
        [int]$Current,
        [int]$Total,
        [string]$Activity
    )
    
    $percentComplete = ($Current / $Total) * 100
    Write-Progress -Activity $Activity -Status "$Current из $Total завершено" -PercentComplete $percentComplete
}

# Функция для сравнения текущих результатов с предыдущими
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
    $diffReport = "reports\diff_report_$logDateTime.txt"
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

# Функция формирования итогового отчета
function New-Report {
    param (
        [hashtable]$Results,
        [string]$Title = "Отчет о проверке кода"
    )
    
    $reportDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $reportPath = "reports\code_quality_report_$logDateTime.md"
    
    # Формируем отчет в формате Markdown
    $report = "# $Title`n`n"
    $report += "**Дата проверки:** $reportDate`n`n"
    
    # Общая статистика
    $totalChecks = $Results.Count
    $successChecks = ($Results.Values | Where-Object { $_.ExitCode -eq 0 }).Count
    $failedChecks = $totalChecks - $successChecks
    
    $report += "## Общая статистика`n`n"
    $report += "- **Всего проверок:** $totalChecks`n"
    $report += "- **Успешно:** $successChecks`n"
    $report += "- **С ошибками:** $failedChecks`n`n"
    
    # Детали по каждой проверке
    $report += "## Детали проверок`n`n"
    
    foreach ($key in $Results.Keys) {
        $result = $Results[$key]
        $status = if ($result.ExitCode -eq 0) { "✅ Успешно" } else { "❌ Ошибка" }
        
        $report += "### $key - $status`n`n"
        
        if ($result.ExitCode -ne 0) {
            $report += "````n"
            $report += "$($result.Output -join "`n")`n"
            $report += "````n`n"
        }
        else {
            $report += "_Проверка прошла успешно_`n`n"
        }
    }
    
    # Рекомендации
    $report += "## Рекомендации`n`n"
    
    if ($failedChecks -gt 0) {
        $report += "- Исправьте обнаруженные ошибки`n"
        $report += "- Запустите проверку повторно с флагом `-Fix` для автоматического исправления проблем`n"
    }
    else {
        $report += "- Все проверки успешны, код соответствует стандартам качества`n"
    }
    
    # Сохраняем отчет
    $report | Out-File -FilePath $reportPath -Encoding utf8
    
    Write-Log "Итоговый отчет сохранен в $reportPath" -Color Green
    
    return $reportPath
}

# Активируем виртуальное окружение
Start-VirtualEnv

# Проверяем наличие инструментов
Test-Tools

# Лог-файл для отчетов
$logDateTime = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs\check_code_$logDateTime.log"
"Запуск проверок кода $logDateTime" | Out-File -FilePath $logFile

# Функция для записи в файл лога и на консоль
function Write-Log {
    param (
        [string]$Message,
        [ConsoleColor]$Color = "White"
    )

    Write-Host $Message -ForegroundColor $Color
    $Message | Out-File -FilePath $logFile -Append
}

# Функция для запуска инструмента и проверки результата
function Invoke-Tool {
    param (
        [string]$Name,
        [string]$Command,
        [string]$Arguments,
        [bool]$ContinueOnError = $true
    )

    Write-Log "Запуск $Name..." -Color Cyan
    Write-Log "Выполнение: $Command $Arguments" -Color Gray

    try {
        if ($EnableCache) {
            # Формируем ключ для кэша
            $cacheKey = "$Name|$Command|$Arguments"
            
            # Проверяем кэш
            if ($cache.ContainsKey($cacheKey)) {
                $lastRunTime = [DateTime]$cache[$cacheKey].timestamp
                $currentTime = Get-Date
                $fileChanged = $false
                
                # Проверяем, изменились ли файлы с момента последнего запуска
                if ($ChangedOnly) {
                    $changedFiles = & git diff --name-only HEAD~1 | Where-Object { $_ -match '\.py$' }
                    $fileChanged = $changedFiles.Count -gt 0
                }
                
                # Если не прошло более 1 часа и файлы не изменились
                if (($currentTime - $lastRunTime).TotalHours -lt 1 -and -not $fileChanged) {
                    Write-Log "Используем кэшированный результат для $Name" -Color Yellow
                    $exitCode = $cache[$cacheKey].exitCode
                    $output = $cache[$cacheKey].output
                    
                    $output | Out-File -FilePath $logFile -Append
                    
                    if ($exitCode -eq 0) {
                        Write-Log "${Name}: Успешно (из кэша)" -Color Green
                        return $true
                    }
                    else {
                        Write-Log "${Name}: Обнаружены проблемы (код выхода $exitCode) (из кэша)" -Color Red
                        if (-not $ContinueOnError) {
                            exit $exitCode
                        }
                        return $false
                    }
                }
            }
        }
        
        $output = Invoke-Expression "$Command $Arguments 2>&1"
        $exitCode = $LASTEXITCODE
        
        # Сохраняем в кэш
        if ($EnableCache) {
            $cacheKey = "$Name|$Command|$Arguments"
            $cache[$cacheKey] = @{
                timestamp = Get-Date -Format "o"
                exitCode  = $exitCode
                output    = $output
            }
        }
        
        $output | Out-File -FilePath $logFile -Append
        
        if ($exitCode -eq 0) {
            Write-Log "${Name}: Успешно" -Color Green
            return $true
        }
        else {
            Write-Log "${Name}: Обнаружены проблемы (код выхода $exitCode)" -Color Red
            Write-Log "Вывод ошибки:" -Color Yellow
            Write-Log "$output" -Color Yellow
            Write-Log "Рекомендации по исправлению:" -Color Magenta
            Write-Log "- Проверьте синтаксис и форматирование кода." -Color Magenta
            Write-Log "- Убедитесь, что все зависимости установлены." -Color Magenta
            Write-Log "- Ознакомьтесь с документацией инструмента $Name." -Color Magenta

            if (-not $ContinueOnError) {
                exit $exitCode
            }
            return $false
        }
    }
    catch {
        Write-Log "Ошибка при выполнении $Name : $($_)" -Color Red
        return $false
    }
}

# Проверка и установка отсутствующих импортов
if ($CheckImports) {
    Write-Log "=== Проверка импортов и зависимостей ===" -Color Magenta

    # Находим неиспользуемые импорты
    Write-Log "Анализ неиспользуемых импортов..." -Color Cyan

    # Запускаем check_imports.py для анализа неиспользуемых импортов
    $null = Invoke-Tool -Name "check_imports.py" -Command "python" -Arguments "check_imports.py --output=unused_imports.txt"

    # Проверяем зависимости с возможностью автоматической установки
    Write-Log "Проверка зависимостей проекта..." -Color Cyan

    $depsArgs = "check_dependencies.py"
    if ($InstallMissing) {
        $depsArgs += " --auto-install"
    }

    Invoke-Tool -Name "check_dependencies.py" -Command "python" -Arguments $depsArgs

    # Если указан флаг Fix, удаляем неиспользуемые импорты
    if ($Fix) {
        Write-Log "Удаление неиспользуемых импортов с помощью autoflake..." -Color Cyan
        Invoke-Tool -Name "autoflake" -Command "python -m autoflake" -Arguments "--in-place --remove-all-unused-imports --remove-unused-variables --recursive ."
        Write-Log "Неиспользуемые импорты удалены" -Color Green
    }
}

# Проверки стиля кода
if ($StyleChecks) {
    Write-Log "=== Проверки стиля кода ===" -Color Magenta

    # Если указан флаг Fix, исправляем стиль кода
    if ($Fix) {
        # Исправляем стиль кода с помощью black, isort и autoflake
        Invoke-Tool -Name "Black" -Command "python -m black" -Arguments "."
        Invoke-Tool -Name "isort" -Command "python -m isort" -Arguments "."
        Invoke-Tool -Name "autoflake" -Command "python -m autoflake" -Arguments "--in-place --remove-all-unused-imports --remove-unused-variables --recursive ."
    }

    # Запуск flake8 после исправлений
    Invoke-Tool -Name "flake8" -Command "python -m flake8" -Arguments ". --count --select=E9,F63,F7,F82 --show-source --statistics"

    # Дополнительные проверки
    Invoke-Tool -Name "flake8 (полный)" -Command "python -m flake8" -Arguments ". --count --max-complexity=10 --max-line-length=100 --statistics > flake8_report.txt"
}

# Статический анализ кода
if ($StaticAnalysis) {
    Write-Log "=== Статический анализ кода ===" -Color Magenta

    # Pylint - статический анализатор кода
    Invoke-Tool -Name "pylint" -Command "python -m pylint" -Arguments "--recursive=y --output=pylint_report.txt ."

    # mypy - проверка аннотаций типов
    Invoke-Tool -Name "mypy" -Command "python -m mypy" -Arguments "--ignore-missing-imports ."

    # bandit - проверка безопасности
    Invoke-Tool -Name "bandit" -Command "python -m bandit" -Arguments "-r ."
}

# Тесты
if ($Tests) {
    Write-Log "=== Запуск тестов ===" -Color Magenta

    if ($Coverage) {
        # Запуск тестов с измерением покрытия
        $testArgs = "--cov=. --cov-report=term"

        if ($GenerateHTML) {
            $testArgs += " --cov-report=html"
        }

        Invoke-Tool -Name "pytest с покрытием" -Command "python -m pytest" -Arguments "tests/ $testArgs -v"
    }
    else {
        # Обычный запуск тестов
        Invoke-Tool -Name "pytest" -Command "python -m pytest" -Arguments "tests/ -v"
    }
}

# Проверка распространенных ошибок в коде
if ($CommonErrors) {
    Write-Log "=== Проверка распространенных ошибок в коде ===" -Color Magenta

    # Запускаем check_common_errors.py для анализа распространенных ошибок
    $commonErrorsArgs = "check_common_errors.py"
    if ($Fix) {
        $commonErrorsArgs += " --output=common_errors_report.txt"
    }

    Invoke-Tool -Name "check_common_errors.py" -Command "python" -Arguments $commonErrorsArgs

    Write-Log "Проверка распространенных ошибок завершена" -Color Cyan
}

# Проверка на расширенные типы ошибок
if ($AdvancedErrors) {
    Write-Log "=== Проверка расширенных типов ошибок в коде ===" -Color Magenta

    # Запускаем check_errors.py для анализа расширенных типов ошибок
    Invoke-Tool -Name "check_errors.py" -Command "python" -Arguments "check_errors.py"

    Write-Log "Проверка расширенных типов ошибок завершена" -Color Cyan
}

# Автоматическое исправление ошибок в коде
if (($CommonErrors -or $AdvancedErrors) -and $Fix) {
    Write-Log "=== Исправление ошибок в коде ===" -Color Magenta

    # Запускаем fix_remaining_issues.py для автоматического исправления распространенных ошибок
    $fixCommonErrorsArgs = "fix_remaining_issues.py --output=fix_common_errors_report.txt"
    Invoke-Tool -Name "fix_remaining_issues.py" -Command "python" -Arguments $fixCommonErrorsArgs

    # Запускаем fix_code_style.py с параметром --specific-issues для исправления расширенных типов ошибок
    $fixSpecificArgs = "fix_code_style.py --specific-issues"
    if ($AdvancedErrors) {
        $fixSpecificArgs += " --aggressive"
    }
    Invoke-Tool -Name "fix_code_style.py" -Command "python" -Arguments $fixSpecificArgs

    Write-Log "Исправление ошибок в коде завершено" -Color Cyan
}

# Собираем результаты всех проверок
$results = @{}

# Если включен параллельный режим, используем кэш для промежуточных результатов
if ($EnableCache) {
    # Сохраняем кэш для будущих запусков
    $cache | ConvertTo-Json | Out-File -FilePath $cacheFile -Encoding utf8
    Write-Log "Кэш сохранен в $cacheFile" -Color Green
}

# Создаем консолидированный отчет, если требуется
if ($GenerateHTML) {
    $reportPath = New-Report -Results $results -Title "Отчет о качестве кода DMarket Trading Bot"
    
    # Если требуется сравнение с предыдущим отчетом
    if ($Compare) {
        # Находим предыдущий отчет
        $previousReports = Get-ChildItem -Path "reports" -Filter "code_quality_report_*.md" | 
        Sort-Object LastWriteTime -Descending | 
        Select-Object -Skip 1 -First 1
        
        if ($previousReports) {
            $previousReport = $previousReports[0].FullName
            Compare-Results -CurrentReport $reportPath -PreviousReport $previousReport
        }
        else {
            Write-Log "Предыдущие отчеты не найдены для сравнения" -Color Yellow
        }
    }
}

Write-Log "Все проверки завершены. Подробные результаты в $logFile" -Color Cyan

# Деактивация виртуального окружения
if (Get-Command deactivate -ErrorAction SilentlyContinue) {
    deactivate
    Write-Host "Виртуальное окружение деактивировано" -ForegroundColor Cyan
}
