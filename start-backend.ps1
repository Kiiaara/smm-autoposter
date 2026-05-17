Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path ".venv")) {
    Write-Host "Создаю виртуальное окружение..."
    python -m venv .venv
}
& ".venv\Scripts\Activate.ps1"
pip install -r requirements.txt --quiet
uvicorn main:app --reload --port 8000
