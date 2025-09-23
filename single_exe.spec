# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# データファイルのリスト（存在するものだけ）
data_files = []
for file in ['ui_manager.py', 'scraper_engine.py', 'chrome_driver_manager.py', 
             'prefecture_mapper.py', 'gurunavi_label_based_extractor.py',
             'gurunavi_multi_approach_extractor.py', 'phone_cleaner_simple.py']:
    if os.path.exists(file):
        data_files.append((file, '.'))

# config.jsonがある場合のみ追加
if os.path.exists('config.json'):
    data_files.append(('config.json', '.'))

a = Analysis(
    ['gurunavi_scraper_v3.py'],
    pathex=[],
    binaries=[],
    datas=data_files,
    hiddenimports=[
        'numpy',
        'numpy.core._multiarray_umath',
        'numpy.core._multiarray_tests',
        'numpy.random.common',
        'numpy.random.bounded_integers',
        'numpy.random.entropy',
        'pandas',
        'pandas._libs',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.nattype',
        'pandas._libs.tslibs.timedeltas',
        'pandas._libs.skiplist',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.styles.stylesheet',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.common.exceptions',
        'requests',
        'urllib3',
        'certifi',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        '_tkinter',
        'psutil'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'PIL'],
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
    name='Beyond_Gurunavi_Scraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
    icon='icon.ico' if os.path.exists('icon.ico') else None
)
