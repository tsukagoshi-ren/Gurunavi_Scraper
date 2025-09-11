"""
スクレイピングエンジン
実際のスクレイピング処理を実行
"""

import time
import random
import logging
import re
from datetime import datetime
from pathlib import Path
import pandas as pd

try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class ScraperEngine:
    """スクレイピングエンジンクラス"""
    
    def __init__(self, chrome_manager, prefecture_mapper, config, callback=None):
        self.logger = logging.getLogger(__name__)
        self.chrome_manager = chrome_manager
        self.prefecture_mapper = prefecture_mapper
        self.config = config
        self.callback = callback
        self.driver = None
        self.ua_index = 0
        self.access_count = 0
        self.processed_urls = set()  # 重複URL防止用
        
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
            
            # ドライバー再作成
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
        """店舗URLの有効性チェック"""
        if not url or not isinstance(url, str):
            return False
        
        # 無効なパターンを除外
        invalid_patterns = [
            r'/rs/',           # 検索結果ページ
            r'/area/',         # エリアページ
            r'/city/',         # 市区町村ページ
            r'/plan/',         # プランページ
            r'/campaign/',     # キャンペーンページ
            r'/lottery/',      # 抽選ページ
            r'/kanjirank/',    # ランキングページ
            r'/mycoupon/',     # クーポンページ
            r'/guide/',        # ガイドページ
            r'/help/',         # ヘルプページ
            r'/search',        # 検索ページ
            r'/special/',      # 特集ページ
            r'/feature/',      # 特集ページ
            r'/category/',     # カテゴリページ
            r'/genre/',        # ジャンルページ
            r'member\.gnavi', # メンバーサイト
            r'guide\.gnavi',  # ガイドサイト
            r'www\.gnavi',    # メインサイト
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, url):
                return False
        
        # 店舗URLの有効パターン
        # 通常: https://r.gnavi.co.jp/○○○○○○○○/
        # または: https://r.gnavi.co.jp/○○○○○○○○/menu/
        valid_patterns = [
            r'r\.gnavi\.co\.jp/[a-zA-Z0-9]{8,}/?$',  # 8文字以上の店舗ID
            r'r\.gnavi\.co\.jp/[a-zA-Z0-9]{8,}/menu/?$'  # メニューページ
        ]
        
        for pattern in valid_patterns:
            if re.search(pattern, url):
                return True
        
        return False
    
    def get_store_list(self, prefecture, city, max_count, unlimited):
        """店舗一覧取得"""
        try:
            if not self.initialize_driver():
                raise Exception("ドライバー初期化失敗")
            
            # URL生成
            search_url = self.prefecture_mapper.generate_search_url(prefecture, city)
            self.logger.info(f"検索URL: {search_url}")
            
            # ページアクセス
            self.driver.get(search_url)
            
            # ページ読み込み待機（JavaScriptで生成される要素を待つ）
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "result-cassette__box"))
                )
            except TimeoutException:
                # 代替セレクタ
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='shop'], [class*='store'], [class*='restaurant']"))
                )
            
            # 検索結果数取得
            total_count = self._get_total_count()
            self.logger.info(f"検索結果総数: {total_count}件")
            
            # 取得件数決定
            if unlimited:
                target_count = total_count
            else:
                target_count = min(max_count, total_count)
            
            self.logger.info(f"取得目標: {target_count}件")
            
            # 店舗リスト取得
            store_list = []
            page_num = 1
            self.processed_urls.clear()  # 重複チェック用セットをクリア
            
            while len(store_list) < target_count:
                # 現在ページの店舗取得
                page_stores = self._extract_stores_from_page()
                
                if not page_stores:
                    self.logger.warning(f"ページ {page_num} で店舗が見つかりません")
                    break
                
                # 有効で重複しない店舗のみ追加
                valid_stores = []
                for store in page_stores:
                    if (store and 
                        store.get('url') and 
                        self.is_valid_store_url(store['url']) and
                        store['url'] not in self.processed_urls):
                        
                        self.processed_urls.add(store['url'])
                        valid_stores.append(store)
                
                # 必要な分だけ追加
                remaining = target_count - len(store_list)
                store_list.extend(valid_stores[:remaining])
                
                self.logger.info(f"ページ {page_num}: {len(valid_stores)}件取得 (累計: {len(store_list)}件)")
                
                # 目標達成チェック
                if len(store_list) >= target_count:
                    break
                
                # 次ページへ
                if not self._go_to_next_page():
                    self.logger.info("次ページがありません")
                    break
                
                page_num += 1
                self.wait_with_cooltime()
            
            self.logger.info(f"店舗一覧取得完了: {len(store_list)}件")
            return store_list
            
        except Exception as e:
            self.logger.error(f"店舗一覧取得エラー: {e}")
            raise
    
    def _get_total_count(self):
        """検索結果総数取得"""
        try:
            # パターン1: 検索結果数の表示を探す
            selectors = [
                ".result-count",
                ".search-result-count",
                "[class*='count']",
                ".hit-num",
                ".total-count"
            ]
            
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text
                    # 数字を抽出
                    match = re.search(r'(\d+)', text.replace(',', ''))
                    if match:
                        return int(match.group(1))
                except:
                    continue
            
            # パターン2: 店舗数をカウント
            stores = self._extract_stores_from_page()
            if stores:
                # 1ページ30件として概算
                return len(stores) * 10  # デフォルト10ページ分
            
            return 100  # デフォルト値
            
        except Exception as e:
            self.logger.warning(f"検索結果総数取得エラー: {e}")
            return 100
    
    def _extract_stores_from_page(self):
        """現在ページから店舗情報抽出"""
        stores = []
        
        try:
            # JavaScriptで動的に読み込まれる要素を確実に取得
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # スクロール後の読み込み待機
            
            # JavaScriptを使用して店舗要素を取得
            store_elements = self.driver.execute_script("""
                // 複数のセレクタパターンを試す
                const selectors = [
                    '.result-cassette__box',
                    '.shop-cassette',
                    '.restaurant-list__item',
                    '[class*="shop-item"]',
                    '[class*="store-item"]',
                    '.list-rst',
                    'article[class*="restaurant"]'
                ];
                
                for (let selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        return Array.from(elements).map(el => ({
                            'html': el.outerHTML,
                            'selector': selector
                        }));
                    }
                }
                
                return [];
            """)
            
            if not store_elements:
                self.logger.warning("JavaScriptで店舗要素が見つかりません")
                # Seleniumで再試行
                selectors = [
                    ".result-cassette__box",
                    ".shop-cassette",
                    ".restaurant-list__item",
                    "[class*='shop-item']",
                    "[class*='store-item']",
                    ".list-rst",
                    "article[class*='restaurant']"
                ]
                
                for selector in selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            store_elements = []
                            for element in elements:
                                store_elements.append({
                                    'element': element,
                                    'selector': selector
                                })
                            self.logger.info(f"Selenium店舗要素発見: {selector} ({len(elements)}件)")
                            break
                    except:
                        continue
            else:
                self.logger.info(f"JavaScript店舗要素発見: {len(store_elements)}件")
            
            if not store_elements:
                self.logger.warning("店舗要素が見つかりません")
                return stores
            
            # 各店舗から情報抽出
            for idx, store_data in enumerate(store_elements):
                try:
                    if 'html' in store_data:
                        # JavaScriptで取得したHTML要素から情報抽出
                        store_info = self._extract_store_info_from_html(store_data['html'])
                    else:
                        # Selenium要素から情報抽出
                        store_info = self._extract_store_info(store_data['element'])
                    
                    if store_info and self.is_valid_store_url(store_info.get('url')):
                        stores.append(store_info)
                except Exception as e:
                    self.logger.warning(f"店舗情報抽出エラー (index {idx}): {e}")
                    continue
            
            return stores
            
        except Exception as e:
            self.logger.error(f"ページ店舗抽出エラー: {e}")
            return stores
    
    def _extract_store_info_from_html(self, html_content):
        """HTML文字列から店舗情報抽出"""
        try:
            # JavaScriptで詳細な情報抽出
            store_info = self.driver.execute_script("""
                const div = document.createElement('div');
                div.innerHTML = arguments[0];
                
                // すべてのリンク要素を取得
                const links = div.querySelectorAll('a');
                
                for (let link of links) {
                    const href = link.href || link.getAttribute('href');
                    if (!href) continue;
                    
                    // 店舗URLパターンをチェック
                    const validPatterns = [
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{8,}\\/?$/,
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{8,}\\/menu\\/?$/
                    ];
                    
                    // 無効パターンをチェック
                    const invalidPatterns = [
                        /\\/rs\\//,
                        /\\/area\\//,
                        /\\/city\\//,
                        /\\/plan\\//,
                        /\\/campaign\\//,
                        /\\/lottery\\//,
                        /\\/kanjirank\\//,
                        /\\/mycoupon\\//,
                        /\\/guide\\//,
                        /\\/help\\//,
                        /\\/search/,
                        /\\/special\\//,
                        /\\/feature\\//,
                        /\\/category\\//,
                        /\\/genre\\//,
                        /member\\.gnavi/,
                        /guide\\.gnavi/,
                        /www\\.gnavi/
                    ];
                    
                    // 無効パターンチェック
                    let isInvalid = false;
                    for (let pattern of invalidPatterns) {
                        if (pattern.test(href)) {
                            isInvalid = true;
                            break;
                        }
                    }
                    
                    if (isInvalid) continue;
                    
                    // 有効パターンチェック
                    let isValid = false;
                    for (let pattern of validPatterns) {
                        if (pattern.test(href)) {
                            isValid = true;
                            break;
                        }
                    }
                    
                    if (isValid) {
                        // 店舗名を取得
                        let name = link.textContent.trim();
                        if (!name) {
                            name = link.getAttribute('title') || '';
                        }
                        
                        // 親要素から店舗名を探す
                        if (!name) {
                            const parent = link.closest('[class*="cassette"], [class*="item"], [class*="shop"]');
                            if (parent) {
                                const nameEl = parent.querySelector('[class*="name"], h3, h4, .title');
                                if (nameEl) {
                                    name = nameEl.textContent.trim();
                                }
                            }
                        }
                        
                        if (name) {
                            return {
                                'name': name,
                                'url': href
                            };
                        }
                    }
                }
                
                return null;
            """, html_content)
            
            return store_info
            
        except Exception as e:
            self.logger.warning(f"HTML情報抽出エラー: {e}")
            return None
    
    def _extract_store_info(self, element):
        """店舗要素から情報抽出"""
        try:
            # まずぐるなび特有のtitleLinkクラスを探す
            try:
                title_link = element.find_element(By.CSS_SELECTOR, "a[class*='titleLink'], a[class*='style_titleLink']")
                url = title_link.get_attribute('href')
                
                if url and self.is_valid_store_url(url):
                    # 店舗名を取得（h2要素から）
                    name = None
                    try:
                        name_element = title_link.find_element(By.CSS_SELECTOR, "h2[class*='restaurantName'], h2[class*='style_restaurantName']")
                        name = name_element.text.strip()
                        # PRタグを除去
                        if name.startswith('PR'):
                            name = re.sub(r'^PR\s*', '', name).strip()
                    except:
                        pass
                    
                    # 店舗名が取得できない場合
                    if not name:
                        name = title_link.text.strip()
                        # ジャンル文字列を除去
                        name = re.sub(r'和風軽食・喫茶|洋食|中華|イタリアン|フレンチ|居酒屋|カフェ|バー|焼肉|寿司|ラーメン', '', name).strip()
                        # PRタグを除去
                        name = re.sub(r'^PR\s*', '', name).strip()
                    
                    if name:
                        return {
                            'name': name,
                            'url': url
                        }
            except:
                pass
            
            # 従来の方法でリンク要素を取得
            link_elements = element.find_elements(By.TAG_NAME, "a")
            
            for link_element in link_elements:
                try:
                    url = link_element.get_attribute('href')
                    if not url or not self.is_valid_store_url(url):
                        continue
                    
                    # 店舗名を取得
                    name = link_element.text.strip()
                    if not name:
                        name = link_element.get_attribute('title') or ''
                    
                    # 親要素から店舗名を探す
                    if not name:
                        try:
                            parent = link_element.find_element(By.XPATH, "./ancestor::*[contains(@class, 'cassette') or contains(@class, 'item') or contains(@class, 'shop')][1]")
                            name_selectors = [
                                "[class*='name']",
                                "h3", "h4", ".title"
                            ]
                            for selector in name_selectors:
                                try:
                                    name_el = parent.find_element(By.CSS_SELECTOR, selector)
                                    name = name_el.text.strip()
                                    if name:
                                        break
                                except:
                                    continue
                        except:
                            pass
                    
                    if name:
                        return {
                            'name': name,
                            'url': url
                        }
                        
                except Exception as e:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.warning(f"店舗情報抽出エラー: {e}")
            return None
    
    def _go_to_next_page(self):
        """次ページへ移動"""
        try:
            # 次ページボタンのセレクタ
            next_selectors = [
                "a.next",
                ".pagination__next a",
                "[class*='next'] a",
                "a[rel='next']",
                ".pager-next a"
            ]
            
            for selector in next_selectors:
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if next_button.is_enabled():
                        # スクロールして表示
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                        time.sleep(0.5)
                        next_button.click()
                        
                        # ページ遷移待機
                        time.sleep(2)
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.warning(f"次ページ移動エラー: {e}")
            return False
    
    def get_store_detail(self, url):
        """店舗詳細取得"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.access_count += 1
                
                # アクセス（タイムアウト対策）
                self.logger.info(f"店舗詳細アクセス試行 {attempt + 1}/{max_retries}: {url}")
                self.driver.get(url)
                self.wait_with_cooltime()
                
                # ページ読み込み待機
                wait = WebDriverWait(self.driver, 20)  # 20秒に延長
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                
                # 詳細情報取得
                detail = {
                    'URL': url,
                    '店舗名': self._extract_detail_text(['h1', '.shop-name', '#shop-name', '[class*="name"]']),
                    '電話番号': self._extract_phone_number(),
                    '住所': self._extract_detail_text(['.address', '[class*="address"]', '.shop-address']),
                    'ジャンル': self._extract_detail_text(['.genre', '[class*="genre"]', '[class*="category"]']),
                    '営業時間': self._extract_detail_text(['.business-hours', '[class*="hours"]', '[class*="open"]', '.shop-hours']),
                    '定休日': self._extract_detail_text(['.holiday', '[class*="holiday"]', '[class*="closed"]', '.shop-holiday']),
                    'クレジットカード': self._extract_detail_text(['.credit', '[class*="credit"]', '[class*="card"]']),
                    '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 空欄は「-」に置換
                for key in detail:
                    if key not in ['URL', '取得日時']:
                        if not detail[key] or detail[key].strip() == '':
                            detail[key] = '-'
                
                self.logger.info(f"詳細取得完了: {detail['店舗名']}")
                return detail
                
            except Exception as e:
                self.logger.warning(f"店舗詳細取得エラー (試行{attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    # リトライ前の待機とドライバーリフレッシュ
                    time.sleep(5)
                    
                    # 複数回失敗した場合はドライバーを再初期化
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
                    # 最終的に失敗した場合もデータ構造を返す
                    self.logger.error(f"店舗詳細取得最終失敗 ({url}): {e}")
        
        # エラー時も基本構造を返す
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
    
    def _extract_detail_text(self, selectors):
        """詳細ページからテキスト抽出"""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text
            except:
                continue
        return ''
    
    def _extract_phone_number(self):
        """電話番号抽出"""
        try:
            # 電話番号リンク
            tel_link = self.driver.find_element(By.CSS_SELECTOR, "a[href^='tel:']")
            href = tel_link.get_attribute('href')
            if href:
                return href.replace('tel:', '')
        except:
            pass
        
        # テキストから抽出
        text = self._extract_detail_text(['.tel', '.phone', '[class*="tel"]', '[class*="phone"]'])
        if text:
            # 電話番号パターン
            match = re.search(r'(\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,4})', text)
            if match:
                return match.group(1)
        
        return text
    
    def save_store_list(self, store_list, save_path, filename):
        """店舗一覧をExcelに保存"""
        try:
            df = pd.DataFrame(store_list)
            
            # ファイルパス作成
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            full_path = save_dir / filename
            
            # Excel保存
            with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='店舗一覧', index=False)
                
                # 列幅調整
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
    
    def save_results(self, results, save_path, filename):
        """詳細結果をExcelに保存"""
        try:
            df = pd.DataFrame(results)
            
            # ファイルパス作成
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            full_path = save_dir / filename
            
            # Excel保存（統計シートなし）
            with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
                # メインシートのみ
                df.to_excel(writer, sheet_name='店舗詳細', index=False)
                
                # 列幅調整
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