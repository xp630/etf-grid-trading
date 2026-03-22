"""
ETF网格交易系统 - 主程序入口
"""
import os
import sys
import time
import signal
import yaml
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engines.data import DataEngine
from engines.execution import ExecutionEngine
from engines.risk import RiskEngine
from utils.position_tracker import PositionTracker
from utils.market_calendar import get_market_calendar
from strategies.grid import GridStrategy
from notification.notifier import Notifier


def setup_logging(config: dict = None):
    """配置日志系统，支持文件输出"""
    if config is None:
        config = {}

    log_config = config.get('logging', {})
    log_dir = log_config.get('dir', 'logs')
    log_level = log_config.get('level', 'INFO')
    max_bytes = log_config.get('max_bytes', 10 * 1024 * 1024)
    backup_count = log_config.get('backup_count', 30)

    os.makedirs(log_dir, exist_ok=True)

    # 创建logger
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除已有的handlers
    logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出（按日期轮转）
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


class TradingSystem:
    """交易系统主类"""

    def __init__(self, config_path: str = 'config.yaml'):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 设置日志
        global logger
        logger = setup_logging(self.config)

        # 初始化数据库路径
        db_path = self.config['database']['path']
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # 初始化组件
        self.tracker = PositionTracker(db_path)
        self.risk = RiskEngine(self.tracker, self.config['risk'])
        self.data = DataEngine(self.config['market']['etf_code'])
        self.notifier = Notifier(self.config['notification'].get('server酱_key', ''))
        self.execution = ExecutionEngine(self.tracker, self.risk, self.data)

        # 初始化策略
        self.strategy = GridStrategy(
            data_engine=self.data,
            execution_engine=self.execution,
            risk_engine=self.risk,
            position_tracker=self.tracker,
            config=self.config['grid']
        )

        # 运行状态
        self.running = False
        self._last_summary_date: str = None  # 上次发送每日总结的日期

    def signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info("收到退出信号，正在停止...")
        self.running = False

    def is_trading_time(self) -> bool:
        """检查是否在交易时间内"""
        return get_market_calendar().is_market_open()

    def _is_market_close_time(self) -> bool:
        """检查是否接近收盘时间（14:55-15:00）"""
        now = datetime.now()
        current_time = now.time()
        close_time = datetime.strptime(
            self.config['market']['trading_hours']['cancel_before'], '%H:%M'
        ).time()
        # 在cancel_before时间后5分钟内
        return current_time >= close_time

    def _send_daily_summary(self):
        """发送每日总结"""
        today = datetime.now().strftime('%Y-%m-%d')
        if self._last_summary_date == today:
            return  # 今天已发送

        daily_pnl = self.tracker.get_daily_pnl()
        positions = self.tracker.get_all_positions()
        trades = self.tracker.get_trades(limit=50)

        success = self.notifier.send_daily_summary(
            daily_pnl=daily_pnl,
            trades=[{
                'action': t['action'],
                'symbol': t['symbol'],
                'price': t['price'],
                'quantity': t['quantity']
            } for t in trades],
            positions={k: {
                'quantity': v.quantity,
                'avg_price': v.avg_price
            } for k, v in positions.items()}
        )

        if success:
            self._last_summary_date = today
            logger.info("每日总结已发送")
        else:
            logger.warning("每日总结发送失败")

    def run(self):
        """运行交易系统"""
        logger.info("ETF网格交易系统启动")
        logger.info(f"配置: {self.config['market']['etf_code']}")

        # 注册信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.running = True

        while self.running:
            try:
                if not self.is_trading_time():
                    logger.info("非交易时间，等待...")
                    time.sleep(60)
                    continue

                # 执行策略
                result = self.strategy.run_once()

                if result['status'] == 'executed':
                    logger.info(f"执行信号: {result['signals']}")

                    # 发送微信通知
                    for item in result.get('results', []):
                        sig = item['signal']
                        res = item['result']

                        if res['success']:
                            self.notifier.send_trade(
                                sig['action'],
                                self.config['market']['etf_code'],
                                sig['price'],
                                sig['quantity']
                            )
                        else:
                            logger.error(f"下单失败: {res['reason']}")

                elif result['status'] == 'no_signal':
                    # 无信号时静默等待
                    pass

                elif result['status'] == 'error':
                    logger.error(f"策略执行错误: {result['message']}")
                    self.notifier.send_error(result['message'])

                # 检查风控状态
                daily_pnl = self.tracker.get_daily_pnl()
                current_price = self.data.get_current_price()
                initial_capital = self.config['risk']['initial_capital']
                total_assets = initial_capital + daily_pnl

                risk_status = self.risk.get_status(daily_pnl, total_assets)

                if risk_status['daily_remaining'] < 0:
                    logger.warning("触及日亏损限制，停止交易")
                    self.notifier.send_risk_warning('daily_loss', abs(daily_pnl))
                    # 发送每日总结后等待到下一个交易日
                    self._send_daily_summary()
                    time.sleep(3600)
                    continue

                if total_assets < risk_status['stop_loss_line']:
                    logger.warning("触及总止损线，永久停止交易")
                    self.notifier.send_stop_loss(total_assets)
                    self._send_daily_summary()
                    self.running = False
                    break

                # 检查是否接近收盘时间，发送每日总结
                if self._is_market_close_time():
                    self._send_daily_summary()

                # 每10秒循环
                time.sleep(10)

            except Exception as e:
                logger.error(f"系统异常: {e}")
                self.notifier.send_error(str(e))
                time.sleep(30)

        logger.info("交易系统已停止")


def main():
    """主函数"""
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'config.yaml'
    )

    if not os.path.exists(config_path):
        print(f"配置文件不存在: {config_path}")
        sys.exit(1)

    system = TradingSystem(config_path)
    system.run()


if __name__ == '__main__':
    main()