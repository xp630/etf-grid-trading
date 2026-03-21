"""
Unit tests for PositionTracker
"""
import os
import tempfile
import pytest
from datetime import date

from utils.position_tracker import PositionTracker, Position


@pytest.fixture
def db_file():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


def test_initial_state(db_file):
    tracker = PositionTracker(db_file)
    positions = tracker.get_all_positions()
    assert positions == {}
    assert tracker.get_total_value(3.80) == 0


def test_buy_position(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    positions = tracker.get_all_positions()
    assert '510300' in positions
    assert positions['510300'].quantity == 100
    assert abs(positions['510300'].avg_price - 3.80) < 0.001


def test_position_value(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    value = tracker.get_total_value(current_price=3.90)
    assert abs(value - 390.0) < 0.01


def test_sell_position(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    tracker.record_sell('510300', 3.90, 100, 5)
    positions = tracker.get_all_positions()
    assert '510300' not in positions


def test_partial_sell(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 200, 5)
    tracker.record_sell('510300', 3.90, 100, 5)
    positions = tracker.get_all_positions()
    assert positions['510300'].quantity == 100


def test_get_position(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    pos = tracker.get_position('510300')
    assert pos is not None
    assert pos.symbol == '510300'
    assert pos.quantity == 100
    assert abs(pos.avg_price - 3.80) < 0.001
    assert pos.level_index == 5


def test_get_position_not_exists(db_file):
    tracker = PositionTracker(db_file)
    pos = tracker.get_position('510300')
    assert pos is None


def test_is_level_holding(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    assert tracker.is_level_holding(5) is True
    assert tracker.is_level_holding(3) is False


def test_get_trades(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    trades = tracker.get_trades()
    assert len(trades) == 1
    assert trades[0]['symbol'] == '510300'
    assert trades[0]['action'] == 'buy'
    assert trades[0]['price'] == 3.80
    assert trades[0]['quantity'] == 100


def test_get_trades_with_symbol_filter(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    tracker.record_buy('510500', 5.00, 200, 3)
    trades_510300 = tracker.get_trades(symbol='510300')
    assert len(trades_510300) == 1
    assert trades_510300[0]['symbol'] == '510300'


def test_multiple_buys_same_symbol(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    tracker.record_buy('510300', 3.90, 100, 5)
    positions = tracker.get_all_positions()
    assert positions['510300'].quantity == 200
    # Average price should be (3.80*100 + 3.90*100) / 200 = 3.85
    assert abs(positions['510300'].avg_price - 3.85) < 0.001


def test_sell_with_profit(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    tracker.record_sell('510300', 3.90, 100, 5)
    # Check trades for profit record
    trades = tracker.get_trades(symbol='510300')
    assert len(trades) == 2
    assert trades[1]['action'] == 'sell'
    assert trades[1]['profit'] is not None


def test_empty_trades(db_file):
    tracker = PositionTracker(db_file)
    trades = tracker.get_trades()
    assert trades == []


def test_buy_date_recorded(db_file):
    tracker = PositionTracker(db_file)
    tracker.record_buy('510300', 3.80, 100, 5)
    pos = tracker.get_position('510300')
    assert pos.buy_date is not None
    assert len(pos.buy_date) > 0