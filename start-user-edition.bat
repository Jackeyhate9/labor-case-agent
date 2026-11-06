@echo off
setlocal

set "APP_EDITION=distribution"
set "APP_CONFIGURATION_MODE=user"
set "LABOR_CASE_AGENT_HOME=%LOCALAPPDATA%\LaborCaseAgent"

set "MODEL_ROOT="
set "MODEL_RUNTIME_ROOT="
set "LLM_PROVIDER="
set "LLM_BASE_URL="
set "LLM_MODEL="
set "OLLAMA_OCR_BASE_URL="
set "OLLAMA_OCR_MODEL="
set "OCR_PROVIDER="
set "MOSS_PYTHON="
set "MOSS_MODEL_PATH="
set "AUDIO_PROVIDER="
set "EMBEDDING_PYTHON="
set "BGE_M3_MODEL_PATH="
set "NEMOTRON_EMBED_MODEL_PATH="
set "EMBEDDING_PROVIDER="

call "%~dp0start-labor-case-agent.bat" %*
