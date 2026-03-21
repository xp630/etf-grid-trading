"""
Unit tests for RiskEngine
"""
import os
import tempfile
import pytest
import sys
sys.path.insert(0, '../../..')

from engines.risk import RiskEngine
from utils.position_tracker import PositionTracker


@pytest.fixture
def risk_engine():
    """创建风控引擎"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    tracker = PositionTracker(path)
    config = {
        'max_position': 5000,
        'max_daily_loss': 100,
        'total_stop_loss': 9000,
        'initial_capital': 10000
    }

    engine = RiskEngine(tracker, config)
    yield engine
    os.unlink(path)


def test_within_position_limit(risk_engine):
    """测试：仓位在限制内"""
    result = risk_engine.check_order('buy', 500, 3.80)
    assert result['allowed'] == True


def test_exceed_position_limit(risk_engine):
    """测试：超出仓位限制"""
    result = risk_engine.check_order('buy', 6000, 3.80)
    assert result['allowed'] == False
    assert 'position_limit' in result['reason'].lower()


def test_within_daily_loss(risk_engine):
    """测试：日亏损在限制内"""
    result = risk_engine.check_daily_loss(50)
    assert result['allowed'] == True


def test_exceed_daily_loss(risk_engine):
    """测试：超出日亏损限制"""
    result = risk_engine.check_daily_loss(-150)
    assert result['allowed'] == False
    assert 'daily_loss' in result['reason'].lower()


def test_total_stop_loss(risk_engine):
    """测试：触及总止损线"""
    result = risk_engine.check_total_assets(8500)
    assert result['allowed'] == False
    assert 'stop_loss' in result['reason'].lower()


def test_all_checks_pass(risk_engine):
    """测试：所有检查都通过"""
    result = risk_engine.check_all('buy', 500, 3.80, daily_pnl=10, total_assets=9500)
    assert result['allowed'] == True


def test_check_order_sell_always_allowed(risk_engine):
    """测试：卖出订单始终被允许（不检查仓位）"""
    result = risk_engine.check_order('sell', 10000, 3.80)
    assert result['allowed'] == True


def test_get_status(risk_engine):
    """测试：获取风控状态"""
    status = risk_engine.get_status(daily_pnl=-30, total_assets=9700)
    assert status['daily_pnl'] == -30
    assert status['daily_limit'] == 100
    assert status['daily_remaining'] == 70
    assert status['total_assets'] == 9700
    assert status['stop_loss_line'] == 9000
    assert status['position_limit'] == 5000