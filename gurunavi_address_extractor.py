"""
住所・郵便番号取得対応版：ぐるなび店舗データ抽出
URL、店舗名、電話番号、郵便番号、住所、取得日時の6項目を取得
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import re
import time
import logging

class GurunaviAddressExtractor:
    """住所・郵便番号対応版ぐるなび店舗情報抽出クラス"""
    
    def __init__(self, driver, logger=None):
        self.driver = driver
        self.logger = logger or logging.getLogger(__name__)
        if self.driver is None:
            raise ValueError("Driver cannot be None")
        self.wait = WebDriverWait(driver, 15)
    
    def extract_store_data_with_address(self, url):
        """店舗データを抽出（郵便番号含む6項目）"""
        try:
            from datetime import datetime
            
            if self.driver is None:
                self.logger.error("Driver is None in extract_store_data_with_address")
                return self._get_default_detail(url)
            
            # 基本情報の初期化（6項目）
            detail = {
                'URL': url,
                '店舗名': '-',
                '電話番号': '-',
                '郵便番号': '-',
                '住所': '-',
                '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # ページが完全に読み込まれるのを待つ
            self._ensure_page_loaded()
            
            # 店舗名を取得
            detail['店舗名'] = self._extract_shop_name()
            
            # 電話番号を取得してクリーニング
            raw_phone = self._extract_phone_number()
            detail['電話番号'] = self._clean_phone_number(raw_phone)
            
            # 郵便番号と住所を取得
            postal_and_address = self._extract_postal_and_address()
            detail['郵便番号'] = postal_and_address['postal_code']
            detail['住所'] = postal_and_address['address']
            
            self.logger.info(f"取得結果: {detail}")
            return detail
            
        except Exception as e:
            self.logger.error(f"データ抽出エラー: {e}")
            return self._get_default_detail(url)
    
    def _ensure_page_loaded(self):
        """ページが完全に読み込まれることを確認"""
        try:
            if self.driver is None:
                self.logger.error("Driver is None in _ensure_page_loaded")
                return
            
            # JavaScriptの読み込み完了を待つ
            self.driver.execute_script("return document.readyState") == "complete"
            
            # スクロールして遅延読み込みをトリガー
            self.driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 1000);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
        except Exception as e:
            self.logger.warning(f"ページ読み込み確認エラー: {e}")
    
    def _extract_shop_name(self):
        """店舗名を取得"""
        try:
            if self.driver is None:
                return '-'
            
            # JavaScriptで取得
            js_script = """
            // ヘッダーの店舗名を探す
            const headerName = document.querySelector('#header-main-name a');
            if (headerName) {
                return headerName.innerText.trim();
            }
            
            // h1タグから取得
            const h1 = document.querySelector('h1');
            if (h1) {
                return h1.innerText.trim();
            }
            
            return null;
            """
            
            name = self.driver.execute_script(js_script)
            if name and 'ぐるなび' not in name:
                self.logger.info(f"店舗名取得成功: {name}")
                return name
            
            # titleタグから取得
            title = self.driver.title
            if title:
                name = title.split(' - ')[0].split('｜')[0].strip()
                if name and name != 'ぐるなび':
                    return name
            
        except Exception as e:
            self.logger.warning(f"店舗名抽出エラー: {e}")
        
        return '-'
    
    def _extract_phone_number(self):
        """電話番号を取得"""
        try:
            if self.driver is None:
                return '-'
            
            # JavaScriptで複数の方法で取得
            js_script = """
            // ヘッダーの電話番号を最優先で探す
            const headerPhone = document.querySelector('#header-main-phone .number');
            if (headerPhone) {
                return headerPhone.innerText.trim();
            }
            
            // アコーディオンコンテンツから探す
            const bluePhones = document.querySelectorAll('.commonAccordion_content_item_desc.-blue, p.-blue');
            for (let elem of bluePhones) {
                const text = elem.innerText.trim();
                if (text && text.match(/\\d{2,4}[-\\s]?\\d{2,4}[-\\s]?\\d{3,4}/)) {
                    return text;
                }
            }
            
            // 一般的な電話番号要素から探す
            const phoneElems = document.querySelectorAll('[class*="phone"], [class*="tel"], .number');
            for (let elem of phoneElems) {
                const text = elem.innerText.trim();
                if (text && text.match(/\\d{2,4}[-\\s]?\\d{2,4}[-\\s]?\\d{3,4}/)) {
                    return text;
                }
            }
            
            return null;
            """
            
            phone = self.driver.execute_script(js_script)
            if phone:
                self.logger.info(f"電話番号取得成功: {phone}")
                return phone
            
        except Exception as e:
            self.logger.warning(f"電話番号抽出エラー: {e}")
        
        return '-'
    
    def _extract_postal_and_address(self):
        """郵便番号と住所を取得（分離版）"""
        try:
            if self.driver is None:
                return {'postal_code': '-', 'address': '-'}
            
            # 方法1: JavaScriptで直接取得（最も確実）
            js_script = """
            // 方法1: テーブル構造から取得（旧レイアウト）
            const thElements = document.querySelectorAll('th');
            for (let th of thElements) {
                if (th.innerText.includes('住所')) {
                    const td = th.nextElementSibling;
                    if (td) {
                        // 全テキストを取得
                        let fullText = td.innerText.trim();
                        
                        // 郵便番号を抽出
                        let postalCode = '';
                        const postalMatch = fullText.match(/〒(\\d{3}-\\d{4})/);
                        if (postalMatch) {
                            postalCode = postalMatch[1];
                        }
                        
                        // 住所テキストを抽出（郵便番号を除去）
                        let address = fullText.replace(/〒\\d{3}-\\d{4}\\s*/g, '');
                        address = address.split('\\n')[0].trim(); // 最初の行のみ
                        
                        return {
                            postal_code: postalCode,
                            address: address
                        };
                    }
                }
            }
            
            // 方法2: commonAccordion構造から取得（新レイアウト）
            const items = document.querySelectorAll('.commonAccordion_content_item');
            for (let item of items) {
                const title = item.querySelector('.commonAccordion_content_item_title');
                if (title && title.innerText.includes('住所')) {
                    const desc = item.querySelector('.commonAccordion_content_item_desc');
                    if (desc) {
                        let fullText = desc.innerText.trim();
                        
                        // 郵便番号を抽出
                        let postalCode = '';
                        const postalMatch = fullText.match(/〒(\\d{3}-\\d{4})/);
                        if (postalMatch) {
                            postalCode = postalMatch[1];
                        }
                        
                        // 住所テキストを抽出（郵便番号を除去）
                        let address = fullText.replace(/〒\\d{3}-\\d{4}\\s*/g, '');
                        // 「地図アプリで見る」などを除去
                        address = address.replace(/地図アプリで見る/g, '').trim();
                        address = address.split('\\n')[0].trim(); // 最初の行のみ
                        
                        return {
                            postal_code: postalCode,
                            address: address
                        };
                    }
                }
            }
            
            // 方法3: addressクラスから直接取得
            const addressElems = document.querySelectorAll('.address, .adr, [class*="address"]');
            for (let elem of addressElems) {
                let fullText = elem.innerText.trim();
                if (fullText && !fullText.includes('メール') && !fullText.includes('URL')) {
                    // 郵便番号を抽出
                    let postalCode = '';
                    const postalMatch = fullText.match(/〒(\\d{3}-\\d{4})/);
                    if (postalMatch) {
                        postalCode = postalMatch[1];
                    }
                    
                    // 住所テキストを抽出
                    let address = fullText.replace(/〒\\d{3}-\\d{4}\\s*/g, '');
                    address = address.split('\\n')[0].trim();
                    
                    if (address.length > 5) { // 短すぎる文字列を除外
                        return {
                            postal_code: postalCode,
                            address: address
                        };
                    }
                }
            }
            
            return null;
            """
            
            result = self.driver.execute_script(js_script)
            if result:
                postal_code = result.get('postal_code', '') or '-'
                address = self._clean_address(result.get('address', ''))
                
                self.logger.info(f"郵便番号取得: {postal_code}")
                self.logger.info(f"住所取得成功: {address}")
                
                return {'postal_code': postal_code, 'address': address}
            
            # 方法2: Seleniumでフォールバック取得
            return self._extract_postal_and_address_selenium_fallback()
            
        except Exception as e:
            self.logger.warning(f"郵便番号・住所抽出エラー: {e}")
            return {'postal_code': '-', 'address': '-'}
    
    def _extract_postal_and_address_selenium_fallback(self):
        """Seleniumを使った郵便番号・住所取得のフォールバック"""
        try:
            # テーブル構造から探す
            th_elements = self.driver.find_elements(By.TAG_NAME, "th")
            for th in th_elements:
                if "住所" in th.text:
                    # 隣接するtd要素を探す
                    parent_tr = th.find_element(By.XPATH, "..")
                    td = parent_tr.find_element(By.TAG_NAME, "td")
                    
                    full_text = td.text.strip()
                    
                    # 郵便番号を抽出
                    postal_code = '-'
                    postal_match = re.search(r'〒(\d{3}-\d{4})', full_text)
                    if postal_match:
                        postal_code = postal_match.group(1)
                    
                    # 住所を抽出（郵便番号を除去）
                    address = re.sub(r'〒\d{3}-\d{4}\s*', '', full_text)
                    address = self._clean_address(address)
                    
                    return {'postal_code': postal_code, 'address': address}
            
            # commonAccordion構造から探す
            items = self.driver.find_elements(By.CSS_SELECTOR, ".commonAccordion_content_item")
            for item in items:
                try:
                    title_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_title")
                    if "住所" in title_elem.text:
                        desc_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_desc")
                        full_text = desc_elem.text.strip()
                        
                        # 郵便番号を抽出
                        postal_code = '-'
                        postal_match = re.search(r'〒(\d{3}-\d{4})', full_text)
                        if postal_match:
                            postal_code = postal_match.group(1)
                        
                        # 住所を抽出
                        address = re.sub(r'〒\d{3}-\d{4}\s*', '', full_text)
                        address = self._clean_address(address)
                        
                        return {'postal_code': postal_code, 'address': address}
                except:
                    continue
            
        except Exception as e:
            self.logger.debug(f"Seleniumフォールバック失敗: {e}")
        
        return {'postal_code': '-', 'address': '-'}
    
    def _clean_address(self, raw_address):
        """住所のクリーニング処理（郵便番号は既に除去済み前提）"""
        if not raw_address or raw_address == '-':
            return raw_address
        
        try:
            address = raw_address
            
            # 不要な文字列を除去
            remove_patterns = [
                r'地図アプリで見る',
                r'大きな地図で見る',
                r'地図印刷',
                r'地図・アクセス',
                r'MAP',
                r'マップ'
            ]
            
            for pattern in remove_patterns:
                address = re.sub(pattern, '', address)
            
            # 改行を除去して最初の行のみ取得
            lines = address.strip().split('\n')
            address = lines[0].strip()
            
            # 連続するスペースを1つに
            address = re.sub(r'\s+', ' ', address)
            
            # 前後の空白を除去
            address = address.strip()
            
            # 住所として妥当な長さかチェック
            if len(address) < 5:
                return '-'
            
            return address
            
        except Exception as e:
            self.logger.warning(f"住所クリーニングエラー: {e}")
            return raw_address
    
    def _clean_phone_number(self, raw_text):
        """電話番号クリーニング処理"""
        if not raw_text or raw_text == '-':
            return raw_text
        
        try:
            lines = raw_text.strip().split('\n')
            first_line = lines[0].strip() if lines else raw_text.strip()
            
            patterns = [
                r'(0\d{1,4}-\d{1,4}-\d{3,4})',
                r'(0\d{9,10})',
                r'(050-\d{4}-\d{4})',
                r'(0120-\d{3}-\d{3})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, first_line)
                if match:
                    return match.group(1)
            
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
    
    def _get_default_detail(self, url):
        """デフォルトの店舗データ（6項目）"""
        from datetime import datetime
        return {
            'URL': url,
            '店舗名': '取得失敗',
            '電話番号': '-',
            '郵便番号': '-',
            '住所': '-',
            '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }