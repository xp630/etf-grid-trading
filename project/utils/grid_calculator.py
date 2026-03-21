"""
网格计算器 - 网格交易价格计算工具
"""
from typing import List


class GridCalculator:
    def __init__(self, base_price: float, levels: int = 10, spacing: float = 0.05):
        """
        初始化网格计算器

        Args:
            base_price: 基准价（前一交易日收盘价），必须大于0
            levels: 网格格数（单边格数），必须大于0
            spacing: 网格间距（百分比），必须大于0

        Raises:
            ValueError: 当base_price、levels或spacing小于等于0时
        """
        if base_price <= 0:
            raise ValueError("base_price must be greater than 0")
        if levels <= 0:
            raise ValueError("levels must be greater than 0")
        if spacing <= 0:
            raise ValueError("spacing must be greater than 0")

        self.base_price = base_price
        self.levels = levels
        self.spacing = spacing
        self._levels_cache = None

    def _calculate_levels(self) -> List[float]:
        """计算所有档位价格，返回从最低档到最高档的价格列表"""
        step = self.base_price * self.spacing
        # Total levels = levels below + base + levels above
        # With levels=10: 5 below + base + 5 above = 11 total
        levels_below = self.levels // 2
        levels_above = self.levels - levels_below

        all_levels = []

        # From lowest to highest
        for i in range(levels_below, -1, -1):
            price = self.base_price - i * step
            all_levels.append(round(price, 2))

        for i in range(1, levels_above + 1):
            price = self.base_price + i * step
            all_levels.append(round(price, 2))

        return all_levels

    def get_levels(self) -> List[float]:
        """获取所有档位价格列表"""
        if self._levels_cache is None:
            self._levels_cache = self._calculate_levels()
        return self._levels_cache

    def get_level_index(self, price: float) -> int:
        """
        获取价格所属的档位索引（0=最下档，len-1=最上档）
        """
        levels = self.get_levels()
        step = self.base_price * self.spacing

        if price <= levels[0]:
            return 0
        if price >= levels[-1]:
            return len(levels) - 1

        # Find the closest level index
        # index = round((base_price - price) / step) + levels_below
        levels_below = self.levels // 2

        if price <= self.base_price:
            # Below or at base price
            diff = self.base_price - price
            steps = round(diff / step)
            index = levels_below - steps
        else:
            # Above base price
            diff = price - self.base_price
            steps = round(diff / step)
            index = levels_below + steps

        # Clamp to valid range
        return max(0, min(index, len(levels) - 1))

    def get_price_at_level(self, level_index: int) -> float:
        """获取指定档位的价格"""
        levels = self.get_levels()
        if level_index < 0 or level_index >= len(levels):
            raise ValueError(f"level_index {level_index} out of range [0, {len(levels)-1}]")
        return levels[level_index]
