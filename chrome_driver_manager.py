"""
ChromeDriver管理クラス
ChromeDriverのダウンロード、設定、初期化を管理
"""

import os
import subprocess
import shutil
import zipfile
import logging
from pathlib import Path
import requests
import json

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class ChromeDriverManager:
    """ChromeDriver管理クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.app_dir = Path.cwd()
        self.drivers_dir = self.app_dir / "drivers"
        self.drivers_dir.mkdir(exist_ok=True)
        self.chromedriver_path = self.drivers_dir / "chromedriver.exe"
        
        # Chrome for Testing API
        self.cft_api_url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
        
    def check_chrome_installed(self):
        """Chrome インストール確認"""
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                self.logger.info(f"Chrome検出: {path}")
                return True
        
        self.logger.error("Google Chromeがインストールされていません")
        return False
    
    def get_chrome_version(self):
        """Chrome バージョン取得"""
        try:
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
            ]
            
            for chrome_path in chrome_paths:
                if os.path.exists(chrome_path):
                    result = subprocess.run(
                        [chrome_path, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        version = result.stdout.strip().split()[-1]
                        self.logger.info(f"Chromeバージョン: {version}")
                        return version
            
            return None
            
        except Exception as e:
            self.logger.error(f"Chromeバージョン取得エラー: {e}")
            return None
    
    def download_chromedriver(self, chrome_version=None):
        """ChromeDriverダウンロード"""
        try:
            if not chrome_version:
                chrome_version = self.get_chrome_version()
                if not chrome_version:
                    chrome_version = "131.0.6778.85"  # デフォルトバージョン
            
            self.logger.info(f"ChromeDriver取得開始: バージョン {chrome_version}")
            
            # Chrome for Testing APIから適切なバージョンを検索
            response = requests.get(self.cft_api_url, timeout=10)
            data = response.json()
            
            # メジャーバージョンで検索
            major_version = chrome_version.split('.')[0]
            matching_version = None
            download_url = None
            
            for version_data in reversed(data['versions']):
                if version_data['version'].startswith(major_version):
                    if 'chromedriver' in version_data['downloads']:
                        for platform_data in version_data['downloads']['chromedriver']:
                            if platform_data['platform'] == 'win64':
                                matching_version = version_data['version']
                                download_url = platform_data['url']
                                break
                    if download_url:
                        break
            
            if not download_url:
                self.logger.error(f"ChromeDriverが見つかりません: {chrome_version}")
                return False
            
            self.logger.info(f"ダウンロードURL: {download_url}")
            
            # ダウンロード
            response = requests.get(download_url, timeout=60)
            if response.status_code != 200:
                self.logger.error(f"ダウンロード失敗: HTTP {response.status_code}")
                return False
            
            # 一時ディレクトリに保存
            temp_dir = self.drivers_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            zip_path = temp_dir / "chromedriver.zip"
            
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            # 解凍
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # chromedriver.exeを探す
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file == "chromedriver.exe":
                        source = Path(root) / file
                        shutil.copy2(source, self.chromedriver_path)
                        self.logger.info(f"ChromeDriver配置完了: {self.chromedriver_path}")
                        
                        # クリーンアップ
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return True
            
            self.logger.error("chromedriver.exeが見つかりません")
            return False
            
        except Exception as e:
            self.logger.error(f"ChromeDriverダウンロードエラー: {e}")
            return False
    
    def verify_chromedriver(self):
        """ChromeDriver動作確認"""
        if not self.chromedriver_path.exists():
            return False
        
        try:
            result = subprocess.run(
                [str(self.chromedriver_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.logger.info(f"ChromeDriver確認OK: {result.stdout.strip()}")
                return True
        except Exception as e:
            self.logger.error(f"ChromeDriver確認エラー: {e}")
        
        return False
    
    def setup_chromedriver(self):
        """ChromeDriver セットアップ"""
        try:
            # Chrome確認
            if not self.check_chrome_installed():
                raise Exception("Google Chromeがインストールされていません")
            
            # 既存のChromeDriver確認
            if self.verify_chromedriver():
                self.logger.info("既存のChromeDriverが利用可能")
                return True
            
            # ChromeDriverダウンロード
            self.logger.info("ChromeDriverをダウンロードします")
            if self.download_chromedriver():
                if self.verify_chromedriver():
                    self.logger.info("ChromeDriverセットアップ完了")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"ChromeDriverセットアップエラー: {e}")
            return False
    
    def create_driver(self, headless=True, user_agent=None):
        """WebDriver作成"""
        if not SELENIUM_AVAILABLE:
            raise Exception("Seleniumがインストールされていません")
        
        if not self.chromedriver_path.exists():
            if not self.setup_chromedriver():
                raise Exception("ChromeDriverのセットアップに失敗しました")
        
        try:
            chrome_options = Options()
            
            # 基本オプション
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # JavaScript有効化（重要）
            chrome_options.add_argument("--enable-javascript")
            
            # ヘッドレスモード
            if headless:
                chrome_options.add_argument("--headless=new")
            
            # ウィンドウサイズ
            chrome_options.add_argument("--window-size=1920,1080")
            
            # User-Agent
            if user_agent:
                chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # 画像無効化（高速化）
            prefs = {
                "profile.default_content_setting_values": {
                    "images": 2,
                    "plugins": 2,
                    "popups": 2,
                    "geolocation": 2,
                    "notifications": 2,
                    "media_stream": 2,
                }
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # サービス作成
            service = Service(
                executable_path=str(self.chromedriver_path),
                log_path='NUL'  # ログ出力無効化
            )
            
            # ドライバー作成
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.implicitly_wait(10)
            driver.set_page_load_timeout(30)
            
            self.logger.info("WebDriver作成成功")
            return driver
            
        except Exception as e:
            self.logger.error(f"WebDriver作成エラー: {e}")
            raise
    
    def cleanup_driver(self, driver):
        """WebDriverクリーンアップ"""
        if driver:
            try:
                driver.quit()
                self.logger.info("WebDriverクリーンアップ完了")
            except Exception as e:
                self.logger.error(f"WebDriverクリーンアップエラー: {e}")
    
    def fix_chromedriver(self):
        """ChromeDriver修正（再ダウンロード）"""
        try:
            self.logger.info("ChromeDriver修正開始")
            
            # 既存のドライバー削除
            if self.chromedriver_path.exists():
                os.remove(self.chromedriver_path)
                self.logger.info("既存のChromeDriver削除")
            
            # 再ダウンロード
            if self.setup_chromedriver():
                self.logger.info("ChromeDriver修正完了")
                return True
            else:
                self.logger.error("ChromeDriver修正失敗")
                return False
                
        except Exception as e:
            self.logger.error(f"ChromeDriver修正エラー: {e}")
            return False