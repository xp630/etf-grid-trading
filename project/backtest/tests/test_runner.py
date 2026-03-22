"""
Unit tests for BacktestRunner
"""
import pytest
import sys
import os
# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backtest.runner import BacktestRunner


@pytest.fixture
def default_config():
    """默认回测配置"""
    return {
        'grid': {
            'levels': 10,
            'spacing': 0.05,
            'unit_size': 500
        },
        'risk': {
            'initial_capital': 10000,
            'max_position': 5000
        }
    }


class TestBacktestRunner:
    """BacktestRunner测试"""

    def test_initialization(self, default_config):
        """测试初始化"""
        runner = BacktestRunner(default_config)

        assert runner.initial_capital == 10000
        assert runner.grid_config == default_config['grid']
        assert runner.risk_config == default_config['risk']
        assert runner.trades == []
        assert runner.daily_pnl == []

    def test_run_with_single_price(self, default_config):
        """测试单日价格回测"""
        runner = BacktestRunner(default_config)
        result = runner.run([4.0], ['2024-01-01'])

        assert 'initial_capital' in result
        assert 'final_value' in result
        assert 'total_return' in result
        assert result['initial_capital'] == 10000

    def test_run_with_oscillating_prices(self, default_config):
        """测试震荡市场价格回测"""
        runner = BacktestRunner(default_config)

        # 模拟震荡市：价格上下波动
        prices = [4.0, 4.1, 4.2, 4.1, 4.0, 3.9, 3.8, 3.9, 4.0, 4.1]
        dates = [f'2024-01-{i+1:02d}' for i in range(len(prices))]

        result = runner.run(prices, dates)

        assert result['initial_capital'] == 10000
        assert result['total_trades'] >= 0
        assert len(result['daily_pnl']) == len(prices)

    def test_run_with_uptrend_prices(self, default_config):
        """测试上涨市场价格回测"""
        runner = BacktestRunner(default_config)

        # 单边上涨
        prices = [4.0, 4.05, 4.10, 4.15, 4.20, 4.25, 4.30]
        dates = [f'2024-01-{i+1:02d}' for i in range(len(prices))]

        result = runner.run(prices, dates)

        assert result['total_trades'] >= 0
        assert len(result['daily_pnl']) == len(prices)

    def test_run_with_downtrend_prices(self, default_config):
        """测试下跌市场价格回测"""
        runner = BacktestRunner(default_config)

        # 单边下跌
        prices = [4.3, 4.25, 4.20, 4.15, 4.10, 4.05, 4.0]
        dates = [f'2024-01-{i+1:02d}' for i in range(len(prices))]

        result = runner.run(prices, dates)

        assert len(result['daily_pnl']) == len(prices)

    def test_run_with_flat_prices(self, default_config):
        """测试横盘市场价格回测"""
        runner = BacktestRunner(default_config)

        # 横盘 - 价格不变时不应触发新交易
        prices = [4.0] * 10
        dates = [f'2024-01-{i+1:02d}' for i in range(len(prices))]

        result = runner.run(prices, dates)

        # 横盘时交易次数应该很少或为0
        assert result['total_trades'] >= 0
        assert len(result['daily_pnl']) == len(prices)

    def test_run_without_dates(self, default_config):
        """测试不提供日期的回测"""
        runner = BacktestRunner(default_config)

        prices = [4.0, 4.1, 4.2, 4.1, 4.0]
        result = runner.run(prices)

        assert 'Day 0' in result['daily_pnl'][0]['date']
        assert len(result['daily_pnl']) == len(prices)

    def test_win_rate_calculation(self, default_config):
        """测试胜率计算"""
        runner = BacktestRunner(default_config)

        # 震荡市，产生多笔交易
        prices = []
        base = 4.0
        for i in range(50):
            # 模拟周期性波动
            phase = (i % 10) / 10 * 3.14159 * 2
            price = 4.0 + 0.2 * (1 - abs((i % 20) - 10) / 10)
            prices.append(round(price, 3))

        dates = [f'2024-01-{i+1:02d}' for i in range(len(prices))]
        result = runner.run(prices, dates)

        # 验证胜率在合理范围
        if result['sell_trades'] > 0:
            assert 0 <= result['win_rate'] <= 1

    def test_max_drawdown_calculation(self, default_config):
        """测试最大回撤计算"""
        runner = BacktestRunner(default_config)

        # 产生回撤的价格序列
        prices = [4.0, 4.1, 4.2, 4.3, 4.2, 4.1, 4.0, 3.9, 3.8]
        dates = [f'2024-01-{i+1:02d}' for i in range(len(prices))]

        result = runner.run(prices, dates)

        assert 0 <= result['max_drawdown'] <= 1

    def test_total_return_calculation(self, default_config):
        """测试总收益率计算"""
        runner = BacktestRunner(default_config)

        prices = [4.0, 4.2, 4.4, 4.6]  # 持续上涨
        dates = [f'2024-01-{i+1:02d}' for i in range(len(prices))]

        result = runner.run(prices, dates)

        # 验证收益率计算
        expected_return = (result['final_value'] - result['initial_capital']) / result['initial_capital']
        assert abs(result['total_return'] - expected_return) < 0.0001


class TestBacktestRunnerEdgeCases:
    """边界情况测试"""

    def test_empty_prices(self, default_config):
        """测试空价格列表"""
        runner = BacktestRunner(default_config)
        result = runner.run([])

        assert result == {}

    def test_single_rising_price(self, default_config):
        """测试单日上涨价格"""
        runner = BacktestRunner(default_config)
        result = runner.run([4.5], ['2024-01-01'])

        # 单日数据，回测逻辑会产生一笔初始买入
        assert result['total_trades'] >= 0
        assert result['initial_capital'] == 10000

    def test_custom_initial_capital(self):
        """测试自定义初始资金"""
        config = {
            'grid': {'levels': 10, 'spacing': 0.05},
            'risk': {}
        }
        runner = BacktestRunner(config)
        runner.initial_capital = 50000

        result = runner.run([4.0], ['2024-01-01'])

        assert result['initial_capital'] == 50000
