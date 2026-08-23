# -*- coding: utf-8 -*-
"""默认值生成"""

import random
import string
from datetime import datetime, timedelta

# ─── 英国日期格式化辅助函数 ───

_MONTHS_FULL = ["January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]
_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _ordinal_suffix(day: int) -> str:
    """返回日期序数后缀：1st, 2nd, 3rd, 4th..."""
    if 10 < day % 100 < 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _uk_date(date_str: str, short_month: bool = False) -> str:
    """YYYY-MM-DD → '30th June 2026' 或 '30th Jun 2026'"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    months = _MONTHS_SHORT if short_month else _MONTHS_FULL
    return f"{dt.day}{_ordinal_suffix(dt.day)} {months[dt.month - 1]} {dt.year}"


def _uk_date_range(start_str: str, end_str: str) -> str:
    """生成 '17th Jul - 31st Jul' 格式的日期区间（短月份名）"""
    return f"{_uk_date(start_str, short_month=True)} - {_uk_date(end_str, short_month=True)}"


def _is_eu_dst(day: datetime) -> bool:
    """判断日期是否处于欧盟夏令时（CEST）

    欧盟规则：3 月最后一个周日 01:00 UTC 至 10 月最后一个周日 01:00 UTC。
    2026 年：3 月 29 日 - 10 月 25 日（德国/比利时与欧盟一致）。
    """
    year = day.year
    last_march_sunday = datetime(year, 3, 31) - timedelta(days=(datetime(year, 3, 31).weekday() + 1) % 7)
    last_oct_sunday = datetime(year, 10, 31) - timedelta(days=(datetime(year, 10, 31).weekday() + 1) % 7)
    return last_march_sunday <= day < last_oct_sunday


def _eu_offset_label(day: datetime) -> str:
    """Wise EUR 账单使用的时区标签

    真实 Wise statement 显示 GMT offset（如 [GMT+02:00]），而非 CET/CEST 缩写：
      - 夏令时（3 月底 - 10 月底）→ GMT+02:00
      - 冬令时 → GMT+01:00
    """
    return "GMT+02:00" if _is_eu_dst(day) else "GMT+01:00"


# ─── 银行固定代码（不能用随机值，必须与银行真实信息匹配） ───

# 各银行的真实 sort code（公开信息）
BANK_SORT_CODES = {
    "gb-monzo": "04-00-04",           # Monzo 真实 sort code
    "de-wise": "23-14-70",            # Wise UK sort code
    "gb-wisegbpstatementuk": "23-14-70",
    "de-monese": "04-29-21",          # Monese sort code (UK 体系)
}

# 比利时 IBAN 银行码（NBB 分配）
# Wise Europe SA (BIC TRWIBEB1) 为 "967"
# PPS EU SA (BIC PESOBEB1) 为 "974"（从真实 Monese EUR 对账单样本核实：
#   IBAN BE96974149185205 → BBAN 974 1491852 05，银行码 974
#   IBAN BE29974102728164 → BBAN 974 1027281 64，银行码 974
# 两份独立样本一致确认）
DE_MONESE_BE_BANK_CODE = "974"

# 各银行的真实 BIC
BANK_BICS = {
    "gb-monzo": "MONZGB2L",
    "de-wise": "TRWIGB2L",            # 修正：TRWIGB2L 不是 WISEGB2L
    "gb-wisegbpstatementuk": "TRWIGB2L",
    "de-monese": "PESOBEB1",           # PPS EU SA (比利时 EMI, EEA 客户)
    "gb-monese": "MNEEGB21",           # Monese UK 实体 (UK 客户)
}

# IBAN 中的 4 字符银行代码（取 BIC 前 4 位）
BANK_IBAN_CODES = {
    "gb-monzo": "MONZ",
    "de-wise": "TRWI",                # 修正：TRWI 不是 WISE
    "gb-wisegbpstatementuk": "TRWI",
    "de-monese": "PESO",              # PPS EU SA 银行代码
    "gb-monese": "MNSE",              # Monese UK 实体
}

# ─── MariBank Philippines 业务常量（对齐 2026 真实规则）───
MARIBANK_INTEREST_RATE_ANNUAL = 0.0325      # 余额 ≤ 1,000,000 PHP 的年利率
MARIBANK_INTEREST_RATE_HIGH = 0.0375        # 超 1,000,000 部分年利率
MARIBANK_HIGH_TIER_THRESHOLD = 1_000_000    # 高档利率起算余额
MARIBANK_INTEREST_TAX_RATE = 0.20           # 利息预扣税税率（withholding tax）
MARIBANK_ACCOUNT_NO_LEN = 11                # MariBank 账户号位数（纯数字）
MARIBANK_SN_PREFIX = "S01"                  # S/N 序列号前缀
MARIBANK_SN_DATE_FMT = "%y%m%d"              # S/N 中段用账期结束日(YYMMDD),对齐真实 eStatement
MARIBANK_SN_RANDOM_LEN = 8                  # S/N 末段随机字母长度(对齐真实 S01-YYMMDDXXXXXXXX)
MARIBANK_OPENING_RANGE = (3000, 30000)      # ph-seabank 期初余额范围（原全局 800 连一笔 ATM 都放不下）
MARIBANK_MIN_BUFFER = 100                   # 逐笔生成时保留的最小可用余额缓冲
PDIC_COVERAGE_LIMIT = 1_000_000             # 菲律宾存款保险上限（PHP）
# MariBank Philippines 官方联系邮箱（取自 PDS 产品披露表）
MARIBANK_CONTACT_EMAIL = "contact@cs.maribank.com.ph"
# MariBank 利息计息公式生效日期（对齐 2026-03/05 公开样本：*Computation is effective from 15 JAN 2026）
MARIBANK_INTEREST_EFFECTIVE_DATE = "15 JAN 2026"
# MariBank Philippines 总行办公地址（官方 Branch Locations 页面确认）
MARIBANK_HEAD_OFFICE = "MariBank Philippines, Inc., 32 Rizal Street, Brgy. Poblacion II, Pagsanjan, Laguna"
# 本地 ATM 提现手续费（官方 Fees & Rates 页面确认：Local ATM Cash Withdrawal ₱15）
# MariBank 规则：若 ATM owner 自身收取 transaction fee，则只适用该 owner fee。
MARIBANK_ATM_FEE = 15.0
# 各 ATM owner 银行对非本行本地卡的实际提现费（官方公开费率核实）：
#   Metrobank 官方 FAQ：Other LOCAL cards → ₱18
#   BDO 官方 ATM 页面：Non-BDO Local Cards → ₱18
#   BPI 未公布固定跨行提现费（仅说明因银行/owner 而异）→ 回退 MariBank 自身费率
MARIBANK_ATM_OWNER_FEES = {
    "METROBANK": 18.0,
    "BDO": 18.0,
}
MARIBANK_ATM_FEE_DEFAULT = MARIBANK_ATM_FEE


def _gen_uk_sort_code() -> str:
    """生成随机英国 Sort Code：XX-XX-XX 格式（仅用于无固定 sort code 的场景）"""
    d = [random.randint(0, 9) for _ in range(6)]
    return f"{d[0]}{d[1]}-{d[2]}{d[3]}-{d[4]}{d[5]}"


# 会话级已用账号集合（防止跨样本冲突：不同人不能用同账号）
_USED_ACCOUNT_NUMBERS = set()

# 英国常见姓名（用于随机生成客户名，避免多张账单都是 CHAN KA WAI）
_UK_FIRST_NAMES = [
    "James", "Oliver", "George", "Harry", "Jack", "Charlie", "Thomas", "William",
    "Emily", "Sophia", "Olivia", "Amelia", "Emma", "Charlotte", "Lily", "Ella",
    "Daniel", "Matthew", "Ryan", "Nathan", "Samuel", "Alexander", "Benjamin", "Ethan",
    "Grace", "Chloe", "Freya", "Sophie", "Mia", "Isabella", "Poppy", "Daisy",
    "Stanley", "Sam", "Zander", "Glen", "Danielle", "Jerome", "Marcus", "Felix",
]
_UK_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Taylor", "Davies", "Wilson",
    "Evans", "Thomas", "Roberts", "Walker", "Wright", "Thompson", "White", "Hughes",
    "Edwards", "Green", "Hall", "Wood", "Harris", "Martin", "Jackson", "Clarke",
    "Turner", "Hamilton", "Matthews", "Armstrong", "Rhodes", "Barnes", "Cooper", "Fisher",
]


def _gen_uk_account_number() -> str:
    """生成随机 8 位账号（会话内唯一，不重复）"""
    while True:
        acct = "".join(random.choices(string.digits, k=8))
        if acct not in _USED_ACCOUNT_NUMBERS:
            _USED_ACCOUNT_NUMBERS.add(acct)
            return acct


# VocaLink 04-00-04（Monzo）Double Alternate 国内模量校验
# 规则（VocaLink Validating Account Numbers, 040004 无 Exception）：
#   账号 8 位 × 权重 8,7,6,5,4,3,2,1；乘积 ≥10 时对乘积各位求和一次；
#   累加总和 mod 10 == 0 才通过。
_VOCALINK_040004_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 1)


def _vocalink_040004_pass(account_number: str) -> bool:
    """校验账号能否与 Monzo sort code 04-00-04 合法配对"""
    total = 0
    for d, w in zip(account_number.zfill(8), _VOCALINK_040004_WEIGHTS):
        p = int(d) * w
        if p >= 10:
            p = sum(int(x) for x in str(p))
        total += p
    return total % 10 == 0


def _gen_monzo_account_number() -> str:
    """生成 Monzo 账号：随机 8 位且通过 VocaLink DBLAL 国内校验"""
    while True:
        acct = _gen_uk_account_number()
        if _vocalink_040004_pass(acct):
            return acct


def _gen_uk_iban(bank_code: str, sort_code: str, account_number: str) -> str:
    """从银行代码、sort code、账号生成合规的英国 IBAN

    显示分组对齐真实样本：GB17 MONZ 0400 0334 6467 72
    （GB+校验位 与银行码之间有空格；其后 14 位按 4-4-4-2 分组）
    """
    sc = sort_code.replace("-", "")
    base = f"GB00{bank_code}{sc}{account_number}"
    rearranged = base[4:] + base[:4]
    converted = ""
    for ch in rearranged:
        if ch.isalpha():
            converted += str(ord(ch.upper()) - 55)
        else:
            converted += ch
    check = 98 - (int(converted) % 97)
    check_str = str(check).zfill(2)
    digits = f"{sc}{account_number}"          # 6 位排序码 + 8 位账号 = 14 位
    groups = f"{digits[0:4]} {digits[4:8]} {digits[8:12]} {digits[12:14]}"
    return f"GB{check_str} {bank_code} {groups}"


def _get_bank_sort_code(bt_code: str) -> str:
    """获取银行的真实 sort code"""
    return BANK_SORT_CODES.get(bt_code, _gen_uk_sort_code())


def _get_bank_bic(bt_code: str) -> str:
    """获取银行的真实 BIC"""
    return BANK_BICS.get(bt_code, "MONZGB2L")


def _get_bank_iban_code(bt_code: str) -> str:
    """获取 IBAN 中的银行代码"""
    return BANK_IBAN_CODES.get(bt_code, "MONZ")


# ─── 英国邮编生成器 ───

# 城市-邮编配对表（确保邮编与城市匹配，不会出现 Brighton + ZG1 这种不匹配）
_CITY_POSTCODES_GB = [
    ("London", "SW1A 1AA"), ("London", "EC2A 4JE"), ("London", "N1 9GU"),
    ("City of London", "EC2A 4JE"),
    ("Manchester", "M1 1AE"), ("Manchester", "M2 5BD"),
    ("Birmingham", "B4 7DL"), ("Birmingham", "B2 4QA"),
    ("Liverpool", "L1 8JQ"), ("Leeds", "LS1 1UR"),
    ("Glasgow", "G3 6RA"), ("Edinburgh", "EH3 9DR"),
    ("Bristol", "BS1 5AH"), ("Sheffield", "S1 2BJ"),
    ("Newcastle", "NE1 1AE"), ("Nottingham", "NG1 1AA"),
    ("Southampton", "SO14 7DW"), ("Portsmouth", "PO1 3AA"),
    ("Brighton", "BN1 1AA"), ("Brighton", "BN1 1FN"),
    ("Oxford", "OX1 1AA"), ("Cambridge", "CB2 3BU"),
    ("Cardiff", "CF5 1LJ"), ("Belfast", "BT7 3AB"),
    ("York", "YO1 7JT"), ("Bath", "BA1 1AA"),
    ("Leicester", "LE1 1AA"), ("Coventry", "CV1 2GB"),
    ("Reading", "RG1 2LG"), ("Milton Keynes", "MK9 1AA"),
    ("Wakefield", "WF1 1AA"), ("Exeter", "EX2 8GY"),
    ("Plymouth", "PL1 5EJ"), ("Derby", "DE1 1AA"),
    ("Norwich", "NR1 1AA"), ("Aberdeen", "AB25 1GA"),
    ("Dundee", "DD1 1LW"), ("Swansea", "SA1 1AA"),
    ("Hull", "HU1 1AA"), ("Sunderland", "SR1 1SB"),
    ("Wolverhampton", "WV1 1AA"), ("Stoke-on-Trent", "ST4 1LE"),
    ("Bradford", "BD1 1LH"), ("Luton", "LU1 1AA"),
    ("Bournemouth", "BH1 1AA"), ("Swindon", "SN1 3JL"),
    ("Gloucester", "GL1 1BZ"), ("Worcester", "WR1 1AA"),
    ("Newport", "NP20 1JE"), ("Inverness", "IV1 1HY"),
    ("Salford", "M6 6HE"), ("Wigan", "WN1 1AA"),
    ("Bolton", "BL1 1DY"), ("Stockport", "SK1 3NL"),
    ("Blackpool", "FY1 1HP"), ("Preston", "PR1 2RA"),
    ("Chester", "CH2 3AD"), ("Shrewsbury", "SY1 1XH"),
    ("Canterbury", "CT1 1AA"), ("Chelmsford", "CM1 1LR"),
    ("Colchester", "CO1 1AA"), ("Ipswich", "IP1 1AA"),
    ("Cheltenham", "GL53 7HG"), ("Durham", "DH1 3AF"),
    # 北爱尔兰（BT 前缀）
    ("Londonderry", "BT47 6HB"), ("Derry", "BT47 6HB"),
    ("Lisburn", "BT28 3PN"), ("Newry", "BT34 2SF"),
    ("Armagh", "BT60 1AA"), ("Craigavon", "BT63 5RL"),
    ("Bangor", "BT20 5DL"), ("Newtownabbey", "BT36 6LL"),
    ("Carrickfergus", "BT38 7FG"), ("Larne", "BT40 1AA"),
    # 苏格兰补充
    ("Stirling", "FK8 1AA"), ("Dunfermline", "KY12 7AN"),
    ("Kirkcaldy", "KY1 1AH"), ("Ayr", "KA7 1SH"),
    ("Perth", "PH1 1AA"), ("Dumfries", "DG1 1AA"),
    ("Falkirk", "FK1 1AA"), ("Ripon", "HG4 1AA"),
    # 威尔士补充
    ("Wrexham", "LL11 1RE"), ("Merthyr Tydfil", "CF47 8UD"),
    ("Barry", "CF62 8HD"),
]

# ─── 英国 城市-郡-邮编 三元绑定表（地址闭合，防 city/county/postcode 矛盾）───
# 审核驱动：randomuser API 的 GB state/postcode 与城市不闭合（如 Westminster+Surrey+RY71、
# Stevenage+Herefordshire），RY/AY/TV 并非真实分配的 postcode area。
# 本表以 (city, county, postcode_area) 记录为单位取值，三者地理关系真实一致。
# 邮编只固化"区"(postcode area+digits，如 EX1)，后缀(2字母)程序随机生成，
# 避免撞上 large-user/delivery office/已停用邮编（如 EX1 1AA、LU1 1AA、GL1 1AA）。
_UK_ADDRESS_RECORDS = [
    # Exeter / Devon
    ("Exeter", "Devon", "EX1 2BP", "Clifton Road"),
    ("Exeter", "Devon", "EX1 2PS", "Ladysmith Road"),
    ("Exeter", "Devon", "EX1 3EG", "Ringswell Avenue"),
    ("Exeter", "Devon", "EX1 1BZ", "South Street"),
    ("Exeter", "Devon", "EX1 2QL", "Fore Street"),
    # Sheffield / South Yorkshire
    ("Sheffield", "South Yorkshire", "S1 4PF", "The Moor"),
    ("Sheffield", "South Yorkshire", "S1 4EU", "West Street"),
    ("Sheffield", "South Yorkshire", "S1 2PD", "Chapel Walk"),
    ("Sheffield", "South Yorkshire", "S1 2HE", "Fargate"),
    ("Sheffield", "South Yorkshire", "S1 4GF", "Division Street"),
    # Gloucester / Gloucestershire
    ("Gloucester", "Gloucestershire", "GL1 3HF", "London Road"),
    ("Gloucester", "Gloucestershire", "GL1 1DP", "Clarence Street"),
    ("Gloucester", "Gloucestershire", "GL1 4HR", "Barton Street"),
    ("Gloucester", "Gloucestershire", "GL1 2DP", "Southgate Street"),
    # Luton / Bedfordshire
    ("Luton", "Bedfordshire", "LU1 1LZ", "Dallow Road"),
    ("Luton", "Bedfordshire", "LU1 1RB", "Rothesay Road"),
    ("Luton", "Bedfordshire", "LU1 3RS", "Tennyson Road"),
    ("Luton", "Bedfordshire", "LU1 4DD", "Ross Way"),
    ("Luton", "Bedfordshire", "LU1 5EZ", "Hillborough Road"),
    # London / Greater London
    ("London", "Greater London", "SW1E 5HJ", "Bressenden Place"),
    ("London", "Greater London", "SW1P 2DY", "Great Peter Street"),
]


def _random_uk_address() -> tuple:
    """生成随机英国 城市+郡+邮编+街道 四元绑定记录（地址全闭合）

    每条记录经 Streetlist 公开数据核实：邮编当前在用、sector 真实分配、街道与邮编对应。
    返回 (city, county, postcode, street)，门牌号由调用方合理生成。
    """
    return random.choice(_UK_ADDRESS_RECORDS)

# 城市 → 邮编前缀映射（用于 API 返回未知城市时生成匹配邮编）
_CITY_POSTCODE_PREFIX = {
    "London": "SW", "Manchester": "M", "Birmingham": "B",
    "Liverpool": "L", "Leeds": "LS", "Glasgow": "G",
    "Edinburgh": "EH", "Bristol": "BS", "Sheffield": "S",
    "Newcastle": "NE", "Nottingham": "NG", "Southampton": "SO",
    "Portsmouth": "PO", "Brighton": "BN", "Oxford": "OX",
    "Cambridge": "CB", "Cardiff": "CF", "Belfast": "BT",
    "York": "YO", "Bath": "BA", "Leicester": "LE",
    "Coventry": "CV", "Reading": "RG", "Milton Keynes": "MK",
    "Wakefield": "WF", "Exeter": "EX", "Plymouth": "PL",
    "Derby": "DE", "Norwich": "NR", "Aberdeen": "AB",
    "Dundee": "DD", "Swansea": "SA", "Hull": "HU",
    "Sunderland": "SR", "Wolverhampton": "WV", "Stoke-on-Trent": "ST",
    "Bradford": "BD", "Luton": "LU", "Bournemouth": "BH",
    "Swindon": "SN", "Gloucester": "GL", "Worcester": "WR",
    "Newport": "NP", "Inverness": "IV", "Salford": "M",
    "City of London": "EC", "Falkirk": "FK",
    "Wigan": "WN", "Bolton": "BL", "Stockport": "SK",
    "Blackpool": "FY", "Preston": "PR", "Chester": "CH",
    "Shrewsbury": "SY", "Canterbury": "CT", "Chelmsford": "CM",
    "Colchester": "CO", "Ipswich": "IP", "Cheltenham": "GL",
    "Durham": "DH", "St Albans": "AL", "High Wycombe": "HP",
    "Maidstone": "ME", "Tunbridge Wells": "TN", "Guildford": "GU",
    "Reading": "RG", "Slough": "SL", "Luton": "LU",
    "Oxford": "OX", "Cambridge": "CB", "Milton Keynes": "MK",
    "Bedford": "MK", "Luton": "LU", "Northampton": "NN",
    "Peterborough": "PE", "Lincoln": "LN", "Grimsby": "DN",
    "Scunthorpe": "DN", "Huddersfield": "HD", "Halifax": "HX",
    "Rotherham": "S", "Doncaster": "DN", "Barnsley": "S",
    # 北爱尔兰
    "Londonderry": "BT", "Derry": "BT", "Lisburn": "BT",
    "Newry": "BT", "Armagh": "BT", "Craigavon": "BT",
    "Bangor": "BT", "Newtownabbey": "BT", "Carrickfergus": "BT", "Larne": "BT",
    # 苏格兰补充
    "Stirling": "FK", "Dunfermline": "KY", "Kirkcaldy": "KY",
    "Ayr": "KA", "Perth": "PH", "Dumfries": "DG",
    "Falkirk": "FK", "Ripon": "HG",
    # 威尔士补充
    "Wrexham": "LL", "Merthyr Tydfil": "CF", "Barry": "CF",
}

_UK_STREET_NAMES = [
    "George Street", "King Street", "Queen Street", "High Street",
    "Church Road", "London Road", "Park Road", "Station Road",
    "Mill Road", "Oxford Street", "Victoria Street", "Albert Road",
    "Edward Street", "Charles Street", "James Street", "William Street",
]


def _ph_date(date_str: str) -> str:
    """YYYY-MM-DD → '01 APR 2026'（MariBank 菲律宾账单日期格式）"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.day:02d} {_MONTHS_SHORT[dt.month - 1].upper()} {dt.year}"


def _ph_period_display(start_str: str, end_str: str) -> str:
    """生成 '01 MAR 2026 to 31 MAR 2026' 格式的账期显示"""
    return f"{_ph_date(start_str)} to {_ph_date(end_str)}"


# ─── 英国地址簿（street + postcode + city 三元绑定） ───
# 第七轮审核 P0：gb-kraken 地址 street/postcode 不匹配。
# postcodes.io 验证有效性，街道-邮编配对来自公开可查的知名地址。
# 结构：城市 → [(街道, 邮编), ...]
_UK_ADDRESS_BOOK = {
    "London": [
        ("Whitehall", "SW1A 2AA"),          # 10 Downing Street (St James's ward)
        ("Baker Street", "NW1 6XE"),         # Sherlock Holmes Museum (Regent's Park ward)
    ],
    "Edinburgh": [("Princes Street", "EH2 2EQ")],       # 市中心商业街 (City Centre ward)
    "Manchester": [("Oxford Road", "M13 9PL")],         # 曼大附近 (Hulme ward)
    "Birmingham": [("New Street", "B2 4JQ")],            # 市中心 (Ladywood ward)
    "Liverpool": [("Castle Street", "L2 9SQ")],          # 市政厅 (City Centre North ward)
    "Leeds": [("Park Row", "LS1 4AZ")],                  # 金融区 (Beeston & Holbeck ward)
    "Glasgow": [("Buchanan Street", "G1 3JX")],         # 购物街 (Anderston/City ward)
    "Sheffield": [("Fargate", "S1 2BJ")],                # 步行区 (City ward)
    "Newcastle": [("Grey Street", "NE1 5DF")],            # Grey's Monument (Monument ward)
    "Nottingham": [("Old Market Square", "NG1 2DT")],     # 市政广场 (Castle ward)
    "Cambridge": [("Trumpington Street", "CB2 1AG")],    # King's College (Market ward)
    "Oxford": [("Broad Street", "OX1 3BG")],             # Bodleian Library (Carfax & Jericho ward)
    "Cardiff": [("Queen Street", "CF10 2HQ")],            # 购物街 (Cathays ward)
    "Belfast": [("Royal Avenue", "BT1 4DA")],            # 市中心 (Central ward)
    "Bath": [("Westgate Street", "BA1 1QE")],            # 市中心 (Kingsmead ward)
    "Durham": [("North Road", "DH1 4RQ")],               # 火车站附近 (Neville's Cross ward)
}


def _random_uk_book_address() -> tuple:
    """从英国地址簿抽取整条记录：(城市, 街道(含门牌), 邮编)

    供 gb-kraken 使用；街道+邮编在簿内已绑定地理一致性，
    杜绝随机拼接产生的不匹配。
    注意：勿与本文件上方 _random_uk_address()（四元含郡，
    供 gb-wisegbpstatementuk 使用）混淆——两者服务不同模板。
    """
    city = random.choice(list(_UK_ADDRESS_BOOK.keys()))
    street, postcode = random.choice(_UK_ADDRESS_BOOK[city])
    house = random.randint(1, 48)
    return city, f"{house} {street}", postcode


def _random_uk_postcode() -> str:
    """生成随机英国邮编（从配对表选取，确保与城市匹配）"""
    return random.choice(_CITY_POSTCODES_GB)[1]


def _random_uk_city_postcode() -> tuple:
    """生成随机英国城市+邮编配对"""
    return random.choice(_CITY_POSTCODES_GB)


# ─── 德国城市-邮编配对表 ───

_CITY_POSTCODES_DE = [
    ("Berlin", "10115"), ("München", "80331"), ("Hamburg", "20095"),
    ("Frankfurt am Main", "60311"), ("Köln", "50667"), ("Stuttgart", "70173"),
    ("Düsseldorf", "40210"), ("Leipzig", "04109"), ("Dortmund", "44135"),
    ("Essen", "45127"), ("Bremen", "28195"), ("Dresden", "01067"),
    ("Hannover", "30159"), ("Nürnberg", "90402"), ("Bochum", "44787"),
    ("Bonn", "53111"), ("Münster", "48143"), ("Mannheim", "68159"),
    ("Karlsruhe", "76131"), ("Augsburg", "86150"), ("Wiesbaden", "65183"),
    ("Aachen", "52062"), ("Braunschweig", "38100"), ("Kiel", "24103"),
    ("Chemnitz", "09111"), ("Halle (Saale)", "06108"), ("Magdeburg", "39104"),
    ("Freiburg", "79098"), ("Mainz", "55116"), ("Erfurt", "99084"),
    ("Kassel", "34117"), ("Trier", "54290"), ("Jena", "07743"),
    ("Göttingen", "37073"), ("Heidelberg", "69115"), ("Regensburg", "93047"),
    # 以下为 randomuser.me API 常见德国城市（审核报告逐一确认）
    ("Kirn", "55606"),
    ("Borgholzhausen", "33829"),
    ("Leutershausen", "91578"),
    ("Neustadt (Dosse)", "16845"),
    ("Lingen (Ems)", "49808"),
    ("Bad Gandersheim", "37581"),
    ("Heimbach", "52396"),
    ("Eilenburg", "04838"),
    ("Saarbrücken", "66111"), ("Potsdam", "14467"), ("Rostock", "18055"),
    ("Flensburg", "24937"), ("Krefeld", "47798"), ("Mönchengladbach", "41061"),
    ("Oberhausen", "46045"), ("Hagen", "58095"), ("Hamm", "59065"),
    ("Solingen", "42651"), ("Leverkusen", "51371"), ("Ludwigshafen", "67059"),
    ("Osnabrück", "49074"), ("Oldenburg", "26122"), ("Wuppertal", "42275"),
    ("Bielefeld", "33602"), ("Münster", "48143"), ("Gelsenkirchen", "45879"),
    ("Duisburg", "47051"), ("Herne", "44623"), ("Neuss", "41460"),
    ("Paderborn", "33098"), ("Würzburg", "97070"), ("Ulm", "89073"),
    ("Ingolstadt", "85049"), ("Fürth", "90762"), ("Bamberg", "96047"),
    ("Heilbronn", "74072"), ("Pforzheim", "75172"), ("Reutlingen", "72764"),
    ("Koblenz", "56068"), ("Cottbus", "03046"), ("Görlitz", "02826"),
    ("Stralsund", "18439"), ("Greifswald", "17489"), ("Schwerin", "19053"),
    ("Weimar", "99423"), ("Gera", "07545"), ("Zwickau", "08056"),
    ("Plauen", "08523"), ("Dessau", "06844"),
    # 审核报告中发现的城市（确保邮编与官方一致）
    ("Gersthofen", "86368"), ("Vöhrenbach", "78147"),
    ("Wolfratshausen", "82515"), ("Kamenz", "01917"),
    ("Freystadt", "92342"), ("Norderney", "26548"),
    ("Liebenwalde", "16559"), ("Trochtelfingen", "72818"),
    ("Kleve", "47533"), ("Friesoythe", "26169"),
    ("Burglengenfeld", "93133"), ("Neustadt an der Waldnaab", "92660"),
]

# 德国城市 → 联邦州映射
_DE_CITY_STATE = {
    "Berlin": "Berlin", "München": "Bayern", "Hamburg": "Hamburg",
    "Frankfurt am Main": "Hessen", "Köln": "Nordrhein-Westfalen",
    "Stuttgart": "Baden-Württemberg", "Düsseldorf": "Nordrhein-Westfalen",
    "Leipzig": "Sachsen", "Dortmund": "Nordrhein-Westfalen",
    "Essen": "Nordrhein-Westfalen", "Bremen": "Bremen",
    "Dresden": "Sachsen", "Hannover": "Niedersachsen",
    "Nürnberg": "Bayern", "Bochum": "Nordrhein-Westfalen",
    "Bonn": "Nordrhein-Westfalen", "Münster": "Nordrhein-Westfalen",
    "Mannheim": "Baden-Württemberg", "Karlsruhe": "Baden-Württemberg",
    "Augsburg": "Bayern", "Wiesbaden": "Hessen",
    "Aachen": "Nordrhein-Westfalen", "Braunschweig": "Niedersachsen",
    "Kiel": "Schleswig-Holstein", "Chemnitz": "Sachsen",
    "Halle (Saale)": "Sachsen-Anhalt", "Magdeburg": "Sachsen-Anhalt",
    "Freiburg": "Baden-Württemberg", "Mainz": "Rheinland-Pfalz",
    "Erfurt": "Thüringen", "Kassel": "Hessen",
    "Trier": "Rheinland-Pfalz", "Jena": "Thüringen",
    "Göttingen": "Niedersachsen", "Heidelberg": "Baden-Württemberg",
    "Regensburg": "Bayern",
    # 审核确认的 randomuser.me 常见城市
    "Kirn": "Rheinland-Pfalz",
    "Borgholzhausen": "Nordrhein-Westfalen",
    "Leutershausen": "Bayern",
    "Neustadt (Dosse)": "Brandenburg",
    "Lingen (Ems)": "Niedersachsen",
    "Bad Gandersheim": "Niedersachsen",
    "Heimbach": "Nordrhein-Westfalen",
    "Eilenburg": "Sachsen",
    "Saarbrücken": "Saarland", "Potsdam": "Brandenburg", "Rostock": "Mecklenburg-Vorpommern",
    "Flensburg": "Schleswig-Holstein", "Krefeld": "Nordrhein-Westfalen",
    "Mönchengladbach": "Nordrhein-Westfalen", "Oberhausen": "Nordrhein-Westfalen",
    "Hagen": "Nordrhein-Westfalen", "Hamm": "Nordrhein-Westfalen",
    "Solingen": "Nordrhein-Westfalen", "Leverkusen": "Nordrhein-Westfalen",
    "Ludwigshafen": "Rheinland-Pfalz", "Osnabrück": "Niedersachsen",
    "Oldenburg": "Niedersachsen", "Wuppertal": "Nordrhein-Westfalen",
    "Bielefeld": "Nordrhein-Westfalen", "Gelsenkirchen": "Nordrhein-Westfalen",
    "Duisburg": "Nordrhein-Westfalen", "Herne": "Nordrhein-Westfalen",
    "Neuss": "Nordrhein-Westfalen", "Paderborn": "Nordrhein-Westfalen",
    "Würzburg": "Bayern", "Ulm": "Baden-Württemberg",
    "Ingolstadt": "Bayern", "Fürth": "Bayern", "Bamberg": "Bayern",
    "Heilbronn": "Baden-Württemberg", "Pforzheim": "Baden-Württemberg",
    "Reutlingen": "Baden-Württemberg", "Koblenz": "Rheinland-Pfalz",
    "Cottbus": "Brandenburg", "Görlitz": "Sachsen",
    "Stralsund": "Mecklenburg-Vorpommern", "Greifswald": "Mecklenburg-Vorpommern",
    "Schwerin": "Mecklenburg-Vorpommern", "Weimar": "Thüringen",
    "Gera": "Thüringen", "Zwickau": "Sachsen", "Plauen": "Sachsen",
    "Dessau": "Sachsen-Anhalt",
}

# ─── 德国街道-城市-门牌表 ───
# 结构：城市 → [(街道名, 邮编, 门牌上限), ...]
# 街道绑定城区邮编，门牌上限为合理范围，避免「随机街道+三位数门牌」冲突。
# 审计核实：Bochum Lindenstraße → 44869 Höntrop, 1-43；Dortmund Unter den Linden → 44289 Sölde, 1-24。
_DE_STREETS_BY_CITY = {
    "Berlin": [("Friedrichstraße", "10117", 50), ("Unter den Linden", "10117", 68), ("Karl-Liebknecht-Straße", "10178", 60), ("Torstraße", "10119", 100)],
    "München": [("Kaufingerstraße", "80331", 60), ("Sendlinger Straße", "80331", 80), ("Schellingstraße", "80333", 60), ("Sonnenstraße", "80331", 70)],
    "Hamburg": [("Mönckebergstraße", "20095", 29), ("Spitalerstraße", "20095", 50), ("Reeperbahn", "20359", 120), ("Alsterarkaden", "20354", 30)],
    "Frankfurt am Main": [("Zeil", "60313", 120), ("Kaiserstraße", "60311", 100), ("Goethestraße", "60313", 60), ("Schillerstraße", "60313", 50)],
    "Köln": [("Schildergasse", "50667", 80), ("Hohe Straße", "50667", 60), ("Ehrenstraße", "50672", 70), ("Breite Straße", "50667", 50)],
    "Stuttgart": [("Königstraße", "70173", 100), ("Calwer Straße", "70173", 60), ("Hauptstätter Straße", "70173", 80), ("Rotebühlstraße", "70178", 120)],
    "Düsseldorf": [("Schadowstraße", "40212", 80), ("Königsallee", "40212", 100), ("Flinger Straße", "40213", 60), ("Friedrichstraße", "40217", 70)],
    "Leipzig": [("Käthe-Kollwitz-Straße", "04109", 46), ("Grimmaische Straße", "04109", 50), ("Hainstraße", "04109", 40), ("Karl-Liebknecht-Straße", "04107", 50)],
    "Dortmund": [("Westenhellweg", "44135", 60), ("Saarlandstraße", "44137", 80), ("Hansastraße", "44137", 70), ("Kaiserstraße", "44135", 80), ("Unter den Linden", "44289", 24), ("Rheinische Straße", "44137", 120)],
    "Essen": [("Kettwiger Straße", "45127", 60), ("Limbecker Straße", "45127", 80), ("Rüttenscheider Straße", "45130", 120)],
    "Bremen": [("Sögestraße", "28195", 60), ("Obernstraße", "28195", 40), ("Schlachte", "28195", 40), ("Am Wall", "28195", 80)],
    "Dresden": [("Prager Straße", "01069", 17), ("Hauptstraße", "01097", 60), ("Neustädter Markt", "01097", 30), ("Bautzner Straße", "01099", 120)],
    "Hannover": [("Georgstraße", "30159", 60), ("Bahnhofstraße", "30159", 50), ("Karmarschstraße", "30159", 70), ("Lister Meile", "30161", 100)],
    "Nürnberg": [("Königstraße", "90402", 80), ("Karolinenstraße", "90402", 60), ("Ludwigstraße", "90402", 50), ("Breite Gasse", "90402", 40)],
    "Bochum": [("Kortumstraße", "44787", 60), ("Bongardstraße", "44787", 40), ("Huestraße", "44787", 34), ("Massenbergstraße", "44787", 40), ("Lindenstraße", "44869", 43), ("Universitätsstraße", "44789", 125)],
    "Bonn": [("Bonner Talweg", "53113", 80), ("Maxstraße", "53111", 50), ("Sternstraße", "53111", 40), ("Prinz-Albert-Straße", "53115", 40)],
    "Münster": [("Prinzipalmarkt", "48143", 40), ("Ludgeristraße", "48143", 60), ("Salzstraße", "48143", 50), ("Aegidiistraße", "48143", 40)],
    "Mannheim": [("Kunststraße", "68159", 50), ("Planken", "68161", 80), ("Friedrichstraße", "68199", 70), ("Augustaanlage", "68165", 100)],
    "Karlsruhe": [("Kaiserstraße", "76133", 100), ("Karlstraße", "76133", 60), ("Ettlinger Straße", "76137", 67), ("Waldstraße", "76133", 70)],
    "Augsburg": [("Maximilianstraße", "86150", 60), ("Annastraße", "86150", 50), ("Bahnhofstraße", "86150", 70), ("Gögginger Straße", "86199", 120)],
    "Aachen": [("Krämerstraße", "52062", 50), ("Großkölnstraße", "52062", 60), ("Adalbertstraße", "52062", 40), ("Pontstraße", "52062", 70)],
    "Kiel": [("Holstenstraße", "24103", 60), ("Dänische Straße", "24103", 50), ("Sofienstraße", "24103", 40), ("Ringstraße", "24114", 80)],
    "Braunschweig": [("Bohlweg", "38100", 60), ("Schuhstraße", "38100", 50), ("Hutfiltern", "38100", 40), ("Hagenmarkt", "38100", 13)],
    "Saarbrücken": [("Bahnhofstraße", "66111", 80), ("Kaiserstraße", "66111", 60), ("Fahrstraße", "66111", 50), ("St. Johanner Straße", "66111", 70)],
    "Potsdam": [("Brandenburger Straße", "14467", 80), ("Friedrich-Ebert-Straße", "14469", 60), ("Am Kanal", "14467", 10)],
    "Rostock": [("Kröpeliner Straße", "18055", 80), ("Lange Straße", "18055", 60), ("Am Strom", "18119", 40)],
    "Bielefeld": [("Bahnhofstraße", "33602", 18), ("Niedernstraße", "33602", 50), ("August-Bebel-Straße", "33602", 70)],
    "Würzburg": [("Kaiserstraße", "97070", 60), ("Schönbornstraße", "97070", 50), ("Bahnhofstraße", "97070", 40)],
    "Ulm": [("Hirschstraße", "89073", 60), ("Bahnhofstraße", "89073", 50), ("Münchner Straße", "89073", 70)],
    "Heidelberg": [("Hauptstraße", "69117", 120), ("Bergheimer Straße", "69115", 100), ("Sofienstraße", "69115", 60)],
    "Mainz": [("Augustinerstraße", "55116", 60), ("Bahnhofstraße", "55116", 50), ("Große Bleiche", "55116", 70)],
    "Freiburg": [("Kaiser-Joseph-Straße", "79098", 60), ("Bertoldstraße", "79098", 50), ("Günterstalstraße", "79102", 80)],
    "Regensburg": [("Kaiserstraße", "93047", 60), ("Gesandtenstraße", "93047", 50), ("Bahnhofstraße", "93047", 18)],
}

# 通用德国街道名（几乎每个德国城镇都有，仅用于 fallback 路径）
_DE_GENERIC_STREETS = [
    "Hauptstraße", "Bahnhofstraße", "Schulstraße", "Kirchstraße",
    "Parkstraße", "Gartenstraße", "Marktstraße", "Rathausstraße",
    "Bergstraße", "Mühlenstraße",
]


def _random_de_address() -> tuple:
    """生成随机德国地址：(城市, 邮编, 门牌号, 街道名, 联邦州)

    优先从街道簿 _DE_STREETS_BY_CITY 取（城市+街道+邮编+门牌范围绑定）；
    表外城市使用通用街道名 + 城市中心邮编 + 门牌 1-120（避免三位数）。
    """
    if _DE_STREETS_BY_CITY:
        city = random.choice(list(_DE_STREETS_BY_CITY.keys()))
        street, postcode, house_max = random.choice(_DE_STREETS_BY_CITY[city])
        house = random.randint(1, house_max)
    else:
        city, postcode = random.choice(_CITY_POSTCODES_DE)
        street = random.choice(_DE_GENERIC_STREETS)
        house = random.randint(1, 120)
    state = _DE_CITY_STATE.get(city, "")
    return city, postcode, house, street, state


def _random_de_city_postcode() -> tuple:
    """生成随机德国城市+邮编配对（供旧调用方保留，新代码请用 _random_de_address）"""
    return random.choice(_CITY_POSTCODES_DE)


# ─── 菲律宾地址簿（street + barangay + postcode 三元绑定） ───
# 第四轮审核发现：三个词库独立随机拼接会产生真实地理冲突（如 Sct. Borromeo 实际属
# South Triangle 而非 Commonwealth；358 Quirino Ave 公开记录在 Don Galo）。
# 故改为整条地址记录制：每条 (街道, Barangay, 邮编) 都是一条现实一致的真实组合，
# 来源为审核引用的政府/商业公开资料与广泛可查的机构地址，不再独立采样。
# 结构：城市 → [(街道, Barangay, 邮编), ...]
_PH_ADDRESS_BOOK = {
    "Quezon City": [
        ("Sct. Borromeo", "Barangay South Triangle", "1103"),      # DPWH/BIR 公开资料
        ("Quezon Avenue", "Barangay Bagong Pag-asa", "1105"),      # QC 政府图书馆资料确认邮编
        ("Commonwealth Avenue", "Barangay Commonwealth", "1121"),
        ("Times Street", "Barangay West Triangle", "1104"),
        ("Tandang Sora Avenue", "Barangay Culiat", "1128"),
    ],
    "Manila": [
        ("Taft Avenue", "Barangay 664", "1000"),                   # Ermita 区
        ("Rizal Avenue", "Barangay 306", "1003"),                  # Santa Cruz 区
        ("Mabini Street", "Barangay 706", "1004"),                 # Malate 区
    ],
    "Makati": [
        ("Ayala Avenue", "Barangay Bel-Air", "1209"),
        ("Makati Avenue", "Barangay Poblacion", "1210"),
    ],
    "Pasig": [
        ("Julia Vargas Avenue", "Barangay San Antonio", "1605"),   # Ortigas 中心 Pasig 侧
        ("Shaw Boulevard", "Barangay Oranbo", "1600"),
    ],
    "Mandaluyong": [
        ("Shaw Boulevard", "Barangay Plainview", "1550"),
        ("EDSA", "Barangay Wack-Wack", "1550"),
    ],
    "Pasay": [
        ("Roxas Boulevard", "Barangay 76", "1300"),
        ("Taft Avenue", "Barangay 33", "1300"),
    ],
    "Parañaque": [
        ("Quirino Avenue", "Barangay Don Galo", "1700"),           # 审核引用 M Lhuillier 分支目录
        ("Dr. A. Santos Avenue", "Barangay San Isidro", "1700"),
    ],
    "Las Piñas": [
        ("Alabang-Zapote Road", "Barangay Pulang Lupa", "1740"),
    ],
    "Muntinlupa": [
        ("National Road", "Barangay Putatan", "1770"),
    ],
    "Caloocan": [
        ("C-3 Road", "Barangay 22", "1400"),                       # 审核引用 Brgy 22 街道名录
        ("Dagat-Dagatan Avenue", "Barangay 22", "1400"),           # 同上来源
        ("Samson Road", "Barangay 24", "1400"),
    ],
    "Malabon": [
        ("Letre Road", "Barangay Longos", "1470"),
    ],
    "Navotas": [
        ("North Bay Boulevard", "Barangay North Bay Blvd. South", "1480"),
    ],
    "Valenzuela": [
        ("MacArthur Highway", "Barangay Karuhatan", "1440"),
    ],
    "Marikina": [
        ("Sumulong Highway", "Barangay Barangka", "1800"),
        ("J. P. Rizal Street", "Barangay San Roque", "1800"),
    ],
    "San Juan": [
        ("Ortigas Avenue", "Barangay Progreso", "1500"),
        ("Pinaglabanan Street", "Barangay Corazon de Jesus", "1500"),
    ],
    "Cebu City": [
        ("Colon Street", "Barangay Santo Niño", "6000"),
        ("Osmeña Boulevard", "Barangay Capitol Site", "6000"),
    ],
    "Davao City": [
        ("Rizal Street", "Barangay Poblacion", "8000"),
        ("Ponciano Street", "Barangay Poblacion", "8000"),
    ],
    "Bacolod": [
        ("Lacson Street", "Barangay Villamonte", "6100"),
    ],
    "Iloilo City": [
        ("Diversion Road", "Barangay San Rafael, Mandurriao", "5000"),  # 能源部/Maya 渠道资料
        ("General Luna Street", "Barangay Molo", "5000"),
    ],
    "Angeles City": [
        ("Fields Avenue", "Barangay Balibago", "2009"),
        ("MacArthur Highway", "Barangay Balibago", "2009"),
    ],
    "Baguio": [
        ("Session Road", "Barangay Session Road Area", "2600"),
        ("Magsaysay Avenue", "Barangay SLU-SVP Village", "2600"),
    ],
    "Naga": [
        ("Elias Angeles Street", "Barangay Dinaga", "4400"),
    ],
}


def _random_ph_city_street() -> tuple:
    """从地址簿抽取一条完整的菲律宾地址记录：(城市, 街道, 邮编, Barangay)

    三元组在簿内已绑定地理一致性，杜绝 street/barangay/postcode 独立随机拼接。
    """
    city = random.choice(list(_PH_ADDRESS_BOOK.keys()))
    street, barangay, postcode = random.choice(_PH_ADDRESS_BOOK[city])
    return city, street, postcode, barangay


def _gen_be_iban(bank_code: str = "967") -> str:
    """生成合规比利时 IBAN

    比利时 BBAN 结构（SWIFT IBAN Registry）: 3位银行码 + 7位账号 + 2位国内校验位
      - 国内校验位(第15-16位) = (银行码+账号 共10位) mod 97，结果两位（不足补0）
      - 国际校验位(第3-4位)   = 标准 MOD-97 算法：98 - (IBAN去掉前4位并前置BE00编码) mod 97
    返回分组格式: BE XX XXXX XXXX XXXX

    Args:
        bank_code: 比利时 3 位银行码。
            Wise Europe SA (BIC TRWIBEB1) → "967"（默认）
            PPS EU SA (BIC PESOBEB1) → 见 DE_MONESE_BE_BANK_CODE 常量
    """
    account = "".join(random.choices(string.digits, k=7))
    bban = bank_code + account
    # 国内校验位（比利时规则：余数为0时校验位写97，不写00）
    domestic = int(bban) % 97
    if domestic == 0:
        domestic = 97
    bban_full = bban + str(domestic).zfill(2)
    # 国际校验位（BE00 → "111400"）
    n = int(bban_full + "111400")
    check = 98 - (n % 97)
    check_str = str(check).zfill(2)
    return f"BE{check_str} {bban_full[:4]} {bban_full[4:8]} {bban_full[8:12]}"


# 会话级已用 Monese ID 集合（防止跨样本冲突）
_USED_MONESE_IDS = set()


def _gen_monese_id() -> str:
    """生成独立 Monese ID（M 前缀 + 8 位数字，不与 IBAN 账户号关联）

    真实 Monese EUR 对账单的 Monese ID 以 M 开头 + 8 位数字，
    是独立于 IBAN 账户号的标识符。
    样本：M67748970、M49841099（来自真实对账单截图核实）
    """
    while True:
        mid = "M" + "".join(random.choices(string.digits, k=8))
        if mid not in _USED_MONESE_IDS:
            _USED_MONESE_IDS.add(mid)
            return mid




def _gen_uuid() -> str:
    """生成 UUID 格式的参考号（如 6b94c41e-1234-5678-9abc-def012345678）"""
    import uuid
    return str(uuid.uuid4())


def get_field_defaults(bt_code: str) -> dict:
    """根据账单类型返回默认字段值"""
    defaults = {}
    now = datetime.now()
    last_month = now.replace(day=1) - timedelta(days=1)
    month_start = last_month.replace(day=1)
    month_end = last_month

    # 随机金额（非整百整千，增加真实感）
    opening = round(random.uniform(800, 15000), 2)
    credits = round(random.uniform(300, 6000), 2)
    debits = round(random.uniform(300, 6000), 2)

    # 随机英国地址（城市与邮编配对，不会出现 Brighton + ZG1 这种不匹配）
    city, postcode = _random_uk_city_postcode()
    defaults["customer_name"] = f"{random.choice(_UK_FIRST_NAMES)} {random.choice(_UK_LAST_NAMES)}".upper()
    defaults["address_unit"] = random.choice(["Flat 3", "Flat 7", "Apt 12", "Suite 5", "Flat 1A"])
    defaults["address_street"] = f"{random.randint(1, 200)} {random.choice(_UK_STREET_NAMES)}"
    defaults["address_district"] = city
    defaults["postal_code"] = postcode
    defaults["country"] = "United Kingdom"
    defaults["period_start"] = month_start.strftime("%Y-%m-%d")
    defaults["period_end"] = month_end.strftime("%Y-%m-%d")
    defaults["issue_date"] = now.strftime("%Y-%m-%d")
    defaults["opening_balance"] = f"{opening:.2f}"
    defaults["closing_balance"] = f"{opening + credits - debits:.2f}"
    defaults["total_credits"] = f"{credits:.2f}"
    defaults["total_debits"] = f"{debits:.2f}"

    if bt_code == "gb-monzo":
        sort_code = _get_bank_sort_code("gb-monzo")  # 04-00-04
        acct_no = _gen_monzo_account_number()  # 通过 VocaLink DBLAL 国内校验
        defaults.update({
            "sort_code": sort_code, "bic": _get_bank_bic("gb-monzo"),
            "iban": _gen_uk_iban(_get_bank_iban_code("gb-monzo"), sort_code, acct_no),
            "account_number": acct_no,
            "balance_pots": f"{round(random.uniform(100, 5000), 2):.2f}",
            "total_outgoings": f"{debits:.2f}",
            "total_deposits": f"{credits:.2f}",
            # 真实 Monzo 样本账期显示为 DD/MM/YYYY（模板展示用，交易生成仍解析 ISO）
            "period_display": f"{month_start.strftime('%d/%m/%Y')} - {month_end.strftime('%d/%m/%Y')}",
        })
    elif bt_code == "de-wise":
        # Wise EUR（德国客户）→ Wise Europe SA（比利时实体）
        de_city, de_postcode, de_house, de_road, de_state = _random_de_address()
        de_street = f"{de_road} {de_house}"
        defaults.update({
            "wise_currency": "EUR",
            "wise_iban": _gen_be_iban(),           # 比利时 IBAN
            "wise_bic": "TRWIBEB1XXX",               # Wise Europe SA BIC
            "wise_city": de_city,                   # 德国城市
            "wise_state": de_state,                 # 联邦州
            "wise_postcode": de_postcode,           # 街道所属城区邮编
            "wise_country": "Germany",
            "wise_balance": f"{round(random.uniform(2000, 20000), 2):.2f}",
            "wise_ref": _gen_uuid(),
            "wise_timezone": _eu_offset_label(month_start + (month_end - month_start) / 2),
            "wise_period_start": month_start.strftime("%Y-%m-%d"),
            "wise_period_end": month_end.strftime("%Y-%m-%d"),
            "wise_balance_date": month_end.strftime("%Y-%m-%d"),
            "wise_generated_date": now.strftime("%Y-%m-%d"),
            # 通用地址字段也设为德国
            "address_district": de_city,
            "address_street": de_street,
            "postal_code": de_postcode,
            "country": "Germany",
        })

    elif bt_code == "gb-wisegbpstatementuk":
        # Wise GBP（英国客户）→ Wise Payments Ltd（英国实体）
        # 地址用 城市-郡-邮编 三元绑定表（闭合），禁止 randomuser API 覆盖
        # （审核驱动：API 的 GB state/postcode 与城市不闭合，RY/AY/TV 非真实 postcode area）
        wise_sort = _get_bank_sort_code(bt_code)  # 23-14-70
        wise_acct = _gen_uk_account_number()
        gb_city, gb_county, gb_postcode, gb_street = _random_uk_address()
        defaults.update({
            "wise_currency": "GBP",
            "wise_iban": _gen_uk_iban(_get_bank_iban_code(bt_code), wise_sort, wise_acct),
            "wise_bic": _get_bank_bic(bt_code),  # TRWIGB2L
            "wise_city": gb_city,
            "wise_state": gb_county,
            "wise_postcode": gb_postcode,
            "wise_country": "United Kingdom",
            "wise_balance": f"{round(random.uniform(2000, 20000), 2):.2f}",
            "wise_ref": _gen_uuid(),
            "wise_timezone": "UTC",
            # 通用地址字段与 wise 地址同源（同一四元记录），街道+邮编+城市+郡全闭合
            "address_district": gb_city,
            "address_street": f"{random.randint(1, 80)} {gb_street}",
            "postal_code": gb_postcode,
            "country": "United Kingdom",
            "account_number": wise_acct, "sort_code": wise_sort,
            "wise_period_start": month_start.strftime("%Y-%m-%d"),
            "wise_period_end": month_end.strftime("%Y-%m-%d"),
            "wise_balance_date": month_end.strftime("%Y-%m-%d"),  # 账期截止日，不是生成日期
            "wise_generated_date": now.strftime("%Y-%m-%d"),
        })
    elif bt_code == "gb-kraken":
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        # Kraken Public ID 必须以 AA 开头，16位大写字母+数字
        kraken_pid = "AA" + "".join(random.choices(string.ascii_uppercase + string.digits, k=14))
        # balance_date 应为下月1日 00:00:00 UTC（不是当前日期）
        next_month_start = month_end + timedelta(days=1)
        defaults.update({
            "kraken_public_id": kraken_pid,
            "account_number": "K" + "".join(random.choices(string.digits, k=8)),
            "statement_month": month_start.strftime("%B %Y"),
            "balance_date": next_month_start.strftime("%Y-%m-%d") + " 00:00:00",
        })
        # 第七轮审核 P0：gb-kraken 地址 street/postcode 不匹配。
        # street 从通用池随机取、postcode 从城市池随机取，两者无地理绑定。
        # 改用 _UK_ADDRESS_BOOK 整条记录制（城市+街道+邮编绑定的真实地址对）。
        gb_city, gb_street, gb_postcode = _random_uk_book_address()
        defaults.update({
            "address_district": gb_city,
            "address_street": gb_street,
            "postal_code": gb_postcode,
        })
    elif bt_code == "gb-octopusenergybill":
        # Octopus 账单：供电/用量/费率等由服务端按账单模型生成，
        # 这里只提供基础字段（账期保持 ISO 格式，由服务转成英国显示格式）。
        defaults.update({
            "account_number": "A-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8)),
            "bill_number": "".join(random.choices(string.digits, k=9)),
            "previous_balance": f"{round(random.uniform(-3500, 2500), 2):.2f}",
        })
    elif bt_code == "ph-seabank":
        # MariBank 余额需覆盖全局范围，确保消费交易能在不透支的前提下生成。
        opening = round(random.uniform(*MARIBANK_OPENING_RANGE), 2)
        ph_city, ph_street, ph_postcode, ph_barangay = _random_ph_city_street()
        # 账期显示用账期首末日；签发日 = 账期结束后首日（下月 1 日），对齐真实 eStatement
        next_month_start = month_end + timedelta(days=1)
        defaults.update({
            "issue_date": next_month_start.strftime("%Y-%m-%d"),
            "opening_balance": f"{opening:.2f}",
            "closing_balance": f"{opening + credits - debits:.2f}",
            "account_number": "".join(random.choices(string.digits, k=MARIBANK_ACCOUNT_NO_LEN)),
            "bill_number": (
                MARIBANK_SN_PREFIX + "-"
                + month_end.strftime(MARIBANK_SN_DATE_FMT)
                + "".join(random.choices(string.ascii_uppercase, k=MARIBANK_SN_RANDOM_LEN))
            ),
            "pdic_coverage": f"{PDIC_COVERAGE_LIMIT:,.2f}",
            "bank_head_office": MARIBANK_HEAD_OFFICE,
            "contact_email": MARIBANK_CONTACT_EMAIL,
            "interest_effective_date": MARIBANK_INTEREST_EFFECTIVE_DATE,
            "interest_rate_display": f"{MARIBANK_INTEREST_RATE_ANNUAL * 100:.2f}%",
            "interest_rate_high_display": f"{MARIBANK_INTEREST_RATE_HIGH * 100:.2f}%",
            "interest_tax_rate_display": f"{MARIBANK_INTEREST_TAX_RATE * 100:.0f}%",
            "pdic_limit_display": f"{PDIC_COVERAGE_LIMIT:,.2f}",
            # 利息公式 illustrative example（按 ₱1,000,000 × 3.25% ÷ 365 推导，对齐公开样本）
            "interest_example_balance": f"{float(MARIBANK_HIGH_TIER_THRESHOLD):,.2f}",
            "interest_example_gross": f"{round(MARIBANK_HIGH_TIER_THRESHOLD * MARIBANK_INTEREST_RATE_ANNUAL / 365, 2):,.2f}",
            "interest_example_wt": f"{round(MARIBANK_HIGH_TIER_THRESHOLD * MARIBANK_INTEREST_RATE_ANNUAL / 365 * MARIBANK_INTEREST_TAX_RATE, 2):,.2f}",
            "interest_example_net": f"{round(MARIBANK_HIGH_TIER_THRESHOLD * MARIBANK_INTEREST_RATE_ANNUAL / 365 * (1 - MARIBANK_INTEREST_TAX_RATE), 2):,.2f}",
            # 显示格式字段：账期与签发日（对齐真实 2026 样本）
            "period_display": _ph_period_display(
                month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d")),
            "issue_date_display": _ph_date(next_month_start.strftime("%Y-%m-%d")),
            "address_district": ph_city,
            "address_street": f"{random.randint(1, 999)} {ph_street}",
            "address_barangay": ph_barangay,
            "postal_code": ph_postcode,
            "country": "Philippines",
        })
    elif bt_code == "de-monese":
        # Monese 德国客户：使用德国城市-街道-门牌绑定地址
        de_city, de_postcode, de_house, de_road, de_state = _random_de_address()
        de_street = f"{de_road} {de_house}"
        monese_acct = _gen_uk_account_number()
        defaults.update({
            # EEA 客户（德国）→ PPS EU SA（比利时 EMI 实体）：
            # 使用 BE IBAN + PESOBEB1，而非 UK 实体的 GB IBAN + MNEEGB21（Monese IBAN 显示不带空格）
            "iban": _gen_be_iban(DE_MONESE_BE_BANK_CODE).replace(" ", ""),
            "bic": _get_bank_bic("de-monese"),  # PESOBEB1
            "account_number": monese_acct,
            "monese_id": _gen_monese_id(),      # 独立 M 前缀 ID（指纹③）
            "statement_period": f"{month_start.day:02d} {_MONTHS_FULL[month_start.month - 1]} {month_start.year} - {month_end.day:02d} {_MONTHS_FULL[month_end.month - 1]} {month_end.year}",
            # 德国地址（对齐真实样本：姓名/街道门牌/联邦州/邮编/城市/国家）
            "address_street": de_street,
            "address_state": de_state,
            "postal_code": de_postcode,
            "address_district": de_city,
            "country": "Germany",
            # 指纹④方案B：不再预设 total_credits/debits/closing_balance，
            # 全部由交易自然生成后反推（清空继承的上层默认值）
            "total_credits": "0.00",
            "total_debits": "0.00",
            "closing_balance": "0.00",
        })
    return defaults

_GB_OCTOPUS_STREETS = {
    "Bradford": [("Victoria Road", "BD18 3HQ", 50)],
    "Chelmsford": [("Inchbonnie Road", "CM3 5GE", 50)],
    "Chichester": [("Gribble Lane", "PO20 2AE", 50)],
    "Ipswich": [("Angus Close", "IP4 3EL", 50), ("Bostock Road", "IP2 8LP", 50)],
    "Leeds": [("Silk Mill Way", "LS16 6RN", 50)],
    "Leicester": [("Bloomfield Road", "LE2 6LD", 50)],
    "Liverpool": [("Fieldton Road", "L11 9AE", 50)],
    "Oxford": [("Barns Road", "OX4 3RA", 50), ("Dene Road", "OX3 7EE", 50)],
}