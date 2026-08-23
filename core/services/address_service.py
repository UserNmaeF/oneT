# -*- coding: utf-8 -*-
"""地址获取服务：API 优先，本地数据池兜底"""

import json
import random
import urllib.request
from abc import ABC, abstractmethod

from config.settings import COUNTRY_MAP, API_SUPPORTED_NAT
from data.address_pool import ADDRESS_POOL
from core.models import AddressData


class AddressProvider(ABC):
    """地址提供者接口"""

    @abstractmethod
    def get_address(self, region_code: str) -> AddressData | None:
        """获取一个随机地址，失败返回 None"""


class RandomUserProvider(AddressProvider):
    """randomuser.me API 地址提供者"""

    def get_address(self, region_code: str) -> AddressData | None:
        nat = API_SUPPORTED_NAT.get(region_code)
        if not nat:
            return None
        try:
            url = f"https://randomuser.me/api/?nat={nat}&results=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            user = payload.get("results", [{}])[0]
            return self._parse_user(user, region_code)
        except Exception:
            return None

    def _parse_user(self, user: dict, region_code: str) -> AddressData:
        name = user.get("name", {})
        loc = user.get("location", {})
        street = loc.get("street", {})
        unit = random.choice(ADDRESS_POOL[region_code]["units"]) if region_code in ADDRESS_POOL else "Flat A"

        city = loc.get("city", "")
        raw_postcode = str(loc.get("postcode", ""))
        country = loc.get("country", "")

        # 德国区域：仅当城市在街道簿内时采用 API 地址（确保街道+邮编+门牌一致）；
        # 表外城市直接放弃，让 AddressService 回退到本地池（使用街道簿保证一致）。
        if region_code == "de":
            from core.defaults import _DE_STREETS_BY_CITY, _DE_CITY_STATE
            in_book = city in _DE_STREETS_BY_CITY
            if not in_book:
                return None
            postcode = self._fix_de_postcode(city, raw_postcode)
            api_state = loc.get("state", "")
            wise_state = _DE_CITY_STATE.get(city, api_state)
        elif region_code == "gb":
            # 与 DE 同策略：城市不在配对表/前缀映射内则放弃 API 地址，
            # 回退本地池（避免 randomuser.me 合成假邮编如 YW9 9UX）
            from core.defaults import _CITY_POSTCODES_GB, _CITY_POSTCODE_PREFIX
            in_table = any(c.lower() == city.lower() for c, _ in _CITY_POSTCODES_GB)
            in_prefix = any(c.lower() == city.lower() for c in _CITY_POSTCODE_PREFIX)
            if not in_table and not in_prefix:
                return None
            postcode = self._fix_uk_postcode(city, raw_postcode)
            wise_state = loc.get("state", "")
        else:
            postcode = raw_postcode
            wise_state = loc.get("state", "")

        return AddressData(
            customer_name=(name.get("first", "") + " " + name.get("last", "")).strip(),
            address_unit=unit,
            address_street=f"{(lambda n: n if n <= 350 else random.randint(1, 350))(int(street.get('number', 1) or 1))} {street.get('name', '')}".strip(),
            address_district=city,
            postal_code=postcode,
            country=country,
            extra={
                "wise_city": city,
                "wise_state": wise_state,
                "wise_postcode": postcode,
                "wise_country": country,
            },
        )

    def _fix_uk_postcode(self, city: str, raw_postcode: str) -> str:
        """确保 UK 邮编与城市匹配

        1. 先在配对表中查找精确匹配 → 用其 area+district 前缀 + 随机后缀
           （避免固定 "1AA" 后缀被审核判定为停用邮编/邮件中心）
        2. 找不到则用城市→邮编前缀映射生成
        3. 完全未知则放弃（上层 RandomUserProvider 已过滤）
        """
        from core.defaults import _CITY_POSTCODES_GB, _CITY_POSTCODE_PREFIX
        import string as _string

        def _varied_suffix():
            # 英国邮编 inward code 必须是 数字+字母+字母（NAA），如 "3HA"、"7JN"
            return (str(random.randint(1, 9)) +
                    random.choice(_string.ascii_uppercase) +
                    random.choice(_string.ascii_uppercase))

        # 1. 精确匹配配对表 → 用 area 前缀 + 随机后缀
        for paired_city, paired_postcode in _CITY_POSTCODES_GB:
            if city.lower() == paired_city.lower():
                # 取邮编前缀部分（如 "SR1" "WF2" "FK8"），替换后缀为随机
                parts = paired_postcode.rsplit(" ", 1)
                if len(parts) == 2:
                    return f"{parts[0]} {_varied_suffix()}"
                return paired_postcode

        # 2. 用前缀映射生成
        for c, prefix in _CITY_POSTCODE_PREFIX.items():
            if city.lower() == c.lower():
                district = random.randint(1, 9)
                return f"{prefix}{district} {_varied_suffix()}"

        # 3. 完全未知城市：保留 API 原始邮编
        if raw_postcode and len(raw_postcode) >= 5:
            return raw_postcode
        return random.choice(_CITY_POSTCODES_GB)[1]

    def _fix_de_postcode(self, city: str, raw_postcode: str) -> str:
        """确保德国邮编与城市匹配

        德国邮编 5 位数字，从配对表查找。
        """
        from core.defaults import _CITY_POSTCODES_DE, _DE_CITY_STATE

        # 精确匹配配对表
        for paired_city, paired_postcode in _CITY_POSTCODES_DE:
            if city.lower() == paired_city.lower():
                return paired_postcode

        # 部分匹配（城市名包含）
        for paired_city, paired_postcode in _CITY_POSTCODES_DE:
            if paired_city.lower() in city.lower() or city.lower() in paired_city.lower():
                return paired_postcode

        # 未知城市：保留 API 原始邮编（5 位数字才保留）
        if raw_postcode and len(raw_postcode) == 5 and raw_postcode.isdigit():
            return raw_postcode

        # 完全无效：用随机德国邮编
        return random.choice(_CITY_POSTCODES_DE)[1]


class LocalPoolProvider(AddressProvider):
    """本地地址池提供者"""

    def get_address(self, region_code: str) -> AddressData | None:
        if region_code not in ADDRESS_POOL:
            return None
        pool = ADDRESS_POOL[region_code]
        first = random.choice(pool["first_names"])
        last = random.choice(pool["last_names"])
        unit = random.choice(pool["units"])

        # 德国区域：使用 defaults 的街道簿（城市-街道-邮编-门牌绑定），
        # 消除「随机选取不同城市/街道/邮编」导致的地址硬冲突。
        if region_code == "de":
            from core.defaults import _random_de_address
            city, postcode, house, street, state = _random_de_address()
            street_address = f"{street} {house}"
            extra = {
                "address_state": state,
                "wise_city": city,
                "wise_state": state,
                "wise_postcode": postcode,
                "wise_country": "Germany",
            }
            return AddressData(
                customer_name=f"{first} {last}",
                address_unit=unit,
                address_street=street_address,
                address_district=city,
                postal_code=postcode,
                country="Germany",
                extra=extra,
            )

        # 非德国区域：保持原有逻辑
        street_num = random.randint(1, 350)
        street = random.choice(pool["streets"])
        city = random.choice(pool["cities"])
        country = COUNTRY_MAP.get(region_code, "United Kingdom")

        # 邮编、州必须与城市匹配：优先从配对表取，找不到再回落随机池
        postcode = self._city_postcode(region_code, city)
        if not postcode:
            postcode = random.choice(pool["postcodes"])
        state = self._city_state(region_code, city)

        extra = {}
        if region_code in ("de", "gb"):
            extra = {
                "address_state": state,
                "wise_city": city,
                "wise_state": state,
                "wise_postcode": postcode,
                "wise_country": country,
            }

        return AddressData(
            customer_name=f"{first} {last}",
            address_unit=unit,
            address_street=f"{street_num} {street}",
            address_district=city,
            postal_code=postcode,
            country=country,
            extra=extra,
        )

    @staticmethod
    def _city_postcode(region_code: str, city: str) -> str:
        """查询城市→邮编配对（使用 defaults 中的配对表）"""
        from core.defaults import _CITY_POSTCODES_GB, _CITY_POSTCODES_DE
        table = _CITY_POSTCODES_GB if region_code == "gb" else _CITY_POSTCODES_DE
        for paired_city, postcode in table:
            if paired_city.lower() == city.lower():
                return postcode
        # 部分匹配
        for paired_city, postcode in table:
            if paired_city.lower() in city.lower() or city.lower() in paired_city.lower():
                return postcode
        return ""

    @staticmethod
    def _city_state(region_code: str, city: str) -> str:
        """查询城市→州（德国专用，防止 API/池数据与城市不匹配）"""
        if region_code != "de":
            return ""
        from core.defaults import _DE_CITY_STATE
        # 精确匹配
        for c, s in _DE_CITY_STATE.items():
            if c.lower() == city.lower():
                return s
        # 部分匹配（如 "Frankfurt" → "Frankfurt am Main"）
        for c, s in _DE_CITY_STATE.items():
            if c.lower() in city.lower() or city.lower() in c.lower():
                return s
        return ""


class AddressService:
    """地址获取服务"""

    def __init__(self, providers: list[AddressProvider] = None):
        self.providers = providers or [RandomUserProvider(), LocalPoolProvider()]
        self._last_source = ""

    @property
    def last_source(self) -> str:
        """上次地址来源描述"""
        return self._last_source

    def get_random_address(self, region_code: str) -> AddressData | None:
        """获取随机地址，依次尝试各提供者"""
        for provider in self.providers:
            result = provider.get_address(region_code)
            if result is not None:
                self._last_source = provider.__class__.__name__
                return result
        return None

    def get_address_as_dict(self, region_code: str) -> dict:
        """获取地址并转为表单字段字典"""
        addr = self.get_random_address(region_code)
        if addr is None:
            return {}
        values = {
            "customer_name": addr.customer_name,
            "address_unit": addr.address_unit,
            "address_street": addr.address_street,
            "address_district": addr.address_district,
            "postal_code": addr.postal_code,
            "country": addr.country,
        }
        values.update(addr.extra)
        return values