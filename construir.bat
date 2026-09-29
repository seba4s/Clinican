@echo off
rem ======================================================================
rem  CLINICAN - Compila el programa (seccion 10 de la especificacion)
rem
rem  Doble clic sobre este archivo. Hace tres cosas:
rem    1. Crea el entorno .venv e instala requirements.txt
rem       (solo la primera vez necesita internet).
rem    2. Corre las pruebas y compila dist\CLINICAN\CLINICAN.exe con PyInstaller.
rem    3. Crea el acceso directo "CLINICAN" en el escritorio.
rem
rem  La base de datos vive en C:\Clinican\datos y los respaldos en
rem  C:\Clinican\respaldos: recompilar NO los borra.
rem ======================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === CLINICAN: preparando la compilacion ===
echo.

rem ---------------------------------------------------------------- Python
if not exist ".venv\Scripts\python.exe" (
    echo Creando el entorno .venv ...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 goto sin_python
)
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" goto sin_python

echo Instalando o revisando las librerias (requirements.txt) ...
"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto error_pip

rem ---------------------------------------------------------------- Pruebas
echo.
echo Corriendo las pruebas automaticas ...
"%PY%" -m pytest -q
if errorlevel 1 goto error_pruebas

rem ---------------------------------------------------------------- PyInstaller
rem PIL._tkinter_finder: Pillow lo carga por nombre para mostrar el logo; sin el, el .exe no abre.
echo.
echo Compilando CLINICAN.exe (tarda uno o dos minutos) ...
"%PY%" -m PyInstaller --noconfirm --windowed --name CLINICAN --icon assets\clinican.ico ^
    --collect-all customtkinter --hidden-import PIL._tkinter_finder --add-data "assets;assets" main.py
if errorlevel 1 goto error_pyinstaller
if not exist "dist\CLINICAN\CLINICAN.exe" goto error_pyinstaller

rem ---------------------------------------------------------------- Acceso directo
echo.
echo Creando el acceso directo en el escritorio ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$escritorio = [Environment]::GetFolderPath('Desktop');" ^
    "$acceso = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $escritorio 'CLINICAN.lnk'));" ^
    "$acceso.TargetPath = (Resolve-Path 'dist\CLINICAN\CLINICAN.exe').Path;" ^
    "$acceso.WorkingDirectory = (Resolve-Path 'dist\CLINICAN').Path;" ^
    "$acceso.IconLocation = (Resolve-Path 'assets\clinican.ico').Path;" ^
    "$acceso.Description = 'CLINICAN - Peluqueria canina';" ^
    "$acceso.Save()"
if errorlevel 1 (
    echo No se pudo crear el acceso directo. Puede abrir el programa desde dist\CLINICAN\CLINICAN.exe
)

echo.
echo === Listo ===
echo Programa:       %CD%\dist\CLINICAN\CLINICAN.exe
echo Base de datos:  %CD%\datos\clinican.db
echo Respaldos:      %CD%\respaldos\
echo En el escritorio quedo el acceso directo "CLINICAN".
echo.
pause
exit /b 0

:sin_python
echo.
echo ERROR: no se encontro Python 3.11 o superior.
echo Instalelo desde python.org (marque "Add python.exe to PATH") y vuelva a intentar.
goto fin_error

:error_pip
echo.
echo ERROR: no se pudieron instalar las librerias.
echo La primera vez se necesita internet. Revise la conexion y vuelva a intentar.
goto fin_error

:error_pruebas
echo.
echo ERROR: alguna prueba automatica fallo. No se compilo el programa.
echo Revise el mensaje de arriba.
goto fin_error

:error_pyinstaller
echo.
echo ERROR: PyInstaller no pudo compilar el programa. Revise el mensaje de arriba.
goto fin_error

:fin_error
echo.
pause
exit /b 1
