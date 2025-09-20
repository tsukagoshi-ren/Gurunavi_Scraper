"""
都道府県・おすすめエリアマッピングクラス
ぐるなびのURL生成に必要な地域情報を管理
市区町村の代わりにおすすめエリアを使用
"""

from urllib.parse import urlencode

class PrefectureMapper:
    """都道府県・おすすめエリアマッピングクラス"""
    
    def __init__(self):
        self.base_url = "https://r.gnavi.co.jp"
        
        # 都道府県コードマッピング（全国を追加）
        self.prefecture_codes = {
            '全国': 'jp',
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
        
        # おすすめエリアマッピング（エリア名: エリアコード）
        self.area_codes = {}
        
        # 都道府県別のおすすめエリアリスト
        self.prefecture_areas = {
            '全国': [],
            
            '北海道': {
                '札幌すすきの': 'aream5909',
                '札幌駅': 'aream5502',
                '函館': 'aream5702',
                '札幌大通・狸小路': 'aream5504',
                '旭川': 'aream5800',
                '帯広・十勝': 'aream5902',
                '琴似・西区': 'aream5524',
                '北区（北24条・麻生）': 'aream5582',
                '釧路・阿寒': 'aream5904',
                '東区（元町・栄町）': 'aream5586'
            },
            
            '青森県': {
                '青森市': 'aream6102',
                '八戸': 'aream6112',
                '弘前': 'aream6104',
                '五所川原・中泊': 'aream6106',
                '三沢': 'aream6109',
                '十和田': 'aream6107',
                'むつ市・大間・野辺地': 'aream6434'
            },
            
            '岩手県': {
                '盛岡': 'aream6152',
                '花巻': 'aream6172',
                '一関・平泉': 'aream6164',
                '奥州・金ケ崎': 'aream6163',
                '北上・西和賀': 'aream6174',
                '釜石・大槌': 'aream6183',
                '八幡平・滝沢・紫波': 'aream6162',
                '大船渡・陸前高田・住田': 'aream6184',
                '洋野・久慈・普代': 'aream6181',
                '岩泉・宮古・山田': 'aream6182'
            },
            
            '宮城県': {
                '仙台': 'aream6202',
                '泉区・泉中央・富谷': 'aream6222',
                '長町・太白区': 'aream6232',
                '宮城野区・若林区': 'aream6240',
                '名取・沿岸南部': 'aream6262',
                '石巻': 'aream6264',
                '大崎・古川・登米': 'aream6266',
                '塩釜・多賀城': 'aream6254',
                '松島・利府': 'aream6252',
                '青葉区郊外': 'aream6214'
            },
            
            '秋田県': {
                '秋田市': 'aream6302',
                '仙北・大仙': 'aream6306',
                '由利本荘・にかほ': 'aream6304',
                '北秋田・大館・鹿角': 'aream6305',
                '横手': 'aream6322',
                '湯沢・羽後': 'aream6307',
                '能代・八峰・藤里': 'aream6312',
                '男鹿・大潟・五城目': 'aream6303'
            },
            
            '山形県': {
                '山形市': 'aream6352',
                '米沢・高畠・南陽': 'aream6362',
                '天童・東根・尾花沢': 'aream6375',
                '鶴岡・庄内': 'aream6372',
                '酒田・遊佐': 'aream6436',
                '新庄・最上': 'aream6376',
                '寒河江・大江・朝日町': 'aream6374',
                '上山': 'aream6364'
            },
            
            '福島県': {
                '福島市': 'aream6402',
                '郡山': 'aream6437',
                'いわき': 'aream6422',
                '会津若松': 'aream6432',
                '白河・矢吹': 'aream6438',
                '須賀川・天栄': 'aream6440',
                '二本松・本宮': 'aream6403',
                '田村・小野・三春': 'aream6439',
                '相馬・南相馬': 'aream6424'
            },
            
            '茨城県': {
                'つくば': 'aream2822',
                '土浦': 'aream3071',
                '牛久・龍ケ崎・阿見': 'aream2810',
                'ひたちなか・勝田': 'aream3069',
                '日立': 'aream2802',
                '守谷': 'aream3072',
                '取手': 'aream3080',
                '鹿嶋・潮来': 'aream2832',
                '石岡・かすみがうら市': 'aream2809',
                '古河': 'aream3073'
            },
            
            '栃木県': {
                '宇都宮': 'aream3063',
                '小山・下野': 'aream2712',
                '佐野': 'aream3064',
                '日光': 'aream2722',
                '栃木市・壬生': 'aream3066',
                '足利': 'aream3065',
                '大田原': 'aream2725',
                '鹿沼': 'aream2719',
                '黒磯': 'aream2723',
                '那須町・那須高原': 'aream2724'
            },
            
            '群馬県': {
                '高崎': 'aream2612',
                '前橋': 'aream3061',
                '伊勢崎': 'aream2614',
                '太田': 'aream3062',
                '桐生・みどり市': 'aream2615',
                '館林・大泉・明和': 'aream2616',
                '沼田・みなかみ・片品': 'aream2605',
                '渋川・伊香保': 'aream3060',
                '藤岡・玉村': 'aream2607',
                '富岡': 'aream2609',
                '草津': 'aream2602',
                '安中': 'aream2606',
                '東吾妻・中之条・高山': 'aream2603'
            },
            
            '埼玉県': {
                '大宮': 'aream2402',
                '浦和': 'aream2410',
                '川越': 'aream2434',
                '川口・東川口': 'aream2422',
                '越谷': 'aream3079',
                '所沢': 'aream2432',
                '久喜・加須': 'aream2448',
                '朝霞': 'aream2424',
                'さいたま新都心・与野': 'aream2404',
                '草加': 'aream2428'
            },
            
            '千葉県': {
                '柏': 'aream2542',
                '船橋・西船橋': 'aream2530',
                '千葉駅・蘇我': 'aream2502',
                '松戸': 'aream2544',
                '八千代・佐倉・四街道': 'aream2554',
                '木更津': 'aream2556',
                '津田沼': 'aream2532',
                '海浜幕張': 'aream2508',
                '本八幡': 'aream3051',
                '市原': 'aream3055'
            },
            
            '東京都': {
                '新宿': 'aream2115',
                '銀座': 'aream2105',
                '渋谷': 'aream2126',
                '池袋': 'aream2157',
                '新橋': 'aream2107',
                '赤坂': 'aream2133',
                '恵比寿': 'aream2178',
                '上野': 'aream2198',
                '立川': 'aream2286',
                '六本木': 'aream2132',
                '神田': 'aream2142',
                '浅草': 'aream2205',
                '丸の内': 'aream2141',
                '有楽町・日比谷': 'aream2106',
                '秋葉原': 'aream2200'
            },
            
            '神奈川県': {
                '横浜駅': 'aream2322',
                '川崎': 'aream2302',
                '武蔵小杉・元住吉': 'aream2310',
                '関内・馬車道': 'aream2332',
                '橋本・相模原・古淵': 'aream2384',
                '本厚木・厚木': 'aream3033',
                '藤沢': 'aream2914',
                '小田原・南足柄': 'aream2380',
                '溝の口': 'aream2308',
                '横須賀・追浜': 'aream2372'
            },
            
            '新潟県': {
                '新潟市中央区': 'aream6602',
                '長岡': 'aream6622',
                '上越市': 'aream6632',
                '新潟市西区': 'aream6603',
                '柏崎': 'aream6926',
                '佐渡': 'aream6642',
                '南魚沼・湯沢': 'aream6610',
                '燕市・三条市': 'areal6607',
                '妙高': 'aream6614',
                '村上・関川': 'aream6612'
            },
            
            '富山県': {
                '富山市': 'aream6702',
                '高岡': 'aream6722',
                '砺波・南砺': 'aream6704',
                '滑川・魚津': 'aream6711',
                '射水': 'aream6705',
                '黒部・入善・朝日町': 'aream6712',
                '氷見': 'aream6927',
                '小矢部': 'aream6706'
            },
            
            '石川県': {
                '金沢': 'aream6930',
                '加賀・小松': 'aream6812',
                '野々市': 'aream6806',
                '七尾・和倉温泉・羽咋': 'aream6822',
                '白山・松任': 'aream6842',
                '輪島・珠洲・穴水': 'aream6832',
                'かほく・津幡・内灘': 'aream6805'
            },
            
            '福井県': {
                '福井市': 'aream6902',
                '敦賀・若狭・美浜': 'aream6922',
                '越前市': 'aream6916',
                '鯖江・越前町': 'aream6917',
                '坂井・あわら・永平寺': 'aream6912',
                '小浜': 'aream6928',
                '勝山': 'aream6913',
                '大野': 'aream6914'
            },
            
            '山梨県': {
                '甲府': 'aream4762',
                '甲斐・韮崎・南アルプス': 'aream4764',
                '河口湖・富士吉田・山中湖': 'aream4752',
                '甲州・山梨市・笛吹': 'aream4763',
                '大月・上野原・都留': 'aream4765'
            },
            
            '長野県': {
                '長野市': 'aream4702',
                '松本': 'aream4712',
                '上田・東御・長和': 'aream4854',
                '岡谷・諏訪・茅野': 'aream4722',
                '軽井沢': 'aream4732',
                '佐久・小海・川上': 'aream4855',
                '飯田・大鹿・根羽': 'aream4715',
                '伊那・箕輪・辰野': 'aream4713',
                '塩尻・山形村': 'aream4711',
                '千曲・坂城': 'aream4704',
                '小諸・御代田': 'aream4707',
                '駒ケ根・飯島・中川': 'aream4714',
                '安曇野・筑北': 'aream4710',
                '飯山・中野・志賀高原': 'aream4853',
                '白馬・大町': 'aream4709'
            },
            
            '岐阜県': {
                '岐阜市': 'aream4502',
                '大垣・海津': 'aream4506',
                '多治見': 'aream4510',
                '可児・美濃加茂・白川': 'aream4507',
                '飛騨・高山': 'aream4522',
                '各務原': 'aream4504',
                '本巣・池田・揖斐川': 'aream4505',
                '関・美濃': 'aream4512',
                '瑞浪': 'aream4511',
                '羽島': 'aream4503',
                '中津川・恵那': 'aream4509',
                '下呂': 'aream4848'
            },
            
            '静岡県': {
                '静岡': 'aream4826',
                '浜松駅周辺': 'aream4836',
                '沼津': 'aream4816',
                '富士市': 'aream4818',
                '三島': 'aream4812',
                'その他浜松市': 'aream4877',
                '清水': 'aream4827',
                '藤枝': 'aream4822',
                '掛川': 'aream4832',
                '御殿場': 'aream4860'
            },
            
            '愛知県': {
                '名駅': 'aream4102',
                '栄周辺': 'aream4122',
                '豊田': 'aream4272',
                '豊橋': 'aream4288',
                '岡崎': 'aream4838',
                '金山・東別院': 'aream4182',
                '刈谷': 'aream4274',
                '一宮': 'aream4302',
                '春日井': 'aream4842',
                '伏見': 'aream4144'
            },
            
            '三重県': {
                '四日市': 'aream4602',
                '津': 'aream4604',
                '鈴鹿': 'aream4850',
                '桑名・いなべ': 'aream4849',
                '伊勢': 'aream4612',
                '松阪': 'aream4608',
                '鳥羽・志摩': 'aream4852',
                '亀山': 'aream4605',
                '名張': 'aream4610',
                '伊賀': 'aream4609',
                '明和・玉城': 'aream4611',
                '尾鷲・大紀・大台': 'aream4606'
            },
            
            '滋賀県': {
                '大津市南部': 'aream3702',
                '草津・南草津': 'aream3712',
                '近江八幡': 'aream3860',
                '彦根・多賀・愛荘': 'aream3861',
                '守山': 'aream3866',
                '長浜・米原': 'aream3722',
                '甲賀・湖南': 'aream3705',
                '栗東': 'aream3704',
                '東近江・日野': 'aream3706',
                '野洲': 'aream3709'
            },
            
            '京都府': {
                '四条烏丸・烏丸御池': 'aream3414',
                '京都駅': 'aream3404',
                '四条河原町周辺・寺町': 'aream3402',
                '木屋町・先斗町': 'aream3418',
                '祇園': 'aream3422',
                '伏見・醍醐': 'aream3442',
                '宇治': 'aream3847',
                '八幡・京田辺': 'aream3464',
                '西院': 'aream3416',
                '二条城': 'aream3413'
            },
            
            '大阪府': {
                'なんば（難波）': 'aream3144',
                '梅田・大阪駅': 'aream3102',
                '心斎橋': 'aream3162',
                '北新地': 'aream3108',
                '岸和田・和泉・泉佐野': 'aream3314',
                '（大阪）福島・野田・中之島': 'aream3118',
                '天王寺・阿倍野': 'aream3264',
                '（大阪）京橋': 'aream3224',
                '本町・堺筋本町': 'aream3188',
                'なかもず・深井・北野田': 'aream3313'
            },
            
            '兵庫県': {
                '三宮': 'aream3502',
                '姫路': 'aream3584',
                '尼崎': 'aream3566',
                '西宮': 'aream3570',
                '明石': 'aream3587',
                '加古川': 'aream3582',
                '神戸': 'aream3850',
                '宝塚': 'aream3562',
                '伊丹': 'aream3855',
                '丹波・城崎': 'aream3590'
            },
            
            '奈良県': {
                '奈良市': 'aream3602',
                '橿原': 'aream3612',
                '王寺・広陵・香芝': 'aream3604',
                '生駒': 'aream3858',
                '天理': 'aream3607',
                '大和高田': 'aream3611',
                '大和郡山': 'aream3859',
                '桜井・宇陀': 'aream3603',
                '吉野・五條・十津川': 'aream3622',
                '曽爾・川上・下北山': 'aream3606'
            },
            
            '和歌山県': {
                '和歌山市': 'aream3802',
                '岩出・紀の川・橋本': 'aream3812',
                '田辺・白浜・すさみ': 'aream3822',
                '有田・湯浅・みなべ': 'aream3811',
                '新宮・串本': 'aream3863',
                '海南': 'aream3862'
            },
            
            '鳥取県': {
                '鳥取市': 'aream7102',
                '米子': 'aream7103',
                '倉吉・湯梨浜・琴浦': 'aream7112',
                '境港': 'aream7104',
                '八頭・若桜・智頭': 'aream7132',
                '大山・伯耆・南部': 'aream7105',
                '日南・日野・江府': 'aream7106'
            },
            
            '島根県': {
                '松江': 'aream7152',
                '出雲': 'aream7438',
                '津和野・益田・吉賀': 'aream7157',
                '浜田・江津': 'aream7172',
                '安来': 'aream7155',
                '大田・美郷・邑南': 'aream7156',
                '雲南・飯南・奥出雲': 'aream7154'
            },
            
            '岡山県': {
                '岡山市': 'aream7202',
                '倉敷': 'aream7212',
                '津山': 'aream7232',
                '総社・高梁・吉備中央': 'aream7252',
                '井原・笠岡・浅口': 'aream7242',
                '赤磐・瀬戸内・備前': 'aream7222',
                '美作・奈義・勝央': 'aream7262',
                '新見・真庭': 'aream7272',
                '美咲': 'aream7231'
            },
            
            '広島県': {
                '広島市': 'aream7303',
                '福山・府中': 'aream7332',
                '呉': 'aream7323',
                '尾道': 'aream7333',
                '西条・東広島': 'aream7322',
                '廿日市市・大竹市': 'aream7320',
                '三原': 'aream7434',
                '三次・世羅': 'aream7343',
                '安芸高田・山県郡': 'aream7344',
                '庄原・神石': 'aream7342'
            },
            
            '山口県': {
                '下関': 'aream7437',
                '山口市': 'aream7412',
                '周南': 'aream7436',
                '宇部': 'aream7432',
                '岩国': 'aream7402',
                '防府': 'aream7435',
                '下松': 'aream7424',
                '光市・柳井・周防大島': 'aream7423',
                '山陽小野田': 'aream7427',
                '長門': 'aream7425',
                '萩': 'aream7422'
            },
            
            '徳島県': {
                '徳島市': 'aream7602',
                '鳴門': 'aream7923',
                '美馬・吉野川・石井': 'aream7603',
                '阿南': 'aream7612',
                '小松島': 'aream7605',
                '三好': 'aream7604',
                '阿波': 'aream7925',
                '美波・牟岐・海陽': 'aream7608',
                '那賀・勝浦': 'aream7607',
                '安芸・室戸': 'aream7902'
            },
            
            '香川県': {
                '高松': 'aream7702',
                '丸亀': 'aream7704',
                '三豊・観音寺': 'aream7703',
                '綾川・まんのう': 'aream7706',
                '多度津・善通寺・琴平': 'aream7705',
                '坂出': 'aream7722',
                '小豆島・直島': 'aream7732',
                '三木・さぬき・東かがわ': 'aream7712'
            },
            
            '愛媛県': {
                '松山': 'aream7802',
                '今治': 'aream7812',
                '新居浜': 'aream7924',
                '西条': 'aream7805',
                '八幡浜・大洲・西予': 'aream7807',
                '宇和島': 'aream7822',
                '四国中央': 'aream7806',
                '伊予・砥部': 'aream7803',
                '久万高原・東温': 'aream7804'
            },
            
            '高知県': {
                '高知市': 'aream7912',
                '南国・香南・香美': 'aream7903',
                '宿毛': 'aream7908',
                '四万十市・土佐清水': 'aream7922',
                '土佐・須崎・いの町': 'aream7914',
                '梼原・津野・四万十町': 'aream7907',
                '安芸・室戸': 'aream7902',
                '仁淀川・越知・佐川': 'aream7906',
                '大豊・本山・土佐町': 'aream7904'
            },
            
            '福岡県': {
                '博多': 'aream5042',
                '小倉北区': 'aream5131',
                '天神': 'aream5012',
                '久留米': 'aream5144',
                '筑豊・糟屋郡': 'aream5148',
                '八幡西区・東区': 'aream5136',
                '大名': 'aream5014',
                '西中洲・春吉': 'aream5054',
                '中洲': 'aream5052',
                '薬院': 'aream5026'
            },
            
            '佐賀県': {
                '佐賀市': 'aream5162',
                '唐津・呼子・玄海': 'aream5439',
                '鳥栖・みやき・神埼': 'aream5438',
                '伊万里・有田': 'aream5152',
                '嬉野・鹿島・太良': 'aream5151',
                '武雄': 'aream5153',
                '多久・小城': 'aream5150'
            },
            
            '長崎県': {
                '長崎市': 'aream5202',
                '佐世保': 'aream5222',
                '諫早': 'aream5207',
                '時津・長与': 'aream5204',
                '大村': 'aream5212',
                '五島': 'aream5232',
                '島原・南島原': 'aream5206',
                '壱岐': 'aream5242',
                '西海': 'aream5203'
            },
            
            '熊本県': {
                '熊本市': 'aream5252',
                '山鹿・大津・菊陽': 'aream5253',
                '宇土・宇城・美里': 'aream5266',
                '西原・益城・御船': 'aream5254',
                '荒尾・玉名・長洲': 'aream5262',
                '人吉・球磨・錦町': 'aream5268',
                '小国・阿蘇・南阿蘇': 'aream5264'
            },
            
            '大分県': {
                '大分市': 'aream5302',
                '別府': 'aream5308',
                '中津': 'aream5332',
                '日田': 'aream5322',
                '湯布院': 'aream5444',
                '臼杵・津久見': 'aream5304',
                '杵築': 'aream5303',
                '佐伯': 'aream5312',
                '玖珠・九重': 'aream5323'
            },
            
            '宮崎県': {
                '宮崎市': 'aream5352',
                '都城・三股': 'aream5364',
                '延岡': 'aream5355',
                '日向・門川': 'aream5359',
                '日南・串間': 'aream5354',
                '高鍋・西都・都農': 'aream5362',
                '小林・えびの・高原町': 'aream5358',
                '五ヶ瀬・高千穂・日之影': 'aream5356',
                '美郷・椎葉・西米良': 'aream5357'
            },
            
            '鹿児島県': {
                '鹿児島市': 'aream5402',
                'さつま・薩摩川内・姶良': 'areal5406',
                '霧島・湧水': 'aream5406',
                '鹿屋・垂水': 'aream5412',
                '指宿・南九州': 'aream5403',
                '阿久根・出水・伊佐': 'aream5407',
                'いちき串木野・日置': 'aream5404',
                '志布志・曽於・大崎': 'aream5408',
                '奄美大島・徳之島・与論': 'areal5403',
                '種子島・屋久島': 'areal5402'
            },
            
            '沖縄県': {
                '那覇': 'aream8102',
                '宮古島・伊良部島・多良間島': 'aream8502',
                '恩納村・読谷・北谷': 'aream8302',
                '浦添': 'aream8603',
                '宜野湾・北中城・中城': 'aream8202',
                '沖縄市・うるま市': 'aream8352',
                '南風原・南城市・八重瀬': 'aream8156',
                '名護・宜野座': 'aream8402',
                '石垣島・西表島・与那国島': 'aream8552',
                '本部・今帰仁': 'aream8404'
            }
        }
        
        # 全ての都道府県のエリアコードを統合
        for prefecture, areas in self.prefecture_areas.items():
            if isinstance(areas, dict):
                self.area_codes.update(areas)
    
    def get_prefectures(self):
        """都道府県リスト取得（全国を含む）"""
        return list(self.prefecture_codes.keys())
    
    def get_cities(self, prefecture):
        """指定都道府県のおすすめエリアリスト取得（互換性のため関数名はそのまま）"""
        areas = self.prefecture_areas.get(prefecture, {})
        if isinstance(areas, dict):
            return list(areas.keys())
        return []
    
    def generate_search_url(self, prefecture, city=None, page=1):
        """
        検索URL生成（ページネーション対応）
        
        Args:
            prefecture (str): 都道府県名（「全国」を含む）
            city (str): エリア名（旧市区町村名）
            page (int): ページ番号（デフォルト: 1）
            
        Returns:
            str: 生成されたURL
        """
        if prefecture not in self.prefecture_codes:
            raise ValueError(f"未対応の都道府県: {prefecture}")
        
        # エリア名（city）が指定されている場合
        if city:
            areas = self.prefecture_areas.get(prefecture, {})
            if isinstance(areas, dict) and city in areas:
                area_code = areas[city]
                base_url = f"{self.base_url}/area/{area_code}/rs/"
            else:
                # エリア名が見つからない場合は都道府県レベルで検索
                pref_code = self.prefecture_codes[prefecture]
                base_url = f"{self.base_url}/area/{pref_code}/rs/"
        else:
            # 都道府県のみ、または全国の場合
            pref_code = self.prefecture_codes[prefecture]
            base_url = f"{self.base_url}/area/{pref_code}/rs/"
        
        # ページ番号が2以上の場合はパラメータを追加
        if page > 1:
            url = f"{base_url}?p={page}"
        else:
            url = base_url
        
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
        """URLから都道府県・エリア情報を抽出"""
        import re
        
        # 全国の場合
        if '/area/jp/' in url:
            return {'prefecture': '全国', 'city': None}
        
        # エリアコード抽出
        area_match = re.search(r'/area/(aream\d+)/', url)
        if area_match:
            area_code = area_match.group(1)
            # エリアコードから都道府県とエリア名を逆引き
            for pref, areas in self.prefecture_areas.items():
                if isinstance(areas, dict):
                    for area_name, code in areas.items():
                        if code == area_code:
                            return {'prefecture': pref, 'city': area_name}
        
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
        """エリアの有効性チェック（互換性のため関数名はそのまま）"""
        areas = self.prefecture_areas.get(prefecture, {})
        if isinstance(areas, dict):
            return city in areas
        return False
    
    def get_area_display_name(self, prefecture, city=None):
        """表示用のエリア名を取得"""
        if prefecture == '全国':
            return '全国'
        elif city:
            return f"{prefecture} {city}"
        else:
            return prefecture