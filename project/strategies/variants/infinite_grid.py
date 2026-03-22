"""
无限网格策略 - 无限加仓的网格策略变体
"""
from typing import List, Dict, Any
from strategies.base import BaseStrategy, Signal


class InfiniteGridStrategy(BaseStrategy):
    """
    无限网格策略

    与基础网格策略的区别：
    - 同一档位可以多次买入（无限加仓）
    - 卖出时按先进先出原则
    - 风险更高但收益也更高
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "InfiniteGridStrategy"

        # 策略组件（需外部注入）
        self.data = None
        self.execution = None
        self.risk = None
        self.tracker = None

        # 状态
        self.grid = None
        self.current_price = 0

    def check_signals(self) -> List[Signal]:
        """检查交易信号"""
        signals = []

        if not self.data or not self.grid:
            return signals

        # 获取当前价格
        self.current_price = self.data.get_current_price()

        # 检查是否需要买入（价格跌破档位）
        if self.current_price < self.grid.base_price:
            for level_idx in range(len(self.grid.get_levels())):
                level_price = self.grid.get_price_at_level(level_idx)
                if self.current_price < level_price:
                    # 无限网格不检查档位是否有持仓，直接买入
                    quantity = int(self.config.get('unit_size', 500) / level_price / 100) * 100
                    signals.append(Signal(
                        action='buy',
                        price=level_price,
                        quantity=quantity,
                        level_index=level_idx,
                        reason='infinite_grid_buy'
                    ))
                    break  # 每次最多一个信号

        # 检查是否需要卖出（有持仓且价格上涨）
        if self.current_price > self.grid.base_price:
            for level_idx in range(len(self.grid.get_levels()) - 1, -1, -1):
                level_price = self.grid.get_price_at_level(level_idx)
                if self.current_price > level_price:
                    # 检查该档位是否有持仓
                    positions = self.tracker.get_all_positions()
                    for symbol, position in positions.items():
                        if position.level_index == level_idx:
                            # 有持仓，卖出
                            signals.append(Signal(
                                action='sell',
                                price=level_price,
                                quantity=position.quantity,
                                level_index=level_idx,
                                reason='grid_sell'
                            ))
                            break
                    if signals:  # 找到卖出的就停止
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
        positions = self.tracker.get_all_positions() if self.tracker else {}
        return {
            'name': self.name,
            'current_price': self.current_price,
            'position_count': len(positions),
            'total_cost': sum(p.avg_price * p.quantity for p in positions.values())
        }
