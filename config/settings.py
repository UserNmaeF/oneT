# -*- coding: utf-8 -*-
"""配置常量"""

import os
from pathlib import Path

# ─── 项目路径 ───
PROJECT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_DIR / "data" / "templates"
ASSETS_DIR = PROJECT_DIR / "assets"

# ─── 地区 ───
REGIONS = [
    {"id": 6, "code": "gb", "name": "英国"},
    {"id": 7, "code": "de", "name": "德国"},
    {"id": 8, "code": "ph", "name": "菲律宾"},
]

# ─── 账单类型 ───
BILL_TYPES = [
    {"id": "2",  "region_id": 6, "code": "gb-monzo",              "name": "Monzo Bank Statement",              "currency": "\u00a3", "category": "bank"},
    {"id": "3",  "region_id": 6, "code": "gb-kraken",             "name": "Kraken Statement",                  "currency": "\u00a3", "category": "crypto"},
    {"id": "5",  "region_id": 7, "code": "de-wise",               "name": "Wise EUR Statement (DE)",           "currency": "\u20ac", "category": "bank"},
    {"id": "6",  "region_id": 6, "code": "gb-wisegbpstatementuk", "name": "Wise GBP Statement (UK)",           "currency": "\u00a3", "category": "bank"},
    {"id": "8",  "region_id": 6, "code": "gb-octopusenergybill",  "name": "Octopus Energy Bill",               "currency": "\u00a3", "category": "utility"},
    {"id": "9",  "region_id": 8, "code": "ph-seabank",            "name": "MariBank Statement",                 "currency": "PHP", "category": "bank"},
    {"id": "14", "region_id": 7, "code": "de-monese",             "name": "Monese EUR Statement (DE)",         "currency": "\u20ac", "category": "bank"},
]

# ─── 区域代码映射 ───
REGION_CODE_MAP = {
    2: "hk", 3: "au", 4: "ca", 5: "sg", 6: "gb", 7: "de", 8: "ph",
}

# ─── 自动字段（不显示在表单中，由程序自动生成） ───
AUTO_FIELDS = {
    "transactions", "wise_transactions", "portfolio_table",
    "currency", "statement_period", "statement_month", "balance_date",
    # Octopus 账单：供电/用量/费率/账务区块全部自动生成
    "transactions_section", "direct_debit_note", "distributor",
    "tariff_name", "mpan", "meter_serial", "opening_reading",
    "closing_reading", "kwh_used", "billing_days", "unit_rate",
    "standing_charge", "new_balance", "prev_balance_num",
    "charges_num", "payments_num", "credits_num", "new_balance_num",
    # Monese 自动生成字段
    "monese_id",
    # Monzo 账期显示（DD/MM/YYYY）
    "period_display",
    # Monzo 总余额（Personal Account + Pots，闭合计算阶段自动生成）
    "total_balance",
    # Octopus 自动生成字段
    "supply_number", "supply_address", "reading_type",
    "payment_method", "eau_kwh", "eau_cost",
    # ph-seabank (MariBank) 自动生成显示字段
    "issue_date_display", "period_display", "contact_email",
    "interest_effective_date", "interest_rate_display",
    "interest_rate_high_display", "interest_tax_rate_display",
    "pdic_limit_display", "interest_details", "interest_gross",
    "interest_tax", "interest_net", "pdic_coverage", "bank_head_office",
    "interest_example_balance", "interest_example_gross",
    "interest_example_wt", "interest_example_net",
}

# ─── 表单字段显示优先级 ───
FIELD_PRIORITY = [
    "customer_name", "address_unit", "address_street", "address_district",
    "postal_code", "country", "account_number", "bill_number",
    "period_start", "period_end", "issue_date",
    "sort_code", "bic", "iban", "opening_balance", "closing_balance",
    "total_credits", "total_debits", "total_outgoings", "total_deposits", "balance_pots",
    "wise_currency", "wise_iban", "wise_bic", "wise_city", "wise_state",
    "wise_postcode", "wise_country", "wise_balance", "wise_ref", "wise_timezone",
    "wise_period_start", "wise_period_end", "wise_balance_date", "wise_generated_date",
    "kraken_public_id", "previous_balance",
]

# ─── API 支持的国家映射 ───
API_SUPPORTED_NAT = {"gb": "gb", "de": "de", "au": "au", "ca": "ca"}

# ─── 国家名称映射 ───
COUNTRY_MAP = {
    "gb": "United Kingdom",
    "de": "Germany",
    "ph": "Philippines",
    "hk": "Hong Kong",
    "au": "Australia",
    "ca": "Canada",
    "sg": "Singapore",
}