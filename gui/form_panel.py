# -*- coding: utf-8 -*-
"""表单面板"""

import tkinter as tk
from tkinter import ttk

from core.models import FormSpec


class FormPanel(ttk.LabelFrame):
    """动态表单面板：根据 FormSpec 生成表单控件"""

    def __init__(self, parent, on_field_change=None, **kwargs):
        super().__init__(parent, text="填写信息", padding="10", **kwargs)
        self.field_widgets = {}
        self._on_field_change = on_field_change
        self._build_scrollable_body()

    def _build_scrollable_body(self):
        """构建可滚动表单区域"""
        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.form_frame = ttk.Frame(self.canvas)
        self.form_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮：进入画布时绑定，离开时解绑
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def build(self, form_spec: FormSpec):
        """根据表单规格重建表单"""
        # 清空旧控件
        for widget in self.form_frame.winfo_children():
            widget.destroy()
        self.field_widgets = {}

        if not form_spec or not form_spec.fields:
            ttk.Label(self.form_frame, text="该账单类型没有可填写的字段", foreground="gray").pack(pady=20)
            return

        for field in form_spec.fields:
            frame = ttk.Frame(self.form_frame)
            frame.pack(fill=tk.X, pady=2)
            ttk.Label(frame, text=field.label, width=20, anchor="e").pack(side=tk.LEFT, padx=(0, 10))
            var = tk.StringVar(value=field.default_value)
            if self._on_field_change:
                var.trace_add("write", lambda *_: self._on_field_change())
            ttk.Entry(frame, textvariable=var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.field_widgets[field.placeholder] = var

    def clear(self):
        """清空表单"""
        for widget in self.form_frame.winfo_children():
            widget.destroy()
        self.field_widgets = {}
        ttk.Label(self.form_frame, text="请先选择账单类型", foreground="gray").pack(pady=20)

    def get_values(self) -> dict:
        """收集所有字段当前值"""
        return {ph: var.get() for ph, var in self.field_widgets.items()}

    def set_values(self, values: dict):
        """批量设置字段值"""
        for ph, var in self.field_widgets.items():
            if ph in values:
                var.set(values[ph])

    def set_value(self, placeholder: str, value: str):
        """设置单个字段值"""
        if placeholder in self.field_widgets:
            self.field_widgets[placeholder].set(value)