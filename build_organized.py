"""
Beyond Gurunavi Scraper - 整理された配布パッケージビルドスクリプト
ChromeDriver同梱版（アクセス権限エラー対応）
"""

import os
import sys
import shutil
import subprocess
import zipfile
import time
import stat
from pathlib import Path
from datetime import datetime

def force_remove_readonly(func, path, excinfo):
    """読み取り専用ファイルを強制削除するためのコールバック"""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"  ⚠️ ファイル削除エラー: {path} - {e}")

def safe_remove_directory(path):
    """ディレクトリを安全に削除（複数試行）"""
    if not os.path.exists(path):
        return True
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # 読み取り専用属性を解除
            for root, dirs, files in os.walk(path):
                for dir in dirs:
                    os.chmod(os.path.join(root, dir), stat.S_IWUSR)
                for file in files:
                    filepath = os.path.join(root, file)
                    os.chmod(filepath, stat.S_IWUSR)
            
            # 削除試行
            shutil.rmtree(path, onerror=force_remove_readonly)
            return True
            
        except PermissionError as e:
            if attempt < max_attempts - 1:
                print(f"  ⚠️ 削除試行 {attempt + 1}/{max_attempts} 失敗: {e}")
                print(f"     再試行まで3秒待機...")
                time.sleep(3)
                
                # ChromeDriverプロセスを強制終了
                try:
                    subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], 
                                 capture_output=True, text=True)
                except:
                    pass
            else:
                print(f"  ❌ ディレクトリ削除失敗: {path}")
                return False
        except Exception as e:
            print(f"  ❌ 予期しないエラー: {e}")
            return False
    
    return False

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
'''
    
    with open('single_exe.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("  ✓ single_exe.spec を作成しました")

def clean_previous_builds():
    """以前のビルドを削除"""
    print("\n🧹 以前のビルドをクリーンアップ中...")
    
    # ChromeDriverプロセスを事前に終了
    try:
        result = subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✓ ChromeDriverプロセスを終了しました")
            time.sleep(2)  # プロセス終了を待つ
    except:
        pass
    
    dirs_to_remove = ['build', 'dist', '__pycache__', 'Beyond_Gurunavi_Scraper']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            print(f"  削除中: {dir_name}")
            if safe_remove_directory(dir_name):
                print(f"  ✓ {dir_name} を削除")
            else:
                print(f"  ⚠️ {dir_name} の削除に失敗しました（続行）")

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

def safe_copy_file(src, dst):
    """ファイルを安全にコピー"""
    try:
        # 宛先が存在する場合、権限を変更してから削除
        if os.path.exists(dst):
            os.chmod(dst, stat.S_IWRITE)
            os.remove(dst)
        
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"    ⚠️ ファイルコピーエラー: {src} → {dst}: {e}")
        return False

def create_organized_distribution():
    """整理された配布パッケージを作成"""
    print("\n📦 整理された配布フォルダを作成中...")
    
    # メインフォルダ作成（既存フォルダの安全な削除）
    main_folder = Path('Beyond_Gurunavi_Scraper')
    if main_folder.exists():
        print("  既存のフォルダを削除中...")
        if not safe_remove_directory(main_folder):
            # 削除できない場合は別名で作成
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            main_folder = Path(f'Beyond_Gurunavi_Scraper_{timestamp}')
            print(f"  ⚠️ 別名で作成: {main_folder}")
    
    main_folder.mkdir()
    
    # ==============================================
    # 1. メインアプリケーション（最上位に配置）
    # ==============================================
    
    # EXEファイルを最上位にコピー
    exe_path = Path('dist') / 'Beyond_Gurunavi_Scraper.exe'
    if exe_path.exists():
        if safe_copy_file(exe_path, main_folder / 'Beyond_Gurunavi_Scraper.exe'):
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
    
    try:
        with open(system_folder / 'config.json', 'w', encoding='utf-8') as f:
            f.write(config_content)
        print("  ✓ config.json を_systemフォルダに作成")
        
        # config.jsonを最上位にもコピー（互換性のため）
        safe_copy_file(system_folder / 'config.json', main_folder / 'config.json')
    except Exception as e:
        print(f"  ⚠️ config.json作成エラー: {e}")
    
    # ChromeDriverをコピー（存在する場合）
    drivers_folder = system_folder / 'drivers'
    drivers_folder.mkdir()
    
    chromedriver_path = Path('drivers') / 'chromedriver.exe'
    if chromedriver_path.exists():
        if safe_copy_file(chromedriver_path, drivers_folder / 'chromedriver.exe'):
            print("  ✓ 既存のChromeDriverをコピー")
    else:
        print("  ⚠️ ChromeDriverは初回起動時に自動ダウンロードされます")
    
    # driversフォルダを最上位にもコピー（互換性のため）
    try:
        top_drivers = main_folder / 'drivers'
        top_drivers.mkdir()
        if (drivers_folder / 'chromedriver.exe').exists():
            safe_copy_file(drivers_folder / 'chromedriver.exe', top_drivers / 'chromedriver.exe')
    except Exception as e:
        print(f"  ⚠️ driversフォルダ作成エラー: {e}")
    
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
    
    # ログクリアツール
    log_clear = """@echo off
echo ログファイルをクリアします...
del /Q "..\\_system\\logs\\*.log" 2>nul
del /Q "..\\logs\\*.log" 2>nul
echo.
echo ログファイルをクリアしました
echo.
pause
"""
    try:
        with open(tools_folder / 'ログクリア.bat', 'w', encoding='shift-jis') as f:
            f.write(log_clear)
    except:
        # shift-jisでエラーが出る場合はutf-8で試す
        with open(tools_folder / 'ログクリア.bat', 'w', encoding='utf-8') as f:
            f.write(log_clear)
    
    # 出力フォルダを開く
    open_output = """@echo off
explorer "..\\output"
"""
    try:
        with open(tools_folder / '出力フォルダを開く.bat', 'w', encoding='shift-jis') as f:
            f.write(open_output)
    except:
        with open(tools_folder / '出力フォルダを開く.bat', 'w', encoding='utf-8') as f:
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
   • エリアを選択（任意）
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


【 トラブルシューティング 】
────────────────────────────────────────────────────────
エラーが発生した場合の対処法：

1. 「アクセスが拒否されました」エラー
   → アンチウイルスソフトを一時的に無効化
   → 管理者権限で実行

2. ChromeDriverエラー
   → Google Chromeを最新版に更新
   → PCを再起動してから実行

3. 起動しない場合
   → Windows Defenderの除外設定に追加
   → .NET Framework 4.8以降をインストール


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
    
    # フォルダ名を探す（タイムスタンプ付きの可能性も考慮）
    folder_name = 'Beyond_Gurunavi_Scraper'
    if not os.path.exists(folder_name):
        # タイムスタンプ付きのフォルダを探す
        folders = [f for f in os.listdir('.') if f.startswith('Beyond_Gurunavi_Scraper')]
        if folders:
            folder_name = folders[0]
        else:
            print("  ❌ 配布フォルダが見つかりません")
            return None
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_name = f'Beyond_Gurunavi_Scraper_{timestamp}.zip'
    
    try:
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(folder_name):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, '.')
                    zf.write(file_path, arc_name)
        
        size_mb = os.path.getsize(zip_name) / 1024 / 1024
        print(f"  ✓ {zip_name} を作成（{size_mb:.1f} MB）")
        
        return zip_name
    except Exception as e:
        print(f"  ❌ ZIP作成エラー: {e}")
        return None

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
        
        if dist_folder:
            print(f"\n📁 配布フォルダ: {dist_folder}/")
        if zip_file:
            print(f"📦 配布ZIP: {zip_file}")
        
        print("\n特徴:")
        print("  • EXEファイルが目立つように配置")
        print("  • システムファイルは_systemフォルダに整理")
        print("  • ChromeDriver同梱済み（可能な場合）")
        print("  • わかりやすい説明書付き")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
    input("\nEnterキーで終了...")