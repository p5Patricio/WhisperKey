# -*- mode: python ; coding: utf-8 -*-

from whisperkey.version import __version__

block_cipher = None

a = Analysis(
    ['whisperkey/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('whisperkey/version.py', 'whisperkey'),
        ('assets/bin', 'assets/bin'),
        ('assets/icons', 'assets/icons'),
    ],
    hiddenimports=[
        'whisperkey.platform.windows',
        'whisperkey.platform.linux',
        'whisperkey.platform.macos',
        'whisperkey.splash',
        'whisperkey.settings_gui',
        'whisperkey.onboarding',
        'whisperkey.updater',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tests',
        'docs',
        'notebooks',
        'torch.testing',
        'torch.utils.benchmark',
        'torch.utils.tensorboard',
        'torch.utils.cpp_extension',
        'torch.utils.mobile_optimizer',
        'torch.utils.dlpack',
        'IPython',
        'matplotlib',
        'pytest',
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    icon='assets/icons/app.ico',
    version='whisperkey/version.py',
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
