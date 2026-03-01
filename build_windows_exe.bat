@echo off
setlocal

set "APP_NAME=Valorador de Opciones"
set "SPEC_FILE=%APP_NAME%.spec"

python --version >nul 2>&1
if errorlevel 1 (
  echo Error: Python no esta disponible en PATH.
  exit /b 1
)

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
  echo Falta PyInstaller en este entorno.
  echo Instalalo con:
  echo   python -m pip install -r requirements.txt pyinstaller
  exit /b 1
)

if not exist "%SPEC_FILE%" (
  echo Error: no existe %SPEC_FILE%.
  exit /b 1
)

echo Generando %APP_NAME%.exe...
python -m PyInstaller --clean --noconfirm "%SPEC_FILE%"
if errorlevel 1 exit /b 1

echo Ejecutable generado en:
echo   dist\%APP_NAME%\%APP_NAME%.exe
