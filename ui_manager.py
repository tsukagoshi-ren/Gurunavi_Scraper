"""
UI管理クラス（シンプル版）
中央寄せデザインで視認性を向上
おすすめエリア対応版
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
import threading
import time

class UIManager:
    """UI管理クラス"""
    
    def __init__(self, window, app):
        self.window = window
        self.app = app
        
        # UI変数
        self.prefecture_var = tk.StringVar()
        self.city_var = tk.StringVar()  # エリア名を格納（変数名は互換性のためそのまま）
        self.max_count_var = tk.IntVar(value=30)
        self.unlimited_var = tk.BooleanVar(value=False)
        self.save_path_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.filename_var = tk.StringVar()
        
        # 設定変数
        self.cooltime_min_var = tk.DoubleVar(value=2.0)
        self.cooltime_max_var = tk.DoubleVar(value=4.0)
        self.ua_switch_var = tk.IntVar(value=15)
        
        # 実行中変数
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="待機中")
        self.elapsed_var = tk.StringVar(value="経過時間: 0秒")
        
        # タイマー用
        self.start_time = None
        self.timer_running = False
        self.total_stores = 0
        self.current_store = 0
    
    def setup_ui(self):
        """UI構築"""
        # ウィンドウサイズと位置を中央に設定
        self.window.geometry("680x720")
        
        # 画面中央に配置
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
        
        # メインフレーム
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル（中央寄せ）
        title_label = ttk.Label(
            main_frame,
            text="ぐるなび店舗情報取得ツール",
            font=('Yu Gothic UI', 16, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(10, 20))
        
        # タブ作成
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 各タブ
        self.search_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.running_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.search_tab, text="　　検索　　")
        self.notebook.add(self.settings_tab, text="　　設定　　")
        self.notebook.add(self.running_tab, text="　実行中　")
        
        # タブ内容構築
        self.setup_search_tab()
        self.setup_settings_tab()
        self.setup_running_tab()
        
        # グリッド設定
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
    
    def setup_search_tab(self):
        """検索タブ構築（エリア対応版）"""
        # メインコンテナ
        container = ttk.Frame(self.search_tab, padding="20")
        container.grid(row=0, column=0, sticky='nsew')
        self.search_tab.columnconfigure(0, weight=1)
        self.search_tab.rowconfigure(0, weight=1)
        
        # 中央配置用のサブコンテナ
        center_frame = ttk.Frame(container)
        center_frame.grid(row=0, column=0)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # 統一幅とパディング
        FRAME_WIDTH = 420
        FRAME_PADDING = 20
        
        # 検索条件セクション
        search_frame = ttk.LabelFrame(center_frame, text="検索条件", padding=FRAME_PADDING)
        search_frame.grid(row=0, column=0, pady=(0, 15), sticky='ew')
        
        # 都道府県
        ttk.Label(search_frame, text="都道府県:").grid(row=0, column=0, sticky='w', padx=(20, 10), pady=8)
        self.prefecture_combo = ttk.Combobox(
            search_frame,
            textvariable=self.prefecture_var,
            width=28,
            state='readonly'
        )
        self.prefecture_combo['values'] = self.app.prefecture_mapper.get_prefectures()
        self.prefecture_combo.grid(row=0, column=1, pady=8, padx=(0, 20))
        self.prefecture_combo.bind('<<ComboboxSelected>>', self.on_prefecture_changed)
        
        # エリア（旧：市区町村）
        ttk.Label(search_frame, text="エリア:").grid(row=1, column=0, sticky='w', padx=(20, 10), pady=8)
        self.city_combo = ttk.Combobox(
            search_frame,
            textvariable=self.city_var,
            width=28,
            state='readonly'  # 読み取り専用に変更
        )
        self.city_combo.grid(row=1, column=1, pady=8, padx=(0, 20))
        
        # エリア情報ラベル
        self.city_info_label = ttk.Label(
            search_frame,
            text="※都道府県を選択してください",
            font=('Yu Gothic UI', 9),
            foreground='gray'
        )
        self.city_info_label.grid(row=2, column=0, columnspan=2, pady=(0, 5))
        
        # 検索件数セクション
        count_frame = ttk.LabelFrame(center_frame, text="検索件数", padding=FRAME_PADDING)
        count_frame.grid(row=1, column=0, pady=(0, 15), sticky='ew')
        
        # 件数入力
        input_frame = ttk.Frame(count_frame)
        input_frame.grid(row=0, column=0, pady=(5, 10))
        
        ttk.Label(input_frame, text="取得件数:").pack(side=tk.LEFT, padx=(0, 10))
        self.count_entry = ttk.Entry(input_frame, textvariable=self.max_count_var, width=8)
        self.count_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.count_entry.bind('<KeyRelease>', self.on_count_entry_changed)
        ttk.Label(input_frame, text="件").pack(side=tk.LEFT)
        
        # スライダー
        self.count_scale = ttk.Scale(
            count_frame,
            from_=1,
            to=5000,
            orient=tk.HORIZONTAL,
            variable=self.max_count_var,
            length=350,
            command=self.update_count_from_slider
        )
        self.count_scale.grid(row=1, column=0, pady=(0, 5))
        
        # 範囲表示
        range_frame = ttk.Frame(count_frame)
        range_frame.grid(row=2, column=0)
        ttk.Label(range_frame, text="1", font=('Arial', 8)).pack(side=tk.LEFT)
        ttk.Label(range_frame, text="5000", font=('Arial', 8)).pack(side=tk.LEFT, padx=(310, 0))
        
        # 全件取得
        self.unlimited_check = ttk.Checkbutton(
            count_frame,
            text="全件取得",
            variable=self.unlimited_var,
            command=self.on_unlimited_changed
        )
        self.unlimited_check.grid(row=3, column=0, pady=(10, 5))
        
        # 1ページあたりの件数情報
        ttk.Label(
            count_frame,
            text="※1ページあたり30件の店舗が表示されます",
            font=('Yu Gothic UI', 9),
            foreground='blue'
        ).grid(row=4, column=0, pady=(5, 0))
        
        # 保存設定セクション
        save_frame = ttk.LabelFrame(center_frame, text="保存設定", padding=FRAME_PADDING)
        save_frame.grid(row=2, column=0, pady=(0, 15), sticky='ew')
        
        # 保存先
        ttk.Label(save_frame, text="保存先:").grid(row=0, column=0, sticky='w', padx=(20, 10), pady=8)
        path_entry = ttk.Entry(save_frame, textvariable=self.save_path_var, width=32)
        path_entry.grid(row=0, column=1, pady=8, padx=(0, 5))
        ttk.Button(save_frame, text="参照", command=self.browse_save_path, width=8).grid(row=0, column=2, pady=8, padx=(0, 20))
        
        # ファイル名
        ttk.Label(save_frame, text="ファイル名:").grid(row=1, column=0, sticky='w', padx=(20, 10), pady=8)
        file_entry = ttk.Entry(save_frame, textvariable=self.filename_var, width=32)
        file_entry.grid(row=1, column=1, pady=8, padx=(0, 5))
        ttk.Button(save_frame, text="自動", command=self.auto_filename, width=8).grid(row=1, column=2, pady=8, padx=(0, 20))
        
        # 実行ボタン
        button_frame = ttk.Frame(center_frame)
        button_frame.grid(row=3, column=0, pady=20)
        
        self.start_button = ttk.Button(
            button_frame,
            text="スクレイピング開始",
            command=self.app.start_scraping,
            style='Accent.TButton'
        )
        self.start_button.pack()
        
        # スタイル設定
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Yu Gothic UI', 12, 'bold'))
    
    def setup_settings_tab(self):
        """設定タブ構築"""
        # メインコンテナ
        container = ttk.Frame(self.settings_tab, padding="20")
        container.grid(row=0, column=0, sticky='nsew')
        self.settings_tab.columnconfigure(0, weight=1)
        self.settings_tab.rowconfigure(0, weight=1)
        
        # 中央配置用のサブコンテナ
        center_frame = ttk.Frame(container)
        center_frame.grid(row=0, column=0)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        FRAME_PADDING = 20
        
        # アクセスクールタイムセクション
        cooltime_frame = ttk.LabelFrame(center_frame, text="アクセスクールタイム", padding=FRAME_PADDING)
        cooltime_frame.grid(row=0, column=0, pady=(0, 20), padx=20, sticky='ew')
        
        # 最小値
        min_frame = ttk.Frame(cooltime_frame)
        min_frame.grid(row=0, column=0, pady=8)
        ttk.Label(min_frame, text="最小値（秒）:", width=18).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Spinbox(
            min_frame,
            from_=1.0,
            to=10.0,
            increment=0.5,
            textvariable=self.cooltime_min_var,
            width=15
        ).pack(side=tk.LEFT)
        
        # 最大値
        max_frame = ttk.Frame(cooltime_frame)
        max_frame.grid(row=1, column=0, pady=8)
        ttk.Label(max_frame, text="最大値（秒）:", width=18).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Spinbox(
            max_frame,
            from_=2.0,
            to=20.0,
            increment=0.5,
            textvariable=self.cooltime_max_var,
            width=15
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            cooltime_frame,
            text="※推奨: 最小2秒、最大4秒",
            font=('Yu Gothic UI', 9),
            foreground='blue'
        ).grid(row=2, column=0, pady=(10, 0))
        
        # User-Agent切り替えセクション
        ua_frame = ttk.LabelFrame(center_frame, text="User-Agent切り替え", padding=FRAME_PADDING)
        ua_frame.grid(row=1, column=0, pady=(0, 20), padx=20, sticky='ew')
        
        ua_input_frame = ttk.Frame(ua_frame)
        ua_input_frame.grid(row=0, column=0, pady=8)
        ttk.Label(ua_input_frame, text="切り替え間隔（店舗数）:", width=22).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Spinbox(
            ua_input_frame,
            from_=5,
            to=50,
            increment=5,
            textvariable=self.ua_switch_var,
            width=15
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            ua_frame,
            text="※推奨: 15店舗ごと",
            font=('Yu Gothic UI', 9),
            foreground='blue'
        ).grid(row=1, column=0, pady=(10, 0))
        
        # ChromeDriverセクション
        driver_frame = ttk.LabelFrame(center_frame, text="ChromeDriver", padding=FRAME_PADDING)
        driver_frame.grid(row=2, column=0, padx=20, sticky='ew')
        
        ttk.Button(
            driver_frame,
            text="ChromeDriver修正",
            command=self.fix_chromedriver,
            width=20
        ).pack(pady=10)
        
        ttk.Label(
            driver_frame,
            text="※問題がある場合に実行してください",
            font=('Yu Gothic UI', 9),
            foreground='gray'
        ).pack()
    
    def setup_running_tab(self):
        """実行中タブ構築"""
        # メインコンテナ
        container = ttk.Frame(self.running_tab, padding="20")
        container.grid(row=0, column=0, sticky='nsew')
        self.running_tab.columnconfigure(0, weight=1)
        self.running_tab.rowconfigure(0, weight=1)
        
        # 中央配置用のサブコンテナ
        center_frame = ttk.Frame(container)
        center_frame.grid(row=0, column=0)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # ステータス表示
        status_frame = ttk.LabelFrame(center_frame, text="実行状況", padding="30")
        status_frame.grid(row=0, column=0, pady=(0, 20), sticky='ew')
        
        # ステータステキスト
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=('Yu Gothic UI', 12)
        )
        self.status_label.grid(row=0, column=0, pady=(0, 15))
        
        # プログレスバー
        self.progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            maximum=100,
            length=450
        )
        self.progress_bar.grid(row=1, column=0, pady=10)
        
        # プログレステキスト
        self.progress_label = ttk.Label(
            status_frame, 
            text="0 / 0 件",
            font=('Yu Gothic UI', 10)
        )
        self.progress_label.grid(row=2, column=0, pady=(5, 15))
        
        # 経過時間
        self.elapsed_label = ttk.Label(
            status_frame,
            textvariable=self.elapsed_var,
            font=('Yu Gothic UI', 11)
        )
        self.elapsed_label.grid(row=3, column=0, pady=5)
        
        # ログ表示
        log_frame = ttk.LabelFrame(center_frame, text="処理ログ", padding="20")
        log_frame.grid(row=1, column=0, pady=(0, 20), sticky='ew')
        
        # ログテキスト
        log_container = ttk.Frame(log_frame)
        log_container.grid(row=0, column=0)
        
        self.log_text = tk.Text(
            log_container, 
            height=10, 
            width=60, 
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.log_text.grid(row=0, column=0)
        
        # スクロールバー
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # 制御ボタン
        self.stop_button = ttk.Button(
            center_frame,
            text="強制停止",
            command=self.app.stop_scraping,
            width=15
        )
        self.stop_button.grid(row=2, column=0, pady=10)
    
    def on_count_entry_changed(self, event):
        """手入力時の処理"""
        try:
            value = self.count_entry.get()
            if value:
                count = int(value)
                if count < 1:
                    count = 1
                elif count > 5000:
                    count = 5000
                self.max_count_var.set(count)
        except ValueError:
            pass
    
    def update_count_from_slider(self, value):
        """スライダー変更時の処理"""
        count = int(float(value))
        self.max_count_var.set(count)
    
    def on_unlimited_changed(self):
        """全件取得チェック変更時の処理"""
        if self.unlimited_var.get():
            self.count_scale.config(state='disabled')
            self.count_entry.config(state='disabled')
        else:
            self.count_scale.config(state='normal')
            self.count_entry.config(state='normal')
    
    def on_prefecture_changed(self, event):
        """都道府県変更時の処理（エリア対応版）"""
        prefecture = self.prefecture_var.get()
        if prefecture:
            self.app.on_prefecture_changed(prefecture)
            
            # 全国選択時の処理
            if prefecture == '全国':
                self.city_combo.config(state='disabled')
                self.city_info_label.config(text="※全国選択時はエリア指定不可")
                self.city_var.set('')
            else:
                areas = self.app.prefecture_mapper.get_cities(prefecture)
                if areas:
                    # エリアリストがある場合
                    self.city_combo.config(state='readonly')
                    self.city_info_label.config(text=f"※{len(areas)}個のおすすめエリアから選択可能")
                else:
                    # エリアリストがない場合
                    self.city_combo.config(state='disabled')
                    self.city_info_label.config(text="※エリア情報がありません")
    
    def update_city_list(self, cities):
        """エリアリスト更新（変数名は互換性のためそのまま）"""
        self.city_combo['values'] = [''] + cities
        self.city_var.set('')
    
    def browse_save_path(self):
        """保存先選択"""
        folder = filedialog.askdirectory(initialdir=self.save_path_var.get())
        if folder:
            self.save_path_var.set(folder)
    
    def auto_filename(self):
        """自動ファイル名生成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefecture = self.prefecture_var.get() or "gurunavi"
        area = self.city_var.get()
        if area:
            # ファイル名用にエリア名から特殊文字を安全な文字に変換
            safe_area = area.replace('・', '_').replace('（', '').replace('）', '').replace(' ', '')
            filename = f"{prefecture}_{safe_area}_{timestamp}"
        else:
            filename = f"{prefecture}_stores_{timestamp}"
        self.filename_var.set(filename)
    
    def fix_chromedriver(self):
        """ChromeDriver修正"""
        result = messagebox.askyesno("確認", "ChromeDriverを修正しますか？")
        if result:
            try:
                success = self.app.chrome_manager.fix_chromedriver()
                if success:
                    messagebox.showinfo("完了", "ChromeDriverの修正が完了しました")
                else:
                    messagebox.showerror("エラー", "ChromeDriverの修正に失敗しました")
            except Exception as e:
                messagebox.showerror("エラー", f"修正中にエラーが発生しました:\n{str(e)}")
    
    def switch_to_running_tab(self):
        """実行中タブに切り替え"""
        self.notebook.select(self.running_tab)
        self.start_timer()
    
    def start_timer(self):
        """タイマー開始"""
        self.start_time = time.time()
        self.timer_running = True
        self.update_timer()
    
    def update_timer(self):
        """タイマー更新"""
        if self.timer_running and self.start_time:
            elapsed = time.time() - self.start_time
            minutes, seconds = divmod(int(elapsed), 60)
            if minutes > 0:
                self.elapsed_var.set(f"経過時間: {minutes}分{seconds}秒")
            else:
                self.elapsed_var.set(f"経過時間: {seconds}秒")
            
            # 100ms後に再更新
            self.window.after(100, self.update_timer)
    
    def update_progress(self, data):
        """進捗更新（改善版）"""
        if 'message' in data:
            self.status_var.set(data['message'])
            self.add_log(data['message'])
        
        # 進捗率の計算を改善
        if 'current' in data and 'total' in data:
            self.current_store = data['current']
            self.total_stores = data['total']
            
            # より正確な進捗率計算
            if self.total_stores > 0:
                # 詳細取得フェーズの場合、50%から開始
                if 'phase' in data and data['phase'] == 'detail':
                    base_progress = 50
                    detail_progress = (self.current_store / self.total_stores) * 50
                    actual_progress = base_progress + detail_progress
                else:
                    # リスト取得フェーズは0-50%
                    actual_progress = min(data.get('progress', 0), 50)
                
                self.progress_var.set(actual_progress)
                self.progress_label.config(text=f"{self.current_store} / {self.total_stores} 件")
        elif 'progress' in data:
            # フォールバック
            self.progress_var.set(data['progress'])
        
        if 'phase' in data:
            if data['phase'] == 'complete':
                self.timer_running = False
                self.progress_var.set(100)
                self.progress_label.config(text=f"{self.total_stores} / {self.total_stores} 件")
                self.add_log("=== 処理完了 ===")
                
                # シンプルな完了メッセージ
                if 'elapsed_time' in data:
                    elapsed = data['elapsed_time']
                    minutes, seconds = divmod(int(elapsed), 60)
                    if minutes > 0:
                        time_text = f"{minutes}分{seconds}秒"
                    else:
                        time_text = f"{seconds}秒"
                    
                    messagebox.showinfo(
                        "完了",
                        f"処理が完了しました\n\n処理時間: {time_text}"
                    )
    
    def add_log(self, message):
        """ログ追加"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)
        
        # ログが長くなりすぎた場合の制限
        lines = self.log_text.get(1.0, tk.END).split('\n')
        if len(lines) > 100:
            # 古い行を削除
            self.log_text.delete(1.0, f"{len(lines)-80}.0")
    
    def reset_progress(self):
        """進捗リセット"""
        self.progress_var.set(0)
        self.progress_label.config(text="0 / 0 件")
        self.status_var.set("待機中")
        self.elapsed_var.set("経過時間: 0秒")
        self.timer_running = False
        self.total_stores = 0
        self.current_store = 0
        self.log_text.delete(1.0, tk.END)
    
    def get_search_params(self):
        """検索パラメータ取得"""
        params = {
            'prefecture': self.prefecture_var.get(),
            'city': self.city_var.get(),  # エリア名が格納される
            'max_count': self.max_count_var.get(),
            'unlimited': self.unlimited_var.get(),
            'save_path': self.save_path_var.get(),
            'filename': self.filename_var.get(),
            'url_only': False
        }
        return params
    
    def get_settings(self):
        """設定取得"""
        return {
            'cooltime_min': self.cooltime_min_var.get(),
            'cooltime_max': self.cooltime_max_var.get(),
            'ua_switch_interval': self.ua_switch_var.get()
        }