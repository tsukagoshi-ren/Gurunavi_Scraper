"""
現実的処理時間対応スクレイピングエンジン
UA切り替え改善・生データログ出力対応版
"""

import time
import random
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from urllib.parse import urlparse

from gurunavi_label_based_extractor import GurunaviLabelBasedExtractor
from gurunavi_multi_approach_extractor import GurunaviMultiApproachExtractor

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class ImprovedScraperEngine:
    """段階的動的生成対応スクレイピングエンジンクラス（UA切り替え改善版）"""
    
    def __init__(self, chrome_manager, prefecture_mapper, config, callback=None):
        self.logger = logging.getLogger(__name__)
        self.chrome_manager = chrome_manager
        self.prefecture_mapper = prefecture_mapper
        self.config = config
        self.callback = callback
        self.driver = None
        self.ua_index = 0
        self.access_count = 0
        self.processed_urls = set()
        
        # Excel保存用の変数
        self.excel_file_path = None
        self.current_results = []
        
        # 並列保存用の設定
        self.save_queue = None
        self.save_executor = None
        self._setup_async_save()
        
        # UA切り替え改善：デフォルト値を30に変更
        if self.config.get('ua_switch_interval', 15) == 15:
            self.config['ua_switch_interval'] = 30
            self.logger.info("UA切り替え間隔を30件に変更しました（60件問題対策）")
        
        # 統計情報
        self.stats = {
            'start_time': None,
            'total_stores': 0,
            'processed_stores': 0,
            'successful_stores': 0,
            'failed_stores': 0,
            'ua_switches': 0,
            'captcha_encounters': 0,
            'ip_restrictions': 0,
            'estimated_completion': None,
            'phone_extraction_failures': 0,  # 電話番号取得失敗カウント追加
            'success_rate': 1.0  # 成功率追跡
        }
        
        # 時間帯別速度調整
        self.time_multiplier = self._get_time_multiplier()
        
        # プロセス優先度設定
        self._set_process_priority()
    
    
    def _setup_async_save(self):
        """非同期保存の設定"""
        import queue
        from concurrent.futures import ThreadPoolExecutor
        
        self.save_queue = queue.Queue()
        self.save_executor = ThreadPoolExecutor(max_workers=1)
        
        def save_worker():
            while True:
                item = self.save_queue.get()
                if item is None:
                    break
                try:
                    self._do_save(item['data'], item['path'], item['filename'])
                except Exception as e:
                    self.logger.error(f"非同期保存エラー: {e}")
                finally:
                    self.save_queue.task_done()
        
        self.save_executor.submit(save_worker)
    
    def _set_process_priority(self):
        """プロセス優先度を設定"""
        try:
            import psutil
            import os
            
            p = psutil.Process(os.getpid())
            if os.name == 'nt':  # Windows
                p.nice(psutil.HIGH_PRIORITY_CLASS)
                self.logger.info("プロセス優先度を高に設定しました")
            else:  # Linux/Mac
                p.nice(-5)
                self.logger.info("プロセス優先度を上げました (nice: -5)")
        except Exception as e:
            self.logger.debug(f"プロセス優先度設定失敗: {e}")
    
    def _get_time_multiplier(self):
        """現在時刻に基づく速度調整倍率を取得"""
        try:
            current_hour = datetime.now().hour
            time_config = self.config.get('time_zone_aware', {})
            
            # ピークタイム（昼食時間）
            peak = time_config.get('peak_hours', {})
            if peak.get('start', 12) <= current_hour <= peak.get('end', 13):
                return peak.get('multiplier', 1.5)
            
            # 夜の繁忙時間
            evening = time_config.get('evening_hours', {})
            if evening.get('start', 18) <= current_hour <= evening.get('end', 20):
                return evening.get('multiplier', 1.3)
            
            # 安全時間帯（深夜早朝）
            safe = time_config.get('safe_hours', {})
            safe_start = safe.get('start', 23)
            safe_end = safe.get('end', 6)
            if current_hour >= safe_start or current_hour <= safe_end:
                return safe.get('multiplier', 0.8)
            
            # 通常時間帯
            return 1.0
            
        except Exception as e:
            self.logger.warning(f"時間帯調整取得エラー: {e}")
            return 1.0
    
    def initialize_driver(self):
        """ドライバー初期化（最適化オプション付き）"""
        try:
            user_agent = self.config['user_agents'][self.ua_index]
            
            # ChromeDriverManagerが最適化ドライバーを作成する場合
            if hasattr(self.chrome_manager, 'create_optimized_driver'):
                self.driver = self.chrome_manager.create_optimized_driver(
                    headless=True,
                    user_agent=user_agent
                )
            else:
                # 従来の方法（後方互換性）
                self.driver = self.chrome_manager.create_driver(
                    headless=True,
                    user_agent=user_agent
                )
            
            # 広告・アナリティクスをブロック
            self._block_unnecessary_resources()
            
            # タイムアウト設定（段階的に調整）
            if self.stats['processed_stores'] < 30:
                self.driver.set_page_load_timeout(20)
            elif self.stats['processed_stores'] < 60:
                self.driver.set_page_load_timeout(25)
            else:
                self.driver.set_page_load_timeout(30)
            
            self.driver.implicitly_wait(8)
            self.driver.set_script_timeout(20)
            
            self.logger.info(f"ドライバー初期化完了 (UA: {self.ua_index}) - 最適化版")
            return True
        except Exception as e:
            self.logger.error(f"ドライバー初期化エラー: {e}")
            # より詳細なエラー情報
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def _block_unnecessary_resources(self):
        """不要なリソースをブロック"""
        try:
            if self.driver:
                self.driver.execute_cdp_cmd('Network.setBlockedURLs', {
                    'urls': [
                        '*googletagmanager*', 
                        '*google-analytics*',
                        '*doubleclick*', 
                        '*facebook*',
                        '*twitter.com/widgets*',
                        '*platform.twitter*',
                        '*amazon-adsystem*',
                        '*googleapis.com/maps*',  # 地図API（必要に応じて）
                        '*hotjar*',
                        '*newrelic*',
                        '*clarity.ms*'
                    ]
                })
                self.logger.debug("広告・アナリティクスのブロック設定完了")
        except Exception as e:
            self.logger.debug(f"リソースブロック設定エラー: {e}")
    
    def cleanup(self):
        """クリーンアップ"""
        if self.driver:
            self.chrome_manager.cleanup_driver(self.driver)
            self.driver = None
        
        # 非同期保存の終了
        if self.save_queue:
            self.save_queue.put(None)
        if self.save_executor:
            self.save_executor.shutdown(wait=True)
    
    def switch_user_agent(self):
        """User-Agent切り替え（改善版：セッション復元対策）"""
        try:
            old_ua = self.ua_index
            self.ua_index = (self.ua_index + 1) % len(self.config['user_agents'])
            self.stats['ua_switches'] += 1
            
            self.logger.info(f"=== UA切り替え開始 (切り替え回数: {self.stats['ua_switches']}) ===")
            
            # 切り替え前に長めの待機（人間の休憩を模倣）
            wait_time = random.uniform(8, 12)
            self.logger.info(f"UA切り替え前の休憩: {wait_time:.1f}秒")
            time.sleep(wait_time)
            
            # 現在のCookieを保存（可能な場合）
            cookies = None
            try:
                cookies = self.driver.get_cookies()
                self.logger.debug(f"Cookie保存: {len(cookies)}個")
            except:
                pass
            
            # ドライバー切り替え
            self.cleanup()
            if not self.initialize_driver():
                raise Exception("ドライバー再初期化失敗")
            
            # ぐるなびトップページにアクセスして信頼性構築
            self.logger.info("信頼性構築のためトップページアクセス")
            self.driver.get("https://r.gnavi.co.jp")
            time.sleep(random.uniform(3, 5))
            
            # Cookieの復元を試みる（可能な場合）
            if cookies:
                try:
                    for cookie in cookies:
                        if 'expiry' in cookie:
                            del cookie['expiry']
                        self.driver.add_cookie(cookie)
                    self.logger.debug("Cookie復元完了")
                except Exception as e:
                    self.logger.warning(f"Cookie復元失敗: {e}")
            
            # 追加の待機
            additional_wait = random.uniform(5, 8)
            self.logger.info(f"UA切り替え完了: {old_ua} → {self.ua_index}、追加待機: {additional_wait:.1f}秒")
            time.sleep(additional_wait)
            
            # 60件ごとの特別な処理
            if self.stats['processed_stores'] % 60 == 0:
                self.logger.warning("=== 60件処理完了 - 追加の安全対策実行 ===")
                extra_wait = random.uniform(15, 20)
                self.logger.info(f"60件境界での特別待機: {extra_wait:.1f}秒")
                time.sleep(extra_wait)
            
        except Exception as e:
            self.logger.error(f"User-Agent切り替えエラー: {e}")
            raise
    
    def wait_with_cooltime(self):
        """安全なクールタイム待機（動的調整付き）"""
        base_min = self.config['cooltime_min']
        base_max = self.config['cooltime_max']
        
        # 時間帯による調整
        adjusted_min = base_min * self.time_multiplier
        adjusted_max = base_max * self.time_multiplier
        
        # 成功率に応じた動的調整
        if self.stats['processed_stores'] > 10:
            success_rate = self.stats['successful_stores'] / self.stats['processed_stores']
            if success_rate > 0.9:
                # 成功率が高い場合は短縮
                adjusted_min *= 0.8
                adjusted_max *= 0.8
            elif success_rate < 0.5:
                # 成功率が低い場合は延長
                adjusted_min *= 1.2
                adjusted_max *= 1.2
        
        # 60件前後での追加調整
        if 58 <= self.stats['processed_stores'] <= 65:
            adjusted_min *= 1.5
            adjusted_max *= 1.5
            self.logger.debug(f"60件境界付近のため待機時間を1.5倍に調整")
        
        cooltime = random.uniform(adjusted_min, adjusted_max)
        
        self.logger.debug(f"クールタイム待機: {cooltime:.1f}秒 (倍率: {self.time_multiplier})")
        time.sleep(cooltime)
    
    def _trigger_stepwise_loading(self):
        """段階的スクロールによるLazy Loading誘発"""
        try:
            self.logger.debug("段階的読み込み誘発開始")
            
            # Phase 1: 基本DOM読み込み確認（10秒→8秒に短縮）
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(1)
            
            # Phase 2: 段階的スクロールでコンテンツ読み込み誘発
            scroll_positions = [0, 200, 500, 800, 1100, 1400, 800, 400, 0]
            
            for i, position in enumerate(scroll_positions):
                self.logger.debug(f"スクロール {i+1}/{len(scroll_positions)}: {position}px")
                self.driver.execute_script(f"window.scrollTo(0, {position});")
                time.sleep(0.8)
                
                # 途中で要素チェック（効率化）
                if i == 4:  # 中間地点で確認
                    try:
                        elements_found = len(self.driver.find_elements(By.CSS_SELECTOR, "#info-table, .basic-table"))
                        if elements_found > 0:
                            self.logger.debug("中間チェック: 主要要素検出済み")
                            break
                    except:
                        pass
            
            # Phase 3: 店舗情報エリアにフォーカス
            try:
                info_elements = self.driver.find_elements(By.CSS_SELECTOR, "#info-table, .basic-table, #info-name")
                if info_elements:
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", info_elements[0])
                    time.sleep(1.5)
                    self.logger.debug("店舗情報エリアにフォーカス完了")
            except Exception as e:
                self.logger.debug(f"店舗情報エリアフォーカス失敗: {e}")
            
            self.logger.debug("段階的読み込み誘発完了")
            return True
            
        except Exception as e:
            self.logger.warning(f"段階的読み込み誘発エラー: {e}")
            return False
    
    def _wait_for_network_completion(self):
        """AJAX/Fetch完了の効率的検知（最適化版）"""
        try:
            self.logger.debug("ネットワーク完了待機開始（最適化版）")
            
            # 一覧ページの場合は短い待機時間
            max_wait = 3000 if self._is_list_page() else 8000
            
            # ネットワークアクティビティ監視スクリプト（軽量版）
            network_script = f"""
            const controller = new AbortController();
            const signal = controller.signal;
            
            let pendingRequests = 0;
            const startTime = Date.now();
            const maxWaitTime = {max_wait}; // 動的に変更
            
            // Fetch監視（軽量）
            const originalFetch = window.fetch;
            window.fetch = function(...args) {{
                pendingRequests++;
                return originalFetch.apply(this, args).finally(() => {{
                    pendingRequests--;
                }});
            }};
            
            // XMLHttpRequest監視（軽量）
            const OriginalXHR = window.XMLHttpRequest;
            const originalSend = OriginalXHR.prototype.send;
            OriginalXHR.prototype.send = function(...args) {{
                pendingRequests++;
                this.addEventListener('loadend', () => pendingRequests--);
                return originalSend.apply(this, args);
            }};
            
            // 非同期チェック
            return new Promise((resolve) => {{
                const checkNetwork = () => {{
                    const elapsed = Date.now() - startTime;
                    
                    if (elapsed > maxWaitTime) {{
                        resolve({{completed: false, reason: 'timeout', elapsed: elapsed}});
                        return;
                    }}
                    
                    if (pendingRequests === 0) {{
                        // 0.3秒間アイドル状態が続いたら完了とみなす（短縮）
                        setTimeout(() => {{
                            if (pendingRequests === 0) {{
                                resolve({{completed: true, reason: 'idle', elapsed: elapsed}});
                            }} else {{
                                setTimeout(checkNetwork, 100);
                            }}
                        }}, 300);
                    }} else {{
                        setTimeout(checkNetwork, 100);
                    }}
                }};
                
                // 初回チェック
                setTimeout(checkNetwork, 50);
            }});
            """
            
            try:
                result = self.driver.execute_async_script(network_script)
                
                if result.get('completed', False):
                    self.logger.debug(f"ネットワーク完了検知: {result.get('reason')} ({result.get('elapsed', 0)}ms)")
                    return True
                else:
                    self.logger.debug(f"ネットワーク監視タイムアウト: {result.get('reason')} ({result.get('elapsed', 0)}ms)")
                    return False
                    
            except Exception as e:
                self.logger.debug(f"ネットワーク監視スクリプトエラー: {e}")
                # フォールバック: 基本待機（短縮）
                time.sleep(1)
                return False
                
        except Exception as e:
            self.logger.warning(f"ネットワーク完了待機エラー: {e}")
            return False
    
    def _is_list_page(self):
        """現在のページが一覧ページかどうか判定"""
        try:
            current_url = self.driver.current_url
            # URLに '/rs/' が含まれていれば一覧ページ
            return '/rs/' in current_url or '/rs?' in current_url
        except:
            return False
    
    def _wait_for_stepwise_content_load(self):
        """段階的コンテンツ読み込み完了待機（詳細ページ専用）"""
        try:
            # 一覧ページの場合はスキップ
            if self._is_list_page():
                self.logger.debug("一覧ページのため段階的読み込みをスキップ")
                return True
            
            self.logger.debug("段階的コンテンツ読み込み待機開始（詳細ページ）")
            
            # Step 1: 段階的スクロール誘発
            scroll_success = self._trigger_stepwise_loading()
            
            # Step 2: ネットワーク完了待機
            network_success = self._wait_for_network_completion()
            
            # Step 3: 最終安定化待機
            time.sleep(1.5)
            
            # Step 4: 結果検証（詳細ページ用の要素）
            verification_selectors = [
                "#info-table",
                "#info-name", 
                ".basic-table",
                ".number"
            ]
            
            found_elements = []
            for selector in verification_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        found_elements.append(selector)
                except:
                    pass
            
            success = len(found_elements) > 0
            self.logger.info(f"段階的読み込み完了 - 検出要素: {found_elements} (スクロール: {scroll_success}, ネットワーク: {network_success})")
            
            return success
            
        except Exception as e:
            self.logger.error(f"段階的コンテンツ読み込み待機エラー: {e}")
            return False
    
    def is_valid_store_url(self, url):
        """店舗URLの有効性チェック"""
        if not url or not isinstance(url, str):
            return False
        
        try:
            parsed = urlparse(url.strip())
            
            # 1. ドメインの厳密チェック - r.gnavi.co.jp のみ許可
            if parsed.netloc.lower() != 'r.gnavi.co.jp':
                return False
            
            # 2. パスの取得（クエリパラメータを除去）
            path = parsed.path.rstrip('/')
            
            # 3. 除外パターンの厳密チェック
            invalid_patterns = [
                r'/rs/?$',          # 検索結果
                r'/area/',          # 地域ページ
                r'/city/',          # 市区町村ページ
                r'/campaign/',      # キャンペーン
                r'/lottery/',       # 抽選
                r'/kanjirank',      # ランキング
                r'/mycoupon',       # マイクーポン
                r'/guide/',         # ガイド
                r'/help/',          # ヘルプ
                r'/search',         # 検索
                r'/special/',       # 特集
                r'/feature/',       # フィーチャー
                r'/category/',      # カテゴリ
                r'/genre/',         # ジャンル
                r'/apps',           # アプリ関連
                r'/api/',           # API
                r'/static/',        # 静的ファイル
                r'/css/',           # CSS
                r'/js/',            # JavaScript
                r'/img/',           # 画像
                # 都道府県名の除外パターン（新規追加）
                r'^/(hokkaido|aomori|iwate|miyagi|akita|yamagata|fukushima|ibaraki|tochigi|gunma|saitama|chiba|tokyo|kanagawa|niigata|toyama|ishikawa|fukui|yamanashi|nagano|gifu|shizuoka|aichi|mie|shiga|kyoto|osaka|hyogo|nara|wakayama|tottori|shimane|okayama|hiroshima|yamaguchi|tokushima|kagawa|ehime|kochi|fukuoka|saga|nagasaki|kumamoto|oita|miyazaki|kagoshima|okinawa)/?$',
            ]
            
            for pattern in invalid_patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    return False
            
            # 4. 有効パターンチェック - 店舗URLのみ
            valid_patterns = [
                r'^/[a-zA-Z0-9]{3,20}/?$',  # 基本店舗URL
                r'^/[a-zA-Z0-9]{3,20}/(menu|course|map|coupon|photo|plan)/?$'  # サブページ
            ]
            
            for pattern in valid_patterns:
                if re.match(pattern, path, re.IGNORECASE):
                    return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"URL検証エラー: {url} - {e}")
            return False
    
    def get_base_store_url(self, url):
        """店舗URLのベースURL取得"""
        try:
            parsed = urlparse(url)
            
            # ドメインチェック
            if parsed.netloc.lower() != 'r.gnavi.co.jp':
                return None
            
            path_parts = parsed.path.strip('/').split('/')
            
            if len(path_parts) >= 1 and path_parts[0]:
                store_id = path_parts[0]
                # 店舗IDの形式チェック（3-20文字の英数字）
                if re.match(r'^[a-zA-Z0-9]{3,20}$', store_id):
                    return f"{parsed.scheme}://{parsed.netloc}/{store_id}"
            
            return None
        except Exception:
            return None
    
    def get_store_list(self, prefecture, city, max_count, unlimited):
        """店舗一覧取得（最適化版・同一Excel保存）"""
        try:
            if not self.initialize_driver():
                raise Exception("ドライバー初期化失敗")
            
            # URL生成（最初のページ）
            search_url = self.prefecture_mapper.generate_search_url(prefecture, city, page=1)
            self.logger.info(f"検索URL: {search_url}")
            self.logger.info(f"検索エリア: {self.prefecture_mapper.get_area_display_name(prefecture, city)}")
            
            # ページアクセス
            self.driver.get(search_url)
            
            # 一覧ページ専用の軽量な読み込み待機
            if not self._wait_for_list_page_load():
                self.logger.warning("一覧ページの読み込み確認できませんでしたが続行します")
            
            # 現在のページを確認
            current_url = self.driver.current_url
            page_title = self.driver.title
            self.logger.info(f"ページ読み込み完了 - URL: {current_url}")
            self.logger.info(f"ページタイトル: {page_title}")
            
            # エラーページかどうかチェック
            if "404" in page_title or "エラー" in page_title or "見つかりません" in page_title:
                raise Exception(f"エラーページが表示されました: {page_title}")
            
            # ページごとの処理
            all_store_urls = []
            page_num = 1
            self.processed_urls.clear()
            consecutive_empty_pages = 0
            max_pages = 50 if unlimited else min(20, (max_count // 30) + 5)
            
            while len(all_store_urls) < (float('inf') if unlimited else max_count):
                # 進捗コールバック
                if self.callback:
                    self.callback({
                        'phase': 'listing',
                        'message': f'ページ {page_num} の店舗URL取得中...',
                        'progress': min((len(all_store_urls) / max_count) * 50, 50) if not unlimited else 0,
                        'current': len(all_store_urls),
                        'target': max_count if not unlimited else '無制限'
                    })
                
                self.logger.info(f"ページ {page_num} の店舗URL取得中...")
                page_store_urls = self._extract_store_urls_from_page()
                
                if not page_store_urls:
                    consecutive_empty_pages += 1
                    self.logger.warning(f"ページ {page_num} で店舗URLが見つかりません（連続{consecutive_empty_pages}回目）")
                    
                    if consecutive_empty_pages >= 3:
                        self.logger.warning("3ページ連続で店舗が見つからないため終了します")
                        break
                else:
                    consecutive_empty_pages = 0
                    
                    # 重複除去とベースURL取得
                    new_urls = []
                    for url in page_store_urls:
                        base_url = self.get_base_store_url(url)
                        if base_url not in self.processed_urls:
                            new_urls.append(base_url)
                            self.processed_urls.add(base_url)
                    
                    # 必要な分だけ追加
                    if not unlimited:
                        remaining = max_count - len(all_store_urls)
                        new_urls = new_urls[:remaining]
                    
                    all_store_urls.extend(new_urls)
                    self.logger.info(f"ページ {page_num}: {len(new_urls)}件取得 (累計: {len(all_store_urls)}件)")
                
                # 目標達成チェック
                if not unlimited and len(all_store_urls) >= max_count:
                    self.logger.info(f"目標件数に到達しました: {len(all_store_urls)}件")
                    break
                
                # 最大ページ数チェック
                if page_num >= max_pages:
                    self.logger.warning(f"最大ページ数({max_pages})に到達しました")
                    break
                
                # 10ページごとのメモリ解放処理
                if page_num % 10 == 0:
                    self._perform_memory_cleanup_light(page_num)
                
                # 次ページへ
                page_num += 1
                next_url = self.prefecture_mapper.generate_search_url(prefecture, city, page=page_num)
                
                self.logger.info(f"次ページへ移動: {next_url}")
                self.driver.get(next_url)
                
                # 一覧ページ専用の軽量待機
                self._wait_for_list_page_load()
                self.wait_with_cooltime()
            
            # 店舗リストを作成
            store_list = []
            for i, url in enumerate(all_store_urls, 1):
                # URLから店舗IDを抽出
                try:
                    parsed = urlparse(url)
                    store_id = parsed.path.strip('/').split('/')[0]
                    name = f"店舗ID: {store_id}"
                except:
                    name = f"店舗 {i}"
                
                store_list.append({
                    'name': name,
                    'url': url
                })
            
            self.logger.info(f"店舗一覧取得完了: {len(store_list)}件")
            return store_list
            
        except Exception as e:
            self.logger.error(f"店舗一覧取得エラー: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def _wait_for_list_page_load(self):
        """一覧ページ専用の軽量な読み込み待機"""
        try:
            self.logger.debug("一覧ページ読み込み待機開始")
            
            # 1. 基本的な読み込み待機（3秒で十分）
            try:
                WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                self.logger.warning("一覧ページの基本要素待機タイムアウト")
            
            # 2. 最小限のスクロール（1回のみ）
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
            
            # 3. 店舗リンクの存在確認（一覧ページ特有の要素）
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/r.gnavi.co.jp/']")
            
            if links:
                self.logger.debug(f"一覧ページ読み込み完了: {len(links)}個のリンク検出")
                return True
            
            # 4. フォールバック：もう少し待つ
            time.sleep(1)
            
            return True
            
        except Exception as e:
            self.logger.warning(f"一覧ページ読み込み待機エラー: {e}")
            return False
    
    def _save_urls_to_excel(self, urls, page_num, excel_path):
        """URLをExcelに保存（追記モード）"""
        try:
            # データフレーム作成
            df_new = pd.DataFrame({
                'ページ番号': [page_num] * len(urls),
                'URL': urls,
                '取得日時': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] * len(urls)
            })
            
            # ファイルが存在する場合は追記、なければ新規作成
            if excel_path.exists():
                # 既存データを読み込み
                df_existing = pd.read_excel(excel_path)
                # 結合
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                # 保存
                df_combined.to_excel(excel_path, index=False)
                self.logger.debug(f"Excel追記: {len(urls)}件 (合計: {len(df_combined)}件)")
            else:
                # 新規作成
                df_new.to_excel(excel_path, index=False)
                self.logger.debug(f"Excel新規作成: {len(urls)}件")
                
        except Exception as e:
            self.logger.error(f"Excel保存エラー: {e}")
            # エラー時はCSVで保存を試みる
            csv_path = excel_path.with_suffix('.csv')
            try:
                with open(csv_path, 'a', encoding='utf-8') as f:
                    for url in urls:
                        f.write(f"{page_num},{url},{datetime.now()}\n")
                self.logger.info(f"CSV代替保存成功: {csv_path}")
            except:
                pass
    
    def _load_urls_from_excel(self, excel_path):
        """Excelから全URLを読み込んで店舗リストを作成"""
        try:
            # Excelファイルを読み込み
            df = pd.read_excel(excel_path)
            
            store_list = []
            for idx, row in df.iterrows():
                url = row['URL']
                # URLから店舗IDを抽出
                try:
                    parsed = urlparse(url)
                    store_id = parsed.path.strip('/').split('/')[0]
                    name = f"店舗ID: {store_id}"
                except:
                    name = f"店舗 {idx + 1}"
                
                store_list.append({
                    'name': name,
                    'url': url
                })
            
            return store_list
            
        except Exception as e:
            self.logger.error(f"Excel読み込みエラー: {e}")
            # CSVファイルがあれば試す
            csv_path = excel_path.with_suffix('.csv')
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path, names=['page', 'url', 'datetime'])
                    return [{'name': f"店舗 {i+1}", 'url': url} 
                           for i, url in enumerate(df['url'].tolist())]
                except:
                    pass
            return []
    
    def _perform_memory_cleanup_light(self, page_num):
        """軽量版メモリ解放（一覧ページ用）"""
        try:
            self.logger.info(f"=== {page_num}ページ処理完了 - 軽量メモリ解放 ===")
            
            import gc
            
            # processed_urlsのサイズ制限
            if len(self.processed_urls) > 500:
                urls_list = list(self.processed_urls)
                self.processed_urls = set(urls_list[-500:])
                self.logger.debug(f"processed_urls制限: {len(urls_list)}件 → 500件")
            
            # ガベージコレクション
            gc.collect()
            
            # ブラウザキャッシュのクリア
            self.driver.execute_script("window.localStorage.clear();")
            
            self.logger.info("軽量メモリ解放完了")
            
        except Exception as e:
            self.logger.warning(f"軽量メモリ解放エラー: {e}")
    
    def _perform_memory_cleanup(self, page_num, prefecture, city):
        """10ページごとのメモリ解放処理"""
        try:
            self.logger.warning(f"=== {page_num}ページ処理完了 - メモリ解放処理開始 ===")
            
            # 1. メモリ使用状況を記録
            import gc
            import psutil
            
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            self.logger.info(f"メモリ解放前: {memory_before:.1f}MB")
            
            # 2. ブラウザのメモリをクリア
            try:
                # Cookieをクリア
                self.driver.delete_all_cookies()
                
                # ローカルストレージ・セッションストレージをクリア
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
                
                # ページを空白ページに移動（メモリ解放）
                self.driver.get("about:blank")
                time.sleep(2)
                
                # JavaScriptガベージコレクションを強制実行
                self.driver.execute_script("if (typeof gc === 'function') gc();")
                
            except Exception as e:
                self.logger.warning(f"ブラウザメモリクリアエラー: {e}")
            
            # 3. processed_urlsのサイズ制限（最新1000件のみ保持）
            if len(self.processed_urls) > 1000:
                # リストに変換して最新1000件を取得
                urls_list = list(self.processed_urls)
                self.processed_urls = set(urls_list[-1000:])
                self.logger.info(f"processed_urls制限: {len(urls_list)}件 → 1000件")
            
            # 4. Pythonのガベージコレクション実行
            gc.collect()
            gc.collect()  # 2回実行でより確実に
            
            # 5. メモリ使用状況を再確認
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_freed = memory_before - memory_after
            self.logger.info(f"メモリ解放後: {memory_after:.1f}MB (解放: {memory_freed:.1f}MB)")
            
            # 6. システムメモリの状況確認
            system_memory = psutil.virtual_memory()
            self.logger.info(f"システムメモリ使用率: {system_memory.percent:.1f}%")
            
            # 7. メモリ使用率が高い場合は追加対策
            if system_memory.percent > 80:
                self.logger.warning(f"システムメモリ使用率が高い({system_memory.percent:.1f}%) - ドライバー再起動を推奨")
                
                # 20ページごと、またはメモリ逼迫時はドライバー完全再起動
                if page_num % 20 == 0 or system_memory.percent > 85:
                    self.logger.warning("ドライバー完全再起動を実行")
                    self._restart_driver_completely(prefecture, city, page_num)
            
            # 8. 次のページ処理の準備（少し長めに待機）
            time.sleep(3)
            
            self.logger.info(f"=== メモリ解放処理完了 ===")
            
        except Exception as e:
            self.logger.error(f"メモリ解放処理エラー: {e}")
    
    def _restart_driver_completely(self, prefecture, city, next_page):
        """ドライバーの完全再起動"""
        try:
            self.logger.info("ドライバー完全再起動開始")
            
            # 現在のUser-Agent Indexを保持
            current_ua_index = self.ua_index
            
            # ドライバーを完全に終了
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            
            # 3秒待機（プロセス完全終了を待つ）
            time.sleep(3)
            
            # 新しいドライバーを作成
            self.ua_index = current_ua_index  # User-Agentを維持
            if not self.initialize_driver():
                raise Exception("ドライバー再初期化失敗")
            
            # 広告ブロックを再設定
            self._block_unnecessary_resources()
            
            # 次のページURLを生成して移動
            next_url = self.prefecture_mapper.generate_search_url(prefecture, city, page=next_page + 1)
            self.driver.get(next_url)
            
            self.logger.info("ドライバー完全再起動完了")
            
        except Exception as e:
            self.logger.error(f"ドライバー再起動エラー: {e}")
            raise
    
    def _extract_store_urls_from_page(self):
        """現在ページから店舗URL抽出"""
        try:
            # ページが完全に読み込まれているかを再確認
            time.sleep(1)
            
            # JavaScriptでページ内の全リンクを取得
            all_links = self.driver.execute_script("""
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(link => ({
                    href: link.href,
                    text: link.textContent.trim(),
                    title: link.getAttribute('title') || ''
                }));
            """)
            
            # 店舗URLをフィルタリング
            store_urls = []
            for link_data in all_links:
                url = link_data['href']
                
                if self.is_valid_store_url(url):
                    # URLを正規化（クエリパラメータ除去）
                    normalized_url = url.split('?')[0].rstrip('/')
                    store_urls.append(normalized_url)
            
            # 重複除去
            unique_urls = list(set(store_urls))
            
            return unique_urls
            
        except Exception as e:
            self.logger.error(f"店舗URL抽出エラー: {e}")
            return []
    
    def get_store_detail(self, url):
        """店舗詳細取得（最適化版）"""
        try:
            # driver の存在確認
            if self.driver is None:
                self.logger.error("Driver is None before creating extractor")
                return self._get_default_detail(url)
            
            # 早期エラーチェック
            if self._quick_error_check():
                self.logger.warning(f"エラーページ検出: {url}")
                return self._get_default_detail(url)
            
            # 60件前後での特別な待機
            if 58 <= self.stats['processed_stores'] <= 62:
                extra_wait = random.uniform(3, 5)
                self.logger.warning(f"60件境界付近での追加待機: {extra_wait:.1f}秒")
                time.sleep(extra_wait)
            
            # リトライ機能付きページアクセス
            success = self._get_with_retry(url)
            if not success:
                return self._get_default_detail(url)
            
            # 段階的コンテンツ読み込み
            self._wait_for_stepwise_content_load()
            
            # 複数要素を一度に取得（高速化）
            store_data = self._extract_all_data_at_once(url)
            
            if store_data:
                # 電話番号が取得できなかった場合の詳細デバッグ
                if store_data['電話番号'] == '-':
                    self.stats['phone_extraction_failures'] += 1
                    self.logger.warning(f"電話番号取得失敗 (累計: {self.stats['phone_extraction_failures']}件)")
                    self._debug_phone_extraction_failure(url)
                
                self.wait_with_cooltime()
                return store_data
            
            # フォールバック：従来の方法で取得
            from gurunavi_multi_approach_extractor import GurunaviMultiApproachExtractor
            extractor = GurunaviMultiApproachExtractor(self.driver, self.logger)
            detail = extractor.extract_store_data_multi(url)
            
            self.wait_with_cooltime()
            return detail
            
        except Exception as e:
            self.logger.error(f"店舗詳細取得エラー: {e}")
            return self._get_default_detail(url)
    
    def _get_with_retry(self, url, max_retries=2):
        """リトライ機能付きページアクセス"""
        for i in range(max_retries):
            try:
                self.driver.get(url)
                return True
            except TimeoutException:
                self.logger.warning(f"タイムアウト発生 (試行 {i+1}/{max_retries}): {url}")
                if i == 0:
                    # 初回失敗時は強制停止して再試行
                    try:
                        self.driver.execute_script("window.stop();")
                    except:
                        pass
                    time.sleep(1)
                else:
                    # 2回目失敗時はリフレッシュ
                    try:
                        self.driver.refresh()
                    except:
                        pass
            except Exception as e:
                self.logger.error(f"ページアクセスエラー: {e}")
                return False
        return False
    
    def _quick_error_check(self):
        """軽量なエラーチェック"""
        try:
            title = self.driver.title
            if any(word in title.lower() for word in ['404', 'error', 'not found', '見つかりません']):
                return True
        except:
            pass
        return False
    
    def _extract_all_data_at_once(self, url):
        """複数要素を一度のJavaScript実行で取得（高速化）"""
        try:
            result = self.driver.execute_script("""
                // 店舗名の取得
                let shopName = '-';
                const headerName = document.querySelector('#header-main-name a');
                if (headerName) {
                    shopName = headerName.innerText.trim();
                } else {
                    const h1 = document.querySelector('h1');
                    if (h1) shopName = h1.innerText.trim();
                }
                
                // 電話番号の取得
                let phone = '-';
                let phoneSource = 'none';
                
                // ヘッダーから優先的に取得
                const headerPhone = document.querySelector('#header-main-phone .number');
                if (headerPhone) {
                    phone = headerPhone.innerText.trim();
                    phoneSource = 'header';
                } else {
                    // その他の場所から探す
                    const phoneElements = document.querySelectorAll('.number, p.-blue, [class*="phone"], [class*="tel"]');
                    for (let elem of phoneElements) {
                        const text = elem.innerText.trim();
                        if (text && text.match(/\\d{2,4}[-\\s]?\\d{2,4}[-\\s]?\\d{3,4}/)) {
                            phone = text;
                            phoneSource = 'content';
                            break;
                        }
                    }
                }
                
                // エラーチェック
                const hasError = document.body.innerText.includes('404') || 
                                document.title.includes('エラー');
                
                return {
                    shopName: shopName,
                    phone: phone,
                    phoneSource: phoneSource,
                    hasError: hasError,
                    timestamp: new Date().toISOString()
                };
            """)
            
            if result and not result.get('hasError'):
                from datetime import datetime
                
                # 生データログ出力
                if result.get('phone') and result['phone'] != '-':
                    self.logger.info(f"電話番号取得成功 - ソース: {result.get('phoneSource')}, 値: {result['phone']}")
                
                # クリーニング処理
                cleaned_phone = self._clean_phone_number(result.get('phone', '-'))
                
                return {
                    'URL': url,
                    '店舗名': result.get('shopName', '-'),
                    '電話番号': cleaned_phone,
                    '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"一括データ取得エラー: {e}")
            return None
    
    def _extract_raw_phone_for_debug(self):
        """デバッグ用: 電話番号の生データを取得"""
        try:
            # 複数の方法で生データ取得を試みる
            
            # 方法1: JavaScriptで直接取得
            js_script = """
            // 電話番号要素を複数の方法で探す
            const selectors = [
                '.commonAccordion_content_item_desc.-blue',
                'p.-blue',
                '[class*="phone"]',
                '[class*="tel"]'
            ];
            
            for (let selector of selectors) {
                const elem = document.querySelector(selector);
                if (elem && elem.innerText) {
                    return {
                        selector: selector,
                        text: elem.innerText,
                        html: elem.innerHTML,
                        textContent: elem.textContent
                    };
                }
            }
            
            // ラベルベースで探す
            const items = document.querySelectorAll('.commonAccordion_content_item');
            for (let item of items) {
                const title = item.querySelector('.commonAccordion_content_item_title');
                if (title && title.innerText.includes('電話')) {
                    const desc = item.querySelector('.commonAccordion_content_item_desc');
                    if (desc) {
                        return {
                            selector: 'label-based',
                            text: desc.innerText,
                            html: desc.innerHTML,
                            textContent: desc.textContent
                        };
                    }
                }
            }
            
            return null;
            """
            
            result = self.driver.execute_script(js_script)
            
            if result:
                self.logger.debug(f"電話番号生データ取得成功 - セレクタ: {result.get('selector')}")
                return result.get('text', '')
            
            # 方法2: Seleniumで直接要素取得
            try:
                phone_elem = self.driver.find_element(By.CSS_SELECTOR, "p.-blue")
                if phone_elem:
                    return phone_elem.text
            except:
                pass
            
            return '-'
            
        except Exception as e:
            self.logger.debug(f"生データ取得エラー: {e}")
            return '-'
    
    def _debug_phone_extraction_failure(self, url):
        """電話番号取得失敗時のデバッグ情報出力"""
        try:
            self.logger.warning("=== 電話番号取得失敗デバッグ ===")
            self.logger.warning(f"URL: {url}")
            self.logger.warning(f"処理済み件数: {self.stats['processed_stores']}")
            
            # ページソースの一部を確認
            page_source = self.driver.page_source[:3000]
            if 'recaptcha' in page_source.lower():
                self.logger.warning("CAPTCHAの可能性あり")
            if '403' in page_source or '429' in page_source:
                self.logger.warning("レート制限の可能性あり")
            
            # 電話番号っぽいパターンが存在するか確認
            phone_pattern = r'\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,4}'
            matches = re.findall(phone_pattern, page_source)
            if matches:
                self.logger.warning(f"ページ内に電話番号パターン検出: {matches[:3]}")
            else:
                self.logger.warning("ページ内に電話番号パターンが見つかりません")
            
            self.logger.warning("=" * 40)
            
        except Exception as e:
            self.logger.debug(f"デバッグ情報出力エラー: {e}")
    
    def _get_default_detail(self, url):
        """デフォルトの店舗データ（4項目のみ）"""
        from datetime import datetime
        return {
            'URL': url,
            '店舗名': '取得失敗',
            '電話番号': '-',
            '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _clean_phone_number(self, raw_text):
        """電話番号クリーニング処理"""
        if not raw_text or raw_text == '-':
            return raw_text
        
        try:
            import re
            
            # 改行で分割して最初の行を取得
            lines = raw_text.strip().split('\n')
            first_line = lines[0].strip() if lines else raw_text.strip()
            
            # 電話番号パターンにマッチする部分を抽出
            patterns = [
                r'(0\d{1,4}-\d{1,4}-\d{3,4})',
                r'(0\d{9,10})',
                r'(050-\d{4}-\d{4})',
                r'(0120-\d{3}-\d{3})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, first_line)
                if match:
                    phone = match.group(1)
                    self.logger.debug(f"電話番号クリーニング: '{raw_text[:30]}...' → '{phone}'")
                    return phone
            
            # マッチしない場合、不要な文言を除外
            if any(kw in first_line for kw in ['ぐるなび', '見た', 'スムーズ', '問合']):
                numbers = re.findall(r'[\d-]+', first_line)
                if numbers:
                    phone = numbers[0]
                    digits_only = re.sub(r'[^\d]', '', phone)
                    if 10 <= len(digits_only) <= 11:
                        return phone
            
            return first_line
            
        except Exception as e:
            self.logger.warning(f"電話番号クリーニングエラー: {e}")
            return raw_text
    
    def _detect_captcha(self):
        """CAPTCHA検知"""
        try:
            captcha_indicators = [
                "recaptcha",
                "captcha",
                "robot",
                "verification",
                "security check"
            ]
            
            page_source = self.driver.page_source.lower()
            return any(indicator in page_source for indicator in captcha_indicators)
            
        except Exception:
            return False
    
    def _detect_ip_restriction(self):
        """IP制限検知"""
        try:
            # HTTPエラーコードチェック
            if "403" in self.driver.title or "429" in self.driver.title:
                return True
            
            # 一般的な制限メッセージ
            restriction_messages = [
                "access denied",
                "too many requests",
                "rate limit",
                "blocked",
                "アクセスが制限",
                "接続できません"
            ]
            
            page_source = self.driver.page_source.lower()
            return any(msg in page_source for msg in restriction_messages)
            
        except Exception:
            return False
    
    def _is_valid_phone_number(self, phone_str):
        """電話番号の妥当性チェック"""
        if not phone_str:
            return False
        
        # 数字とハイフンのみ抽出
        cleaned = re.sub(r'[^\d-]', '', str(phone_str))
        
        # 10-11桁の数字があるかチェック
        digits_only = cleaned.replace('-', '')
        return 10 <= len(digits_only) <= 11
    
    def _update_estimated_completion(self):
        """完了予想時間の更新"""
        if not self.stats['start_time'] or self.stats['total_stores'] == 0:
            return
        
        elapsed = time.time() - self.stats['start_time']
        if self.stats['processed_stores'] > 0:
            avg_time_per_store = elapsed / self.stats['processed_stores']
            remaining_stores = self.stats['total_stores'] - self.stats['processed_stores']
            estimated_remaining = remaining_stores * avg_time_per_store
            
            self.stats['estimated_completion'] = datetime.now() + timedelta(seconds=estimated_remaining)
    
    def get_processing_stats(self):
        """処理統計情報取得"""
        elapsed = 0
        if self.stats['start_time']:
            elapsed = time.time() - self.stats['start_time']
        
        return {
            '経過時間': f"{elapsed/60:.1f}分",
            '処理済み店舗数': self.stats['processed_stores'],
            '成功店舗数': self.stats['successful_stores'],
            '失敗店舗数': self.stats['failed_stores'],
            '電話番号取得失敗': self.stats['phone_extraction_failures'],
            'UA切り替え回数': self.stats['ua_switches'],
            'CAPTCHA遭遇回数': self.stats['captcha_encounters'],
            'IP制限遭遇回数': self.stats['ip_restrictions'],
            '平均処理時間/店舗': f"{elapsed/max(self.stats['processed_stores'], 1):.1f}秒",
            '完了予想時刻': self.stats['estimated_completion'].strftime('%H:%M:%S') if self.stats['estimated_completion'] else 'N/A',
            '現在時間帯倍率': f"{self.time_multiplier}x"
        }
    
    def start_processing(self, store_list, search_params):
        """メイン処理開始（URLリストを店舗詳細シートに直接保存）"""
        self.stats['start_time'] = time.time()
        self.stats['total_stores'] = len(store_list)
        self.current_results = []
        
        self.logger.info(f"=== 処理開始 (高速化・長時間対応版) ===")
        self.logger.info(f"対象店舗数: {len(store_list)}")
        self.logger.info(f"時間帯倍率: {self.time_multiplier}x")
        self.logger.info(f"UA切り替え間隔: {self.config['ua_switch_interval']}件")
        self.logger.info(f"予想処理時間: {len(store_list) * 8 * self.time_multiplier / 60:.1f}分")
        
        # 出力ファイルパスを決定
        save_dir = Path(search_params['save_path'])
        save_dir.mkdir(parents=True, exist_ok=True)
        filename = search_params['filename']
        if not filename.endswith('.xlsx'):
            filename += '.xlsx'
        self.excel_file_path = save_dir / filename
        
        # 最初にURLのみを店舗詳細シートに保存
        self._initialize_excel_with_urls(store_list)
        
        # メモリ監視の初期化
        self._init_memory_monitoring()
        
        if not self.initialize_driver():
            raise Exception("ドライバー初期化失敗")
        
        try:
            for idx, store in enumerate(store_list, 1):
                if self.callback:
                    # 進捗情報に統計を含める
                    progress_data = {
                        'phase': 'detail',
                        'message': f'店舗詳細取得中 ({idx}/{len(store_list)}): {store["name"]}',
                        'progress': (idx / len(store_list)) * 100,
                        'current': idx,
                        'total': len(store_list),
                        'stats': self.get_processing_stats()
                    }
                    self.callback(progress_data)
                
                # 店舗詳細取得
                detail = self.get_store_detail(store['url'])
                
                # 詳細データをExcelの該当行に更新
                self._update_excel_row(idx, detail)
                
                # 統計更新
                self.stats['processed_stores'] = idx
                if detail['店舗名'] != '取得失敗' and detail['店舗名'] != '-':
                    self.stats['successful_stores'] += 1
                else:
                    self.stats['failed_stores'] += 1
                
                # 成功率更新
                self.stats['success_rate'] = self.stats['successful_stores'] / self.stats['processed_stores']
                
                self._update_estimated_completion()
                
                # メモリチェック（50件ごと）
                if idx % 50 == 0:
                    self._check_memory_usage()
                
                # User-Agent切り替えチェック（改善版）
                ua_interval = self.config.get('ua_switch_interval', 30)
                
                # 60件境界での特別処理
                if idx == 60:
                    self.logger.warning("=== 60件処理完了 - 特別なUA切り替え実行 ===")
                    try:
                        self.switch_user_agent()
                    except Exception as e:
                        self.logger.error(f"60件境界でのUA切り替えエラー: {e}")
                        # エラーでも続行を試みる
                        time.sleep(10)
                
                # 通常のUA切り替え（60件境界以外）
                elif idx % ua_interval == 0 and idx < len(store_list) and idx != 60:
                    self.logger.info(f"定期UA切り替え実行 ({idx}件処理完了)")
                    try:
                        self.switch_user_agent()
                    except Exception as e:
                        self.logger.error(f"UA切り替えエラー: {e}")
                        break
            
            # 最終統計出力
            final_stats = self.get_processing_stats()
            self.logger.info("=== 処理完了統計 ===")
            for key, value in final_stats.items():
                self.logger.info(f"{key}: {value}")
            
            # 処理統計をExcelに保存
            self._save_stats_to_excel()
            
            # 最終的なデータを読み込んで返す
            df = pd.read_excel(self.excel_file_path, sheet_name='店舗詳細')
            self.current_results = df.to_dict('records')
            
            return self.current_results
            
        finally:
            self.cleanup()
    
    def _initialize_excel_with_urls(self, store_list):
        """ExcelファイルをURL一覧で初期化（店舗詳細シートに直接）"""
        try:
            self.logger.info(f"ExcelファイルをURL一覧で初期化: {self.excel_file_path}")
            
            # URL一覧のデータフレーム作成（最初はURLのみ、他は空白）
            data = []
            for store in store_list:
                data.append({
                    'URL': store['url'],
                    '店舗名': '',
                    '電話番号': '',
                    '取得日時': ''
                })
            
            df = pd.DataFrame(data)
            
            # Excelに保存
            with pd.ExcelWriter(self.excel_file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='店舗詳細', index=False)
                
                # 列幅調整
                worksheet = writer.sheets['店舗詳細']
                worksheet.column_dimensions['A'].width = 60  # URL
                worksheet.column_dimensions['B'].width = 30  # 店舗名
                worksheet.column_dimensions['C'].width = 15  # 電話番号
                worksheet.column_dimensions['D'].width = 20  # 取得日時
            
            self.logger.info(f"URL一覧で初期化完了: {len(store_list)}件")
            
        except Exception as e:
            self.logger.error(f"Excel初期化エラー: {e}")
    
    def _update_excel_row(self, row_number, detail):
        """Excelの特定行を更新（詳細データで上書き）"""
        try:
            from openpyxl import load_workbook
            
            # 既存のワークブックを開く
            book = load_workbook(self.excel_file_path)
            sheet = book['店舗詳細']
            
            # 行番号は2から始まる（1行目はヘッダー）
            excel_row = row_number + 1
            
            # データを更新（A列のURLはそのまま、B～D列を更新）
            sheet.cell(row=excel_row, column=2, value=detail.get('店舗名', ''))      # B列: 店舗名
            sheet.cell(row=excel_row, column=3, value=detail.get('電話番号', ''))    # C列: 電話番号
            sheet.cell(row=excel_row, column=4, value=detail.get('取得日時', ''))    # D列: 取得日時
            
            # 保存
            book.save(self.excel_file_path)
            book.close()
            
            # ログ（10件ごと）
            if row_number % 10 == 0:
                status = "成功" if detail.get('店舗名') not in ['', '-', '取得失敗'] else "失敗"
                self.logger.info(f"Excel更新: {row_number}行目 - {status}")
            
        except Exception as e:
            self.logger.error(f"Excel行更新エラー (行{row_number}): {e}")
    
    def _save_stats_to_excel(self):
        """処理統計を同じExcelの「処理統計」シートに保存"""
        try:
            from openpyxl import load_workbook
            
            stats = self.get_processing_stats()
            stats_data = []
            for key, value in stats.items():
                stats_data.append({'項目': key, '値': str(value)})
            
            df_stats = pd.DataFrame(stats_data)
            
            # 既存のワークブックを開く
            if self.excel_file_path.exists():
                book = load_workbook(self.excel_file_path)
                
                # 処理統計シートが存在する場合は削除
                if '処理統計' in book.sheetnames:
                    del book['処理統計']
                
                # ワークブックを保存して閉じる
                book.save(self.excel_file_path)
                book.close()
                
                # 改めてExcelWriterで開いて統計シートを追加
                with pd.ExcelWriter(self.excel_file_path, engine='openpyxl', mode='a') as writer:
                    df_stats.to_excel(writer, sheet_name='処理統計', index=False)
                    
                    # 列幅調整
                    worksheet = writer.sheets['処理統計']
                    worksheet.column_dimensions['A'].width = 25
                    worksheet.column_dimensions['B'].width = 30
            
            self.logger.info("処理統計を保存しました")
            
        except Exception as e:
            self.logger.warning(f"処理統計保存エラー: {e}")
    
    def _init_memory_monitoring(self):
        """メモリ監視の初期化"""
        try:
            import psutil
            import gc
            
            # ガベージコレクションを最適化
            gc.collect()
            gc.set_threshold(700, 10, 10)  # より積極的なGC
            
            self.process = psutil.Process()
            initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            self.logger.info(f"初期メモリ使用量: {initial_memory:.1f}MB")
        except Exception as e:
            self.logger.debug(f"メモリ監視初期化エラー: {e}")
    
    def _check_memory_usage(self):
        """メモリ使用量チェック"""
        try:
            import psutil
            import gc
            
            # プロセスメモリ
            process_memory = self.process.memory_percent()
            # システム全体
            system_memory = psutil.virtual_memory().percent
            
            self.logger.debug(f"メモリ使用率 - プロセス: {process_memory:.1f}%, システム: {system_memory:.1f}%")
            
            # プロセスメモリが5%超えたらGC実行
            if process_memory > 5.0:
                gc.collect()
                self.logger.info("ガベージコレクション実行")
            
            # システムメモリが80%超えたら警告
            if system_memory > 80:
                self.logger.warning(f"システムメモリ使用率が高い: {system_memory:.1f}%")
                # 必要に応じてドライバー再起動を検討
                if system_memory > 85 and self.stats['processed_stores'] % 30 == 0:
                    self.logger.warning("メモリ逼迫のためドライバー再起動を推奨")
        
        except Exception as e:
            self.logger.debug(f"メモリチェックエラー: {e}")
    
    def save_results_incremental(self, detail_data, save_path, filename):
        """逐次保存（使用しない - 直接Excel更新に変更）"""
        pass
    
    def _do_save(self, results, save_path, filename):
        """実際の保存処理（使用しない - 直接Excel更新に変更）"""
        pass
    
    def save_results(self, results, save_path, filename):
        """最終結果をExcelに保存（既存ファイルに統合）"""
        try:
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            full_path = save_dir / filename
            
            # 既存ファイルがある場合は更新、なければ新規作成
            if full_path.exists():
                # 既存ファイルの更新
                from openpyxl import load_workbook
                book = load_workbook(full_path)
                
                with pd.ExcelWriter(full_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    writer.book = book
                    
                    # 店舗詳細シートを更新
                    df = pd.DataFrame(results)
                    df.to_excel(writer, sheet_name='店舗詳細', index=False)
                    
                    # 統計シートも更新
                    if hasattr(self, 'get_processing_stats'):
                        stats_df = pd.DataFrame([self.get_processing_stats()]).T
                        stats_df.columns = ['値']
                        stats_df.to_excel(writer, sheet_name='処理統計')
                    
                    # 列幅調整
                    for sheet_name in ['店舗詳細', '処理統計']:
                        if sheet_name in writer.sheets:
                            worksheet = writer.sheets[sheet_name]
                            for column in worksheet.columns:
                                max_length = 0
                                column_letter = column[0].column_letter
                                for cell in column:
                                    try:
                                        if len(str(cell.value)) > max_length:
                                            max_length = len(str(cell.value))
                                    except:
                                        pass
                                adjusted_width = min(max_length + 2, 50)
                                worksheet.column_dimensions[column_letter].width = adjusted_width
            else:
                # 新規作成
                with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
                    df = pd.DataFrame(results)
                    df.to_excel(writer, sheet_name='店舗詳細', index=False)
                    
                    # 統計シート追加
                    if hasattr(self, 'get_processing_stats'):
                        stats_df = pd.DataFrame([self.get_processing_stats()]).T
                        stats_df.columns = ['値']
                        stats_df.to_excel(writer, sheet_name='処理統計')
            
            self.logger.info(f"最終結果保存: {full_path}")
            
        except Exception as e:
            self.logger.error(f"結果保存エラー: {e}")
            raise