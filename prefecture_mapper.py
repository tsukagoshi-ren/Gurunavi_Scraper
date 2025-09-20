"""
都道府県・市区町村マッピングクラス
ぐるなびのURL生成に必要な地域情報を管理
"""

from urllib.parse import urlencode

class PrefectureMapper:
    """都道府県・市区町村マッピングクラス（全国対応版）"""
    
    def __init__(self):
        self.base_url = "https://r.gnavi.co.jp"
        
        # 都道府県コードマッピング（全国を追加）
        self.prefecture_codes = {
            '全国': 'jp',  # 全国を追加
            '北海道': 'hokkaido',
            '青森県': 'aomori',
            '岩手県': 'iwate',
            '宮城県': 'miyagi',
            '秋田県': 'akita',
            '山形県': 'yamagata',
            '福島県': 'fukushima',
            '茨城県': 'ibaraki',
            '栃木県': 'tochigi',
            '群馬県': 'gunma',
            '埼玉県': 'saitama',
            '千葉県': 'chiba',
            '東京都': 'tokyo',
            '神奈川県': 'kanagawa',
            '新潟県': 'niigata',
            '富山県': 'toyama',
            '石川県': 'ishikawa',
            '福井県': 'fukui',
            '山梨県': 'yamanashi',
            '長野県': 'nagano',
            '岐阜県': 'gifu',
            '静岡県': 'shizuoka',
            '愛知県': 'aichi',
            '三重県': 'mie',
            '滋賀県': 'shiga',
            '京都府': 'kyoto',
            '大阪府': 'osaka',
            '兵庫県': 'hyogo',
            '奈良県': 'nara',
            '和歌山県': 'wakayama',
            '鳥取県': 'tottori',
            '島根県': 'shimane',
            '岡山県': 'okayama',
            '広島県': 'hiroshima',
            '山口県': 'yamaguchi',
            '徳島県': 'tokushima',
            '香川県': 'kagawa',
            '愛媛県': 'ehime',
            '高知県': 'kochi',
            '福岡県': 'fukuoka',
            '佐賀県': 'saga',
            '長崎県': 'nagasaki',
            '熊本県': 'kumamoto',
            '大分県': 'oita',
            '宮崎県': 'miyazaki',
            '鹿児島県': 'kagoshima',
            '沖縄県': 'okinawa'
        }
        
        # 市区町村コードマッピング（主要都市）
        self.city_codes = {
            # 北海道
            '札幌市中央区': 'CWTAV0020000',
            '札幌市北区': 'CWTAV0010000',
            '札幌市東区': 'CWTAV0030000',
            '札幌市白石区': 'CWTAV0040000',
            '札幌市豊平区': 'CWTAV0050000',
            '札幌市南区': 'CWTAV0060000',
            '札幌市西区': 'CWTAV0070000',
            '札幌市厚別区': 'CWTAV0080000',
            '札幌市手稲区': 'CWTAV0090000',
            '札幌市清田区': 'CWTAV0100000',
            
            # 東京23区
            '千代田区': 'CWTAV1010000',
            '中央区': 'CWTAV1020000',
            '港区': 'CWTAV1050000',
            '新宿区': 'CWTAV1130000',
            '文京区': 'CWTAV1140000',
            '台東区': 'CWTAV1150000',
            '墨田区': 'CWTAV1160000',
            '江東区': 'CWTAV1170000',
            '品川区': 'CWTAV1180000',
            '目黒区': 'CWTAV1190000',
            '大田区': 'CWTAV1210000',
            '世田谷区': 'CWTAV1540000',
            '渋谷区': 'CWTAV1510000',
            '中野区': 'CWTAV1520000',
            '杉並区': 'CWTAV1530000',
            '豊島区': 'CWTAV1220000',
            '北区': 'CWTAV1230000',
            '荒川区': 'CWTAV1240000',
            '板橋区': 'CWTAV1250000',
            '練馬区': 'CWTAV1260000',
            '足立区': 'CWTAV1200000',
            '葛飾区': 'CWTAV1310000',
            '江戸川区': 'CWTAV1320000',
            
            # 神奈川県
            '横浜市鶴見区': 'CWTAV2310000',
            '横浜市神奈川区': 'CWTAV2320000',
            '横浜市西区': 'CWTAV2330000',
            '横浜市中区': 'CWTAV2340000',
            '横浜市南区': 'CWTAV2350000',
            '横浜市保土ケ谷区': 'CWTAV2360000',
            '横浜市磯子区': 'CWTAV2370000',
            '横浜市金沢区': 'CWTAV2380000',
            '横浜市港北区': 'CWTAV2390000',
            '横浜市戸塚区': 'CWTAV2400000',
            '横浜市港南区': 'CWTAV2410000',
            '横浜市旭区': 'CWTAV2420000',
            '横浜市緑区': 'CWTAV2430000',
            '横浜市瀬谷区': 'CWTAV2440000',
            '横浜市栄区': 'CWTAV2450000',
            '横浜市泉区': 'CWTAV2460000',
            '横浜市青葉区': 'CWTAV2470000',
            '横浜市都筑区': 'CWTAV2480000',
            
            # 愛知県
            '名古屋市千種区': 'CWTAV4500000',
            '名古屋市東区': 'CWTAV4510000',
            '名古屋市北区': 'CWTAV4520000',
            '名古屋市西区': 'CWTAV4530000',
            '名古屋市中村区': 'CWTAV4540000',
            '名古屋市中区': 'CWTAV4560000',
            '名古屋市昭和区': 'CWTAV4570000',
            '名古屋市瑞穂区': 'CWTAV4580000',
            '名古屋市熱田区': 'CWTAV4590000',
            '名古屋市中川区': 'CWTAV4600000',
            '名古屋市港区': 'CWTAV4610000',
            '名古屋市南区': 'CWTAV4620000',
            '名古屋市守山区': 'CWTAV4630000',
            '名古屋市緑区': 'CWTAV4640000',
            '名古屋市名東区': 'CWTAV4650000',
            '名古屋市天白区': 'CWTAV4660000',
            
            # 大阪府
            '大阪市都島区': 'CWTAV5480000',
            '大阪市福島区': 'CWTAV5470000',
            '大阪市此花区': 'CWTAV5460000',
            '大阪市西区': 'CWTAV5510000',
            '大阪市港区': 'CWTAV5520000',
            '大阪市大正区': 'CWTAV5530000',
            '大阪市天王寺区': 'CWTAV5540000',
            '大阪市浪速区': 'CWTAV5550000',
            '大阪市西淀川区': 'CWTAV5560000',
            '大阪市東淀川区': 'CWTAV5570000',
            '大阪市東成区': 'CWTAV5580000',
            '大阪市生野区': 'CWTAV5590000',
            '大阪市旭区': 'CWTAV5600000',
            '大阪市城東区': 'CWTAV5610000',
            '大阪市阿倍野区': 'CWTAV5620000',
            '大阪市住吉区': 'CWTAV5630000',
            '大阪市東住吉区': 'CWTAV5640000',
            '大阪市西成区': 'CWTAV5650000',
            '大阪市淀川区': 'CWTAV5660000',
            '大阪市鶴見区': 'CWTAV5670000',
            '大阪市住之江区': 'CWTAV5680000',
            '大阪市平野区': 'CWTAV5690000',
            '大阪市北区': 'CWTAV5490000',
            '大阪市中央区': 'CWTAV5500000',
            
            # 福岡県
            '福岡市東区': 'CWTAV8110000',
            '福岡市博多区': 'CWTAV8120000',
            '福岡市中央区': 'CWTAV8130000',
            '福岡市南区': 'CWTAV8140000',
            '福岡市西区': 'CWTAV8150000',
            '福岡市城南区': 'CWTAV8160000',
            '福岡市早良区': 'CWTAV8170000',
        }
        
        # 都道府県別の市区町村リスト（全国の場合は空）
        self.prefecture_cities = {
            '全国': [],  # 全国の場合は市区町村選択なし
            '北海道': ['札幌市中央区', '札幌市北区', '札幌市東区', '札幌市白石区', 
                     '札幌市豊平区', '札幌市南区', '札幌市西区', '札幌市厚別区',
                     '札幌市手稲区', '札幌市清田区'],
            '東京都': ['千代田区', '中央区', '港区', '新宿区', '文京区', '台東区',
                     '墨田区', '江東区', '品川区', '目黒区', '大田区', '世田谷区',
                     '渋谷区', '中野区', '杉並区', '豊島区', '北区', '荒川区',
                     '板橋区', '練馬区', '足立区', '葛飾区', '江戸川区'],
            '神奈川県': ['横浜市鶴見区', '横浜市神奈川区', '横浜市西区', '横浜市中区',
                      '横浜市南区', '横浜市保土ケ谷区', '横浜市磯子区', '横浜市金沢区',
                      '横浜市港北区', '横浜市戸塚区', '横浜市港南区', '横浜市旭区',
                      '横浜市緑区', '横浜市瀬谷区', '横浜市栄区', '横浜市泉区',
                      '横浜市青葉区', '横浜市都筑区'],
            '愛知県': ['名古屋市千種区', '名古屋市東区', '名古屋市北区', '名古屋市西区',
                     '名古屋市中村区', '名古屋市中区', '名古屋市昭和区', '名古屋市瑞穂区',
                     '名古屋市熱田区', '名古屋市中川区', '名古屋市港区', '名古屋市南区',
                     '名古屋市守山区', '名古屋市緑区', '名古屋市名東区', '名古屋市天白区'],
            '大阪府': ['大阪市都島区', '大阪市福島区', '大阪市此花区', '大阪市西区',
                     '大阪市港区', '大阪市大正区', '大阪市天王寺区', '大阪市浪速区',
                     '大阪市西淀川区', '大阪市東淀川区', '大阪市東成区', '大阪市生野区',
                     '大阪市旭区', '大阪市城東区', '大阪市阿倍野区', '大阪市住吉区',
                     '大阪市東住吉区', '大阪市西成区', '大阪市淀川区', '大阪市鶴見区',
                     '大阪市住之江区', '大阪市平野区', '大阪市北区', '大阪市中央区'],
            '福岡県': ['福岡市東区', '福岡市博多区', '福岡市中央区', '福岡市南区',
                     '福岡市西区', '福岡市城南区', '福岡市早良区']
        }
        
        # 他の都道府県にも空リストを設定
        for prefecture in self.prefecture_codes.keys():
            if prefecture not in self.prefecture_cities:
                self.prefecture_cities[prefecture] = []
    
    def get_prefectures(self):
        """都道府県リスト取得（全国を含む）"""
        return list(self.prefecture_codes.keys())
    
    def get_cities(self, prefecture):
        """指定都道府県の市区町村リスト取得"""
        return self.prefecture_cities.get(prefecture, [])
    
    def generate_search_url(self, prefecture, city=None, page=1):
        """
        検索URL生成（ページネーション対応）
        
        Args:
            prefecture (str): 都道府県名（「全国」を含む）
            city (str): 市区町村名（オプション）
            page (int): ページ番号（デフォルト: 1）
            
        Returns:
            str: 生成されたURL
        """
        if prefecture not in self.prefecture_codes:
            raise ValueError(f"未対応の都道府県: {prefecture}")
        
        pref_code = self.prefecture_codes[prefecture]
        
        # URLの基本部分を構築
        if city and city in self.city_codes:
            # 市区町村が指定されている場合
            city_code = self.city_codes[city]
            base_url = f"{self.base_url}/city/{city_code}/rs/"
        else:
            # 都道府県のみ、または全国の場合
            base_url = f"{self.base_url}/area/{pref_code}/rs/"
        
        # ページ番号が2以上の場合はパラメータを追加
        if page > 1:
            url = f"{base_url}?p={page}"
        else:
            url = base_url
        
        # 市区町村名が指定されているがコードがない場合はフリーワード検索
        if city and city not in self.city_codes:
            params = {'fwp': city}
            if page > 1:
                params['p'] = page
            query_string = urlencode(params)
            url = f"{self.base_url}/area/{pref_code}/rs/?{query_string}"
        
        return url
    
    def generate_next_page_url(self, current_url, next_page):
        """
        現在のURLから次のページのURLを生成
        
        Args:
            current_url (str): 現在のURL
            next_page (int): 次のページ番号
            
        Returns:
            str: 次ページのURL
        """
        # URLからクエリパラメータを除去
        base_url = current_url.split('?')[0]
        
        # rs/で終わっていない場合は追加
        if not base_url.endswith('/rs/'):
            if '/rs' in base_url:
                base_url = base_url.replace('/rs', '/rs/')
            else:
                base_url = base_url.rstrip('/') + '/rs/'
        
        # ページパラメータを追加
        if next_page > 1:
            return f"{base_url}?p={next_page}"
        else:
            return base_url
    
    def parse_url_components(self, url):
        """URLから都道府県・市区町村情報を抽出"""
        import re
        
        # 全国の場合
        if '/area/jp/' in url:
            return {'prefecture': '全国', 'city': None}
        
        # 市区町村コード抽出
        city_match = re.search(r'/city/([A-Z0-9]+)/', url)
        if city_match:
            city_code = city_match.group(1)
            for city, code in self.city_codes.items():
                if code == city_code:
                    # 都道府県を逆引き
                    for pref, cities in self.prefecture_cities.items():
                        if city in cities:
                            return {'prefecture': pref, 'city': city}
        
        # 都道府県コード抽出
        pref_match = re.search(r'/area/([a-z]+)/', url)
        if pref_match:
            pref_code = pref_match.group(1)
            for pref, code in self.prefecture_codes.items():
                if code == pref_code:
                    return {'prefecture': pref, 'city': None}
        
        return {'prefecture': None, 'city': None}
    
    def extract_page_number(self, url):
        """URLからページ番号を抽出"""
        import re
        
        # ?p=2 のようなパラメータからページ番号を抽出
        page_match = re.search(r'[?&]p=(\d+)', url)
        if page_match:
            return int(page_match.group(1))
        return 1
    
    def is_valid_prefecture(self, prefecture):
        """都道府県の有効性チェック"""
        return prefecture in self.prefecture_codes
    
    def is_valid_city(self, prefecture, city):
        """市区町村の有効性チェック"""
        cities = self.get_cities(prefecture)
        return city in cities
    
    def get_area_display_name(self, prefecture, city=None):
        """表示用のエリア名を取得"""
        if prefecture == '全国':
            return '全国'
        elif city:
            return f"{prefecture} {city}"
        else:
            return prefecture