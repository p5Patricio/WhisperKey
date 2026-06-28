# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Usuario\\Documents\\WhisperKey\\whisperkey\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('config.toml', '.')],
    hiddenimports=['whisperkey.platform.windows', 'whisperkey.platform.linux', 'whisperkey.platform.macos', 'whisperkey.splash', 'whisperkey.settings_gui', 'whisperkey.onboarding', 'whisperkey.updater'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests', 'docs', 'notebooks', 'torch.testing', 'torch.utils.benchmark', 'torch.utils.tensorboard', 'torch.utils.cpp_extension', 'torch.utils.mobile_optimizer', 'torch.utils.dlpack', 'IPython', 'matplotlib', 'pytest'],
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
    icon=['C:\\Users\\Usuario\\Documents\\WhisperKey\\assets\\icons\\app.ico'],
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
