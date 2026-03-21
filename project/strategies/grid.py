"""
网格策略 - 核心交易策略
"""
from typing import List, Dict, Any
from engines.data import DataEngine
from engines.execution import ExecutionEngine
from engines.risk import RiskEngine
from utils.position_tracker import PositionTracker
from utils.grid_calculator import GridCalculator


class GridStrategy:
    """
    网格策略

    核心逻辑：
    1. 监控价格变动
    2. 当价格跌破某档位且该档位空仓时，买入
    3. 当价格涨破某档位且该档位有持仓时，卖出
    """

    def __init__(self,
                 data_engine: DataEngine,
                 execution_engine: ExecutionEngine,
                 risk_engine: RiskEngine,
                 position_tracker: PositionTracker,
                 config: Dict[str, Any] = None):
        """
        初始化网格策略

        Args:
            data_engine: 数据引擎
            execution_engine: 执行引擎
            risk_engine: 风控引擎
            position_tracker: 持仓追踪器
            config: 策略配置
        """
        self.data = data_engine
        self.execution = execution_engine
        self.risk = risk_engine
        self.tracker = position_tracker

        # 配置
        self.config = config or {}
        self.levels = self.config.get('levels', 10)
        self.spacing = self.config.get('spacing', 0.05)
        self.unit_size = self.config.get('unit_size', 500)
        self.etf_code = self.config.get('etf_code', '510300')

        # 状态
        self.grid: GridCalculator = None
        self.current_price: float = 0
        self.last_processed_level: int = None

        # 初始化网格
        self._init_grid()

    def _init_grid(self):
        """初始化网格"""
        baseline = self.data.get_baseline_price()
        self.grid = GridCalculator(
            base_price=baseline,
            levels=self.levels,
            spacing=self.spacing
        )
        self.current_price = baseline

    def check_signals(self) -> List[Dict[str, Any]]:
        """
        检查交易信号

        Returns:
            信号列表，每个信号包含：
            - action: 'buy' 或 'sell'
            - price: 价格
            - quantity: 数量
            - level_index: 档位索引
        """
        signals = []

        # 获取当前价格
        self.current_price = self.data.get_current_price()

        # 确定当前价格所在的档位
        current_level = self.grid.get_level_index(self.current_price)

        # 检查是否需要买入（价格跌破档位，且该档位空仓）
        # 只有当 current_price < level_price 且 price >= 基准价 才买入
        # 当 price < 基准价 时买入（表示已经从基准价下跌）
        if self.current_price < self.grid.base_price:
            for level_idx in range(len(self.grid.get_levels())):
                level_price = self.grid.get_price_at_level(level_idx)
                if self.current_price < level_price and not self.tracker.is_level_holding(level_idx):
                    # 计算买入数量（每格固定金额）
                    quantity = int(self.unit_size / level_price / 100) * 100  # 向下取整到百股

                    signals.append({
                        'action': 'buy',
                        'price': level_price,
                        'quantity': quantity,
                        'level_index': level_idx
                    })
                    break  # 每次最多处理一个信号

        # 检查是否需要卖出（价格涨超档位，且该档位有持仓）
        # 只有当 current_price > level_price 时才触发卖出
        for level_idx in range(len(self.grid.get_levels()) - 1, -1, -1):
            level_price = self.grid.get_price_at_level(level_idx)
            if self.current_price > level_price and self.tracker.is_level_holding(level_idx):
                position = self.tracker.get_position(self.etf_code)
                quantity = position.quantity if position else 100

                signals.append({
                    'action': 'sell',
                    'price': level_price,
                    'quantity': quantity,
                    'level_index': level_idx
                })
                break  # 每次最多处理一个信号

        return signals

    def execute_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        执行信号

        Args:
            signals: 信号列表

        Returns:
            执行结果列表
        """
        results = []

        for signal in signals:
            result = self.execution.place_order(
                action=signal['action'],
                symbol=self.etf_code,
                price=signal['price'],
                quantity=signal['quantity'],
                level_index=signal['level_index']
            )

            results.append({
                'signal': signal,
                'result': result
            })

        return results

    def run_once(self) -> Dict[str, Any]:
        """
        运行一次策略检查和执行

        Returns:
            执行结果摘要
        """
        if not self.data.is_market_open():
            return {
                'status': 'market_closed',
                'message': 'Market is not open'
            }

        try:
            signals = self.check_signals()

            if not signals:
                return {
                    'status': 'no_signal',
                    'current_price': self.current_price
                }

            results = self.execute_signals(signals)

            return {
                'status': 'executed',
                'signals': signals,
                'results': results
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    def get_status(self) -> Dict[str, Any]:
        """
        获取策略状态

        Returns:
            策略状态信息
        """
        positions = self.tracker.get_all_positions()
        daily_pnl = self.tracker.get_daily_pnl()
        current_price = self.data.get_current_price()

        return {
            'current_price': current_price,
            'baseline_price': self.grid.base_price if self.grid else None,
            'positions': {k: {'quantity': v.quantity, 'avg_price': v.avg_price}
                          for k, v in positions.items()},
            'total_position_value': self.tracker.get_total_value(current_price),
            'daily_pnl': daily_pnl,
            'grid_levels': len(self.grid.get_levels()) if self.grid else 0
        }