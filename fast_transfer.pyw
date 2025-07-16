# -*- coding: utf-8 -*-

import os
import random
import shutil
import stat
import subprocess
import sys
import threading
import time
import tkinter as tk
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
        # 移除固定的初始大小，让窗口根据内容自适应
        # master.geometry("600x550")

        # --- UI Elements ---
        # Source Directory
        self.source_label = tk.Label(master, text="源文件夹:")
        self.source_label.pack(pady=5)
        self.source_path = tk.StringVar()
        self.source_entry = tk.Entry(master, textvariable=self.source_path, width=70)
        self.source_entry.pack(padx=10)
        self.source_button = tk.Button(master, text="选择源文件夹", command=self.select_source)
        self.source_button.pack()

        # Target Directory
        self.target_label = tk.Label(master, text="目标文件夹:")
        self.target_label.pack(pady=5)
        self.target_path = tk.StringVar()
        self.target_entry = tk.Entry(master, textvariable=self.target_path, width=70)
        self.target_entry.pack(padx=10)
        self.target_button = tk.Button(master, text="选择目标文件夹", command=self.select_target)
        self.target_button.pack(pady=(0, 10))

        # --- Advanced Settings ---
        settings_frame = tk.LabelFrame(master, text="高级设置", padx=10, pady=10)
        settings_frame.pack(padx=10, pady=10, fill="x")

        # Max Workers
        tk.Label(settings_frame, text="并行进程数:").grid(row=0, column=0, sticky="w")
        self.max_workers_var = tk.StringVar(value="16")
        tk.Entry(settings_frame, textvariable=self.max_workers_var, width=10).grid(row=0, column=1, padx=5)

        # Chunk Size
        tk.Label(settings_frame, text="包大小上限(MB):").grid(row=0, column=2, sticky="w", padx=(10, 0))
        self.chunk_size_var = tk.StringVar(value="64")
        tk.Entry(settings_frame, textvariable=self.chunk_size_var, width=10).grid(row=0, column=3, padx=5)

        # File Count Limit
        tk.Label(settings_frame, text="包内文件数上限:").grid(row=0, column=4, sticky="w", padx=(10, 0))
        self.file_limit_var = tk.StringVar(value="500")
        tk.Entry(settings_frame, textvariable=self.file_limit_var, width=10).grid(row=0, column=5, padx=5)

        # Timeout
        tk.Label(settings_frame, text="超时上限(秒):").grid(row=1, column=0, sticky="w", pady=(5,0))
        self.timeout_var = tk.StringVar(value="10")
        tk.Entry(settings_frame, textvariable=self.timeout_var, width=10).grid(row=1, column=1, padx=5, pady=(5,0))

        # Start Button
        self.start_button = tk.Button(master, text="开始迁移", command=self.start_transfer, font=("Arial", 12, "bold"))
        self.start_button.pack(pady=10)

        # Stats Frame
        self.stats_frame = tk.Frame(master)
        self.stats_frame.pack(pady=5)

        self.time_label = tk.Label(self.stats_frame, text="已用时间: 0s")
        self.time_label.pack(side=tk.LEFT, padx=10)

        self.cache_label = tk.Label(self.stats_frame, text="缓存占用: 0 MB")
        self.cache_label.pack(side=tk.LEFT, padx=10)

        # Progress Bar
        self.progress = ttk.Progressbar(master, orient="horizontal", length=500, mode="determinate")
        self.progress.pack(pady=10)
        
        # Status Log
        self.status_label = tk.Label(master, text="状态: 等待操作")
        self.status_label.pack()

        # Debug/Log Area
        self.log_frame = tk.Frame(master)
        self.log_text = tk.Text(self.log_frame, height=10, width=80, state="disabled")
        self.log_scroll = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=self.log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Debug toggle button
        self.debug_button = tk.Button(master, text="显示日志", command=self.toggle_log_view)
        self.debug_button.pack(pady=5)

        # --- Core Logic Handler ---
        self.transfer_handler = None
        self.log_visible = False
        self.start_time = 0
        self.timer_id = None

    def select_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_path.set(path)

    def select_target(self):
        path = filedialog.askdirectory()
        if path:
            self.target_path.set(path)

    def start_transfer(self):
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
        self.status_label.config(text="正在准备迁移...")
        self.progress['value'] = 0
        self.time_label.config(text="已用时间: 0s")
        self.cache_label.config(text="缓存占用: 0 MB")
        self.master.update_idletasks()

        self.start_time = time.time()
        self.update_stats()

        self.transfer_handler = TransferLogic(
            source, target, 
            self.update_status, self.log_message,
            max_workers=max_workers,
            chunk_size_mb=chunk_size_mb,
            chunk_file_limit=file_limit,
            timeout_seconds=timeout
        )
        
        # Run the transfer logic in a separate thread to avoid blocking the UI
        transfer_thread = threading.Thread(target=self._run_transfer_thread)
        transfer_thread.daemon = True  # Allows main window to exit even if thread is running
        transfer_thread.start()

    def _run_transfer_thread(self):
        try:
            self.transfer_handler.run()
            self.master.after(0, self._on_transfer_complete, None)
        except Exception as e:
            self.master.after(0, self._on_transfer_complete, e)

    def _on_transfer_complete(self, error):
        if self.timer_id:
            self.master.after_cancel(self.timer_id)
            self.timer_id = None
        
        if error:
            messagebox.showerror("迁移失败", f"发生了一个错误: {error}")
        else:
            # 先更新最终时间，再显示会阻塞进程的对话框
            self.time_label.config(text=f"总耗时: {int(time.time() - self.start_time)}s")
            messagebox.showinfo("成功", "文件迁移完成！")

        self.start_button.config(state="normal")
        self.status_label.config(text="状态: 等待操作")


    def update_stats(self):
        # Update timer
        elapsed_seconds = int(time.time() - self.start_time)
        self.time_label.config(text=f"已用时间: {elapsed_seconds}s")

        # Update cache size
        cache_size = 0
        if self.transfer_handler and os.path.exists(self.transfer_handler.cache_dir):
            for root, _, files in os.walk(self.transfer_handler.cache_dir):
                for name in files:
                    try:
                        cache_size += os.path.getsize(os.path.join(root, name))
                    except FileNotFoundError:
                        continue
        self.cache_label.config(text=f"缓存占用: {cache_size / 1024 / 1024:.2f} MB")
        
        self.timer_id = self.master.after(1000, self.update_stats) # Schedule next update

    def toggle_log_view(self):
        if self.log_visible:
            self.log_frame.pack_forget()
            self.debug_button.config(text="显示日志")
            # 移除手动调整窗口大小的逻辑，让Tkinter自动处理
            # self.master.geometry("600x450")
        else:
            self.log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
            self.debug_button.config(text="隐藏日志")
            # 移除手动调整窗口大小的逻辑，让Tkinter自动处理
            # self.master.geometry("600x650")
        self.log_visible = not self.log_visible

    def log_message(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.master.update_idletasks()

    def update_status(self, message, progress_value=None):
        self.status_label.config(text=f"状态: {message}")
        self.log_message(f"[状态] {message}") # Also log status updates
        if progress_value is not None:
            self.progress['value'] = progress_value
        self.master.update_idletasks()


class TransferLogic:
    def __init__(self, source_dir, target_dir, status_callback=print, log_callback=print, 
                 max_workers=8, chunk_size_mb=64, chunk_file_limit=20000, timeout_seconds=15):
        self.source_dir = os.path.abspath(source_dir)
        self.target_dir = os.path.abspath(target_dir)
        self.status_callback = status_callback
        self.log_callback = log_callback
        
        # Configurable parameters
        self.max_workers = max_workers
        self.chunk_size_limit = chunk_size_mb * 1024 * 1024
        self.chunk_file_limit = chunk_file_limit
        self.timeout = timeout_seconds

        self.seven_zip_path = resource_path("7-Zip/7z.exe")
        if not os.path.exists(self.seven_zip_path):
            raise FileNotFoundError(f"7-Zip executable not found at {self.seven_zip_path}")

        self.cache_dir = os.path.join(self.source_dir, "_fast_transfer_cache_")
        self.task_plan = []
        self.total_transfer_size = 0
        self.processed_size = 0
        self.progress_lock = threading.Lock()
        self.pack_counter = 0

    def run(self):
        """主执行函数"""
        self.status_callback("1. 准备环境...")
        self._prepare_environment()

        self.status_callback("2. 扫描文件并制定计划...")
        self._scan_and_plan()

        self.status_callback(f"3. 开始执行 {len(self.task_plan)} 个任务...")
        self._execute_plan()

        self.status_callback("4. 清理临时文件...")
        self._cleanup()
        
        self.status_callback("完成！", 100)

    def _prepare_environment(self):
        """创建缓存目录"""
        self.log_callback(f"创建缓存目录: {self.cache_dir}")
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

        self.log_callback(f"总文件数: {len(all_files)}, 总大小: {self.total_transfer_size / 1024 / 1024:.2f} MB")
        self.log_callback(f"平均文件大小: {avg_size / 1024:.2f} KB")
        self.status_callback(f"大文件阈值动态设定为: {large_file_threshold / 1024 / 1024:.2f} MB")
        self.log_callback(f"大文件阈值: {large_file_threshold} 字节")

        small_files_to_pack = []
        for file_info in all_files:
            if file_info['size'] >= large_file_threshold:
                # 大文件直接移动
                self.task_plan.append({'type': 'move_large', 'file_info': file_info})
            else:
                # 小文件等待打包
                small_files_to_pack.append(file_info)

        # 在分包前，随机打乱小文件列表。
        # 这是解决“老大难”问题的关键：确保每个包里的文件都来自不同目录，从而分散IO压力。
        self.log_callback("正在随机化文件列表以优化IO负载...")
        random.shuffle(small_files_to_pack)

        # 新策略：以文件数量为基础，将任务尽可能平均地分配给每个工作线程
        if self.max_workers > 0 and small_files_to_pack:
            # 计算理论上每个包应该包含多少文件，以实现负载均衡
            ideal_files_per_pack = (len(small_files_to_pack) + self.max_workers - 1) // self.max_workers
            self.log_callback(f"新分包策略: 目标是创建 {self.max_workers} 个包, 每个包约 {ideal_files_per_pack} 个文件。")
        else:
            ideal_files_per_pack = self.chunk_file_limit # Fallback to old limit

        current_chunk = []
        current_chunk_size = 0
        for file_info in small_files_to_pack:
            # 主要以文件数量为分包依据，大小限制作为安全阀
            if current_chunk and (len(current_chunk) >= ideal_files_per_pack or current_chunk_size + file_info['size'] > self.chunk_size_limit):
                self.task_plan.append({'type': 'pack', 'files': current_chunk})
                current_chunk = []
                current_chunk_size = 0
            
            current_chunk.append(file_info)
            current_chunk_size += file_info['size']
        
        if current_chunk:
            self.task_plan.append({'type': 'pack', 'files': current_chunk})
        
        self.log_callback(f"规划完成。大文件任务数: {len([t for t in self.task_plan if t['type'] == 'move_large'])}")
        self.log_callback(f"规划完成。小文件包任务数: {len([t for t in self.task_plan if t['type'] == 'pack'])}")


    def _execute_plan(self):
        """
        使用线程池并行执行计划中的任务。
        采用'as_completed'模式，任何任务完成后都会立即处理其结果，
        并能容忍单个任务的失败而不中断整个流程。
        """
        if self.total_transfer_size == 0:
            self.status_callback("没有需要执行的任务。")
            return

        self.log_callback(f"启动线程池，最大并行进程数: {self.max_workers}")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._process_task, task): task for task in self.task_plan}
            
            for future in as_completed(futures):
                task = futures[future]
                try:
                    # 获取任务结果。如果任务在执行期间抛出异常，这里会重新抛出。
                    future.result()
                except Exception as e:
                    # 捕获并记录失败，但不中断整个迁移过程
                    task_type = task.get('type', '未知')
                    if task_type == 'pack':
                        # 为了日志清晰，我们尝试获取pack_id，但这在失败时可能不可行
                        # 因此我们只记录这是一个打包任务失败了
                        self.log_callback(f"[严重错误] 一个打包任务在多次重试后最终失败: {e}")
                    elif task_type == 'move_large':
                        filename = os.path.basename(task.get('file_info', {}).get('path', '未知文件'))
                        self.log_callback(f"[严重错误] 移动大文件 {filename} 失败: {e}")
                    
                    # 标记这部分大小为“已处理”（尽管是失败的），避免进度条卡住
                    failed_task_size = 0
                    if task_type == 'pack':
                        failed_task_size = sum(f['size'] for f in task.get('files', []))
                    elif task_type == 'move_large':
                        failed_task_size = task.get('file_info', {}).get('size', 0)

                    with self.progress_lock:
                        self.processed_size += failed_task_size
                        progress = (self.processed_size / self.total_transfer_size) * 100
                        self.status_callback(f"一个任务失败，已跳过", progress)

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
        """带超时和重试逻辑的执行命令函数"""
        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.CREATE_NO_WINDOW

        for i in range(retries):
            try:
                # 使用 Popen 而不是 run，以便在超时后可以杀死进程
                # 在中文Windows上，命令行工具通常使用'gbk'编码
                # 使用 CREATE_NO_WINDOW 标志来阻止为子进程创建控制台窗口
                process = subprocess.Popen(
                    cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                    text=True, encoding='gbk', errors='ignore',
                    creationflags=creation_flags
                )
                stdout, stderr = process.communicate(timeout=self.timeout)
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)
                return # Success
            except subprocess.TimeoutExpired:
                process.kill() # 杀死卡死的进程
                self.log_callback(f"[警告] 命令 {' '.join(cmd)} 超时({self.timeout}s)！正在进行第 {i + 1}/{retries} 次重试...")
                if i == retries - 1: # Last retry failed
                    raise
            except Exception as e:
                self.log_callback(f"[错误] 命令 {' '.join(cmd)} 执行失败: {e}")
                raise

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
                    self.log_callback(f"[警告] 无法修改文件属性 {path}: {e}")

                # 尝试删除
                os.remove(prefixed_path)
                return True # 删除成功
            except OSError as e:
                if i < retries - 1:
                    self.log_callback(f"[警告] 删除文件 {path} 失败，将在 {delay}s 后重试... ({e})")
                    time.sleep(delay)
                else:
                    self.log_callback(f"[严重错误] 多次尝试后，删除文件 {path} 仍失败: {e}")
                    return False # 最终失败

    def _process_task(self, task):
        """处理单个任务（打包或移动大文件），此方法将在工作线程中执行。"""
        if task['type'] == 'pack':
            with self.progress_lock:
                self.pack_counter += 1
                pack_id = self.pack_counter

            self.log_callback(f"[工人-{threading.get_ident()}] 开始处理包 {pack_id}")
            
            archive_name = f"pack_{pack_id}.7z"
            # 应用长路径前缀
            archive_path = self._long_path_prefix(os.path.join(self.cache_dir, archive_name))
            file_list_path = os.path.join(self.cache_dir, f"filelist_{pack_id}.txt") # filelist本身路径短，无需前缀

            with open(file_list_path, 'w', encoding='utf-8') as f:
                for file_info in task['files']:
                    # 文件列表内使用相对路径，不受长路径影响
                    relative_path = os.path.relpath(file_info['path'], self.source_dir)
                    f.write(relative_path + "\n")
            
            cmd_pack = [self.seven_zip_path, 'a', archive_path, f'@{file_list_path}', '-mx0']
            self.log_callback(f"[工人-{threading.get_ident()}] 打包 {archive_name}...")
            # CWD也需要长路径支持
            self._run_command_with_retry(cmd_pack, cwd=self._long_path_prefix(self.source_dir))

            self.log_callback(f"[工人-{threading.get_ident()}] 移动 {archive_name}...")
            # shutil.move 在现代Python中通常支持长路径，无需额外处理
            moved_archive_path = shutil.move(archive_path, self._long_path_prefix(self.target_dir))

            self.log_callback(f"[工人-{threading.get_ident()}] 解压 {archive_name}...")
            # 为解压命令的所有绝对路径添加前缀
            cmd_extract = [
                self.seven_zip_path, 'x', 
                self._long_path_prefix(moved_archive_path), 
                f'-o{self._long_path_prefix(self.target_dir)}'
            ]
            self._run_command_with_retry(cmd_extract)

            self._remove_file_with_retry(moved_archive_path)
            self._remove_file_with_retry(file_list_path)

            pack_size = 0
            for file_info in task['files']:
                pack_size += file_info['size']
                self._remove_file_with_retry(file_info['path'])
            
            self._cleanup_empty_dirs(task['files'])

            with self.progress_lock:
                self.processed_size += pack_size
                progress = (self.processed_size / self.total_transfer_size) * 100
                self.status_callback(f"包 {pack_id} 处理完成", progress)

        elif task['type'] == 'move_large':
            file_info = task['file_info']
            filename = os.path.basename(file_info['path'])
            self.log_callback(f"[工人-{threading.get_ident()}] 开始移动大文件: {filename}")

            relative_path = os.path.relpath(file_info['path'], self.source_dir)
            target_path = os.path.join(self.target_dir, relative_path)
            
            # 确保目标目录存在，同样使用长路径
            os.makedirs(self._long_path_prefix(os.path.dirname(target_path)), exist_ok=True)
            # 对move操作的源和目标都使用长路径，确保万无一失
            shutil.move(self._long_path_prefix(file_info['path']), self._long_path_prefix(target_path))
            
            # 移动后，源文件已不存在，但我们需要它的路径来清理目录
            self._cleanup_empty_dirs([file_info])

            with self.progress_lock:
                self.processed_size += file_info['size']
                progress = (self.processed_size / self.total_transfer_size) * 100
                self.status_callback(f"大文件 {filename} 移动完成", progress)

    def _cleanup_empty_dirs(self, list_of_files):
        """在删除文件后，递归删除所有空的父目录。"""
        # 获取所有被删除文件所在的目录
        dirs_to_check = set(os.path.dirname(f['path']) for f in list_of_files)
        
        for d in dirs_to_check:
            # 从当前目录开始，向上回溯，尝试删除
            # 直到遇到非空目录或抵达总的源目录为止
            current_dir = d
            # 只要当前目录不是总的源目录，就继续尝试
            # 在判断和操作时，都使用长路径前缀
            while current_dir != self.source_dir and os.path.isdir(self._long_path_prefix(current_dir)):
                try:
                    prefixed_dir = self._long_path_prefix(current_dir)
                    if not os.listdir(prefixed_dir):
                        self.log_callback(f"清理空目录: {current_dir}")
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
            self.log_callback(f"清理缓存目录: {self.cache_dir}")
            shutil.rmtree(self.cache_dir)

def main():
    root = tk.Tk()
    app = FileTransferApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
