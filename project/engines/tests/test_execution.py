"""
Unit tests for ExecutionEngine
"""
import pytest
import os
import tempfile
import sys
sys.path.insert(0, '../../..')

from engines.execution import ExecutionEngine
from engines.risk import RiskEngine
from utils.position_tracker import PositionTracker


@pytest.fixture
def setup():
    """创建测试依赖"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    tracker = PositionTracker(db_path)

    config = {
        'max_position': 5000,
        'max_daily_loss': 100,
        'total_stop_loss': 9000,
        'initial_capital': 10000
    }
    risk = RiskEngine(tracker, config)

    yield {'tracker': tracker, 'risk': risk, 'db_path': db_path}

    os.unlink(db_path)


def test_place_buy_order_success(setup):
    """测试成功下单买入"""
    engine = ExecutionEngine(setup['tracker'], setup['risk'])

    result = engine.place_order('buy', '510300', 3.80, 100, level_index=5)

    assert result['success'] == True
    assert 'order_id' in result


def test_place_buy_order_rejected_by_risk(setup):
    """测试风控拒绝买入"""
    # 先买入大量，使仓位接近上限
    setup['tracker'].record_buy('510300', 3.80, 1000, 5)

    engine = ExecutionEngine(setup['tracker'], setup['risk'])

    # 再尝试买入（应该被拒绝）
    result = engine.place_order('buy', '510300', 3.80, 500, level_index=3)

    assert result['success'] == False
    assert 'risk' in result['reason'].lower()


def test_place_sell_order(setup):
    """测试卖出订单"""
    setup['tracker'].record_buy('510300', 3.80, 100, 5)

    engine = ExecutionEngine(setup['tracker'], setup['risk'])
    result = engine.place_order('sell', '510300', 3.90, 100, level_index=5)

    assert result['success'] == True


def test_cancel_order(setup):
    """测试取消订单"""
    engine = ExecutionEngine(setup['tracker'], setup['risk'])
    result = engine.cancel_order('order_123')

    assert result['success'] == True


def test_get_order_status(setup):
    """测试查询订单状态"""
    engine = ExecutionEngine(setup['tracker'], setup['risk'])
    status = engine.get_order_status('order_123')

    assert status is not None