@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 echo Instala Python 3.11 o superior desde https://www.python.org/downloads/windows/
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Acceso: demo@cindylu.local
echo Clave: CindyLu-Demo-2026
.venv\Scripts\python.exe demo.py
pause
exit /b
:error
echo No se pudo iniciar la demostracion.
pause
