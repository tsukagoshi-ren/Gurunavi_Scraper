"""
改善版：ぐるなび店舗データ抽出メソッド
ラベルベースでの確実な情報取得
"""

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import re
import logging

class GurunaviLabelBasedExtractor:
    """ラベルベースでぐるなび店舗情報を抽出するクラス"""
    
    def __init__(self, driver, logger=None):
        self.driver = driver
        self.logger = logger or logging.getLogger(__name__)
    
    def extract_store_data(self, url):
        """店舗詳細データをラベルベースで抽出"""
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
                '取得日時': self._get_current_datetime()
            }
            
            # 各項目をラベルベースで抽出
            detail['店舗名'] = self._extract_shop_name()
            detail['電話番号'] = self._extract_phone_by_label()
            detail['住所'] = self._extract_address_by_label()
            detail['ジャンル'] = self._extract_genre_by_label()
            detail['営業時間'] = self._extract_business_hours_by_label()
            detail['定休日'] = self._extract_holiday_by_label()
            detail['クレジットカード'] = self._extract_credit_card_by_label()
            
            return detail
            
        except Exception as e:
            self.logger.error(f"データ抽出エラー: {e}")
            return self._get_default_detail(url)
    
    def _extract_shop_name(self):
        """店舗名を抽出"""
        try:
            # h1タグから店舗名を取得（最も確実）
            h1_elements = self.driver.find_elements(By.TAG_NAME, "h1")
            for h1 in h1_elements:
                text = h1.text.strip()
                if text and not any(word in text for word in ['ぐるなび', '検索', 'ログイン']):
                    self.logger.debug(f"店舗名取得成功: h1 = {text}")
                    return text
            
            # titleタグから取得
            title = self.driver.title
            if title:
                # "店舗名 - ぐるなび" のような形式から店舗名を抽出
                name = title.split(' - ')[0].split('｜')[0].strip()
                if name and name != 'ぐるなび':
                    self.logger.debug(f"店舗名取得成功: title = {name}")
                    return name
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"店舗名抽出エラー: {e}")
            return '-'
    
    def _extract_phone_by_label(self):
        """ラベルベースで電話番号を抽出"""
        try:
            # commonAccordion_content_item構造から取得
            items = self.driver.find_elements(By.CSS_SELECTOR, ".commonAccordion_content_item")
            
            for item in items:
                try:
                    # タイトル要素を探す
                    title_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_title")
                    if title_elem and "電話" in title_elem.text:
                        # 説明要素から電話番号を取得
                        desc_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_desc")
                        
                        # 青い文字の電話番号を優先的に取得
                        try:
                            phone_elem = desc_elem.find_element(By.CSS_SELECTOR, "p.-blue")
                            phone = phone_elem.text.strip()
                            if self._is_valid_phone_number(phone):
                                self.logger.debug(f"電話番号取得成功: {phone}")
                                return phone
                        except:
                            pass
                        
                        # その他の電話番号パターンを探す
                        text = desc_elem.text.strip()
                        phone_match = re.search(r'(\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,4})', text)
                        if phone_match:
                            phone = phone_match.group(1)
                            if self._is_valid_phone_number(phone):
                                self.logger.debug(f"電話番号取得成功: {phone}")
                                return phone
                except:
                    continue
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"電話番号抽出エラー: {e}")
            return '-'
    
    def _extract_address_by_label(self):
        """ラベルベースで住所を抽出"""
        try:
            # commonAccordion_content_item構造から取得
            items = self.driver.find_elements(By.CSS_SELECTOR, ".commonAccordion_content_item")
            
            for item in items:
                try:
                    title_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_title")
                    if title_elem and "住所" in title_elem.text:
                        desc_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_desc")
                        address = desc_elem.text.strip()
                        
                        # 郵便番号を除去
                        address = re.sub(r'〒\d{3}-\d{4}\s*', '', address)
                        # 「地図アプリで見る」などのリンクテキストを除去
                        address = address.replace('地図アプリで見る', '').strip()
                        
                        if address:
                            self.logger.debug(f"住所取得成功: {address}")
                            return address
                except:
                    continue
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"住所抽出エラー: {e}")
            return '-'
    
    def _extract_genre_by_label(self):
        """ラベルベースでジャンルを抽出"""
        try:
            # 「お店のウリ」から取得を試みる
            items = self.driver.find_elements(By.CSS_SELECTOR, ".commonAccordion_content_item")
            
            for item in items:
                try:
                    title_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_title")
                    title_text = title_elem.text.strip()
                    
                    # ジャンル関連のラベルを探す
                    if any(label in title_text for label in ["お店のウリ", "ジャンル", "料理", "カテゴリ"]):
                        desc_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_desc")
                        
                        # リスト形式の場合
                        try:
                            li_elements = desc_elem.find_elements(By.TAG_NAME, "li")
                            if li_elements:
                                genres = [li.text.strip() for li in li_elements if li.text.strip()]
                                if genres:
                                    genre_text = "、".join(genres[:3])  # 最初の3つを取得
                                    self.logger.debug(f"ジャンル取得成功: {genre_text}")
                                    return genre_text
                        except:
                            pass
                        
                        # テキスト形式の場合
                        text = desc_elem.text.strip()
                        if text:
                            # 複数行の場合は最初の行を取得
                            genre_text = text.split('\n')[0].strip()
                            self.logger.debug(f"ジャンル取得成功: {genre_text}")
                            return genre_text
                except:
                    continue
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"ジャンル抽出エラー: {e}")
            return '-'
    
    def _extract_business_hours_by_label(self):
        """ラベルベースで営業時間を抽出"""
        try:
            items = self.driver.find_elements(By.CSS_SELECTOR, ".commonAccordion_content_item")
            
            for item in items:
                try:
                    title_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_title")
                    if title_elem and "営業時間" in title_elem.text:
                        desc_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_desc")
                        hours_text = desc_elem.text.strip()
                        
                        if hours_text:
                            # 改行を半角スペースで置換して整形
                            hours_text = hours_text.replace('\n', ' ')
                            # （L.O.14:00）のような形式を保持
                            hours_text = re.sub(r'\s+', ' ', hours_text)
                            
                            self.logger.debug(f"営業時間取得成功: {hours_text}")
                            return hours_text
                except:
                    continue
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"営業時間抽出エラー: {e}")
            return '-'
    
    def _extract_holiday_by_label(self):
        """ラベルベースで定休日を抽出"""
        try:
            items = self.driver.find_elements(By.CSS_SELECTOR, ".commonAccordion_content_item")
            
            for item in items:
                try:
                    title_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_title")
                    if title_elem and "定休日" in title_elem.text:
                        desc_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_desc")
                        holiday_text = desc_elem.text.strip()
                        
                        if holiday_text:
                            # 改行を読点で置換
                            holiday_text = holiday_text.replace('\n', '、')
                            # 複数の句読点を整理
                            holiday_text = re.sub(r'[、，,]+', '、', holiday_text)
                            
                            self.logger.debug(f"定休日取得成功: {holiday_text}")
                            return holiday_text
                except:
                    continue
            
            return '-'
            
        except Exception as e:
            self.logger.warning(f"定休日抽出エラー: {e}")
            return '-'
    
    def _extract_credit_card_by_label(self):
        """ラベルベースでクレジットカード情報を抽出"""
        try:
            items = self.driver.find_elements(By.CSS_SELECTOR, ".commonAccordion_content_item")
            
            for item in items:
                try:
                    title_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_title")
                    title_text = title_elem.text.strip()
                    
                    # クレジットカード関連のラベルを探す
                    if any(label in title_text for label in ["キャッシュレス", "クレジット", "カード", "支払", "決済"]):
                        desc_elem = item.find_element(By.CSS_SELECTOR, ".commonAccordion_content_item_desc")
                        
                        # カードブランドの画像があるか確認
                        try:
                            img_elements = desc_elem.find_elements(By.TAG_NAME, "img")
                            card_brands = []
                            
                            for img in img_elements:
                                alt_text = img.get_attribute("alt")
                                if alt_text and "logo" in alt_text.lower():
                                    brand = alt_text.replace("_logo", "").upper()
                                    card_brands.append(brand)
                            
                            if card_brands:
                                card_info = "利用可（" + "、".join(card_brands) + "）"
                                self.logger.debug(f"クレジットカード情報取得成功: {card_info}")
                                return card_info
                        except:
                            pass
                        
                        # テキストから判定
                        text = desc_elem.text.strip()
                        if text:
                            if any(word in text for word in ["VISA", "MasterCard", "JCB", "AMEX", "クレジット"]):
                                # カード会社名を抽出
                                cards = []
                                if "VISA" in text: cards.append("VISA")
                                if "Master" in text: cards.append("MasterCard")
                                if "JCB" in text: cards.append("JCB")
                                if "AMEX" in text or "American Express" in text: cards.append("AMEX")
                                
                                if cards:
                                    card_info = "利用可（" + "、".join(cards) + "）"
                                else:
                                    card_info = "利用可"
                                
                                self.logger.debug(f"クレジットカード情報取得成功: {card_info}")
                                return card_info
                            elif "現金のみ" in text:
                                return "利用不可（現金のみ）"
                except:
                    continue
            
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
            'ジャンル': '-',
            '営業時間': '-',
            '定休日': '-',
            'クレジットカード': '-',
            '取得日時': self._get_current_datetime()
        }


# scraper_engine.pyの該当メソッドを置き換える例
def integrate_label_based_extractor(self):
    """
    scraper_engine.pyのImprovedScraperEngineクラスに統合する場合の例
    _extract_gurunavi_store_dataメソッドを以下のように置き換える
    """
    
    def _extract_gurunavi_store_data(self, url):
        """ぐるなび店舗データ抽出（ラベルベース版）"""
        try:
            # ラベルベース抽出器を使用
            extractor = GurunaviLabelBasedExtractor(self.driver, self.logger)
            return extractor.extract_store_data(url)
            
        except Exception as e:
            self.logger.error(f"ぐるなびデータ抽出エラー: {e}")
            return self._get_default_detail(url)