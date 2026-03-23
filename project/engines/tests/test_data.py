"""
Unit tests for DataEngine
"""
import pytest
import time
from unittest.mock import MagicMock, patch
import sys
sys.path.insert(0, '../../..')

from engines.data import DataEngine


@pytest.fixture
def mock_config():
    return {
        'market': {'etf_code': '510300'},
        'data_source': {'index': 'mock'},
    }


def test_init(mock_config):
    """测试初始化"""
    engine = DataEngine(mock_config)
    assert engine.symbol == '510300'
    assert engine._source is not None


def test_get_price_with_cache(mock_config):
    """测试带缓存的价格获取"""
    engine = DataEngine(mock_config)

    # 手动设置缓存
    engine._price_cache = 3.85
    engine._cache_timestamp = time.time()

    # 应该返回缓存价格
    price = engine.get_price_with_cache(cache_seconds=10)
    assert abs(price - 3.85) < 0.001


def test_get_market_status(mock_config):
    """测试获取市场状态"""
    engine = DataEngine(mock_config)
    status = engine.get_market_status()

    assert 'symbol' in status
    assert 'is_open' in status
    assert 'current_price' in status
    assert status['symbol'] == '510300'
