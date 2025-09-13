"""
ぐるなび店舗情報スクレイピングツール v3.0
メインアプリケーション
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime
import logging
from pathlib import Path
import json

# カスタムモジュール
from prefecture_mapper import PrefectureMapper
from chrome_driver_manager import ChromeDriverManager
# from scraper_engine import ScraperEngine
from ui_manager import UIManager
# 改良版スクレイパーエンジン使用
from scraper_engine import ImprovedScraperEngine

class GurunaviScraperApp:
    """メインアプリケーションクラス"""
    
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("ぐるなび店舗情報取得ツール v3.0")
        self.window.geometry("800x600")
        self.window.resizable(True, True)
        
        # 設定・パス
        self.app_dir = Path.cwd()
        self.config_file = self.app_dir / "config.json"
        self.log_file = self.app_dir / "scraper.log"
        
        # ログ設定
        self.setup_logging()
        
        # 設定読み込み
        self.config = self.load_config()
        
        # マネージャー初期化
        self.prefecture_mapper = PrefectureMapper()
        self.chrome_manager = ChromeDriverManager()
        self.scraper_engine = None
        self.ui_manager = UIManager(self.window, self)
        
        # 状態管理
        self.is_running = False
        self.start_time = None
        self.scraped_stores = []
        
        # UI構築
        self.ui_manager.setup_ui()
        
        self.logger.info("アプリケーション起動完了 v3.0")
    
    def setup_logging(self):
        """ログ設定"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_config(self):
        """設定読み込み"""
        default_config = {
            "cooltime_min": 1.0,
            "cooltime_max": 5.0,
            "ua_switch_interval": 100,
            "last_save_path": str(Path.home() / "Downloads"),
            "user_agents": [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            ]
        }
        
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
        except Exception as e:
            self.logger.error(f"設定読み込みエラー: {e}")
        
        return default_config
    
    def save_config(self):
        """設定保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            self.logger.info("設定保存完了")
        except Exception as e:
            self.logger.error(f"設定保存エラー: {e}")
    
    def start_scraping(self):
        """スクレイピング開始"""
        if self.is_running:
            messagebox.showwarning("警告", "既に実行中です")
            return
        
        # 入力値取得
        search_params = self.ui_manager.get_search_params()
        if not self.validate_params(search_params):
            return
        
        # 設定取得
        settings = self.ui_manager.get_settings()
        self.config.update(settings)
        self.save_config()
        
        # 初期化
        self.is_running = True
        self.start_time = time.time()
        self.scraped_stores = []
        
        # スクレイパーエンジン初期化
        self.scraper_engine = ImprovedScraperEngine(
            chrome_manager=self.chrome_manager,
            prefecture_mapper=self.prefecture_mapper,
            config=self.config,
            callback=self.update_progress
        )
        
        # UIを実行中タブに切り替え
        self.ui_manager.switch_to_running_tab()
        
        # ワーカースレッド開始
        thread = threading.Thread(
            target=self.scraping_worker,
            args=(search_params,)
        )
        thread.daemon = True
        thread.start()
    
    def validate_params(self, params):
        """パラメータ検証"""
        if not params['prefecture']:
            messagebox.showerror("エラー", "都道府県を選択してください")
            return False
        
        if not params['save_path']:
            messagebox.showerror("エラー", "保存先を指定してください")
            return False
        
        if not params['filename']:
            messagebox.showerror("エラー", "ファイル名を入力してください")
            return False
        
        return True
    
    def scraping_worker(self, search_params):
        """スクレイピングワーカースレッド（改良版）"""
        try:
            self.logger.info(f"スクレイピング開始: {search_params}")
            
            self.scraper_engine = ImprovedScraperEngine(
                chrome_manager=self.chrome_manager,
                prefecture_mapper=self.prefecture_mapper,
                config=self.config,
                callback=self.update_progress
            )
            
            # フェーズ1: 店舗一覧取得（URLのみ）
            self.update_progress({
                'phase': 'listing',
                'message': '店舗一覧を取得中...',
                'progress': 0
            })
            
            store_list = self.scraper_engine.get_store_list(
                prefecture=search_params['prefecture'],
                city=search_params['city'],
                max_count=search_params['max_count'],
                unlimited=search_params['unlimited']
            )
            
            if not store_list:
                raise Exception("店舗一覧の取得に失敗しました")
            
            self.logger.info(f"店舗一覧取得完了: {len(store_list)}件")
            
            # 店舗一覧をExcelに保存
            self.scraper_engine.save_store_list(
                store_list,
                search_params['save_path'],
                search_params['filename'] + "_list"
            )
            
            # URL取得のみで終了するオプション
            url_only_mode = search_params.get('url_only', False)
            if url_only_mode:
                self.update_progress({
                    'phase': 'complete',
                    'message': f'URL取得完了: {len(store_list)}件',
                    'progress': 100,
                    'elapsed_time': time.time() - self.start_time
                })
                
                messagebox.showinfo(
                    "完了",
                    f"店舗URL取得が完了しました\n\n"
                    f"取得件数: {len(store_list)}件\n"
                    f"処理時間: {time.time() - self.start_time:.1f}秒"
                )
                return
            
            # フェーズ2: 店舗詳細取得
            total_stores = len(store_list)
            for idx, store in enumerate(store_list, 1):
                if not self.is_running:
                    break
                
                self.update_progress({
                    'phase': 'detail',
                    'message': f'店舗詳細を取得中 ({idx}/{total_stores}): {store["name"]}',
                    'progress': 50 + (idx / total_stores) * 50,  # 50-100%の範囲
                    'current': idx,
                    'total': total_stores
                })
                
                # 店舗詳細取得
                detail = self.scraper_engine.get_store_detail(store['url'])
                if detail:
                    self.scraped_stores.append(detail)
                
                # User-Agent切り替え
                if idx % self.config['ua_switch_interval'] == 0:
                    self.scraper_engine.switch_user_agent()
            
            # フェーズ3: 結果保存
            if self.scraped_stores:
                self.update_progress({
                    'phase': 'saving',
                    'message': 'Excelファイルに保存中...',
                    'progress': 100
                })
                
                self.scraper_engine.save_results(
                    self.scraped_stores,
                    search_params['save_path'],
                    search_params['filename']
                )
                
                # 完了
                elapsed_time = time.time() - self.start_time
                self.update_progress({
                    'phase': 'complete',
                    'message': f'完了: {len(self.scraped_stores)}件取得',
                    'progress': 100,
                    'elapsed_time': elapsed_time
                })
                
                messagebox.showinfo(
                    "完了",
                    f"スクレイピングが完了しました\n\n"
                    f"取得件数: {len(self.scraped_stores)}件\n"
                    f"処理時間: {elapsed_time:.1f}秒"
                )
            
        except Exception as e:
            self.logger.error(f"スクレイピングエラー: {e}")
            messagebox.showerror("エラー", f"エラーが発生しました:\n{str(e)}")
        finally:
            self.cleanup()

    def update_progress(self, data):
        """進捗更新コールバック"""
        self.window.after(0, self.ui_manager.update_progress, data)
    
    def stop_scraping(self):
        """スクレイピング強制停止"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.cleanup()
        self.ui_manager.reset_progress()
        # messagebox.showinfo は削除（停止メッセージ画面に既に表示）
    
    def cleanup(self):
        """クリーンアップ"""
        self.is_running = False
        if self.scraper_engine:
            self.scraper_engine.cleanup()
            self.scraper_engine = None
    
    def set_scraping_state(self, is_scraping):
        """スクレイピング状態設定"""
        self.is_running = is_scraping
        if not is_scraping:
            # 終了時にUIを有効化
            self.ui_manager.enable_all_tabs()
            self.ui_manager.timer_running = False
    
    def on_prefecture_changed(self, prefecture):
        """都道府県変更時の処理"""
        cities = self.prefecture_mapper.get_cities(prefecture)
        self.ui_manager.update_city_list(cities)
    
    def run(self):
        """アプリケーション実行"""
        try:
            self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.window.mainloop()
        except KeyboardInterrupt:
            self.logger.info("アプリケーション中断")
        finally:
            self.cleanup()
            self.logger.info("アプリケーション終了")
    
    def on_closing(self):
        """ウィンドウ閉じる時の処理"""
        if self.is_running:
            result = messagebox.askyesno(
                "確認",
                "スクレイピング実行中です。終了しますか？"
            )
            if not result:
                return
        
        self.cleanup()
        self.window.destroy()

def main():
    """メイン関数"""
    try:
        app = GurunaviScraperApp()
        app.run()
    except Exception as e:
        logging.error(f"アプリケーション起動エラー: {e}")
        messagebox.showerror("起動エラー", f"アプリケーション起動失敗:\n{e}")

if __name__ == "__main__":
    main()