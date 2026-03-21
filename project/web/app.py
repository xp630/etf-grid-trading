"""
Flask Web监控面板
"""
from flask import Flask, render_template, jsonify, request
import yaml
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.position_tracker import PositionTracker
from engines.risk import RiskEngine
from engines.data import DataEngine
from notification.notifier import Notifier

app = Flask(__name__)

# 全局状态
_state = {
    'tracker': None,
    'risk': None,
    'data': None,
    'notifier': None,
    'config': None
}


def init_app():
    """初始化应用"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'config.yaml'
    )

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    _state['config'] = config

    # 初始化组件
    db_path = config['database']['path']
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    _state['tracker'] = PositionTracker(db_path)
    _state['risk'] = RiskEngine(
        _state['tracker'],
        config['risk']
    )
    _state['data'] = DataEngine(config['market']['etf_code'])
    _state['notifier'] = Notifier(config['notification'].get('server酱_key', ''))


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """获取系统状态"""
    try:
        current_price = _state['data'].get_current_price()
        positions = _state['tracker'].get_all_positions()
        daily_pnl = _state['tracker'].get_daily_pnl()
        trades = _state['tracker'].get_trades(limit=10)

        # 计算总资产
        position_value = sum(
            p.quantity * current_price
            for p in positions.values()
        )
        # 从配置获取初始资金
        initial_capital = _state['config']['risk']['initial_capital']
        total_assets = initial_capital + daily_pnl

        return jsonify({
            'success': True,
            'data': {
                'current_price': current_price,
                'positions': [
                    {
                        'symbol': k,
                        'quantity': v.quantity,
                        'avg_price': v.avg_price,
                        'current_value': v.quantity * current_price,
                        'pnl': (current_price - v.avg_price) * v.quantity
                    }
                    for k, v in positions.items()
                ],
                'daily_pnl': daily_pnl,
                'total_assets': total_assets,
                'position_value': position_value,
                'cash': total_assets - position_value,
                'recent_trades': trades,
                'risk_status': _state['risk'].get_status(daily_pnl, total_assets)
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/risk/status')
def api_risk_status():
    """获取风控状态"""
    try:
        daily_pnl = _state['tracker'].get_daily_pnl()
        current_price = _state['data'].get_current_price()
        position_value = _state['tracker'].get_total_value(current_price)
        initial_capital = _state['config']['risk']['initial_capital']
        total_assets = initial_capital + daily_pnl

        return jsonify({
            'success': True,
            'data': _state['risk'].get_status(daily_pnl, total_assets)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/config')
def api_config():
    """获取配置（脱敏）"""
    config = _state['config'].copy()
    # 隐藏敏感信息
    if 'notification' in config:
        config['notification']['server酱_key'] = '****' if config['notification'].get('server酱_key') else ''
    return jsonify({
        'success': True,
        'data': config
    })


if __name__ == '__main__':
    init_app()
    app.run(host='0.0.0.0', port=5000, debug=True)