"""
改善版：ぐるなび店舗データ抽出
住所・営業時間・定休日の取得を改善
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import re
import time
import logging

class GurunaviMultiApproachExtractor:
    """改善版ぐるなび店舗情報抽出クラス"""
    
    def __init__(self, driver, logger=None):
        self.driver = driver
        self.logger = logger or logging.getLogger(__name__)
        self.wait = WebDriverWait(driver, 15)
    
    def extract_store_data(self, url):
        """店舗データを抽出（ジャンル・クレカ除外版）"""
        try:
            # 基本情報の初期化
            detail = {
                'URL': url,
                '店舗名': '-',
                '電話番号': '-',
                '住所': '-',
                '営業時間': '-',
                '定休日': '-',
                '取得日時': self._get_current_datetime()
            }
            
            # ページが完全に読み込まれるのを待つ
            self._ensure_page_loaded()
            
            # 各項目を取得
            detail['店舗名'] = self._extract_shop_name()
            detail['電話番号'] = self._extract_phone_number()
            detail['住所'] = self._extract_address_improved()
            detail['営業時間'] = self._extract_business_hours_improved()
            detail['定休日'] = self._extract_holiday_improved()
            
            self.logger.info(f"取得結果: {detail}")
            return detail
            
        except Exception as e:
            self.logger.error(f"データ抽出エラー: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return self._get_default_detail(url)
    
    def _ensure_page_loaded(self):
        """ページが完全に読み込まれることを確認"""
        try:
            # 複数の方法で読み込み完了を確認
            
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
    
    def _extract_shop_name(self):
        """店舗名を取得（既存メソッドで成功しているので維持）"""
        try:
            # JavaScriptで取得
            js_script = """
            const h1 = document.querySelector('h1');
            if (h1) return h1.innerText.trim();
            return null;
            """
            name = self.driver.execute_script(js_script)
            if name and 'ぐるなび' not in name:
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
        """電話番号を取得（既存メソッドで成功しているので維持）"""
        try:
            # JavaScriptで取得
            js_script = """
            // 電話番号を探す複数の方法
            const patterns = [
                '.commonAccordion_content_item_desc.-blue',
                'p.-blue',
                '[class*="phone"]',
                '[class*="tel"]'
            ];
            
            for (let pattern of patterns) {
                const elems = document.querySelectorAll(pattern);
                for (let elem of elems) {
                    const text = elem.innerText.trim();
                    if (text && text.match(/\\d{2,4}[-\\s]?\\d{2,4}[-\\s]?\\d{3,4}/)) {
                        return text;
                    }
                }
            }
            
            // ラベルベースで探す
            const items = document.querySelectorAll('.commonAccordion_content_item');
            for (let item of items) {
                const title = item.querySelector('.commonAccordion_content_item_title');
                if (title && title.innerText.includes('電話')) {
                    const desc = item.querySelector('.commonAccordion_content_item_desc');
                    if (desc) {
                        const phoneElem = desc.querySelector('.-blue') || desc.querySelector('p');
                        if (phoneElem) return phoneElem.innerText.trim();
                    }
                }
            }
            
            return null;
            """
            
            phone = self.driver.execute_script(js_script)
            if phone and self._is_valid_phone_number(phone):
                return phone
            
        except Exception as e:
            self.logger.warning(f"電話番号抽出エラー: {e}")
        
        return '-'
    
    def _extract_address_improved(self):
        """住所を改善された方法で取得"""
        try:
            # 方法1: JavaScriptで詳細に取得
            js_script = """
            // 住所ラベルを含む要素を探す
            const items = document.querySelectorAll('.commonAccordion_content_item');
            
            for (let item of items) {
                const title = item.querySelector('.commonAccordion_content_item_title');
                if (title && title.innerText.includes('住所')) {
                    const descContainer = item.querySelector('.commonAccordion_content_item_desc');
                    if (descContainer) {
                        // 住所のテキストを含むp要素を探す（最初のp要素）
                        const paragraphs = descContainer.querySelectorAll('p');
                        for (let p of paragraphs) {
                            const text = p.innerText.trim();
                            // 電話番号パターンを含まない、かつ「地図」を含まないテキスト
                            if (text && 
                                !text.match(/\\d{2,4}[-\\s]?\\d{2,4}[-\\s]?\\d{3,4}/) &&
                                !text.includes('地図')) {
                                
                                // 郵便番号を除去
                                let address = text.replace(/〒\\d{3}-\\d{4}\\s*/, '');
                                // 都道府県名が含まれているか確認
                                const prefectures = ['北海道', '青森県', '岩手県', '宮城県', '秋田県',
                                    '山形県', '福島県', '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県',
                                    '東京都', '神奈川県', '新潟県', '富山県', '石川県', '福井県', '山梨県',
                                    '長野県', '岐阜県', '静岡県', '愛知県', '三重県', '滋賀県', '京都府',
                                    '大阪府', '兵庫県', '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県',
                                    '広島県', '山口県', '徳島県', '香川県', '愛媛県', '高知県', '福岡県',
                                    '佐賀県', '長崎県', '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'];
                                
                                const hasPrefecture = prefectures.some(pref => address.includes(pref));
                                if (hasPrefecture || address.includes('区') || address.includes('市')) {
                                    return address;
                                }
                            }
                        }
                        
                        // 上記で見つからない場合、descContainer全体のテキストから抽出
                        const fullText = descContainer.innerText;
                        const lines = fullText.split('\\n');
                        for (let line of lines) {
                            const cleaned = line.trim();
                            if (cleaned && 
                                !cleaned.match(/\\d{2,4}[-\\s]?\\d{2,4}[-\\s]?\\d{3,4}/) &&
                                !cleaned.includes('地図') &&
                                cleaned.length > 5) {
                                
                                let address = cleaned.replace(/〒\\d{3}-\\d{4}\\s*/, '');
                                if (address) return address;
                            }
                        }
                    }
                }
            }
            
            return null;
            """
            
            address = self.driver.execute_script(js_script)
            if address:
                self.logger.info(f"住所取得成功: {address}")
                return address
            
            # 方法2: 直接要素を探索
            elements = self.driver.find_elements(By.CLASS_NAME, "commonAccordion_content_item")
            for elem in elements:
                try:
                    title = elem.find_element(By.CLASS_NAME, "commonAccordion_content_item_title")
                    if "住所" in title.text:
                        desc = elem.find_element(By.CLASS_NAME, "commonAccordion_content_item_desc")
                        
                        # p要素を個別にチェック
                        p_elements = desc.find_elements(By.TAG_NAME, "p")
                        for p in p_elements:
                            text = p.text.strip()
                            # 電話番号でない、地図リンクでない
                            if (text and 
                                not re.search(r'\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,4}', text) and
                                '地図' not in text):
                                
                                # 郵便番号を除去
                                address = re.sub(r'〒\d{3}-\d{4}\s*', '', text).strip()
                                if address:
                                    self.logger.info(f"住所取得成功（要素探索）: {address}")
                                    return address
                except:
                    continue
            
        except Exception as e:
            self.logger.warning(f"住所抽出エラー: {e}")
        
        return '-'
    
    def _extract_business_hours_improved(self):
        """営業時間を改善された方法で取得"""
        try:
            # JavaScriptで取得
            js_script = """
            const items = document.querySelectorAll('.commonAccordion_content_item');
            
            for (let item of items) {
                const title = item.querySelector('.commonAccordion_content_item_title');
                if (title && title.innerText.includes('営業時間')) {
                    const desc = item.querySelector('.commonAccordion_content_item_desc');
                    if (desc) {
                        // 全てのテキストを取得して整形
                        let hours = desc.innerText.trim();
                        // 改行を半角スペースに置換
                        hours = hours.replace(/\\n+/g, ' ');
                        // 連続するスペースを1つに
                        hours = hours.replace(/\\s+/g, ' ');
                        return hours;
                    }
                }
            }
            
            return null;
            """
            
            hours = self.driver.execute_script(js_script)
            if hours:
                self.logger.info(f"営業時間取得成功: {hours}")
                return hours
            
            # 方法2: 要素を直接探索
            elements = self.driver.find_elements(By.CLASS_NAME, "commonAccordion_content_item")
            for elem in elements:
                try:
                    title = elem.find_element(By.CLASS_NAME, "commonAccordion_content_item_title")
                    if "営業時間" in title.text:
                        desc = elem.find_element(By.CLASS_NAME, "commonAccordion_content_item_desc")
                        text = desc.text.strip()
                        if text:
                            # 整形
                            text = text.replace('\n', ' ')
                            text = re.sub(r'\s+', ' ', text)
                            self.logger.info(f"営業時間取得成功（要素探索）: {text}")
                            return text
                except:
                    continue
            
        except Exception as e:
            self.logger.warning(f"営業時間抽出エラー: {e}")
        
        return '-'
    
    def _extract_holiday_improved(self):
        """定休日を改善された方法で取得"""
        try:
            # JavaScriptで取得
            js_script = """
            const items = document.querySelectorAll('.commonAccordion_content_item');
            
            for (let item of items) {
                const title = item.querySelector('.commonAccordion_content_item_title');
                if (title && title.innerText.includes('定休日')) {
                    const desc = item.querySelector('.commonAccordion_content_item_desc');
                    if (desc) {
                        // 全てのテキストを取得
                        let holiday = desc.innerText.trim();
                        // 改行を読点に置換
                        holiday = holiday.replace(/\\n+/g, '、');
                        // 連続する読点を1つに
                        holiday = holiday.replace(/[、，,]+/g, '、');
                        return holiday;
                    }
                }
            }
            
            return null;
            """
            
            holiday = self.driver.execute_script(js_script)
            if holiday:
                self.logger.info(f"定休日取得成功: {holiday}")
                return holiday
            
            # 方法2: 要素を直接探索
            elements = self.driver.find_elements(By.CLASS_NAME, "commonAccordion_content_item")
            for elem in elements:
                try:
                    title = elem.find_element(By.CLASS_NAME, "commonAccordion_content_item_title")
                    if "定休日" in title.text:
                        desc = elem.find_element(By.CLASS_NAME, "commonAccordion_content_item_desc")
                        text = desc.text.strip()
                        if text:
                            # 整形
                            text = text.replace('\n', '、')
                            text = re.sub(r'[、，,]+', '、', text)
                            self.logger.info(f"定休日取得成功（要素探索）: {text}")
                            return text
                except:
                    continue
            
        except Exception as e:
            self.logger.warning(f"定休日抽出エラー: {e}")
        
        return '-'
    
    def _is_valid_phone_number(self, phone_str):
        """電話番号の妥当性チェック"""
        if not phone_str:
            return False
        
        # 数字とハイフンのみ抽出
        cleaned = re.sub(r'[^\d-]', '', str(phone_str))
        
        # 10-11桁の数字があるかチェック
        digits_only = cleaned.replace('-', '')
        return 10 <= len(digits_only) <= 11
    
    def _get_current_datetime(self):
        """現在日時を取得"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _get_default_detail(self, url):
        """デフォルトの店舗データ"""
        return {
            'URL': url,
            '店舗名': '取得失敗',
            '電話番号': '-',
            '住所': '-',
            '営業時間': '-',
            '定休日': '-',
            '取得日時': self._get_current_datetime()
        }

    # scraper_engine.pyへの統合例
    def integrate_improved_extractor(self):
        """
        scraper_engine.pyのImprovedScraperEngineクラスに統合
        """
        
        def _extract_gurunavi_store_data(self, url):
            """ぐるなび店舗データ抽出（改善版）"""
            try:
                # 改善版抽出器を使用
                extractor = GurunaviImprovedExtractor(self.driver, self.logger)
                return extractor.extract_store_data(url)
                
            except Exception as e:
                self.logger.error(f"ぐるなびデータ抽出エラー: {e}")
                return self._get_default_detail(url)