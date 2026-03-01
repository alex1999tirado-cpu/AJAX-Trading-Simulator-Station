from PyInstaller.utils.hooks import collect_data_files, collect_submodules


block_cipher = None

datas = []
datas += collect_data_files("matplotlib")
datas += collect_data_files("certifi")

hiddenimports = []
hiddenimports += collect_submodules("yfinance")
hiddenimports += [
    "tkinter",
    "tkinter.ttk",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends._backend_tk",
]


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Valorador de Opciones",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Valorador de Opciones",
)

app = BUNDLE(
    coll,
    name="Valorador de Opciones.app",
    icon=None,
    bundle_identifier="com.alextirado.valoradoropciones",
    info_plist={
        "CFBundleDisplayName": "Valorador de Opciones",
        "CFBundleName": "Valorador de Opciones",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
    },
)
