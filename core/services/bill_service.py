# -*- coding: utf-8 -*-
"""账单生成服务"""

from core.models import Template, FormField, FormSpec
from core.placeholders import extract_placeholders, get_placeholder_label
from core.defaults import get_field_defaults, _ph_date, _ph_period_display
from core.html_builder import generate_bill_html
from core.transaction_generator import (
    generate_monzo_transactions, generate_wise_transactions,
    generate_monese_transactions, generate_seabank_transactions,
    generate_kraken_data, generate_octopus_data,
)
from config.settings import AUTO_FIELDS, FIELD_PRIORITY, BILL_TYPES

from core.template_loader import TemplateLoader
from renderers.base import Renderer


class BillService:
    """账单生成服务（核心编排）"""

    def __init__(self, template_loader: TemplateLoader = None, renderer: Renderer = None):
        self.template_loader = template_loader or TemplateLoader()
        self.renderer = renderer
        self._templates: dict[str, Template] = {}

    def load_templates(self) -> dict[str, Template]:
        """加载所有模板"""
        self._templates = self.template_loader.load_all()
        return self._templates

    def get_template(self, bt_code: str) -> Template | None:
        """获取指定模板"""
        if not self._templates:
            self.load_templates()
        return self._templates.get(bt_code)

    def get_form_spec(self, bt_code: str) -> FormSpec | None:
        """根据模板生成表单规格"""
        template = self.get_template(bt_code)
        if template is None:
            return None

        placeholders = extract_placeholders(template.html_template)
        defaults = get_field_defaults(bt_code)

        # 排序：优先级在前，其余按字母序
        sorted_phs = [p for p in FIELD_PRIORITY if p in placeholders and p not in AUTO_FIELDS]
        for p in sorted(placeholders):
            if p not in sorted_phs and p not in AUTO_FIELDS:
                sorted_phs.append(p)

        fields = [
            FormField(
                placeholder=ph,
                label=get_placeholder_label(ph),
                default_value=defaults.get(ph, ""),
            )
            for ph in sorted_phs
        ]

        return FormSpec(bt_code=bt_code, fields=fields)

    def get_field_defaults(self, bt_code: str) -> dict:
        """获取默认字段值"""
        return get_field_defaults(bt_code)

    def generate_html(self, bt_code: str, field_values: dict) -> str | None:
        """生成 HTML 账单

        合并策略：默认值（特别是 AUTO_FIELDS）作为底层数据，
        用户输入的 field_values 覆盖默认值。同时自动生成交易记录，
        并保证余额计算闭合（closing = opening + credits - debits）。
        """
        template = self.get_template(bt_code)
        if template is None:
            return None
        # 合并：默认值打底 + 用户输入覆盖
        defaults = get_field_defaults(bt_code)
        merged = {**defaults, **field_values}
        # 自动填充 currency（从 BILL_TYPES 配置获取）
        bill_type = next((bt for bt in BILL_TYPES if bt["code"] == bt_code), None)
        if bill_type:
            merged.setdefault("currency", bill_type["currency"])
        # 先生成交易记录（交易档案推导总额，写入 merged）
        self._generate_transactions(bt_code, merged)
        # 再计算余额闭合（用交易推导的总额）
        self._calculate_balances(bt_code, merged)
        # ph-seabank 特殊：重算显示格式字段（确保用户覆盖 period_start/period_end 后仍同步）
        if bt_code == "ph-seabank":
            self._recompute_ph_display_fields(merged)
        return generate_bill_html(template, merged)

    def _calculate_balances(self, bt_code: str, values: dict):
        """自动计算余额闭合关系

        银行账单逻辑：closing_balance = opening_balance + total_credits - total_debits
        Wise 逻辑：wise_balance = opening_balance + total_credits - total_debits
        Octopus 逻辑（credit 口径）：new_balance = prev - charges + payments + credits
        """
        def _to_float(v):
            try:
                return float(str(v).replace(",", "").replace(currency, "").strip())
            except (ValueError, TypeError):
                return 0.0

        currency = values.get("currency", "")

        # 银行类账单：closing = opening + credits - debits
        if bt_code in ("gb-monzo", "de-monese", "ph-seabank"):
            opening = _to_float(values.get("opening_balance", 0))
            credits = _to_float(values.get("total_credits", 0))
            debits = _to_float(values.get("total_debits", 0))
            closing = round(opening + credits - debits, 2)
            # Monese 不允许透支：如果 closing < 0，调整 debits 使 closing = 0.01
            if bt_code == "de-monese" and closing < 0:
                debits = round(opening + credits - 0.01, 2)
                values["total_debits"] = f"{debits:,.2f}"
                closing = 0.01
            if bt_code == "de-monese":
                values["opening_balance"] = f"{opening:,.2f}"
                values["total_credits"] = f"{credits:,.2f}"
                values["total_debits"] = f"{debits:,.2f}"
                values["closing_balance"] = f"{closing:,.2f}"
            else:
                values["closing_balance"] = f"{closing:.2f}"

        # Monzo 额外字段
        if bt_code == "gb-monzo":
            opening = _to_float(values.get("opening_balance", 0))
            credits = _to_float(values.get("total_credits", 0))
            debits = _to_float(values.get("total_debits", 0))
            # 真实样本格式：Total outgoings 带负号、Total deposits 带正号，均含千位逗号
            # 符号由模板渲染（-{{currency}}… / +{{currency}}…），此处存无符号千位逗号数值
            values["total_deposits"] = f"{credits:,.2f}"
            values["total_outgoings"] = f"{debits:,.2f}"
            values["total_credits"] = f"{credits:,.2f}"
            values["total_debits"] = f"{debits:,.2f}"
            # Total balance = Personal Account balance + Pots（千位逗号）
            closing = _to_float(values.get("closing_balance", 0))
            pots = _to_float(values.get("balance_pots", 0))
            values["total_balance"] = f"{closing + pots:,.2f}"
            values["closing_balance"] = f"{closing:,.2f}"
            values["balance_pots"] = f"{pots:,.2f}"

        # Wise：wise_balance = opening + credits - debits（不允许负余额）
        if bt_code in ("de-wise", "gb-wisegbpstatementuk"):
            opening = _to_float(values.get("opening_balance", 0))
            credits = _to_float(values.get("total_credits", 0))
            debits = _to_float(values.get("total_debits", 0))
            balance = round(opening + credits - debits, 2)
            # Wise 不允许主动透支：如果余额为负，减少支出使余额为最小正值
            if balance < 0:
                debits = round(opening + credits - 0.01, 2)
                values["total_debits"] = f"{debits:.2f}"
                balance = 0.01
            values["wise_balance"] = f"{balance:.2f}"

        # Octopus（credit 口径，官方确认正余额=credit）：prev - charges + payments + credits
        if bt_code == "gb-octopusenergybill":
            prev = _to_float(values.get("prev_balance_num", "0"))
            charges = _to_float(values.get("charges_num", "0"))
            payments = _to_float(values.get("payments_num", "0"))
            credits = _to_float(values.get("credits_num", "0"))
            nb = round(prev - charges + payments + credits, 2)
            values["new_balance_num"] = f"{nb:.2f}"
            # 如果显示字段尚未由 generate_octopus_data 写入，则重算（防御）
            if "new_balance" not in values:
                from core.transaction_generator import _fmt_cash
                values["new_balance"] = _fmt_cash(nb, currency)

    def _recompute_ph_display_fields(self, values: dict):
        """重算 ph-seabank 显示格式字段

        模板使用 period_display / issue_date_display（"01 MAR 2026 to 31 MAR 2026"、
        "01 APR 2026"）作为展示文本；用户可能覆盖 period_start/period_end/issue_date，
        这里确保显示字段始终与底层 ISO 日期一致。
        """
        period_start = values.get("period_start", "")
        period_end = values.get("period_end", "")
        if period_start and period_end:
            try:
                values["period_display"] = _ph_period_display(period_start, period_end)
            except Exception:
                pass
        # 签发日显示 = issue_date 本身（默认已是账期结束后首日）
        issue_date = values.get("issue_date", "")
        if issue_date:
            try:
                from datetime import datetime as _dt2
                _dt2.strptime(issue_date, "%Y-%m-%d")
                values["issue_date_display"] = _ph_date(issue_date)
            except Exception:
                pass

    def _generate_transactions(self, bt_code: str, values: dict):
        """根据账单类型生成交易记录 HTML

        交易档案推导实际总额，写入 values 字典。
        """
        currency = values.get("currency", "")
        period_start = values.get("period_start", "")
        period_end = values.get("period_end", "")
        opening = values.get("opening_balance", "0")
        closing = values.get("closing_balance", "0")
        credits = values.get("total_credits", "0")
        debits = values.get("total_debits", "0")

        if bt_code == "gb-monzo":
            if not values.get("transactions"):
                values["transactions"] = generate_monzo_transactions(
                    currency, period_start, period_end, opening, credits, debits,
                    closing, values=values)

        elif bt_code in ("de-wise", "gb-wisegbpstatementuk"):
            if not values.get("wise_transactions"):
                values["wise_transactions"] = generate_wise_transactions(
                    currency, period_start, period_end, opening, closing, values=values)

        elif bt_code == "de-monese":
            if not values.get("transactions"):
                # 指纹④方案B：交易自然生成，汇总额由交易反推
                values["transactions"] = generate_monese_transactions(
                    currency, period_start, period_end, opening, values=values)

        elif bt_code == "ph-seabank":
            if not values.get("transactions"):
                values["transactions"] = generate_seabank_transactions(
                    currency, period_start, period_end, opening, credits, debits, values=values)

        elif bt_code == "gb-kraken":
            # 统一生成 portfolio + transactions（持仓守恒）
            if not values.get("portfolio_table") or not values.get("transactions"):
                portfolio_html, txn_html = generate_kraken_data(currency, period_start, period_end)
                if not values.get("portfolio_table"):
                    values["portfolio_table"] = portfolio_html
                if not values.get("transactions"):
                    values["transactions"] = txn_html

        elif bt_code == "gb-octopusenergybill":
            # 生成供电详情、用量、费用与账务数据（金额闭合）
            generate_octopus_data(values)

    def render_to_pdf(self, html: str, output_path: str) -> None:
        """渲染为 PDF"""
        if self.renderer:
            self.renderer.render_pdf(html, output_path)

    def render_to_png(self, html: str, output_path: str) -> None:
        """渲染为 PNG 文件"""
        if self.renderer:
            self.renderer.render_png(html, output_path)

    def render_to_png_bytes(self, html: str) -> bytes:
        """渲染为 PNG 字节流（用于预览）"""
        if self.renderer:
            return self.renderer.render_png_bytes(html)
        return b""