# -*- coding: utf-8 -*-
"""渲染器抽象接口"""

from abc import ABC, abstractmethod


class Renderer(ABC):
    """渲染器接口：将 HTML 渲染为 PDF/PNG"""

    @abstractmethod
    def render_pdf(self, html_content: str, output_path: str) -> None:
        """渲染为 PDF 文件"""

    @abstractmethod
    def render_png(self, html_content: str, output_path: str) -> None:
        """渲染为 PNG 图片"""

    @abstractmethod
    def render_png_bytes(self, html_content: str) -> bytes:
        """渲染为 PNG 图片字节流（用于预览）"""