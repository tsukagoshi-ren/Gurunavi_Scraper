"""
電話番号クリーニング処理
取得した電話番号から番号部分のみを抽出
"""

import re

def clean_phone_number(raw_text):
    """
    電話番号文字列から番号部分のみを抽出
    
    Args:
        raw_text (str): 取得した生の電話番号テキスト
        
    Returns:
        str: クリーンな電話番号または元のテキスト
    """
    if not raw_text or raw_text == '-':
        return raw_text
    
    try:
        # 改行で分割して最初の行（電話番号）を取得
        lines = raw_text.strip().split('\n')
        first_line = lines[0].strip() if lines else raw_text.strip()
        
        # 電話番号のパターンにマッチする部分を抽出
        phone_patterns = [
            r'(0\d{1,4}-\d{1,4}-\d{3,4})',  # ハイフン付き
            r'(0\d{9,10})',                   # ハイフンなし
            r'(050-\d{4}-\d{4})',             # IP電話
            r'(0120-\d{3}-\d{3})',            # フリーダイヤル
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, first_line)
            if match:
                return match.group(1)
        
        # パターンにマッチしない場合は最初の行をそのまま返す
        # ただし、「ぐるなび」などのキーワードが含まれている場合は元のテキストは返さない
        if any(keyword in first_line for keyword in ['ぐるなび', '見た', 'スムーズ', '問合']):
            # 数字とハイフンのみ抽出を試みる
            numbers = re.findall(r'[\d-]+', first_line)
            if numbers:
                phone = numbers[0]
                # 10-11桁の電話番号か確認
                digits_only = re.sub(r'[^\d]', '', phone)
                if 10 <= len(digits_only) <= 11:
                    return phone
            return raw_text  # クリーニングできない場合は元のテキストを返す
        
        return first_line
        
    except Exception:
        return raw_text