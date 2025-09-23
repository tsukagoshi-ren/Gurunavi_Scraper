"""
改善版：ぐるなび店舗データ抽出
ヘッダー部分からの電話番号取得対応
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import re
import time
import logging

class GurunaviMultiApproachExtractor:
    """改善版ぐるなび店舗情報抽出クラス（ヘッダー対応）"""
    
    def __init__(self, driver, logger=None):
        self.driver = driver
        self.logger = logger or logging.getLogger(__name__)
        # driver が None でないことを確認
        if self.driver is None:
            raise ValueError("Driver cannot be None")
        self.wait = WebDriverWait(driver, 15)
    
    def extract_store_data_multi(self, url):
        """店舗データを抽出（4項目のみ）"""
        try:
            from datetime import datetime
            
            # driver の存在確認
            if self.driver is None:
                self.logger.error("Driver is None in extract_store_data_multi")
                return self._get_default_detail(url)
            
            # 基本情報の初期化（4項目のみ）
            detail = {
                'URL': url,
                '店舗名': '-',
                '電話番号': '-',
                '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # ページが完全に読み込まれるのを待つ
            self._ensure_page_loaded()
            
            # 店舗名を取得（ヘッダー優先）
            detail['店舗名'] = self._extract_shop_name_with_header()
            
            # 電話番号を取得してクリーニング（ヘッダー優先）
            raw_phone = self._extract_phone_number_with_header()
            
            # 生データログ出力
            if raw_phone and raw_phone != '-':
                self.logger.info(f"=== 電話番号生データ（クリーニング前） ===")
                self.logger.info(f"URL: {url}")
                self.logger.info(f"生データ: '{raw_phone}'")
                self.logger.info(f"文字数: {len(raw_phone)}")
                self.logger.info("=" * 40)
            
            detail['電話番号'] = self._clean_phone_number(raw_phone)
            
            self.logger.info(f"取得結果: {detail}")
            return detail
            
        except Exception as e:
            self.logger.error(f"データ抽出エラー: {e}")
            return self._get_default_detail(url)
    
    def _ensure_page_loaded(self):
        """ページが完全に読み込まれることを確認"""
        try:
            # driver の存在確認
            if self.driver is None:
                self.logger.error("Driver is None in _ensure_page_loaded")
                return
                
            # 1. JavaScriptの読み込み完了を待つ
            self.driver.execute_script("return document.readyState") == "complete"
            
            # 2. スクロールして遅延読み込みをトリガー
            self.driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 1000);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # 3. アコーディオンが存在する場合は展開を試みる
            self._try_expand_accordions()
            
        except Exception as e:
            self.logger.warning(f"ページ読み込み確認エラー: {e}")
    
    def _try_expand_accordions(self):
        """アコーディオンメニューを展開する"""
        try:
            # driver の存在確認
            if self.driver is None:
                return
                
            # アコーディオンのトグルボタンを探してクリック
            accordion_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                "[class*='accordion'][class*='button'], [class*='accordion'][class*='trigger'], .js-accordion-trigger")
            
            for button in accordion_buttons[:5]:  # 最初の5個まで
                try:
                    if button.is_displayed():
                        self.driver.execute_script("arguments[0].click();", button)
                        time.sleep(0.3)
                except:
                    continue
            
        except Exception as e:
            self.logger.debug(f"アコーディオン展開試行: {e}")
    
    def _extract_shop_name_with_header(self):
        """店舗名を取得（ヘッダー優先）"""
        try:
            # driver の存在確認
            if self.driver is None:
                self.logger.error("Driver is None in _extract_shop_name_with_header")
                return '-'
            
            # 方法1: ヘッダーから取得（最優先）
            js_script_header = """
            // ヘッダーの店舗名を探す
            const headerName = document.querySelector('#header-main-name a');
            if (headerName) {
                const name = headerName.innerText.trim();
                console.log('ヘッダーから店舗名取得:', name);
                return name;
            }
            
            // h1タグから取得
            const h1 = document.querySelector('h1');
            if (h1) {
                const name = h1.innerText.trim();
                console.log('h1から店舗名取得:', name);
                return name;
            }
            
            return null;
            """
            
            name = self.driver.execute_script(js_script_header)
            if name and 'ぐるなび' not in name:
                self.logger.info(f"店舗名取得成功（ヘッダー/h1）: {name}")
                return name
            
            # 方法2: titleタグから取得
            title = self.driver.title
            if title:
                name = title.split(' - ')[0].split('｜')[0].strip()
                if name and name != 'ぐるなび':
                    self.logger.info(f"店舗名取得成功（title）: {name}")
                    return name
            
        except Exception as e:
            self.logger.warning(f"店舗名抽出エラー: {e}")
        
        return '-'
    
    def _extract_phone_number_with_header(self):
        """電話番号を取得（ヘッダー優先）"""
        try:
            # driver の存在確認
            if self.driver is None:
                self.logger.error("Driver is None in _extract_phone_number_with_header")
                return '-'
            
            # JavaScriptで複数の方法で取得
            js_script = """
            // 方法1: ヘッダーの電話番号を最優先で探す
            const headerPhone = document.querySelector('#header-main-phone .number');
            if (headerPhone) {
                const phone = headerPhone.innerText.trim();
                console.log('ヘッダーから電話番号取得:', phone);
                return {
                    source: 'header',
                    phone: phone,
                    raw: headerPhone.innerText
                };
            }
            
            // 方法2: header-main-phone-info から探す
            const headerPhoneInfo = document.querySelector('#header-main-phone-info .number');
            if (headerPhoneInfo) {
                const phone = headerPhoneInfo.innerText.trim();
                console.log('ヘッダー情報から電話番号取得:', phone);
                return {
                    source: 'header-info',
                    phone: phone,
                    raw: headerPhoneInfo.innerText
                };
            }
            
            // 方法3: アコーディオンコンテンツから探す（青い文字）
            const bluePhones = document.querySelectorAll('.commonAccordion_content_item_desc.-blue, p.-blue');
            for (let elem of bluePhones) {
                const text = elem.innerText.trim();
                if (text && text.match(/\\d{2,4}[-\\s]?\\d{2,4}[-\\s]?\\d{3,4}/)) {
                    console.log('青い文字から電話番号取得:', text);
                    return {
                        source: 'blue-text',
                        phone: text,
                        raw: elem.innerText
                    };
                }
            }
            
            // 方法4: 一般的な電話番号要素から探す
            const patterns = [
                '[class*="phone"]',
                '[class*="tel"]',
                '.number'
            ];
            
            for (let pattern of patterns) {
                const elems = document.querySelectorAll(pattern);
                for (let elem of elems) {
                    const text = elem.innerText.trim();
                    if (text && text.match(/\\d{2,4}[-\\s]?\\d{2,4}[-\\s]?\\d{3,4}/)) {
                        console.log('パターンマッチから電話番号取得:', text, 'セレクタ:', pattern);
                        return {
                            source: pattern,
                            phone: text,
                            raw: elem.innerText
                        };
                    }
                }
            }
            
            // 方法5: ラベルベースで探す（最終手段）
            const items = document.querySelectorAll('.commonAccordion_content_item');
            for (let item of items) {
                const title = item.querySelector('.commonAccordion_content_item_title');
                if (title && title.innerText.includes('電話')) {
                    const desc = item.querySelector('.commonAccordion_content_item_desc');
                    if (desc) {
                        const phoneElem = desc.querySelector('.-blue') || desc.querySelector('p');
                        if (phoneElem) {
                            const phone = phoneElem.innerText.trim();
                            console.log('ラベルベースから電話番号取得:', phone);
                            return {
                                source: 'label-based',
                                phone: phone,
                                raw: phoneElem.innerText
                            };
                        }
                    }
                }
            }
            
            return null;
            """
            
            result = self.driver.execute_script(js_script)
            
            if result:
                phone = result.get('phone', '')
                source = result.get('source', 'unknown')
                raw = result.get('raw', phone)
                
                self.logger.info(f"電話番号取得成功 - ソース: {source}")
                self.logger.debug(f"生データ: '{raw}'")
                
                if phone and self._is_valid_phone_number(phone):
                    return phone
                elif raw:
                    # 生データから電話番号部分を抽出
                    extracted = self._extract_phone_from_raw(raw)
                    if extracted:
                        return extracted
            
            # Seleniumによるフォールバック
            self.logger.debug("JavaScriptで取得失敗、Seleniumで再試行")
            
            # ヘッダーから直接取得を試みる
            try:
                header_phone = self.driver.find_element(By.CSS_SELECTOR, "#header-main-phone .number")
                if header_phone:
                    phone_text = header_phone.text.strip()
                    self.logger.info(f"Seleniumでヘッダーから電話番号取得: {phone_text}")
                    return phone_text
            except NoSuchElementException:
                pass
            
            # その他の要素から取得
            try:
                phone_elem = self.driver.find_element(By.CSS_SELECTOR, "p.-blue, .number")
                if phone_elem:
                    return phone_elem.text.strip()
            except NoSuchElementException:
                pass
            
        except Exception as e:
            self.logger.warning(f"電話番号抽出エラー: {e}")
        
        return '-'
    
    def _extract_phone_from_raw(self, raw_text):
        """生テキストから電話番号部分を抽出"""
        if not raw_text:
            return None
        
        # 電話番号パターン
        patterns = [
            r'(0\d{1,4}-\d{1,4}-\d{3,4})',
            r'(0\d{9,10})',
            r'(050-\d{4}-\d{4})',
            r'(0120-\d{3}-\d{3})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, raw_text)
            if match:
                phone = match.group(1)
                self.logger.debug(f"生データから電話番号抽出: '{raw_text}' → '{phone}'")
                return phone
        
        return None
    
    def _is_valid_phone_number(self, phone_str):
        """電話番号の妥当性チェック（追加メソッド）"""
        if not phone_str:
            return False
        
        # 数字とハイフンのみ抽出
        cleaned = re.sub(r'[^\d-]', '', str(phone_str))
        
        # 10-11桁の数字があるかチェック
        digits_only = cleaned.replace('-', '')
        return 10 <= len(digits_only) <= 11
    
    def _clean_phone_number(self, raw_text):
        """電話番号クリーニング処理"""
        if not raw_text or raw_text == '-':
            return raw_text
        
        try:
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
            
            # 電話番号として妥当な場合はそのまま返す
            if self._is_valid_phone_number(first_line):
                return first_line
            
            return raw_text
            
        except Exception as e:
            self.logger.warning(f"電話番号クリーニングエラー: {e}")
            return raw_text
    
    def _get_current_datetime(self):
        """現在日時を取得"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _get_default_detail(self, url):
        """デフォルトの店舗データ"""
        from datetime import datetime
        return {
            'URL': url,
            '店舗名': '取得失敗',
            '電話番号': '-',
            '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


# scraper_engine.pyの該当メソッドを置き換える例
def integrate_improved_extractor(self):
    """
    scraper_engine.pyのImprovedScraperEngineクラスに統合
    """
    
    def _extract_gurunavi_store_data(self, url):
        """ぐるなび店舗データ抽出（ヘッダー対応版）"""
        try:
            # 改善版抽出器を使用
            extractor = GurunaviMultiApproachExtractor(self.driver, self.logger)
            return extractor.extract_store_data_multi(url)
            
        except Exception as e:
            self.logger.error(f"ぐるなびデータ抽出エラー: {e}")
            return self._get_default_detail(url)