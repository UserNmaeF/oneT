# -*- coding: utf-8 -*-
"""预览面板"""

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk


class PreviewPanel(ttk.LabelFrame):
    """预览面板：模拟纸张效果展示账单预览图，点击可放大查看"""

    PREVIEW_BG = "#e8e8e8"
    PAPER_SHADOW = "#c0c0c0"
    PAPER_BORDER = "#d0d0d0"
    CANVAS_WIDTH = 400
    THUMB_MAX_W = 380          # 缩略图最大宽度
    ZOOM_MIN = 0.1             # 放大窗口最小比例
    ZOOM_MAX = 3.0             # 放大窗口最大比例
    ZOOM_STEP = 1.1            # 滚轮缩放步长

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="预览", padding="8", **kwargs)
        self._full_image = None      # 原图（供放大预览）
        self._preview_photo = None   # 缩略图 PhotoImage（防止 GC）
        self._zoom_window = None     # 放大窗口引用
        self._build_status_bar()
        self._build_canvas()

    def _build_status_bar(self):
        """状态栏（预览自动刷新，无需手动按钮）"""
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 8))
        self.status_label = ttk.Label(bar, text="输入自动刷新", foreground="gray")
        self.status_label.pack(side=tk.LEFT)
        ttk.Label(bar, text="点击预览可放大", foreground="#999999").pack(side=tk.RIGHT)

    def _build_canvas(self):
        """预览画布（模拟纸张效果）"""
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            canvas_frame,
            bg=self.PREVIEW_BG,
            width=self.CANVAS_WIDTH,
            highlightthickness=0,
            relief=tk.FLAT,
        )
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮滚动缩略图
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # 点击预览图打开放大窗口
        self.canvas.bind("<Button-1>", lambda e: self._open_zoom_window())

    # ─── 公开方法 ───

    def set_status(self, text, color="gray"):
        self.status_label.config(text=text, foreground=color)

    def show_placeholder(self):
        """显示初始占位提示"""
        self._full_image = None
        self._preview_photo = None
        self.canvas.delete("all")
        w = self.CANVAS_WIDTH
        h = 300
        # 纸张阴影
        self.canvas.create_rectangle(12, 12, w + 12, h + 12, fill="#cccccc", outline="")
        # 白纸
        self.canvas.create_rectangle(8, 8, w + 8, h + 8, fill="#ffffff", outline=self.PAPER_BORDER, width=1)
        # 提示文字
        self.canvas.create_text(
            w // 2 + 8, h // 2 - 10,
            text="修改字段后自动刷新",
            fill="#bbbbbb", font=("Arial", 14),
        )
        self.canvas.create_text(
            w // 2 + 8, h // 2 + 15,
            text="点击预览可放大",
            fill="#bbbbbb", font=("Arial", 11),
        )
        self.canvas.configure(scrollregion=(0, 0, w + 20, h + 20))

    def show_image(self, img: Image.Image):
        """显示预览图片（带纸张效果），并保留原图供放大"""
        self._full_image = img
        # 生成缩略图
        thumb = img
        w, h = img.size
        if w > self.THUMB_MAX_W:
            ratio = self.THUMB_MAX_W / w
            thumb = img.resize((self.THUMB_MAX_W, int(h * ratio)), Image.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(thumb)

        self.canvas.delete("all")
        img_w, img_h = thumb.size
        # 纸张阴影（右下偏移）
        shadow = 6
        self.canvas.create_rectangle(
            shadow + 8, shadow + 8, img_w + shadow + 8, img_h + shadow + 8,
            fill="#c0c0c0", outline="",
        )
        # 白纸背景
        self.canvas.create_rectangle(
            8, 8, img_w + 8, img_h + 8,
            fill="#ffffff", outline=self.PAPER_BORDER, width=1,
        )
        # 缩略图
        self.canvas.create_image(8, 8, anchor="nw", image=self._preview_photo)
        self.canvas.configure(scrollregion=(0, 0, img_w + 20, img_h + 20))

    def clear(self):
        """清空画布"""
        self._full_image = None
        self._preview_photo = None
        self.canvas.delete("all")

    # ─── 放大预览窗口 ───

    def _open_zoom_window(self):
        """打开放大预览窗口（滚轮缩放 / 左键拖动）"""
        if self._full_image is None:
            return
        # 已有窗口则提升到前台
        if self._zoom_window is not None and self._zoom_window.winfo_exists():
            self._zoom_window.lift()
            self._zoom_window.focus_force()
            return

        win = tk.Toplevel(self)
        win.title(f"账单预览 - 放大（{self._full_image.width}×{self._full_image.height}px）")
        win.geometry("920x720")
        win.minsize(420, 320)
        win.configure(bg="#f0f2f5")
        self._zoom_window = win
        win.protocol("WM_DELETE_WINDOW", self._close_zoom_window)

        # 工具栏：缩放比例 + 操作提示
        toolbar = ttk.Frame(win)
        toolbar.pack(fill=tk.X, padx=8, pady=6)
        self._zoom_scale_label = ttk.Label(toolbar, text="100%", font=("Arial", 11, "bold"))
        self._zoom_scale_label.pack(side=tk.LEFT)
        ttk.Label(toolbar, text="  滚轮缩放 · 左键拖动 · 右键关闭", foreground="#888888").pack(side=tk.LEFT, padx=8)

        # 画布 + 双滚动条
        canvas_frame = ttk.Frame(win)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(canvas_frame, bg="#e8e8e8", highlightthickness=0)
        hbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self._zoom_canvas = canvas

        # 状态
        canvas._zoom_scale = 1.0
        canvas._zoom_photo = None
        canvas._img_w = self._full_image.width
        canvas._img_h = self._full_image.height

        def render():
            """按当前缩放比例重绘图片"""
            scale = canvas._zoom_scale
            new_w = max(1, int(canvas._img_w * scale))
            new_h = max(1, int(canvas._img_h * scale))
            img = self._full_image.resize((new_w, new_h), Image.LANCZOS)
            canvas._zoom_photo = ImageTk.PhotoImage(img)
            canvas.delete("all")
            canvas.create_image(0, 0, anchor="nw", image=canvas._zoom_photo)
            canvas.configure(scrollregion=(0, 0, new_w, new_h))
            self._zoom_scale_label.config(text=f"{int(scale * 100)}%")

        def on_wheel(event):
            factor = self.ZOOM_STEP if event.delta > 0 else 1 / self.ZOOM_STEP
            scale = max(self.ZOOM_MIN, min(self.ZOOM_MAX, canvas._zoom_scale * factor))
            canvas._zoom_scale = scale
            render()

        # 事件绑定
        canvas.bind("<MouseWheel>", on_wheel)
        canvas.bind("<ButtonPress-1>", lambda e: canvas.scan_mark(e.x, e.y))
        canvas.bind("<B1-Motion>", lambda e: canvas.scan_dragto(e.x, e.y, gain=1))
        win.bind("<Button-3>", lambda e: self._close_zoom_window())

        render()

    def _close_zoom_window(self):
        """关闭放大窗口"""
        if self._zoom_window is not None:
            try:
                self._zoom_window.destroy()
            except Exception:
                pass
            self._zoom_window = None