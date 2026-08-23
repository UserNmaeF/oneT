# -*- coding: utf-8 -*-
"""主窗口应用"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from config.settings import REGIONS, BILL_TYPES, REGION_CODE_MAP
from gui.controller import BillController
from gui.form_panel import FormPanel
from gui.preview_panel import PreviewPanel


class BillGeneratorApp:
    """oneT 主窗口"""

    def __init__(self, root, controller: BillController):
        self.root = root
        self.ctrl = controller
        self._build_ui()
        self._connect_controller()

    def _build_ui(self):
        self.root.title("oneT")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ─── 顶部：选择区域 ───
        top_frame = ttk.LabelFrame(main_frame, text="选择账单类型", padding="10")
        top_frame.pack(fill=tk.X, pady=(0, 10))

        region_frame = ttk.Frame(top_frame)
        region_frame.pack(fill=tk.X, pady=5)

        ttk.Label(region_frame, text="地区:").pack(side=tk.LEFT)
        self.region_combo = ttk.Combobox(region_frame, state="readonly", width=15)
        self.region_combo.pack(side=tk.LEFT, padx=(5, 20))
        self.region_combo.bind("<<ComboboxSelected>>", self._on_region_change)

        ttk.Label(region_frame, text="账单类型:").pack(side=tk.LEFT)
        self.type_combo = ttk.Combobox(region_frame, state="readonly", width=35)
        self.type_combo.pack(side=tk.LEFT, padx=5)
        self.type_combo.bind("<<ComboboxSelected>>", self._on_type_change)

        # ─── 中间：左表单 + 右预览 ───
        mid_frame = ttk.Frame(main_frame)
        mid_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 左：表单
        self.form_panel = FormPanel(mid_frame, on_field_change=self._on_field_change)
        self.form_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 右：预览
        self.preview_panel = PreviewPanel(mid_frame)
        self.preview_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))

        # ─── 底部按钮 ───
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        self.status_label = ttk.Label(btn_frame, text="", foreground="gray")
        self.status_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="生成PDF", command=self._generate_pdf).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="生成PNG图片", command=self._generate_png).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="一键填充", command=self._fill_defaults).pack(side=tk.RIGHT, padx=5)

        # ─── 初始化 ───
        region_names = [r["name"] for r in REGIONS]
        self.region_combo["values"] = region_names
        self.preview_panel.show_placeholder()

    def _connect_controller(self):
        # 注入字段值获取器
        self.ctrl._field_values_getter = self.form_panel.get_values

        # 连接控制器回调；启动主线程轮询消费渲染线程的回调队列
        self.ctrl.start_polling(self.root)
        self.ctrl.on_status = self._set_status
        self.ctrl.on_preview_loading = lambda: self.preview_panel.set_status("生成中...", "#2196F3")
        self.ctrl.on_preview_ready = lambda img: (self.preview_panel.show_image(img),
                                                  self.preview_panel.set_status("✓ 已更新", "#4CAF50"))
        self.ctrl.on_preview_done = lambda: None
        self.ctrl.on_preview_error = lambda msg: self.preview_panel.set_status(f"✗ {msg}", "#f44336")

        # 加载模板
        self.ctrl.load_initial()

        # 默认选中英国
        region_names = list(self.region_combo["values"])
        if region_names:
            try:
                uk_idx = region_names.index("英国")
            except ValueError:
                uk_idx = 0
            self.region_combo.current(uk_idx)
            self._on_region_change(None)

    def _set_status(self, text, color="gray"):
        self.status_label.config(text=text, foreground=color)

    def _get_region_id(self):
        idx = self.region_combo.current()
        if idx < 0:
            return None
        return REGIONS[idx]["id"]

    def _on_region_change(self, event):
        region_id = self._get_region_id()
        if region_id is None:
            return
        types = [bt for bt in BILL_TYPES if bt["region_id"] == region_id]
        self.type_combo["values"] = [bt["name"] for bt in types]
        if types:
            self.type_combo.current(0)
            self._on_type_change(None)

    def _on_type_change(self, event):
        idx = self.type_combo.current()
        if idx < 0:
            return
        region_id = self._get_region_id()
        types = [bt for bt in BILL_TYPES if bt["region_id"] == region_id]
        if idx >= len(types):
            return
        bt_code = types[idx]["code"]
        self.ctrl.current_bt_code = bt_code

        # 构建表单
        form_spec = self.ctrl.bill_service.get_form_spec(bt_code)
        if form_spec:
            self.form_panel.build(form_spec)
        else:
            self.form_panel.clear()

        self.ctrl.on_type_change(bt_code, form_spec)

    def _on_field_change(self):
        self.ctrl.on_field_change()

    def _fill_defaults(self):
        if not self.ctrl.current_bt_code:
            return
        defaults = self.ctrl.get_field_defaults()

        # 同时获取随机真实地址（API 优先，本地兜底），合并到默认值中
        region_id = self._get_region_id()
        if region_id is not None:
            region_code = REGION_CODE_MAP.get(region_id)
            if region_code:
                addr_values = self.ctrl.fill_random_address(region_code)
                if addr_values:
                    defaults.update(addr_values)  # 地址覆盖默认值

        self.form_panel.set_values(defaults)
        self.ctrl.on_field_change()

    def _fill_random_address(self):
        if not self.ctrl.current_bt_code:
            return
        region_id = self._get_region_id()
        if region_id is None:
            return
        region_code = REGION_CODE_MAP.get(region_id)
        if not region_code:
            return
        values = self.ctrl.fill_random_address(region_code)
        if values:
            self.form_panel.set_values(values)
            self.ctrl._schedule_preview()

    def _generate_pdf(self):
        self._generate("pdf")

    def _generate_png(self):
        self._generate("png")

    def _generate(self, fmt):
        if not self.ctrl.current_bt_code:
            messagebox.showwarning("提示", "请先选择账单类型")
            return
        field_values = self.form_panel.get_values()
        html = self.ctrl.bill_service.generate_html(self.ctrl.current_bt_code, field_values)
        if html is None:
            messagebox.showerror("错误", "模板数据不存在")
            return

        default_name = f"bill_{self.ctrl.current_bt_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}"
        file_path = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper() + "文件", f"*.{fmt}"), ("所有文件", "*.*")],
            initialfile=default_name,
        )
        if not file_path:
            return

        self.ctrl.generate_output(fmt, field_values, file_path)