$ErrorActionPreference = "Stop"

$appName = "Valorador de Opciones"
$specFile = "$appName.spec"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python no esta disponible en PATH."
}

try {
    python -c "import PyInstaller" | Out-Null
} catch {
    throw "Falta PyInstaller. Instala dependencias con: python -m pip install -r requirements.txt pyinstaller"
}

if (-not (Test-Path $specFile)) {
    throw "No existe $specFile."
}

Write-Host "Generando $appName.exe..."
python -m PyInstaller --clean --noconfirm $specFile

Write-Host "Ejecutable generado en:"
Write-Host "  dist\$appName\$appName.exe"
