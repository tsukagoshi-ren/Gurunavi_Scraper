"""
UI管理クラス（現実的処理時間対応版）
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
        self.cooltime_min_var = tk.DoubleVar(value=2.0)
        self.cooltime_max_var = tk.DoubleVar(value=4.0)
        self.ua_switch_var = tk.IntVar(value=15)
        
        # 実行中変数
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="待機中")
        self.elapsed_var = tk.StringVar(value="経過時間: 0秒")
        
        # 処理時間予測用
        self.time_prediction_var = tk.StringVar(value="時間帯と件数を設定してください")
        
        # タイマー用
        self.start_time = None
        self.timer_running = False
        self.last_stats_update = 0
    
    def setup_ui(self):
        """UI構築"""
        # メインフレーム
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル
        title_label = ttk.Label(
            main_frame,
            text="ぐるなび店舗情報取得ツール",
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
        
        # 処理時間予測の初期化
        self.initialize_time_prediction()
        
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
        count_frame.columnconfigure(0, weight=0, minsize=80)
        count_frame.columnconfigure(1, weight=0, minsize=300)
        count_frame.columnconfigure(2, weight=0, minsize=80)
        
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
        
        # 検索オプションセクション
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
        
        # 処理時間予測セクション
        prediction_frame = ttk.LabelFrame(content_frame, text="処理時間予測", padding="15")
        prediction_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # 予測時間表示
        prediction_label = ttk.Label(
            prediction_frame, 
            textvariable=self.time_prediction_var,
            font=('Arial', 10),
            foreground='blue'
        )
        prediction_label.grid(row=0, column=0, pady=5)
        
        # 時間帯情報表示
        self.time_zone_var = tk.StringVar()
        time_zone_label = ttk.Label(
            prediction_frame,
            textvariable=self.time_zone_var,
            font=('Arial', 9)
        )
        time_zone_label.grid(row=1, column=0, pady=5)
        
        # 推奨時間帯の案内
        recommendation_text = (
            "推奨実行時間: 深夜23:00～早朝6:00\n"
            "注意時間帯: 昼食(12-13時)、夕食(18-20時)"
        )
        recommendation_label = ttk.Label(
            prediction_frame,
            text=recommendation_text,
            font=('Arial', 8),
            foreground='gray'
        )
        recommendation_label.grid(row=2, column=0, pady=(10, 0))
        
        # 実行ボタン
        button_frame = ttk.Frame(content_frame)
        button_frame.grid(row=5, column=0, pady=20)
        
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
            from_=1.0,
            to=10.0,
            increment=0.5,
            textvariable=self.cooltime_min_var,
            width=10
        ).grid(row=0, column=1, pady=5)
        
        ttk.Label(cooltime_frame, text="最大値（秒）:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Spinbox(
            cooltime_frame,
            from_=2.0,
            to=20.0,
            increment=0.5,
            textvariable=self.cooltime_max_var,
            width=10
        ).grid(row=1, column=1, pady=5)
        
        ttk.Label(
            cooltime_frame,
            text="※現実的な設定: 最小2秒、最大4秒を推奨\n※アクセス制限回避のため十分な間隔を設定してください",
            font=('Arial', 9),
            foreground='blue'
        ).grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        # User-Agent切り替えセクション
        ua_frame = ttk.LabelFrame(content_frame, text="User-Agent切り替え", padding="15")
        ua_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(ua_frame, text="切り替え間隔（アクセス数）:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Spinbox(
            ua_frame,
            from_=5,
            to=50,
            increment=5,
            textvariable=self.ua_switch_var,
            width=10
        ).grid(row=0, column=1, pady=5)
        
        ttk.Label(
            ua_frame,
            text="※現実的な設定: 15店舗ごとの切り替えを推奨\n※頻繁な切り替えでアクセス制限を回避します",
            font=('Arial', 9),
            foreground='blue'
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
        
        # 処理時間情報セクション
        info_frame = ttk.LabelFrame(content_frame, text="処理時間について", padding="15")
        info_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        info_text = (
            "現実的な処理時間:\n"
            "• 1店舗あたり約7-10秒（時間帯により変動）\n"
            "• 深夜時間帯: 約7秒/店舗（最速）\n"
            "• 通常時間帯: 約8秒/店舗\n"
            "• 昼食・夕食時間帯: 約10-12秒/店舗（最遅）\n\n"
            "100店舗の場合の予想処理時間:\n"
            "• 深夜時間帯: 約12分\n"
            "• 通常時間帯: 約14分\n"
            "• 繁忙時間帯: 約18分"
        )
        
        ttk.Label(
            info_frame,
            text=info_text,
            font=('Arial', 9),
            foreground='darkgreen'
        ).grid(row=0, column=0, pady=5)
        
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
        self.log_text = tk.Text(log_frame, height=8, width=60, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # スクロールバー
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # 統計情報表示
        stats_frame = ttk.LabelFrame(content_frame, text="詳細統計", padding="15")
        stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # 統計情報表示用テキスト
        self.stats_text = tk.Text(stats_frame, height=6, width=60, wrap=tk.WORD)
        self.stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # 統計用スクロールバー
        stats_scrollbar = ttk.Scrollbar(stats_frame, orient=tk.VERTICAL, command=self.stats_text.yview)
        stats_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.stats_text.configure(yscrollcommand=stats_scrollbar.set)
        
        # 制御ボタン
        button_frame = ttk.Frame(content_frame)
        button_frame.grid(row=3, column=0, pady=10)
        
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
        stats_frame.columnconfigure(0, weight=1)
    
    def initialize_time_prediction(self):
        """処理時間予測の初期化"""
        self.update_time_prediction()
        self.update_time_zone_info()
    
    def update_time_prediction(self):
        """処理時間予測の更新"""
        try:
            # 件数取得
            if self.unlimited_var.get():
                store_count = 100  # 予測用のサンプル数
                count_text = "全件"
            else:
                store_count = self.max_count_var.get()
                count_text = f"{store_count}件"
            
            # 時間予測計算
            estimated_minutes = self.app.get_estimated_time(store_count)
            
            if estimated_minutes < 1:
                time_text = f"約{estimated_minutes*60:.0f}秒"
            else:
                time_text = f"約{estimated_minutes:.0f}分"
            
            # 予測時間表示更新
            prediction_text = f"{count_text}の処理予想時間: {time_text}"
            
            # 長時間処理の警告
            if estimated_minutes > 30:
                prediction_text += "\n⚠️ 処理時間が長くなります。深夜時間帯での実行を推奨。"
            
            self.time_prediction_var.set(prediction_text)
            
        except Exception as e:
            self.time_prediction_var.set("予測時間計算エラー")
    
    def update_time_zone_info(self):
        """時間帯情報の更新"""
        try:
            current_hour = datetime.now().hour
            if 12 <= current_hour <= 13:
                time_zone = "昼食時間帯 (処理時間 +50%)"
                color = 'orange'
            elif 18 <= current_hour <= 20:
                time_zone = "夕食時間帯 (処理時間 +30%)"
                color = 'orange'
            elif current_hour >= 23 or current_hour <= 6:
                time_zone = "深夜・早朝時間帯 (処理時間 -20%)"
                color = 'green'
            else:
                time_zone = "通常時間帯"
                color = 'black'
            
            self.time_zone_var.set(f"現在: {time_zone}")
            
        except Exception as e:
            self.time_zone_var.set("時間帯情報取得エラー")
    
    def on_prefecture_changed(self, event):
        """都道府県変更時の処理"""
        prefecture = self.prefecture_var.get()
        if prefecture:
            self.app.on_prefecture_changed(prefecture)
            self.update_time_prediction()
    
    def update_city_list(self, cities):
        """市区町村リスト更新"""
        self.city_combo['values'] = [''] + cities
        self.city_var.set('')
        self.update_time_prediction()
    
    def update_count_label(self, value):
        """件数ラベル更新（時間予測付き）"""
        count = int(float(value))
        self.count_label.config(text=f"{count}件")
        self.max_count_var.set(count)
        self.update_time_prediction()
    
    def on_unlimited_changed(self):
        """無制限チェック変更時の処理（時間予測付き）"""
        if self.unlimited_var.get():
            self.count_scale.config(state='disabled')
            self.count_label.config(text="全件")
        else:
            self.count_scale.config(state='normal')
            self.update_count_label(self.max_count_var.get())
        
        self.update_time_prediction()
    
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
        # 時間帯情報も更新
        self.update_time_zone_info()
    
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
        """進捗更新（統計情報対応）"""
        if 'message' in data:
            self.status_var.set(data['message'])
            self.add_log(data['message'])
        
        if 'progress' in data:
            self.progress_var.set(data['progress'])
            self.progress_label.config(text=f"{int(data['progress'])}%")
        
        # 統計情報の表示
        if 'stats' in data:
            self.update_stats_display(data['stats'])
        
        if 'phase' in data:
            if data['phase'] == 'complete':
                self.timer_running = False
                self.add_log("=== スクレイピング完了 ===")
                
                # 最終統計の表示
                if 'final_stats' in data:
                    self.display_final_stats(data['final_stats'])
    
    def update_stats_display(self, stats):
        """統計情報表示更新"""
        try:
            # 5秒に一度だけ統計更新
            if time.time() - self.last_stats_update < 5:
                return
            
            self.last_stats_update = time.time()
            
            # 統計情報のフォーマット
            stats_text = "=== 処理統計 ===\n"
            for key, value in stats.items():
                stats_text += f"{key}: {value}\n"
            
            # 統計テキストエリアに表示
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, stats_text)
            
            # 完了予想時刻の表示
            if '完了予想時刻' in stats and stats['完了予想時刻'] != 'N/A':
                completion_time = stats['完了予想時刻']
                self.status_var.set(f"処理中... (完了予想: {completion_time})")
            
        except Exception as e:
            self.add_log(f"統計表示エラー: {e}")
    
    def display_final_stats(self, final_stats):
        """最終統計の表示"""
        try:
            final_text = "\n=== 最終統計 ===\n"
            for key, value in final_stats.items():
                final_text += f"{key}: {value}\n"
            
            self.add_log(final_text)
            
            # 統計テキストエリアにも表示
            self.stats_text.insert(tk.END, final_text)
            self.stats_text.see(tk.END)
            
        except Exception as e:
            self.add_log(f"最終統計表示エラー: {e}")
    
    def add_log(self, message):
        """ログ追加"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)
        
        # ログが長くなりすぎた場合の制限
        lines = self.log_text.get(1.0, tk.END).split('\n')
        if len(lines) > 200:
            # 古い行を削除
            self.log_text.delete(1.0, f"{len(lines)-150}.0")
    
    def reset_progress(self):
        """進捗リセット"""
        self.progress_var.set(0)
        self.progress_label.config(text="0%")
        self.status_var.set("待機中")
        self.elapsed_var.set("経過時間: 0秒")
        self.timer_running = False
        self.log_text.delete(1.0, tk.END)
        self.stats_text.delete(1.0, tk.END)
    
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