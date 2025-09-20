"""
現実的処理時間対応スクレイピングエンジン
全国対応・正しいURL構造に対応
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
    """段階的動的生成対応スクレイピングエンジンクラス（ページネーション修正版）"""
    
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
        """店舗一覧取得（正しいページネーション対応）"""
        try:
            if not self.initialize_driver():
                raise Exception("ドライバー初期化失敗")
            
            # URL生成（最初のページ）
            search_url = self.prefecture_mapper.generate_search_url(prefecture, city, page=1)
            self.logger.info(f"検索URL: {search_url}")
            self.logger.info(f"検索エリア: {self.prefecture_mapper.get_area_display_name(prefecture, city)}")
            
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
            max_pages = 50 if unlimited else min(20, (max_count // 30) + 5)  # 1ページ30件なので調整
            
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
                
                # 次ページへ（正しいURL生成）
                page_num += 1
                next_url = self.prefecture_mapper.generate_search_url(prefecture, city, page=page_num)
                
                self.logger.info(f"次ページへ移動: {next_url}")
                self.driver.get(next_url)
                
                # ページ読み込み待機
                self._wait_for_stepwise_content_load()
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
    
    def get_store_detail(self, url):
        """店舗詳細取得（4項目のみ）"""
        try:
            self.driver.get(url)
            
            # 段階的コンテンツ読み込み
            self._wait_for_stepwise_content_load()
            
            # 複数アプローチ抽出器を使用（4項目のみ）
            extractor = GurunaviMultiApproachExtractor(self.driver, self.logger)
            detail = extractor.extract_store_data_multi_modified(url)
            
            self.wait_with_cooltime()
            return detail
            
        except Exception as e:
            self.logger.error(f"店舗詳細取得エラー: {e}")
            return self._get_default_detail(url)
    
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
        self.logger.info(f"予想処理時間: {len(store_list) * 8 * self.time_multiplier / 60:.1f}分")
        
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
                
                # 統計更新
                self.stats['processed_stores'] = idx
                if detail['店舗名'] != '取得失敗':
                    self.stats['successful_stores'] += 1
                else:
                    self.stats['failed_stores'] += 1
                
                self._update_estimated_completion()
                
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