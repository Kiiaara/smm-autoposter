Set-Location "$PSScriptRoot\frontend"
if (-not (Test-Path "node_modules")) {
    Write-Host "Устанавливаю зависимости..."
    npm install
}
npm run dev
