@echo off
chcp 65001 >nul
title FireArt - Crear instalador
cd /d "%~dp0"
echo ==========================================
echo   FireArt - Creando el instalador
echo ==========================================

where python >nul 2>nul
if errorlevel 1 (
    echo Python no esta instalado. Intentando instalarlo con winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo Cierra esta ventana y vuelve a abrir Crear_Instalador.bat para continuar.
    pause
    exit /b 1
)

if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller || goto error

set QT_QPA_PLATFORM=offscreen
python tests\prueba_humo.py || goto error
set QT_QPA_PLATFORM=

pyinstaller --noconfirm --clean --windowed --name FireArt --collect-all imageio --collect-all imageio_ffmpeg main.py || goto error

set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "%ISCC%" (
    "%ISCC%" instalador.iss
    echo.
    echo Listo: salida\FireArt-Instalador.exe
) else (
    echo.
    echo Programa listo en dist\FireArt\FireArt.exe  (abre con doble clic^).
    echo Para crear el instalador, instala Inno Setup desde https://jrsoftware.org/isdl.php y repite.
)
pause
exit /b 0

:error
echo.
echo Hubo un error. Copia el mensaje de arriba para pedir ayuda.
pause
exit /b 1
