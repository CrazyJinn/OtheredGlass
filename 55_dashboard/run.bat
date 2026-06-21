@echo off
REM Quick start 55_dashboard (Streamlit). Windows: double-click to run.
cd /d "%~dp0"

REM Use .venv if present, else system python
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

REM Dependency check: install requirements.txt if streamlit is missing
"%PY%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
  echo [setup] streamlit not found, installing requirements.txt ...
  "%PY%" -m pip install -r requirements.txt
)

if not exist ".env" (
  echo [warn] No .env found. See .env.example for Neo4j creds, or put settings.json in project root.
)

echo [run] Starting Streamlit at http://localhost:8501
"%PY%" -m streamlit run app.py --server.port 8501 --server.headless false
