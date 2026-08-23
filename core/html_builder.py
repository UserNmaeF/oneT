# -*- coding: utf-8 -*-
"""HTML 账单生成"""

import re

from core.models import Template


def generate_bill_html(template: Template, field_values: dict) -> str:
    """生成完整 HTML 账单文档"""
    html = template.html_template
    css = template.css_template

    for key, value in field_values.items():
        html = html.replace("{{" + key + "}}", str(value))
    html = re.sub(r'\{\{\w+\}\}', '', html)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #fff; display: flex; justify-content: center; padding: 0; }}
{css}
/* 打印/PDF 输出：去除屏幕预览用的卡片阴影，
   避免 Chromium 把 box-shadow 栅格化成大型灰度位图嵌入 PDF */
@media print {{
    .page {{ box-shadow: none !important; margin: 0 !important; }}
}}
</style>
</head>
<body>
{html}
</body>
</html>"""