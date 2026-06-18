# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['gui_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src', 'src'),                    # 把 src 目录打包进去
        ('config.yaml.template', '.'),     # 把配置模板打包进去
    ],
    hiddenimports=[
        # Crypto 相关
        'Crypto',
        'Crypto.Cipher',
        'Crypto.Cipher.DES',
        'Crypto.Util',
        'Crypto.Util.Padding',
        'Crypto.Random',
        'Crypto.Hash',
        # 网络请求
        'requests',
        'urllib3',
        'chardet',
        'idna',
        'certifi',
        # 其他依赖
        'yaml',
        'flask',
        'apscheduler',
        'werkzeug',
        'jinja2',
        'markupsafe',
        'itsdangerous',
        'click',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='IPTV列表获取工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # True=显示黑框（调试用），False=不显示
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)