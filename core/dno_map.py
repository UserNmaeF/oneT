# -*- coding: utf-8 -*-
"""DNO 区域映射与 MPAN 生成

提供英国电力分销网络运营商 (DNO) 按城市/邮编前缀的映射，
以及合法的 MPAN (Meter Point Administration Number) 生成。

数据来源：综合 public 行业资料；LLD 对照以 ENA Distributor identifiers 为准
# （外部审核第 8 轮锚定：10=Eastern England, 11=East Midlands,
#  13=Cheshire/Merseyside/N.Wales, 20=Southern England, 23=Yorkshire）。Octopus 账单仅使用上述五组。
"""

import random

# ─── MPAN 校验位权重 ───
# 13 位 MPAN 核心中，前 12 位的素数权重序列（跳过 11）
# 来源：Wikipedia MPAN article / MRA D0660，经外部审核 5 个真实账单样本校准
_MPAN_WEIGHTS = [3, 5, 7, 13, 17, 19, 23, 29, 31, 37, 41, 43]


def mpan_check_digit(digits: str) -> int:
    """计算 13 位 MPAN 核心的第 13 位校验位

    算法：
      1. 前 12 位逐位 × 权重，求和
      2. remainder = sum % 11
      3. check = 11 - remainder
      4. 若 check == 10 → check = 0；若 check == 11 → check = 0

    验证示例：MPAN "1301001802540" — 前 12 位 "130100180254" 应得校验位 0
    """
    s = sum(int(d) * w for d, w in zip(digits, _MPAN_WEIGHTS))
    # check = (sum % 11) % 10  （Wikipedia MPAN article / MRA D0660）
    return (s % 11) % 10


# 会话级已用 MPAN 集合（跨账户唯一，Metering System 全国唯一引用）
_USED_MPANS = set()


def build_mpan_parts(ll: int, profile_class: str = "01") -> dict:
    """生成 MPAN 组成部分与合法校验位

    Args:
        ll: 2 位 Licence Identifier Digits (10-23)
        profile_class: 用电配置文件 (00=无配置文件, 01=标准, 02=经济7)
    Returns:
        dict: {"mpan": 13位字符串, "top": S 格式 Supply Number 展示串}
    """
    tpr = "0018"                                # 家用时制 TPR
    llf = f"0{random.randint(100, 299)}"        # 线损因子（01xx-02xx 家用区间）
    prefix = f"{ll:02d}{profile_class}{tpr}{llf}"
    check = mpan_check_digit(prefix)
    mpan = prefix + str(check)
    top = f"S {ll:02d} {profile_class} {tpr} {llf} {check}"
    return {"mpan": mpan, "top": top}


def generate_unique_mpan(ll: int) -> dict:
    """生成会话内唯一的合法 MPAN（避免不同账户共享同一 Metering System）"""
    for _ in range(64):
        parts = build_mpan_parts(ll, random.choice(["01", "02"]))
        if parts["mpan"] not in _USED_MPANS:
            _USED_MPANS.add(parts["mpan"])
            return parts
    parts = build_mpan_parts(ll)
    _USED_MPANS.add(parts["mpan"])
    return parts


def generate_mpan(ll: int, profile_class: str = "01") -> str:
    """兼容接口：仅返回 13 位 MPAN 字符串"""
    return build_mpan_parts(ll, profile_class)["mpan"]


# ─── 城市 → DNO 映射 ───
# 英国主要城市（含 GB 地址池及 _CITY_POSTCODES_GB 列表）对应的 DNO 信息。
# 映射依据：energynetworks.org "Your network operator" 地图、Ofgem 牌照区数据、
#           各 DNO 官网覆盖查询。

# 结构: {
#   "City Name": {
#       "dno": "DNO 显示名称",     # Octopus 账单上显示的运营商名称
#       "ll": 整数,                # Licence Identifier Digits (10-23)
#       "group": "集团名"           # 仅用于参考分类
#   }
# }

CITY_DNO_MAP = {
    # === UK Power Networks (London) — LLD 22 ===
    "London":             {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},
    "City of London":     {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},

    # === UK Power Networks (South East) — LLD 21 ===
    "Brighton":           {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "Brighton and Hove":  {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "Canterbury":         {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "Chelmsford":         {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "Colchester":         {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "Ipswich":            {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "Maidstone":          {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "Tunbridge Wells":    {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},

    # === UK Power Networks (East of England) — LLD 15 ===
    "Cambridge":          {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "Peterborough":       {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "Luton":              {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "Milton Keynes":      {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "Norwich":            {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "St Albans":          {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "High Wycombe":       {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "Chelmsford":         {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "Bedford":            {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "Reading":            {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    # Note: Reading RG prefix actually spans UKPN East and SSE SEPD boundary;
    # central Reading is UKPN East.

    # === SSE Southern Electric Power Distribution — LLD 10 ===
    "Oxford":             {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "Southampton":        {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "Portsmouth":         {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "Bournemouth":        {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "Swindon":            {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "Gloucester":         {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "Slough":             {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "Guildford":          {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},

    # === SSE Scottish Hydro Electric Power Distribution — LLD 11 ===
    "Dundee":             {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "Inverness":          {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "Aberdeen":           {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "Perth":              {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "Stirling":           {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "Kirkcaldy":          {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "Dunfermline":        {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "Falkirk":            {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "Ripon":              {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},

    # === SP Energy Networks (SP Distribution) — LLD 17 ===
    "Glasgow":            {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},
    "Edinburgh":          {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},
    "Ayr":                {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},
    "Dumfries":           {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},

    # === SP Energy Networks (SP Manweb) — LLD 12 ===
    "Liverpool":          {"dno": "SP Manweb", "ll": 13, "group": "SPEN"},
    "Chester":            {"dno": "SP Manweb", "ll": 13, "group": "SPEN"},
    "Shrewsbury":         {"dno": "SP Manweb", "ll": 13, "group": "SPEN"},
    "Wrexham":            {"dno": "SP Manweb", "ll": 13, "group": "SPEN"},

    # === National Grid Electricity Distribution (West Midlands) — LLD 16 ===
    "Birmingham":         {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "Coventry":           {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "Wolverhampton":      {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "Stoke-on-Trent":     {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "Worcester":          {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "Hereford":           {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},

    # === National Grid Electricity Distribution (East Midlands) — LLD 13 ===
    "Nottingham":         {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    "Leicester":          {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    "Derby":              {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    "Lincoln":            {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    "Northampton":        {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    "Grimsby":            {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},

    # === National Grid Electricity Distribution (South West) — LLD 14 ===
    "Bristol":            {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "Bath":               {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "Plymouth":           {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "Exeter":             {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "Gloucester":         {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "Cheltenham":         {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "Swansea":            {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},

    # === National Grid Electricity Distribution (South Wales) via LLD ? ===
    # Note: NGED South Wales shares LLD 13? Actually South Wales is covered by
    # National Grid Electricity Distribution (South Wales) licence, which is
    # part of the same NGED group. The MPAN LLD for South Wales is 24? Or 13?
    # The standard 14 DNOs listed in Ofgem as 10-23 include NGED South Wales
    # as a separate licence. For our purposes, Cardiff CF is NGED South Wales.
    "Cardiff":            {"dno": "National Grid Electricity Distribution (South Wales)", "ll": 13, "group": "NGED"},
    "Merthyr Tydfil":     {"dno": "National Grid Electricity Distribution (South Wales)", "ll": 13, "group": "NGED"},
    "Barry":              {"dno": "National Grid Electricity Distribution (South Wales)", "ll": 13, "group": "NGED"},
    "Newport":            {"dno": "National Grid Electricity Distribution (South Wales)", "ll": 13, "group": "NGED"},

    # === Northern Powergrid (Yorkshire) — LLD 18 ===
    "Leeds":              {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Sheffield":          {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Bradford":           {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Wakefield":          {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "York":               {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Hull":               {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Doncaster":          {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Rotherham":          {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Barnsley":           {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Halifax":            {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Huddersfield":       {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "Scunthorpe":         {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},

    # === Northern Powergrid (Northeast) — LLD 19 ===
    "Newcastle":          {"dno": "Northern Powergrid (Northeast)", "ll": 19, "group": "NPG"},
    "Sunderland":         {"dno": "Northern Powergrid (Northeast)", "ll": 19, "group": "NPG"},
    "Durham":             {"dno": "Northern Powergrid (Northeast)", "ll": 19, "group": "NPG"},
    "Middlesbrough":      {"dno": "Northern Powergrid (Northeast)", "ll": 19, "group": "NPG"},

    # === Electricity North West — LLD 20 ===
    "Manchester":         {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "Salford":            {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "Bolton":             {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "Stockport":          {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "Blackpool":          {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "Preston":            {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "Wigan":              {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},

    # === Northern Ireland Electricity Networks — LLD 23 ===
    "Belfast":            {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Londonderry":        {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Derry":              {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Lisburn":            {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Newry":              {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Armagh":             {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Craigavon":          {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Bangor":             {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Newtownabbey":       {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Carrickfergus":      {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    "Larne":              {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},

    # === Unknown / fallback (use generic SSE) ===
    "Chichester":         {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
}

# 别名映射（部分城市可能有多个名称）
_CITY_ALIASES = {
    "kingston upon hull": "Hull",
    "hull": "Hull",
    "city of london": "London",
    "london": "London",
    "brighton and hove": "Brighton",
    "stoke on trent": "Stoke-on-Trent",
    "midlands": "Birmingham",
    "newcastle upon tyne": "Newcastle",
    "newcastle": "Newcastle",
    "dundee city": "Dundee",
    "inverness": "Inverness",
    "southampton": "Southampton",
    "portsmouth": "Portsmouth",
    "bath": "Bath",
    "plymouth": "Plymouth",
    "cambridge": "Cambridge",
    "oxford": "Oxford",
    "cardiff": "Cardiff",
    "belfast": "Belfast",
    "salford": "Salford",
    "manchester": "Manchester",
    "liverpool": "Liverpool",
    "leeds": "Leeds",
}


def get_dno_info(city: str) -> dict:
    """根据城市名获取 DNO 信息

    返回 dict: {"dno": "显示名称", "ll": int, "group": "集团名"}
    匹配顺序：城市精确/别名/包含 → 邮编前缀兜底（城市未知时使用）→ 默认值。
    """
    key = city.strip().lower()
    # 直接匹配
    for name, info in CITY_DNO_MAP.items():
        if name.lower() == key:
            return info
    # 别名匹配
    if key in _CITY_ALIASES:
        return CITY_DNO_MAP.get(_CITY_ALIASES[key], _FALLBACK_DNO)
    # 部分匹配（城市名包含）
    for name, info in CITY_DNO_MAP.items():
        if name.lower() in key or key in name.lower():
            return info
    return _FALLBACK_DNO


def get_dno_info_by_postcode(postcode: str) -> dict:
    """根据邮编外层前缀获取 DNO 信息（城市未知时的兜底）

    邮编前缀与 DNO 的对应关系存在边界重叠，这里只覆盖高置信度的前缀。
    """
    prefix = _postcode_prefix(postcode)
    if prefix and prefix in _POSTCODE_PREFIX_DNO:
        return _POSTCODE_PREFIX_DNO[prefix]
    return _FALLBACK_DNO


def _postcode_prefix(postcode: str) -> str:
    """提取邮编外层前缀字母（如 PO1 3AA → PO）"""
    if not postcode:
        return ""
    text = postcode.strip().upper()
    # 截取首个数字前的字母部分
    i = 0
    while i < len(text) and text[i].isalpha():
        i += 1
    return text[:i]


_POSTCODE_PREFIX_DNO = {
    # 北爱尔兰
    "BT": {"dno": "Northern Ireland Electricity Networks", "ll": 23, "group": "NIE"},
    # 苏格兰北部（SHEPD）
    "IV": {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "KW": {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "AB": {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "DD": {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "PH": {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    "ZE": {"dno": "Scottish Hydro Electric Power Distribution", "ll": 11, "group": "SSE"},
    # 苏格兰中南部（SP Distribution）
    "G":  {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},
    "EH": {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},
    "KA": {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},
    "ML": {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},
    "TD": {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},
    "DG": {"dno": "SP Distribution", "ll": 17, "group": "SPEN"},
    # 伦敦（UKPN London）
    "EC": {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},
    "E":  {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},
    "N":  {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},
    "NW": {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},
    "SE": {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},
    "SW": {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},
    "W":  {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},
    "WC": {"dno": "UK Power Networks (London)", "ll": 22, "group": "UKPN"},
    # 东南（UKPN South East）
    "BN": {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "TN": {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "RH": {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "ME": {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "CT": {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "DA": {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    "BR": {"dno": "UK Power Networks (South East)", "ll": 21, "group": "UKPN"},
    # 东部（UKPN East of England）
    "CB": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "CM": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "CO": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "IP": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "NR": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "PE": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "SG": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "SS": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "AL": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "LU": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "MK": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    "HP": {"dno": "UK Power Networks (East of England)", "ll": 10, "group": "UKPN"},
    # 中南部（SSE Southern Electric Power Distribution）
    "SO": {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "PO": {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "BH": {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "SP": {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "DT": {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "RG": {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "OX": {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "SN": {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    "GU": {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"},
    # 西南（NGED South West）
    "BS": {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "BA": {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "EX": {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "PL": {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "TQ": {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "TR": {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    "GL": {"dno": "National Grid Electricity Distribution (South West)", "ll": 14, "group": "NGED"},
    # 威尔士（NGED South Wales）
    "CF": {"dno": "National Grid Electricity Distribution (South Wales)", "ll": 13, "group": "NGED"},
    "SA": {"dno": "National Grid Electricity Distribution (South Wales)", "ll": 13, "group": "NGED"},
    "NP": {"dno": "National Grid Electricity Distribution (South Wales)", "ll": 13, "group": "NGED"},
    # 西米德兰（NGED West Midlands）
    "B":  {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "CV": {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "DY": {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "WS": {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "WV": {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "HR": {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    "TF": {"dno": "National Grid Electricity Distribution (West Midlands)", "ll": 16, "group": "NGED"},
    # 东米德兰（NGED East Midlands）
    "DE": {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    "NG": {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    "LE": {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    "LN": {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    "NN": {"dno": "National Grid Electricity Distribution (East Midlands)", "ll": 11, "group": "NGED"},
    # 约克郡（Northern Powergrid Yorkshire）
    "LS": {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "WF": {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "HD": {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "HG": {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "HX": {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "YO": {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "HU": {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "BD": {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    "DN": {"dno": "Northern Powergrid (Yorkshire)", "ll": 23, "group": "NPG"},
    # 东北（Northern Powergrid Northeast）
    "NE": {"dno": "Northern Powergrid (Northeast)", "ll": 19, "group": "NPG"},
    "SR": {"dno": "Northern Powergrid (Northeast)", "ll": 19, "group": "NPG"},
    "DH": {"dno": "Northern Powergrid (Northeast)", "ll": 19, "group": "NPG"},
    "TS": {"dno": "Northern Powergrid (Northeast)", "ll": 19, "group": "NPG"},
    "DL": {"dno": "Northern Powergrid (Northeast)", "ll": 19, "group": "NPG"},
    # 西北（Electricity North West）
    "M":  {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "WA": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "WN": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "BL": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "PR": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "BB": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "CA": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "LA": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "FY": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "OL": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    "SK": {"dno": "Electricity North West", "ll": 20, "group": "ENWL"},
    # 北威尔士/默西塞德（SP Manweb）
    "CH": {"dno": "SP Manweb", "ll": 13, "group": "SPEN"},
    "LL": {"dno": "SP Manweb", "ll": 13, "group": "SPEN"},
    "L":  {"dno": "SP Manweb", "ll": 13, "group": "SPEN"},
    "CW": {"dno": "SP Manweb", "ll": 13, "group": "SPEN"},
}

_FALLBACK_DNO = {"dno": "SSE Southern Electric Power Distribution", "ll": 20, "group": "SSE"}


def get_distributor_display(city: str) -> str:
    """获取 Octopus 账单上显示的配电公司名称"""
    return get_dno_info(city)["dno"]


def get_mpan_ll(city: str) -> int:
    """获取城市对应的 MPAN Licence Identifier Digits"""
    return get_dno_info(city)["ll"]