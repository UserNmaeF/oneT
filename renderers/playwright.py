# -*- coding: utf-8 -*-
"""Playwright 渲染器实现（线程安全版）

保留 Chromium/Skia 原生 Creator/Producer/CreationDate，不做任何后处理。
"""

import threading
import re
from concurrent.futures import ThreadPoolExecutor

from renderers.base import Renderer

# PDF 页眉页脚 margin（仅当模板提供约定 <template id="pdf-header|pdf-footer"> 时启用）
_PDF_HEADER_MARGIN_TOP = "22mm"
_PDF_FOOTER_MARGIN_BOTTOM = "18mm"
_PDF_SIDE_MARGIN = "0mm"


def _settle_page(page, html_content: str) -> None:
    """注入 HTML 并等待渲染稳定

    - networkidle 只保证网络空闲；base64 data URI 字体不产生网络请求，
      需显式等待 document.fonts.ready，避免截图/出 PDF 时仍用 fallback 字体
    - 追加一帧 rAF + 50ms，让字体切换后的重排完成
    """
    page.set_content(html_content, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.evaluate(
        "new Promise(r => requestAnimationFrame(() => setTimeout(r, 50)))"
    )


class PlaywrightRenderer(Renderer):
    """使用 Playwright (Chromium headless) 渲染 HTML

    线程安全设计：
    - Playwright sync API 禁止跨线程使用浏览器实例
    - 因此使用 ThreadPoolExecutor 固定 2 个 worker 线程
    - 每个 worker 线程通过 threading.local 缓存自己的 browser
    - 浏览器实例复用，避免每次启动 Chromium 的开销
    """

    def __init__(self, max_workers: int = 2):
        self._thread_local = threading.local()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="bill-renderer",
        )
        self._lock = threading.Lock()
        self._browsers = []  # 记录所有 browser 实例，用于关闭

    def _get_browser(self):
        """获取当前线程的浏览器实例（按线程缓存）"""
        local = self._thread_local
        if not hasattr(local, "browser"):
            from playwright.sync_api import sync_playwright
            local.playwright = sync_playwright().start()
            local.browser = local.playwright.chromium.launch(headless=True)
            with self._lock:
                self._browsers.append(local)
        return local.browser

    def _run(self, func, *args, **kwargs):
        """在渲染线程池中执行 Playwright 调用"""
        future = self._executor.submit(func, *args, **kwargs)
        return future.result()

    def render_pdf(self, html_content: str, output_path: str) -> None:
        """渲染为 PDF 文件

        PDF 元数据保留 Chromium 原生输出（Creator/Producer/CreationDate），
        不做任何后处理。
        模板可通过 <template id="pdf-header"> / <template id="pdf-footer">
        提供每页重复页眉页脚；检测到约定元素时启用 displayHeaderFooter。
        """
        def job():
            browser = self._get_browser()
            page = browser.new_page()
            header_match = re.search(
                r'<template\s+id="pdf-header">(.*?)</template>', html_content, re.S | re.I
            )
            footer_match = re.search(
                r'<template\s+id="pdf-footer">(.*?)</template>', html_content, re.S | re.I
            )
            header_html = header_match.group(1) if header_match else None
            footer_html = footer_match.group(1) if footer_match else None
            try:
                _settle_page(page, html_content)
                if header_html or footer_html:
                    page.pdf(
                        path=output_path,
                        format="A4",
                        print_background=True,
                        display_header_footer=True,
                        header_template=header_html or "<div></div>",
                        footer_template=footer_html or "<div></div>",
                        margin={
                            "top": _PDF_HEADER_MARGIN_TOP,
                            "bottom": _PDF_FOOTER_MARGIN_BOTTOM,
                            "left": _PDF_SIDE_MARGIN,
                            "right": _PDF_SIDE_MARGIN,
                        },
                    )
                else:
                    page.pdf(path=output_path, format="A4", print_background=True)
            finally:
                page.close()
            self._run(job)

    def render_png(self, html_content: str, output_path: str) -> None:
        def job():
            browser = self._get_browser()
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            try:
                _settle_page(page, html_content)
                page.screenshot(path=output_path, full_page=True)
            finally:
                page.close()
        self._run(job)

    def render_png_bytes(self, html_content: str) -> bytes:
        def job():
            browser = self._get_browser()
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            try:
                _settle_page(page, html_content)
                return page.screenshot(full_page=True)
            finally:
                page.close()
        return self._run(job)

    def close(self):
        """关闭所有浏览器实例，释放资源"""
        with self._lock:
            browsers = self._browsers[:]
            self._browsers.clear()
        for local in browsers:
            try:
                local.browser.close()
            except Exception:
                pass
            try:
                local.playwright.stop()
            except Exception:
                pass
        self._executor.shutdown(wait=False)
