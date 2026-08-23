# -*- coding: utf-8 -*-
"""交易记录生成器 ─ 含 Octopus 电费账单模型

关键逻辑：
1. 交易笔数随机 3-8 笔（不再固定 5 笔）
2. 商户池扩大到 60+（降低跨样本重复率）
3. 交易金额合计 = 汇总额（从交易推导）
4. running balance 精确闭合到 closing_balance
5. Type 与 Description 逻辑配对

Octopus 账单模型：
  new_balance = previous_balance + total_charges - total_payments + total_credits
  - 冲销(credit)与付款均为入账，展示为 +£
  - 电费(VAT 5%)、日租费、冲销区间、交易日期全部在账期内闭合
"""

import random
import string
from datetime import datetime, timedelta

from core.defaults import (
    MARIBANK_INTEREST_RATE_ANNUAL,
    MARIBANK_INTEREST_RATE_HIGH,
    MARIBANK_HIGH_TIER_THRESHOLD,
    MARIBANK_INTEREST_TAX_RATE,
    MARIBANK_MIN_BUFFER,
    MARIBANK_ATM_OWNER_FEES,
    MARIBANK_ATM_FEE_DEFAULT,
    _MONTHS_SHORT,
)

# ─── 英国交易档案：(type, description, is_credit, min, max, round_to) ───
TXN_PROFILES_GB = [
    # === 卡支付 - 超市/食品 ===
    ("Card Payment", "TESCO STORES 4823", False, 10, 150, None),
    ("Card Payment", "SAINSBURYS ONLINE", False, 15, 200, None),
    ("Card Payment", "ASDA SUPERSTORE", False, 10, 180, None),
    ("Card Payment", "LIDL GB GMBH", False, 8, 120, None),
    ("Card Payment", "ALDI STORES UK", False, 8, 100, None),
    ("Card Payment", "WAITROSE FOOD", False, 15, 250, None),
    ("Card Payment", "CO-OP FOOD 2241", False, 5, 80, None),
    ("Card Payment", "ICELAND FOODS", False, 5, 90, None),
    ("Card Payment", "MARKS SPENCER FOOD", False, 10, 120, None),
    # === 卡支付 - 外卖/餐厅 ===
    ("Card Payment", "UBER TRIPS LONDON", False, 8, 50, None),
    ("Card Payment", "DELIVEROO ORDER", False, 10, 40, None),
    ("Card Payment", "JUST EAT TAKEAWAY", False, 10, 45, None),
    ("Card Payment", "UBER EATS DELIVERY", False, 8, 35, None),
    ("Card Payment", "PRET A MANGER", False, 5, 25, None),
    ("Card Payment", "STARBUCKS COFFEE", False, 3, 15, None),
    ("Card Payment", "COSTA COFFEE 2841", False, 3, 12, None),
    ("Card Payment", "MCDONALDS RESTAURANT", False, 3, 20, None),
    ("Card Payment", "NANDO CHICKEN", False, 10, 40, None),
    ("Card Payment", "GREGGS BAKERS", False, 3, 12, None),
    ("Card Payment", "WAGAMAMA RESTAURANT", False, 15, 60, None),
    ("Card Payment", "PHO CAFE LONDON", False, 10, 35, None),
    ("Card Payment", "DOUGH LIFE PIZZA", False, 12, 45, None),
    # === 卡支付 - 零售 ===
    ("Card Payment", "AMAZON UK MARKETPLACE", False, 5, 300, None),
    ("Card Payment", "AMAZON UK REFUND", True, 5, 100, None),  # 卡退款
    ("Card Payment", "ARGOS RETAIL 0394", False, 5, 200, None),
    ("Card Payment", "PRIMARK STORES", False, 5, 100, None),
    ("Card Payment", "H&M UK ONLINE", False, 10, 150, None),
    ("Card Payment", "NEXT RETAIL ONLINE", False, 10, 200, None),
    ("Card Payment", "JD SPORTS UK", False, 20, 250, None),
    ("Card Payment", "CURRYS PC WORLD", False, 10, 500, None),
    ("Card Payment", "HOME BARGAINS 119", False, 5, 80, None),
    ("Card Payment", "BM STORES RETAIL", False, 5, 70, None),
    ("Card Payment", "POUNDLAND RETAIL", False, 3, 50, None),
    ("Card Payment", "WILKO STORES", False, 5, 90, None),
    ("Card Payment", "BOOTS PHARMACY 2841", False, 3, 60, None),
    ("Card Payment", "SUPERDRUG STORES", False, 3, 50, None),
    ("Card Payment", "APPLE UK STORE", False, 20, 800, None),
    ("Card Payment", "GOOGLE PLAY STORE", False, 2, 50, None),
    # === 卡支付 - 交通/出行 ===
    ("Card Payment", "TFL TRAVEL CHARGE", False, 2, 15, None),
    ("Card Payment", "TFL CONGESTION CHARGE", False, 15, 15, None),
    ("Card Payment", "NATIONAL RAIL TICKET", False, 5, 200, None),
    ("Card Payment", "UBER TRIP LONDON", False, 5, 60, None),
    ("Card Payment", "BOLT RIDE UK", False, 5, 45, None),
    ("Card Payment", "SHELL PETROL STN", False, 20, 100, None),
    ("Card Payment", "BP PETROL STATION", False, 20, 90, None),
    ("Card Payment", "ESSO PETROL STATN", False, 20, 85, None),
    # === 卡支付 - 娱乐/订阅 ===
    ("Card Payment", "CINEWORLD CINEMA", False, 8, 30, None),
    ("Card Payment", "VUE CINEMA UK", False, 8, 25, None),
    ("Card Payment", "AUDIBLE UK SUBS", False, 8, 15, None),
    ("Card Payment", "ZOOM US PAYMENT", False, 10, 15, None),
    # === 卡支付 - 订阅服务（流媒体/订阅商通过卡扣，不走 Bacs Direct Debit）===
    ("Card Payment", "SPOTIFY UK PREMIUM", False, 9.99, 11.99, None),
    ("Card Payment", "NETFLIX.COM", False, 8.99, 17.99, None),
    ("Card Payment", "AMAZON PRIME UK", False, 8.99, 8.99, None),
    ("Card Payment", "NOW TV MEMBERSHIP", False, 9.99, 33.99, None),
    ("Card Payment", "DISNEY PLUS UK", False, 7.99, 10.99, None),
    ("Card Payment", "APPLE ICLOUD+ UK", False, 0.99, 6.99, None),
    ("Card Payment", "GOOGLE ONE UK", False, 1.59, 7.99, None),
    # === 直接借记 - 能源/水 ===
    ("Direct Debit", "BRITISH GAS ENERGY", False, 40, 180, None),
    ("Direct Debit", "OCTOPUS ENERGY DD", False, 35, 150, None),
    ("Direct Debit", "E.ON NEXT ENERGY", False, 40, 160, None),
    ("Direct Debit", "OVO ENERGY DD", False, 35, 140, None),
    ("Direct Debit", "THAMES WATER RATES", False, 20, 60, None),
    ("Direct Debit", "SEVERN TRENT WATER", False, 20, 55, None),
    # === 直接借记 - 通信/税 ===
    ("Direct Debit", "EE MOBILE BILL", False, 20, 80, None),
    ("Direct Debit", "VODAFONE UK BILL", False, 20, 75, None),
    ("Direct Debit", "THREE MOBILE BILL", False, 15, 65, None),
    ("Direct Debit", "O2 MOBILE BILL", False, 18, 70, None),
    ("Direct Debit", "VIRGIN MEDIA BB", False, 25, 65, None),
    ("Direct Debit", "SKY DIGITAL SUBS", False, 25, 70, None),
    ("Direct Debit", "TV LICENCE", False, 14.99, 15.54, None),  # 2026/27 彩电执照 £180/年，月付约 £15
    ("Direct Debit", "COUNCIL TAX DD", False, 100, 350, None),
    ("Direct Debit", "DVLA VEHICLE TAX", False, 15, 30, None),
    # === ATM 取款 ===
    ("ATM Withdrawal", "ATM Cash Machine", False, 20, 200, 20),
    ("ATM Withdrawal", "LINK ATM WITHDRAWAL", False, 20, 200, 20),
    ("ATM Withdrawal", "ATM TSB BANK", False, 20, 200, 20),
    ("ATM Withdrawal", "ATM BARCLAYS BANK", False, 20, 200, 20),
    # === 转账收入（Bacs/银行转账类，非 Faster Payment）===
    # HMRC 个人退税走 BACS repayment；工资/利息/他人转账多为普通银行转账轨道
    ("Bank Transfer", "EMPLOYER SALARY", True, 1500, 4500, None),
    ("Bank Transfer", "BANK TRANSFER", True, 50, 800, None),
    ("Bank Transfer", "HMRC TAX REFUND", True, 50, 500, None),
    ("Bank Transfer", "INTEREST PAYMENT", True, 1, 50, None),
    ("Cash Deposit", "PAYPOINT CASH DEPOSIT", True, 5, 300, None),  # Monzo无网点，PayPoint现金存款单笔上限£300
    # === 定期转账 ===
    ("Standing Order", "RENT PAYMENT", False, 800, 2500, None),
    ("Standing Order", "SAVINGS TRANSFER", False, 100, 500, None),
    ("Standing Order", "MORTGAGE PAYMENT", False, 500, 2000, None),
    ("Standing Order", "CHARITY DONATION OXFAM", False, 5, 50, None),
    ("Standing Order", "CHARITY DONATION NSPCC", False, 5, 30, None),
    ("Standing Order", "GYM MEMBERSHIP PURE", False, 20, 60, None),
    ("Standing Order", "GYM MEMBERSHIP VIRGIN", False, 15, 45, None),
    ("Standing Order", "CHILD MAINTENANCE", False, 100, 500, None),
    # === 快速支付转出 ===
    ("Faster Payment Out", "PAYPAL TRANSFER", False, 10, 200, None),
    ("Faster Payment Out", "VENMO TRANSFER UK", False, 10, 150, None),
    ("Faster Payment Out", "FRIEND TRANSFER", False, 10, 300, None),
]

# 欧元区（SEPA）交易档案：(type, description, is_credit, min, max, round_to)
# 用于 de-wise（Wise EUR，德国客户）对账单，避免英国场景词库混入 EUR 账单。
TXN_PROFILES_EUR = [
    # === 转账收入（SEPA）===
    ("SEPA Credit Transfer In", "SEPA EINGANG", True, 100, 2000, None),
    ("SEPA Credit Transfer In", "GEHALT BAYER AG", True, 2000, 5000, None),
    ("SEPA Credit Transfer In", "GEHALT SIEMENS AG", True, 2000, 5000, None),
    ("SEPA Credit Transfer In", "UEBERWEISUNG FRIEND", True, 50, 800, None),
    ("SEPA Credit Transfer In", "RENTENVERSICHERUNG", True, 800, 3000, None),
    # === 转账支出（SEPA）===
    ("SEPA Credit Transfer Out", "MIETE WOHNUNG", False, 500, 2000, None),
    ("SEPA Credit Transfer Out", "UEBERWEISUNG", False, 50, 800, None),
    ("SEPA Credit Transfer Out", "SPARBUCH SPAREN", False, 100, 500, None),
    # === SEPA 直接借记 ===
    ("SEPA Direct Debit", "AOK KRANKENKASSE", False, 150, 400, None),
    ("SEPA Direct Debit", "TK TECHNIKER", False, 100, 350, None),
    ("SEPA Direct Debit", "GEZ BEITRAG", False, 18, 20, None),
    ("SEPA Direct Debit", "STADTWERKE STROM", False, 40, 150, None),
    ("SEPA Direct Debit", "STADTWERKE GAS", False, 30, 120, None),
    ("SEPA Direct Debit", "WASSERWERKE GMBH", False, 20, 80, None),
    ("SEPA Direct Debit", "VODAFONE DE", False, 20, 60, None),
    ("SEPA Direct Debit", "TELEKOM DE", False, 20, 60, None),
    ("SEPA Direct Debit", "1UND1 INTERNET", False, 20, 60, None),
    ("SEPA Direct Debit", "HUK COBURG VERSICHERUNG", False, 50, 200, None),
    ("SEPA Direct Debit", "ADAC MITGLIEDSCHAFT", False, 40, 100, None),
    # === 卡支付 - 超市 ===
    ("Card Payment", "REWE MARKT", False, 15, 150, None),
    ("Card Payment", "ALDI SUED", False, 10, 120, None),
    ("Card Payment", "EDEKA", False, 10, 130, None),
    ("Card Payment", "LIDL DE", False, 8, 100, None),
    ("Card Payment", "PENNY DE", False, 5, 70, None),
    ("Card Payment", "NETTO DE", False, 5, 60, None),
    ("Card Payment", "DM DROGERIE", False, 5, 60, None),
    ("Card Payment", "ROSSMANN", False, 5, 70, None),
    ("Card Payment", "REWE LEBENSMITTEL", False, 15, 150, None),
    # === 卡支付 - 餐饮/咖啡 ===
    ("Card Payment", "STARBUCKS DE", False, 3, 15, None),
    ("Card Payment", "MC DONALDS DE", False, 3, 15, None),
    ("Card Payment", "BURGER KING DE", False, 3, 15, None),
    ("Card Payment", "SUBWAY DE", False, 5, 15, None),
    ("Card Payment", "BAECKEREI KIEFER", False, 2, 12, None),
    ("Card Payment", "BETTY BAR", False, 5, 25, None),
    # === 卡支付 - 零售/在线 ===
    ("Card Payment", "AMAZON EU SARL", False, 5, 200, None),
    ("Card Payment", "ZALANDO DE", False, 20, 150, None),
    ("Card Payment", "OTTO DE", False, 20, 200, None),
    ("Card Payment", "MEDIA MARKT", False, 20, 300, None),
    ("Card Payment", "SATURN DE", False, 20, 250, None),
    ("Card Payment", "H&M DE", False, 10, 100, None),
    ("Card Payment", "IKEA DE", False, 20, 400, None),
    ("Card Payment", "DECATHLON DE", False, 10, 150, None),
    # === 卡支付 - 交通 ===
    ("Card Payment", "DEUTSCHE BAHN", False, 10, 120, None),
    ("Card Payment", "BVG TICKET", False, 3, 60, None),
    ("Card Payment", "DB FERNVERKEHR", False, 20, 150, None),
    ("Card Payment", "TANKSTELLE ARAL", False, 30, 80, None),
    ("Card Payment", "SHELL DE TANKSTELLE", False, 30, 80, None),
    # === 订阅 ===
    ("Direct Debit", "NETFLIX DE", False, 8, 17, None),
    ("Direct Debit", "SPOTIFY DE", False, 10, 12, None),
    ("Direct Debit", "DAZN DE", False, 20, 30, None),
    ("Direct Debit", "APPLE MEDIA SERVICES", False, 5, 15, None),
    # === 取款（ATM，取整 10 欧元）===
    ("ATM Withdrawal", "GELDAUTOMAT SPARKASSE", False, 20, 200, 10),
    ("ATM Withdrawal", "GELDAUTOMAT COMDIRECT", False, 20, 200, 10),
    ("ATM Withdrawal", "GELDAUTOMAT DEUTSCHE BANK", False, 20, 200, 10),
    ("ATM Withdrawal", "GELDAUTOMAT VOLKSBANK", False, 20, 200, 10),
]

# 菲律宾商户名
# 菲律宾交易档案：(type, description, is_credit, min, max)
TXN_PROFILES_PH = [
    # 卡支付
    ("Card Payment", "SM SUPERMARKET", False, 100, 3000, None),
    ("Card Payment", "7-ELEVEN PH", False, 50, 500, None),
    ("Card Payment", "LAZADA PH", False, 200, 5000, None),
    ("Card Payment", "SHOPEE PH", False, 100, 3000, None),
    ("Card Payment", "JOLLIBEE FOOD", False, 100, 500, None),
    ("Card Payment", "MCDONALDS PH", False, 50, 300, None),
    ("Card Payment", "GLOBE TELECOM", False, 500, 2000, None),
    ("Card Payment", "CEBU PACIFIC", False, 1000, 5000, None),
    ("Card Payment", "WATSONS PH", False, 100, 500, None),
    # 账单支付
    ("Bills Payment", "MERALCO ELECTRIC", False, 500, 3000, None),
    ("Bills Payment", "MAYNILAD WATER", False, 200, 1000, None),
    ("Bills Payment", "PLDT INTERNET", False, 1000, 2500, None),
    ("Bills Payment", "GLOBE POSTPAID", False, 500, 1500, None),
    # ATM（取整 ₱100 倍数 + ₱15 fee）
    ("ATM Withdrawal", "ATM BPI", False, 1000, 10000, 100),
    ("ATM Withdrawal", "ATM BDO", False, 1000, 10000, 100),
    ("ATM Withdrawal", "ATM Metrobank", False, 1000, 10000, 100),
    # 收入
    ("Salary", "EMPLOYER SALARY", True, 10000, 50000, None),
    ("Transfer In", "BANK TRANSFER", True, 500, 10000, None),
    ("Cash Deposit", "PAYPARTNER CASH IN", True, 500, 5000, None),
    ("Refund", "LAZADA REFUND", True, 50, 500, None),
]

# Monese 商户模板：(merchant_name, detail_template, is_purchase, min_amt, max_amt, round_to)
# is_purchase=True → 支出(-)，is_purchase=False → 收入(+)
# min_amt/max_amt → 真实金额范围（按商户类型设定，避免 Spotify €254 这种异常）
# round_to → 取整单位（None=不取整, 10=取10倍数, 0.01=精确到分）
MONESE_MERCHANT_TEMPLATES = [
    # === 超市/食品（支出）===
    ("REWE Markt", "Kartenkauf {date_str}\nVielen Dank", True, 15, 120, None),
    ("ALDI", "Kartenzahlung\n{store_id}", True, 10, 100, None),
    ("Edeka Markt", "Lebensmittel\nKartenzahlung", True, 10, 130, None),
    ("Lidl GmbH", "Kartenzahlung\nVielen Dank", True, 8, 100, None),
    ("Penny Markt", "Lebensmittel\nKartenzahlung", True, 5, 70, None),
    ("Netto Marken", "Kartenzahlung\nVielen Dank", True, 5, 60, None),
    ("dm-drogerie", "Drogerie\nKartenzahlung", True, 5, 60, None),
    ("Rossmann", "Drogerie\nKartenzahlung", True, 5, 70, None),
    ("Bauhaus", "Baumarkt\nKartenzahlung", True, 15, 250, None),
    ("OBI Baumarkt", "Kartenzahlung\nFiliale {store_id}", True, 15, 200, None),
    # === 在线购物（支出）===
    ("Amazon EU", "AMZN Mktp DE\n{order_id}", True, 10, 300, None),
    ("Zalando DE", "Online Bestellung\nOrder {order_id}", True, 20, 200, None),
    ("OTTO DE", "Bestellung\nOrder {order_id}", True, 20, 250, None),
    ("IKEA DE", "Kartenzahlung\nFiliale {store_id}", True, 20, 400, None),
    ("MediaMarkt", "Elektronik\nKartenzahlung", True, 20, 500, None),
    ("Saturn DE", "Elektronik\nKartenzahlung", True, 20, 450, None),
    ("Thalia DE", "Buecher\nOnline Bestellung", True, 10, 80, None),
    ("H&M DE", "Kleidung\nKartenzahlung", True, 10, 150, None),
    ("C&A DE", "Kartenzahlung\nFiliale {store_id}", True, 10, 120, None),
    ("Decathlon DE", "Sport\nKartenzahlung", True, 15, 180, None),
    # === 餐饮（支出）===
    ("McDonalds DE", "Kartenzahlung\nFiliale {store_id}", True, 5, 25, None),
    ("Starbucks DE", "Kaffee\nKartenzahlung", True, 3, 15, None),
    ("Subway DE", "Kartenzahlung\nVielen Dank", True, 5, 20, None),
    ("Burger King DE", "Kartenzahlung\nFiliale {store_id}", True, 5, 22, None),
    ("LEON Restaurant", "Kartenzahlung\nVielen Dank", True, 8, 35, None),
    # === 交通（支出）===
    ("DB Vertrieb", "Reiseauskunft\nFlexpreis\n{ticket_id}", True, 10, 120, None),
    ("Flixbus DE", "Reiseauskunft\nTicket {ticket_id}", True, 5, 60, None),
    ("BVG Berlin", "Fahrgeld\nKartenzahlung", True, 3, 30, None),
    ("MVV Muenchen", "Fahrgeld\nKartenzahlung", True, 3, 30, None),
    ("Aral AG", "Tankstelle\nKartenzahlung", True, 20, 80, None),
    ("Shell DE", "Tankstelle\nKartenzahlung", True, 20, 80, None),
    ("TOTAL Deutschland", "Tankstelle\nKartenzahlung", True, 20, 75, None),
    # === 订阅/直接借记（支出，金额按真实价格）===
    ("Vodafone DE", "Rechnung\nRechnungsnummer {invoice_id}", True, 20, 70, None),
    ("Telekom DE", "Rechnung\nRechnungsnummer {invoice_id}", True, 20, 65, None),
    ("O2 DE", "Rechnung\nRechnungsnummer {invoice_id}", True, 15, 55, None),
    ("Netflix Intl", "Abo\nKartenzahlung", True, 7.99, 17.99, None),
    ("Spotify AB", "Premium Abo\nKartenzahlung", True, 5.99, 21.99, None),
    ("Disney Plus", "Abo\nKartenzahlung", True, 5.99, 13.99, None),
    ("DAZN DE", "Sport Abo\nKartenzahlung", True, 9.99, 44.99, None),
    ("AOK Krankenkasse", "Beitrag\nSepa Lastschrift", True, 100, 400, None),
    ("TK Krankenkasse", "Beitrag\nSepa Lastschrift", True, 100, 380, None),
    ("GEZ Berlin", "Beitrag\nSepa Lastschrift", True, 55.08, 55.08, None),
    # === 其他支出 ===
    ("PAYBACK", "Punktebonus\nKartenzahlung", True, 5, 50, None),
    ("Apotheke am Markt", "Gesundheit\nKartenzahlung", True, 8, 80, None),
    ("Douglas DE", "Parfuemerie\nKartenzahlung", True, 15, 120, None),
    ("Tedi", "Sonderposten\nKartenzahlung", True, 3, 30, None),
    ("Ernstings family", "Kleidung\nKartenzahlung", True, 5, 50, None),
    # === 收入类（退款/返现/转账/工资）===
    ("PayPal EU", "Instant Transfer\nPP-{paypal_id}", False, 50, 500, None),
    ("CAG GmbH", "DE{iban_ref}\nPrivacy ReClaim", False, 20, 300, None),
    ("LOTTO24", "NL{lotto_ref}\nGewinn aus Gluecksspiel\n{lotto_id}", False, 10, 200, None),
    ("Amazon EU", "Erstattung\nOrder {order_id}", False, 10, 150, None),
    ("Edeka Markt", "Rueckerstattung\nKartenzahlung", False, 5, 50, None),
    ("Zalando DE", "Rueckerstattung\nOrder {order_id}", False, 15, 120, None),
    ("PayPal EU", "Rueckerstattung\nPP-{paypal_id}", False, 10, 200, None),
    ("Siemens AG", "Gehaltsabrechnung\n{date_str}", False, 2500, 4500, None),
    ("BASF SE", "Gehalt\n{date_str}", False, 2200, 4200, None),
    ("Allianz SE", "Auszahlung\nPolnr {invoice_id}", False, 100, 800, None),
]


def _gen_monese_merchant(txn_date=None):
    """随机选择一个 Monese 商户并生成随机订单号/发票号

    返回 (merchant, detail, is_purchase, min_amt, max_amt, round_to)
    """
    template = random.choice(MONESE_MERCHANT_TEMPLATES)
    merchant, detail_tpl, is_purchase = template[0], template[1], template[2]
    min_amt = template[3] if len(template) > 3 else 10
    max_amt = template[4] if len(template) > 4 else 350
    round_to = template[5] if len(template) > 5 else None
    detail = _format_merchant_detail(detail_tpl, txn_date)
    return merchant, detail, is_purchase, min_amt, max_amt, round_to


def _format_merchant_detail(detail_tpl, txn_date=None):
    """格式化商户详情模板（替换占位符变量）"""
    return detail_tpl.format(
        order_id="".join(random.choices(string.digits, k=8)),
        date_str=(txn_date or datetime.now()).strftime("%Y-%m"),
        store_id="".join(random.choices(string.digits, k=4)),
        ticket_id="".join(random.choices(string.digits, k=6)),
        invoice_id=f"2026/{random.randint(100, 999)}",
        paypal_id=f"{''.join(random.choices(string.digits, k=4))}-{''.join(random.choices(string.digits, k=4))}",
        iban_ref="".join(random.choices(string.digits, k=10)),
        lotto_ref="".join(random.choices(string.digits, k=10)),
        lotto_id=f"C{random.randint(100000, 999999)}",
    )


def _random_dates(period_start, period_end, count):
    try:
        p_start = datetime.strptime(period_start, "%Y-%m-%d")
        p_end = datetime.strptime(period_end, "%Y-%m-%d")
    except (ValueError, TypeError):
        p_start = datetime.now().replace(day=1)
        p_end = datetime.now()
    days = max(1, (p_end - p_start).days)
    dates = [p_start + timedelta(days=random.randint(0, days)) for _ in range(count)]
    dates.sort()
    return dates


def _fmt_date(dt, fmt="dd/mm/yyyy"):
    if fmt == "dd/mm/yyyy":
        return dt.strftime("%d/%m/%Y")
    elif fmt == "yyyy-mm-dd":
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%d/%m/%Y")


def _to_float(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _gen_amount(min_val, max_val, round_to=None):
    amount = random.uniform(min_val, max_val)
    if round_to:
        amount = round(round(amount / round_to) * round_to, 2)
    return round(amount, 2)


def _pick_profiles(profiles, num_credits, num_debits):
    """从档案池中选指定数量的收入和支出档案（不重复）"""
    credit_pool = [p for p in profiles if p[2]]
    debit_pool = [p for p in profiles if not p[2]]
    random.shuffle(credit_pool)
    random.shuffle(debit_pool)
    picked_credits = credit_pool[:num_credits]
    picked_debits = debit_pool[:num_debits]
    return picked_credits, picked_debits


# Monzo 描述拟真辅助池
# 银行转账显示真实人名 + Reference；工资显示雇主公司名（对齐公开真实样本风格）
_MONZO_PERSON_NAMES = [
    "A. Whitfield", "S. Dunbar", "J. Ashworth", "E. Kowalski", "M. Treacy",
    "R. Okafor", "H. Lindqvist", "T. Fairbanks", "C. Nowell", "P. Achebe",
    "L. Fontaine", "D. Marchetti", "K. Osei", "N. Blackwood", "V. Petrova",
]
_MONZO_REFERENCE_NOTES = [
    "Rent", "Invoice", "Holiday split", "Dinner", "Concert tickets",
    "Loan repayment", "Birthday gift", "Taxi share", "Deposit refund",
    "Furniture", "Wedding gift", "Utilities split",
]
_MONZO_EMPLOYERS = [
    "AVERHAM FARMS LTD", "BRIGHTSPARK MEDIA LTD", "CALDER VALE LOGISTICS",
    "DELTA RECRUITMENT LTD", "ELMHURST CLEANING SERVICES", "FOXHALL ENGINEERING",
    "GRANGE PARK HOSPITALITY", "HOLLOWBROOK CONSULTING",
]
_MONZO_UK_DESRIPTOR_CITIES = [
    "LONDON GBR", "MANCHESTER GBR", "BIRMINGHAM GBR", "LEEDS GBR",
    "GLASGOW GBR", "BRISTOL GBR", "SHEFFIELD GBR", "NOTTINGHAM GBR",
    "HIGH WYCOMBE GBR", "READING GBR", "CAMBRIDGE GBR", "OXFORD GBR",
]


def _monzo_desc(txn_type: str, merchant: str, is_credit: bool, values: dict | None) -> str:
    """按交易类型生成贴近真实 Monzo statement 的描述

    - Bank Transfer 收入 → 人名/公司名 "(Bank Transfer)" + Reference 行
    - Card Payment → 商户描述符追加 城市 GBR 后缀（如 STARBUCKS HIGH WYCOMBE GBR）
    - 其余类型保留 "{merchant} ({type})" 结构
    """
    if txn_type == "Bank Transfer" and is_credit:
        if merchant == "EMPLOYER SALARY":
            name = random.choice(_MONZO_EMPLOYERS)
            # 薪资参考随机化：标签/月份/序号组合，避免跨账户重复
            label = random.choice(["SALARY", "PAYROLL", "WAGES", "BACS SALARY"])
            # 用账期月份（values.period_start）而非当前月份，避免7月账单标8月工资
            ym = "2026-07"
            if values and values.get("period_start"):
                try:
                    ym = datetime.strptime(str(values["period_start"])[:10], "%Y-%m-%d").strftime("%Y-%m")
                except (ValueError, TypeError):
                    pass
            note = f"{label} {ym} {random.randint(1000, 9999)}"
            return f"{name} (Bank Transfer)<br>Reference: {note}"
        name = random.choice(_MONZO_PERSON_NAMES)
        note = random.choice(_MONZO_REFERENCE_NOTES)
        return f"Name: {name} (Bank Transfer)<br>Reference: {note}"
    if txn_type == "Card Payment":
        own_city = (values or {}).get("address_district", "")
        suffix = f"{str(own_city).upper()} GBR" if own_city and random.random() < 0.6 \
            else random.choice(_MONZO_UK_DESRIPTOR_CITIES)
        return f"{merchant} {suffix}"
    return f"{merchant} ({txn_type})"


def generate_monzo_transactions(currency, period_start, period_end,
                                opening_balance, total_credits, total_debits,
                                closing_balance=None, num_txns=None, values=None):
    """生成 Monzo 银行流水表格 HTML（4列，对齐公开真实样本格式）

    - 表头：Date | Description | (GBP) Amount | (GBP) Balance
    - 行内金额不带 £ 符号、含千位逗号；收入无 + 号、支出带 -
    - Direct Debit 不落在周末（顺延至周一）
    """
    if num_txns is None:
        num_txns = random.randint(3, 8)

    dates = _random_dates(period_start, period_end, num_txns)
    opening = _to_float(opening_balance)

    num_credits = max(1, round(num_txns * random.uniform(0.25, 0.45)))
    num_debits = num_txns - num_credits
    picked_c, picked_d = _pick_profiles(TXN_PROFILES_GB, num_credits, num_debits)

    txns = []
    ci, di = 0, 0
    for i in range(num_txns):
        if ci < num_credits and (di >= num_debits or random.random() > 0.5):
            p = picked_c[ci % len(picked_c)]
            amt = _gen_amount(p[3], p[4], p[5])
            txns.append((True, amt, p[0], p[1], dates[i]))
            ci += 1
        else:
            p = picked_d[di % len(picked_d)]
            amt = _gen_amount(p[3], p[4], p[5])
            txns.append((False, amt, p[0], p[1], dates[i]))
            di += 1

    # Bacs 规则：Direct Debit 不在周末扣款，顺延至下一个工作日（周一）
    adjusted = []
    for t in txns:
        is_credit, amount, txn_type, merchant, dt = t
        if txn_type == "Direct Debit" and dt.weekday() >= 5:
            dt = dt + timedelta(days=7 - dt.weekday())
        adjusted.append((is_credit, amount, txn_type, merchant, dt))
    # 日期可能因顺延乱序，重新排序保证余额链时间递增
    adjusted.sort(key=lambda t: t[4])
    txns = adjusted

    actual_credits = round(sum(t[1] for t in txns if t[0]), 2)
    actual_debits = round(sum(t[1] for t in txns if not t[0]), 2)

    if values is not None:
        values["total_credits"] = f"{actual_credits:,.2f}"
        values["total_debits"] = f"{actual_debits:,.2f}"
        values["total_deposits"] = f"+{actual_credits:,.2f}"
        values["total_outgoings"] = f"-{actual_debits:,.2f}"

    running = opening
    rows = []
    for is_credit, amount, txn_type, merchant, dt in txns:
        running = round(running + (amount if is_credit else -amount), 2)
        desc = _monzo_desc(txn_type, merchant, is_credit, values)
        amt_str = f"-{amount:,.2f}" if not is_credit else f"{amount:,.2f}"
        cls = "credit" if is_credit else "debit"
        rows.append(
            f'<tr><td>{_fmt_date(dt)}</td><td style="text-align:left">{desc}</td>'
            f'<td class="{cls}" style="text-align:right">{amt_str}</td>'
            f'<td style="text-align:right">{running:,.2f}</td></tr>'
        )
    header = ('<table class="bank-table" style="width:100%;border-collapse:collapse;'
              'font-size:11px;margin-top:8px;">'
              '<tr><th>Date</th><th style="text-align:left">Description</th>'
              '<th style="text-align:right">(GBP) Amount</th>'
              '<th style="text-align:right">(GBP) Balance</th></tr>')
    return header + "".join(rows) + "</table>"


# Wise 2026 年 7 月各类型 Transaction ID 数量级范围（基于公开真实 Wise statement 样本推算）
# 公开样本：2026-04 CARD-3634756479 / TRANSFER-2059519458；2025-09 CARD-2899448794
# 7 月应高于 4 月样本，区间按月均增长率推算。
_WISE_TXN_ID_RANGE_2026_07 = {
    "CARD": (3_650_000_000, 3_750_000_000),         # 7月 Card ~3.65B-3.75B（高于4月的3.63B）
    "TRANSFER": (2_070_000_000, 2_130_000_000),      # 7月 Transfer ~2.07B-2.13B（高于4月的2.06B）
    "DIRECT_DEBIT": (32_500_000, 33_500_000),         # 7月 Direct Debit ~32.5M-33.5M（高于4月的~32.3M）
}


def _txn_type_to_prefix(txn_type: str) -> str:
    """交易类型 → Wise Transaction ID 前缀"""
    if txn_type in ("Card Payment", "ATM Withdrawal"):
        return "CARD"
    elif txn_type in ("SEPA Direct Debit", "Direct Debit"):
        return "DIRECT_DEBIT"
    else:
        return "TRANSFER"


def _assign_wise_txn_ids(txns: list, period_start: str, period_end: str) -> list:
    """为交易按日期驱动分配 Transaction ID

    核心逻辑：ID 由交易日期在账期中的累计非线性偏移决定。
    每天的增量不是固定常量，而是由日期哈希驱动的随机波动
    （工作日交易量大、周末交易量小），避免出现精确线性公式。
    日期相同 → 哈希相同 → ID 基准相同 → 跨账户全局单调递增。
    """
    import hashlib
    from datetime import timedelta as _td

    # 计算账期天数
    try:
        p_start = datetime.strptime(period_start, "%Y-%m-%d")
        p_end = datetime.strptime(period_end, "%Y-%m-%d")
        total_days = max(1, (p_end - p_start).days)
    except (ValueError, TypeError):
        p_start = datetime.now().replace(day=1)
        p_end = datetime.now()
        total_days = 30

    n = len(txns)
    ids = [None] * n

    # 按类型分组
    by_prefix = {}
    for i, t in enumerate(txns):
        prefix = _txn_type_to_prefix(t[2])
        by_prefix.setdefault(prefix, []).append((i, t[4]))

    for prefix, items in by_prefix.items():
        lo, hi = _WISE_TXN_ID_RANGE_2026_07.get(prefix, (1_000_000_000, 2_000_000_000))
        span = hi - lo
        avg_daily = span / total_days

        # 预计算每天的累计偏移（确定性，同一日期跨账户一致）
        cumulative_table = {}  # day_offset → cumulative_offset

        def _cumulative_offset(day_offset):
            """计算从账期第0天到第day_offset天的累计 ID 偏移（非线性）"""
            if day_offset in cumulative_table:
                return cumulative_table[day_offset]
            cumulative = 0.0
            for d in range(day_offset):
                date = p_start + _td(days=d)
                # 日期哈希 → 确定性日交易量波动系数（0.65-1.35）
                day_key = f"{prefix}_{date.strftime('%Y%m%d')}"
                h = int(hashlib.sha256(day_key.encode()).hexdigest()[:8], 16)
                variation = 0.65 + (h % 7000) / 10000  # 0.65-1.35
                # 周末交易量降低
                if date.weekday() >= 5:
                    variation *= 0.6
                cumulative += avg_daily * variation
            cumulative_table[day_offset] = cumulative
            return cumulative

        # 按日期排序，同日内用确定性哈希散布 jitter
        items.sort(key=lambda x: x[1])
        prev_date = None
        same_day_offset = 0
        for idx, dt in items:
            day_offset = max(0, (dt - p_start).days)
            base_id = int(lo + _cumulative_offset(day_offset))
            # jitter 范围 = 平均日增量的 30%，保证不同日期不交叉 + 同日广泛散布
            jitter_max = max(int(avg_daily * 0.3), 1000)
            if dt != prev_date:
                same_day_offset = 0
                prev_date = dt
            else:
                same_day_offset += 1
            # 确定性哈希：merchant + amount + date → 广泛散布，不同账户同日不聚集
            merchant = txns[idx][3]
            amount = txns[idx][1]
            hash_input = f"{prefix}_{dt.strftime('%Y%m%d')}_{merchant}_{amount:.2f}_{same_day_offset}"
            jitter_hash = int(hashlib.sha256(hash_input.encode()).hexdigest()[:8], 16)
            # 哈希映射到 [0, jitter_max)，同日内按 hash 排序递增避免逆序
            jitter_raw = jitter_hash % jitter_max
            # 同日多笔交易：按哈希值排序后递增分配，确保账户内单调
            jitter = same_day_offset * (jitter_max // 10) + jitter_raw % (jitter_max // 10)
            id_val = base_id + jitter
            if id_val > hi:
                id_val = hi - random.randint(0, 500)
            ids[idx] = f"{prefix}-{id_val}"

    # 兜底
    for i in range(n):
        if ids[i] is None:
            ids[i] = f"TRANSFER-{random.randint(2_070_000_000, 2_130_000_000)}"
    return ids


# 转账具名对手方池（真实 statement 显示具体姓名/公司，而非泛化 "Bank transfer"）
_WISE_COUNTERPARTS_IN = [
    "STEFAN BAUER", "LEA HOFFMANN", "JONAS REICHERT", "PETRA SOMMER",
    "THOMAS LINDNER", "SABINE WALLNER", "MICHAEL BRANDL", "KARIN OSTNER",
    "ANDREAS VOGEL", "JULIANE SEIDL",
]
_WISE_COUNTERPARTS_OUT = [
    "TOBIAS FRANK", "JENNIFER KEIL", "MARCO SILBER", "NADJA HERZOG",
    "FLORIAN ADLER", "CHRISTIAN ROTHER", "MELANIE STURM", "DANIEL HOFMEISTER",
]
# 转账参考用途（真实 incoming 常带 reference）
_WISE_TRANSFER_REFS = [
    "MIETE", "URLAUB", "RUECKZAHLUNG", "GESCHENK", "WOHNUNG KAUTION",
    "REPARATUR", "TEILEZAHLUNG", "SHOPPING", "TANKEN", "LEBENSMITTEL",
]
# 泛化转账商户名 → 生成时替换为具名对手方
_GENERIC_TRANSFER_MERCHANTS = {
    "Bank transfer", "SEPA EINGANG", "UEBERWEISUNG", "UEBERWEISUNG FRIEND",
    "MIETE WOHNUNG",
    "SPARBUCH SPAREN", "EMPLOYER SALARY", "BANK TRANSFER", "FRIEND TRANSFER",
    "PAYPAL TRANSFER", "VENMO TRANSFER UK",
}


# 卡商户 descriptor 城市池：用大城市而非持有人所在城市
# （审核驱动：TFL CONGESTION CHARGE + Armagh 这类"伦敦交通+北爱小城"组合不协调；
#   真实卡网络 descriptor 的城市是商户门店所在地，与持有人住址无关）
_CARD_DESCRIPTOR_CITIES = ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"]


def _card_descriptor(merchant: str) -> str:
    """把词典化卡商户转成更接近卡网络原始 descriptor 的形式（加城市/门店号噪声）

    城市取自 _CARD_DESCRIPTOR_CITIES（商户门店所在地），
    不使用持有人所在城市，避免 TFL 等城市服务商与小城市错配。
    """
    r = random.random()
    desc_city = random.choice(_CARD_DESCRIPTOR_CITIES)
    if not desc_city:
        return merchant
    if r < 0.40:
        return f"{merchant} {desc_city}"
    if r < 0.70:
        return f"{merchant} {random.randint(100, 4999)} {desc_city}"
    return merchant


def _wise_txn_lines(txn_type: str, merchant: str, amount: float,
                    currency: str, txn_id: str, holder: str = "",
                    ref: str = "") -> tuple:
    """把交易类型转成 Wise 原生两行描述：(主描述, 元数据行)

    对齐真实 Wise statement 结构：
      - 主描述：Card transaction of ... issued by ... / Sent money to ... / Received money from ...
      - 元数据行：日期由渲染层拼接；卡交易含 卡尾号+持卡人姓名（真实样本持续出现）；
        转账含 Ref: 用途；末尾 Transaction: CARD-/TRANSFER-/DIRECT_DEBIT-... ID。
      分隔符统一 ASCII ", "（PDF 文本提取稳定）。
    """
    if txn_type == "Card Payment":
        title = f"Card transaction of {currency}{amount:.2f} issued by {merchant}"
        last4 = "".join(random.choices(string.digits, k=4))
        parts = [f"Card ending in {last4}"]
        if holder:
            parts.append(holder)
        parts.append(f"Transaction: {txn_id}")
        meta = ", ".join(parts)
    elif txn_type == "ATM Withdrawal":
        title = f"Cash withdrawal of {currency}{amount:.2f} at {merchant}"
        last4 = "".join(random.choices(string.digits, k=4))
        parts = [f"Card ending in {last4}"]
        if holder:
            parts.append(holder)
        parts.append(f"Transaction: {txn_id}")
        meta = ", ".join(parts)
    elif txn_type in ("SEPA Credit Transfer In", "Faster Payment In"):
        # 真实 Wise：主描述带 with reference，详情行 Transaction 后跟完整 Reference
        title = f"Received money from {merchant} with reference {ref}"
        meta = f"Transaction: {txn_id}, Reference: {ref}"
    elif txn_type in ("SEPA Credit Transfer Out", "Faster Payment Out"):
        title = f"Sent money to {merchant} with reference {ref}"
        meta = f"Transaction: {txn_id}, Reference: {ref}"
    elif txn_type == "Standing Order":
        title = f"Standing order to {merchant} with reference {ref}"
        meta = f"Transaction: {txn_id}, Reference: {ref}"
    elif txn_type in ("SEPA Direct Debit", "Direct Debit"):
        # 真实 Wise：直接借记显示 Paid to + Mandat/客户参考号
        title = f"Paid to {merchant}"
        mandate = "".join(random.choices(string.digits, k=10))
        meta = f"Transaction: {txn_id}, Reference: {mandate}"
    else:
        title = f"{txn_type} - {merchant}"
        meta = f"Transaction: {txn_id}"
    return title, meta


def _is_weekend(dt) -> bool:
    """是否周六/周日"""
    return dt.weekday() >= 5


def _prev_weekday(dt):
    """回退到最近一个工作日（周五）"""
    while dt.weekday() >= 5:
        dt = dt - timedelta(days=1)
    return dt


def _last_banking_day(p_end):
    """账期月末最后一个银行工作日（养老金等固定入账日）"""
    d = p_end
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def generate_wise_transactions(currency, period_start, period_end,
                                opening_balance, closing_balance=None, num_txns=None, values=None):
    """生成 Wise 交易行 HTML（4 列：描述/汇入/汇出/余额）

    对齐真实 Wise statement 结构：
      - 表头 4 列，日期放在描述下方第二行
      - 汇出金额显示为负数
      - 非卡类交易（转账/直接借记）不落在周末（SEPA 结算规则）
      - RENTENVERSICHERUNG 养老金固定在月末最后一个银行工作日入账
      - 同月内不重复同一商户档案
    """
    if num_txns is None:
        num_txns = random.randint(3, 6)

    # 选择交易档案
    profiles = TXN_PROFILES_EUR if currency == "€" else TXN_PROFILES_GB

    try:
        p_start = datetime.strptime(period_start, "%Y-%m-%d")
        p_end = datetime.strptime(period_end, "%Y-%m-%d")
    except (ValueError, TypeError):
        p_start = datetime.now().replace(day=1)
        p_end = datetime.now()
    pension_day = _last_banking_day(p_end)

    dates = _random_dates(period_start, period_end, num_txns)
    opening = _to_float(opening_balance)
    target = _to_float(closing_balance) if closing_balance else opening
    values = values or {}
    holder = str(values.get("customer_name", "") or "")
    city = str(values.get("wise_city", "") or "")

    txns = []
    used_profiles = []
    for i in range(num_txns - 1):
        # 同月内不重复同一商户档案（避免 AOK 月内两笔这类异常）
        available = [p for p in profiles if p not in used_profiles] or profiles
        profile = random.choice(available)
        used_profiles.append(profile)
        is_credit = profile[2]
        merchant = profile[1]
        desc = profile[0]
        amount = _gen_amount(profile[3], profile[4], profile[5])
        dt = dates[i]
        # 泛化转账户名 → 具名对手方（真实 statement 显示姓名/公司而非 "Bank transfer"）
        is_transfer_type = desc in ("SEPA Credit Transfer In", "SEPA Credit Transfer Out",
                                    "Faster Payment In", "Faster Payment Out", "Standing Order")
        if is_transfer_type and merchant in _GENERIC_TRANSFER_MERCHANTS:
            pool = _WISE_COUNTERPARTS_IN if is_credit else _WISE_COUNTERPARTS_OUT
            merchant = random.choice(pool)
        # 卡商户加原始 descriptor 噪声（门店城市/门店号），避免词典化干净名称
        if desc in ("Card Payment", "ATM Withdrawal"):
            merchant = _card_descriptor(merchant)
        # 非卡类交易避开周末（SEPA 工作日结算）
        if desc not in ("Card Payment", "ATM Withdrawal") and _is_weekend(dt):
            dt = _prev_weekday(dt)
        # 养老金固定在月末最后一个银行工作日
        if "RENTENVERSICHERUNG" in merchant.upper():
            dt = pension_day
            amount = round(random.uniform(1200, 2200), 2)
            is_credit = True
            desc = "SEPA Credit Transfer In"
        txns.append([is_credit, amount, desc, merchant, dt])

    # 按日期排序后重算 running（日期调整可能改变顺序）
    txns.sort(key=lambda t: t[4])
    running = opening
    for t in txns:
        is_credit, amount = t[0], t[1]
        # Wise 不允许透支：debit 不能超过当前可用余额
        if not is_credit and amount > running:
            amount = round(running * random.uniform(0.3, 0.8), 2)
            if amount < 1:
                is_credit = True
                amount = _gen_amount(50, 500, None)
                t[2] = "SEPA Credit Transfer In"
                t[3] = random.choice(_WISE_COUNTERPARTS_IN)
        t[1] = amount
        running = round(running + (amount if is_credit else -amount), 2)

    last_diff = round(target - running, 2)
    in_type = "SEPA Credit Transfer In" if currency == "€" else "Faster Payment In"
    out_type = "SEPA Credit Transfer Out" if currency == "€" else "Faster Payment Out"
    # 闭合行日期：不早于已有最大交易日的随机银行工作日（避免 5/5 固定月末同日收尾）
    max_dt = max((t[4] for t in txns), default=pension_day)
    candidates = []
    d = max_dt
    while d <= p_end:
        if not _is_weekend(d):
            candidates.append(d)
        d = d + timedelta(days=1)
    closing_dt = random.choice(candidates) if candidates else _prev_weekday(max_dt)
    close_pool = _WISE_COUNTERPARTS_IN if last_diff >= 0 else _WISE_COUNTERPARTS_OUT
    close_name = random.choice(close_pool)
    if last_diff >= 0:
        txns.append([True, last_diff, in_type, close_name, closing_dt])
    else:
        send_amount = min(abs(last_diff), max(round(running - 0.01, 2), 0))
        txns.append([False, send_amount, out_type, close_name, closing_dt])

    actual_credits = round(sum(t[1] for t in txns if t[0]), 2)
    actual_debits = round(sum(t[1] for t in txns if not t[0]), 2)
    if values is not None:
        values["total_credits"] = f"{actual_credits:.2f}"
        values["total_debits"] = f"{actual_debits:.2f}"

    # 按日期驱动分配 Transaction ID（跨账户全局单调递增）
    txn_ids = _assign_wise_txn_ids(txns, period_start, period_end)

    running = opening
    rows = []
    for idx, (is_credit, amount, txn_type, merchant, dt) in enumerate(txns):
        running = round(running + (amount if is_credit else -amount), 2)
        is_transfer = txn_type in ("SEPA Credit Transfer In", "SEPA Credit Transfer Out",
                                   "Faster Payment In", "Faster Payment Out", "Standing Order")
        # 养老金是固定法定支付，不带随意用途 reference
        if "RENTENVERSICHERUNG" in merchant.upper():
            ref = ""
        else:
            ref = random.choice(_WISE_TRANSFER_REFS) if is_transfer else ""
        title, meta = _wise_txn_lines(txn_type, merchant, amount, currency,
                                      txn_ids[idx], holder=holder, ref=ref)
        # 日期并入描述第二行（对齐真实 Wise 4 列结构），分隔符统一 ASCII
        meta = f"{_fmt_date(dt)}, {meta}"
        if is_credit:
            rows.append(
                f'<div class="txn-row">'
                f'<div class="td-desc"><div class="txn-title">{title}</div>'
                f'<div class="txn-meta">{meta}</div></div>'
                f'<div class="td-in">{currency}{amount:.2f}</div>'
                f'<div class="td-out"></div>'
                f'<div class="td-bal">{currency}{running:.2f}</div></div>'
            )
        else:
            rows.append(
                f'<div class="txn-row">'
                f'<div class="td-desc"><div class="txn-title">{title}</div>'
                f'<div class="txn-meta">{meta}</div></div>'
                f'<div class="td-in"></div>'
                f'<div class="td-out">-{currency}{amount:.2f}</div>'
                f'<div class="td-bal">{currency}{running:.2f}</div></div>'
            )
    # 真实 Wise statement 显示顺序为最新交易在前（倒序）；
    # running balance 按时间正序累计后再反转输出顺序，余额列数值不变。
    rows.reverse()
    return "".join(rows)


def generate_monese_transactions(currency, period_start, period_end,
                                  opening_balance, num_txns=None, values=None):
    """生成 Monese 交易行 HTML（卡消费风格，英文标签）

    指纹④方案B：不再预设总额/闭合转账，交易自然生成后反推汇总额。
    指纹⑤：同日交易只首笔显示 Processed date，其余留空；同日组末尾才显示分割线（对齐真实样本）。
    """
    if num_txns is None:
        # 7-10 笔：保证跨页时第 2 页有交易延续（6 笔会导致第 2 页只剩 Closing balance）
        num_txns = random.randint(7, 10)

    dates = _random_dates(period_start, period_end, num_txns)
    opening = _to_float(opening_balance)
    running = opening

    txns = []
    for i in range(num_txns):
        merchant, detail, is_purchase, min_amt, max_amt, round_to = _gen_monese_merchant(dates[i])
        is_credit = not is_purchase
        # 如果余额不足 €50，强制生成一笔入账（修复：必须调 _format_merchant_detail）
        if running < 50 and not is_credit:
            credit_tpls = [t for t in MONESE_MERCHANT_TEMPLATES if not t[2]]
            if credit_tpls:
                t = random.choice(credit_tpls)
                merchant, detail = t[0], _format_merchant_detail(t[1], dates[i])
                is_credit = True
                min_amt, max_amt, round_to = t[3], t[4], t[5]
        # 保证月末账单至少含一笔入账
        if i == num_txns - 1 and not any(t[0] for t in txns) and not is_credit:
            credit_tpls = [t for t in MONESE_MERCHANT_TEMPLATES if not t[2]]
            if credit_tpls:
                t = random.choice(credit_tpls)
                merchant, detail = t[0], _format_merchant_detail(t[1], dates[i])
                is_credit = True
                min_amt, max_amt, round_to = t[3], t[4], t[5]
        # 用商户自己的金额范围生成（Spotify €5.99-€21.99 而非 €10-350）
        amount = _gen_amount(min_amt, max_amt, round_to)
        running = round(running + (amount if is_credit else -amount), 2)
        txns.append((is_credit, amount, merchant, detail, dates[i]))

    actual_credits = round(sum(t[1] for t in txns if t[0]), 2)
    actual_debits = round(sum(t[1] for t in txns if not t[0]), 2)
    if values is not None:
        values["opening_balance"] = f"{opening:,.2f}"
        values["total_credits"] = f"{actual_credits:,.2f}"
        values["total_debits"] = f"{actual_debits:,.2f}"
        values["closing_balance"] = f"{running:,.2f}"

    running = opening
    rows = []
    prev_pay_date_str = ""
    for i, (is_credit, amount, merchant, detail, dt) in enumerate(txns):
        running = round(running + (amount if is_credit else -amount), 2)
        sign = "+" if is_credit else "-"
        pay_date_str = dt.strftime("%d/%m/%Y")
        # 指纹⑤：Processed date 与 Payment made 有时不同（对齐真实样本）
        # 卡支付通常延后 1-2 天处理；SEPA/直接借记/工资可能同日处理
        # 同日交易只首笔显示 Processed date，其余留空
        if pay_date_str != prev_pay_date_str:
            if random.random() < 0.7:
                # 70% 概率：处理日延后 1-2 天
                processed_dt = dt + timedelta(days=random.randint(1, 2))
                while processed_dt.weekday() >= 5:
                    processed_dt += timedelta(days=1)
                processed_date = processed_dt.strftime("%d/%m/%Y")
            else:
                # 30% 概率：同日处理
                processed_date = pay_date_str
        else:
            processed_date = ""  # 同日后续交易留空
        prev_pay_date_str = pay_date_str
        
        # 判断是否为该日期的最后一笔交易
        is_day_last = (i == len(txns) - 1) or (txns[i+1][4].strftime("%d/%m/%Y") != pay_date_str)
        row_cls = "day-last" if is_day_last else ""

        # detail 换行格式化
        detail_html = detail.replace("\n", "<br>")

        rows.append(
            f'<tr class="{row_cls}">'
            f'<td class="date-col">{processed_date}</td>'
            f'<td class="pdate-col">{pay_date_str}</td>'
            f'<td class="desc-col"><div class="txn-desc-name">{merchant}</div>'
            f'<div class="txn-desc-detail">{detail_html}</div></td>'
            f'<td class="amt-col r">{sign}{currency}{amount:,.2f}</td>'
            f'<td class="bal-col r">{currency}{running:,.2f}</td>'
            f'</tr>'
        )
    return "".join(rows)


def _ph_date_str(dt) -> str:
    """datetime.date → '01 APR 2026'（MariBank 菲律宾账单日期格式，带年份）"""
    return f"{dt.day:02d} {_MONTHS_SHORT[dt.month - 1].upper()} {dt.year}"


def _ph_date_short(dt) -> str:
    """datetime.date → '01 APR'（行级日期不带年份：账期已限定年，对齐参考模板）"""
    return f"{dt.day:02d} {_MONTHS_SHORT[dt.month - 1].upper()}"


def _ph_float(v):
    """安全转浮点数"""
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def generate_seabank_transactions(currency, period_start, period_end,
                                  opening_balance, total_credits, total_debits,
                                  num_txns=None, values=None):
    """生成 MariBank 交易行，并按每日余额计提利息与预扣税。

    对齐真实 2026 MariBank 公开样本：
    - 交易明细表 4 列（DATE / TRANSACTION / OUTGOING / INCOMING），无 running balance
    - 利息净额作为一笔 INTEREST 入账出现在交易流中
    - 利息独立展示在 SAVINGS - INTEREST & TAX DETAILS 区块（逐日列表）
    - 日期格式：DD MMM YYYY
    - 分层利率：3.25%（≤1M）/ 3.75%（>1M）
    """
    if num_txns is None:
        num_txns = random.randint(3, 8)

    dates = _random_dates(period_start, period_end, num_txns)
    opening = _ph_float(opening_balance)
    credit_profiles = [profile for profile in TXN_PROFILES_PH if profile[2]]
    debit_profiles = [profile for profile in TXN_PROFILES_PH if not profile[2]]
    random.shuffle(credit_profiles)
    random.shuffle(debit_profiles)

    num_credits = max(1, round(num_txns * random.uniform(0.25, 0.45)))
    num_debits = num_txns - num_credits
    txns = []
    running = opening
    credit_index = debit_index = 0

    for index in range(num_txns):
        use_credit = credit_index < num_credits and (
            debit_index >= num_debits or random.random() > 0.5
        )
        if use_credit:
            profile = credit_profiles[credit_index % len(credit_profiles)]
            amount = _gen_amount(profile[3], profile[4], profile[5])
            credit_index += 1
            is_credit = True
        else:
            profile = debit_profiles[debit_index % len(debit_profiles)]
            available = running - MARIBANK_MIN_BUFFER
            max_amount = min(profile[4], available)
            if profile[5] is not None:
                max_amount = min(profile[4], (available // profile[5]) * profile[5])

            # 消费不得突破最低缓冲；无法支付时改用一笔入账以保持余额非负。
            if max_amount < profile[3]:
                if credit_index >= len(credit_profiles):
                    continue
                profile = credit_profiles[credit_index % len(credit_profiles)]
                amount = _gen_amount(profile[3], profile[4], profile[5])
                credit_index += 1
                is_credit = True
            else:
                amount = _gen_amount(profile[3], max_amount, profile[5])
                debit_index += 1
                is_credit = False

        txns.append((is_credit, amount, profile[0], profile[1], dates[index]))
        running = round(running + (amount if is_credit else -amount), 2)

    sorted_txns = sorted(txns, key=lambda txn: txn[4])

    # 为每笔 ATM Withdrawal 添加手续费（MariBank 规则：ATM owner 收费时只适用 owner fee，
    # 否则适用 MariBank 自身 ₱15；owner 费率来自官方公开页面）
    atm_fee_txns = []
    for txn in sorted_txns:
        is_credit, amount, txn_type, merchant, dt = txn
        if txn_type == "ATM Withdrawal" and not is_credit:
            # 提取 ATM 银行名用于 fee 描述与 owner fee 查表
            bank_name = merchant.replace("ATM ", "").strip()
            fee_amount = MARIBANK_ATM_OWNER_FEES.get(bank_name.upper(), MARIBANK_ATM_FEE_DEFAULT)
            fee_desc = f"{bank_name} ATM Fee"
            atm_fee_txns.append((False, fee_amount, "ATM Fee", fee_desc, dt))
    sorted_txns.extend(atm_fee_txns)
    sorted_txns.sort(key=lambda txn: txn[4])

    period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
    period_end_date = datetime.strptime(period_end, "%Y-%m-%d").date()
    days = [
        period_start_date + timedelta(days=offset)
        for offset in range((period_end_date - period_start_date).days + 1)
    ]
    transactions_by_day = {}
    for txn in sorted_txns:
        transactions_by_day.setdefault(txn[4].date(), []).append(txn)

    # MariBank 规则:利息按前一日余额每日午夜入账,扣 20% withholding tax。
    # 利息独立展示在 SAVINGS - INTEREST & TAX DETAILS 区块(逐日列表)。
    # 关键:前日已入账的净利息必须计入次日计息基数(真实规则:
    #   prev_day_balance + net_interest → next_day_balance)。
    interest_rows = []
    gross_total = 0.0
    tax_total = 0.0
    net_total = 0.0
    daily_net_by_day = {}
    # day_balance:每日计息基数(前一日结束后的真实余额,含已入账利息)
    day_balance = {}
    running_balance = opening
    for day in days:
        # 当日计息基数 = 当日开始前余额(= 前日普通交易 + 前日利息 累计)
        base = max(0, running_balance)
        day_balance[day] = base
        # 当日利息基于 base 计算(午夜入账)
        if base <= 0:
            daily_gross = 0.0
            daily_tax = 0.0
            daily_net = 0.0
        elif base <= MARIBANK_HIGH_TIER_THRESHOLD:
            daily_gross = round(base * MARIBANK_INTEREST_RATE_ANNUAL / 365, 2)
            daily_tax = round(daily_gross * MARIBANK_INTEREST_TAX_RATE, 2)
            daily_net = round(daily_gross - daily_tax, 2)
        else:
            # 分层利率：≤1M 按 3.25%，>1M 部分按 3.75%
            tier1 = MARIBANK_HIGH_TIER_THRESHOLD * MARIBANK_INTEREST_RATE_ANNUAL / 365
            tier2 = (base - MARIBANK_HIGH_TIER_THRESHOLD) * MARIBANK_INTEREST_RATE_HIGH / 365
            daily_gross = round(tier1 + tier2, 2)
            daily_tax = round(daily_gross * MARIBANK_INTEREST_TAX_RATE, 2)
            daily_net = round(daily_gross - daily_tax, 2)
        daily_net_by_day[day] = daily_net
        if daily_gross > 0:
            date_str = _ph_date_short(day)
            interest_rows.append(
                f'<tr><td>{date_str}</td><td class="text-right">{currency} {base:.2f}</td>'
                f'<td class="text-right">{currency} {daily_gross:.2f}</td>'
                f'<td class="text-right">{currency} {daily_tax:.2f}</td>'
                f'<td class="text-right">{currency} {daily_net:.2f}</td></tr>'
            )
            gross_total += daily_gross
            tax_total += daily_tax
            net_total += daily_net
        # 更新 running_balance:当日普通交易 + 当日净利息(利息午夜入账,影响次日余额)
        for is_credit, amount, _, _, _ in transactions_by_day.get(day, []):
            running_balance = round(
                running_balance + (amount if is_credit else -amount), 2
            )
        running_balance = round(running_balance + daily_net, 2)

    # 月度汇总
    net = round(net_total, 2)

    # 在交易流末尾添加一笔净利息入账记录（对齐真实样本：INTEREST / JUL 2026 · NET INTEREST）
    # 利息入账日在账期最后一日
    interest_flow_dt = datetime.combine(period_end_date, datetime.min.time())
    # 账期月份缩写
    period_month_abbr = _MONTHS_SHORT[period_end_date.month - 1].upper()
    period_year = period_end_date.year
    if net > 0:
        sorted_txns.append(
            (True, net, "INTEREST", f"{period_month_abbr} {period_year} · NET INTEREST", interest_flow_dt)
        )
        # 重新排序
        sorted_txns.sort(key=lambda txn: txn[4])

    # total_credits/debits 仅含普通交易 + 利息净额入账（不含预扣税收支）
    plain_credits = round(sum(t[1] for t in sorted_txns if t[0]), 2)
    plain_debits = round(sum(t[1] for t in sorted_txns if not t[0]), 2)
    if values is not None:
        values["total_credits"] = f"{plain_credits:.2f}"
        values["total_debits"] = f"{plain_debits:.2f}"
        values["interest_gross"] = f"{gross_total:.2f}"
        values["interest_tax"] = f"{tax_total:.2f}"
        values["interest_net"] = f"{net:.2f}"
        values["interest_details"] = "".join(interest_rows)

    # 交易明细行（4 列：DATE / TRANSACTION / OUTGOING / INCOMING，无 running balance）
    rows = []
    for is_credit, amount, txn_type, merchant, dt in sorted_txns:
        date_str = _ph_date_short(dt.date())
        if is_credit:
            rows.append(
                f'<tr><td>{date_str}</td><td>{txn_type}<span class="col-gray">{merchant}</span></td>'
                f'<td></td><td class="text-right">{currency} {amount:.2f}</td></tr>'
            )
        else:
            rows.append(
                f'<tr><td>{date_str}</td><td>{txn_type}<span class="col-gray">{merchant}</span></td>'
                f'<td class="text-right">{currency} {amount:.2f}</td><td></td></tr>'
            )
    return "".join(rows)


_QTY_RANGES = {
    "BTC": (0.05, 4.0, 6),
    "ETH": (0.5, 40.0, 6),
    "XRP": (200, 8000, 2),
    "SOL": (2, 150, 4),
    "ADA": (1000, 60000, 2),
    "DOT": (10, 2500, 2),
    "LTC": (0.5, 60, 4),
}

_TXN_DELTA = {
    "Buy": 1, "Deposit": 1, "Reward": 1, "Unstake": 1,
    "Sell": -1, "Withdrawal": -1, "Stake": -1,
    # Card Payment 从 Kraken Everyday balance(法币)支付,不影响 trading crypto 持仓
    "Card Payment": 0,
}

# 总量 delta：Stake/Unstake 是 Spot↔Staking 内部转移，总持仓不变
# （第六轮审核 P0：Stake 不得影响 total portfolio，否则 close_qty 被多减一次）
_TXN_DELTA_TOTAL = {
    "Buy": 1, "Deposit": 1, "Reward": 1,
    "Sell": -1, "Withdrawal": -1,
    "Stake": 0, "Unstake": 0,
    "Card Payment": 0,
}

_TXN_AMOUNT_LIMIT = {
    "Buy": 0.4, "Deposit": 0.5, "Reward": 0.03,
    "Sell": 0.5, "Withdrawal": 0.5, "Card Payment": 0.3, "Stake": 0.2, "Unstake": 0.15,
}


def _gen_kraken_assets(price_fetcher=None, period_start="", period_end=""):
    """生成 Kraken 资产列表（会话级真实价格，跨账户一致）

    价格直接取自会话缓存的市场价（无额外随机波动），
    同一进程内所有账单使用同一组市场价格。
    """
    from core.crypto_prices import CryptoPriceFetcher, _FALLBACK_RANGES
    if price_fetcher is None:
        price_fetcher = CryptoPriceFetcher()

    symbols = list(_FALLBACK_RANGES.keys())
    n_assets = random.randint(2, 4)
    chosen = random.sample(symbols, n_assets)

    assets = []
    for symbol in chosen:
        daily_prices = price_fetcher.fetch_daily_prices(symbol, period_start, period_end)
        open_price = price_fetcher.get_open_price(symbol, daily_prices)
        close_price = price_fetcher.get_close_price(symbol, daily_prices)

        # 不再叠加 ±0.3% 随机波动 —— 直接使用市场价
        open_price = round(open_price, 2)
        close_price = round(close_price, 2)

        lo, hi, prec = _QTY_RANGES.get(symbol, (0.01, 100, 2))
        qty = round(random.uniform(lo, hi), prec)

        assets.append({
            "symbol": symbol,
            # 全部从 Spot 起始；Staking 余额只经由 Stake/Unstake 交易产生
            # （第五轮审核 P1：Stake 后资产不得凭空消失，须体现为 Earn/Staking 余额）
            "wallet": "Spot",
            "open_qty": qty, "open_price": open_price,
            "close_qty": qty, "close_price": close_price,
            "daily_prices": daily_prices,
            "prec": prec,
        })
    return assets


def _gen_kraken_ref() -> str:
    """生成 Kraken 风格交易参考号：XXXXX-XXXXX-XXXXX

    大写字母+数字，排除易混淆字符 I/O/0/1
    """
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    parts = []
    for _ in range(3):
        part = "".join(random.choices(chars, k=5))
        parts.append(part)
    return "-".join(parts)


def generate_kraken_data(currency, period_start, period_end, num_txns=None):
    """生成 Kraken portfolio + transactions（持仓守恒 + 会话级真实价格）

    交易类型多样化：Buy/Sell/Stake/Deposit/Withdrawal/Reward/Card Payment
    - Stake 手续费 = 0（Kraken 规则：staking/unstaking 无交易费）
    - Buy/Sell 手续费 = 交易额 × 费率（0.15%-0.40%）
    - Reference 使用 Kraken 风格 ID (XXXXX-XXXXX-XXXXX)
    - Activity 时间含 UTC 时分秒
    - 交易条数 0-10，资产组合 2-4 种
    """
    from core.crypto_prices import CryptoPriceFetcher
    price_fetcher = CryptoPriceFetcher()

    # 先 fetch 所有资产价格（触发会话级缓存，后续账单复用）
    assets = _gen_kraken_assets(price_fetcher, period_start, period_end)

    # 交易条数：0-10（偶尔 0 交易）
    if num_txns is None:
        num_txns = random.choices(
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            weights=[5, 8, 10, 13, 13, 12, 10, 9, 7, 6, 5]
        )[0]

    dates = _random_dates(period_start, period_end, max(1, num_txns))
    # 交易类型权重
    txn_types = random.choices(
        ["Buy", "Sell", "Stake", "Deposit", "Withdrawal", "Reward", "Card Payment"],
        weights=[25, 22, 10, 8, 8, 7, 5],
        k=num_txns
    )

    qty_deltas = {}
    staked_qty = {}   # 各币种当前 Staking 余额（Spot ↔ Staking 迁移）
    current_qty = {a["symbol"]: a["open_qty"] for a in assets}
    txn_rows = []
    for idx, dt in enumerate(dates):
        if idx >= len(txn_types):
            break
        txn_type = txn_types[idx]

        # 随机选资产（Reward 可发生在已 stake 的资产上）
        if txn_type == "Reward":
            # reward 只对持有 >0 的资产
            eligible = [a for a in assets if current_qty.get(a["symbol"], 0) > 0.0001]
            if not eligible:
                continue
            asset = random.choice(eligible)
        else:
            asset = random.choice(assets)
        symbol = asset["symbol"]
        prec = asset.get("prec", 2)
        current = current_qty.get(symbol, 0)

        # 交易金额
        limit_ratio = _TXN_AMOUNT_LIMIT.get(txn_type, 0.3)
        is_positive = _TXN_DELTA.get(txn_type, 0) >= 0

        if txn_type == "Reward":
            amount = round(current * random.uniform(0.005, 0.03), prec)
            if amount < 10 ** (-prec):
                amount = 0
        elif txn_type == "Stake":
            max_amt = max(0.0001, current * limit_ratio)
            lo, hi, _ = _QTY_RANGES.get(symbol, (0.001, 1.0, 2))
            amount = round(random.uniform(lo, min(hi, max_amt)), prec)
        elif txn_type == "Card Payment":
            lo, hi, _ = _QTY_RANGES.get(symbol, (0.001, 1.0, 2))
            max_amt = current * limit_ratio if current > 0.0001 else hi
            amount = round(random.uniform(lo, max(lo, min(hi, max_amt))), prec)
        elif txn_type == "Unstake":
            # Unstake 上限 = 当前 Staking 余额；无仓可解则跳过
            staked = staked_qty.get(symbol, 0)
            if staked <= 10 ** (-prec):
                continue
            lo, hi, _ = _QTY_RANGES.get(symbol, (0.001, 1.0, 2))
            amount = round(random.uniform(lo, min(hi, staked)), prec)
        elif txn_type == "Deposit":
            lo, hi, _ = _QTY_RANGES.get(symbol, (0.001, 1.0, 2))
            amount = round(random.uniform(lo, hi), prec)
        else:  # Buy / Sell / Withdrawal
            if is_positive:
                lo, hi, _ = _QTY_RANGES.get(symbol, (0.001, 1.0, 2))
                max_amt = hi * limit_ratio
                amount = round(random.uniform(lo, min(hi, max_amt)), prec)
            else:
                if current <= 0.0001:
                    continue
                max_amt = current * limit_ratio
                lo, _, _ = _QTY_RANGES.get(symbol, (0.001, 1.0, 2))
                amount = round(random.uniform(lo, max_amt), prec)

        if amount <= 0:
            continue

        # 真实当日价格（不叠加额外波动）
        date_str = dt.strftime("%Y-%m-%d")
        daily_prices = asset.get("daily_prices", [])
        base_price = price_fetcher.get_price_for_date(symbol, date_str, daily_prices)
        price = round(base_price, 2)

        # 手续费（Kraken 规则）
        value = round(amount * price, 2)
        if txn_type == "Stake":
            fee = 0.0  # Kraken: staking/unstaking 无交易费
        elif txn_type in ("Reward", "Deposit", "Unstake"):
            fee = 0.0
        elif txn_type == "Card Payment":
            fee = 0.0  # Kraken Card: 无 transaction fee(官方 FAQ 2026-07-17)
        elif txn_type == "Withdrawal":
            fee = round(random.uniform(0.0, 2.5), 2)
        else:  # Buy/Sell
            fee_rate = random.uniform(0.0016, 0.0040)  # 0.16%-0.40%
            fee = round(value * fee_rate, 2)
            fee = max(fee, 0.01)

        delta = amount * _TXN_DELTA.get(txn_type, 0)           # Spot 运行余额 delta
        delta_total = amount * _TXN_DELTA_TOTAL.get(txn_type, 0) # 总持仓 delta（Stake/Unstake=0）
        qty_deltas[symbol] = qty_deltas.get(symbol, 0) + delta_total
        current_qty[symbol] = current_qty.get(symbol, 0) + delta
        # Stake/Unstake = Spot ↔ Staking 余额迁移（总量不变，仅换钱包）
        if txn_type == "Stake":
            staked_qty[symbol] = staked_qty.get(symbol, 0) + amount
        elif txn_type == "Unstake":
            staked_qty[symbol] = max(0, staked_qty.get(symbol, 0) - amount)

        # 时间戳：随机时分秒
        t = dt + timedelta(hours=random.randint(8, 20), minutes=random.randint(0, 59), seconds=random.randint(0, 59))

        # Counter party
        if txn_type in ("Buy", "Sell", "Stake", "Unstake", "Reward"):
            counter = "Kraken"
        elif txn_type == "Card Payment":
            counter = "Kraken Card"
        else:
            counter = ""

        # Wallet 字段：Stake/Unstake 发生在 Staking 钱包；
        # Card Payment 消费 Kraken Card 关联的 Funding(Everyday) 法币余额，
        # 与 Spot 交易持仓无关（第五轮审核 P2：不得标记 Wallet=Spot）
        if txn_type in ("Stake", "Unstake"):
            row_wallet = "Staking"
        elif txn_type == "Card Payment":
            row_wallet = "Funding"
        else:
            row_wallet = "Spot"

        ref = _gen_kraken_ref()
        txn_rows.append(
            f'<tr>'
            f'<td class="align-left">{t.strftime("%Y-%m-%d %H:%M:%S")}</td>'
            f'<td class="align-left">{txn_type}</td>'
            f'<td class="align-left">{symbol}</td>'
            f'<td class="align-left">{row_wallet}</td>'
            f'<td class="align-right">{amount}</td>'
            f'<td class="align-right">{currency}{price:.2f}</td>'
            f'<td class="align-right">{currency}{fee:.2f}</td>'
            f'<td class="align-right">{currency}{value:.2f}</td>'
            f'<td class="align-left">{counter}</td>'
            f'<td class="align-left">{ref}</td>'
            f'</tr>'
        )

    # 更新 close_qty（总持仓）与 Spot/Staking 拆分
    for asset in assets:
        symbol = asset["symbol"]
        delta = qty_deltas.get(symbol, 0)
        prec = asset.get("prec", 2)
        asset["close_qty"] = round(asset["open_qty"] + delta, prec)
        net_staked = round(staked_qty.get(symbol, 0), prec)
        asset["close_spot"] = round(asset["close_qty"] - net_staked, prec)
        asset["close_staked"] = net_staked

    # 构建 portfolio rows：Spot 行 + （如有）Staking 余额行
    # 第五轮审核 P1：Stake 迁移到 Staking 的资产必须在组合中可见
    portfolio_rows = []
    for a in assets:
        prec = a.get("prec", 2)

        def _row(wallet_label, open_qty_, close_qty_):
            open_value = round(open_qty_ * a["open_price"], 2)
            close_value = round(close_qty_ * a["close_price"], 2)
            net_change = round(close_value - open_value, 2)
            return (
                f'<tr>'
                f'<td class="align-left">{a["symbol"]}</td>'
                f'<td class="align-left">{wallet_label}</td>'
                f'<td class="align-right">{round(open_qty_, prec)}</td>'
                f'<td class="align-right">{currency}{a["open_price"]:.2f}</td>'
                f'<td class="align-right">{currency}{open_value:.2f}</td>'
                f'<td class="align-right">{round(close_qty_, prec)}</td>'
                f'<td class="align-right">{currency}{a["close_price"]:.2f}</td>'
                f'<td class="align-right">{currency}{close_value:.2f}</td>'
                f'<td class="align-right">{currency}{net_change:.2f}</td>'
                f'</tr>'
            )

        portfolio_rows.append(_row("Spot", a["open_qty"], a["close_spot"]))
        if a["close_staked"] > 0:
            portfolio_rows.append(_row("Staking", 0, a["close_staked"]))

    return "".join(portfolio_rows), "".join(txn_rows)


def _distribute_amount(total, n):
    """将 total 分成 n 份（带随机方差），合计精确等于 total"""
    if n <= 0:
        return []
    if n == 1:
        return [round(total, 2)]
    portions = [random.uniform(0.3, 1.7) for _ in range(n)]
    s = sum(portions)
    amounts = [round(total * p / s, 2) for p in portions]
    diff = round(total - sum(amounts), 2)
    amounts[-1] = round(amounts[-1] + diff, 2)
    return amounts


# ──────────────────────────────────────────────
# Octopus 电费账单数据生成
# ──────────────────────────────────────────────

def _fmt_cash(n: float, currency: str = "£") -> str:
    """格式化金额显示：负值 → "-£1,234.56"，正值 → "£1,234.56" """
    sign = "-" if n < 0 else ""
    return f"{sign}{currency}{abs(n):,.2f}"


def generate_octopus_data(values: dict):
    """生成 Octopus 电费账单的供电详情、用量、费用与账务数据

    写入 values 的字段：
      - 供电: distributor, mpan, tariff_name, meter_serial
      - 用量: opening_reading, closing_reading, kwh_used, billing_days
      - 费率: unit_rate, standing_charge
      - 显示: previous_balance, new_balance, period_start, period_end, issue_date (UK 格式)
      - 数值: prev_balance_num, charges_num, payments_num, credits_num, new_balance_num
      - 区块: transactions_section, direct_debit_note

    数据模型（Octopus 正余额=credit 口径，官方帮助中心确认）：
      new_balance = previous_balance - total_charges + total_payments + total_credits
    """
    from core.defaults import _uk_date, _uk_date_range, _MONTHS_FULL, _MONTHS_SHORT
    from core.dno_map import (get_dno_info, get_dno_info_by_postcode,
                              _FALLBACK_DNO, generate_unique_mpan, CITY_DNO_MAP)

    currency = values.get("currency", "£")

    # ── 日期解析（ISO）与格式化 ──
    try:
        p_start = datetime.strptime(str(values.get("period_start", "")), "%Y-%m-%d")
        p_end = datetime.strptime(str(values.get("period_end", "")), "%Y-%m-%d")
    except (ValueError, TypeError):
        now = datetime.now()
        p_start = now.replace(day=1)
        p_end = (p_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    try:
        issue = datetime.strptime(str(values.get("issue_date", "")), "%Y-%m-%d")
    except (ValueError, TypeError):
        issue = datetime.now()

    days = (p_end - p_start).days + 1
    values["billing_days"] = str(days)

    # 日期显示格式（UK 格式，覆盖原始 ISO 值）
    values["period_start"] = _uk_date(p_start.strftime("%Y-%m-%d"))
    values["period_end"] = _uk_date(p_end.strftime("%Y-%m-%d"))
    values["issue_date"] = _uk_date(issue.strftime("%Y-%m-%d"))

    # ── 供电信息（DNO 与城市/邮编一致） ──
    city = str(values.get("address_district", ""))
    postal = str(values.get("postal_code", ""))
    if city.strip() and get_dno_info(city)["dno"] != _FALLBACK_DNO["dno"]:
        dno = get_dno_info(city)
    else:
        # 城市未知时用邮编前缀兜底
        dno = get_dno_info_by_postcode(postal)

    # Octopus 取值域收敛：仅使用 ENA 锚定的五个 DNO 组（LLD 10/11/13/20/23）。
    # Northern Ireland（MPRN 体系、无 Octopus）、非法邮编、其余区域一律改选。
    # 城市与邮编配对同步更新；街道为全英通用名可跨城使用。
    import re as _re
    _OCTOPUS_DNOS = {
        "UK Power Networks (East of England)",                       # LLD 10
        "National Grid Electricity Distribution (East Midlands)",    # LLD 11
        "SP Manweb",                                                 # LLD 13
        "SSE Southern Electric Power Distribution",                  # LLD 20
        "Northern Powergrid (Yorkshire)",                            # LLD 23
    }
    # 始终从允许的城市-邮编配对表重新选取（确保 postcode 真实且 DNO 在五组内），
    # 不依赖 API/LocalPool 的原始地址（可能含垃圾邮编或不匹配街道）
    if (dno.get("group") == "NIE"
            or dno.get("dno") not in _OCTOPUS_DNOS
            or not _re.match(r"^[A-Z]{1,2}[0-9]\d", postal.strip().upper())
            or not _re.match(r"^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$", postal.strip().upper())):
        from core.defaults import _CITY_POSTCODES_GB
        # 优先从验证过的城市簿取（有真实 street↔postcode 对）；
        # 30% 概率用未覆盖城市（只显示 city+postcode 无街道）
        from core.defaults import _GB_OCTOPUS_STREETS
        verified_cities = {k.lower() for k in _GB_OCTOPUS_STREETS}
        verified_pairs = [(c, pc) for c, pc in _CITY_POSTCODES_GB
                          if c.lower() in verified_cities]
        all_allowed = {k.lower() for k, v in CITY_DNO_MAP.items()
                       if v["dno"] in _OCTOPUS_DNOS}
        other_pairs = [(c, pc) for c, pc in _CITY_POSTCODES_GB
                       if c.lower() in all_allowed and c.lower() not in verified_cities]
        pairs = verified_pairs if (verified_pairs and random.random() < 0.7) else (other_pairs or verified_pairs)
        assert pairs, "octopus: no allowed city pair"
        new_city, new_pc = random.choice(pairs)
        dno = get_dno_info(new_city)
        values["address_district"] = new_city
        values["postal_code"] = new_pc
        city, postal = new_city, new_pc

    values["distributor"] = dno["dno"]

    # MPAN（素数权重 MOD11 合法校验位 + 会话内跨账户唯一 + S 格式 Supply Number）
    mpan_parts = generate_unique_mpan(dno["ll"])
    values["mpan"] = mpan_parts["mpan"]
    values["supply_number"] = mpan_parts["top"]
    # 供应地址：优先使用经验证的 (street, postcode) 对（postcodes.io + doogal.co.uk 核实）；
    # 未覆盖的城市只显示 city + postcode（不写街道，避免 postcode↔street mismatch）
    from core.defaults import _GB_OCTOPUS_STREETS
    if city in _GB_OCTOPUS_STREETS:
        _street, _pc, _mx = random.choice(_GB_OCTOPUS_STREETS[city])
        _house = random.randint(1, _mx)
        values["address_street"] = f"{_house} {_street}"
        values["address_unit"] = ""
        values["postal_code"] = _pc
        postal = _pc
        values["supply_address"] = f"{_house} {_street}, {city}, {_pc}"
    else:
        # 未覆盖城市：只显示 city + postcode（不写街道，消除 mismatch）
        values["address_street"] = ""
        values["address_unit"] = ""
        values["supply_address"] = f"{city}, {postal}"
    values["reading_type"] = "Actual"
    # 电表编号
    ms_prefix = f"{random.randint(10,99)}{random.choice('LKGTBCSP')}"
    ms_suffix = f"{random.randint(100,999)} {random.randint(100,999)}"
    values["meter_serial"] = f"{ms_prefix} {ms_suffix}"

    # ── 费率（p/kWh 与 p/天），按 Tariff 波动 ──
    tariff_names = [
        "Flexible Octopus", "Agile Octopus", "Tracker",
        "Cosy Octopus", "Octopus Go", "Intelligent Octopus"
    ]
    tariff_weights = [58, 12, 10, 8, 7, 5]
    tariff = random.choices(tariff_names, weights=tariff_weights)[0]
    values["tariff_name"] = tariff

    # 费率范围
    unit_rate = round(random.uniform(22.0, 34.0), 2)
    standing_rate = round(random.uniform(42.0, 58.0), 2)
    is_tou = tariff in ("Intelligent Octopus", "Octopus Go")
    night_rate = 0.0
    if tariff == "Tracker":
        unit_rate = round(random.uniform(18.0, 26.0), 2)
    elif tariff == "Agile Octopus":
        unit_rate = round(random.uniform(14.0, 28.0), 2)
    elif tariff == "Cosy Octopus":
        standing_rate = round(random.uniform(48.0, 62.0), 2)
    if is_tou:
        # TOU 费率：日间高价 + 夜间低价（23:30-05:30 约 5 小时）
        night_rate = round(random.uniform(5.0, 12.0), 2)

    if is_tou:
        values["unit_rate"] = f"{unit_rate:.2f}p day / {night_rate:.2f}p night (23:30-05:30)"
    else:
        values["unit_rate"] = f"{unit_rate:.2f}"
    values["standing_charge"] = f"{standing_rate:.2f}"

    # ── 电表读数与用量 ──
    opening = random.randint(5000, 99000)
    kwh = random.randint(120, 900)
    values["opening_reading"] = f"{opening:,}"
    values["closing_reading"] = f"{opening + kwh:,}"
    values["kwh_used"] = f"{kwh}"

    # TOU 用量分割（夜间约占 35-55%）
    if is_tou:
        night_kwh = int(kwh * random.uniform(0.35, 0.55))
        day_kwh = kwh - night_kwh
    else:
        day_kwh, night_kwh = kwh, 0

    # ── 费用计算 ──
    if is_tou:
        energy_charge = round((day_kwh * unit_rate + night_kwh * night_rate) / 100, 2)
    else:
        energy_charge = round(kwh * unit_rate / 100, 2)
    standing_total = round(days * standing_rate / 100, 2)
    subtotal = round(energy_charge + standing_total, 2)
    vat = round(subtotal * 0.05, 2)
    total_charges = round(subtotal + vat, 2)
    values["charges_num"] = f"{total_charges:.2f}"

    # 费用行 HTML（charges-table 样式）
    period_range = _uk_date_range(p_start.strftime("%Y-%m-%d"), p_end.strftime("%Y-%m-%d"))
    c_rows = []
    if is_tou:
        c_rows.append(
            f'<tr><td>Electricity used<br>({day_kwh} kWh @ {unit_rate:.2f}p + {night_kwh} kWh @ {night_rate:.2f}p)</td>'
            f'<td>{period_range}</td><td>{currency}{energy_charge:,.2f}</td></tr>'
        )
    else:
        c_rows.append(
            f'<tr><td>Electricity used<br>({kwh} kWh @ {unit_rate:.2f}p/kWh)</td>'
            f'<td>{period_range}</td><td>{currency}{energy_charge:,.2f}</td></tr>'
        )
    c_rows.append(
        f'<tr><td>Standing charge<br>({days} days @ {standing_rate:.2f}p/day)</td>'
        f'<td>{period_range}</td><td>{currency}{standing_total:,.2f}</td></tr>'
    )
    c_rows.append(
        f'<tr><td>VAT @ 5%</td><td></td><td>{currency}{vat:,.2f}</td></tr>'
    )
    c_rows.append(
        f'<tr class="total-row"><td><strong>Total electricity charges</strong></td>'
        f'<td></td><td><strong>{currency}{total_charges:,.2f}</strong></td></tr>'
    )
    charge_rows = "".join(c_rows)

    # ── 冲销（reversal credits） ──
    n_credits = random.choices([0, 1, 2, 3], weights=[35, 30, 25, 10])[0]
    credit_rows_list = []
    total_credits = 0.0
    for _ in range(n_credits):
        amt = round(random.uniform(60, 350), 2)
        total_credits += amt
        # 冲销对应扣费区间：在本期或上期内的连续区间
        w_start = p_start - timedelta(days=random.randint(0, 30))
        w_end = min(w_start + timedelta(days=random.randint(9, 16)), p_end)
        w_start = w_end - timedelta(days=random.randint(9, 16))
        if w_start < p_start - timedelta(days=31):
            w_start = p_start - timedelta(days=15)
        # 交易日期在周期末或接近周期末（≤ period_end）
        txn = p_end - timedelta(days=random.randint(0, 5))
        w_range = _uk_date_range(w_start.strftime("%Y-%m-%d"), w_end.strftime("%Y-%m-%d"))
        txn_str = _uk_date(txn.strftime("%Y-%m-%d"))
        credit_rows_list.append(
            f'<tr><td>Reversed electricity charge<br>({w_range})</td>'
            f'<td>{txn_str}</td><td>+ {currency}{amt:,.2f}</td></tr>'
        )
    values["credits_num"] = f"{total_credits:.2f}"

    # ── 付款（Direct Debit） ──
    has_dd = random.random() < 0.72
    payment_rows_list = []
    total_payments = 0.0
    dd_amount = 0.0
    dd_date_str = ""
    if has_dd:
        # 付款金额 ≈ 覆盖大部分费用
        dd_amount = round(total_charges * random.uniform(0.75, 1.05), 2)
        total_payments = dd_amount
        # 付款日期：账期初
        pay_date = p_start + timedelta(days=random.randint(0, 7))
        pay_date_str = _uk_date(pay_date.strftime("%Y-%m-%d"))
        payment_rows_list.append(
            f'<tr><td>Direct Debit payment</td>'
            f'<td>{pay_date_str}</td><td>+ {currency}{dd_amount:,.2f}</td></tr>'
        )
        # 下次 DD 扣款日：必须晚于账单签发日（避免“账单日之后才扣款”的时间倒置）
        dd_due = max(issue, p_end) + timedelta(days=random.randint(5, 12))
        dd_date_str = _uk_date(dd_due.strftime("%Y-%m-%d"))
    values["payments_num"] = f"{total_payments:.2f}"

    # ── 余额计算 ──
    try:
        prev = float(str(values.get("previous_balance", "0")).replace(",", "").replace("£", "").strip())
    except (ValueError, TypeError):
        prev = 0.0
    new_balance = round(prev - total_charges + total_payments + total_credits, 2)
    values["prev_balance_num"] = f"{prev:.2f}"
    values["new_balance_num"] = f"{new_balance:.2f}"

    # 显示格式（含符号与货币符号）
    values["previous_balance"] = _fmt_cash(prev, currency)
    values["new_balance"] = _fmt_cash(new_balance, currency)

    # ── 构造交易区块 HTML ──
    sections = []
    sections.append(f'<h2>1. We have debited you</h2>'
                    f'<table class="charges-table">{charge_rows}</table>')
    if n_credits > 0:
        sections.append(f'<h2>2. We have credited you</h2>'
                        f'<table class="credited-table">{"".join(credit_rows_list)}</table>')
    if len(payment_rows_list) > 0:
        sections.append(f'<h2>3. We have received payments</h2>'
                        f'<table class="credited-table">{"".join(payment_rows_list)}</table>')
    values["transactions_section"] = "".join(sections)

    # ── About Your Tariff / 年用量估算（对齐真实账单第 2 页字段） ──
    values["payment_method"] = "Direct Debit" if has_dd else "On receipt of bill"
    # EAU 是基于历史读数的年度估算，非当月用量简单年化；
    # 独立随机取值，避免 round(月用量 × 365 / 天数) 的机械公式指纹
    eau_kwh = random.randint(2500, 11000)
    eau_annual_net = eau_kwh * unit_rate / 100 + 365 * standing_rate / 100
    eau_cost = round(eau_annual_net * 1.05, 2)  # 含 5% VAT
    values["eau_kwh"] = f"{eau_kwh:,}"
    values["eau_cost"] = f"{currency}{eau_cost:,.2f}"

    # ── Direct Debit 备注 ──
    if has_dd:
        values["direct_debit_note"] = (
            f"Your Direct Debit of {currency}{dd_amount:,.2f} will leave your "
            f"account on {dd_date_str}. If you'd like to make a payment sooner, "
            f"there are 5 ways you can pay, as detailed in this bill."
        )
    else:
        values["direct_debit_note"] = (
            "As you have no Direct Debit in place, your balance is due for "
            "payment in 14 days. There are 5 ways you can pay, as detailed in this bill."
        )