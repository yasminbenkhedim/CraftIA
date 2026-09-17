# CraftAI — Script de démarrage Worker Celery (PowerShell)
# Prérequis : Redis doit tourner (C:\Users\ybenkhedim002\Redis-x64-5.0.14.1\redis-server.exe)
# Usage : depuis la racine du projet -> .\start_worker.ps1
#
# Les variables métier (PEXELS_API_KEY, OPENAI_API_KEY, OPENAI_BASE_URL,
# WAV2LIP_*, ...) sont chargées automatiquement depuis .env par
# backend/env_bootstrap.py au démarrage du worker -- ne pas les fixer ici en
# dur, sinon elles écrasent silencieusement .env (override=False ne s'applique
# qu'aux vars DEJA presentes dans l'environnement).
# On ne définit ici que l'infrastructure locale.

$env:REDIS_URL        = "redis://localhost:6379/0"
$env:DATABASE_URL     = "sqlite:///./backend/createflow.db"
$env:PYTHONPATH       = $PSScriptRoot

# Sélection de l'interpréteur : le .venv du projet en priorité (il contient
# torch/opencv/librosa nécessaires à Wav2Lip). Sinon, python du PATH en repli.
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    Write-Host "Worker : utilisation du .venv -> $venvPython" -ForegroundColor Green
    $python = $venvPython
} else {
    Write-Host "Worker : .venv introuvable, repli sur 'python' du PATH (Wav2Lip risque d'etre indisponible)" -ForegroundColor Yellow
    $python = "python"
}

& $python -m celery -A backend.celery_app worker --loglevel=info --concurrency=2
