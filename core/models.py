# -*- coding: utf-8 -*-
"""数据模型定义"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Region:
    """地区"""
    id: int
    code: str
    name: str


@dataclass
class BillType:
    """账单类型"""
    id: str
    region_id: int
    code: str
    name: str
    currency: str
    category: str


@dataclass
class Template:
    """账单模板"""
    btid: int
    bt_code: str
    html_template: str
    css_template: str = ""
    js_template: str = ""


@dataclass
class FormField:
    """表单字段定义"""
    placeholder: str
    label: str
    default_value: str = ""


@dataclass
class FormSpec:
    """表单规格（由模板生成，用于构建表单）"""
    bt_code: str
    fields: list[FormField] = field(default_factory=list)


@dataclass
class AddressData:
    """随机地址数据"""
    customer_name: str = ""
    address_unit: str = ""
    address_street: str = ""
    address_district: str = ""
    postal_code: str = ""
    country: str = ""
    # 地区特定字段
    extra: dict = field(default_factory=dict)