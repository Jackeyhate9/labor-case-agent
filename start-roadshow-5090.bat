@echo off
setlocal

set "REPO_ROOT=%~dp0"
set "APP_EDITION=roadshow"
set "APP_CONFIGURATION_MODE=environment"
set "LABOR_CASE_AGENT_HOME=%LOCALAPPDATA%\LaborCaseAgent-Roadshow"

set "MODEL_ROOT=%REPO_ROOT%dist\models"
set "MODEL_RUNTIME_ROOT=%REPO_ROOT%dist\runtimes"

set "LLM_PROVIDER=ollama"
set "LLM_BASE_URL=http://127.0.0.1:11434/v1"
set "LLM_MODEL=qwen3.6-fable5MTP:latest"
set "OLLAMA_OCR_BASE_URL=http://127.0.0.1:11434"
set "OLLAMA_OCR_MODEL=unlimitedocrlocal:latest"
set "OCR_PROVIDER=ollama-ocr"

set "MOSS_PYTHON=%REPO_ROOT%.venv-moss\Scripts\python.exe"
set "MOSS_MODEL_PATH=%REPO_ROOT%dist\models\MOSS-Transcribe-Diarize"
set "AUDIO_PROVIDER=moss-transcribe-diarize"

set "EMBEDDING_PYTHON=%REPO_ROOT%.venv-moss\Scripts\python.exe"
set "BGE_M3_MODEL_PATH=%REPO_ROOT%dist\models\bge-m3"
set "NEMOTRON_EMBED_MODEL_PATH=%REPO_ROOT%dist\models\Nemotron-3-Embed-1B-BF16"
set "EMBEDDING_PROVIDER=bge-m3"

where ollama.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Ollama was not found. Install or start Ollama before the roadshow.
  pause
  exit /b 1
)

if not exist "%MODEL_ROOT%\bge-m3\pytorch_model.bin" (
  echo [ERROR] The roadshow model collection is incomplete:
  echo         %MODEL_ROOT%
  pause
  exit /b 1
)

if not exist "%MOSS_PYTHON%" (
  echo [ERROR] The roadshow Python runtime is missing:
  echo         %MOSS_PYTHON%
  pause
  exit /b 1
)

if /I "%~1"=="--check" (
  echo EDITION_OK=roadshow
  echo OLLAMA_OK=http://127.0.0.1:11434
  echo MODEL_ROOT_OK=%MODEL_ROOT%
  echo MOSS_RUNTIME_OK=%MOSS_PYTHON%
  echo DATA_ROOT_OK=%LABOR_CASE_AGENT_HOME%
  call "%REPO_ROOT%start-labor-case-agent.bat" --check
  exit /b %ERRORLEVEL%
)

call "%REPO_ROOT%start-labor-case-agent.bat" %*
