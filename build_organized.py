"""
Beyond Gurunavi Scraper - 整理された配布パッケージビルドスクリプト
ChromeDriver同梱版
"""

import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path
from datetime import datetime

def install_all_requirements():
    """必要なパッケージを完全インストール"""
    print("📦 必要なパッケージをインストール中...")
    
    packages = [
        'pyinstaller',
        'numpy',
        'pandas',
        'openpyxl',
        'selenium',
        'requests',
        'urllib3',
        'certifi',
        'psutil'
    ]
    
    for package in packages:
        print(f"  📥 {package} をインストール中...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', package])
            print(f"  ✓ {package} インストール完了")
        except:
            print(f"  ⚠️ {package} のインストールに失敗（既存の可能性）")

def create_single_exe_spec():
    """単一EXEファイル用のspecファイルを作成"""
    print("\n📝 単一EXE用specファイルを作成中...")
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['gurunavi_scraper_v3.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui_manager.py', '.'),
        ('scraper_engine.py', '.'),
        ('chrome_driver_manager.py', '.'),
        ('prefecture_mapper.py', '.'),
        ('gurunavi_label_based_extractor.py', '.'),
        ('gurunavi_multi_approach_extractor.py', '.'),
        ('phone_cleaner_simple.py', '.'),
        ('config.json', '.') if os.path.exists('config.json') else None
    ],
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

# データファイルのNoneを除去
a.datas = [x for x in a.datas if x is not None]

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
'''
    
    with open('single_exe.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("  ✓ single_exe.spec を作成しました")

def clean_previous_builds():
    """以前のビルドを削除"""
    print("\n🧹 以前のビルドをクリーンアップ中...")
    
    dirs_to_remove = ['build', 'dist', '__pycache__', 'Beyond_Gurunavi_Scraper']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"  ✓ {dir_name} を削除")
            except:
                print(f"  ⚠️ {dir_name} の削除失敗")

def build_single_exe():
    """単一EXEファイルをビルド"""
    print("\n🔨 単一EXEファイルをビルド中...")
    print("  （この処理には数分かかる場合があります）")
    
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', 'single_exe.spec'],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("  ✓ ビルド成功")
            return True
        else:
            print(f"  ❌ ビルドエラー: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"  ❌ ビルド失敗: {e}")
        return False

def create_organized_distribution():
    """整理された配布パッケージを作成"""
    print("\n📦 整理された配布フォルダを作成中...")
    
    # メインフォルダ作成
    main_folder = Path('Beyond_Gurunavi_Scraper')
    if main_folder.exists():
        shutil.rmtree(main_folder)
    main_folder.mkdir()
    
    # ==============================================
    # 1. メインアプリケーション（最上位に配置）
    # ==============================================
    
    # EXEファイルを最上位にコピー（シンプルな名前で）
    exe_path = Path('dist') / 'Beyond_Gurunavi_Scraper.exe'
    if exe_path.exists():
        shutil.copy2(exe_path, main_folder / 'Beyond_Gurunavi_Scraper.exe')
        print(f"  ✓ メインアプリをコピー（{exe_path.stat().st_size / 1024 / 1024:.1f} MB）")
    else:
        print("  ❌ EXEファイルが見つかりません")
        return None
    
    # ==============================================
    # 2. システムフォルダ（_systemフォルダ内に整理）
    # ==============================================
    
    system_folder = main_folder / '_system'
    system_folder.mkdir()
    
    # config.jsonを_systemに配置
    config_content = """{
  "cooltime_min": 2.0,
  "cooltime_max": 4.0,
  "ua_switch_interval": 15,
  "retry_delay": 5.0,
  "captcha_delay": 30.0,
  "ip_limit_delay": 60.0,
  "last_save_path": "output",
  "user_agents": [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0"
  ],
  "time_zone_aware": {
    "peak_hours": {"start": 12, "end": 13, "multiplier": 1.5},
    "evening_hours": {"start": 18, "end": 20, "multiplier": 1.3},
    "safe_hours": {"start": 23, "end": 6, "multiplier": 0.8}
  }
}"""
    
    with open(system_folder / 'config.json', 'w', encoding='utf-8') as f:
        f.write(config_content)
    print("  ✓ config.json を_systemフォルダに作成")
    
    # config.jsonを最上位にもコピー（互換性のため）
    shutil.copy2(system_folder / 'config.json', main_folder / 'config.json')
    
    # ChromeDriverをコピー（存在する場合）
    drivers_folder = system_folder / 'drivers'
    drivers_folder.mkdir()
    
    chromedriver_path = Path('drivers') / 'chromedriver.exe'
    if chromedriver_path.exists():
        shutil.copy2(chromedriver_path, drivers_folder / 'chromedriver.exe')
        print("  ✓ 既存のChromeDriverをコピー")
    else:
        print("  ⚠️ ChromeDriverは初回起動時に自動ダウンロードされます")
    
    # driversフォルダを最上位にもコピー（互換性のため）
    shutil.copytree(drivers_folder, main_folder / 'drivers', dirs_exist_ok=True)
    
    # ログフォルダ
    (system_folder / 'logs').mkdir()
    (main_folder / 'logs').mkdir()  # 互換性のため最上位にも作成
    
    # ==============================================
    # 3. 出力フォルダ（最上位に配置して見つけやすく）
    # ==============================================
    
    output_folder = main_folder / 'output'
    output_folder.mkdir()
    print("  ✓ outputフォルダを作成")
    
    # ==============================================
    # 4. 説明書（最上位に配置）
    # ==============================================
    
    create_user_friendly_readme(main_folder)
    
    # ==============================================
    # 5. ユーティリティ（_toolsフォルダ）
    # ==============================================
    
    tools_folder = main_folder / '_tools'
    tools_folder.mkdir()
    
    # ログクリアツール（shift_jis対応）
    log_clear = """@echo off
echo ログファイルをクリアします...
del /Q "..\_system\logs\*.log" 2>nul
del /Q "..\logs\*.log" 2>nul
echo.
echo ログファイルをクリアしました
echo.
pause
"""
    with open(tools_folder / 'ログクリア.bat', 'w', encoding='shift-jis') as f:
        f.write(log_clear)
    
    # 出力フォルダを開く
    open_output = """@echo off
explorer "..\output"
"""
    with open(tools_folder / '出力フォルダを開く.bat', 'w', encoding='shift-jis') as f:
        f.write(open_output)
    
    print("  ✓ ユーティリティバッチファイルを作成")
    
    print("  ✓ フォルダ構成を整理しました")
    
    return main_folder

def create_user_friendly_readme(main_folder):
    """ユーザーフレンドリーな説明書を作成"""
    readme_content = """============================================================
    Beyond Gurunavi Scraper v1.0
    ぐるなび店舗情報取得ツール
============================================================

【 起動方法 】
────────────────────────────────────────────────────────
  Beyond_Gurunavi_Scraper.exe をダブルクリック
────────────────────────────────────────────────────────


【 フォルダ構成 】
────────────────────────────────────────────────────────
Beyond_Gurunavi_Scraper/
│
├── Beyond_Gurunavi_Scraper.exe     ← これを実行
├── README.txt                       ← この説明書
├── output/                          ← 取得データの保存場所
│
├── config.json                      ← 設定ファイル
├── drivers/                         ← ChromeDriver格納
├── logs/                            ← ログファイル
│
├── _system/                         ← システムファイル
│   ├── config.json
│   ├── drivers/
│   │   └── chromedriver.exe
│   └── logs/
│
└── _tools/                          ← 便利ツール
    ├── ログクリア.bat
    └── 出力フォルダを開く.bat
────────────────────────────────────────────────────────


【 使い方 】
────────────────────────────────────────────────────────
1. アプリを起動
   「Beyond_Gurunavi_Scraper.exe」をダブルクリック

2. 検索条件を設定
   • 都道府県を選択
   • 市区町村を選択（任意）
   • 取得件数を設定（1～5000件）

3. データ取得開始
   「スクレイピング開始」ボタンをクリック

4. 完了を待つ
   処理が完了するまでお待ちください
   ※100件で約10～15分程度

5. データ確認
   「output」フォルダにExcelファイルが保存されます


【 必要な環境 】
────────────────────────────────────────────────────────
• Windows 10/11（64ビット）
• Google Chrome（最新版）
• インターネット接続
• 4GB以上のメモリ推奨


【 よくある質問 】
────────────────────────────────────────────────────────
Q: 起動時に警告が出る
A: Windows Defenderの警告は「詳細情報」→「実行」で進めてください

Q: ChromeDriverエラーが出る
A: 設定タブから「ChromeDriver修正」をクリック

Q: 処理が途中で止まる
A: アクセス制限の可能性があります。1時間ほど待って再実行

Q: データが保存されない
A: 「output」フォルダを確認してください

Q: 取得が遅い
A: 深夜（23:00～6:00）の実行が最も高速です


【 取得データの内容 】
────────────────────────────────────────────────────────
Excel形式（.xlsx）で以下の情報を保存：
  • URL（店舗ページのリンク）
  • 店舗名
  • 電話番号
  • 取得日時


【 注意事項 】
────────────────────────────────────────────────────────
• 大量データの取得は時間を分散して実行してください
• サーバーに過度な負荷をかけないよう配慮してください
• 取得したデータは適切に管理してください


【 サポート 】
────────────────────────────────────────────────────────
問題が発生した場合：
1. logs/ フォルダのログファイルを確認
2. Google Chromeを最新版に更新
3. PCを再起動して再実行


============================================================
                © 2024 Beyond Gurunavi Scraper
============================================================
"""
    
    with open(main_folder / 'README.txt', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print("  ✓ README.txt を作成")

def create_final_zip():
    """最終的なZIPファイルを作成"""
    print("\n🗜️ 配布用ZIPファイルを作成中...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_name = f'Beyond_Gurunavi_Scraper_{timestamp}.zip'
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk('Beyond_Gurunavi_Scraper'):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name = os.path.relpath(file_path, '.')
                zf.write(file_path, arc_name)
    
    size_mb = os.path.getsize(zip_name) / 1024 / 1024
    print(f"  ✓ {zip_name} を作成（{size_mb:.1f} MB）")
    
    return zip_name

def print_folder_structure():
    """フォルダ構造を表示"""
    print("\n📂 最終的なフォルダ構造:")
    print("""
Beyond_Gurunavi_Scraper/
│
├── Beyond_Gurunavi_Scraper.exe      ← メインアプリ
├── README.txt                        ← 説明書
├── output/                           ← データ保存フォルダ
│
├── config.json                       ← 設定（互換性用）
├── drivers/                          ← ChromeDriver（互換性用）
├── logs/                             ← ログ（互換性用）
│
├── _system/                          ← システムファイル
│   ├── config.json
│   ├── drivers/
│   │   └── chromedriver.exe
│   └── logs/
│
└── _tools/                           ← ユーティリティ
    ├── ログクリア.bat
    └── 出力フォルダを開く.bat
    """)

def main():
    """メイン処理"""
    print("=" * 60)
    print("  Beyond Gurunavi Scraper")
    print("  整理された配布パッケージ ビルド")
    print("=" * 60)
    
    try:
        # 1. パッケージインストール
        install_all_requirements()
        
        # 2. クリーンアップ
        clean_previous_builds()
        
        # 3. specファイル作成
        create_single_exe_spec()
        
        # 4. ビルド実行
        if not build_single_exe():
            print("\n❌ ビルドに失敗しました")
            return
        
        # 5. 整理された配布パッケージ作成
        dist_folder = create_organized_distribution()
        if not dist_folder:
            print("\n❌ パッケージ作成に失敗しました")
            return
        
        # 6. ZIP作成
        zip_file = create_final_zip()
        
        # 7. フォルダ構造を表示
        print_folder_structure()
        
        # 完了
        print("\n" + "=" * 60)
        print("✅ ビルド完了！")
        print("=" * 60)
        print(f"\n📁 配布フォルダ: Beyond_Gurunavi_Scraper/")
        print(f"📦 配布ZIP: {zip_file}")
        print("\n特徴:")
        print("  • EXEファイルが目立つように配置")
        print("  • システムファイルは_systemフォルダに整理")
        print("  • ChromeDriver同梱済み")
        print("  • わかりやすい説明書付き")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
    input("\nEnterキーで終了...")