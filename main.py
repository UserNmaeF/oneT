#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oneT
从模板生成账单PDF/图片，无需登录，无水印
"""

import sys
import os

# 确保项目根目录在 sys.path 中
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import socket
import tkinter as tk
from tkinter import messagebox

from core.services.bill_service import BillService
from core.services.address_service import AddressService
from core.template_loader import TemplateLoader
from renderers.playwright import PlaywrightRenderer
from gui.controller import BillController
from gui.app import BillGeneratorApp

# 单实例锁端口（仅绑定本机回环，不对外监听；冲突概率可忽略）
_SINGLETON_PORT = 47771


def acquire_singleton():
    """尝试获取单实例锁：绑定本机回环端口成功即为首个实例

    Returns:
        锁 socket（保持引用防止释放），非首个实例返回 None
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", _SINGLETON_PORT))
        sock.listen(1)
        return sock
    except OSError:
        return None


def main():
    # ─── 单实例检查：重复启动时弹窗提示并退出 ───
    lock_sock = acquire_singleton()
    if lock_sock is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning(
            "oneT 已在运行",
            "oneT 已有一个实例正在运行。\n请使用已打开的窗口，或先关闭它再启动新实例。",
            parent=root,
        )
        root.destroy()
        return

    # 创建依赖
    template_loader = TemplateLoader()
    renderer = PlaywrightRenderer()
    address_service = AddressService()
    bill_service = BillService(template_loader=template_loader, renderer=renderer)

    # 创建控制器
    controller = BillController(
        bill_service=bill_service,
        address_service=address_service,
        renderer=renderer,
    )

    # 启动 GUI
    root = tk.Tk()
    app = BillGeneratorApp(root, controller)

    def on_close():
        # 停止回调轮询 → 关窗 → 释放浏览器资源
        controller.stop_polling()
        root.destroy()
        renderer.close()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

    # 释放单实例锁
    try:
        lock_sock.close()
    except OSError:
        pass


if __name__ == "__main__":
    main()
