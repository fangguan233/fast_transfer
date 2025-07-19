# -*- coding: utf-8 -*-

import json
import os
import random
import shutil
import stat
import subprocess
import queue
import sys
import threading
import time
import tkinter as tk
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import filedialog, messagebox, ttk


def resource_path(relative_path):
    """ 获取资源的绝对路径，对开发模式和PyInstaller打包模式都有效 """
    try:
        # PyInstaller 创建一个临时文件夹，并把路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class FileTransferApp:
    def __init__(self, master):
        self.master = master
        master.title("极速跨盘迁移工具")
        master.geometry("600x750") # 稍微增加高度以容纳设置面板
        master.minsize(500, 450)
        master.configure(bg="#F0F0F0")

        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        
        # Light Blue and White Theme
        BG_COLOR = "#F0F0F0"
        TEXT_COLOR = "#333333"
        BUTTON_COLOR = "#5CACEE"  # 淡蓝色
        BUTTON_ACTIVE_COLOR = "#4A90E2" # 稍深的淡蓝色
        ENTRY_BG_COLOR = "#FFFFFF"
        PROGRESS_BAR_COLOR = "#5CACEE"
        
        style.configure(".", background=BG_COLOR, foreground=TEXT_COLOR, font=('Microsoft YaHei UI', 9))
        style.configure("TButton", padding=6, relief="flat", background=BUTTON_COLOR, foreground="white")
        style.map("TButton", background=[('active', BUTTON_ACTIVE_COLOR)])
        style.configure("TEntry", padding=5, relief="flat", fieldbackground=ENTRY_BG_COLOR, foreground=TEXT_COLOR)
        style.configure("TProgressbar", thickness=15, background=PROGRESS_BAR_COLOR, troughcolor='#E0E0E0')
        style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR)
        style.configure("TCheckbutton", background=BG_COLOR, foreground=TEXT_COLOR)
        style.map("TCheckbutton", background=[('active', BG_COLOR)], indicatorcolor=[('selected', BUTTON_COLOR)])
        style.configure("TFrame", background=BG_COLOR)
        style.configure("TLabelframe", background=BG_COLOR, bordercolor="#DDDDDD")
        style.configure("TLabelframe.Label", background=BG_COLOR, foreground=TEXT_COLOR)

        # --- App Variables ---
        self.source_path = tk.StringVar()
        self.target_path = tk.StringVar()
        self.max_workers_var = tk.StringVar(value="16")
        self.chunk_size_var = tk.StringVar(value="64")
        self.file_limit_var = tk.StringVar(value="500")
        self.timeout_var = tk.StringVar(value="10")
        self.debug_mode_var = tk.BooleanVar(value=False)
        self.copy_only_var = tk.BooleanVar(value=False)
        self.enable_intra_disk_check = True # 将从配置文件加载
        
        # --- UI Layout ---
        # Header
        header_frame = ttk.Frame(master, padding=(10, 10))
        header_frame.pack(fill="x")
        ttk.Label(header_frame, text="极速跨盘迁移工具", font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        self.settings_button = ttk.Button(header_frame, text="⚙️ 设置", command=self.toggle_settings_panel)
        self.settings_button.pack(side="right", pady=(0, 4))

        # --- Settings Panel (initially hidden) ---
        self.settings_panel_visible = False
        self.settings_frame = ttk.LabelFrame(master, text="高级设置", padding=(15, 10))
        # Grid configuration for settings
        self.settings_frame.columnconfigure(1, weight=1)
        self.settings_frame.columnconfigure(3, weight=1)
        # Widgets inside settings panel
        ttk.Label(self.settings_frame, text="并行进程数:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(self.settings_frame, textvariable=self.max_workers_var, width=10).grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Label(self.settings_frame, text="包大小上限(MB):").grid(row=0, column=2, sticky="w", padx=(15, 0), pady=5)
        ttk.Entry(self.settings_frame, textvariable=self.chunk_size_var, width=10).grid(row=0, column=3, padx=5, sticky="ew")
        ttk.Label(self.settings_frame, text="包内文件数上限:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(self.settings_frame, textvariable=self.file_limit_var, width=10).grid(row=1, column=1, padx=5, sticky="ew")
        ttk.Label(self.settings_frame, text="超时上限(秒):").grid(row=1, column=2, sticky="w", padx=(15, 0), pady=5)
        ttk.Entry(self.settings_frame, textvariable=self.timeout_var, width=10).grid(row=1, column=3, padx=5, sticky="ew")
        mode_frame = ttk.Frame(self.settings_frame)
        mode_frame.grid(row=2, column=0, columnspan=4, pady=(10,0), sticky="w")
        ttk.Checkbutton(mode_frame, text="调试模式", variable=self.debug_mode_var).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(mode_frame, text="仅复制 (不删除源文件)", variable=self.copy_only_var).pack(side=tk.LEFT)

        # Main Content
        self.content_frame = ttk.Frame(master, padding=(20, 10))
        self.content_frame.pack(fill="both", expand=True)

        # Source
        ttk.Label(self.content_frame, text="源文件夹").pack(anchor="w")
        source_frame = ttk.Frame(self.content_frame)
        source_frame.pack(fill="x", pady=(0, 10))
        self.source_entry = ttk.Entry(source_frame, textvariable=self.source_path)
        self.source_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.source_browse_btn = ttk.Button(source_frame, text="浏览", command=self.select_source)
        self.source_browse_btn.pack(side="left", padx=(5, 0))

        # Target
        ttk.Label(self.content_frame, text="目标文件夹").pack(anchor="w")
        target_frame = ttk.Frame(self.content_frame)
        target_frame.pack(fill="x", pady=(0, 20))
        self.target_entry = ttk.Entry(target_frame, textvariable=self.target_path)
        self.target_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.target_browse_btn = ttk.Button(target_frame, text="浏览", command=self.select_target)
        self.target_browse_btn.pack(side="left", padx=(5, 0))

        # Start Button
        self.start_button = ttk.Button(self.content_frame, text="开始迁移", command=self.start_transfer, style="TButton")
        self.start_button.pack(pady=10, ipady=8, fill="x")

        # Progress Bar
        self.progress = ttk.Progressbar(self.content_frame, orient="horizontal", length=500, mode="determinate")
        self.progress.pack(pady=10, fill="x")
        
        # Status Log
        self.status_label = ttk.Label(self.content_frame, text="状态: 等待操作", anchor="center")
        self.status_label.pack(fill="x")

        # Footer
        self.footer_frame = ttk.Frame(master, padding=(10, 5))
        self.footer_frame.pack(fill="x")
        self.time_label = ttk.Label(self.footer_frame, text="已用时间: 0s")
        self.time_label.pack(side=tk.LEFT)
        self.cache_label = ttk.Label(self.footer_frame, text="缓存占用: 0 MB")
        self.cache_label.pack(side=tk.LEFT, padx=20)
        self.debug_button = ttk.Button(self.footer_frame, text="显示日志", command=self.toggle_log_view)
        self.debug_button.pack(side="right")

        # Log Area (initially hidden)
        self.log_frame = ttk.Frame(master)
        self.log_text = tk.Text(self.log_frame, height=8, width=80, state="disabled", bg="#FFFFFF", fg="#000000", relief="flat", bd=1)
        self.log_scroll = ttk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=self.log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Core Logic Handler ---
        self.transfer_handler = None
        self.log_visible = False
        self.start_time = 0
        self.timer_id = None
        self.gui_queue = queue.Queue()

        # Graceful Exit
        master.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.is_closing = False

        # Load previous settings
        self._load_settings()

        # --- Animations & Effects ---
        self._bind_hover_effects()
        self.source_path.trace_add("write", self._handle_path_change)
        self.target_path.trace_add("write", self._handle_path_change)

    def toggle_settings_panel(self):
        """“手风琴”式展开/收起动画，通过动画化一个占位符框架来实现"""
        if hasattr(self, 'animating') and self.animating:
            return

        if not hasattr(self, 'animation_scaffold'):
            self.animation_scaffold = ttk.Frame(self.master, height=1)

        if self.settings_panel_visible:
            # 收起
            target_height = self.settings_frame.winfo_height()
            self.settings_frame.pack_forget()
            self.animation_scaffold.pack(before=self.content_frame, fill='x')
            self._animate_scaffold(target_height, 1, False)
        else:
            # 展开
            # 先获取目标高度
            self.settings_frame.pack(before=self.content_frame, padx=10, pady=(0, 10), fill="x")
            self.master.update_idletasks()
            target_height = self.settings_frame.winfo_reqheight()
            self.settings_frame.pack_forget()
            
            self.animation_scaffold.pack(before=self.content_frame, fill='x')
            self._animate_scaffold(1, target_height, True)
        
        self.settings_panel_visible = not self.settings_panel_visible

    def _animate_scaffold(self, start_height, end_height, expanding):
        """通过改变占位符高度来实现平滑的推拉效果"""
        self.animating = True
        duration = 200  # ms
        frames = 20
        interval = duration // frames
        
        height_step = (end_height - start_height) / frames
        
        def _step(frame_num):
            if frame_num > frames:
                # 动画结束
                self.animation_scaffold.pack_forget() # 移除占位符
                if expanding:
                    # 换上真正的设置面板
                    self.settings_frame.pack(before=self.content_frame, padx=10, pady=(0, 10), fill="x")
                self.animating = False
                return

            new_height = start_height + height_step * frame_num
            self.animation_scaffold.config(height=int(new_height))
            self.master.after(interval, lambda: _step(frame_num + 1))

        _step(1)

    def _load_settings(self):
        try:
            with open("settings.json", "r", encoding='utf-8') as f:
                settings = json.load(f)
            
            self.source_path.set(settings.get("source_path", ""))
            self.target_path.set(settings.get("target_path", ""))
            self.max_workers_var.set(settings.get("max_workers", "16"))
            self.chunk_size_var.set(settings.get("chunk_size", "64"))
            self.file_limit_var.set(settings.get("file_limit", "500"))
            self.timeout_var.set(settings.get("timeout", "10"))
            self.debug_mode_var.set(settings.get("debug_mode", False))
            self.copy_only_var.set(settings.get("copy_only", False))
            self.enable_intra_disk_check = settings.get("enable_intra_disk_check", True)
            self.log_message("成功加载上次的设置。")
        except (FileNotFoundError, json.JSONDecodeError):
            self.log_message("未找到设置文件，使用默认设置。")
            pass

    def _save_settings(self):
        settings = {
            "source_path": self.source_path.get(),
            "target_path": self.target_path.get(),
            "max_workers": self.max_workers_var.get(),
            "chunk_size": self.chunk_size_var.get(),
            "file_limit": self.file_limit_var.get(),
            "timeout": self.timeout_var.get(),
            "debug_mode": self.debug_mode_var.get(),
            "copy_only": self.copy_only_var.get(),
            "enable_intra_disk_check": self.enable_intra_disk_check,
        }
        try:
            with open("settings.json", "w", encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
        except IOError:
            self.log_message("[警告] 无法保存设置文件。")

    def select_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_path.set(path)

    def select_target(self):
        path = filedialog.askdirectory()
        if path:
            self.target_path.set(path)

    def start_transfer(self):
        self._process_gui_queue()
        source = self.source_path.get()
        target = self.target_path.get()

        if not source or not target:
            messagebox.showerror("错误", "请同时选择源文件夹和目标文件夹。")
            return
        if not os.path.isdir(source):
            messagebox.showerror("错误", f"源文件夹路径无效:\n{source}")
            return
        if not os.path.isdir(target):
            if messagebox.askyesno("确认", f"目标文件夹不存在:\n{target}\n\n是否要创建它？"):
                try:
                    os.makedirs(target)
                except Exception as e:
                    messagebox.showerror("错误", f"无法创建目标文件夹: {e}")
                    return
            else:
                return
        
        # --- 智能模式检测 ---
        try:
            # 检查配置是否启用同盘检测
            if self.enable_intra_disk_check:
                # 仅在非“仅复制”模式下，才启用同盘快速移动
                if not self.copy_only_var.get():
                    source_drive = os.path.splitdrive(os.path.abspath(source))[0]
                    target_drive = os.path.splitdrive(os.path.abspath(target))[0]

                    if source_drive.upper() == target_drive.upper():
                        self.log_message(f"检测到同盘操作 ({source_drive})，将执行快速移动。")
                        self._perform_intra_disk_move(source, target)
                        return # 同盘移动完成后，结束函数
                else:
                    self.log_message("“仅复制”模式已启用，将执行标准复制流程。")
            else:
                self.log_message("同盘移动检测已在配置文件中禁用，强制执行跨盘逻辑。")
        except Exception as e:
            self.log_message(f"[警告] 无法自动检测磁盘驱动器: {e}。将继续执行跨盘逻辑。")
        # --- 结束智能模式检测 ---

        try:
            max_workers = int(self.max_workers_var.get())
            chunk_size_mb = int(self.chunk_size_var.get())
            file_limit = int(self.file_limit_var.get())
            timeout = int(self.timeout_var.get())
            if max_workers <= 0 or chunk_size_mb <= 0 or file_limit <= 0 or timeout <= 0:
                raise ValueError("参数必须为正数")
        except ValueError as e:
            messagebox.showerror("设置错误", f"高级设置中的参数无效: {e}")
            return

        self.start_button.config(state="disabled")
        self.settings_button.config(state="disabled")
        self.status_label.config(text="正在准备迁移...")
        self.progress['value'] = 0
        self.time_label.config(text="已用时间: 0s")
        self.cache_label.config(text="缓存占用: 0 MB")
        self.master.update_idletasks()

        self.start_time = time.time()
        self.update_stats()

        resume_session = False
        temp_cache_dir = os.path.join(source, "_fast_transfer_cache_")
        temp_session_file = os.path.join(temp_cache_dir, "transfer_session.json")

        if os.path.exists(temp_session_file):
            if messagebox.askyesno("恢复任务", "检测到上次有未完成的迁移任务，是否继续？"):
                resume_session = True
            else:
                try:
                    shutil.rmtree(temp_cache_dir)
                except OSError as e:
                    messagebox.showerror("错误", f"无法清理旧的缓存目录: {e}\n请手动删除后重试。")
                    self.start_button.config(state="normal")
                    self.settings_button.config(state="normal")
                    return
        
        self.transfer_handler = TransferLogic(
            source, target, 
            self.update_status, self.log_message,
            max_workers=max_workers,
            chunk_size_mb=chunk_size_mb,
            chunk_file_limit=file_limit,
            timeout_seconds=timeout,
            resume_session=resume_session,
            debug_mode=self.debug_mode_var.get(),
            copy_only=self.copy_only_var.get()
        )
        
        transfer_thread = threading.Thread(target=self._run_transfer_thread, daemon=False)
        transfer_thread.start()

    def _run_transfer_thread(self):
        try:
            self.transfer_handler.run()
            self.gui_queue.put(("transfer_complete", None))
        except Exception as e:
            self.gui_queue.put(("transfer_complete", e))

    def update_stats(self):
        elapsed_seconds = int(time.time() - self.start_time)
        self.time_label.config(text=f"已用时间: {elapsed_seconds}s")
        cache_size = 0
        if self.transfer_handler and os.path.exists(self.transfer_handler.cache_dir):
            for root, _, files in os.walk(self.transfer_handler.cache_dir):
                for name in files:
                    try:
                        cache_size += os.path.getsize(os.path.join(root, name))
                    except FileNotFoundError:
                        continue
        self.cache_label.config(text=f"缓存占用: {cache_size / 1024 / 1024:.2f} MB")
        self.timer_id = self.master.after(1000, self.update_stats)

    def toggle_log_view(self):
        """切换日志区域的可见性，并确保其布局位置正确。"""
        if self.log_visible:
            self.log_frame.pack_forget()
            self.debug_button.config(text="显示日志")
        else:
            # 关键修复：确保日志框架被正确地放置在页脚框架之前
            self.log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True, before=self.footer_frame)
            self.debug_button.config(text="隐藏日志")
        self.log_visible = not self.log_visible

    def log_message(self, message):
        self.gui_queue.put(("log", message))

    def update_status(self, message, progress_value=None):
        self.gui_queue.put(("status", message, progress_value))

    def _bind_hover_effects(self):
        """为主要按钮绑定悬停动效"""
        buttons_to_animate = [
            self.settings_button, 
            self.start_button, 
            self.debug_button
        ]
        # Also include the browse buttons
        for child in self.content_frame.winfo_children():
            if isinstance(child, ttk.Frame):
                for sub_child in child.winfo_children():
                    if isinstance(sub_child, ttk.Button):
                        buttons_to_animate.append(sub_child)

        for btn in buttons_to_animate:
            btn.bind("<Enter>", self._on_enter)
            btn.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        """鼠标进入按钮时的动效 - 简化为仅变色，由style处理"""
        pass

    def _on_leave(self, event):
        """鼠标离开按钮时的动效 - 简化为仅变色，由style处理"""
        pass

    def _handle_path_change(self, *args):
        """当路径文本变化时，自动调整窗口宽度以显示完整路径。"""
        # 使用 after 以确保StringVar更新后再执行
        self.master.after(1, self._adjust_window_width)

    def _adjust_window_width(self):
        try:
            # 获取字体用于测量
            font = tk.font.Font(font=self.source_entry.cget("font"))

            # 计算两个路径中较长的一个所需的宽度
            source_text_width = font.measure(self.source_path.get())
            target_text_width = font.measure(self.target_path.get())
            max_text_width = max(source_text_width, target_text_width)

            # 获取浏览按钮的宽度和一些边距/填充
            self.master.update_idletasks() # 确保能获取到正确的宽度
            browse_btn_width = self.source_browse_btn.winfo_width()
            # 估算总边距：Entry的内边距 + Frame的边距 + 按钮的边距
            padding = 60 

            required_width = max_text_width + browse_btn_width + padding
            current_width = self.master.winfo_width()
            current_height = self.master.winfo_height()

            # 如果需要更宽的窗口
            if required_width > current_width:
                # 设置一个最大宽度，不超过屏幕的90%
                max_width = int(self.master.winfo_screenwidth() * 0.9)
                new_width = min(required_width, max_width)
                self.master.geometry(f"{new_width}x{current_height}")
        except Exception:
            # 如果在UI销毁过程中发生错误，则忽略
            pass

    def _on_closing(self):
        if self.is_closing:
            return
        self._save_settings()
        if self.transfer_handler and self.start_button['state'] == 'disabled':
            if messagebox.askyesno("退出确认", "迁移任务正在进行中，确定要中断并退出吗？\n所有已启动的压缩进程将被终止。"):
                self.is_closing = True
                self.log_message("正在中断任务...")
                self.transfer_handler.stop()
                self.master.destroy()
            else:
                return 
        else:
            self.is_closing = True
            self.master.destroy()

    def _process_gui_queue(self):
        if self.is_closing:
            return
        try:
            while not self.gui_queue.empty():
                msg_type, *args = self.gui_queue.get_nowait()
                if self.is_closing: break
                if msg_type == "log":
                    message, = args
                    self.log_text.config(state="normal")
                    self.log_text.insert(tk.END, message + "\n")
                    self.log_text.see(tk.END)
                    self.log_text.config(state="disabled")
                elif msg_type == "status":
                    message, progress_value = args
                    self.status_label.config(text=f"状态: {message}")
                    self.log_text.config(state="normal")
                    self.log_text.insert(tk.END, f"[状态] {message}\n")
                    self.log_text.see(tk.END)
                    self.log_text.config(state="disabled")
                    if progress_value is not None:
                        self._animate_progress(progress_value)
                elif msg_type == "transfer_complete":
                    error, = args
                    if self.timer_id:
                        self.master.after_cancel(self.timer_id)
                        self.timer_id = None
                    if error:
                        messagebox.showerror("迁移失败", f"发生了一个错误: {error}")
                    else:
                        self.time_label.config(text=f"总耗时: {int(time.time() - self.start_time)}s")
                        messagebox.showinfo("成功", "文件迁移完成！")
                    if self.master.winfo_exists():
                        self.start_button.config(state="normal")
                        self.settings_button.config(state="normal")
                        self.status_label.config(text="状态: 等待操作")
                    return
                elif msg_type == "intra_disk_complete":
                    error, = args
                    if error:
                        messagebox.showerror("盘内移动失败", f"发生了一个错误: {error}")
                        self.status_label.config(text="状态: 盘内移动失败")
                    else:
                        self.progress['value'] = 100
                        self.status_label.config(text="状态: 盘内移动完成！")
                        messagebox.showinfo("成功", "盘内移动完成！")
                    if self.master.winfo_exists():
                        self.start_button.config(state="normal")
                        self.settings_button.config(state="normal")
                    return
        except queue.Empty:
            pass
        self.master.after(100, self._process_gui_queue)

    def _animate_progress(self, target_value):
        """平滑更新进度条的动画"""
        current_value = self.progress['value']
        if abs(target_value - current_value) < 1:
            self.progress['value'] = target_value
            return

        duration = 150  # ms
        frames = 10
        interval = duration // frames
        
        value_step = (target_value - current_value) / frames

        def _step(frame_num):
            if frame_num > frames:
                self.progress['value'] = target_value # 确保最终值精确
                return
            
            new_value = current_value + value_step * frame_num
            self.progress['value'] = new_value
            self.master.after(interval, lambda: _step(frame_num + 1))

        _step(1)

    def _perform_intra_disk_move(self, source, target):
        """在后台线程中执行同盘移动操作，移动源文件夹的内容。"""
        self.start_button.config(state="disabled")
        self.settings_button.config(state="disabled")
        self.status_label.config(text="状态: 正在执行盘内移动...")
        self.progress['value'] = 10 # Give some visual feedback
        self.master.update_idletasks()

        def move_thread_func():
            try:
                items = os.listdir(source)
                total_items = len(items)
                moved_items = 0

                for item_name in items:
                    source_item = os.path.join(source, item_name)
                    dest_item = os.path.join(target, item_name)

                    if os.path.exists(dest_item):
                        # 如果目标已存在，则跳过并记录
                        self.log_message(f"[警告] 目标已存在，跳过移动: {dest_item}")
                        continue
                    
                    # 移动每个文件或文件夹
                    shutil.move(source_item, dest_item)
                    moved_items += 1
                    
                    # 更新UI进度
                    progress = (moved_items / total_items) * 100
                    self.gui_queue.put(("status", f"正在移动: {item_name}", progress))

                self.gui_queue.put(("intra_disk_complete", None))
            except Exception as e:
                self.gui_queue.put(("intra_disk_complete", e))

        threading.Thread(target=move_thread_func, daemon=True).start()


class TransferLogic:
    def __init__(self, source_dir, target_dir, status_callback=print, log_callback=print, 
                 max_workers=8, chunk_size_mb=64, chunk_file_limit=20000, timeout_seconds=15, resume_session=False, debug_mode=False, copy_only=False):
        self.source_dir = os.path.abspath(source_dir)
        self.target_dir = os.path.abspath(target_dir)
        self.status_callback = status_callback
        self.log_callback = log_callback
        
        # Configurable parameters
        self.max_workers = max_workers
        self.chunk_size_limit = chunk_size_mb * 1024 * 1024
        self.chunk_file_limit = chunk_file_limit
        self.timeout = timeout_seconds
        self.resume_session = resume_session
        self.debug_mode = debug_mode
        self.copy_only = copy_only

        self.seven_zip_path = resource_path("7-Zip/7z.exe")
        if not os.path.exists(self.seven_zip_path):
            raise FileNotFoundError(f"7-Zip executable not found at {self.seven_zip_path}")

        # 性能优化：缓存/会话文件应基于源目录，以分离IO操作
        self.cache_dir = os.path.join(self.source_dir, "_fast_transfer_cache_")
        self.session_file_path = os.path.join(self.cache_dir, "transfer_session.json")
        self.task_plan = []
        self.total_transfer_size = 0
        self.processed_size = 0
        self.progress_lock = threading.Lock()
        self.last_reported_progress = -1 # 用于UI更新节流
        
        # 性能优化：用于异步写入会话的队列和锁
        self.completed_task_queue = queue.Queue()
        self.session_write_lock = threading.Lock() # 保护文件写入操作本身
        self.completed_task_ids = set() # 内存中的完成集合，用于快速恢复

        # 优雅退出机制
        self._stop_event = threading.Event()
        self._active_processes = set()
        self._process_lock = threading.Lock()

    def run(self):
        """主执行函数"""
        # 启动会话写入线程
        session_writer_thread = threading.Thread(target=self._session_writer_loop, daemon=True)
        session_writer_thread.start()

        try:
            if self._stop_event.is_set(): return # 启动时就检查是否需要停止
            if self.resume_session:
                self.status_callback("检测到未完成的任务，正在恢复...")
                if not self._load_session():
                    self.log_callback("[警告] 加载会话失败，将作为新任务重新开始。")
                    self.resume_session = False
                    if os.path.exists(self.cache_dir):
                        shutil.rmtree(self.cache_dir)
                    self.task_plan = []
                    self.total_transfer_size = 0
                    self.processed_size = 0
            
            self.recovery_tasks = []
            if not self.resume_session:
                self.status_callback("1. 准备环境...")
                self._prepare_environment()
                self.status_callback("2. 扫描文件并制定计划...")
                self._scan_and_plan()
                self._save_session()
            else: # This is a resume operation
                self._plan_recovery_tasks()

            if not self.task_plan and not self.recovery_tasks and not self.resume_session:
                self.log_callback("没有需要执行的任务。")
                self.status_callback("完成！", 100)
            else:
                self.status_callback(f"3. 开始执行 {len(self.task_plan)} 个任务...")
                self._execute_plan()
                
                if not self._stop_event.is_set():
                    self.status_callback("完成！", 100)

        finally:
            # 终极清理流程：
            # 1. 通知书记员线程结束
            self.completed_task_queue.put(None)
            # 2. 等待书记员完成最后写入并退出
            session_writer_thread.join()
            # 3. 在所有线程结束后，安全地清理缓存
            if not self._stop_event.is_set():
                self.status_callback("6. 清理临时文件...")
                self._cleanup()

    def stop(self):
        """外部调用的停止方法，用于触发优雅退出。"""
        self.log_callback("收到停止信号...")
        self._stop_event.set()
        
        # 立即终止所有由我们启动的7z.exe子进程
        with self._process_lock:
            self._debug_log(f"正在终止 {len(self._active_processes)} 个活动进程...")
            for p in self._active_processes:
                try:
                    p.kill()
                except Exception as e:
                    self._debug_log(f"终止进程 {p.pid} 失败: {e}")
            self._active_processes.clear()

    def _debug_log(self, message):
        """仅在调试模式下记录日志。"""
        if self.debug_mode:
            self.log_callback(message)

    def _prepare_environment(self):
        """创建缓存目录"""
        self._debug_log(f"创建缓存目录: {self.cache_dir}")
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
        os.makedirs(self.cache_dir)

    def _scan_and_plan(self):
        """
        扫描所有文件，动态计算大文件阈值，并创建任务计划。
        """
        self.status_callback("正在扫描文件...")
        all_files = []
        self.total_transfer_size = 0
        for root, _, files in os.walk(self.source_dir):
            # Skip our own cache directory
            if root.startswith(self.cache_dir):
                continue
            for name in files:
                path = os.path.join(root, name)
                try:
                    size = os.path.getsize(path)
                    all_files.append({'path': path, 'size': size})
                    self.total_transfer_size += size
                except FileNotFoundError:
                    # File might be a broken symlink or deleted during scan
                    continue
        
        if not all_files:
            self.status_callback("源文件夹中没有文件可迁移。")
            return

        # 动态计算大文件阈值
        # 逻辑: 文件大小 > (平均文件大小 * 10) 或 > 256MB，取较小者作为阈值。
        # 增加一个保底阈值 16MB，避免在全是小文件的目录中把稍大的文件也判断为大文件。
        avg_size = self.total_transfer_size / len(all_files)
        dynamic_threshold = avg_size * 10
        large_file_threshold = min(dynamic_threshold, 256 * 1024 * 1024) # 256MB
        large_file_threshold = max(large_file_threshold, 16 * 1024 * 1024) # 16MB保底

        self._debug_log(f"总文件数: {len(all_files)}, 总大小: {self.total_transfer_size / 1024 / 1024:.2f} MB")
        self._debug_log(f"平均文件大小: {avg_size / 1024:.2f} KB")
        self.status_callback(f"大文件阈值动态设定为: {large_file_threshold / 1024 / 1024:.2f} MB")
        self._debug_log(f"大文件阈值: {large_file_threshold} 字节")

        small_files_to_pack = []
        for file_info in all_files:
            if file_info['size'] >= large_file_threshold:
                # 大文件直接移动
                self.task_plan.append({
                    'type': 'move_large', 
                    'file_info': file_info,
                    'task_id': str(uuid.uuid4())
                })
            else:
                # 小文件等待打包
                small_files_to_pack.append(file_info)

        # 在分包前，随机打乱小文件列表。
        # 这是解决“老大难”问题的关键：确保每个包里的文件都来自不同目录，从而分散IO压力。
        self._debug_log("正在随机化文件列表以优化IO负载...")
        random.shuffle(small_files_to_pack)

        # 新策略：以文件数量为基础，将任务尽可能平均地分配给每个工作线程
        if self.max_workers > 0 and small_files_to_pack:
            # 计算理论上每个包应该包含多少文件，以实现负载均衡
            ideal_files_per_pack = (len(small_files_to_pack) + self.max_workers - 1) // self.max_workers
            self._debug_log(f"新分包策略: 目标是创建 {self.max_workers} 个包, 每个包约 {ideal_files_per_pack} 个文件。")
        else:
            ideal_files_per_pack = self.chunk_file_limit # Fallback to old limit

        current_chunk = []
        current_chunk_size = 0
        pack_id_counter = 0
        for file_info in small_files_to_pack:
            # 主要以文件数量为分包依据，大小限制作为安全阀
            if current_chunk and (len(current_chunk) >= ideal_files_per_pack or current_chunk_size + file_info['size'] > self.chunk_size_limit):
                pack_id_counter += 1
                self.task_plan.append({
                    'type': 'pack', 
                    'files': current_chunk,
                    'task_id': str(uuid.uuid4()),
                    'pack_id': pack_id_counter # 关键修复：为恢复清理提供依据
                })
                current_chunk = []
                current_chunk_size = 0
            
            current_chunk.append(file_info)
            current_chunk_size += file_info['size']
        
        if current_chunk:
            pack_id_counter += 1
            self.task_plan.append({
                'type': 'pack', 
                'files': current_chunk,
                'task_id': str(uuid.uuid4()),
                'pack_id': pack_id_counter
            })
        
        self._debug_log(f"规划完成。大文件任务数: {len([t for t in self.task_plan if t['type'] == 'move_large'])}")
        self._debug_log(f"规划完成。小文件包任务数: {len([t for t in self.task_plan if t['type'] == 'pack'])}")


    def _execute_plan(self):
        """
        最终架构：使用双线程池和回调链，并优先处理恢复任务。
        """
        if not self.task_plan and not self.recovery_tasks:
            self.status_callback("没有需要执行的任务。")
            return

        cleanup_workers = self.max_workers
        self._debug_log(f"启动主线程池({self.max_workers}工)和清理线程池({cleanup_workers}工)")

        # 使用一个字典来跟踪所有正在进行的任务，包括它们的清理阶段
        self.active_futures = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as transfer_executor, \
             ThreadPoolExecutor(max_workers=cleanup_workers) as cleanup_executor:
            
            self.cleanup_executor = cleanup_executor # 让回调函数可以访问它

            # 1. 优先提交恢复任务
            if self.recovery_tasks:
                self.log_callback(f"优先处理 {len(self.recovery_tasks)} 个已打包的恢复任务...")
                for task in self.recovery_tasks:
                    future = transfer_executor.submit(self._process_main_task, task)
                    self.active_futures[future] = task
                    future.add_done_callback(self._main_task_done_callback)
            
            # 2. 提交剩余的常规任务
            for task in self.task_plan:
                future = transfer_executor.submit(self._process_main_task, task)
                self.active_futures[future] = task
                future.add_done_callback(self._main_task_done_callback)

            # 等待所有任务（包括它们的清理回调）完成
            # 我们需要一个新的机制来等待，因为 as_completed 不适用于回调链
            # 这里我们用心跳检查 active_futures 字典是否清空
            while self.active_futures:
                if self._stop_event.is_set():
                    # 如果收到停止信号，取消所有还未开始的future
                    for f in self.active_futures:
                        f.cancel()
                    break
                time.sleep(0.5)
        
        self._debug_log("所有任务链已完成。")

    def _long_path_prefix(self, path):
        """为Windows路径添加长路径前缀'\\\\?\\'以支持超过260个字符的路径。"""
        # 只在Windows上应用
        if os.name != 'nt':
            return path
        
        path = os.path.abspath(path)
        # 如果路径已经是UNC路径或已添加前缀，则不处理
        if path.startswith('\\\\?\\') or path.startswith('\\\\'):
            return path
        return '\\\\?\\' + path

    def _run_command_with_retry(self, cmd, cwd=None, retries=3):
        """带超时和重试逻辑的执行命令函数，并支持优雅退出。"""
        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.CREATE_NO_WINDOW

        for i in range(retries):
            if self._stop_event.is_set():
                self.log_callback("操作被用户取消。")
                return

            process = None
            try:
                process = subprocess.Popen(
                    cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                    text=True, encoding='gbk', errors='ignore',
                    creationflags=creation_flags
                )
                # 注册活动进程
                with self._process_lock:
                    self._active_processes.add(process)

                stdout, stderr = process.communicate(timeout=self.timeout)
                
                # 任务完成，注销进程
                with self._process_lock:
                    self._active_processes.discard(process)

                if self._stop_event.is_set(): return

                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)
                return # Success
            except subprocess.TimeoutExpired:
                with self._process_lock:
                    self._active_processes.discard(process)
                process.kill()
                if self._stop_event.is_set(): return
                self.log_callback(f"[警告] 命令 {' '.join(cmd)} 超时({self.timeout}s)！正在进行第 {i + 1}/{retries} 次重试...")
                if i == retries - 1:
                    raise
            except Exception as e:
                with self._process_lock:
                    self._active_processes.discard(process)
                # 仅在调试模式下显示完整的命令错误
                self._debug_log(f"[错误] 命令 {' '.join(cmd)} 执行失败: {e}")
                raise

    def _copy_large_file_with_retry(self, source, dest, retries=3, delay=1.0):
        """为大文件复制增加重试逻辑，以应对瞬时IO错误。"""
        for i in range(retries):
            try:
                shutil.copy2(self._long_path_prefix(source), self._long_path_prefix(dest))
                return # Success
            except (IOError, OSError) as e:
                if i < retries - 1:
                    self.log_callback(f"[警告] 复制大文件 {os.path.basename(source)} 失败，将在 {delay}s 后重试... ({e})")
                    time.sleep(delay)
                else:
                    self.log_callback(f"[严重错误] 多次尝试后，复制大文件 {os.path.basename(source)} 仍失败: {e}")
                    raise # 最终失败，将异常抛出

    def _remove_file_with_retry(self, path, retries=5, delay=0.2):
        """带重试逻辑的文件删除，以应对临时文件锁定和只读属性。"""
        prefixed_path = self._long_path_prefix(path)
        for i in range(retries):
            try:
                # 尝试移除只读属性（如果存在）
                try:
                    mode = os.stat(prefixed_path).st_mode
                    if not (mode & stat.S_IWRITE):
                        os.chmod(prefixed_path, mode | stat.S_IWRITE)
                except FileNotFoundError:
                    return True # 文件已经被其他线程删除，视为成功
                except Exception as e:
                    self._debug_log(f"[警告] 无法修改文件属性 {path}: {e}")

                # 尝试删除
                os.remove(prefixed_path)
                return True # 删除成功
            except OSError as e:
                if i < retries - 1:
                    self._debug_log(f"[警告] 删除文件 {path} 失败，将在 {delay}s 后重试... ({e})")
                    time.sleep(delay)
                else:
                    self.log_callback(f"[严重错误] 多次尝试后，删除文件 {path} 仍失败: {e}")
                    return False # 最终失败

    def _process_main_task(self, task):
        """第一阶段：由主工人执行的高负载任务。成功后返回待清理文件列表。"""
        if task['type'] == 'pack':
            pack_id = task['pack_id'] # 关键修复：必须使用任务自带的、不变的ID
            self.log_callback(f"开始处理包 {pack_id}...")
            
            archive_name = f"pack_{pack_id}.7z"
            archive_path = self._long_path_prefix(os.path.join(self.cache_dir, archive_name))
            file_list_path = os.path.join(self.cache_dir, f"filelist_{pack_id}.txt")

            with open(file_list_path, 'w', encoding='utf-8') as f:
                for file_info in task['files']:
                    relative_path = os.path.relpath(file_info['path'], self.source_dir)
                    f.write(relative_path + "\n")
            
            cmd_pack = [self.seven_zip_path, 'a', archive_path, f'@{file_list_path}', '-mx0', '-mmt']
            self._debug_log(f"[主工-{threading.get_ident()}] 打包 {archive_name}...")
            self._run_command_with_retry(cmd_pack, cwd=self._long_path_prefix(self.source_dir))

            self._debug_log(f"[主工-{threading.get_ident()}] 直接从源盘解压 {archive_name} 到目标盘...")
            cmd_extract = [
                self.seven_zip_path, 'x',
                archive_path, # 直接使用源盘缓存区的压缩包路径
                f'-o{self._long_path_prefix(self.target_dir)}',
                '-y', '-mmt'
            ]
            self._run_command_with_retry(cmd_extract)

            # 任务成功，返回结构化的清理指令
            return {
                "files_to_delete": [archive_path, file_list_path], # 清理源盘的压缩包和文件列表
                "source_paths_for_dir_cleanup": [f['path'] for f in task['files']]
            }
        
        elif task['type'] == 'resume_extract':
            pack_id = task['pack_id']
            self.log_callback(f"恢复处理已存在的包 {pack_id}...")
            
            archive_name = f"pack_{pack_id}.7z"
            archive_path = self._long_path_prefix(os.path.join(self.cache_dir, archive_name))
            file_list_path = os.path.join(self.cache_dir, f"filelist_{pack_id}.txt")

            self._debug_log(f"[主工-{threading.get_ident()}] 直接从源盘缓存解压 {archive_name} 到目标盘...")
            cmd_extract = [
                self.seven_zip_path, 'x',
                archive_path,
                f'-o{self._long_path_prefix(self.target_dir)}',
                '-y', '-mmt'
            ]
            self._run_command_with_retry(cmd_extract)

            # 任务成功，返回结构化的清理指令
            return {
                "files_to_delete": [archive_path, file_list_path],
                "source_paths_for_dir_cleanup": [f['path'] for f in task['files']]
            }

        elif task['type'] == 'move_large':
            file_info = task['file_info']
            filename = os.path.basename(file_info['path'])
            relative_path = os.path.relpath(file_info['path'], self.source_dir)
            target_path = os.path.join(self.target_dir, relative_path)
            
            os.makedirs(self._long_path_prefix(os.path.dirname(target_path)), exist_ok=True)

            if self.copy_only:
                self.log_callback(f"开始复制大文件: {filename}")
                self._copy_large_file_with_retry(file_info['path'], target_path)
                # 在复制模式下，没有源文件需要清理
                return {
                    "files_to_delete": [],
                    "source_paths_for_dir_cleanup": []
                }
            else:
                self.log_callback(f"开始移动大文件: {filename}")
                shutil.move(self._long_path_prefix(file_info['path']), self._long_path_prefix(target_path))
                # 在移动模式下，shutil.move已删除源文件，我们只需清理空目录
                return {
                    "files_to_delete": [],
                    "source_paths_for_dir_cleanup": [file_info['path']]
                }

    def _main_task_done_callback(self, future):
        """第一层回调：主任务完成后，检查结果并派发清理任务。"""
        original_task = self.active_futures.pop(future, None)
        if not original_task: return # 可能已被取消

        try:
            # 获取主任务的结果（即结构化的清理指令）
            cleanup_instructions = future.result()

            # 如果是“仅复制”模式，则移除删除源文件的指令
            if self.copy_only:
                self._debug_log(f"仅复制模式：跳过任务 {original_task.get('task_id')} 的源文件清理。")
                cleanup_instructions["source_paths_for_dir_cleanup"] = []
            
            # 派发清理任务（在复制模式下，这只会清理缓存和压缩包）
            cleanup_future = self.cleanup_executor.submit(self._process_cleanup_task, cleanup_instructions)
            self.active_futures[cleanup_future] = original_task # 跟踪清理任务
            cleanup_future.add_done_callback(self._cleanup_task_done_callback)

        except Exception as e:
            # 主任务失败，记录错误，不进行清理
            task_type = original_task.get('type', '未知')
            self.log_callback(f"[严重错误] {task_type} 任务 {original_task.get('task_id')} 的主流程失败: {e}")
            # 更新进度
            failed_task_size = 0
            if task_type == 'pack':
                failed_task_size = sum(f['size'] for f in original_task.get('files', []))
            elif task_type == 'move_large':
                failed_task_size = original_task.get('file_info', {}).get('size', 0)
            with self.progress_lock:
                self.processed_size += failed_task_size
                progress = (self.processed_size / self.total_transfer_size) * 100
                self.status_callback(f"一个任务失败，已跳过", progress)

    def _process_cleanup_task(self, instructions):
        """第二阶段：由清理工执行的低功耗任务，使用结构化指令。"""
        if self._stop_event.is_set(): return
        
        files_to_delete = instructions.get("files_to_delete", [])
        source_paths_for_dir_cleanup = instructions.get("source_paths_for_dir_cleanup", [])

        self._debug_log(f"[清理工-{threading.get_ident()}] 开始清理 {len(files_to_delete) + len(source_paths_for_dir_cleanup)} 个相关项目...")

        # 1. 删除指定的临时文件和源文件
        # 对于打包任务，这里会包含源文件
        for path in source_paths_for_dir_cleanup:
             if self._stop_event.is_set(): return
             self._remove_file_with_retry(path)
        # 对于所有任务，这里包含缓存文件和压缩包
        for path in files_to_delete:
            if self._stop_event.is_set(): return
            self._remove_file_with_retry(path)
        
        # 2. 只对原始的源文件路径进行空目录清理
        if source_paths_for_dir_cleanup:
            dummy_file_infos = [{'path': p} for p in source_paths_for_dir_cleanup]
            self._cleanup_empty_dirs(dummy_file_infos)
        
        self._debug_log(f"[清理工-{threading.get_ident()}] 清理完成。")

    def _cleanup_task_done_callback(self, future):
        """第二层回调：清理任务完成后，最终标记整个原子任务为完成。"""
        original_task = self.active_futures.pop(future, None)
        if not original_task: return

        try:
            future.result() # 检查清理任务是否出错
            # 整个原子任务成功，更新进度并标记完成
            task_type = original_task.get('type')
            task_size = 0
            if task_type == 'pack':
                task_size = sum(f['size'] for f in original_task.get('files', []))
            elif task_type == 'move_large':
                task_size = original_task.get('file_info', {}).get('size', 0)
            
            with self.progress_lock:
                self.processed_size += task_size
                progress = (self.processed_size / self.total_transfer_size) * 100
                if int(progress) > self.last_reported_progress:
                    self.last_reported_progress = int(progress)
                    self.status_callback(f"进度 {int(progress)}%", progress)
            
            self._mark_task_complete(original_task)

        except Exception as e:
            self.log_callback(f"[严重错误] 任务 {original_task.get('task_id')} 的清理流程失败: {e}")

    def _plan_recovery_tasks(self):
        """
        在恢复任务前，扫描源盘缓存文件夹，为已存在但未完成的压缩包创建优先恢复任务。
        """
        self.log_callback("扫描恢复任务...")
        
        try:
            with open(self.session_file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            full_task_plan = session_data.get('task_plan', [])
        except (IOError, json.JSONDecodeError):
            self.log_callback("[警告] 无法读取会话文件进行恢复规划，跳过。")
            return

        # 创建一个从 pack_id 到任务的映射，以便快速查找
        pack_id_to_task = {t['pack_id']: t for t in full_task_plan if t['type'] == 'pack'}
        
        # 扫描源盘缓存文件夹中的残留压缩包
        try:
            if not os.path.exists(self.cache_dir): return # 缓存目录不存在，无法恢复
            for item in os.listdir(self.cache_dir):
                if item.startswith("pack_") and item.endswith(".7z"):
                    try:
                        pack_id = int(item.split('_')[1].split('.')[0])
                        original_task = pack_id_to_task.get(pack_id)

                        # 如果这个包对应的任务存在，且未完成，则创建恢复任务
                        if original_task and original_task['task_id'] not in self.completed_task_ids:
                            self.log_callback(f"发现可恢复的压缩包: {item}")
                            
                            # 创建一个新的、特殊的恢复任务
                            recovery_task = original_task.copy()
                            recovery_task['type'] = 'resume_extract'
                            self.recovery_tasks.append(recovery_task)
                            
                            # 从主任务计划中移除这个任务，避免重复打包
                            self.task_plan = [t for t in self.task_plan if t['task_id'] != original_task['task_id']]

                    except (ValueError, IndexError):
                        # 文件名不规范，忽略
                        continue
        except Exception as e:
            self.log_callback(f"[警告] 扫描恢复任务时发生错误: {e}")


    def _save_session(self):
        """将当前任务计划保存到会话文件。"""
        self._debug_log("创建会话文件...")
        session_data = {
            "source_dir": self.source_dir,
            "target_dir": self.target_dir,
            "total_transfer_size": self.total_transfer_size,
            "task_plan": self.task_plan,
            "completed_task_ids": []
        }
        try:
            with open(self.session_file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=4)
        except IOError as e:
            self.log_callback(f"[严重错误] 无法写入会话文件: {e}")

    def _load_session(self):
        """
        根据新的原子性算法加载会话。
        任何未被记录为“完成”的任务都将被重新执行。
        """
        self._debug_log("正在加载会话文件...")
        try:
            with open(self.session_file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            if session_data.get('source_dir') != self.source_dir or \
               session_data.get('target_dir') != self.target_dir:
                self.log_callback("[警告] 会话文件与当前目录不匹配。将作为新任务开始。")
                return False

            self.total_transfer_size = session_data.get('total_transfer_size', 0)
            full_task_plan = session_data.get('task_plan', [])
            self.completed_task_ids = set(session_data.get('completed_task_ids', []))

            self.processed_size = 0
            self.task_plan = []
            
            for task in full_task_plan:
                task_id = task.get('task_id')
                if task_id in self.completed_task_ids:
                    # 任务已完成，累加进度
                    if task['type'] == 'pack':
                        self.processed_size += sum(f['size'] for f in task['files'])
                    elif task['type'] == 'move_large':
                        self.processed_size += task['file_info']['size']
                else:
                    # 任务未完成，加入执行计划
                    self.task_plan.append(task)
            
            self._debug_log(f"会话加载成功。{len(self.completed_task_ids)}个任务已完成。")
            self.log_callback(f"剩余任务数: {len(self.task_plan)}")
            
            if self.total_transfer_size > 0:
                progress = (self.processed_size / self.total_transfer_size) * 100
                self.status_callback(f"已恢复进度 {progress:.1f}%", progress)

            return True
        except (IOError, json.JSONDecodeError) as e:
            self.log_callback(f"[错误] 读取或解析会话文件失败: {e}")
            return False

    def _mark_task_complete(self, task):
        """将完成的任务ID放入队列，由独立线程处理文件写入，避免阻塞工作线程。"""
        self.completed_task_queue.put(task['task_id'])

    def _session_writer_loop(self):
        """
        终极性能优化：此循环在独立线程中运行，以基于时间的方式批量更新会话文件，
        而不是为每个完成的任务都写入一次，从而将磁盘I/O降至最低。
        """
        last_write_time = time.time()
        pending_ids = False
        while True:
            try:
                # 等待新任务，但有超时，这样我们可以定期检查是否需要写入
                task_id = self.completed_task_queue.get(timeout=1.0)
                if task_id is None:
                    # 收到结束信号
                    if pending_ids:
                        self._debug_log("[书记员] 收到结束信号，正在进行最后一次写入...")
                        self._write_session_to_disk()
                    self._debug_log("[书记员] 最终写入完成，线程退出。")
                    break
                
                self.completed_task_ids.add(task_id)
                pending_ids = True
                self.completed_task_queue.task_done()

            except queue.Empty:
                # 队列为空，这是我们检查是否需要写入的好时机
                pass

            # 每隔5秒，或者当有待处理的ID时，进行一次写入
            current_time = time.time()
            if pending_ids and (current_time - last_write_time > 5.0):
                self._debug_log("[书记员] 批量写入会话...")
                self._write_session_to_disk()
                last_write_time = current_time
                pending_ids = False
    
    def _write_session_to_disk(self):
        """
        将内存中完整的已完成任务ID集合写入会话文件。
        采用原子写入模式，防止文件损坏。
        """
        with self.session_write_lock:
            temp_file_path = self.session_file_path + ".tmp"
            try:
                # 1. 读取当前状态（如果存在）
                try:
                    with open(self.session_file_path, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    # 如果文件不存在或损坏，从头创建
                    session_data = {
                        "source_dir": self.source_dir,
                        "target_dir": self.target_dir,
                        "total_transfer_size": self.total_transfer_size,
                        "task_plan": self.task_plan,
                        "completed_task_ids": []
                    }

                # 2. 更新内存中的数据
                session_data['completed_task_ids'] = list(self.completed_task_ids)

                # 3. 写入临时文件
                with open(temp_file_path, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=4)
                
                # 4. 原子替换
                os.replace(temp_file_path, self.session_file_path)

            except (IOError, json.JSONDecodeError) as e:
                self.log_callback(f"[严重错误][书记员] 原子写入会话文件失败: {e}")
                # 如果失败，尝试清理临时文件
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)


    def _cleanup_empty_dirs(self, list_of_file_infos, base_dir=None):
        """在删除文件后，递归删除所有空的父目录。"""
        if base_dir is None:
            base_dir = self.source_dir

        # 获取所有被删除文件所在的目录
        dirs_to_check = set(os.path.dirname(f['path']) for f in list_of_file_infos)
        
        for d in dirs_to_check:
            # 从当前目录开始，向上回溯，尝试删除
            # 直到遇到非空目录或抵达指定的基准目录为止
            current_dir = d
            # 在判断和操作时，都使用长路径前缀
            while current_dir != base_dir and os.path.isdir(self._long_path_prefix(current_dir)):
                try:
                    prefixed_dir = self._long_path_prefix(current_dir)
                    if not os.listdir(prefixed_dir):
                        self._debug_log(f"清理空目录: {current_dir}")
                        os.rmdir(prefixed_dir)
                        # 如果删除成功，将目标指向父目录，进行下一次循环
                        current_dir = os.path.dirname(current_dir)
                    else:
                        # 如果目录不为空，则停止这条线的向上回溯
                        break
                except OSError as e:
                    # 如果因任何原因（如权限问题）删除失败，也停止回溯并记录日志
                    self.log_callback(f"[警告] 无法清理目录 {current_dir}: {e}")
                    break


    def _cleanup(self):
        """删除缓存目录"""
        if os.path.exists(self.cache_dir):
            self._debug_log(f"清理缓存目录: {self.cache_dir}")
            shutil.rmtree(self.cache_dir)

def main():
    root = tk.Tk()
    app = FileTransferApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
