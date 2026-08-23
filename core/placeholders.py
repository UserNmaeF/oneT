# -*- coding: utf-8 -*-
"""占位符提取与中文描述映射"""

import re

# ─── 占位符中文描述 ───
PLACEHOLDER_DESCRIPTIONS = {
    "customer_name": "客户姓名",
    "address_unit": "单元/门牌",
    "address_street": "街道地址",
    "address_state": "联邦州/省份",
    "address_district": "区域/城市",
    "postal_code": "邮编",
    "country": "国家",
    "bill_number": "账单编号",
    "account_number": "账号",
    "period_start": "起始日期",
    "period_end": "截止日期",
    "issue_date": "发出日期",
    "currency": "货币符号",
    "statement_period": "账单周期",
    "sort_code": "Sort Code",
    "bic": "BIC代码",
    "iban": "IBAN",
    "opening_balance": "期初余额",
    "closing_balance": "期末余额",
    "total_credits": "总收入",
    "total_debits": "总支出",
    "balance_pots": "Pots余额",
    "total_outgoings": "总支出",
    "total_deposits": "总存款",
    "wise_currency": "货币",
    "wise_iban": "IBAN",
    "wise_bic": "BIC",
    "wise_city": "城市",
    "wise_state": "州/省",
    "wise_postcode": "邮编",
    "wise_country": "国家",
    "wise_balance": "余额",
    "wise_ref": "参考号",
    "wise_timezone": "时区",
    "wise_period_start": "起始日期",
    "wise_period_end": "截止日期",
    "wise_balance_date": "余额日期",
    "wise_generated_date": "生成日期",
    "kraken_public_id": "Kraken Public ID",
    "previous_balance": "上期余额",
    "new_balance": "本期余额",
    "transactions_section": "账务明细",
    "direct_debit_note": "Direct Debit 备注",
    "distributor": "配电公司 (DNO)",
    "tariff_name": "费率方案",
    "mpan": "MPAN 编号",
    "supply_number": "Supply Number（S 格式）",
    "supply_address": "供电地址",
    "reading_type": "电表读数类型",
    "payment_method": "付款方式",
    "eau_kwh": "预估年用电量 kWh",
    "eau_cost": "预估年费用",
    "meter_serial": "电表编号",
    "opening_reading": "期初读数",
    "closing_reading": "期末读数",
    "kwh_used": "用量 (kWh)",
    "billing_days": "计费天数",
    "unit_rate": "电量单价 (p/kWh)",
    "standing_charge": "日租费 (p/天)",
}


def extract_placeholders(html_template: str) -> set[str]:
    """从 HTML 模板中提取所有 {{placeholder}} 占位符"""
    return set(re.findall(r'\{\{(\w+)\}\}', html_template))


def get_placeholder_label(placeholder: str) -> str:
    """获取占位符的中文描述"""
    return PLACEHOLDER_DESCRIPTIONS.get(placeholder, placeholder)