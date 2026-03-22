"""
Flask Web监控面板
"""
from flask import Flask, render_template, jsonify, request
import yaml
import os
import sys
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.position_tracker import PositionTracker
from engines.risk import RiskEngine
from engines.data import DataEngine
from utils.grid_calculator import GridCalculator
from notification.notifier import Notifier

app = Flask(__name__)

# 全局状态
_state = {
    'tracker': None,
    'risk': None,
    'data': None,
    'notifier': None,
    'config': None,
    'grid': None,
    'baseline_price': None
}


def init_app():
    """初始化应用"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
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

    # 初始化网格计算器
    baseline_price = _state['data'].get_baseline_price()
    _state['baseline_price'] = baseline_price
    _state['grid'] = GridCalculator(
        base_price=baseline_price,
        levels=config['grid']['levels'],
        spacing=config['grid']['spacing']
    )


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
        data_info = _state['data'].get_data_info()

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
                'risk_status': _state['risk'].get_status(daily_pnl, total_assets),
                'data_info': data_info
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
    # 添加凭证信息（不含密码）
    if 'credentials' not in config:
        config['credentials'] = {}
    return jsonify({
        'success': True,
        'data': config
    })


@app.route('/api/grid/status')
def api_grid_status():
    """获取网格状态"""
    try:
        current_price = _state['data'].get_current_price()
        positions = _state['tracker'].get_all_positions()
        grid = _state['grid']

        # 获取所有档位
        levels = grid.get_levels()
        current_level_idx = grid.get_level_index(current_price)

        # 构建档位信息
        level_info = []
        for idx, price in enumerate(levels):
            # 检查该档位是否有持仓
            has_position = any(
                p.level_index == idx for p in positions.values()
            )
            level_info.append({
                'index': idx,
                'price': price,
                'is_current': idx == current_level_idx,
                'has_position': has_position,
                'is_below': idx < current_level_idx,
                'is_above': idx > current_level_idx
            })

        return jsonify({
            'success': True,
            'data': {
                'baseline_price': grid.base_price,
                'current_price': current_price,
                'current_level': current_level_idx,
                'levels_count': len(levels),
                'spacing': grid.spacing,
                'unit_size': _state['config']['grid']['unit_size'],
                'levels': level_info
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/trades/export')
def api_trades_export():
    """导出交易记录为CSV"""
    try:
        symbol = request.args.get('symbol', '510300')
        limit = int(request.args.get('limit', 1000))
        trades = _state['tracker'].get_trades(symbol=symbol, limit=limit)

        # 生成CSV
        csv_lines = ['时间,标的,操作,价格,数量,金额,盈亏']
        for t in trades:
            action = '买入' if t['action'] == 'buy' else '卖出'
            amount = t['price'] * t['quantity']
            profit = t.get('profit', '')
            csv_lines.append(
                f"{t['timestamp']},{t['symbol']},{action},"
                f"{t['price']},{t['quantity']},{amount:.2f},{profit}"
            )

        csv_content = '\n'.join(csv_lines)
        return csv_content, 200, {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': f'attachment; filename=trades_{datetime.now().strftime("%Y%m%d")}.csv'
        }
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/order/manual', methods=['POST'])
def api_manual_order():
    """
    手动下单

    请求体:
    {
        "action": "buy" | "sell",
        "price": 3.80,      # 可选，默认市价
        "quantity": 100
    }
    """
    try:
        data = request.get_json()
        action = data.get('action')
        price = data.get('price')  # None表示市价
        quantity = data.get('quantity')

        if action not in ('buy', 'sell'):
            return jsonify({'success': False, 'error': 'action must be buy or sell'}), 400
        if not quantity or quantity <= 0:
            return jsonify({'success': False, 'error': 'quantity must be positive'}), 400

        # 如果没有指定价格，使用当前价格
        if price is None:
            price = _state['data'].get_current_price()

        # 直接通过tracker记录（简化版，不走完整风控流程）
        symbol = _state['config']['market']['etf_code']
        daily_pnl = _state['tracker'].get_daily_pnl()
        total_assets = _state['config']['risk']['initial_capital'] + daily_pnl

        # 风控检查
        risk_result = _state['risk'].check_all(
            action=action,
            amount=price * quantity,
            price=price,
            daily_pnl=daily_pnl,
            total_assets=total_assets
        )

        if not risk_result['allowed']:
            return jsonify({
                'success': False,
                'error': f'Risk check failed: {risk_result["reason"]}'
            }), 400

        # 记录交易（模拟成交）
        if action == 'buy':
            _state['tracker'].record_buy(symbol, price, quantity, 0)
        else:
            _state['tracker'].record_sell(symbol, price, quantity, 0)

        return jsonify({
            'success': True,
            'data': {
                'action': action,
                'symbol': symbol,
                'price': price,
                'quantity': quantity,
                'amount': price * quantity
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config/grid', methods=['PUT'])
def api_update_grid_config():
    """
    更新网格配置（运行时调整）

    请求体:
    {
        "levels": 10,
        "spacing": 0.05,
        "unit_size": 500
    }
    """
    try:
        data = request.get_json()

        # 更新内存中的配置
        if 'levels' in data:
            _state['config']['grid']['levels'] = data['levels']
        if 'spacing' in data:
            _state['config']['grid']['spacing'] = data['spacing']
        if 'unit_size' in data:
            _state['config']['grid']['unit_size'] = data['unit_size']

        # 重新初始化网格
        baseline_price = _state['data'].get_baseline_price()
        _state['baseline_price'] = baseline_price
        _state['grid'] = GridCalculator(
            base_price=baseline_price,
            levels=_state['config']['grid']['levels'],
            spacing=_state['config']['grid']['spacing']
        )

        return jsonify({
            'success': True,
            'data': {
                'grid': _state['config']['grid'],
                'baseline_price': baseline_price
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config/notification', methods=['PUT'])
def api_update_notification_config():
    """
    更新通知配置

    请求体:
    {
        "server酱_key": "SCUxxx"
    }
    """
    try:
        data = request.get_json()
        server酱_key = data.get('server酱_key', '')

        # 更新配置
        _state['config']['notification']['server酱_key'] = server酱_key

        # 重新初始化通知器
        _state['notifier'] = Notifier(server酱_key)

        # 保存到文件
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config.yaml'
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        config['notification']['server酱_key'] = server酱_key
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)

        return jsonify({
            'success': True,
            'data': {
                'notification': {
                    'server酱_key': '****' if server酱_key else '',
                    'enabled': bool(server酱_key)
                }
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/logs')
def api_logs():
    """
    获取日志内容

    Query参数:
        lines: 返回行数，默认100
    """
    try:
        lines = int(request.args.get('lines', 100))
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'logs'
        )
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(log_dir, f'trading_{today}.log')

        logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                logs = [l.strip() for l in all_lines[-lines:] if l.strip()]

        return jsonify({
            'success': True,
            'data': {
                'log_file': log_file,
                'lines': logs,
                'count': len(logs)
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config/credentials', methods=['PUT'])
def api_update_credentials():
    """
    更新聚宽账号凭证

    请求体:
    {
        "username": "xxx",
        "password": "xxx"
    }
    注意: 密码更改后需要重启服务才能生效
    """
    try:
        data = request.get_json()
        username = data.get('username', '')
        password = data.get('password', '')

        # 保存到文件
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config.yaml'
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 更新环境变量（供后续进程使用）
        import os
        if username:
            os.environ['JQCLOUD_USERNAME'] = username
        if password:
            os.environ['JQCLOUD_PASSWORD'] = password

        config['credentials'] = {
            'username': username,
            'password': password
        }

        # 更新内存中的配置
        _state['config']['credentials'] = config['credentials']

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)

        return jsonify({
            'success': True,
            'data': {
                'username': username,
                'password': '****' if password else '',
                'message': '凭证已保存，重启服务后生效'
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    init_app()
    app.run(host='0.0.0.0', port=5000, debug=False)