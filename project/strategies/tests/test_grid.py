"""
Unit tests for GridStrategy
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
sys.path.insert(0, '../../..')

from strategies.grid import GridStrategy


@pytest.fixture
def mock_dependencies():
    """创建模拟依赖"""
    data_engine = MagicMock()
    data_engine.get_current_price.return_value = 3.80
    data_engine.get_baseline_price.return_value = 3.80
    data_engine.is_market_open.return_value = True

    execution_engine = MagicMock()
    risk_engine = MagicMock()
    position_tracker = MagicMock()

    return {
        'data': data_engine,
        'execution': execution_engine,
        'risk': risk_engine,
        'tracker': position_tracker
    }


def test_strategy_initialization(mock_dependencies):
    """测试策略初始化"""
    strategy = GridStrategy(
        data_engine=mock_dependencies['data'],
        execution_engine=mock_dependencies['execution'],
        risk_engine=mock_dependencies['risk'],
        position_tracker=mock_dependencies['tracker']
    )

    assert strategy.current_price == 3.80
    assert strategy.grid is not None


def test_check_signals_no_action(mock_dependencies):
    """测试：无信号（价格未触发档位）"""
    mock_dependencies['tracker'].is_level_holding.return_value = False

    strategy = GridStrategy(
        data_engine=mock_dependencies['data'],
        execution_engine=mock_dependencies['execution'],
        risk_engine=mock_dependencies['risk'],
        position_tracker=mock_dependencies['tracker']
    )

    signals = strategy.check_signals()

    # 价格3.80正好在基准价，不应触发信号
    assert len(signals) == 0


def test_check_signals_buy_signal(mock_dependencies):
    """测试：买入信号（价格跌破档位）"""
    # 设置价格为3.60（低于基准价3.80两个档位）
    mock_dependencies['data'].get_current_price.return_value = 3.60
    mock_dependencies['tracker'].is_level_holding.return_value = False  # 该档位空仓

    strategy = GridStrategy(
        data_engine=mock_dependencies['data'],
        execution_engine=mock_dependencies['execution'],
        risk_engine=mock_dependencies['risk'],
        position_tracker=mock_dependencies['tracker']
    )

    signals = strategy.check_signals()

    # 应该有买入信号
    assert len(signals) > 0
    assert signals[0]['action'] == 'buy'


def test_check_signals_sell_signal(mock_dependencies):
    """测试：卖出信号（价格涨超档位）"""
    # 设置价格为4.00（高于基准价3.80两个档位）
    mock_dependencies['data'].get_current_price.return_value = 4.00
    mock_dependencies['tracker'].is_level_holding.return_value = True  # 该档位有持仓

    strategy = GridStrategy(
        data_engine=mock_dependencies['data'],
        execution_engine=mock_dependencies['execution'],
        risk_engine=mock_dependencies['risk'],
        position_tracker=mock_dependencies['tracker']
    )

    signals = strategy.check_signals()

    # 应该有卖出信号
    assert len(signals) > 0
    assert signals[0]['action'] == 'sell'


def test_run_once_market_closed(mock_dependencies):
    """测试：市场关闭时"""
    mock_dependencies['data'].is_market_open.return_value = False

    strategy = GridStrategy(
        data_engine=mock_dependencies['data'],
        execution_engine=mock_dependencies['execution'],
        risk_engine=mock_dependencies['risk'],
        position_tracker=mock_dependencies['tracker']
    )

    result = strategy.run_once()

    assert result['status'] == 'market_closed'


def test_get_status(mock_dependencies):
    """测试：获取策略状态"""
    mock_dependencies['tracker'].get_all_positions.return_value = {}
    mock_dependencies['tracker'].get_daily_pnl.return_value = 0

    strategy = GridStrategy(
        data_engine=mock_dependencies['data'],
        execution_engine=mock_dependencies['execution'],
        risk_engine=mock_dependencies['risk'],
        position_tracker=mock_dependencies['tracker']
    )

    status = strategy.get_status()

    assert 'current_price' in status
    assert 'baseline_price' in status
    assert 'positions' in status