"""输入归一化。

已有食材、常备调料和排除条件必须使用同一套标准名规则，例如
“番茄”映射到“西红柿”，“马铃薯”映射到“土豆”。归一化采用保守原则：
只有别名字典里明确确认属于同一种采购物品时才合并，不做自动推断。
"""

from __future__ import annotations

_MAX_HOP = 10


class Normalizer:
    """按别名字典把名称统一到标准名。"""

    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        # 别名 -> 标准名；链式别名通过 normalize 中的有限跳解析。
        self._aliases: dict[str, str] = dict(aliases or {})

    def normalize(self, name: str) -> str:
        """返回单个名称的标准名；空白或空字符串原样返回。"""
        cur = (name or "").strip()
        if not cur:
            return cur
        seen: set[str] = set()
        for _ in range(_MAX_HOP):
            nxt = self._aliases.get(cur)
            if nxt is None:
                return cur
            cur = nxt.strip()
            if cur in seen:  # 出现环则停止，避免死循环
                return cur
            seen.add(cur)
        return cur

    def normalize_all(self, names: list[str]) -> list[str]:
        """归一化一组名称，去空、去重，保持首次出现顺序。"""
        result: list[str] = []
        for raw in names:
            cur = self.normalize(raw)
            if cur and cur not in result:
                result.append(cur)
        return result
