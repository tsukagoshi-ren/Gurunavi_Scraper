"""
現実的処理時間対応スクレイピングエンジン
サーバー負荷とアクセス制限を考慮した安全運用版
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
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class ImprovedScraperEngine:
    """現実的処理時間対応スクレイピングエンジンクラス"""
    
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
            
            # より短いタイムアウト設定（現実的な値）
            self.driver.implicitly_wait(5)  # 20→5秒
            self.driver.set_page_load_timeout(20)  # 60→20秒
            self.driver.set_script_timeout(15)  # 30→15秒
            
            self.logger.info(f"ドライバー初期化完了 (UA: {self.ua_index})")
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
    
    def wait_for_page_load(self):
        """現実的なページ読み込み待機"""
        try:
            # 基本要素の読み込み待機（短縮）
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 最小限の待機
            time.sleep(1.5)
            
            # JavaScript完了チェック（タイムアウト短縮）
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                pass  # タイムアウトしても続行
            
            # 確実な読み込みのため追加待機
            time.sleep(1)
            
        except TimeoutException:
            self.logger.warning("ページ読み込みタイムアウト - 続行")
        except Exception as e:
            self.logger.error(f"ページ読み込みエラー: {e}")
    
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
        """店舗一覧取得（改良版 - URL取得のみ）"""
        try:
            if not self.initialize_driver():
                raise Exception("ドライバー初期化失敗")
            
            # URL生成
            search_url = self.prefecture_mapper.generate_search_url(prefecture, city)
            self.logger.info(f"検索URL: {search_url}")
            
            # ページアクセス
            self.driver.get(search_url)
            self.wait_for_page_load()
            
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
        """次ページへ移動"""
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
                            time.sleep(3)
                            self.wait_for_page_load()
                            
                            return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.warning(f"次ページ移動エラー: {e}")
            return False
    
    def get_store_detail(self, url):
        """現実的な店舗詳細取得"""
        max_retries = 2  # リトライ回数削減
        
        for attempt in range(max_retries):
            try:
                self.access_count += 1
                
                # 進捗情報の更新
                self.stats['processed_stores'] += 1
                self._update_estimated_completion()
                
                self.logger.info(f"店舗詳細取得開始 ({attempt + 1}/{max_retries}): {url}")
                
                # ページアクセス
                start_time = time.time()
                self.driver.get(url)
                self.wait_for_page_load()
                
                # CAPTCHA検知
                if self._detect_captcha():
                    self.stats['captcha_encounters'] += 1
                    self.logger.warning("CAPTCHA検知 - 待機中")
                    time.sleep(self.config.get('captcha_delay', 30))
                    continue
                
                # IP制限検知
                if self._detect_ip_restriction():
                    self.stats['ip_restrictions'] += 1
                    self.logger.warning("IP制限検知 - 長時間待機")
                    time.sleep(self.config.get('ip_limit_delay', 60))
                    continue
                
                # データ抽出
                detail = self._extract_store_data_fast(url)
                
                # 処理時間ログ
                processing_time = time.time() - start_time
                self.logger.info(f"店舗詳細取得完了: {detail.get('店舗名', 'Unknown')} ({processing_time:.1f}秒)")
                
                # 成功統計更新
                self.stats['successful_stores'] += 1
                
                # 必須クールタイム
                self.wait_with_cooltime()
                
                return detail
                
            except Exception as e:
                self.logger.warning(f"店舗詳細取得エラー (試行{attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    # リトライ前の待機（短縮）
                    retry_delay = self.config.get('retry_delay', 5) * self.time_multiplier
                    time.sleep(retry_delay)
                    
                    # 最後の試行でドライバーリフレッシュ
                    if attempt == max_retries - 2:
                        try:
                            self.switch_user_agent()
                        except:
                            # ドライバー切り替えに失敗した場合は基本的なクリーンアップのみ
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
    
    def _extract_store_data_fast(self, url):
        """高速データ抽出（BeautifulSoup併用）"""
        try:
            # BeautifulSoupで高速解析
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 基本情報抽出
            detail = {
                'URL': url,
                '店舗名': self._extract_bs4_text(soup, [
                    'h1', '.shop-name', '.restaurant-name', '[class*="name"]'
                ]),
                '電話番号': self._extract_bs4_phone(soup),
                '住所': self._extract_bs4_text(soup, [
                    '.address', '.shop-address', '[class*="address"]'
                ]),
                'ジャンル': self._extract_bs4_text(soup, [
                    '.genre', '.category', '[class*="genre"]'
                ]),
                '営業時間': self._extract_bs4_text(soup, [
                    '.business-hours', '.hours', '[class*="hours"]'
                ]),
                '定休日': self._extract_bs4_text(soup, [
                    '.holiday', '.closed', '[class*="holiday"]'
                ]),
                'クレジットカード': self._extract_bs4_text(soup, [
                    '.credit', '.payment', '[class*="credit"]'
                ]),
                '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # データクリーニング
            for key in detail:
                if key not in ['URL', '取得日時']:
                    if not detail[key] or detail[key].strip() == '':
                        detail[key] = '-'
            
            return detail
            
        except Exception as e:
            self.logger.error(f"データ抽出エラー: {e}")
            return self._get_default_detail(url)
    
    def _extract_bs4_text(self, soup, selectors):
        """BeautifulSoupでテキスト抽出"""
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element and element.get_text(strip=True):
                    return element.get_text(strip=True)
            except:
                continue
        return '-'
    
    def _extract_bs4_phone(self, soup):
        """BeautifulSoupで電話番号抽出"""
        try:
            # tel:リンクから抽出
            tel_link = soup.select_one('a[href^="tel:"]')
            if tel_link:
                href = tel_link.get('href', '')
                phone = href.replace('tel:', '').strip()
                if phone and len(phone) >= 10:
                    return phone
            
            # テキストパターンで抽出
            selectors = ['.tel', '.phone', '[class*="tel"]', '[class*="phone"]']
            for selector in selectors:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    phone_match = re.search(r'(\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,4})', text)
                    if phone_match:
                        return phone_match.group(1)
            
            return '-'
        except:
            return '-'
    
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
        """メイン処理開始"""
        self.stats['start_time'] = time.time()
        self.stats['total_stores'] = len(store_list)
        self.current_results = []
        
        self.logger.info(f"=== 処理開始 ===")
        self.logger.info(f"対象店舗数: {len(store_list)}")
        self.logger.info(f"時間帯倍率: {self.time_multiplier}x")
        self.logger.info(f"予想処理時間: {len(store_list) * 7 * self.time_multiplier / 60:.1f}分")
        
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