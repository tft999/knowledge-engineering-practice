"""CookKG 自定义异常。"""

from __future__ import annotations


class CookKGError(Exception):
    """CookKG 基础异常。"""


class DataLoadError(CookKGError):
    """标准数据缺失或格式错误。"""


class InvalidInputError(CookKGError):
    """用户输入非法（例如菜数超出 1~3）。"""
