#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Valorador de Opciones"
SPEC_FILE="${APP_NAME}.spec"
DIST_DIR="dist"
BUILD_DIR="build"
CREATE_DMG=0

if [[ "${1:-}" == "--dmg" ]]; then
  CREATE_DMG=1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 no esta disponible."
  exit 1
fi

if ! python3 -c "import PyInstaller" >/dev/null 2>&1; then
  echo "Falta PyInstaller en este entorno."
  echo "Instalalo con:"
  echo "  python3 -m pip install -r requirements.txt pyinstaller"
  exit 1
fi

if [[ ! -f "${SPEC_FILE}" ]]; then
  echo "Error: no existe ${SPEC_FILE}."
  exit 1
fi

echo "Generando ${APP_NAME}.app..."
python3 -m PyInstaller --clean --noconfirm "${SPEC_FILE}"

APP_PATH="${DIST_DIR}/${APP_NAME}.app"
if [[ ! -d "${APP_PATH}" ]]; then
  echo "Error: PyInstaller no genero ${APP_PATH}."
  exit 1
fi

echo "App generada en:"
echo "  ${APP_PATH}"

if [[ "${CREATE_DMG}" -eq 1 ]]; then
  DMG_PATH="${DIST_DIR}/${APP_NAME}.dmg"
  TMP_DMG="${BUILD_DIR}/${APP_NAME}-tmp.dmg"

  if ! command -v hdiutil >/dev/null 2>&1; then
    echo "Error: hdiutil no esta disponible. El .app ya esta listo, pero no se pudo crear el .dmg."
    exit 1
  fi

  rm -f "${DMG_PATH}" "${TMP_DMG}"
  hdiutil create -volname "${APP_NAME}" -srcfolder "${APP_PATH}" -ov -format UDZO "${DMG_PATH}"

  echo "DMG generado en:"
  echo "  ${DMG_PATH}"
fi
