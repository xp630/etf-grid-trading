"""
Unit tests for Notifier
"""
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, '../../..')

from notification.notifier import Notifier


def test_send_trade_notification():
    """测试发送交易通知"""
    with patch('requests.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        notifier = Notifier(server酱_key='test_key')
        result = notifier.send_trade('buy', '510300', 3.80, 100)

        assert result == True
        mock_post.assert_called_once()


def test_send_risk_warning():
    """测试发送风险警告"""
    with patch('requests.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        notifier = Notifier(server酱_key='test_key')
        result = notifier.send_risk_warning('daily_loss', 100)

        assert result == True


def test_send_stop_loss():
    """测试发送止损通知"""
    with patch('requests.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        notifier = Notifier(server酱_key='test_key')
        result = notifier.send_stop_loss(8500)

        assert result == True


def test_disabled_notifier():
    """测试禁用通知（无key）"""
    notifier = Notifier(server酱_key='')
    result = notifier.send_trade('buy', '510300', 3.80, 100)

    assert result == False


def test_send_error():
    """测试发送错误通知"""
    with patch('requests.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        notifier = Notifier(server酱_key='test_key')
        result = notifier.send_error('Network error')

        assert result == True


def test_send_daily_summary():
    """测试发送每日总结"""
    with patch('requests.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        notifier = Notifier(server酱_key='test_key')
        result = notifier.send_daily_summary(50.0, [], {})

        assert result == True