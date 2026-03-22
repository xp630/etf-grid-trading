"""
Unit tests for Web App API endpoints
"""
import pytest
import sys
import os
import tempfile
# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Mock the global state before importing app
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_state():
    """创建模拟状态"""
    tracker = MagicMock()
    tracker.get_all_positions.return_value = {}
    tracker.get_daily_pnl.return_value = 0
    tracker.get_trades.return_value = []
    tracker.get_total_value.return_value = 0

    risk = MagicMock()
    risk.get_status.return_value = {
        'daily_pnl': 0,
        'daily_limit': 100,
        'daily_remaining': 100,
        'total_assets': 10000,
        'stop_loss_line': 9000,
        'position_limit': 5000
    }

    data = MagicMock()
    data.get_current_price.return_value = 4.0
    data.get_data_info.return_value = {
        'data_date': '2024-01-01',
        'data_source': 'Mock',
        'data_range': '2024-01-01 ~ 2024-01-01',
        'is_historical': True
    }

    notifier = MagicMock()

    config = {
        'risk': {'initial_capital': 10000},
        'market': {'etf_code': '510300'},
        'notification': {}
    }

    return {
        'tracker': tracker,
        'risk': risk,
        'data': data,
        'notifier': notifier,
        'config': config
    }


@pytest.fixture
def app(mock_state):
    """创建测试Flask应用"""
    with patch('web.app._state', mock_state):
        from web.app import app
        app.config['TESTING'] = True
        yield app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


class TestIndexEndpoint:
    """测试首页路由"""

    def test_index_returns_html(self, client):
        """测试首页返回HTML"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'<!DOCTYPE html' in response.data or b'<html' in response.data


class TestApiStatus:
    """测试 /api/status 端点"""

    def test_status_returns_json(self, client):
        """测试状态端点返回JSON"""
        response = client.get('/api/status')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data

    def test_status_includes_positions(self, client):
        """测试状态包含持仓信息"""
        response = client.get('/api/status')
        data = response.get_json()

        assert 'positions' in data['data']
        assert 'daily_pnl' in data['data']
        assert 'total_assets' in data['data']

    def test_status_includes_risk_status(self, client):
        """测试状态包含风控状态"""
        response = client.get('/api/status')
        data = response.get_json()

        assert 'risk_status' in data['data']

    def test_status_includes_data_info(self, client):
        """测试状态包含数据源信息"""
        response = client.get('/api/status')
        data = response.get_json()

        assert 'data_info' in data['data']

    def test_status_handles_error(self, client, mock_state):
        """测试状态端点错误处理"""
        mock_state['data'].get_current_price.side_effect = Exception("Test error")

        response = client.get('/api/status')
        data = response.get_json()

        assert data['success'] is False
        assert 'error' in data


class TestApiRiskStatus:
    """测试 /api/risk/status 端点"""

    def test_risk_status_returns_json(self, client):
        """测试风控状态返回JSON"""
        response = client.get('/api/risk/status')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data

    def test_risk_status_includes_limits(self, client):
        """测试风控状态包含限制信息"""
        response = client.get('/api/risk/status')
        data = response.get_json()

        risk = data['data']
        assert 'daily_limit' in risk
        assert 'stop_loss_line' in risk
        assert 'position_limit' in risk

    def test_risk_status_handles_error(self, client, mock_state):
        """测试风控状态错误处理"""
        mock_state['tracker'].get_daily_pnl.side_effect = Exception("Test error")

        response = client.get('/api/risk/status')
        data = response.get_json()

        assert data['success'] is False


class TestApiConfig:
    """测试 /api/config 端点"""

    def test_config_returns_json(self, client):
        """测试配置返回JSON"""
        response = client.get('/api/config')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data

    def test_config_hides_sensitive_info(self, client, mock_state):
        """测试配置隐藏敏感信息"""
        mock_state['config']['notification']['server酱_key'] = 'secret_key'

        response = client.get('/api/config')
        data = response.get_json()

        config = data['data']
        assert config['notification']['server酱_key'] == '****'

    def test_config_empty_key_masked(self, client, mock_state):
        """测试空key也被遮蔽"""
        mock_state['config']['notification']['server酱_key'] = ''

        response = client.get('/api/config')
        data = response.get_json()

        assert data['data']['notification']['server酱_key'] == ''


class TestApiPositions:
    """测试持仓数据结构"""

    def test_position_structure(self, client, mock_state):
        """测试持仓数据结构"""
        from utils.position_tracker import Position

        mock_position = Position(
            symbol='510300',
            quantity=100,
            avg_price=4.0,
            level_index=5,
            buy_date='2024-01-01'
        )
        mock_state['tracker'].get_all_positions.return_value = {
            '510300': mock_position
        }

        response = client.get('/api/status')
        data = response.get_json()

        positions = data['data']['positions']
        assert len(positions) == 1
        assert positions[0]['symbol'] == '510300'
        assert positions[0]['quantity'] == 100
        assert 'current_value' in positions[0]
        assert 'pnl' in positions[0]


class TestApiTrades:
    """测试交易记录"""

    def test_recent_trades_structure(self, client, mock_state):
        """测试交易记录结构"""
        mock_trades = [
            {
                'symbol': '510300',
                'action': 'buy',
                'price': 4.0,
                'quantity': 100,
                'level_index': 5,
                'timestamp': '2024-01-01T10:00:00',
                'profit': None
            }
        ]
        mock_state['tracker'].get_trades.return_value = mock_trades

        response = client.get('/api/status')
        data = response.get_json()

        trades = data['data']['recent_trades']
        assert len(trades) == 1
        assert trades[0]['action'] == 'buy'
        assert trades[0]['price'] == 4.0
