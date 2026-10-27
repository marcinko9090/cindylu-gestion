@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 echo Instala Python 3.11 o superior desde https://www.python.org/downloads/windows/
 echo Activa la opcion Add Python to PATH durante la instalacion.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe app.py
pause
exit /b
:error
echo No se pudo preparar el programa. Revisa internet y la instalacion de Python.
pause
