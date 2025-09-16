"""
現実的処理時間対応スクレイピングエンジン
段階的動的生成対応版（スクロール誘発 + ネットワーク完了検知）
"""

import time
import random
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from urllib.parse import urlparse

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
    """段階的動的生成対応スクレイピングエンジンクラス"""
    
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
            'estimated_completion': None
        }
        
        # 時間帯別速度調整
        self.time_multiplier = self._get_time_multiplier()
    
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
        """ドライバー初期化"""
        try:
            user_agent = self.config['user_agents'][self.ua_index]
            self.driver = self.chrome_manager.create_driver(
                headless=True,
                user_agent=user_agent
            )
            
            # 段階的読み込み対応のタイムアウト設定
            self.driver.implicitly_wait(8)
            self.driver.set_page_load_timeout(25)
            self.driver.set_script_timeout(20)
            
            self.logger.info(f"ドライバー初期化完了 (UA: {self.ua_index}) - 段階的読み込み対応")
            return True
        except Exception as e:
            self.logger.error(f"ドライバー初期化エラー: {e}")
            return False
    
    def cleanup(self):
        """クリーンアップ"""
        if self.driver:
            self.chrome_manager.cleanup_driver(self.driver)
            self.driver = None
    
    def switch_user_agent(self):
        """User-Agent切り替え（統計追跡付き）"""
        try:
            old_ua = self.ua_index
            self.ua_index = (self.ua_index + 1) % len(self.config['user_agents'])
            self.stats['ua_switches'] += 1
            
            # 切り替え前に少し待機
            time.sleep(2)
            
            self.cleanup()
            if self.initialize_driver():
                self.logger.info(f"User-Agent切り替え完了: {old_ua} → {self.ua_index}")
                # 切り替え後の追加待機
                time.sleep(3)
            else:
                raise Exception("ドライバー再初期化失敗")
            
        except Exception as e:
            self.logger.error(f"User-Agent切り替えエラー: {e}")
            raise
    
    def wait_with_cooltime(self):
        """安全なクールタイム待機（時間帯考慮）"""
        base_min = self.config['cooltime_min']
        base_max = self.config['cooltime_max']
        
        # 時間帯による調整
        adjusted_min = base_min * self.time_multiplier
        adjusted_max = base_max * self.time_multiplier
        
        cooltime = random.uniform(adjusted_min, adjusted_max)
        
        self.logger.debug(f"クールタイム待機: {cooltime:.1f}秒 (倍率: {self.time_multiplier})")
        time.sleep(cooltime)
    
    def _trigger_stepwise_loading(self):
        """段階的スクロールによるLazy Loading誘発"""
        try:
            self.logger.debug("段階的読み込み誘発開始")
            
            # Phase 1: 基本DOM読み込み確認
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(1)
            
            # Phase 2: 段階的スクロールでコンテンツ読み込み誘発
            scroll_positions = [0, 200, 500, 800, 1100, 1400, 800, 400, 0]
            
            for i, position in enumerate(scroll_positions):
                self.logger.debug(f"スクロール {i+1}/{len(scroll_positions)}: {position}px")
                self.driver.execute_script(f"window.scrollTo(0, {position});")
                time.sleep(0.8)  # 短時間で効率的に
                
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
        """AJAX/Fetch完了の効率的検知"""
        try:
            self.logger.debug("ネットワーク完了待機開始")
            
            # ネットワークアクティビティ監視スクリプト（軽量版）
            network_script = """
            const controller = new AbortController();
            const signal = controller.signal;
            
            let pendingRequests = 0;
            const startTime = Date.now();
            const maxWaitTime = 8000; // 8秒でタイムアウト
            
            // Fetch監視（軽量）
            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                pendingRequests++;
                return originalFetch.apply(this, args).finally(() => {
                    pendingRequests--;
                });
            };
            
            // XMLHttpRequest監視（軽量）
            const OriginalXHR = window.XMLHttpRequest;
            const originalSend = OriginalXHR.prototype.send;
            OriginalXHR.prototype.send = function(...args) {
                pendingRequests++;
                this.addEventListener('loadend', () => pendingRequests--);
                return originalSend.apply(this, args);
            };
            
            // 非同期チェック
            return new Promise((resolve) => {
                const checkNetwork = () => {
                    const elapsed = Date.now() - startTime;
                    
                    if (elapsed > maxWaitTime) {
                        resolve({completed: false, reason: 'timeout', elapsed: elapsed});
                        return;
                    }
                    
                    if (pendingRequests === 0) {
                        // 0.5秒間アイドル状態が続いたら完了とみなす
                        setTimeout(() => {
                            if (pendingRequests === 0) {
                                resolve({completed: true, reason: 'idle', elapsed: elapsed});
                            } else {
                                setTimeout(checkNetwork, 200);
                            }
                        }, 500);
                    } else {
                        setTimeout(checkNetwork, 200);
                    }
                };
                
                // 初回チェック
                setTimeout(checkNetwork, 100);
            });
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
                # フォールバック: 基本待機
                time.sleep(3)
                return False
                
        except Exception as e:
            self.logger.warning(f"ネットワーク完了待機エラー: {e}")
            return False
    
    def _wait_for_stepwise_content_load(self):
        """段階的コンテンツ読み込み完了待機"""
        try:
            self.logger.debug("段階的コンテンツ読み込み待機開始")
            
            # Step 1: 段階的スクロール誘発
            scroll_success = self._trigger_stepwise_loading()
            
            # Step 2: ネットワーク完了待機
            network_success = self._wait_for_network_completion()
            
            # Step 3: 最終安定化待機
            time.sleep(1.5)
            
            # Step 4: 結果検証
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
        """店舗一覧取得（段階的読み込み対応）"""
        try:
            if not self.initialize_driver():
                raise Exception("ドライバー初期化失敗")
            
            # URL生成
            search_url = self.prefecture_mapper.generate_search_url(prefecture, city)
            self.logger.info(f"検索URL: {search_url}")
            
            # ページアクセス
            self.driver.get(search_url)
            
            # 段階的コンテンツ読み込み完了待機
            if not self._wait_for_stepwise_content_load():
                self.logger.warning("段階的読み込み完了を確認できませんでしたが処理を続行します")
            
            # 現在のページを確認
            current_url = self.driver.current_url
            page_title = self.driver.title
            self.logger.info(f"ページ読み込み完了 - URL: {current_url}")
            self.logger.info(f"ページタイトル: {page_title}")
            
            # エラーページかどうかチェック
            if "404" in page_title or "エラー" in page_title or "見つかりません" in page_title:
                raise Exception(f"エラーページが表示されました: {page_title}")
            
            # 店舗URL収集
            all_store_urls = []
            page_num = 1
            self.processed_urls.clear()
            consecutive_empty_pages = 0
            max_pages = 50 if unlimited else min(20, (max_count // 20) + 5)
            
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
                    
                    # 3ページ連続で見つからない場合は終了
                    if consecutive_empty_pages >= 3:
                        self.logger.warning("3ページ連続で店舗が見つからないため終了します")
                        break
                else:
                    consecutive_empty_pages = 0
                    
                    # 新しいURLのみ追加（重複除去）
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
                
                # 次ページへ
                if not self._go_to_next_page():
                    self.logger.info("次ページがありません")
                    break
                
                page_num += 1
                self.wait_with_cooltime()
            
            # 結果を店舗情報形式に変換
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
    
    def _go_to_next_page(self):
        """次ページへ移動（段階的読み込み対応）"""
        try:
            # 次ページボタンの候補セレクタ
            next_selectors = [
                "a.next",
                ".pagination .next a",
                ".pagination__next a",
                "[class*='next'] a",
                "a[rel='next']",
                ".pager-next a",
                ".paging-next a",
                "a[title*='次']",
                "a[title*='Next']"
            ]
            
            for selector in next_selectors:
                try:
                    next_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for next_element in next_elements:
                        if next_element.is_displayed() and next_element.is_enabled():
                            # 次ページボタンをクリック前にスクロール
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", next_element)
                            time.sleep(0.5)
                            
                            # クリック
                            self.driver.execute_script("arguments[0].click();", next_element)
                            
                            # ページ遷移を待つ
                            time.sleep(2)
                            
                            # 段階的読み込み完了を待つ
                            self._wait_for_stepwise_content_load()
                            
                            return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.warning(f"次ページ移動エラー: {e}")
            return False
    
    def get_store_detail(self, url):
        """段階的動的生成対応店舗詳細取得"""
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                self.access_count += 1
                self.stats['processed_stores'] += 1
                self._update_estimated_completion()
                
                self.logger.info(f"店舗詳細取得開始 ({attempt + 1}/{max_retries}): {url}")
                
                # ページアクセス
                start_time = time.time()
                self.driver.get(url)
                
                # 段階的コンテンツ読み込み完了待機
                stepwise_loaded = self._wait_for_stepwise_content_load()
                
                if not stepwise_loaded:
                    self.logger.warning("段階的読み込み確認できませんが処理続行")
                
                # CAPTCHA・IP制限チェック
                if self._detect_captcha():
                    self.stats['captcha_encounters'] += 1
                    self.logger.warning("CAPTCHA検知 - 待機中")
                    time.sleep(self.config.get('captcha_delay', 30))
                    continue
                    
                if self._detect_ip_restriction():
                    self.stats['ip_restrictions'] += 1
                    self.logger.warning("IP制限検知 - 長時間待機")
                    time.sleep(self.config.get('ip_limit_delay', 60))
                    continue
                
                # 店舗詳細データ抽出
                detail = self._extract_gurunavi_store_data(url)
                
                processing_time = time.time() - start_time
                self.logger.info(f"店舗詳細取得完了: {detail.get('店舗名', 'Unknown')} ({processing_time:.1f}秒)")
                
                self.stats['successful_stores'] += 1
                self.wait_with_cooltime()
                
                return detail
                
            except Exception as e:
                self.logger.warning(f"店舗詳細取得エラー (試行{attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    retry_delay = self.config.get('retry_delay', 5) * self.time_multiplier
                    time.sleep(retry_delay)
                    
                    if attempt == max_retries - 2:
                        try:
                            self.switch_user_agent()
                        except:
                            self.cleanup()
                            if not self.initialize_driver():
                                break
                else:
                    self.stats['failed_stores'] += 1
        
        # 失敗時のデフォルトデータ
        self.logger.error(f"店舗詳細取得最終失敗: {url}")
        return self._get_default_detail(url)
    
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
    
    def _extract_gurunavi_store_data(self, url):
        """ぐるなび店舗データ抽出（段階的生成対応）"""
        try:
            # 基本情報の初期化
            detail = {
                'URL': url,
                '店舗名': '-',
                '電話番号': '-',
                '住所': '-',
                'ジャンル': '-',
                '営業時間': '-',
                '定休日': '-',
                'クレジットカード': '-',
                '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 段階的にデータ抽出（各項目で軽い再確認）
            detail['店舗名'] = self._extract_gurunavi_shop_name()
            detail['電話番号'] = self._extract_gurunavi_phone_number()
            detail['住所'] = self._extract_gurunavi_address()
            detail['ジャンル'] = self._extract_gurunavi_genre()
            detail['営業時間'] = self._extract_gurunavi_business_hours()
            detail['定休日'] = self._extract_gurunavi_holiday()
            detail['クレジットカード'] = self._extract_gurunavi_credit_card()
            
            return detail
            
        except Exception as e:
            self.logger.error(f"ぐるなびデータ抽出エラー: {e}")
            return self._get_default_detail(url)

    def _extract_gurunavi_shop_name(self):
        """ぐるなび店舗名抽出（段階的生成対応）"""
        selectors = [
            "#info-name",
            ".fn.org.summary",
            "#info-table .fn",
            "h1",
            ".shop-name",
            ".restaurant-name"
        ]
        
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.text.strip():
                    name = element.text.strip()
                    self.logger.debug(f"店舗名取得成功: {selector} = {name}")
                    return name
            except (NoSuchElementException, Exception):
                continue
        
        # メタタグからの取得
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, "meta[property='og:title']")
            content = element.get_attribute("content")
            if content and content.strip():
                name = content.split(' - ')[0].split('｜')[0].strip()
                if name and name != 'ぐるなび':
                    self.logger.debug(f"店舗名取得成功: メタタグ = {name}")
                    return name
        except:
            pass
        
        # titleタグから
        try:
            title = self.driver.title
            if title and title.strip():
                name = title.split(' - ')[0].split('｜')[0].strip()
                if name and name != 'ぐるなび':
                    self.logger.debug(f"店舗名取得成功: title = {name}")
                    return name
        except:
            pass
        
        self.logger.warning("店舗名の取得に失敗しました")
        return '-'

    def _extract_gurunavi_phone_number(self):
        """ぐるなび電話番号抽出（段階的生成対応）"""
        try:
            # 優先順位に基づく抽出
            phone_selectors = [
                "#info-phone .number",
                ".number",
                "#info-phone td span",
                "#info-phone td li",
            ]
            
            for selector in phone_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and self._is_valid_phone_number(text):
                            self.logger.debug(f"電話番号取得成功: {selector} = {text}")
                            return text
                except:
                    continue
            
            # tel:リンクからの取得
            try:
                tel_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href^='tel:']")
                for tel_element in tel_elements:
                    href = tel_element.get_attribute("href")
                    if href:
                        phone = href.replace("tel:", "").strip()
                        if self._is_valid_phone_number(phone):
                            self.logger.debug(f"電話番号取得成功: tel:リンク = {phone}")
                            return phone
            except:
                pass
            
            # 電話番号行からの正規表現抽出
            try:
                phone_row = self.driver.find_element(By.CSS_SELECTOR, "#info-phone td")
                text = phone_row.text
                phone_match = re.search(r'(\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,4})', text)
                if phone_match and self._is_valid_phone_number(phone_match.group(1)):
                    phone = phone_match.group(1)
                    self.logger.debug(f"電話番号取得成功: 正規表現 = {phone}")
                    return phone
            except:
                pass
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"電話番号抽出エラー: {e}")
            return '-'

    def _extract_gurunavi_address(self):
        """ぐるなび住所抽出（段階的生成対応）"""
        selectors = [
            ".adr .region",
            ".region",
            ".adr",
            ".adr p",
        ]
        
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.text.strip():
                    address = element.text.strip()
                    # 郵便番号を除去
                    address = re.sub(r'〒\d{3}-\d{4}\s*', '', address)
                    if address:
                        self.logger.debug(f"住所取得成功: {selector} = {address}")
                        return address
            except:
                continue
        
        # テーブル行からの直接抽出
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "#info-table tr")
            for row in rows:
                try:
                    th = row.find_element(By.TAG_NAME, "th")
                    if th and "住所" in th.text:
                        td = row.find_element(By.TAG_NAME, "td")
                        if td:
                            address = td.text.strip()
                            address = re.sub(r'〒\d{3}-\d{4}\s*', '', address)
                            if address:
                                self.logger.debug(f"住所取得成功: テーブル行 = {address}")
                                return address
                except:
                    continue
        except:
            pass
        
        self.logger.warning("住所の取得に失敗しました")
        return '-'

    def _extract_gurunavi_genre(self):
        """ぐるなびジャンル抽出（段階的生成対応）"""
        try:
            # "お店のウリ" から抽出
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "#info-table-service tr")
                for row in rows:
                    try:
                        th = row.find_element(By.TAG_NAME, "th")
                        if th and "お店のウリ" in th.text:
                            td = row.find_element(By.TAG_NAME, "td")
                            li_elements = td.find_elements(By.TAG_NAME, "li")
                            if li_elements:
                                genres = [li.text.strip() for li in li_elements if li.text.strip()]
                                if genres:
                                    genre_text = "、".join(genres)
                                    self.logger.debug(f"ジャンル取得成功: お店のウリ = {genre_text}")
                                    return genre_text
                    except:
                        continue
            except:
                pass
            
            # メニューのサービスから抽出
            try:
                service_rows = self.driver.find_elements(By.CSS_SELECTOR, "#info-table-service tr")
                for row in service_rows:
                    try:
                        th = row.find_element(By.TAG_NAME, "th")
                        if th and "メニューのサービス" in th.text:
                            td = row.find_element(By.TAG_NAME, "td")
                            if td:
                                genre_text = td.text.strip()
                                if genre_text:
                                    self.logger.debug(f"ジャンル取得成功: メニューのサービス = {genre_text}")
                                    return genre_text
                    except:
                        continue
            except:
                pass
            
            # その他のカテゴリ情報
            category_selectors = [
                ".category",
                ".breadcrumb a",
                "[class*='category']",
                "[class*='genre']"
            ]
            
            for selector in category_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and text not in ['ホーム', 'トップ', 'ぐるなび']:
                            self.logger.debug(f"ジャンル取得成功: {selector} = {text}")
                            return text
                except:
                    continue
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"ジャンル抽出エラー: {e}")
            return '-'

    def _extract_gurunavi_business_hours(self):
        """ぐるなび営業時間抽出（段階的生成対応）"""
        try:
            selectors = [
                "#info-open td div",
                "#info-open td",
                "#info-open",
            ]
            
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element:
                        hours_text = element.text.strip()
                        if hours_text and "営業時間" not in hours_text:
                            hours_text = hours_text.replace('\n', ' ')
                            hours_text = ' '.join(hours_text.split())
                            if hours_text:
                                self.logger.debug(f"営業時間取得成功: {selector} = {hours_text}")
                                return hours_text
                except:
                    continue
            
            # テーブル行から直接検索
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "#info-table tr")
                for row in rows:
                    try:
                        th = row.find_element(By.TAG_NAME, "th")
                        if th and "営業時間" in th.text:
                            td = row.find_element(By.TAG_NAME, "td")
                            if td:
                                hours_text = td.text.strip()
                                if hours_text:
                                    hours_text = hours_text.replace('\n', ' ')
                                    hours_text = ' '.join(hours_text.split())
                                    self.logger.debug(f"営業時間取得成功: テーブル行 = {hours_text}")
                                    return hours_text
                    except:
                        continue
            except:
                pass
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"営業時間抽出エラー: {e}")
            return '-'

    def _extract_gurunavi_holiday(self):
        """ぐるなび定休日抽出（段階的生成対応）"""
        try:
            selectors = [
                "#info-holiday td li",
                "#info-holiday td ul li",
                "#info-holiday td",
                "#info-holiday",
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        holiday_list = []
                        for element in elements:
                            text = element.text.strip()
                            if text and "定休日" not in text:
                                holiday_list.append(text)
                        
                        if holiday_list:
                            holiday_text = "、".join(holiday_list)
                            self.logger.debug(f"定休日取得成功: {selector} = {holiday_text}")
                            return holiday_text
                except:
                    continue
            
            # テーブル行から直接検索
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "#info-table tr")
                for row in rows:
                    try:
                        th = row.find_element(By.TAG_NAME, "th")
                        if th and "定休日" in th.text:
                            td = row.find_element(By.TAG_NAME, "td")
                            if td:
                                holiday_text = td.text.strip()
                                if holiday_text:
                                    self.logger.debug(f"定休日取得成功: テーブル行 = {holiday_text}")
                                    return holiday_text
                    except:
                        continue
            except:
                pass
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"定休日抽出エラー: {e}")
            return '-'

    def _extract_gurunavi_credit_card(self):
        """ぐるなびクレジットカード情報抽出（段階的生成対応）"""
        try:
            search_terms = [
                "クレジットカード",
                "カード",
                "支払い",
                "決済",
                "VISA",
                "MasterCard",
                "JCB",
                "AMEX",
                "American Express"
            ]
            
            # テーブルから検索
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "#info-table tr, #info-table-service tr, #info-table-seat tr")
                for row in rows:
                    try:
                        th = row.find_element(By.TAG_NAME, "th")
                        th_text = th.text.strip()
                        
                        if any(term in th_text for term in search_terms):
                            td = row.find_element(By.TAG_NAME, "td")
                            if td:
                                card_info = td.text.strip()
                                if card_info:
                                    self.logger.debug(f"クレジットカード情報取得成功: {th_text} = {card_info}")
                                    return card_info
                    except:
                        continue
            except:
                pass
            
            # ページ全体から検索
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
                
                if any(pattern in page_text for pattern in ['クレジットカード利用可', 'カード利用可', 'VISA利用可']):
                    self.logger.debug("クレジットカード情報取得成功: 利用可パターン")
                    return '利用可'
                elif any(pattern in page_text for pattern in ['クレジットカード不可', 'カード不可', '現金のみ']):
                    self.logger.debug("クレジットカード情報取得成功: 利用不可パターン")
                    return '利用不可'
                elif 'クレジットカード' in page_text:
                    card_match = re.search(r'クレジットカード[：:]\s*([^\n]+)', page_text)
                    if card_match:
                        card_info = card_match.group(1).strip()
                        self.logger.debug(f"クレジットカード情報取得成功: 正規表現 = {card_info}")
                        return card_info
                    return '要確認'
            except:
                pass
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"クレジットカード情報抽出エラー: {e}")
            return '-'

    def _is_valid_phone_number(self, phone_str):
        """電話番号の妥当性チェック"""
        if not phone_str:
            return False
        
        # 数字とハイフンのみ抽出
        cleaned = re.sub(r'[^\d-]', '', str(phone_str))
        
        # 基本的な電話番号のパターンチェック
        patterns = [
            r'^\d{2,4}-\d{2,4}-\d{3,4}' # 03-1234-5678
            ,  
            r'^\d{10,11}'   # 03123456789
            ,                 
            r'^\d{2,4}\d{2,4}\d{3,4}'   # 区切りなし
            
        ]
        
        for pattern in patterns:
            if re.match(pattern, cleaned):
                digits_only = cleaned.replace('-', '')
                return 10 <= len(digits_only) <= 11
        
        return False
    
    def _get_default_detail(self, url):
        """デフォルトの店舗データ"""
        return {
            'URL': url,
            '店舗名': '取得失敗',
            '電話番号': '-',
            '住所': '-',
            'ジャンル': '-',
            '営業時間': '-',
            '定休日': '-',
            'クレジットカード': '-',
            '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
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
            'UA切り替え回数': self.stats['ua_switches'],
            'CAPTCHA遭遇回数': self.stats['captcha_encounters'],
            'IP制限遭遇回数': self.stats['ip_restrictions'],
            '平均処理時間/店舗': f"{elapsed/max(self.stats['processed_stores'], 1):.1f}秒",
            '完了予想時刻': self.stats['estimated_completion'].strftime('%H:%M:%S') if self.stats['estimated_completion'] else 'N/A',
            '現在時間帯倍率': f"{self.time_multiplier}x"
        }
    
    def start_processing(self, store_list, search_params):
        """メイン処理開始（段階的読み込み対応）"""
        self.stats['start_time'] = time.time()
        self.stats['total_stores'] = len(store_list)
        self.current_results = []
        
        self.logger.info(f"=== 処理開始 (段階的動的生成対応版) ===")
        self.logger.info(f"対象店舗数: {len(store_list)}")
        self.logger.info(f"時間帯倍率: {self.time_multiplier}x")
        self.logger.info(f"予想処理時間: {len(store_list) * 8 * self.time_multiplier / 60:.1f}分")  # 段階的読み込み考慮
        
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
                self.current_results.append(detail)
                
                # 逐次保存
                self.save_results_incremental(
                    detail,
                    search_params['save_path'],
                    search_params['filename']
                )
                
                # User-Agent切り替えチェック
                if idx % self.config['ua_switch_interval'] == 0 and idx < len(store_list):
                    self.logger.info(f"User-Agent切り替え実行 ({idx}件処理完了)")
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
            
            return self.current_results
            
        finally:
            self.cleanup()
    
    def save_store_list(self, store_list, save_path, filename):
        """店舗一覧をExcelに保存"""
        try:
            df = pd.DataFrame(store_list)
            
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            full_path = save_dir / filename
            
            with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='店舗一覧', index=False)
                
                worksheet = writer.sheets['店舗一覧']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 100)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            self.logger.info(f"店舗一覧保存: {full_path}")
            
        except Exception as e:
            self.logger.error(f"店舗一覧保存エラー: {e}")
    
    def save_results_incremental(self, detail_data, save_path, filename):
        """逐次Excelファイル保存"""
        try:
            # 結果リストに追加
            if detail_data not in self.current_results:
                self.current_results.append(detail_data)
            
            # DataFrameを作成
            df = pd.DataFrame(self.current_results)
            
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            full_path = save_dir / filename
            
            # Excelファイルに上書き保存
            with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='店舗詳細', index=False)
                
                # 列幅自動調整
                worksheet = writer.sheets['店舗詳細']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            cell_length = len(str(cell.value))
                            if cell_length > max_length:
                                max_length = cell_length
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # 進捗ログ（頻度制限）
            if len(self.current_results) % 5 == 0:
                self.logger.info(f"中間保存完了: {full_path} ({len(self.current_results)}件)")
            
        except Exception as e:
            self.logger.error(f"中間保存エラー: {e}")
    
    def save_results(self, results, save_path, filename):
        """最終結果をExcelに保存"""
        try:
            df = pd.DataFrame(results)
            
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            full_path = save_dir / filename
            
            with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='店舗詳細', index=False)
                
                # 統計シート追加
                if hasattr(self, 'get_processing_stats'):
                    try:
                        stats_df = pd.DataFrame([self.get_processing_stats()]).T
                        stats_df.columns = ['値']
                        stats_df.to_excel(writer, sheet_name='処理統計')
                    except:
                        pass
                
                # 列幅調整
                for sheet_name in writer.sheets:
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
            
            self.logger.info(f"最終結果保存: {full_path}")
            
        except Exception as e:
            self.logger.error(f"結果保存エラー: {e}")
            raise