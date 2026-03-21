"""
ETF网格交易系统 - 主程序入口
"""
import os
import sys
import time
import signal
import yaml
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engines.data import DataEngine
from engines.execution import ExecutionEngine
from engines.risk import RiskEngine
from utils.position_tracker import PositionTracker
from strategies.grid import GridStrategy
from notification.notifier import Notifier

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingSystem:
    """交易系统主类"""

    def __init__(self, config_path: str = 'config.yaml'):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

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

    def signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info("收到退出信号，正在停止...")
        self.running = False

    def is_trading_time(self) -> bool:
        """检查是否在交易时间内"""
        now = datetime.now()
        current_time = now.time()

        open_time = datetime.strptime(
            self.config['market']['trading_hours']['open'], '%H:%M'
        ).time()
        close_time = datetime.strptime(
            self.config['market']['trading_hours']['close'], '%H:%M'
        ).time()

        return (
            now.weekday() < 5 and  # 周一到周五
            open_time <= current_time <= close_time
        )

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
                    # 等待到下一个交易日
                    time.sleep(3600)
                    continue

                if total_assets < risk_status['stop_loss_line']:
                    logger.warning("触及总止损线，永久停止交易")
                    self.notifier.send_stop_loss(total_assets)
                    self.running = False
                    break

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