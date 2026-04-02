@echo off
echo.
echo  Iniciando WASDE Monthly Report...
echo.

:: Tenta Anaconda em locais comuns primeiro (mais confiavel que "where python")
if exist "C:\ProgramData\anaconda3\python.exe" (
    "C:\ProgramData\anaconda3\python.exe" "%~dp0run.py"
    goto :end
)
if exist "%USERPROFILE%\anaconda3\python.exe" (
    "%USERPROFILE%\anaconda3\python.exe" "%~dp0run.py"
    goto :end
)
if exist "%USERPROFILE%\miniconda3\python.exe" (
    "%USERPROFILE%\miniconda3\python.exe" "%~dp0run.py"
    goto :end
)

:: Fallback: tenta "python" do PATH
python --version >nul 2>nul
if %errorlevel% equ 0 (
    python "%~dp0run.py"
    goto :end
)

echo.
echo  ERRO: Python nao encontrado!
echo  Instale Python 3.11+ em https://www.python.org/downloads/
echo  Ou instale Anaconda em https://www.anaconda.com/download
echo.

:end
pause
