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
        self.processed_urls = set()
    
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
        """店舗URLの有効性チェック"""
        if not url or not isinstance(url, str):
            return False
        
        # クエリパラメータを除去してベースURLをチェック
        base_url = url.split('?')[0]
        
        # 無効なパターンを除外
        invalid_patterns = [
            r'/rs/$',
            r'/area/$',
            r'/city/$',
            r'/plan/',
            r'/campaign/',
            r'/lottery/',
            r'/kanjirank/',
            r'/mycoupon/',
            r'/guide/',
            r'/help/',
            r'/search',
            r'/special/',
            r'/feature/',
            r'/category/',
            r'/genre/',
            r'member\.gnavi',
            r'guide\.gnavi',
            r'www\.gnavi',
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, base_url):
                return False
        
        # 店舗URLの有効パターン
        valid_patterns = [
            r'r\.gnavi\.co\.jp/[a-zA-Z0-9]{3,}/?$',
            r'r\.gnavi\.co\.jp/[a-zA-Z0-9]{3,}/menu/?$',
            r'r\.gnavi\.co\.jp/[a-zA-Z0-9]{3,}/course/?$',
            r'r\.gnavi\.co\.jp/[a-zA-Z0-9]{3,}/map/?$',
            r'r\.gnavi\.co\.jp/[a-zA-Z0-9]{3,}/coupon/?$',
        ]
        
        for pattern in valid_patterns:
            if re.search(pattern, base_url):
                return True
        
        return False
    
        def get_store_list(self, prefecture, city, max_count, unlimited):
            """店舗一覧取得（改善版）"""
            try:
                if not self.initialize_driver():
                    raise Exception("ドライバー初期化失敗")
                
                # URL生成
                search_url = self.prefecture_mapper.generate_search_url(prefecture, city)
                self.logger.info(f"検索URL: {search_url}")
                
                # ページアクセス
                self.driver.get(search_url)
                
                # ページ読み込み待機（より柔軟な待機処理）
                try:
                    # まず基本的なページ読み込みを待つ
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    # JavaScriptの実行完了を待つ
                    self.driver.execute_script("return document.readyState") == "complete"
                    
                    # 追加の待機時間（動的コンテンツの読み込み用）
                    time.sleep(3)
                    
                    # ページの高さが安定するまで待つ
                    last_height = self.driver.execute_script("return document.body.scrollHeight")
                    time.sleep(1)
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    
                    # 高さが変わらなくなるまで待つ（最大3回）
                    for i in range(3):
                        if last_height == new_height:
                            break
                        last_height = new_height
                        time.sleep(1)
                        new_height = self.driver.execute_script("return document.body.scrollHeight")
                    
                except TimeoutException:
                    self.logger.warning("ページ読み込みタイムアウト - 続行します")
                
                # 現在のページを確認（デバッグ用）
                current_url = self.driver.current_url
                page_title = self.driver.title
                self.logger.info(f"ページ読み込み完了 - URL: {current_url}")
                self.logger.info(f"ページタイトル: {page_title}")
                
                # エラーページかどうかチェック
                if "404" in page_title or "エラー" in page_title or "見つかりません" in page_title:
                    raise Exception(f"エラーページが表示されました: {page_title}")
                
                # 検索結果数取得（エラーを無視して続行）
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
                consecutive_empty_pages = 0  # 連続して空のページ数
                
                while len(store_list) < target_count:
                    # 現在ページの店舗取得
                    self.logger.info(f"ページ {page_num} の店舗を取得中...")
                    page_stores = self._extract_stores_from_page()
                    
                    if not page_stores:
                        consecutive_empty_pages += 1
                        self.logger.warning(f"ページ {page_num} で店舗が見つかりません（連続{consecutive_empty_pages}回目）")
                        
                        # 3ページ連続で店舗が見つからない場合は終了
                        if consecutive_empty_pages >= 3:
                            self.logger.warning("3ページ連続で店舗が見つからないため終了します")
                            break
                        
                        # 次ページへ移動してリトライ
                        if not self._go_to_next_page():
                            self.logger.info("次ページがありません")
                            break
                        
                        page_num += 1
                        self.wait_with_cooltime()
                        continue
                    else:
                        consecutive_empty_pages = 0  # リセット
                    
                    # 有効で重複しない店舗のみ追加
                    valid_stores = []
                    for store in page_stores:
                        if (store and 
                            store.get('url') and 
                            self.is_valid_store_url(store['url']) and
                            store['url'] not in self.processed_urls):
                            
                            # URLの正規化（クエリパラメータを統一）
                            normalized_url = store['url'].split('?')[0]
                            if normalized_url not in self.processed_urls:
                                self.processed_urls.add(normalized_url)
                                self.processed_urls.add(store['url'])  # 元のURLも追加
                                valid_stores.append(store)
                    
                    # 必要な分だけ追加
                    remaining = target_count - len(store_list)
                    store_list.extend(valid_stores[:remaining])
                    
                    self.logger.info(f"ページ {page_num}: {len(valid_stores)}件取得 (累計: {len(store_list)}件)")
                    
                    # 目標達成チェック
                    if len(store_list) >= target_count:
                        self.logger.info(f"目標件数に到達しました: {len(store_list)}件")
                        break
                    
                    # 次ページへ
                    if not self._go_to_next_page():
                        self.logger.info("次ページがありません")
                        break
                    
                    page_num += 1
                    self.wait_with_cooltime()
                    
                    # 無限ループ防止（最大100ページ）
                    if page_num > 100:
                        self.logger.warning("最大ページ数(100)に到達しました")
                        break
                
                # 結果の確認
                if not store_list:
                    self.logger.error("店舗が1件も取得できませんでした")
                    
                    # ページソースの一部を保存（デバッグ用）
                    try:
                        page_source = self.driver.page_source[:5000]  # 最初の5000文字
                        debug_file = Path("debug_page_source.html")
                        with open(debug_file, "w", encoding="utf-8") as f:
                            f.write(page_source)
                        self.logger.info(f"デバッグ用ページソースを保存: {debug_file}")
                    except:
                        pass
                
                self.logger.info(f"店舗一覧取得完了: {len(store_list)}件")
                return store_list
                
            except Exception as e:
                self.logger.error(f"店舗一覧取得エラー: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                raise
            
    def _get_total_count(self):
        """検索結果総数取得"""
        try:
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
                    match = re.search(r'(\d+)', text.replace(',', ''))
                    if match:
                        return int(match.group(1))
                except:
                    continue
            
            stores = self._extract_stores_from_page()
            if stores:
                return len(stores) * 10
            
            return 100
            
        except Exception as e:
            self.logger.warning(f"検索結果総数取得エラー: {e}")
            return 100
    
    def _extract_stores_from_page(self):
        """現在ページから店舗情報抽出（改善版）"""
        stores = []
        
        try:
            # ページ全体をスクロールして動的コンテンツを読み込む
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # まず、JavaScriptで全てのリンクを取得して店舗URLを探す
            store_data = self.driver.execute_script("""
                const allLinks = document.querySelectorAll('a');
                const storeData = [];
                const processedUrls = new Set();
                
                for (let link of allLinks) {
                    const href = link.href || link.getAttribute('href');
                    if (!href || processedUrls.has(href)) continue;
                    
                    // フルURLを取得
                    let fullUrl = href;
                    if (href.startsWith('/')) {
                        fullUrl = window.location.origin + href;
                    }
                    
                    // クエリパラメータを除去してベースURLを取得
                    const baseUrl = fullUrl.split('?')[0];
                    
                    // 店舗URLパターンをチェック（緩和版）
                    const validPatterns = [
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/?$/,
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/menu\\/?$/,
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/course\\/?$/,
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/map\\/?$/,
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/coupon\\/?$/
                    ];
                    
                    // 無効パターンをチェック
                    const invalidPatterns = [
                        /\\/rs\\/$/,
                        /\\/area\\/$/,
                        /\\/city\\/$/,
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
                        if (pattern.test(baseUrl)) {
                            isInvalid = true;
                            break;
                        }
                    }
                    
                    if (isInvalid) continue;
                    
                    // 有効パターンチェック
                    let isValid = false;
                    for (let pattern of validPatterns) {
                        if (pattern.test(baseUrl)) {
                            isValid = true;
                            break;
                        }
                    }
                    
                    if (isValid) {
                        processedUrls.add(href);
                        
                        // 店舗名を取得（複数の方法を試す）
                        let name = '';
                        
                        // 1. リンクのテキストから取得
                        const linkText = link.textContent.trim();
                        if (linkText && linkText.length > 0 && linkText.length < 100) {
                            name = linkText;
                        }
                        
                        // 2. title属性から取得
                        if (!name) {
                            name = link.getAttribute('title') || '';
                        }
                        
                        // 3. 画像のalt属性から取得
                        if (!name) {
                            const img = link.querySelector('img');
                            if (img) {
                                name = img.getAttribute('alt') || '';
                            }
                        }
                        
                        // 4. 親要素から店舗名を探す（より広範囲に探索）
                        if (!name) {
                            let parent = link.parentElement;
                            let searchDepth = 0;
                            while (parent && searchDepth < 5) {
                                // 店舗名が含まれそうな要素を探す
                                const nameElements = parent.querySelectorAll('h1, h2, h3, h4, h5, [class*="name"], [class*="title"], .shop-name, .restaurant-name');
                                for (let el of nameElements) {
                                    const text = el.textContent.trim();
                                    if (text && text.length > 0 && text.length < 100) {
                                        name = text;
                                        break;
                                    }
                                }
                                if (name) break;
                                parent = parent.parentElement;
                                searchDepth++;
                            }
                        }
                        
                        // 5. 同じ親要素内のテキストを探す
                        if (!name) {
                            const container = link.closest('article, div[class*="cassette"], div[class*="item"], div[class*="shop"], div[class*="restaurant"], li');
                            if (container) {
                                const texts = container.querySelectorAll('*:not(script):not(style)');
                                for (let el of texts) {
                                    if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) {
                                        const text = el.textContent.trim();
                                        if (text && text.length > 2 && text.length < 100 && !text.includes('\\n')) {
                                            name = text;
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                        
                        // PRタグやジャンル名を除去
                        if (name) {
                            name = name.replace(/^PR\\s*/, '');
                            name = name.replace(/和風軽食・喫茶|洋食|中華|イタリアン|フレンチ|居酒屋|カフェ|バー|焼肉|寿司|ラーメン/, '');
                            name = name.trim();
                        }
                        
                        // 名前が取得できなかった場合はURLから生成
                        if (!name) {
                            const match = baseUrl.match(/\\/([a-zA-Z0-9]+)\\/?$/);
                            if (match) {
                                name = '店舗ID: ' + match[1];
                            }
                        }
                        
                        if (name) {
                            storeData.push({
                                'name': name,
                                'url': fullUrl
                            });
                        }
                    }
                }
                
                return storeData;
            """)
            
            if store_data and len(store_data) > 0:
                self.logger.info(f"JavaScript店舗データ取得: {len(store_data)}件")
                stores = store_data
            else:
                self.logger.warning("JavaScriptで店舗が見つかりません。Seleniumで再試行")
                
                # Seleniumでのフォールバック処理（全リンクを取得）
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                self.logger.info(f"ページ内の全リンク数: {len(all_links)}")
                
                processed_urls = set()
                for link in all_links:
                    try:
                        url = link.get_attribute('href')
                        if not url or url in processed_urls:
                            continue
                        
                        if self.is_valid_store_url(url):
                            processed_urls.add(url)
                            
                            # 店舗名を取得
                            name = link.text.strip()
                            if not name:
                                name = link.get_attribute('title') or ''
                            
                            # 画像のalt属性を確認
                            if not name:
                                try:
                                    img = link.find_element(By.TAG_NAME, "img")
                                    name = img.get_attribute('alt') or ''
                                except:
                                    pass
                            
                            # 親要素から店舗名を探す
                            if not name:
                                try:
                                    parent = link.find_element(By.XPATH, "..")
                                    for i in range(3):  # 3階層上まで探索
                                        texts = parent.find_elements(By.XPATH, ".//*[contains(@class, 'name') or contains(@class, 'title')]")
                                        for text_el in texts:
                                            text = text_el.text.strip()
                                            if text and len(text) < 100:
                                                name = text
                                                break
                                        if name:
                                            break
                                        parent = parent.find_element(By.XPATH, "..")
                                except:
                                    pass
                            
                            # 名前が取得できない場合はURLから生成
                            if not name:
                                import re
                                match = re.search(r'/([a-zA-Z0-9]+)/?(\?|$)', url)
                                if match:
                                    name = f'店舗ID: {match.group(1)}'
                            
                            if name:
                                stores.append({
                                    'name': name.replace('PR', '').strip(),
                                    'url': url
                                })
                                
                    except Exception as e:
                        continue
                
                if stores:
                    self.logger.info(f"Selenium店舗データ取得: {len(stores)}件")
            
            # デバッグ情報
            if not stores:
                self.logger.warning("店舗が見つかりません。ページ内容を確認します")
                
                # ページのURLを確認
                current_url = self.driver.current_url
                self.logger.info(f"現在のURL: {current_url}")
                
                # ページタイトルを確認
                page_title = self.driver.title
                self.logger.info(f"ページタイトル: {page_title}")
                
                # 全リンクのサンプルを表示（デバッグ用）
                sample_links = self.driver.execute_script("""
                    const links = document.querySelectorAll('a');
                    const samples = [];
                    for (let i = 0; i < Math.min(10, links.length); i++) {
                        const href = links[i].href || links[i].getAttribute('href');
                        if (href) {
                            samples.push(href);
                        }
                    }
                    return samples;
                """)
                self.logger.info(f"リンクサンプル: {sample_links}")
            
            return stores
            
        except Exception as e:
            self.logger.error(f"ページ店舗抽出エラー: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return stores

    def _extract_store_info_from_html(self, html_content):
        """HTML文字列から店舗情報抽出"""
        try:
            store_info = self.driver.execute_script("""
                const div = document.createElement('div');
                div.innerHTML = arguments[0];
                
                const links = div.querySelectorAll('a');
                
                for (let link of links) {
                    const href = link.href || link.getAttribute('href');
                    if (!href) continue;
                    
                    const baseUrl = href.split('?')[0];
                    
                    const validPatterns = [
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/?$/,
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/menu\\/?$/,
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/course\\/?$/,
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/map\\/?$/,
                        /r\\.gnavi\\.co\\.jp\\/[a-zA-Z0-9]{3,}\\/coupon\\/?$/
                    ];
                    
                    const invalidPatterns = [
                        /\\/rs\\/$/,
                        /\\/area\\/$/,
                        /\\/city\\/$/,
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
                    
                    let isInvalid = false;
                    for (let pattern of invalidPatterns) {
                        if (pattern.test(baseUrl)) {
                            isInvalid = true;
                            break;
                        }
                    }
                    
                    if (isInvalid) continue;
                    
                    let isValid = false;
                    for (let pattern of validPatterns) {
                        if (pattern.test(baseUrl)) {
                            isValid = true;
                            break;
                        }
                    }
                    
                    if (isValid) {
                        let name = link.textContent.trim();
                        if (!name) {
                            name = link.getAttribute('title') || '';
                        }
                        
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
            try:
                title_link = element.find_element(By.CSS_SELECTOR, "a[class*='titleLink'], a[class*='style_titleLink']")
                url = title_link.get_attribute('href')
                
                if url and self.is_valid_store_url(url):
                    name = None
                    try:
                        name_element = title_link.find_element(By.CSS_SELECTOR, "h2[class*='restaurantName'], h2[class*='style_restaurantName']")
                        name = name_element.text.strip()
                        if name.startswith('PR'):
                            name = re.sub(r'^PR\s*', '', name).strip()
                    except:
                        pass
                    
                    if not name:
                        name = title_link.text.strip()
                        name = re.sub(r'和風軽食・喫茶|洋食|中華|イタリアン|フレンチ|居酒屋|カフェ|バー|焼肉|寿司|ラーメン', '', name).strip()
                        name = re.sub(r'^PR\s*', '', name).strip()
                    
                    if name:
                        return {
                            'name': name,
                            'url': url
                        }
            except:
                pass
            
            link_elements = element.find_elements(By.TAG_NAME, "a")
            
            for link_element in link_elements:
                try:
                    url = link_element.get_attribute('href')
                    if not url or not self.is_valid_store_url(url):
                        continue
                    
                    name = link_element.text.strip()
                    if not name:
                        name = link_element.get_attribute('title') or ''
                    
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
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                        time.sleep(0.5)
                        next_button.click()
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
                
                self.logger.info(f"店舗詳細アクセス試行 {attempt + 1}/{max_retries}: {url}")
                self.driver.get(url)
                self.wait_with_cooltime()
                
                wait = WebDriverWait(self.driver, 20)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                
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
                
                for key in detail:
                    if key not in ['URL', '取得日時']:
                        if not detail[key] or detail[key].strip() == '':
                            detail[key] = '-'
                
                self.logger.info(f"詳細取得完了: {detail['店舗名']}")
                return detail
                
            except Exception as e:
                self.logger.warning(f"店舗詳細取得エラー (試行{attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(5)
                    
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
            tel_link = self.driver.find_element(By.CSS_SELECTOR, "a[href^='tel:']")
            href = tel_link.get_attribute('href')
            if href:
                return href.replace('tel:', '')
        except:
            pass
        
        text = self._extract_detail_text(['.tel', '.phone', '[class*="tel"]', '[class*="phone"]'])
        if text:
            match = re.search(r'(\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,4})', text)
            if match:
                return match.group(1)
        
        return text
    
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
    
    def save_results(self, results, save_path, filename):
        """詳細結果をExcelに保存"""
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