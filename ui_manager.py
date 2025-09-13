"""
UI管理クラス
タブ式インターフェースの構築と管理
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
        self.city_var = tk.StringVar()
        self.max_count_var = tk.IntVar(value=30)
        self.unlimited_var = tk.BooleanVar(value=False)
        self.save_path_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.filename_var = tk.StringVar()
        
        # 設定変数
        self.cooltime_min_var = tk.DoubleVar(value=1.0)
        self.cooltime_max_var = tk.DoubleVar(value=5.0)
        self.ua_switch_var = tk.IntVar(value=100)
        
        # 実行中変数
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="待機中")
        self.elapsed_var = tk.StringVar(value="経過時間: 0秒")
        
        # タイマー用
        self.start_time = None
        self.timer_running = False
    
    def setup_ui(self):
        """UI構築"""
        # メインフレーム
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル
        title_label = ttk.Label(
            main_frame,
            text="ぐるなび店舗情報取得ツール v3.0",
            font=('Arial', 14, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # タブ作成
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 各タブ
        self.search_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.running_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.search_tab, text="検索")
        self.notebook.add(self.settings_tab, text="設定")
        self.notebook.add(self.running_tab, text="実行中")
        
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
        """検索タブ構築"""
        # パディング用フレーム
        content_frame = ttk.Frame(self.search_tab, padding="20")
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 検索条件セクション
        search_frame = ttk.LabelFrame(content_frame, text="検索条件", padding="15")
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))

        # 検索オプションセクション（新規追加）
        option_frame = ttk.LabelFrame(content_frame, text="取得オプション", padding="15")
        option_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # URL取得のみチェックボックス
        self.url_only_var = tk.BooleanVar(value=False)
        self.url_only_check = ttk.Checkbutton(
            option_frame,
            text="店舗URLのみ取得（詳細情報は取得しない）",
            variable=self.url_only_var
        )
        self.url_only_check.grid(row=0, column=0, sticky=tk.W, pady=5)
        
        ttk.Label(
            option_frame,
            text="※URLのみ取得する場合、処理時間が大幅に短縮されます",
            font=('Arial', 9),
            foreground='gray'
        ).grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        # 実行ボタンのrow番号を変更
        button_frame = ttk.Frame(content_frame)
        button_frame.grid(row=4, column=0, pady=20)  # row=3からrow=4に変更
        
        # 都道府県
        ttk.Label(search_frame, text="都道府県:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.prefecture_combo = ttk.Combobox(
            search_frame,
            textvariable=self.prefecture_var,
            width=20,
            state='readonly'
        )
        self.prefecture_combo['values'] = self.app.prefecture_mapper.get_prefectures()
        self.prefecture_combo.grid(row=0, column=1, pady=5)
        self.prefecture_combo.bind('<<ComboboxSelected>>', self.on_prefecture_changed)
        
        # 市区町村
        ttk.Label(search_frame, text="市区町村:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.city_combo = ttk.Combobox(
            search_frame,
            textvariable=self.city_var,
            width=20,
            state='readonly'
        )
        self.city_combo.grid(row=1, column=1, pady=5)
        
        # 検索件数セクション
        count_frame = ttk.LabelFrame(content_frame, text="検索件数", padding="15")
        count_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # 件数スライダー
        ttk.Label(count_frame, text="取得件数:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.count_scale = ttk.Scale(
            count_frame,
            from_=1,
            to=1000,
            orient=tk.HORIZONTAL,
            variable=self.max_count_var,
            length=300,
            command=self.update_count_label
        )
        self.count_scale.grid(row=0, column=1, pady=5)
        
        self.count_label = ttk.Label(count_frame, text="30件")
        self.count_label.grid(row=0, column=2, padx=(10, 0))
        
        # 無制限チェックボックス
        self.unlimited_check = ttk.Checkbutton(
            count_frame,
            text="無制限（全件取得）",
            variable=self.unlimited_var,
            command=self.on_unlimited_changed
        )
        self.unlimited_check.grid(row=1, column=1, pady=(10, 0))
        
        # 列幅を固定
        count_frame.columnconfigure(0, weight=0, minsize=80)  # ラベル列
        count_frame.columnconfigure(1, weight=0, minsize=300)  # スライダー列
        count_frame.columnconfigure(2, weight=0, minsize=80)   # カウント表示列
        
        # 保存設定セクション
        save_frame = ttk.LabelFrame(content_frame, text="保存設定", padding="15")
        save_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # 保存先
        ttk.Label(save_frame, text="保存先:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Entry(
            save_frame,
            textvariable=self.save_path_var,
            width=40
        ).grid(row=0, column=1, pady=5)
        ttk.Button(
            save_frame,
            text="参照",
            command=self.browse_save_path
        ).grid(row=0, column=2, padx=(5, 0))
        
        # ファイル名
        ttk.Label(save_frame, text="ファイル名:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Entry(
            save_frame,
            textvariable=self.filename_var,
            width=40
        ).grid(row=1, column=1, pady=5)
        ttk.Button(
            save_frame,
            text="自動",
            command=self.auto_filename
        ).grid(row=1, column=2, padx=(5, 0))
        
        # 実行ボタン
        button_frame = ttk.Frame(content_frame)
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
        style.configure('Accent.TButton', font=('Arial', 11, 'bold'))
        
        # グリッド設定
        content_frame.columnconfigure(0, weight=1)
        search_frame.columnconfigure(1, weight=1)
        count_frame.columnconfigure(1, weight=1)
        save_frame.columnconfigure(1, weight=1)
    
    def setup_settings_tab(self):
        """設定タブ構築"""
        # パディング用フレーム
        content_frame = ttk.Frame(self.settings_tab, padding="20")
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # アクセスクールタイムセクション
        cooltime_frame = ttk.LabelFrame(content_frame, text="アクセスクールタイム", padding="15")
        cooltime_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(cooltime_frame, text="最小値（秒）:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Spinbox(
            cooltime_frame,
            from_=0.5,
            to=10.0,
            increment=0.5,
            textvariable=self.cooltime_min_var,
            width=10
        ).grid(row=0, column=1, pady=5)
        
        ttk.Label(cooltime_frame, text="最大値（秒）:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Spinbox(
            cooltime_frame,
            from_=1.0,
            to=20.0,
            increment=0.5,
            textvariable=self.cooltime_max_var,
            width=10
        ).grid(row=1, column=1, pady=5)
        
        ttk.Label(
            cooltime_frame,
            text="※店舗詳細ページへのアクセス間隔をランダムに設定します",
            font=('Arial', 9),
            foreground='gray'
        ).grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        # User-Agent切り替えセクション
        ua_frame = ttk.LabelFrame(content_frame, text="User-Agent切り替え", padding="15")
        ua_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(ua_frame, text="切り替え間隔（アクセス数）:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Spinbox(
            ua_frame,
            from_=5,
            to=100,
            increment=5,
            textvariable=self.ua_switch_var,
            width=10
        ).grid(row=0, column=1, pady=5)
        
        ttk.Label(
            ua_frame,
            text="※指定したアクセス数ごとにUser-Agentを切り替えます",
            font=('Arial', 9),
            foreground='gray'
        ).grid(row=1, column=0, columnspan=2, pady=(10, 0))
        
        # ChromeDriverセクション
        driver_frame = ttk.LabelFrame(content_frame, text="ChromeDriver", padding="15")
        driver_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Button(
            driver_frame,
            text="ChromeDriver修正",
            command=self.fix_chromedriver
        ).grid(row=0, column=0, pady=5)
        
        ttk.Label(
            driver_frame,
            text="※ChromeDriverに問題がある場合に実行してください",
            font=('Arial', 9),
            foreground='gray'
        ).grid(row=1, column=0, pady=(5, 0))
        
        # グリッド設定
        content_frame.columnconfigure(0, weight=1)
    
    def setup_running_tab(self):
        """実行中タブ構築"""
        # パディング用フレーム
        content_frame = ttk.Frame(self.running_tab, padding="20")
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ステータス表示
        status_frame = ttk.LabelFrame(content_frame, text="実行状況", padding="15")
        status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # ステータステキスト
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=('Arial', 11)
        )
        self.status_label.grid(row=0, column=0, pady=5)
        
        # プログレスバー
        self.progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            maximum=100,
            length=400
        )
        self.progress_bar.grid(row=1, column=0, pady=10)
        
        # プログレステキスト
        self.progress_label = ttk.Label(status_frame, text="0%")
        self.progress_label.grid(row=2, column=0, pady=5)
        
        # 経過時間
        self.elapsed_label = ttk.Label(
            status_frame,
            textvariable=self.elapsed_var,
            font=('Arial', 10)
        )
        self.elapsed_label.grid(row=3, column=0, pady=5)
        
        # 詳細ログ
        log_frame = ttk.LabelFrame(content_frame, text="処理ログ", padding="15")
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        
        # ログテキスト
        self.log_text = tk.Text(log_frame, height=10, width=60, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # スクロールバー
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # 制御ボタン
        button_frame = ttk.Frame(content_frame)
        button_frame.grid(row=2, column=0, pady=10)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="強制停止",
            command=self.app.stop_scraping,
            state='normal'
        )
        self.stop_button.pack()
        
        # グリッド設定
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
    
    def on_prefecture_changed(self, event):
        """都道府県変更時の処理"""
        prefecture = self.prefecture_var.get()
        if prefecture:
            self.app.on_prefecture_changed(prefecture)
    
    def update_city_list(self, cities):
        """市区町村リスト更新"""
        self.city_combo['values'] = [''] + cities
        self.city_var.set('')
    
    def update_count_label(self, value):
        """件数ラベル更新"""
        count = int(float(value))
        self.count_label.config(text=f"{count}件")
        self.max_count_var.set(count)
    
    def on_unlimited_changed(self):
        """無制限チェック変更時の処理"""
        if self.unlimited_var.get():
            self.count_scale.config(state='disabled')
            self.count_label.config(text="全件")
        else:
            self.count_scale.config(state='normal')
            self.update_count_label(self.max_count_var.get())
    
    def browse_save_path(self):
        """保存先選択"""
        folder = filedialog.askdirectory(initialdir=self.save_path_var.get())
        if folder:
            self.save_path_var.set(folder)
    
    def auto_filename(self):
        """自動ファイル名生成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefecture = self.prefecture_var.get() or "gurunavi"
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
        """進捗更新"""
        if 'message' in data:
            self.status_var.set(data['message'])
            self.add_log(data['message'])
        
        if 'progress' in data:
            self.progress_var.set(data['progress'])
            self.progress_label.config(text=f"{int(data['progress'])}%")
        
        if 'phase' in data:
            if data['phase'] == 'complete':
                self.timer_running = False
                self.add_log("=== スクレイピング完了 ===")
    
    def add_log(self, message):
        """ログ追加"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def reset_progress(self):
        """進捗リセット"""
        self.progress_var.set(0)
        self.progress_label.config(text="0%")
        self.status_var.set("待機中")
        self.elapsed_var.set("経過時間: 0秒")
        self.timer_running = False
        self.log_text.delete(1.0, tk.END)
    
    def get_search_params(self):
        """検索パラメータ取得"""
        params = {
            'prefecture': self.prefecture_var.get(),
            'city': self.city_var.get(),
            'max_count': self.max_count_var.get(),
            'unlimited': self.unlimited_var.get(),
            'save_path': self.save_path_var.get(),
            'filename': self.filename_var.get(),
            'url_only': getattr(self, 'url_only_var', tk.BooleanVar()).get()
        }
        return params
    
    def get_settings(self):
        """設定取得"""
        return {
            'cooltime_min': self.cooltime_min_var.get(),
            'cooltime_max': self.cooltime_max_var.get(),
            'ua_switch_interval': self.ua_switch_var.get()
        }
    
    def stop_timer(self):
        """タイマー停止"""
        self.timer_running = False
    
    def error_cleanup(self):
        """エラー時のクリーンアップ"""
        self.timer_running = False
        self.reset_progress()