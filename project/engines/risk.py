"""
风控引擎 - 极致安全的风控检查
"""
from typing import Dict, Any
from utils.position_tracker import PositionTracker


class RiskEngine:
    """
    风控引擎

    执行所有下单前的风控检查，确保：
    1. 仓位不超过上限
    2. 日亏损不超过限制
    3. 总资产不触及止损线
    """

    def __init__(self, position_tracker: PositionTracker, config: Dict[str, Any]):
        """
        初始化风控引擎

        Args:
            position_tracker: 持仓追踪器
            config: 风控配置
                - max_position: 最大持仓金额（元）
                - max_daily_loss: 日最大亏损（元）
                - total_stop_loss: 总资产止损线（元）
                - initial_capital: 初始本金（元）
        """
        self.tracker = position_tracker
        self.max_position = config['max_position']
        self.max_daily_loss = config['max_daily_loss']
        self.total_stop_loss = config['total_stop_loss']
        self.initial_capital = config['initial_capital']

    def check_order(self, action: str, amount: float, price: float) -> Dict[str, Any]:
        """
        检查订单是否允许

        Args:
            action: 'buy' 或 'sell'
            amount: 订单金额（元）
            price: 价格

        Returns:
            {'allowed': bool, 'reason': str or None}
        """
        if action == 'buy':
            # 计算买入后的总持仓
            current_value = self.tracker.get_total_value(price)
            new_value = current_value + amount

            if new_value > self.max_position:
                return {
                    'allowed': False,
                    'reason': f'position_limit: current={current_value:.2f}, adding={amount:.2f}, max={self.max_position}'
                }

        return {'allowed': True, 'reason': None}

    def check_daily_loss(self, daily_pnl: float) -> Dict[str, Any]:
        """
        检查日亏损是否超限

        Args:
            daily_pnl: 当日盈亏（负数为亏损）

        Returns:
            {'allowed': bool, 'reason': str or None}
        """
        if daily_pnl < -self.max_daily_loss:
            return {
                'allowed': False,
                'reason': f'daily_loss: {daily_pnl:.2f} exceeds limit {self.max_daily_loss}'
            }

        return {'allowed': True, 'reason': None}

    def check_total_assets(self, total_assets: float) -> Dict[str, Any]:
        """
        检查总资产是否触及止损线

        Args:
            total_assets: 当前总资产

        Returns:
            {'allowed': bool, 'reason': str or None}
        """
        if total_assets < self.total_stop_loss:
            return {
                'allowed': False,
                'reason': f'stop_loss: total_assets={total_assets:.2f} below {self.total_stop_loss}'
            }

        return {'allowed': True, 'reason': None}

    def check_all(self, action: str, amount: float, price: float,
                  daily_pnl: float, total_assets: float) -> Dict[str, Any]:
        """
        执行所有风控检查

        Args:
            action: 'buy' 或 'sell'
            amount: 订单金额（元）
            price: 当前价格
            daily_pnl: 当日盈亏
            total_assets: 总资产

        Returns:
            {'allowed': bool, 'reason': str or None, 'checks': dict}
        """
        checks = {
            'order': self.check_order(action, amount, price),
            'daily_loss': self.check_daily_loss(daily_pnl),
            'total_assets': self.check_total_assets(total_assets)
        }

        # 所有检查都必须通过
        all_passed = all(c['allowed'] for c in checks.values())
        failed_reasons = [c['reason'] for c in checks.values() if not c['allowed']]

        return {
            'allowed': all_passed,
            'reason': '; '.join(failed_reasons) if failed_reasons else None,
            'checks': checks
        }

    def get_status(self, daily_pnl: float, total_assets: float) -> Dict[str, Any]:
        """
        获取当前风控状态

        Returns:
            风控状态摘要
        """
        return {
            'daily_pnl': daily_pnl,
            'daily_limit': self.max_daily_loss,
            'daily_remaining': self.max_daily_loss + daily_pnl,
            'total_assets': total_assets,
            'stop_loss_line': self.total_stop_loss,
            'position_limit': self.max_position
        }