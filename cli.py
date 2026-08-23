#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oneT CLI - 命令行账单生成器
不依赖 tkinter，直接复用 core/ 和 renderers/ 模块
"""

import sys
import os
import re
import argparse
import random
import time
from datetime import datetime

# 确保项目根目录在 sys.path 中
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from config.settings import BILL_TYPES, REGIONS, REGION_CODE_MAP
from core.services.bill_service import BillService
from core.services.address_service import AddressService
from core.template_loader import TemplateLoader
from core.defaults import get_field_defaults
from renderers.playwright import PlaywrightRenderer

# 输出文件名前缀映射：bt_code → 文件名标识（去除暴露模板代号的前缀，对齐真实品牌）
_OUTPUT_NAME_MAP = {
    "ph-seabank": "maribank",
}


def _create_services():
    """创建服务依赖（复用 GUI 的初始化逻辑）"""
    template_loader = TemplateLoader()
    renderer = PlaywrightRenderer()
    address_service = AddressService()
    bill_service = BillService(template_loader=template_loader, renderer=renderer)
    bill_service.load_templates()
    return bill_service, address_service, renderer


def _fill_defaults(bill_service, address_service, bt_code, region_code):
    """一键填充（与 GUI 的 _fill_defaults 逻辑一致）

    1. 获取全部默认值
    2. 同时获取随机真实地址（API 优先，本地兜底）
    3. 合并地址到默认值
    """
    defaults = get_field_defaults(bt_code)
    # ph-seabank 的菲律宾地址(含 Barangay/城市/邮编配对)已在 defaults 内生成完毕,
    # 通用地址服务对菲律宾无 Barangay 层级且城市-邮编可能错配,故跳过覆盖。
    # gb-kraken 同理：API 地址存在城市-邮编错配（如 Salisbury + C0 4UW），
    # 使用 defaults 内的本地城市-邮编配对池。
    # gb-wisegbpstatementuk 同理：API 的 GB state/postcode 与城市不闭合
    # （Westminster+Surrey+RY71 等，RY/AY/TV 非真实 postcode area），
    # 使用 defaults 内的城市-郡-邮编三元绑定表。
    if bt_code not in ("ph-seabank", "gb-kraken", "gb-wisegbpstatementuk"):
        addr_values = address_service.get_address_as_dict(region_code)
        if addr_values:
            defaults.update(addr_values)
    return defaults


def cmd_gen(args):
    """生成账单"""
    bill_service, address_service, renderer = _create_services()

    # 确定要生成的类型列表
    if args.all:
        types = [bt["code"] for bt in BILL_TYPES]
    elif args.type:
        valid_codes = {bt["code"] for bt in BILL_TYPES}
        if args.type not in valid_codes:
            print(f"错误: 未知类型 '{args.type}'")
            print(f"可用类型: {', '.join(valid_codes)}")
            return 1
        types = [args.type]
    else:
        print("错误: 请指定 --type 或 --all")
        return 1

    # 输出目录
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    # 批量生成
    total = len(types) * args.count
    idx = 0
    errors = 0

    for bt_code in types:
        # 获取地区代码
        bt_info = next((bt for bt in BILL_TYPES if bt["code"] == bt_code), None)
        if not bt_info:
            continue
        region_code = REGION_CODE_MAP.get(bt_info["region_id"], "gb")

        for i in range(args.count):
            idx += 1
            # 文件名使用真实当前时间，与页面生成日期、PDF CreationDate 保持一致
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 随机短后缀：避免批量文件名时间戳严格连续（同源批量生成指纹）
            suffix = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=4))
            # 输出文件名前缀：ph-seabank 用 maribank(对齐真实品牌,去模板代号)
            file_prefix = _OUTPUT_NAME_MAP.get(bt_code, bt_code)
            filename = f"bill_{file_prefix}_{ts}_{suffix}.{args.format}"
            filepath = os.path.join(out_dir, filename)

            prefix = f"[{idx}/{total}]"
            print(f"{prefix} {bt_code} → {filepath}", end="", flush=True)

            try:
                # 一键填充默认值 + 随机地址
                field_values = _fill_defaults(bill_service, address_service, bt_code, region_code)
                # 生成 HTML
                html = bill_service.generate_html(bt_code, field_values)
                if html is None:
                    print(" ✗ HTML 生成失败")
                    errors += 1
                    continue

                if args.format == "html":
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(html)
                elif args.format == "pdf":
                    renderer.render_pdf(html, filepath)
                elif args.format == "png":
                    renderer.render_png(html, filepath)
                else:
                    print(f" ✗ 未知格式: {args.format}")
                    errors += 1
                    continue

                print(" ✓")

            except Exception as e:
                print(f" ✗ {e}")
                errors += 1

            # 每份文件之间加入随机间隔，避免"严格等间隔批量导出"指纹
            if idx < total:
                time.sleep(random.uniform(1, 5))

        # 批量生成时在类型批次之间加入随机间隔（额外增加，与文件间间隔叠加）
        if bt_code != types[-1]:
            time.sleep(random.uniform(3, 8))

    renderer.close()

    print(f"\n完成: {total - errors}/{total} 成功" + (f", {errors} 失败" if errors else ""))
    return 0 if errors == 0 else 1


def cmd_list(args):
    """列出所有可用账单类型"""
    print(f"{'类型代码':<30} {'名称':<40} {'地区':<10} {'币种':<6} {'分类':<10}")
    print("-" * 100)
    for bt in BILL_TYPES:
        region = next((r["name"] for r in REGIONS if r["id"] == bt["region_id"]), "?")
        print(f"{bt['code']:<30} {bt['name']:<40} {region:<10} {bt['currency']:<6} {bt['category']:<10}")
    print(f"\n共 {len(BILL_TYPES)} 个类型")


def cmd_validate(args):
    """验证某类型的数据完整性"""
    bt_code = args.type
    valid_codes = {bt["code"] for bt in BILL_TYPES}
    if bt_code not in valid_codes:
        print(f"错误: 未知类型 '{bt_code}'")
        return 1

    bill_service, address_service, renderer = _create_services()

    # 获取地区代码
    bt_info = next((bt for bt in BILL_TYPES if bt["code"] == bt_code), None)
    region_code = REGION_CODE_MAP.get(bt_info["region_id"], "gb")

    print(f"验证类型: {bt_code}")
    print("=" * 60)

    checks_passed = 0
    checks_failed = 0

    def check(name, condition, detail=""):
        nonlocal checks_passed, checks_failed
        if condition:
            print(f"  ✅ {name}")
            checks_passed += 1
        else:
            print(f"  ❌ {name} {detail}")
            checks_failed += 1

    # 生成数据
    field_values = _fill_defaults(bill_service, address_service, bt_code, region_code)
    html = bill_service.generate_html(bt_code, field_values)

    if html is None:
        print("  ❌ HTML 生成失败")
        return 1

    # 1. 检查残留占位符
    remaining = re.findall(r'\{\{(\w+)\}\}', html)
    check("无残留占位符", len(remaining) == 0, f"残留: {set(remaining)}" if remaining else "")

    # 2. 检查余额闭合
    defaults = get_field_defaults(bt_code)
    merged = {**defaults, **field_values}
    bill_service._generate_transactions(bt_code, merged)
    bill_service._calculate_balances(bt_code, merged)

    def _parse_f(val):
        try:
            return float(str(val).replace(",", "").replace("€", "").replace("£", "").replace("₱", "").strip())
        except (ValueError, TypeError):
            return 0.0

    opening = _parse_f(merged.get("opening_balance", 0))
    credits = _parse_f(merged.get("total_credits", 0))
    debits = _parse_f(merged.get("total_debits", 0))
    closing = _parse_f(merged.get("closing_balance", 0))
    expected_closing = round(opening + credits - debits, 2)

    check("余额闭合 (opening + credits - debits = closing)",
          abs(closing - expected_closing) < 0.01,
          f"closing={closing}, expected={expected_closing}")

    # 3. Octopus 特殊检查
    if bt_code == "gb-octopusenergybill":
        prev = float(merged.get("prev_balance_num", 0))
        charges = float(merged.get("charges_num", 0))
        payments = float(merged.get("payments_num", 0))
        credits = float(merged.get("credits_num", 0))
        nb = float(merged.get("new_balance_num", 0))
        expected = round(prev - charges + payments + credits, 2)
        check("Octopus new_balance = prev - charges + payments + credits（credit 口径）",
              abs(nb - expected) < 0.01,
              f"new_balance={nb}, expected={expected}")

    # 4. 检查交易收入/支出合计 = 汇总额
    if bt_code == "gb-monzo":
        def _num(s):
            return float(str(s).replace(",", "").replace("+", "").replace("-", "") or 0)
        txn_credits = re.findall(r'class="credit"[^>]*>([\d,]+\.\d{2})<', html)
        txn_debits = re.findall(r'class="debit"[^>]*>-([\d,]+\.\d{2})<', html)
        actual_c = sum(float(c.replace(",", "")) for c in txn_credits) if txn_credits else 0
        actual_d = sum(float(d.replace(",", "")) for d in txn_debits) if txn_debits else 0
        check("交易收入合计 = Total deposits",
              abs(actual_c - _num(merged.get("total_deposits", 0))) < 0.05,
              f"交易={actual_c:.2f}, 汇总={_num(merged.get('total_deposits', 0)):.2f}")
        check("交易支出合计 = Total outgoings",
              abs(actual_d - _num(merged.get("total_outgoings", 0))) < 0.05,
              f"交易={actual_d:.2f}, 汇总={_num(merged.get('total_outgoings', 0)):.2f}")

    # 4b. MariBank(ph-seabank)利息与预扣税专项检查
    #     防护:若生成器回归导致 interest_* 未写入,html_builder 会静默清空占位符,
    #     “无残留占位符”检查会误报通过,故此处必须显式校验。
    if bt_code == "ph-seabank":
        gross = merged.get("interest_gross", "")
        tax = merged.get("interest_tax", "")
        net = merged.get("interest_net", "")
        check("利息字段已写入 (gross/tax/net)",
              gross != "" and tax != "" and net != "",
              f"gross={gross}, tax={tax}, net={net}")
        if gross and tax and net:
            igross, itax, inet = float(gross), float(tax), float(net)
            # 每日计提模式下,每日 tax 单独 round 后求和,与月度 gross×0.20 有舍入累积差
            check("预扣税 ≈ 利息 × 20%（每日计提,允许舍入累积）",
                  abs(itax - igross * 0.20) < 0.20,
                  f"tax={itax}, expected≈{igross * 0.20:.2f}")
            check("净利息 = 总利息 - 预扣税",
                  abs(inet - round(igross - itax, 2)) < 0.01,
                  f"net={inet}, expected={round(igross - itax, 2)}")
            # 余额数千至数万时,整月 gross 不应超过 max(余额)×3.25%×31/365 的合理上限
            opening_bal = float(merged.get("opening_balance", 0))
            credits_bal = float(merged.get("total_credits", 0))
            max_bal = max(opening_bal, opening_bal + credits_bal)
            gross_limit = max_bal * 0.0325 * 31 / 365
            check("利息不超过 3.25% 月度理论上限",
                  igross <= gross_limit + 0.01,
                  f"gross={igross}, limit={gross_limit:.2f}")

        # 新增检查：尾部 legal-section 内容
        legal_html = re.findall(r'class="legal-section"', html)
        check("尾部法律条款区 (legal-section)", len(legal_html) > 0)

        # 新增检查：contact_email 使用官方邮箱
        contact_email = merged.get("contact_email", "")
        check(f"联系邮箱使用官方邮箱 ({contact_email})",
              "cs.maribank.com.ph" in contact_email,
              f"当前邮箱: {contact_email}")

        # 新增检查：交易明细表无 BALANCE 列（4 列结构）
        # 定位第二个 <table> 的 <thead>（Transaction Details 表，即 split 后索引 2）
        txn_tables = html.split('<table>')
        has_balance_in_txn = False
        for t_idx, tbl in enumerate(txn_tables):
            # 跳过首个 <table> 之前的内容（索引 0）和 Account Summary 表（索引 1）
            if t_idx < 2:
                continue
            # 检查该表是否包含 OUTGOING 或 INCOMING（交易明细表特征）
            if 'OUTGOING' in tbl or 'INCOMING' in tbl:
                if 'BALANCE' in tbl.split('</thead>')[0] if '</thead>' in tbl else '':
                    has_balance_in_txn = True
                    break
        check("交易明细表无 BALANCE 列（4 列结构）",
              not has_balance_in_txn,
              "交易明细表仍包含 BALANCE 列")

        # 新增检查：利息汇总行使用 TOTAL INTEREST(NET) 格式
        has_interest_summary = 'TOTAL INTEREST(NET)' in html
        check("利息汇总使用 TOTAL INTEREST(NET) 格式",
              has_interest_summary,
              "利息汇总格式不正确")

        # 新增检查：交易流中存在 INTEREST 行
        interest_in_txn = 'INTEREST' in html and 'NET INTEREST' in html
        check("交易流包含 INTEREST 入账行",
              interest_in_txn,
              "未找到 INTEREST 交易记录")

        # 新增检查：ATM Fee 按 owner 费率校验（Metrobank/BDO=₱18，其余回退 ₱15）
        from core.defaults import MARIBANK_ATM_OWNER_FEES, MARIBANK_ATM_FEE_DEFAULT
        fee_rows = re.findall(
            r'(\w+)\s*ATM\s*Fee</span></td><td class="text-right">[^<]*?([\d.]+)</td>', html)
        withdrawal_count = len(re.findall(r'ATM Withdrawal<', html))
        if withdrawal_count > 0:
            check(f"每笔 ATM 提现均有对应手续费 ({len(fee_rows)}费/{withdrawal_count}提现)",
                  len(fee_rows) == withdrawal_count,
                  f"提现 {withdrawal_count} 笔但只有 {len(fee_rows)} 笔手续费")
            fee_ok, fee_detail = True, []
            for bank, amount in fee_rows:
                expected = MARIBANK_ATM_OWNER_FEES.get(bank.upper(), MARIBANK_ATM_FEE_DEFAULT)
                if abs(float(amount) - expected) > 0.001:
                    fee_ok = False
                    fee_detail.append(f"{bank}={amount}(应为{expected})")
            check("ATM 手续费符合 owner 官方费率",
                  fee_ok,
                  "; ".join(fee_detail) if fee_detail else "")
        else:
            check("本份无 ATM 提现（fee 检查跳过）", True)

        # 检查：Logo 使用官方 PNG 品牌素材（.brand_ref/mb_logo_header.png）
        # 原手绘 SVG 仿制版已替换为官方 PNG（颜色内嵌在图片像素中，不再依赖 SVG 十六进制色值）
        has_official_logo = 'alt="MariBank"' in html and 'data:image/png;base64,' in html
        has_old_placeholder = '#F7941D' in html or '#0072BC' in html
        has_old_svg = '<svg class="brand-logo"' in html
        check("Logo 使用官方 PNG 品牌素材",
              has_official_logo and not has_old_placeholder and not has_old_svg,
              "官方 PNG logo 缺失、残留旧估算色或旧 SVG 仿制版")

    # 5. 检查地址一致性
    city = field_values.get("address_district", "")
    postcode = field_values.get("postal_code", "")
    check(f"地址已填充 (城市={city}, 邮编={postcode})",
          city != "" and postcode != "",
          "城市或邮编为空")

    # 5b. MariBank(ph-seabank) 地址簿一致性校验
    #     第四轮审核发现三词库随机拼接会产生真实地理冲突（street↔barangay 错配），
    #     现地址来自 _PH_ADDRESS_BOOK 整条记录，此处验证三元组确实在簿内。
    if bt_code == "ph-seabank":
        from core.defaults import _PH_ADDRESS_BOOK
        street = field_values.get("address_street", "")
        barangay = field_values.get("address_barangay", "")
        # address_street 带随机门牌号前缀，剥离后与地址簿比对
        street_only = re.sub(r"^\d+\s+", "", street).strip()
        book_records = _PH_ADDRESS_BOOK.get(city, [])
        matched = any(
            s == street_only and b == barangay and z == postcode
            for s, b, z in book_records
        )
        check(f"地址三元一致 (街道={street_only}, {barangay}, {postcode})",
              matched,
              "不在地址簿中——street/barangay/postcode 组合可能存在地理冲突")

    # 5c. gb-kraken UK 地址簿一致性校验
    #     第七轮审核 P0：street/postcode 不匹配（随机街道配随机邮编）。
    #     现地址来自 _UK_ADDRESS_BOOK 整条记录，此处验证在簿。
    if bt_code == "gb-kraken":
        from core.defaults import _UK_ADDRESS_BOOK
        uk_city = field_values.get("address_district", "")
        uk_street = field_values.get("address_street", "")
        uk_postcode = field_values.get("postal_code", "")
        uk_street_only = re.sub(r"^\d+\s+", "", uk_street).strip()
        uk_records = _UK_ADDRESS_BOOK.get(uk_city, [])
        uk_matched = any(
            s == uk_street_only and z == uk_postcode
            for s, z in uk_records
        )
        check(f"UK 地址一致 (街道={uk_street_only}, {uk_city}, {uk_postcode})",
              uk_matched,
              "不在 UK 地址簿中——street/postcode 组合可能不匹配")

    # 6. 检查姓名非固定值
    name = field_values.get("customer_name", "")
    check(f"姓名随机化 ({name})",
          name != "CHAN KA WAI",
          "仍是固定值 CHAN KA WAI")

    # 7. 检查账号非占位符（de-wise 无账号，用 IBAN 判断）
    acct = field_values.get("account_number", "")
    iban = field_values.get("wise_iban", "")
    acct_ok = (acct != "12345678" and acct != "") or (iban != "")
    check(f"账号非占位符 ({acct or iban})",
          acct_ok,
          "账号与 IBAN 均为空")

    # 8. Kraken 特殊检查
    if bt_code == "gb-kraken":
        # 检查 Public ID 格式
        pid = merged.get("kraken_public_id", "")
        check("Kraken Public ID 以 AA 开头",
              pid.startswith("AA") and len(pid) == 16,
              f"PID={pid}")

        # 检查 Portfolio 数量守恒（Spot + Staking 双钱包模型）
        port_html = merged.get("portfolio_table", "")
        txn_html = merged.get("transactions", "")
        if port_html and txn_html:
            # 提取 Portfolio 行：symbol / wallet / open_qty / close_qty
            port_rows = re.findall(r'<tr>(.*?)</tr>', port_html, re.DOTALL)
            txn_rows = re.findall(r'<tr>(.*?)</tr>', txn_html, re.DOTALL)

            # 交易侧：总量 delta（含 Stake:-1/Unstake:+1）与 Staking 迁移量
            qty_deltas = {}
            staked_delta = {}
            for row in txn_rows:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row)
                if len(cells) >= 5:
                    txn_type, symbol, amount = cells[1], cells[2], cells[4]
                    delta_map = {
                        "Buy": 1, "Deposit": 1, "Reward": 1,
                        "Sell": -1, "Withdrawal": -1,
                        # Stake/Unstake 是 Spot↔Staking 内部转移，总量不变
                        # （第六轮审核 P0：stake_amount_double_deducted_from_spot）
                        "Stake": 0, "Unstake": 0,
                        "Card Payment": 0,
                    }
                    amt = float(amount)
                    qty_deltas[symbol] = qty_deltas.get(symbol, 0) + amt * delta_map.get(txn_type, 0)
                    if txn_type == "Stake":
                        staked_delta[symbol] = staked_delta.get(symbol, 0) + amt
                    elif txn_type == "Unstake":
                        staked_delta[symbol] = staked_delta.get(symbol, 0) - amt

            # Portfolio 侧：按 (symbol, wallet) 归并；守恒关系：
            #   Spot:    close_spot = open_spot + 总delta − 净stake迁移
            #   Staking: close_staked = 净stake迁移
            port_balances = {}   # symbol -> {"spot": (open, close), "staking": (open, close)}
            for row in port_rows:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row)
                if len(cells) >= 9:
                    symbol, wallet = cells[0], cells[1]
                    open_qty, close_qty = float(cells[2]), float(cells[5])
                    entry = port_balances.setdefault(symbol, {})
                    if wallet == "Staking":
                        entry["staking"] = (open_qty, close_qty)
                    else:
                        entry["spot"] = (open_qty, close_qty)

            all_conserved = True
            for symbol, entry in port_balances.items():
                total_delta = qty_deltas.get(symbol, 0)
                net_staked = round(staked_delta.get(symbol, 0), 6)
                spot = entry.get("spot")
                if not spot:
                    continue
                expected_spot = round(spot[0] + total_delta - net_staked,
                                      6 if symbol != "XRP" else 2)
                if abs(spot[1] - expected_spot) > 0.01:
                    all_conserved = False
                    check(f"持仓守恒 {symbol}(Spot)", False,
                          f"close={spot[1]}, expected={expected_spot}")
                if net_staked > 0:
                    stk = entry.get("staking")
                    if not stk or abs(stk[1] - net_staked) > 0.01:
                        all_conserved = False
                        check(f"持仓守恒 {symbol}(Staking)", False,
                              f"staked行缺失或 close={stk[1] if stk else None}, expected={net_staked}")

            if all_conserved:
                check("持仓守恒 (Spot+Staking 双钱包闭合)", True)

        # 价格带校验：每笔 Activity 成交价与快照价必须落在当日真实带宽内
        # （第五轮审核 P0：transaction/snapshot price outside real market range）
        from core.crypto_prices import _get_day_band
        price_ok, price_bad = True, []
        period_start_s = merged.get("period_start", "")
        period_end_s = merged.get("period_end", "")
        for row in re.findall(r'<tr>(.*?)</tr>', merged.get("transactions", ""), re.DOTALL):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row)
            if len(cells) >= 6:
                day_str = cells[0][:10]
                sym, price_txt = cells[2], cells[5]
                m_price = re.search(r'([\d,.]+)', price_txt)
                if not (day_str[:2].isdigit() and m_price):
                    continue
                lo, hi = _get_day_band(sym, day_str)
                p = float(m_price.group(1).replace(',', ''))
                if not (lo * 0.995 <= p <= hi * 1.005):
                    price_ok = False
                    price_bad.append(f"{sym}@{day_str}={p} 应在[{lo:.2f},{hi:.2f}]")

        # 快照价校验：Portfolio Open 取账期首日带、Close 取末日带
        for row in re.findall(r'<tr>(.*?)</tr>', merged.get("portfolio_table", ""), re.DOTALL):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row)
            if len(cells) >= 9:
                sym = cells[0]
                m_open = re.search(r'([\d,.]+)', cells[3])
                m_close = re.search(r'([\d,.]+)', cells[6])
                if not (m_open and m_close and period_start_s):
                    continue
                lo_o, hi_o = _get_day_band(sym, period_start_s)
                lo_c, hi_c = _get_day_band(sym, period_end_s)
                po = float(m_open.group(1).replace(',', ''))
                pc = float(m_close.group(1).replace(',', ''))
                if not (lo_o * 0.995 <= po <= hi_o * 1.005):
                    price_ok = False
                    price_bad.append(f"{sym} Open={po} 应在[{lo_o:.2f},{hi_o:.2f}]")
                if not (lo_c * 0.995 <= pc <= hi_c * 1.005):
                    price_ok = False
                    price_bad.append(f"{sym} Close={pc} 应在[{lo_c:.2f},{hi_c:.2f}]")

        if price_ok:
            check("成交/快照价全部落在当日真实价格带", True)
        else:
            check("成交/快照价全部落在当日真实价格带", False, "; ".join(price_bad[:3]))

    print("\n" + "=" * 60)
    print(f"结果: {checks_passed} 通过, {checks_failed} 失败")
    renderer.close()
    return 0 if checks_failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="oneT CLI - 命令行账单生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python cli.py list                                    列出所有类型
  python cli.py gen --type gb-monzo                     生成1份 Monzo PDF
  python cli.py gen --type gb-kraken --format png      生成 Kraken PNG
  python cli.py gen --type gb-monzo --count 10         批量生成10份
  python cli.py gen --all --out ./test/                 生成所有类型
  python cli.py gen --type gb-monzo --seed 42          固定种子（可复现）
  python cli.py validate --type gb-monzo               验证数据完整性
""")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # gen 子命令
    gen_parser = subparsers.add_parser("gen", help="生成账单")
    gen_parser.add_argument("--type", "-t", help="账单类型代码（如 gb-monzo）")
    gen_parser.add_argument("--format", "-f", choices=["pdf", "png", "html"],
                            default="pdf", help="输出格式 (默认: pdf)")
    gen_parser.add_argument("--out", "-o", default="./output/", help="输出目录 (默认: ./output/)")
    gen_parser.add_argument("--count", "-n", type=int, default=1, help="批量生成数量 (默认: 1)")
    gen_parser.add_argument("--all", action="store_true", help="生成所有类型")
    gen_parser.add_argument("--seed", type=int, help="随机种子（可复现）")

    # list 子命令
    subparsers.add_parser("list", help="列出所有可用账单类型")

    # validate 子命令
    val_parser = subparsers.add_parser("validate", help="验证数据完整性")
    val_parser.add_argument("--type", "-t", required=True, help="账单类型代码")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    # 设置随机种子
    if hasattr(args, "seed") and args.seed is not None:
        random.seed(args.seed)
        print(f"随机种子: {args.seed}")

    if args.command == "gen":
        return cmd_gen(args)
    elif args.command == "list":
        cmd_list(args)
        return 0
    elif args.command == "validate":
        return cmd_validate(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
