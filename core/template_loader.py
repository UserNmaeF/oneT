# -*- coding: utf-8 -*-
"""模板加载器：从模板目录加载账单模板"""

import json
from pathlib import Path

from config import settings
from core.models import Template


class TemplateLoader:
    """从 templates/ 目录加载模板

    目录结构：
        templates/<bt_code>/
            template.html      HTML 模板
            style.css          样式（可选）
            meta.json          元数据（可选）
    图片通过相对路径引用，由 build 阶段嵌入为 data URI。
    """

    def __init__(self, templates_dir: Path = None):
        self.templates_dir = templates_dir or settings.TEMPLATES_DIR

    def load_all(self) -> dict[str, Template]:
        """加载目录下所有模板，返回 {bt_code: Template}"""
        templates = {}
        if not self.templates_dir.exists():
            return templates
        for child in self.templates_dir.iterdir():
            if not child.is_dir():
                continue
            template = self._load_from_dir(child)
            if template:
                templates[template.bt_code] = template
        return templates

    def load(self, bt_code: str) -> Template | None:
        """加载指定模板，不存在返回 None"""
        template_dir = self.templates_dir / bt_code
        if not template_dir.is_dir():
            return None
        return self._load_from_dir(template_dir)

    def _load_from_dir(self, template_dir: Path) -> Template | None:
        html_path = template_dir / "template.html"
        if not html_path.exists():
            return None

        html = html_path.read_text(encoding="utf-8")
        css = ""
        js = ""
        btid = 0
        bt_code = template_dir.name

        # 读取 meta.json（可选）
        meta_path = template_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                btid = meta.get("btid", 0)
                bt_code = meta.get("bt_code", bt_code)
            except (json.JSONDecodeError, OSError):
                pass

        css_path = template_dir / "style.css"
        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")

        js_path = template_dir / "script.js"
        if js_path.exists():
            js = js_path.read_text(encoding="utf-8")

        return Template(
            btid=btid,
            bt_code=bt_code,
            html_template=html,
            css_template=css,
            js_template=js,
        )