param(
    [switch]$UseDocker
)

<#
A small helper to run the SwarmAgents stack locally for development on Windows PowerShell.

Usage:
  # Use docker-compose (if you prefer containers)
  .\scripts\run_local.ps1 -UseDocker

  # Run API and worker as background PowerShell jobs (requires Python and Redis available)
  .\scripts\run_local.ps1

Notes:
- The script starts the API (uvicorn) and the worker as background jobs. Use Get-Job / Receive-Job / Stop-Job to inspect and stop them.
- Ensure you have Python and the required packages installed in your active environment, or run inside the project's virtualenv.
- If you don't have Redis on localhost, prefer -UseDocker to start the compose stack which includes Redis.
#>

if ($UseDocker) {
    Write-Host "Starting docker-compose stack (Redis + API + worker)..."
    # Run docker-compose in the project root
    Push-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) -Force
    docker-compose up --build
    Pop-Location
    return
}

# Ensure Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python executable not found on PATH. Activate your venv or install Python before running this script."
    return
}

# Optional: check redis availability
$redisHost = $env:REDIS_HOST -or 'localhost'
$redisPort = $env:REDIS_PORT -or 6379
try {
    $socket = New-Object System.Net.Sockets.TcpClient
    $socket.Connect($redisHost, [int]$redisPort)
    $socket.Close()
    Write-Host ("Redis appears reachable at {0}:{1}" -f $redisHost, $redisPort)
}
catch {
    Write-Warning ("Redis not reachable at {0}:{1}. Consider running Redis (docker-compose) or set REDIS_HOST to a reachable instance." -f $redisHost, $redisPort)
}

# Start the API as a background job
Write-Host "Starting API (uvicorn) as a background job..."
$apiJobId = (Start-Job -Name SwarmAPI -ScriptBlock {
        python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    }).Id
Start-Sleep -Seconds 1

# Start the worker as a background job
Write-Host "Starting worker as a background job..."
$workerJobId = (Start-Job -Name SwarmWorker -ScriptBlock {
        python worker/worker.py
    }).Id

Write-Host "Started jobs:"
Get-Job -Name SwarmAPI, SwarmWorker | Format-Table Id, Name, State, HasMoreData -AutoSize

# Print started job ids to make use of the variables and help with later inspection
Write-Host ("API job id: {0}" -f $apiJobId)
Write-Host ("Worker job id: {0}" -f $workerJobId)

Write-Host "To follow logs: Receive-Job -Id <Id> -Keep" -ForegroundColor Yellow
Write-Host "To stop jobs: Stop-Job -Id <Id> ; Remove-Job -Id <Id>" -ForegroundColor Yellow
Write-Host "To view job output (once finished): Receive-Job -Id <Id>" -ForegroundColor Yellow

return