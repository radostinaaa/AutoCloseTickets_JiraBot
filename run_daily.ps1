# PowerShell script to run the Jira Auto-Close Bot daily
# This script checks if today is a working day before running

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptPath "jira_auto_close.py"

# Log file in log folder
$logFolder = Join-Path $scriptPath "log"
if (-not (Test-Path $logFolder)) {
    New-Item -ItemType Directory -Path $logFolder | Out-Null
}
$logFile = Join-Path $logFolder "bot_log.txt"

# Function to write to log
function Write-Log {
    param($Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Message"
    Write-Host $logMessage
    Add-Content -Path $logFile -Value $logMessage
}

# Check if today is a working day (Monday-Friday)
$dayOfWeek = (Get-Date).DayOfWeek
if ($dayOfWeek -eq "Saturday" -or $dayOfWeek -eq "Sunday") {
    Write-Log "Today is $dayOfWeek - skipping bot execution"
    exit 0
}

Write-Log "Starting Jira Auto-Close Bot..."

# Run the Python script
try {
    python $pythonScript 2>&1 | Tee-Object -FilePath $logFile -Append
    Write-Log "Bot execution completed successfully"
} catch {
    Write-Log "ERROR: Bot execution failed - $_"
    exit 1
}
