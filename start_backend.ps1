# CraftAI — Script de démarrage backend (PowerShell)
# Usage : depuis la racine du projet -> .\start_backend.ps1
#         ou depuis n'importe où     -> & "C:\...\start_backend.ps1"
#
# Les variables LLM (OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL) sont
# chargées depuis .env par backend/env_bootstrap.py au démarrage -- ne pas les
# fixer ici en dur, sinon elles écrasent silencieusement .env (override=False
# ne s'applique qu'aux vars DEJA presentes dans l'environnement).

$env:DATABASE_URL     = "sqlite:///./createflow.db"

# Se positionner dans le dossier backend/ (relatif à ce script)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $scriptDir "backend")

# Le .venv du projet peut avoir ete cree sur une autre machine (pyvenv.cfg
# pointe alors vers un python.exe introuvable ici, et son uvicorn.exe echoue
# silencieusement). On verifie que le python du .venv repond reellement ;
# sinon on utilise un python systeme avec le site-packages du .venv en
# PYTHONPATH, qui donne acces aux memes paquets installes.
$venvPython = Join-Path $scriptDir "backend\.venv\Scripts\python.exe"
$venvSitePackages = Join-Path $scriptDir "backend\.venv\Lib\site-packages"
$venvWorks = $false
if (Test-Path $venvPython) {
    & $venvPython -c "" 2>$null
    if ($LASTEXITCODE -eq 0) { $venvWorks = $true }
}

if ($venvWorks) {
    & $venvPython -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
} else {
    $systemPython = Get-Command python -ErrorAction SilentlyContinue
    if (-not $systemPython) {
        foreach ($candidate in @("C:\Python313\python.exe", "C:\Python312\python.exe")) {
            if (Test-Path $candidate) { $systemPython = $candidate; break }
        }
    } else {
        $systemPython = $systemPython.Source
    }
    if (-not $systemPython) {
        Write-Host "Aucun interpreteur Python utilisable trouve (ni .venv, ni PATH)." -ForegroundColor Red
        exit 1
    }
    Write-Host "Backend : .venv/python.exe indisponible, repli sur $systemPython + site-packages du .venv" -ForegroundColor Yellow
    $env:PYTHONPATH = $venvSitePackages
    & $systemPython -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}
