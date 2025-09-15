"""
ぐるなび店舗情報スクレイピングツール v3.0
現実的処理時間対応版
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime
import logging
from pathlib import Path
import json
import pandas as pd

# カスタムモジュール
from prefecture_mapper import PrefectureMapper
from chrome_driver_manager import ChromeDriverManager
from ui_manager import UIManager
from scraper_engine import ImprovedScraperEngine

class GurunaviScraperApp:
    """メインアプリケーションクラス"""
    
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("ぐるなび店舗情報取得ツール v3.0（現実的処理時間対応版）")
        self.window.geometry("800x650")
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
        
        self.logger.info("アプリケーション起動完了 v3.0（現実的処理時間対応版）")
    
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
            "cooltime_min": 2.0,
            "cooltime_max": 4.0,
            "ua_switch_interval": 15,
            "retry_delay": 5.0,
            "captcha_delay": 30.0,
            "ip_limit_delay": 60.0,
            "last_save_path": str(Path.home() / "Downloads"),
            "user_agents": [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ],
            "time_zone_aware": {
                "peak_hours": {"start": 12, "end": 13, "multiplier": 1.5},
                "evening_hours": {"start": 18, "end": 20, "multiplier": 1.3},
                "safe_hours": {"start": 23, "end": 6, "multiplier": 0.8}
            }
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
    
    def get_estimated_time(self, store_count):
        """処理時間予測"""
        base_time_per_store = 7  # 秒
        current_hour = datetime.now().hour
        
        # 時間帯倍率の計算
        time_config = self.config.get('time_zone_aware', {})
        
        # ピークタイム
        peak = time_config.get('peak_hours', {})
        if peak.get('start', 12) <= current_hour <= peak.get('end', 13):
            multiplier = peak.get('multiplier', 1.5)
        # 夜の繁忙時間
        elif time_config.get('evening_hours', {}).get('start', 18) <= current_hour <= time_config.get('evening_hours', {}).get('end', 20):
            multiplier = time_config.get('evening_hours', {}).get('multiplier', 1.3)
        # 安全時間帯
        elif current_hour >= time_config.get('safe_hours', {}).get('start', 23) or current_hour <= time_config.get('safe_hours', {}).get('end', 6):
            multiplier = time_config.get('safe_hours', {}).get('multiplier', 0.8)
        else:
            multiplier = 1.0
        
        estimated_seconds = store_count * base_time_per_store * multiplier
        return estimated_seconds / 60  # 分で返す
    
    def start_scraping(self):
        """スクレイピング開始"""
        if self.is_running:
            messagebox.showwarning("警告", "既に実行中です")
            return
        
        # 入力値取得
        search_params = self.ui_manager.get_search_params()
        if not self.validate_params(search_params):
            return
        
        # 処理時間の事前確認
        store_count = search_params['max_count'] if not search_params['unlimited'] else 100
        estimated_time = self.get_estimated_time(store_count)
        
        # 時間帯警告
        if not self.show_time_zone_warning(estimated_time):
            return
        
        # 設定取得
        settings = self.ui_manager.get_settings()
        self.config.update(settings)
        self.save_config()
        
        # 初期化
        self.is_running = True
        self.start_time = time.time()
        self.scraped_stores = []
        
        # UIを実行中タブに切り替え
        self.ui_manager.switch_to_running_tab()
        
        # ワーカースレッド開始
        thread = threading.Thread(
            target=self.scraping_worker,
            args=(search_params,)
        )
        thread.daemon = True
        thread.start()
    
    def show_time_zone_warning(self, estimated_time):
        """時間帯警告表示"""
        current_hour = datetime.now().hour
        
        # 警告メッセージの決定
        warning_msg = ""
        if 12 <= current_hour <= 13:
            warning_msg = "現在は昼食時間帯です。処理時間が通常の1.5倍程度かかる可能性があります。"
        elif 18 <= current_hour <= 20:
            warning_msg = "現在は夕食時間帯です。処理時間が通常の1.3倍程度かかる可能性があります。"
        
        # 長時間処理の警告
        if estimated_time > 30:
            if warning_msg:
                warning_msg += "\n\n"
            warning_msg += f"予想処理時間が{estimated_time:.0f}分と長時間になります。"
        
        # 警告がある場合は確認ダイアログ表示
        if warning_msg:
            full_msg = (
                f"{warning_msg}\n\n"
                f"推奨実行時間: 深夜23:00～早朝6:00\n"
                f"現在の予想処理時間: 約{estimated_time:.0f}分\n\n"
                f"処理を続行しますか？"
            )
            
            result = messagebox.askyesno("時間帯確認", full_msg)
            return result
        
        return True
    
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
        """現実的処理時間対応スクレイピングワーカー"""
        try:
            self.logger.info(f"スクレイピング開始: {search_params}")
            
            # 現実的なスクレイパーエンジンを使用
            self.scraper_engine = ImprovedScraperEngine(
                chrome_manager=self.chrome_manager,
                prefecture_mapper=self.prefecture_mapper,
                config=self.config,
                callback=self.update_progress
            )
            
            # フェーズ1: 店舗一覧取得
            self.update_progress({
                'phase': 'listing',
                'message': '店舗一覧を取得中...',
                'progress': 0
            })
            
            # 店舗一覧取得
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
            
            # URL取得のみオプション
            if search_params.get('url_only', False):
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
            
            # フェーズ2: 現実的な処理時間での店舗詳細取得
            total_stores = len(store_list)
            estimated_time = self.get_estimated_time(total_stores)
            
            # 詳細処理開始のメッセージ
            self.update_progress({
                'phase': 'detail',
                'message': f'店舗詳細取得開始 (予想時間: {estimated_time:.0f}分)',
                'progress': 50,
                'estimated_completion': estimated_time
            })
            
            try:
                # 現実的なスクレイパーで処理開始
                self.scraped_stores = self.scraper_engine.start_processing(
                    store_list, search_params
                )
                
                # 処理完了
                if self.scraped_stores and self.is_running:
                    self.update_progress({
                        'phase': 'saving',
                        'message': '最終結果を保存中...',
                        'progress': 100
                    })
                    
                    # 最終保存
                    self.scraper_engine.save_results(
                        self.scraped_stores,
                        search_params['save_path'],
                        search_params['filename']
                    )
                    
                    # 完了統計
                    elapsed_time = time.time() - self.start_time
                    stats = self.scraper_engine.get_processing_stats()
                    success_count = self.scraper_engine.stats['successful_stores']
                    
                    self.update_progress({
                        'phase': 'complete',
                        'message': f'完了: {len(self.scraped_stores)}件取得',
                        'progress': 100,
                        'elapsed_time': elapsed_time,
                        'final_stats': stats
                    })
                    
                    if self.is_running:
                        # 詳細な完了メッセージ
                        completion_msg = (
                            f"スクレイピングが完了しました\n\n"
                            f"=== 処理結果 ===\n"
                            f"取得件数: {len(self.scraped_stores)}件\n"
                            f"成功件数: {success_count}件\n"
                            f"失敗件数: {len(self.scraped_stores) - success_count}件\n"
                            f"処理時間: {elapsed_time/60:.1f}分\n"
                            f"平均時間/店舗: {elapsed_time/len(self.scraped_stores):.1f}秒\n\n"
                            f"=== その他統計 ===\n"
                            f"UA切り替え: {stats.get('UA切り替え回数', 0)}回\n"
                            f"CAPTCHA遭遇: {stats.get('CAPTCHA遭遇回数', 0)}回\n"
                            f"IP制限遭遇: {stats.get('IP制限遭遇回数', 0)}回\n\n"
                            f"結果ファイル: {search_params['filename']}.xlsx"
                        )
                        
                        messagebox.showinfo("完了", completion_msg)
                
                elif not self.is_running:
                    # 中断処理
                    self.handle_interruption(search_params)
            
            except Exception as processing_error:
                self.logger.error(f"詳細処理エラー: {processing_error}")
                # エラー時でも取得済みデータを保存
                self.handle_processing_error(processing_error, search_params)
            
        except Exception as e:
            self.logger.error(f"スクレイピングエラー: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            error_msg = f"エラーが発生しました:\n{str(e)}"
            if hasattr(self, 'scraped_stores') and self.scraped_stores:
                try:
                    self.save_error_results(search_params)
                    error_msg += f"\n\n取得済みデータは {search_params['filename']}_error.xlsx に保存されました"
                except:
                    pass
            
            messagebox.showerror("エラー", error_msg)
        
        finally:
            self.cleanup()
    
    def handle_interruption(self, search_params):
        """中断処理"""
        try:
            partial_count = len(self.scraped_stores) if self.scraped_stores else 0
            
            self.update_progress({
                'phase': 'stopped',
                'message': f'中断されました: {partial_count}件取得済み',
                'progress': 0
            })
            
            if partial_count > 0:
                # 中断時の部分データ保存
                filename = search_params['filename'] + "_partial"
                self.scraper_engine.save_results(
                    self.scraped_stores,
                    search_params['save_path'],
                    filename
                )
                
                messagebox.showinfo(
                    "中断",
                    f"処理が中断されました\n\n"
                    f"取得済み件数: {partial_count}件\n"
                    f"結果ファイル: {filename}.xlsx"
                )
            
        except Exception as e:
            self.logger.error(f"中断処理エラー: {e}")
    
    def handle_processing_error(self, error, search_params):
        """処理エラー時の対応"""
        try:
            if hasattr(self, 'scraped_stores') and self.scraped_stores:
                self.save_error_results(search_params)
                error_msg = (
                    f"処理中にエラーが発生しました:\n{str(error)}\n\n"
                    f"取得済みデータ: {len(self.scraped_stores)}件\n"
                    f"エラーファイル: {search_params['filename']}_error.xlsx に保存されました"
                )
            else:
                error_msg = f"処理中にエラーが発生しました:\n{str(error)}"
            
            messagebox.showerror("処理エラー", error_msg)
            
        except Exception as e:
            self.logger.error(f"エラー処理中の例外: {e}")
    
    def save_error_results(self, search_params):
        """エラー時結果保存"""
        try:
            filename = search_params['filename'] + "_error"
            self.scraper_engine.save_results(
                self.scraped_stores,
                search_params['save_path'],
                filename
            )
            
        except Exception as e:
            self.logger.error(f"エラー結果保存失敗: {e}")
    
    def update_progress(self, data):
        """進捗更新コールバック（統計情報対応）"""
        # 統計情報を含む進捗更新
        if 'stats' in data:
            # UIに統計情報を表示
            stats_text = "\n".join([f"{k}: {v}" for k, v in data['stats'].items()])
            data['stats_text'] = stats_text
        
        self.window.after(0, self.ui_manager.update_progress, data)
    
    def stop_scraping(self):
        """スクレイピング強制停止"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.cleanup()
        self.ui_manager.reset_progress()
    
    def cleanup(self):
        """クリーンアップ"""
        self.is_running = False
        if self.scraper_engine:
            self.scraper_engine.cleanup()
            self.scraper_engine = None
    
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