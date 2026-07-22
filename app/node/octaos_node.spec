# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['octaos_node.py'],
    pathex=['/Users/sayantande/OctaOsautomation'],
    binaries=[],
    datas=[
        ('/Users/sayantande/OctaOsautomation/app/models', 'app/models'),
        ('/Users/sayantande/OctaOsautomation/app/services', 'app/services'),
        ('/Users/sayantande/OctaOsautomation/app/core', 'app/core'),
    ],
    hiddenimports=[
        'sqlalchemy.ext.baked',
        'sqlite3',
        'json',
        'yaml',
        're',
        'asyncio',
        'httpx',
        'pydantic'
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='octaos-node-bin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
