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

import ctypes
import socket
import tkinter as tk
from tkinter import messagebox

from core.services.bill_service import BillService
from core.services.address_service import AddressService
from core.template_loader import TemplateLoader
from renderers.playwright import PlaywrightRenderer
from gui.controller import BillController
from gui.app import BillGeneratorApp

# ─── 单实例锁配置 ───
# 命名互斥体名称（Windows 内核对象，进程异常退出/崩溃时由 OS 自动释放，
# 不存在端口绑定方案中 TIME_WAIT 残留导致的“假阳性”问题）
_SINGLETON_MUTEX = "Local\\oneT_Singleton_Mutex"
# 预留的回环端口仅作第二道防线；绑定前设置 SO_REUSEADDR，避免端口残留
_SINGLETON_PORT = 47771

# 单实例锁完全不可用时的哨兵值：调用方应放行启动（锁故障 ≠ 已有实例）
UNAVAILABLE = object()

# 互斥体已存在的哨兵值：明确表示"已有实例在运行"，与机制不可用区分开
_MUTEX_EXISTS = object()

# Windows 错误码：ERROR_ALREADY_EXISTS
_ERROR_ALREADY_EXISTS = 183


def _create_mutex_handle():
    """创建/打开命名互斥体。

    Returns:
        int: 新建互斥体的内核句柄（本实例抢到锁）
        _MUTEX_EXISTS: 同名互斥体已存在（已有实例在运行）
        None: 互斥体机制不可用（非 Windows / 创建失败），应走端口回退
    """
    if sys.platform != "win32":
        return None

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.restype = ctypes.c_void_p
    create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]

    handle = create_mutex(None, False, _SINGLETON_MUTEX)
    if not handle:
        return None  # 创建失败（权限等），交由端口回退
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)  # 已存在：释放本次临时句柄
        return _MUTEX_EXISTS
    return handle


def acquire_singleton():
    """尝试获取单实例锁。

    优先使用 Windows 命名互斥体（可靠、无 TIME_WAIT 残留），
    仅当互斥体机制本身不可用时才回退到端口绑定。

    Returns:
        (kind, token) 锁标记；None 表示已有实例在运行；
        UNAVAILABLE 表示锁机制故障（调用方应放行启动）
    """
    # 1) 命名互斥体主方案：已存在即判定"已有实例"，不再走端口回退
    result = _create_mutex_handle()
    if result is _MUTEX_EXISTS:
        return None
    if result is not None:
        return ("mutex", result)

    # 2) 回退：绑定回环端口，并允许地址复用，减少 TIME_WAIT 残留误判
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", _SINGLETON_PORT))
        sock.listen(1)
        return ("port", sock)
    except OSError:
        # 两种锁都不可用（如端口被系统保留：WinError 10013）。
        # 返回 UNAVAILABLE 让调用方放行启动，避免把锁故障误判为“已有实例”。
        return UNAVAILABLE


def release_singleton(lock):
    """释放单实例锁。mutex 句柄随进程退出由内核清理，端口锁需显式关闭。

    Parameters:
        lock: acquire_singleton() 的返回值 (kind, token)
    """
    if lock is None or lock is UNAVAILABLE:
        return
    kind, token = lock
    if kind == "port":
        try:
            token.close()
        except OSError:
            pass
    elif kind == "mutex":
        # 显式关闭互斥体句柄；同进程内再次调用时可重新抢占单实例锁
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle(token)
        except Exception:
            pass


def main():
    # ─── 单实例检查：重复启动时弹窗提示并退出 ───
    lock = acquire_singleton()
    if lock is UNAVAILABLE:
        # 锁机制故障（如端口被系统保留）：放行启动，仅控制台提示
        print("警告: 单实例锁不可用，本次启动不做单实例限制", file=sys.stderr)
    elif lock is None:
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
    if lock is not UNAVAILABLE:
        release_singleton(lock)


if __name__ == "__main__":
    main()
