# -*- coding: utf-8 -*-
"""控制器：协调视图与业务逻辑（线程安全版）

GUI 回调统一经 _callback_queue 投递，由主线程 start_polling 轮询执行。
禁止从渲染线程直接调用 root.after —— tkinter 控件方法非线程安全，
跨线程调用会导致回调丢失/错序/RuntimeError（预览异常的历史根因）。
"""

import os
import queue
import threading
import tempfile
from PIL import Image


class BillController:
    """账单控制器：处理业务逻辑，所有 GUI 回调通过主线程安全调度"""

    def __init__(self, bill_service, address_service, renderer, call_main_thread=None):
        """
        Args:
            call_main_thread: 兼容旧接口；新代码使用 start_polling(root)
        """
        self.bill_service = bill_service
        self.address_service = address_service
        self.renderer = renderer
        self._call_main_thread = call_main_thread or (lambda fn: fn())

        # 主线程回调队列：渲染线程 put，主线程轮询 get 后执行
        self._callback_queue = queue.Queue()
        self._poll_root = None       # 由 start_polling 设置
        self._poll_active = False    # 轮询循环运行标记

        # 状态
        self.current_bt_code = None
        self._preview_timer_id = None
        self._preview_running = False
        self._preview_pending = False
        # 预览代际号：每次重新调度 +1；in-flight 渲染完成时若代际已过期
        # （期间用户切换了类型/字段），结果直接丢弃，防止旧类型预览覆盖新表单
        self._preview_generation = 0
        self._root = None  # 由 app 设置，用于 after/after_cancel

        # 视图回调（由 app 层设置，保证在主线程调用）
        self.on_status = None          # fn(text, color)
        self.on_preview_loading = None  # fn()
        self.on_preview_ready = None    # fn(PIL.Image)
        self.on_preview_done = None     # fn()
        self.on_preview_error = None    # fn(text)

    def start_polling(self, root):
        """启动主线程回调轮询（必须且只需从主线程调用一次）

        此后所有渲染线程回调经 _safe_call 入队，在此处出队执行，
        彻底避免 tkinter 跨线程调用。
        """
        self._poll_root = root
        self._root = root
        if not self._poll_active:
            self._poll_active = True
            root.after(50, self._poll_loop)

    def _poll_loop(self):
        """主线程轮询：取出并执行队列中的 GUI 回调"""
        try:
            while True:
                callback, args = self._callback_queue.get_nowait()
                try:
                    callback(*args)
                except Exception:
                    # 单个回调异常不中断轮询循环
                    pass
        except queue.Empty:
            pass
        if self._poll_active:
            self._poll_root.after(50, self._poll_loop)

    def stop_polling(self):
        """停止轮询（窗口销毁前调用）"""
        self._poll_active = False

    def _safe_call(self, callback, *args):
        """将 GUI 回调投递到主线程队列（任意线程可调用）"""
        if callback is None:
            return
        self._callback_queue.put((callback, args))

    def load_initial(self):
        """初始化加载模板"""
        self.bill_service.load_templates()

    # ─── 事件处理 ───

    def on_type_change(self, bt_code, form_spec):
        """账单类型切换"""
        self.current_bt_code = bt_code
        self._cancel_preview_timer()
        self._schedule_preview()

    def on_field_change(self):
        """表单字段变化"""
        self._schedule_preview()

    # ─── 预览逻辑 ───

    def _cancel_preview_timer(self):
        if self._preview_timer_id is not None:
            try:
                if self._root:
                    self._root.after_cancel(self._preview_timer_id)
            except Exception:
                pass
            self._preview_timer_id = None

    def _schedule_preview(self):
        """防抖调度预览：1.5 秒无变化后自动生成"""
        self._cancel_preview_timer()
        # 代际号 +1：使仍在渲染中的旧任务结果过期
        self._preview_generation += 1
        # 预览状态只更新预览面板，不动底部状态栏
        if self.on_preview_loading:
            self._safe_call(self.on_preview_loading)
        if self._root:
            self._preview_timer_id = self._root.after(1500, self._do_preview)

    def _do_preview(self):
        """执行预览生成（在主线程中由 root.after 调度）"""
        self._preview_timer_id = None
        if self._preview_running:
            self._preview_pending = True
            return
        if not self.current_bt_code:
            return

        # 快照：类型 + 字段值 + 代际号。渲染期间用户切换类型时，
        # 快照保证本次任务自洽，且完成时可检测代际过期并丢弃
        gen = self._preview_generation
        bt_code = self.current_bt_code
        field_values = self._get_field_values()

        self._preview_running = True
        # 预览状态只更新预览面板
        if self.on_preview_loading:
            self._safe_call(self.on_preview_loading)

        def render_job():
            try:
                html = self.bill_service.generate_html(bt_code, field_values)
                if html is None:
                    raise ValueError("模板数据不存在")

                # render_png_bytes 内部通过 ThreadPoolExecutor
                # 调度到固定 worker 线程，避免跨线程 Playwright 问题
                png_bytes = self.renderer.render_png_bytes(html)

                tmp_file = os.path.join(tempfile.gettempdir(), "bill_preview.png")
                with open(tmp_file, "wb") as f:
                    f.write(png_bytes)

                img = Image.open(tmp_file)
                if gen == self._preview_generation:
                    self._safe_call(self.on_preview_ready, img)
            except Exception as e:
                if gen == self._preview_generation:
                    self._safe_call(self.on_preview_error, str(e))
            finally:
                self._safe_call(self.on_preview_done)
                self._preview_running = False
                if self._preview_pending:
                    self._preview_pending = False
                    self._schedule_preview()

        threading.Thread(target=render_job, daemon=True).start()

    def refresh_preview(self):
        """手动刷新预览"""
        self._cancel_preview_timer()
        self._do_preview()

    # ─── 地址填充 ───

    def fill_random_address(self, region_code):
        """填充随机真实地址"""
        values = self.address_service.get_address_as_dict(region_code)
        source = self.address_service.last_source
        if values:
            label = "API" if "RandomUser" in source else "本地库"
            self._safe_call(self.on_status, f"✓ 已填充地址 ({label})", "#4CAF50")
        return values

    # ─── 输出生成 ───

    def generate_output(self, fmt, field_values, output_path):
        """生成输出文件（PDF/PNG）"""
        html = self.bill_service.generate_html(self.current_bt_code, field_values)
        if html is None:
            raise ValueError("生成 HTML 失败")

        self._safe_call(self.on_status, f"正在生成 {fmt.upper()}...", "#2196F3")

        def render_job():
            try:
                if fmt == "pdf":
                    self.renderer.render_pdf(html, output_path)
                else:
                    self.renderer.render_png(html, output_path)
                self._safe_call(self.on_status, f"✓ 已保存: {output_path}", "#4CAF50")
            except Exception as e:
                self._safe_call(self.on_status, f"✗ 生成失败: {e}", "#f44336")
                raise

        threading.Thread(target=render_job, daemon=True).start()

    # ─── 辅助 ───

    def _get_field_values(self):
        """获取表单字段当前值（必须从主线程调用）"""
        return getattr(self, '_field_values_getter', lambda: {})()

    def get_field_defaults(self, bt_code=None):
        """获取默认字段值"""
        return self.bill_service.get_field_defaults(bt_code or self.current_bt_code)