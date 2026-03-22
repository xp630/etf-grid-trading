"""
趋势过滤网格策略 - 实盘版本

功能：
1. 自动计算买入单位（根据本金和配置）
2. MA20趋势过滤（三种模式切换）
3. 止损止盈风控

三种模式：
- FULL_GRID:  正常网格，低买高卖
- BUY_ONLY:    只买不卖，等反弹
- SELL_ONLY:   只卖不买，等回调
"""
from typing import List, Dict, Any, Optional
from collections import deque
from engines.data import DataEngine
from engines.execution import ExecutionEngine
from engines.risk import RiskEngine
from utils.position_tracker import PositionTracker
from utils.grid_calculator import GridCalculator


class TrendGridStrategy:
    """
    趋势过滤网格策略 - 实盘版本

    三种模式:
    - FULL_GRID:  正常网格，低买高卖
    - BUY_ONLY:    只买不卖，等反弹
    - SELL_ONLY:   只卖不买，等回调
    """

    MODE_FULL_GRID = "FULL_GRID"
    MODE_BUY_ONLY = "BUY_ONLY"
    MODE_SELL_ONLY = "SELL_ONLY"

    def __init__(
        self,
        data_engine: DataEngine,
        execution_engine: ExecutionEngine,
        risk_engine: RiskEngine,
        position_tracker: PositionTracker,
        config: Dict[str, Any] = None
    ):
        """
        初始化趋势网格策略

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

        # 网格参数
        self.levels = self.config.get('levels', 10)
        self.spacing = self.config.get('spacing', 0.05)
        self.unit_size = self.config.get('unit_size', 500)
        self.etf_code = self.config.get('etf_code', '510300')

        # 趋势过滤参数
        trend_config = self.config.get('trend_filter', {})
        self.trend_enabled = trend_config.get('enabled', True)
        self.ma_period = trend_config.get('ma_period', 20)
        self.trend_threshold = trend_config.get('trend_threshold', 0.05)
        self.confirm_days = trend_config.get('confirm_days', 1)

        # 自动单位参数
        auto_config = self.config.get('auto_unit', {})
        self.auto_unit_enabled = auto_config.get('enabled', True)
        self.position_ratio = auto_config.get('position_ratio', 0.50)
        self.min_unit = auto_config.get('min_unit', 100)

        # 风控参数
        risk_config = self.config.get('risk_control', {})
        self.stop_loss_pct = risk_config.get('stop_loss_pct', 0.03)
        self.take_profit_pct = risk_config.get('take_profit_pct', 0.08)
        self.trailing_stop_pct = risk_config.get('trailing_stop_pct', 0.02)

        # 状态
        self.grid: GridCalculator = None
        self.current_price: float = 0
        self.grid_base_price: float = 0

        # 趋势状态
        self.current_mode = self.MODE_FULL_GRID
        self.price_history: List[float] = []
        self.mode_history = deque(maxlen=5)

        # 持仓止损止盈状态
        self.position_entry_price: float = 0.0
        self.position_high_price: float = 0.0

        # AI分析配置
        self.ai_config = self.config.get('ai_model', {})
        self.ai_api_key = self.ai_config.get('api_key', '')
        self.ai_provider = self.ai_config.get('provider', 'minimax')
        self.ai_model = self.ai_config.get('model', 'MiniMax-M2.7-highspeed')
        self.ai_enabled = bool(self.ai_api_key)
        self.ai_market_status = None  # 缓存AI分析结果
        self.ai_last_update = 0  # 上次更新时间
        self.ai_update_interval = 300  # AI更新间隔（秒），避免频繁调用

        # 初始化网格
        self._init_grid()

    def _init_grid(self):
        """初始化网格"""
        baseline = self.data.get_baseline_price()
        self.grid_base_price = baseline
        self.grid = GridCalculator(
            base_price=baseline,
            levels=self.levels,
            spacing=self.spacing
        )
        self.current_price = baseline

    def _get_ai_market_analysis(self) -> Optional[Dict]:
        """
        获取AI市场分析

        Returns:
            AI分析结果 dict 或 None
        """
        import time

        # 限制更新频率
        current_time = time.time()
        if self.ai_market_status and (current_time - self.ai_last_update) < self.ai_update_interval:
            return self.ai_market_status

        if not self.ai_enabled:
            return None

        try:
            from utils.llm_service import LLMService

            llm = LLMService(
                api_key=self.ai_api_key,
                provider=self.ai_provider,
                model=self.ai_model
            )

            if not llm.enabled:
                return None

            # 获取历史价格用于分析
            prices = list(self.price_history)[-60:] if len(self.price_history) >= 60 else list(self.price_history)
            if len(prices) < 20:
                return None

            # 计算技术指标
            import pandas as pd
            import numpy as np
            prices_series = pd.Series(prices)
            indicators = {}
            indicators['MA5'] = prices_series.rolling(5).mean().iloc[-1]
            indicators['MA20'] = prices_series.rolling(20).mean().iloc[-1] if len(prices) >= 20 else prices_series.mean()
            indicators['MA60'] = prices_series.rolling(60).mean().iloc[-1] if len(prices) >= 60 else prices_series.mean()

            returns = prices_series.pct_change().dropna()
            indicators['Volatility'] = returns.std() * np.sqrt(250) * 100

            result = llm.analyze_market(prices, [], indicators)
            self.ai_market_status = result
            self.ai_last_update = current_time
            return result

        except Exception as e:
            print(f"AI分析失败: {e}")
            return None

    def _get_ai_adjusted_spacing(self) -> float:
        """
        根据AI分析获取调整后的网格间距

        Returns:
            调整后的网格间距
        """
        ai_result = self._get_ai_market_analysis()

        if not ai_result or ai_result.get('error'):
            return self.spacing  # 返回默认间距

        status = ai_result.get('status', '')

        # AI建议的间距
        grid_suggest = ai_result.get('grid_suggestion', '')
        if grid_suggest:
            try:
                # 尝试解析AI建议的间距，如 "5%" -> 0.05
                import re
                match = re.search(r'(\d+\.?\d*)%', grid_suggest)
                if match:
                    return float(match.group(1)) / 100
            except:
                pass

        # 根据市场状态调整
        if status == 'bull':
            return 0.06  # 牛市放大到6%
        elif status == 'bear':
            return 0.04  # 熊市缩小到4%
        elif status == 'sideways':
            return 0.05  # 震荡保持5%
        elif status == 'volatile':
            return 0.03  # 高波动缩小到3%

        return self.spacing

    def calculate_auto_unit(self, current_price: float, total_capital: float) -> int:
        """
        自动计算每格买入股数

        公式: unit_size = (total_capital × 持仓比例) ÷ (买入档位数 × 当前价格)

        Args:
            current_price: 当前价格
            total_capital: 总资金

        Returns:
            每格买入股数 (100的整数倍)
        """
        if not self.auto_unit_enabled:
            return self.unit_size

        buy_levels = self.levels // 2  # 买入档位 = 总档位的一半

        # 计算可用资金
        available_capital = total_capital * self.position_ratio

        # 计算每格可买股数
        raw_unit = available_capital / (buy_levels * current_price)

        # 向下取整到100股
        unit = int(raw_unit / 100) * 100

        # 确保至少100股
        return max(unit, self.min_unit)

    def _calculate_ma(self, prices: list) -> float:
        """计算MA"""
        if len(prices) < self.ma_period:
            return sum(prices) / len(prices)
        return sum(prices[-self.ma_period:]) / self.ma_period

    def _get_trend_mode(self, current_price: float) -> str:
        """
        根据价格和MA判断趋势模式

        Args:
            current_price: 当前价格

        Returns:
            趋势模式
        """
        if not self.trend_enabled:
            return self.MODE_FULL_GRID

        ma_value = self._calculate_ma(self.price_history)
        upper = ma_value * (1 + self.trend_threshold)
        lower = ma_value * (1 - self.trend_threshold)

        if current_price > upper:
            return self.MODE_SELL_ONLY
        elif current_price < lower:
            return self.MODE_BUY_ONLY
        else:
            return self.MODE_FULL_GRID

    def check_signals(self) -> List[Dict[str, Any]]:
        """
        检查交易信号

        Returns:
            信号列表
        """
        signals = []

        # 获取当前价格
        self.current_price = self.data.get_current_price()

        # 更新价格历史
        self.price_history.append(self.current_price)

        # 判断趋势模式
        preliminary_mode = self._get_trend_mode(self.current_price)

        # 模式确认
        self.mode_history.append(preliminary_mode)
        if len(self.mode_history) >= self.confirm_days:
            if all(m == preliminary_mode for m in self.mode_history):
                if preliminary_mode != self.current_mode:
                    # 模式切换日志将在外层处理
                    self.current_mode = preliminary_mode

        # 动态调整基准价和网格间距
        if self.current_mode != self.MODE_FULL_GRID:
            ma_value = self._calculate_ma(self.price_history)
            self.grid_base_price = ma_value

        # AI动态调整网格间距
        ai_adjusted_spacing = self._get_ai_adjusted_spacing()
        if ai_adjusted_spacing != self.spacing:
            # AI建议调整间距，重新计算网格
            self.grid = GridCalculator(
                base_price=self.grid_base_price,
                levels=self.levels,
                spacing=ai_adjusted_spacing
            )
        elif self.current_mode != self.MODE_FULL_GRID:
            # 非FULL_GRID模式，使用标准间距
            self.grid = GridCalculator(
                base_price=self.grid_base_price,
                levels=self.levels,
                spacing=self.spacing
            )

        # 获取持仓信息
        position = self.tracker.get_position(self.etf_code)
        has_position = position is not None and position.quantity > 0

        if has_position:
            # 有持仓时：检查是否需要卖出
            entry_price = position.avg_price
            self.position_entry_price = entry_price
            if self.current_price > self.position_high_price:
                self.position_high_price = self.current_price

            sell_signal = self._check_sell_signal(
                current_price=self.current_price,
                entry_price=entry_price,
                quantity=position.quantity
            )
            if sell_signal:
                signals.append(sell_signal)
        else:
            # 无持仓时：检查是否需要买入
            self.position_entry_price = 0.0
            self.position_high_price = 0.0

            buy_signal = self._check_buy_signal(
                current_price=self.current_price,
                total_capital=self.risk.initial_capital
            )
            if buy_signal:
                signals.append(buy_signal)

        return signals

    def _check_sell_signal(
        self,
        current_price: float,
        entry_price: float,
        quantity: int
    ) -> Optional[Dict[str, Any]]:
        """
        检查卖出信号

        Args:
            current_price: 当前价格
            entry_price: 持仓均价
            quantity: 持仓数量

        Returns:
            卖出信号或None
        """
        stop_loss = entry_price * (1 - self.stop_loss_pct)
        take_profit = entry_price * (1 + self.take_profit_pct)
        trailing_stop = self.position_high_price * (1 - self.trailing_stop_pct)

        exit_reason = None
        sell_price = current_price

        # 1. 止损检查
        if current_price <= stop_loss:
            exit_reason = '止损'

        # 2. 止盈检查
        elif current_price >= take_profit:
            exit_reason = '止盈'

        # 3. 移动止损检查（需要价格从高点回落）
        elif (current_price <= trailing_stop and
              self.position_high_price > entry_price * (1 + self.take_profit_pct)):
            exit_reason = '移动止损'

        # 4. 网格卖出（震荡市，价格涨到上一档位）
        elif self.current_mode == self.MODE_FULL_GRID:
            if current_price > entry_price * (1 + self.spacing):
                exit_reason = '网格'

        # 5. 趋势反转卖出（SELL_ONLY模式，亏损时）
        elif self.current_mode == self.MODE_SELL_ONLY:
            if current_price < entry_price:
                if current_price <= stop_loss:
                    exit_reason = '止损'
                elif current_price <= trailing_stop:
                    exit_reason = '移动止损'

        if exit_reason:
            return {
                'action': 'sell',
                'price': sell_price,
                'quantity': quantity,
                'exit_reason': exit_reason,
                'entry_price': entry_price
            }

        return None

    def _check_buy_signal(
        self,
        current_price: float,
        total_capital: float
    ) -> Optional[Dict[str, Any]]:
        """
        检查买入信号

        Args:
            current_price: 当前价格
            total_capital: 总资金

        Returns:
            买入信号或None
        """
        if self.current_mode == self.MODE_SELL_ONLY:
            return None  # 上涨趋势不买入

        # 自动计算单位
        unit_size = self.calculate_auto_unit(current_price, total_capital)

        step = self.grid_base_price * self.spacing
        levels_below = self.levels // 2

        for i in range(levels_below):
            level_price = self.grid_base_price - (i + 1) * step
            if current_price <= level_price:
                buy_price = current_price
                quantity = unit_size
                cost = buy_price * quantity * (1 + self.execution.commission_rate + self.execution.slippage_rate)

                # 检查资金是否足够
                if cost <= total_capital:
                    return {
                        'action': 'buy',
                        'price': buy_price,
                        'quantity': quantity,
                        'level_price': level_price
                    }
                else:
                    # 资金不足，尝试用剩余资金买入
                    quantity = int(total_capital / buy_price / 100) * 100
                    if quantity >= 100:
                        return {
                            'action': 'buy',
                            'price': buy_price,
                            'quantity': quantity,
                            'level_price': level_price
                        }
                break

        return None

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
                level_index=0  # 实盘不追踪档位
            )

            results.append({
                'signal': signal,
                'result': result
            })

            # 更新持仓状态
            if result.get('success', False):
                if signal['action'] == 'buy':
                    self.position_entry_price = signal['price']
                    self.position_high_price = signal['price']
                else:
                    self.position_entry_price = 0.0
                    self.position_high_price = 0.0

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
                    'current_price': self.current_price,
                    'mode': self.current_mode
                }

            results = self.execute_signals(signals)

            return {
                'status': 'executed',
                'signals': signals,
                'results': results,
                'mode': self.current_mode
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
        ma_value = self._calculate_ma(self.price_history) if self.price_history else 0

        return {
            'current_price': current_price,
            'baseline_price': self.grid_base_price,
            'ma_value': ma_value,
            'current_mode': self.current_mode,
            'positions': {k: {'quantity': v.quantity, 'avg_price': v.avg_price}
                          for k, v in positions.items()},
            'total_position_value': self.tracker.get_total_value(current_price),
            'daily_pnl': daily_pnl,
            'grid_levels': len(self.grid.get_levels()) if self.grid else 0,
            'auto_unit': self.calculate_auto_unit(current_price, self.risk.initial_capital) if self.auto_unit_enabled else self.unit_size
        }
