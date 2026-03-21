"""
Unit tests for GridCalculator class
"""
import pytest
from project.utils.grid_calculator import GridCalculator


def test_calculate_grid_levels():
    """测试网格档位计算"""
    calc = GridCalculator(base_price=3.80, levels=10, spacing=0.05)
    levels = calc.get_levels()
    assert len(levels) == 11  # 10格+基准价
    assert abs(levels[5] - 3.80) < 0.001  # 基准价在中间


def test_grid_spacing():
    """测试网格间距5%"""
    calc = GridCalculator(base_price=4.0, levels=10, spacing=0.05)
    levels = calc.get_levels()
    for i in range(len(levels) - 1):
        diff = abs(levels[i+1] - levels[i])
        assert abs(diff - 0.20) < 0.001  # 4.0 * 0.05 = 0.20


def test_which_level_price_falls_in():
    """测试价格属于哪个档位"""
    calc = GridCalculator(base_price=4.0, levels=10, spacing=0.05)
    level_idx = calc.get_level_index(3.6)
    assert level_idx == 3  # 4.0 - 2*0.2 = 3.6, base at index 5, so 3.6 at index 3


def test_price_below_lowest_level():
    """测试价格跌破最低档"""
    calc = GridCalculator(base_price=4.0, levels=10, spacing=0.05)
    level_idx = calc.get_level_index(3.0)
    assert level_idx == 0


def test_price_above_highest_level():
    """测试价格涨超最高档"""
    calc = GridCalculator(base_price=4.0, levels=10, spacing=0.05)
    level_idx = calc.get_level_index(5.0)
    assert level_idx == len(calc.get_levels()) - 1


def test_get_price_at_level():
    """测试获取指定档位的价格"""
    calc = GridCalculator(base_price=4.0, levels=10, spacing=0.05)
    # 基准价位于中间档位
    assert calc.get_price_at_level(5) == 4.0
    # 向上两档
    assert calc.get_price_at_level(7) == 4.4  # 4.0 + 2*0.2
    # 向下两档
    assert calc.get_price_at_level(3) == 3.6  # 4.0 - 2*0.2


def test_get_price_at_level_invalid_index():
    """测试获取无效档位索引价格"""
    calc = GridCalculator(base_price=4.0, levels=10, spacing=0.05)
    with pytest.raises(ValueError):
        calc.get_price_at_level(-1)
    with pytest.raises(ValueError):
        calc.get_price_at_level(100)


def test_invalid_base_price():
    """测试无效的基准价"""
    with pytest.raises(ValueError, match="base_price must be greater than 0"):
        GridCalculator(base_price=0, levels=10, spacing=0.05)
    with pytest.raises(ValueError, match="base_price must be greater than 0"):
        GridCalculator(base_price=-1, levels=10, spacing=0.05)


def test_invalid_levels():
    """测试无效的网格格数"""
    with pytest.raises(ValueError, match="levels must be greater than 0"):
        GridCalculator(base_price=4.0, levels=0, spacing=0.05)
    with pytest.raises(ValueError, match="levels must be greater than 0"):
        GridCalculator(base_price=4.0, levels=-1, spacing=0.05)


def test_invalid_spacing():
    """测试无效的网格间距"""
    with pytest.raises(ValueError, match="spacing must be greater than 0"):
        GridCalculator(base_price=4.0, levels=10, spacing=0)
    with pytest.raises(ValueError, match="spacing must be greater than 0"):
        GridCalculator(base_price=4.0, levels=10, spacing=-0.05)


def test_get_level_index_at_boundary():
    """测试档位索引在边界值"""
    calc = GridCalculator(base_price=4.0, levels=10, spacing=0.05)
    levels = calc.get_levels()
    # 测试最低档边界
    assert calc.get_level_index(levels[0]) == 0
    # 测试最高档边界
    assert calc.get_level_index(levels[-1]) == len(levels) - 1
    # 测试刚好在基准价
    assert calc.get_level_index(4.0) == 5