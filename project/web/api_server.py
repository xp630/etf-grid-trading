"""
ETF网格交易系统 - Flask API服务
提供REST API给Streamlit监控面板使用
包含后台交易循环
"""
import os
import sys
import json
import threading
import time
import yaml
import logging
from flask import Flask, jsonify, request
from datetime import datetime
from logging.handlers import RotatingFileHandler

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_logging(config: dict = None):
    """配置日志系统"""
    if config is None:
        config = {}

    log_config = config.get('logging', {})
    log_dir = log_config.get('dir', 'logs')
    log_level = log_config.get('level', 'INFO')
    max_bytes = log_config.get('max_bytes', 10 * 1024 * 1024)
    backup_count = log_config.get('backup_count', 30)

    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger('api_server')
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_file = os.path.join(log_dir, f'trading_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def create_api_server(config_path: str = None):
    """创建API服务器（包含所有路由和交易逻辑）"""

    # 加载配置
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config.yaml'
        )

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 设置日志
    logger = setup_logging(config)

    # 初始化组件
    db_path = config['database']['path']
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    from utils.position_tracker import PositionTracker
    from engines.risk import RiskEngine
    from engines.data import DataEngine
    from engines.execution import ExecutionEngine
    from notification.notifier import Notifier
    from utils.market_calendar import get_market_calendar

    tracker = PositionTracker(db_path)
    risk = RiskEngine(tracker, config['risk'])
    data = DataEngine(config['market']['etf_code'])
    notifier = Notifier(config['notification'].get('server酱_key', ''))
    execution = ExecutionEngine(tracker, risk, data)

    # 启动配置汇总
    creds = config.get('credentials', {})
    uname = creds.get('username', '')
    notif_key = config['notification'].get('server酱_key', '')
    logger.info(
        f"启动配置: ETF={config['market']['etf_code']} "
        f"数据源={config.get('data_source', {}).get('index', 'N/A')} "
        f"账号={uname[:3]}*** {'已配置' if uname else '未配置'} "
        f"网格={config['grid']['levels']}档/{config['grid']['spacing']*100:.1f}%/{config['grid']['unit_size']}元 "
        f"持仓<={config['risk']['max_position']}元 "
        f"日亏熔断={config['risk']['max_daily_loss']}元 总止损={config['risk']['total_stop_loss']}元 "
        f"通知={'有' if notif_key else '无'}"
    )

    # 策略映射
    STRATEGIES = {
        'grid': {
            'config_keys': ['grid']
        },
        'trend_grid': {
            'config_keys': ['grid', 'trend_filter', 'auto_unit', 'risk_control']
        },
        'ma_crossover': {
            'config_keys': ['ma_crossover']
        }
    }

    # 当前策略
    current_strategy_name = 'trend_grid'
    strategy_lock = threading.Lock()
    trading_running = threading.Event()
    trading_running.set()

    strategy = None  # 延迟初始化
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False

    def build_strategy_config(strategy_name: str) -> dict:
        """构建策略配置"""
        if strategy_name not in STRATEGIES:
            strategy_name = 'trend_grid'

        strategy_config = {}
        for key in STRATEGIES[strategy_name]['config_keys']:
            if key in config:
                strategy_config[key] = config[key]

        if strategy_name == 'trend_grid':
            strategy_config['trend_filter'] = config.get('trend_filter', {})
            strategy_config['auto_unit'] = config.get('auto_unit', {})
            strategy_config['risk_control'] = config.get('risk_control', {})
            # 添加AI配置
            strategy_config['ai_model'] = config.get('ai_model', {})

        return strategy_config

    def create_strategy_instance(strategy_name: str):
        """创建策略实例"""
        if strategy_name not in STRATEGIES:
            strategy_name = 'trend_grid'

        strategy_config = build_strategy_config(strategy_name)

        if strategy_name == 'grid':
            from strategies.grid import GridStrategy
            strategy_class = GridStrategy
        elif strategy_name == 'trend_grid':
            from strategies.trend_grid_live import TrendGridStrategy
            strategy_class = TrendGridStrategy
        elif strategy_name == 'ma_crossover':
            from strategies.ma_crossover import MACrossoverStrategy
            strategy_class = MACrossoverStrategy
        else:
            from strategies.trend_grid_live import TrendGridStrategy
            strategy_class = TrendGridStrategy

        return strategy_class(
            data_engine=data,
            execution_engine=execution,
            risk_engine=risk,
            position_tracker=tracker,
            config=strategy_config
        )

    # 初始化策略
    strategy = create_strategy_instance(current_strategy_name)
    logger.info(f"策略初始化完成: {current_strategy_name}")

    # ========== 交易循环 ==========

    def trading_loop():
        """后台交易循环"""
        logger.info("交易循环启动")

        while trading_running.is_set():
            try:
                if not get_market_calendar().is_market_open():
                    time.sleep(60)
                    continue

                with strategy_lock:
                    result = strategy.run_once()

                if result['status'] == 'executed':
                    logger.info(f"执行信号: {result['signals']}")

                    for item in result.get('results', []):
                        sig = item['signal']
                        res = item['result']

                        if res.get('success'):
                            notifier.send_trade(
                                sig['action'],
                                config['market']['etf_code'],
                                sig['price'],
                                sig['quantity']
                            )
                        else:
                            logger.error(f"下单失败: {res.get('reason')}")

                elif result['status'] == 'error':
                    logger.error(f"策略执行错误: {result['message']}")
                    notifier.send_error(result['message'])

                daily_pnl = tracker.get_daily_pnl()
                current_price = data.get_current_price()
                initial_capital = config['risk']['initial_capital']
                total_assets = initial_capital + daily_pnl

                risk_status = risk.get_status(daily_pnl, total_assets)

                if risk_status['daily_remaining'] < 0:
                    logger.warning("触及日亏损限制，停止交易")
                    notifier.send_risk_warning('daily_loss', abs(daily_pnl))
                    time.sleep(3600)
                    continue

                if total_assets < risk_status['stop_loss_line']:
                    logger.warning("触及总止损线，永久停止交易")
                    notifier.send_stop_loss(total_assets)
                    trading_running.clear()
                    break

                time.sleep(10)

            except Exception as e:
                logger.error(f"交易循环异常: {e}")
                time.sleep(30)

        logger.info("交易循环结束")

    # 启动交易线程
    trading_thread = threading.Thread(target=trading_loop, daemon=True)
    trading_thread.start()

    # ========== API 路由 ==========

    @app.route('/api/status', methods=['GET'])
    def get_status():
        try:
            positions = tracker.get_all_positions()
            daily_pnl = tracker.get_daily_pnl()
            current_price = data.get_current_price()
            initial_capital = config['risk']['initial_capital']
            total_assets = initial_capital + daily_pnl
            data_info = data.get_data_info()

            return jsonify({
                'success': True,
                'data': {
                    'current_price': current_price,
                    'total_assets': total_assets,
                    'daily_pnl': daily_pnl,
                    'position_value': tracker.get_total_value(current_price),
                    'positions': [{
                        'symbol': k,
                        'quantity': v.quantity,
                        'avg_price': v.avg_price,
                        'current_value': v.quantity * current_price,
                        'pnl': (current_price - v.avg_price) * v.quantity
                    } for k, v in positions.items()],
                    'recent_trades': [{
                        'action': t['action'],
                        'symbol': t['symbol'],
                        'price': t['price'],
                        'quantity': t['quantity'],
                        'timestamp': t['timestamp']
                    } for t in tracker.get_trades(limit=5)],
                    'data_info': data_info
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/risk/status', methods=['GET'])
    def get_risk_status():
        try:
            daily_pnl = tracker.get_daily_pnl()
            initial_capital = config['risk']['initial_capital']
            total_assets = initial_capital + daily_pnl
            risk_status = risk.get_status(daily_pnl, total_assets)
            return jsonify({'success': True, 'data': risk_status})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/index/quotes', methods=['GET'])
    def get_index_quotes():
        """获取主要指数当前价格"""
        try:
            from engines.data import DataEngine
            quotes = DataEngine.get_index_prices()
            return jsonify({'success': True, 'data': quotes})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/index/trend', methods=['GET'])
    def get_index_trend():
        """获取指数均线趋势"""
        try:
            import pandas as pd
            code = request.args.get('code', '000001.XSHG')
            days = int(request.args.get('days', 120))

            from engines.data import DataEngine

            # 获取数据源配置
            data_source = config.get('data_source', {}).get('index', 'auto')

            # 聚宽指数代码映射
            jq_indices = {
                '000001.XSHG': '上证指数',
                '399001.XSHE': '深证成指',
                '399006.XSHE': '创业板指',
                '000688.XSHG': '科创50',
                '000300.XSHG': '沪深300',
                '000016.XSHG': '上证50',
                '000905.XSHG': '中证500'
            }

            # AkShare指数代码映射
            ak_indices = {
                '000001.XSHG': ('sh000001', '上证指数'),
                '399001.XSHE': ('sz399001', '深证成指'),
                '399006.XSHE': ('sz399006', '创业板指'),
                '000688.XSHG': ('sh000688', '科创50'),
                '000300.XSHG': ('sh000300', '沪深300'),
                '000016.XSHG': ('sh000016', '上证50'),
                '000905.XSHG': ('sh000905', '中证500')
            }

            # Baostock指数代码映射
            bs_indices = {
                '000001.XSHG': ('sh.000001', '上证指数'),
                '399001.XSHE': ('sz.399001', '深证成指'),
                '399006.XSHE': ('sz.399006', '创业板指'),
                '000688.XSHG': ('sh.000688', '科创50'),
                '000300.XSHG': ('sh.000300', '沪深300'),
                '000016.XSHG': ('sh.000016', '上证50'),
                '000905.XSHG': ('sh.000905', '中证500')
            }

            name = jq_indices.get(code, code)

            def calculate_ma(prices):
                ps = pd.Series(prices)
                return ps.rolling(5).mean().tolist(), ps.rolling(20).mean().tolist(), ps.rolling(60).mean().tolist()

            def try_joinquant():
                try:
                    import jqdatasdk as jq
                    import os
                    import pandas as pd
                    username = os.environ.get('JQCLOUD_USERNAME')
                    password = os.environ.get('JQCLOUD_PASSWORD')
                    if not username or not password:
                        return None
                    jq.auth(username, password)
                    end_date = (pd.Timestamp.now() - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
                    df = jq.get_price(code, end_date=end_date, count=days, frequency='daily')
                    prices = df['close'].tolist()
                    dates = [str(d) for d in df.index.tolist()]
                    ma5, ma20, ma60 = calculate_ma(prices)
                    return {
                        'dates': dates, 'prices': prices, 'ma5': ma5, 'ma20': ma20, 'ma60': ma60, 'source': 'joinquant'
                    }
                except Exception as e:
                    logger.warning(f"聚宽数据获取失败: {e}")
                    return None

            def try_akshare():
                try:
                    import akshare as ak
                    import pandas as pd
                    ak_code, ak_name = ak_indices.get(code, (None, None))
                    if not ak_code:
                        return None
                    df = ak.stock_zh_index_daily(symbol=ak_code)
                    df = df.tail(days).reset_index(drop=True)
                    prices = df['close'].tolist()
                    dates = df['date'].tolist()
                    nonlocal name
                    name = ak_name or name
                    ma5, ma20, ma60 = calculate_ma(prices)
                    return {
                        'dates': dates, 'prices': prices, 'ma5': ma5, 'ma20': ma20, 'ma60': ma60, 'source': 'akshare'
                    }
                except Exception as e:
                    logger.warning(f"AkShare数据获取失败: {e}")
                    return None

            def try_baostock():
                try:
                    import baostock as bs
                    import pandas as pd
                    import datetime
                    bs_code, bs_name = bs_indices.get(code, (None, None))
                    if not bs_code:
                        return None
                    lg = bs.login()
                    if lg.error_code != '0':
                        bs.logout()
                        return None
                    end_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
                    start_date = (datetime.datetime.now() - datetime.timedelta(days=days+60)).strftime('%Y-%m-%d')
                    rs = bs.query_history_k_data_plus(bs_code, 'date,close', start_date=start_date, end_date=end_date, frequency='d')
                    if rs.error_code != '0':
                        bs.logout()
                        return None
                    data = rs.get_data()
                    bs.logout()
                    if len(data) == 0:
                        return None
                    data = data.tail(days).reset_index(drop=True)
                    prices = data['close'].astype(float).tolist()
                    dates = data['date'].tolist()
                    nonlocal name
                    name = bs_name or name
                    ma5, ma20, ma60 = calculate_ma(prices)
                    return {
                        'dates': dates, 'prices': prices, 'ma5': ma5, 'ma20': ma20, 'ma60': ma60, 'source': 'baostock'
                    }
                except Exception as e:
                    logger.warning(f"Baostock数据获取失败: {e}")
                    return None

            def try_mock():
                import random
                import pandas as pd
                from datetime import datetime, timedelta
                random.seed(hash(code) % (2**31))
                base = 3000
                dates = [(datetime.now() - timedelta(days=days-i)).strftime('%Y-%m-%d') for i in range(days)]
                prices = [base * (1 + random.uniform(-0.02, 0.015)) for _ in range(days)]
                for i in range(1, len(prices)):
                    prices[i] = prices[i-1] * (1 + random.uniform(-0.01, 0.01))
                random.seed()
                ma5, ma20, ma60 = calculate_ma(prices)
                return {
                    'dates': dates, 'prices': prices, 'ma5': ma5, 'ma20': ma20, 'ma60': ma60, 'source': 'mock'
                }

            # 根据配置选择数据源
            result_data = None
            if data_source == 'auto':
                # 自动模式：按优先级尝试
                result_data = try_joinquant() or try_akshare() or try_baostock() or try_mock()
            elif data_source == 'joinquant':
                result_data = try_joinquant() or try_mock()
            elif data_source == 'akshare':
                result_data = try_akshare() or try_baostock() or try_mock()
            elif data_source == 'baostock':
                result_data = try_baostock() or try_mock()
            else:  # mock
                result_data = try_mock()

            return jsonify({
                'success': True,
                'data': {
                    'code': code,
                    'name': name,
                    **result_data
                }
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/index/spot', methods=['GET'])
    def get_index_spot():
        """获取预设指数实时行情（东方财富）"""
        try:
            import akshare as ak
            df = ak.stock_zh_index_spot_em()
            # 筛选主要指数
            indices = ['000001', '399001', '399006', '000688', '000300', '000016', '000905']
            result = {}
            for idx in indices:
                row = df[df['代码'] == idx]
                if not row.empty:
                    r = row.iloc[0]
                    result[idx] = {
                        'name': r['名称'],
                        'price': float(r['最新价']) if r['最新价'] != '-' else None,
                        'change_pct': float(r['涨跌幅']) if r['涨跌幅'] != '-' else 0,
                        'change_val': float(r['涨跌额']) if r['涨跌额'] != '-' else 0,
                    }
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/stock/trend', methods=['GET'])
    def get_stock_trend():
        """获取股票均线趋势（支持手动输入的股票代码）"""
        try:
            code = request.args.get('code', '')
            days = int(request.args.get('days', 120))

            if not code:
                return jsonify({'success': False, 'error': '股票代码不能为空'})

            # 标准化股票代码格式
            code = code.strip()
            # 自动添加市场前缀和点号 (baostock格式: sh.600000, sz.300463)
            if not code.startswith(('sh.', 'sz.', 'SH.', 'SZ.')):
                code_lower = code.lower()
                if code_lower.startswith('6'):
                    code = 'sh.' + code_lower
                elif code_lower.startswith(('0', '3')):
                    code = 'sz.' + code_lower
                else:
                    return jsonify({'success': False, 'error': f'不支持的股票代码格式: {code}'})

            # 使用baostock获取数据
            try:
                import baostock as bs
                import pandas as pd

                lg = bs.login()
                if lg.error_code != '0':
                    return jsonify({'success': False, 'error': f'baostock登录失败: {lg.error_msg}'})

                # 获取股票基本信息（名称）
                stock_info = bs.query_stock_basic(code=code)
                stock_data = stock_info.get_data()
                stock_name = stock_data['code_name'].iloc[0] if len(stock_data) > 0 else code
                # 尝试修复编码
                try:
                    stock_name = stock_name.encode('latin1').decode('gbk')
                except:
                    pass

                # 计算日期范围
                import datetime
                end_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
                start_date = (datetime.datetime.now() - datetime.timedelta(days=days+30)).strftime('%Y-%m-%d')

                rs = bs.query_history_k_data_plus(
                    code,
                    'date,open,high,low,close,volume',
                    start_date=start_date,
                    end_date=end_date,
                    frequency='d'
                )

                if rs.error_code != '0':
                    bs.logout()
                    return jsonify({'success': False, 'error': f'查询失败: {rs.error_msg}'})

                data = rs.get_data()
                bs.logout()

                if len(data) == 0:
                    return jsonify({'success': False, 'error': f'无数据: {code}'})

                # 取最后days条
                data = data.tail(days).reset_index(drop=True)
                prices = data['close'].astype(float).tolist()
                dates = data['date'].tolist()

                # 计算均线
                ps = pd.Series(prices)
                ma5 = ps.rolling(5).mean().tolist()
                ma20 = ps.rolling(20).mean().tolist()
                ma60 = ps.rolling(60).mean().tolist()

                return jsonify({
                    'success': True,
                    'data': {
                        'code': code,
                        'name': stock_name,
                        'dates': dates,
                        'prices': prices,
                        'ma5': ma5,
                        'ma20': ma20,
                        'ma60': ma60,
                        'source': 'baostock'
                    }
                })
            except Exception as e:
                logger.warning(f"股票数据获取失败: {e}")
                return jsonify({'success': False, 'error': f'获取股票数据失败: {str(e)}'})

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/grid/status', methods=['GET'])
    def get_grid_status():
        try:
            current_price = data.get_current_price()

            if hasattr(strategy, 'grid') and strategy.grid:
                levels = strategy.grid.get_levels()
                baseline_price = strategy.grid.base_price
            else:
                baseline_price = data.get_baseline_price()
                from utils.grid_calculator import GridCalculator
                grid_calc = GridCalculator(base_price=baseline_price, levels=10, spacing=0.05)
                levels = grid_calc.get_levels()

            level_info = []
            for i, price in enumerate(levels):
                is_current = abs(price - current_price) < 0.01
                has_position = tracker.is_level_holding(i) if hasattr(tracker, 'is_level_holding') else False

                level_info.append({
                    'index': i,
                    'price': price,
                    'is_current': is_current,
                    'has_position': has_position,
                    'is_below': price < current_price
                })

            return jsonify({
                'success': True,
                'data': {
                    'baseline_price': baseline_price,
                    'levels': level_info
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/strategy', methods=['GET'])
    def get_strategy():
        try:
            return jsonify({
                'success': True,
                'data': {
                    'name': current_strategy_name,
                    'available': list(STRATEGIES.keys())
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/strategy', methods=['PUT'])
    def switch_strategy():
        nonlocal strategy, current_strategy_name

        try:
            req_data = request.get_json()
            new_strategy_name = req_data.get('name', current_strategy_name)

            if new_strategy_name not in STRATEGIES:
                return jsonify({
                    'success': False,
                    'error': f'未知策略: {new_strategy_name}'
                })

            with strategy_lock:
                new_strategy = create_strategy_instance(new_strategy_name)
                strategy = new_strategy
                current_strategy_name = new_strategy_name

            logger.info(f"策略已切换为: {new_strategy_name}")

            return jsonify({
                'success': True,
                'data': {
                    'name': current_strategy_name,
                    'message': f'策略已切换为: {new_strategy_name}'
                }
            })
        except Exception as e:
            logger.error(f"切换策略失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/strategy/params', methods=['GET'])
    def get_strategy_params():
        try:
            params = {}
            if current_strategy_name == 'trend_grid':
                params = {
                    'trend_filter': config.get('trend_filter', {}),
                    'auto_unit': config.get('auto_unit', {}),
                    'risk_control': config.get('risk_control', {})
                }
            params['grid'] = config.get('grid', {})

            return jsonify({
                'success': True,
                'data': {
                    'strategy': current_strategy_name,
                    'params': params
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/config/settings', methods=['GET'])
    def get_settings():
        return jsonify({'success': True, 'data': config})

    @app.route('/api/config/notification', methods=['PUT'])
    def update_notification():
        try:
            req_data = request.get_json()
            config['notification']['server酱_key'] = req_data.get('server酱_key', '')
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/config/notification/test', methods=['POST'])
    def test_notification():
        try:
            notifier.send_test()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/config/data_source', methods=['PUT'])
    def update_data_source():
        try:
            req_data = request.get_json()
            if 'data_source' not in config:
                config['data_source'] = {}
            config['data_source']['index'] = req_data.get('index', 'auto')
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/config/credentials', methods=['PUT'])
    def update_credentials():
        try:
            req_data = request.get_json()
            config['credentials']['username'] = req_data.get('username', '')
            config['credentials']['password'] = req_data.get('password', '')
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/config/credentials/test', methods=['POST'])
    def test_credentials():
        try:
            from engines.data import DataEngine
            test_data = DataEngine(config['market']['etf_code'])
            price = test_data.get_current_price()
            return jsonify({'success': True, 'data': {'price': price}})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/config/ai_model', methods=['PUT'])
    def update_ai_model():
        try:
            req_data = request.get_json()
            if 'ai_model' not in config:
                config['ai_model'] = {}
            config['ai_model']['provider'] = req_data.get('provider', 'minimax')
            config['ai_model']['model'] = req_data.get('model', 'MiniMax-Text-01')
            config['ai_model']['api_key'] = req_data.get('api_key', '')
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/logs', methods=['GET'])
    def get_logs():
        try:
            lines = int(request.args.get('lines', 100))
            log_dir = config.get('logging', {}).get('dir', 'logs')
            log_file = os.path.join(log_dir, f'trading_{datetime.now().strftime("%Y%m%d")}.log')

            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            else:
                log_lines = []

            return jsonify({
                'success': True,
                'data': {
                    'log_file': log_file,
                    'count': len(log_lines),
                    'lines': [l.strip() for l in log_lines]
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/shutdown', methods=['POST'])
    def shutdown():
        try:
            trading_running.clear()
            logger.info("收到关闭信号")
            os._exit(0)
        except Exception as e:
            logger.error(f"关闭失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    return app, logger


def run_api_server(config_path: str = None, port: int = 5001):
    """运行API服务器"""
    app, logger = create_api_server(config_path)
    logger.info(f"启动API服务器 on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == '__main__':
    run_api_server()
