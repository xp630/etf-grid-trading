"""
Unit tests for DataEngine
"""
import pytest
import time
from unittest.mock import MagicMock, patch
import sys
sys.path.insert(0, '../../..')

from engines.data import DataEngine, JQ_AVAILABLE


def test_init():
    """测试初始化"""
    engine = DataEngine('510300', retry_times=5, retry_interval=1.0)
    assert engine.symbol == '510300'
    assert engine.retry_times == 5
    assert engine.retry_interval == 1.0


def test_mock_price():
    """测试Mock价格生成"""
    engine = DataEngine('510300')
    price = engine._mock_price()

    # Mock价格应该在3.7-3.9范围内
    assert 3.7 <= price <= 3.9


def test_get_price_with_cache():
    """测试带缓存的价格获取"""
    engine = DataEngine('510300')

    # 手动设置缓存
    engine._price_cache = 3.85
    engine._cache_timestamp = time.time()

    # 应该返回缓存价格
    price = engine.get_price_with_cache(cache_seconds=10)
    assert abs(price - 3.85) < 0.001


def test_get_market_status():
    """测试获取市场状态"""
    engine = DataEngine('510300')
    status = engine.get_market_status()

    assert 'symbol' in status
    assert 'is_open' in status
    assert 'current_price' in status
    assert status['symbol'] == '510300'