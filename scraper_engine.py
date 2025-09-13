"""
改良版スクレイピングエンジン
店舗詳細取得の修正版
"""

import time
import random
import logging
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
from urllib.parse import urljoin, urlparse

try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class ImprovedScraperEngine:
    """改良版スクレイピングエンジンクラス"""
    
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
    
    def initialize_driver(self):
        """ドライバー初期化"""
        try:
            user_agent = self.config['user_agents'][self.ua_index]
            self.driver = self.chrome_manager.create_driver(
                headless=True,
                user_agent=user_agent
            )
            self.logger.info("ドライバー初期化完了")
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
        """User-Agent切り替え"""
        try:
            self.ua_index = (self.ua_index + 1) % len(self.config['user_agents'])
            user_agent = self.config['user_agents'][self.ua_index]
            
            self.cleanup()
            self.driver = self.chrome_manager.create_driver(
                headless=True,
                user_agent=user_agent
            )
            
            self.logger.info(f"User-Agent切り替え: インデックス {self.ua_index}")
            
        except Exception as e:
            self.logger.error(f"User-Agent切り替えエラー: {e}")
    
    def wait_with_cooltime(self):
        """クールタイム待機"""
        cooltime = random.uniform(
            self.config['cooltime_min'],
            self.config['cooltime_max']
        )
        time.sleep(cooltime)
    
    def is_valid_store_url(self, url):
        """店舗URLの有効性チェック（修正版）"""
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
        """店舗URLのベースURL取得（修正版）"""
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
    
    def wait_for_page_load(self):
        """ページ読み込み完了待機（改良版）"""
        try:
            # 基本的な要素の読み込み待機
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # JavaScriptの実行完了待機
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # 追加の待機（動的コンテンツ用）
            time.sleep(3)
            
            # ページを下までスクロールして動的コンテンツを読み込み
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 中間位置までスクロール
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            # 元の位置に戻す
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
        except TimeoutException:
            self.logger.warning("ページ読み込みタイムアウト - 続行します")
    
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
        """店舗詳細取得（修正版）"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.access_count += 1
                
                self.logger.info(f"店舗詳細アクセス試行 {attempt + 1}/{max_retries}: {url}")
                self.driver.get(url)
                
                # ページ読み込み待機を強化
                self.wait_for_page_load()
                
                # 追加の待機（ぐるなび特有の動的コンテンツ対応）
                time.sleep(3)
                
                # ページが正常に読み込まれているかチェック
                if not self._verify_page_loaded():
                    raise Exception("ページが正常に読み込まれていません")
                
                # 店舗詳細情報を抽出
                detail = {
                    'URL': url,
                    '店舗名': self._extract_store_name(),
                    '電話番号': self._extract_phone_number(),
                    '住所': self._extract_address(),
                    'ジャンル': self._extract_genre(),
                    '営業時間': self._extract_business_hours(),
                    '定休日': self._extract_holiday(),
                    'クレジットカード': self._extract_credit_card(),
                    '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 空白データの処理
                for key in detail:
                    if key not in ['URL', '取得日時']:
                        if not detail[key] or detail[key].strip() == '':
                            detail[key] = '-'
                
                self.logger.info(f"詳細取得完了: {detail['店舗名']}")
                
                # クールタイム待機
                self.wait_with_cooltime()
                
                return detail
                
            except Exception as e:
                self.logger.warning(f"店舗詳細取得エラー (試行{attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(5)
                    
                    # 2回目以降の試行でドライバーをリフレッシュ
                    if attempt >= 1:
                        try:
                            self.logger.info("ドライバーリフレッシュ実行")
                            self.switch_user_agent()
                        except:
                            self.cleanup()
                            time.sleep(3)
                            if not self.initialize_driver():
                                raise Exception("ドライバー再初期化失敗")
                else:
                    self.logger.error(f"店舗詳細取得最終失敗 ({url}): {e}")
        
        # 失敗時のデフォルトデータ
        return {
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
    
    def _verify_page_loaded(self):
        """ページが正常に読み込まれているかチェック"""
        try:
            # 店舗ページの基本要素が存在するかチェック
            basic_elements = [
                "h1", ".shop-title", ".restaurant-name", "[data-testid*='name']",
                ".shop-name", ".store-name", "#shop-name"
            ]
            
            for selector in basic_elements:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.text.strip():
                        return True
                except:
                    continue
            
            # bodyの内容をチェック
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if len(body_text.strip()) > 100:  # 最低限のコンテンツがあるかチェック
                return True
            
            return False
            
        except Exception:
            return False
    
    def _extract_store_name(self):
        """店舗名抽出（改良版）"""
        selectors = [
            "h1",
            ".shop-title",
            ".restaurant-name", 
            ".shop-name",
            ".store-name",
            "#shop-name",
            "[data-testid*='name']",
            ".name",
            "[class*='shop-name']",
            "[class*='store-name']",
            "[class*='restaurant-name']",
            "h1[class*='title']",
            ".page-title",
            ".main-title"
        ]
        
        return self._extract_text_by_selectors(selectors, "店舗名")
    
    def _extract_phone_number(self):
        """電話番号抽出（改良版）"""
        try:
            # tel:リンクから抽出
            try:
                tel_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href^='tel:']")
                for tel_element in tel_elements:
                    href = tel_element.get_attribute('href')
                    if href:
                        phone = href.replace('tel:', '').strip()
                        if phone and len(phone) >= 10:
                            return phone
            except:
                pass
            
            # テキストから抽出
            selectors = [
                ".tel", ".phone", ".telephone",
                "[class*='tel']", "[class*='phone']",
                ".contact-tel", ".shop-tel",
                "[data-testid*='tel']", "[data-testid*='phone']"
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text:
                            # 電話番号パターンをマッチング
                            phone_patterns = [
                                r'(\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,4})',
                                r'(\d{10,11})',
                                r'(0\d{1,4}-\d{1,4}-\d{3,4})'
                            ]
                            
                            for pattern in phone_patterns:
                                match = re.search(pattern, text)
                                if match:
                                    return match.group(1)
                except:
                    continue
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"電話番号抽出エラー: {e}")
            return '-'
    
    def _extract_address(self):
        """住所抽出（改良版）"""
        selectors = [
            ".address", ".shop-address", ".store-address",
            "[class*='address']", "[data-testid*='address']",
            ".location", ".shop-location"
        ]
        
        return self._extract_text_by_selectors(selectors, "住所")
    
    def _extract_genre(self):
        """ジャンル抽出（改良版）"""
        selectors = [
            ".genre", ".category", ".shop-genre",
            "[class*='genre']", "[class*='category']",
            "[data-testid*='genre']", "[data-testid*='category']",
            ".cuisine", ".food-type"
        ]
        
        return self._extract_text_by_selectors(selectors, "ジャンル")
    
    def _extract_business_hours(self):
        """営業時間抽出（改良版）"""
        selectors = [
            ".business-hours", ".opening-hours", ".shop-hours",
            "[class*='hours']", "[class*='open']", "[class*='time']",
            "[data-testid*='hours']", "[data-testid*='time']",
            ".schedule", ".operation-time"
        ]
        
        return self._extract_text_by_selectors(selectors, "営業時間")
    
    def _extract_holiday(self):
        """定休日抽出（改良版）"""
        selectors = [
            ".holiday", ".closed", ".rest-day",
            "[class*='holiday']", "[class*='closed']", "[class*='rest']",
            "[data-testid*='holiday']", "[data-testid*='closed']"
        ]
        
        return self._extract_text_by_selectors(selectors, "定休日")
    
    def _extract_credit_card(self):
        """クレジットカード情報抽出（改良版）"""
        selectors = [
            ".credit", ".credit-card", ".payment",
            "[class*='credit']", "[class*='card']", "[class*='payment']",
            "[data-testid*='credit']", "[data-testid*='payment']"
        ]
        
        return self._extract_text_by_selectors(selectors, "クレジットカード")
    
    def _extract_text_by_selectors(self, selectors, field_name):
        """セレクタリストからテキスト抽出"""
        try:
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 0:
                            # 不要な文字列を除去
                            cleaned_text = self._clean_extracted_text(text)
                            if cleaned_text:
                                return cleaned_text
                except:
                    continue
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"{field_name}抽出エラー: {e}")
            return '-'
    
    def _clean_extracted_text(self, text):
        """抽出したテキストのクリーニング"""
        if not text:
            return ''
        
        # 改行と余分な空白を除去
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # 不要な文字列を除去
        unwanted_patterns = [
            r'^(詳細|more|MORE|もっと見る|全て見る)',
            r'(クリック|click|CLICK)',
            r'^\s*$'
        ]
        
        for pattern in unwanted_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        return cleaned.strip()
    
    def save_store_list(self, store_list, save_path, filename):
        """店舗一覧をExcelに保存"""
        try:
            df = pd.DataFrame(store_list)
            
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            full_path = save_dir / filename
            self.excel_file_path = full_path  # 後で上書き用に保存
            
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
        """詳細結果を逐次Excelに保存（上書き方式）"""
        try:
            # 結果リストに追加
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
                
                worksheet = writer.sheets['店舗詳細']
                # 列幅を自動調整
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
            
            self.logger.info(f"詳細結果を上書き保存: {full_path} (件数: {len(self.current_results)})")
            
        except Exception as e:
            self.logger.error(f"詳細結果保存エラー: {e}")
    
    def save_results(self, results, save_path, filename):
        """詳細結果をExcelに保存（最終版）"""
        try:
            df = pd.DataFrame(results)
            
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            full_path = save_dir / filename
            
            with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='店舗詳細', index=False)
                
                worksheet = writer.sheets['店舗詳細']
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
            
            self.logger.info(f"詳細結果保存: {full_path}")
            
        except Exception as e:
            self.logger.error(f"結果保存エラー: {e}")
            raise

    # 独立したテスト用関数
    def test_store_detail_extraction(url):
        """店舗詳細抽出テスト関数"""
        import json
        from chrome_driver_manager import ChromeDriverManager
        from prefecture_mapper import PrefectureMapper
        
        # ログ設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # 設定
        config = {
            "cooltime_min": 1.0,
            "cooltime_max": 3.0,
            "user_agents": [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            ]
        }
        
        # インスタンス作成
        chrome_manager = ChromeDriverManager()
        prefecture_mapper = PrefectureMapper()
        
        def progress_callback(data):
            print(f"[{data.get('phase', 'unknown')}] {data.get('message', '')}")
        
        # スクレイパー作成
        scraper = ImprovedScraperEngine(
            chrome_manager=chrome_manager,
            prefecture_mapper=prefecture_mapper,
            config=config,
            callback=progress_callback
        )
        
        try:
            print(f"=== 店舗詳細抽出テスト開始 ===")
            print(f"テスト対象URL: {url}")
            
            # ドライバー初期化
            if not scraper.initialize_driver():
                raise Exception("ドライバー初期化失敗")
            
            # 店舗詳細取得
            detail = scraper.get_store_detail(url)
            
            print(f"\n=== 取得結果 ===")
            for key, value in detail.items():
                print(f"{key}: {value}")
            
            return detail
            
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        finally:
            scraper.cleanup()

    # 使用例
    if __name__ == "__main__":
        # 詳細抽出テスト用の例
        test_url = "https://r.gnavi.co.jp/f086700/"  # 実際の店舗URLに置き換え
        result = test_store_detail_extraction(test_url)