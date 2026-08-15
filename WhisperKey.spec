# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:/Users/Usuario/Documents/WhisperKey/assets/icons', 'assets/icons'), ('C:/Users/Usuario/Documents/WhisperKey/assets/logo.png', 'assets'), ('C:/Users/Usuario/Documents/WhisperKey/build/engine-cpu/Release', 'assets/bin')]
binaries = []
hiddenimports = ['whisperkey.platform.windows', 'whisperkey.platform.linux', 'whisperkey.platform.macos', 'whisperkey.engine', 'whisperkey.splash', 'whisperkey.settings_gui', 'whisperkey.onboarding', 'whisperkey.updater']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:/Users/Usuario/Documents/WhisperKey/whisperkey/__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests', 'docs', 'notebooks', 'IPython', 'matplotlib', 'pytest', 'torch', 'torchaudio', 'torchvision', 'onnxruntime', 'ctranslate2', 'faster_whisper', 'transformers'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WhisperKey',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/Usuario/Documents/WhisperKey/assets/icons/app.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WhisperKey',
)
