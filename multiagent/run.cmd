@echo off
setlocal
set "HERE=%~dp0"

if not "%PYTHON%"=="" goto run

set "BUNDLED=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED%" (
  set "PYTHON=%BUNDLED%"
  goto run
)

python --version >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=python"
  goto run
)

py -3 --version >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=py -3"
  goto run
)

echo [ERROR] python not found. Set the PYTHON environment variable.
exit /b 1

:run
%PYTHON% "%HERE%orchestrator.py" %*
exit /b %errorlevel%
