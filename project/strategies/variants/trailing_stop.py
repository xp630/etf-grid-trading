"""
追踪止损网格策略 - 带追踪止损的网格策略变体
"""
from typing import List, Dict, Any
from strategies.base import BaseStrategy, Signal


class TrailingStopGridStrategy(BaseStrategy):
    """
    追踪止损网格策略

    在基础网格策略基础上增加追踪止损功能：
    - 当持仓盈利达到 trailing_threshold 时启动追踪止损
    - 追踪止损线随价格上升而提高
    - 价格跌破追踪止损线时强制卖出
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "TrailingStopGridStrategy"

        # 策略组件（需外部注入）
        self.data = None
        self.execution = None
        self.risk = None
        self.tracker = None

        # 追踪止损配置
        self.trailing_threshold = config.get('trailing_threshold', 0.02)  # 盈利2%后启动
        self.trailing_stop = config.get('trailing_stop', 0.01)  # 追踪止损1%

        # 状态
        self.grid = None
        self.current_price = 0
        self.highest_price_since_buy = 0
        self.stop_loss_price = 0

    def check_signals(self) -> List[Signal]:
        """检查交易信号"""
        signals = []

        if not self.data or not self.grid:
            return signals

        # 获取当前价格
        self.current_price = self.data.get_current_price()

        # 检查是否有持仓
        positions = self.tracker.get_all_positions()
        has_position = len(positions) > 0

        if has_position:
            # 有持仓时检查是否需要追踪止损
            signals = self._check_trailing_stop(positions)
        else:
            # 无持仓时检查是否需要买入
            signals = self._check_buy_signal()

        return signals

    def _check_trailing_stop(self, positions) -> List[Signal]:
        """检查追踪止损信号"""
        signals = []

        for symbol, position in positions.items():
            avg_price = position.avg_price
            quantity = position.quantity

            # 计算从买入以来的最高价
            if self.highest_price_since_buy == 0:
                self.highest_price_since_buy = self.current_price

            # 更新最高价（只更新更高的价格）
            if self.current_price > self.highest_price_since_buy:
                self.highest_price_since_buy = self.current_price

            # 计算当前盈利比例
            profit_ratio = (self.current_price - avg_price) / avg_price

            # 如果盈利超过阈值，启动追踪止损
            if profit_ratio >= self.trailing_threshold:
                # 计算追踪止损价格（最高价的某个百分比以下）
                self.stop_loss_price = self.highest_price_since_buy * (1 - self.trailing_stop)

                # 检查是否触及追踪止损
                if self.current_price <= self.stop_loss_price:
                    signals.append(Signal(
                        action='sell',
                        price=self.current_price,
                        quantity=quantity,
                        level_index=position.level_index,
                        reason=f'trailing_stop: price={self.current_price}, stop={self.stop_loss_price}, profit={profit_ratio:.2%}'
                    ))
                    # 重置追踪止损状态
                    self.highest_price_since_buy = 0
                    self.stop_loss_price = 0

        return signals

    def _check_buy_signal(self) -> List[Signal]:
        """检查买入信号"""
        signals = []

        if self.current_price < self.grid.base_price:
            for level_idx in range(len(self.grid.get_levels())):
                level_price = self.grid.get_price_at_level(level_idx)
                if self.current_price < level_price and not self.tracker.is_level_holding(level_idx):
                    quantity = int(self.config.get('unit_size', 500) / level_price / 100) * 100
                    signals.append(Signal(
                        action='buy',
                        price=level_price,
                        quantity=quantity,
                        level_index=level_idx,
                        reason='grid_buy'
                    ))
                    # 重置追踪止损状态
                    self.highest_price_since_buy = 0
                    self.stop_loss_price = 0
                    break

        return signals

    def execute_signals(self, signals: List[Signal]) -> List[Dict[str, Any]]:
        """执行信号"""
        results = []

        for signal in signals:
            result = self.execution.place_order(
                action=signal.action,
                symbol=self.config.get('etf_code', '510300'),
                price=signal.price,
                quantity=signal.quantity,
                level_index=signal.level_index
            )
            results.append({
                'signal': signal,
                'result': result
            })

        return results

    def run_once(self) -> Dict[str, Any]:
        """运行一次策略"""
        if not self.data.is_market_open():
            return {'status': 'market_closed'}

        try:
            signals = self.check_signals()

            if not signals:
                return {'status': 'no_signal', 'current_price': self.current_price}

            results = self.execute_signals(signals)

            return {
                'status': 'executed',
                'signals': [(s.action, s.price) for s in signals],
                'results': results
            }

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def get_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        return {
            'name': self.name,
            'current_price': self.current_price,
            'trailing_threshold': self.trailing_threshold,
            'trailing_stop': self.trailing_stop,
            'highest_since_buy': self.highest_price_since_buy,
            'stop_loss_price': self.stop_loss_price,
            'is_tracking': self.highest_price_since_buy > 0
        }
