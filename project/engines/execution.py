"""
执行引擎 - 订单管理与执行
"""
from typing import Dict, Any, Optional
from engines.risk import RiskEngine
from engines.data import DataEngine
from utils.position_tracker import PositionTracker


class ExecutionEngine:
    """
    执行引擎

    负责：
    1. 订单下单（买入/卖出）
    2. 订单取消
    3. 订单状态查询
    4. 成交处理
    """

    def __init__(self,
                 position_tracker: PositionTracker,
                 risk_engine: RiskEngine,
                 data_engine: DataEngine = None):
        """
        初始化执行引擎

        Args:
            position_tracker: 持仓追踪器
            risk_engine: 风控引擎
            data_engine: 数据引擎（可选，用于获取当前价）
        """
        self.tracker = position_tracker
        self.risk = risk_engine
        self.data = data_engine
        self._pending_orders: Dict[str, Dict] = {}

    def place_order(self,
                    action: str,
                    symbol: str,
                    price: float,
                    quantity: int,
                    level_index: int = None) -> Dict[str, Any]:
        """
        下单

        Args:
            action: 'buy' 或 'sell'
            symbol: 标的代码
            price: 价格
            quantity: 数量（股数）
            level_index: 档位索引（用于风控记录）

        Returns:
            {'success': bool, 'order_id': str or None, 'reason': str or None}
        """
        amount = price * quantity

        # 获取当日盈亏和总资产用于风控检查
        daily_pnl = self.tracker.get_daily_pnl()
        # 从配置获取初始资金
        initial_capital = self.risk.initial_capital
        # 估算总资产 = 初始资金 + 当日盈亏
        position_value = self.tracker.get_total_value(price)
        total_assets = initial_capital + daily_pnl

        # 风控检查
        if action == 'buy':
            risk_result = self.risk.check_all(
                action='buy',
                amount=amount,
                price=price,
                daily_pnl=daily_pnl,
                total_assets=total_assets
            )

            if not risk_result['allowed']:
                return {
                    'success': False,
                    'order_id': None,
                    'reason': f"Risk check failed: {risk_result['reason']}"
                }

        # 尝试下单（实际部署时调用聚宽API）
        try:
            order_id = self._submit_order(action, symbol, price, quantity)

            if order_id:
                # 记录持仓（假设成交）
                if action == 'buy':
                    self.tracker.record_buy(symbol, price, quantity, level_index or 0)
                else:
                    self.tracker.record_sell(symbol, price, quantity, level_index or 0)

                return {
                    'success': True,
                    'order_id': order_id,
                    'reason': None
                }
            else:
                return {
                    'success': False,
                    'order_id': None,
                    'reason': 'Order submission failed'
                }

        except Exception as e:
            return {
                'success': False,
                'order_id': None,
                'reason': f'Order error: {str(e)}'
            }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        取消订单

        Args:
            order_id: 订单ID

        Returns:
            {'success': bool, 'reason': str or None}
        """
        try:
            # 实际部署时调用聚宽API
            success = self._do_cancel(order_id)

            if success and order_id in self._pending_orders:
                del self._pending_orders[order_id]

            return {'success': success, 'reason': None}

        except Exception as e:
            return {'success': False, 'reason': str(e)}

    def get_order_status(self, order_id: str) -> Optional[str]:
        """
        查询订单状态

        Args:
            order_id: 订单ID

        Returns:
            订单状态：'pending', 'filled', 'cancelled', 'rejected', None
        """
        if order_id in self._pending_orders:
            return self._pending_orders[order_id].get('status')

        # 实际部署时调用聚宽API查询
        return self._do_query_status(order_id)

    def _submit_order(self, action: str, symbol: str, price: float, quantity: int) -> Optional[str]:
        """
        提交订单到交易所

        实际部署时替换为真实的聚宽API调用
        """
        try:
            import jqdatasdk as jq
            # 实际下单
            order_id = jq.order(symbol, action, price, quantity)
            return order_id
        except:
            # Mock模式（测试用）
            import time
            return f"mock_order_{int(time.time())}"

    def _do_cancel(self, order_id: str) -> bool:
        """取消订单"""
        try:
            import jqdatasdk as jq
            return jq.cancel_order(order_id)
        except:
            return True  # Mock模式

    def _do_query_status(self, order_id: str) -> Optional[str]:
        """查询订单状态"""
        try:
            import jqdatasdk as jq
            return jq.get_order_status(order_id)
        except:
            return 'filled'  # Mock模式