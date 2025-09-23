"""
ChromeDriver管理クラス（最適化版）
長時間実行対応の最適化オプション付き
"""

import os
import time
import logging
import platform
import subprocess
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from webdriver_manager.chrome import ChromeDriverManager as WDM
    WDM_AVAILABLE = True
except ImportError:
    WDM_AVAILABLE = False

class ChromeDriverManager:
    """ChromeDriver管理クラス（最適化版）"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.driver_path = None
        self.drivers = []  # 作成したドライバーのリスト
        
        if not SELENIUM_AVAILABLE:
            self.logger.error("Seleniumがインストールされていません")
            raise ImportError("selenium をインストールしてください: pip install selenium")
    
    def get_chrome_version(self):
        """インストールされているChromeのバージョンを取得"""
        system = platform.system()
        
        try:
            if system == "Windows":
                # レジストリからバージョン取得
                import winreg
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
                    version, _ = winreg.QueryValueEx(key, "version")
                    winreg.CloseKey(key)
                    return version
                except:
                    # 別の場所を試す
                    paths = [
                        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                    ]
                    for path in paths:
                        if os.path.exists(path):
                            result = subprocess.run([path, "--version"], capture_output=True, text=True)
                            if result.returncode == 0:
                                version = result.stdout.strip().split()[-1]
                                return version
            
            elif system == "Darwin":  # macOS
                result = subprocess.run(
                    ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    version = result.stdout.strip().split()[-1]
                    return version
            
            elif system == "Linux":
                result = subprocess.run(["google-chrome", "--version"], capture_output=True, text=True)
                if result.returncode == 0:
                    version = result.stdout.strip().split()[-1]
                    return version
        
        except Exception as e:
            self.logger.warning(f"Chromeバージョン取得エラー: {e}")
        
        return None
    
    def setup_driver_path(self):
        """ChromeDriverのパスを設定"""
        if self.driver_path and os.path.exists(self.driver_path):
            return self.driver_path
        
        # webdriver-managerを使用
        if WDM_AVAILABLE:
            try:
                # WDMで取得したパスを修正
                installed_path = WDM().install()
                
                # THIRD_PARTY_NOTICESファイルが返された場合、実際のchromedriver.exeを探す
                if 'THIRD_PARTY_NOTICES' in installed_path:
                    # ディレクトリを取得
                    driver_dir = os.path.dirname(installed_path)
                    
                    # chromedriver.exeを探す
                    possible_names = ['chromedriver.exe', 'chromedriver']
                    for name in possible_names:
                        exe_path = os.path.join(driver_dir, name)
                        if os.path.exists(exe_path):
                            self.driver_path = exe_path
                            self.logger.info(f"ChromeDriver検出（修正済み）: {self.driver_path}")
                            return self.driver_path
                    
                    # サブディレクトリも確認
                    for root, dirs, files in os.walk(driver_dir):
                        for file in files:
                            if file in possible_names:
                                self.driver_path = os.path.join(root, file)
                                self.logger.info(f"ChromeDriver検出（サブディレクトリ）: {self.driver_path}")
                                return self.driver_path
                else:
                    # 正常なパスの場合
                    self.driver_path = installed_path
                    self.logger.info(f"ChromeDriver自動ダウンロード完了: {self.driver_path}")
                    return self.driver_path
                    
            except Exception as e:
                self.logger.error(f"ChromeDriver自動ダウンロード失敗: {e}")
        
        # 手動でパスを探す
        possible_paths = self._get_possible_driver_paths()
        for path in possible_paths:
            if os.path.exists(path):
                self.driver_path = path
                self.logger.info(f"ChromeDriver検出: {path}")
                return path
        
        self.logger.error("ChromeDriverが見つかりません")
        return None
    
    def _get_possible_driver_paths(self):
        """ChromeDriverの可能なパスリストを取得"""
        paths = []
        
        # カレントディレクトリ
        paths.append(os.path.join(os.getcwd(), "chromedriver.exe"))
        paths.append(os.path.join(os.getcwd(), "chromedriver"))
        
        # PATH環境変数
        env_path = os.environ.get("PATH", "").split(os.pathsep)
        for path in env_path:
            paths.append(os.path.join(path, "chromedriver.exe"))
            paths.append(os.path.join(path, "chromedriver"))
        
        # ユーザーディレクトリ
        user_home = Path.home()
        paths.append(user_home / "chromedriver.exe")
        paths.append(user_home / "chromedriver")
        
        # webdriver-managerのデフォルトパス
        wdm_paths = [
            user_home / ".wdm" / "drivers" / "chromedriver" / "win64",
            user_home / ".wdm" / "drivers" / "chromedriver" / "win32",
            user_home / ".wdm" / "drivers" / "chromedriver",
        ]
        
        for wdm_path in wdm_paths:
            if wdm_path.exists():
                # バージョンディレクトリを探す
                for version_dir in wdm_path.iterdir():
                    if version_dir.is_dir():
                        # chromedriver.exeを探す
                        for root, dirs, files in os.walk(version_dir):
                            for file in files:
                                if file == "chromedriver.exe" or file == "chromedriver":
                                    paths.append(os.path.join(root, file))
        
        return paths
    
    def create_driver(self, headless=True, user_agent=None):
        """基本的なドライバー作成（後方互換性のため維持）"""
        options = Options()
        
        if headless:
            options.add_argument("--headless")
        
        if user_agent:
            options.add_argument(f"user-agent={user_agent}")
        
        # 基本的な最適化オプション
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        return self.create_driver_with_options(options)
    
    def create_driver_with_options(self, options):
        """オプション指定でドライバー作成（最適化版）"""
        try:
            driver_path = self.setup_driver_path()
            if not driver_path:
                raise Exception("ChromeDriverパスの設定に失敗しました")
            
            # サービス作成
            service = Service(driver_path)
            
            # ドライバー作成
            driver = webdriver.Chrome(service=service, options=options)
            
            # 作成したドライバーをリストに追加
            self.drivers.append(driver)
            
            self.logger.info("WebDriver作成成功（最適化版）")
            return driver
            
        except Exception as e:
            self.logger.error(f"WebDriver作成エラー: {e}")
            raise
    
    def create_optimized_driver(self, headless=True, user_agent=None):
        """長時間実行用の最適化ドライバー作成"""
        options = Options()
        
        if headless:
            options.add_argument("--headless")
        
        if user_agent:
            options.add_argument(f"user-agent={user_agent}")
        
        # 最適化オプション（長時間実行対応）
        optimization_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-features=VizDisplayCompositor",
            "--memory-pressure-off",
            "--enable-features=NetworkService,NetworkServiceInProcess",
            "--enable-dns-over-https",
            "--aggressive-cache-discard-threshold=100",
            "--disk-cache-size=100",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
            "--disable-logging",
            "--silent",
            "--log-level=3"
        ]
        
        for arg in optimization_args:
            options.add_argument(arg)
        
        # 実験的オプション
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # プリファレンス設定
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "media_stream": 2,
                "media_stream_mic": 2,
                "media_stream_camera": 2,
                "protocol_handlers": 2,
                "ppapi_broker": 2,
                "automatic_downloads": 2,
                "midi_sysex": 2,
                "push_messaging": 2,
                "ssl_cert_decisions": 2,
                "metro_switch_to_desktop": 2,
                "protected_media_identifier": 2,
                "app_banner": 2,
                "site_engagement": 2,
                "durable_storage": 2
            },
            "profile.managed_default_content_settings": {
                "images": 1,  # 画像は表示（必要に応じて2に変更で無効化）
                "plugins": 2,
                "popups": 2,
                "geolocation": 2,
                "media_stream": 2,
                "media_stream_mic": 2,
                "media_stream_camera": 2
            }
        }
        options.add_experimental_option("prefs", prefs)
        
        return self.create_driver_with_options(options)
    
    def cleanup_driver(self, driver):
        """ドライバーのクリーンアップ"""
        try:
            if driver:
                # リストから削除
                if driver in self.drivers:
                    self.drivers.remove(driver)
                
                # タブを全て閉じる
                try:
                    driver.execute_script("window.open('about:blank', '_self');")
                    time.sleep(0.5)
                except:
                    pass
                
                # ドライバーを終了
                try:
                    driver.quit()
                except:
                    pass
                
                self.logger.info("WebDriverクリーンアップ完了")
        except Exception as e:
            self.logger.warning(f"クリーンアップエラー: {e}")
    
    def cleanup_all(self):
        """全てのドライバーをクリーンアップ"""
        for driver in self.drivers.copy():
            self.cleanup_driver(driver)
        self.drivers.clear()
    
    def fix_chromedriver(self):
        """ChromeDriver修正処理"""
        try:
            chrome_version = self.get_chrome_version()
            if chrome_version:
                self.logger.info(f"Chrome バージョン: {chrome_version}")
                
                # webdriver-managerで最新版を取得
                if WDM_AVAILABLE:
                    try:
                        self.driver_path = WDM().install()
                        self.logger.info("ChromeDriver更新完了")
                        
                        # テスト起動
                        test_driver = self.create_optimized_driver()
                        test_driver.quit()
                        
                        self.logger.info("ChromeDriver修正成功")
                        return True
                    except Exception as e:
                        self.logger.error(f"ChromeDriver修正失敗: {e}")
            
            return False
            
        except Exception as e:
            self.logger.error(f"修正処理エラー: {e}")
            return False
    
    def get_driver_info(self):
        """ドライバー情報を取得"""
        info = {
            "chrome_version": self.get_chrome_version(),
            "driver_path": self.driver_path,
            "active_drivers": len(self.drivers),
            "selenium_version": None,
            "webdriver_manager": WDM_AVAILABLE
        }
        
        if SELENIUM_AVAILABLE:
            try:
                import selenium
                info["selenium_version"] = selenium.__version__
            except:
                pass
        
        return info

# 使用例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    manager = ChromeDriverManager()
    
    # ドライバー情報表示
    info = manager.get_driver_info()
    print("ChromeDriver情報:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # 最適化ドライバー作成テスト
    try:
        driver = manager.create_optimized_driver()
        driver.get("https://www.google.com")
        print(f"ページタイトル: {driver.title}")
        manager.cleanup_driver(driver)
        print("テスト完了")
    except Exception as e:
        print(f"テスト失敗: {e}")