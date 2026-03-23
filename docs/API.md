# API 参考文档

> 面向开发者。本文档描述所有公开模块的类、方法和参数。

---

## 1. strategies/base.py

### Signal（数据类）

```python
@dataclass
class Signal:
    action: str          # "buy" 或 "sell"
    price: float         # 触发信号的价格
    quantity: int        # 交易数量（股数）
    level_index: int     # 触发信号的档位索引
    reason: str          # 信号原因描述
```

### BaseStrategy（抽象基类）

所有策略必须继承此类。

```python
class BaseStrategy(ABC):
    @abstractmethod
    def check_signals(self) -> List[Signal]:
        """检查是否有交易信号，返回信号列表（最多1个）"""
        pass

    @abstractmethod
    def execute_signals(self) -> List[Dict]:
        """执行 check_signals() 返回的信号"""
        pass

    @abstractmethod
    def run_once(self) -> Dict:
        """执行一次完整的策略迭代"""
        pass

    @abstractmethod
    def get_status(self) -> Dict:
        """返回策略当前状态"""
        pass
```

---

## 2. strategies/grid.py

### GridStrategy

基础网格策略。**生产环境推荐使用 `TrendGridStrategy`。**

```python
class GridStrategy(BaseStrategy):
    def __init__(
        self,
        data_engine: DataEngine,
        execution_engine: ExecutionEngine,
        risk_engine: RiskEngine,
        position_tracker: PositionTracker,
        config: Dict[str, Any]
    ):
        """
        参数：
            data_engine: 数据引擎实例
            execution_engine: 执行引擎实例
            risk_engine: 风控引擎实例
            position_tracker: 持仓追踪器实例
            config: 配置字典（来自 config.yaml 的 grid 节）
        """

    def check_signals(self) -> List[Signal]:
        """
        买入条件：price < baseline AND price < level_price AND 档位空仓
        卖出条件：price > level_price AND 档位有持仓
        每次最多返回 1 个信号
        """

    def execute_signals(self) -> List[Dict]:
        """执行 check_signals() 返回的信号列表"""

    def run_once(self) -> Dict:
        """
        返回：
            {
                "price": float,
                "baseline": float,
                "signal": Signal or None,
                "positions": Dict,
                "daily_pnl": float,
                "mode": "full_grid" | "buy_only" | "sell_only"
            }
        """

    def get_status(self) -> Dict:
        """返回当前策略状态"""
```

---

## 3. strategies/trend_grid_live.py

### TrendGridStrategy

增强版网格策略，支持趋势过滤、AI 间距调整、自动单位计算。

```python
class TrendGridStrategy(BaseStrategy):
    # 三种交易模式
    MODE_FULL_GRID = "full_grid"
    MODE_BUY_ONLY = "buy_only"
    MODE_SELL_ONLY = "sell_only"

    def __init__(
        self,
        data_engine: DataEngine,
        execution_engine: ExecutionEngine,
        risk_engine: RiskEngine,
        position_tracker: PositionTracker,
        config: Dict[str, Any],
        llm_service: Optional[LLMService] = None
    ):
        """
        额外参数：
            llm_service: AI 服务实例（可选，用于动态调整网格间距）
        """

    def check_signals(self) -> List[Signal]:
        """
        根据当前模式检查信号：
        - MODE_BUY_ONLY：只检查买入
        - MODE_SELL_ONLY：只检查卖出
        - MODE_FULL_GRID：买入 + 卖出
        """

    def run_once(self) -> Dict:
        """
        每次迭代：
        1. 获取当前价格
        2. 更新趋势模式
        3. 检查并执行信号
        4. 检查止损/止盈/移动止损
        """

    def _get_trend_mode() -> str:
        """
        基于 MA20 判断趋势：
        - price > MA20 × (1 + threshold) → SELL_ONLY
        - price < MA20 × (1 - threshold) → BUY_ONLY
        - 其他 → FULL_GRID
        """

    def _get_ai_market_analysis() -> Dict:
        """
        调用 AI 分析市场，返回调整后的 grid_spacing。
        仅当 llm_service 配置了才生效。
        """

    def _check_sell_signal() -> Optional[Signal]:
        """
        卖出检查顺序：
        1. 止损（亏损 ≥ stop_loss_pct）
        2. 止盈（盈利 ≥ take_profit_pct）
        3. 移动止损（从最高点回落 ≥ trailing_stop_pct）
        4. 网格卖出（价格涨过档位）
        """
```

---

## 4. strategies/variants/infinite_grid.py

### InfiniteGridStrategy

允许同一档位重复买入（无限层叠），使用 FIFO 卖出。

```python
class InfiniteGridStrategy(GridStrategy):
    """
    与 GridStrategy 的区别：
    - 买入时不检查档位是否已有持仓
    - 卖出时按 FIFO 顺序，先买的先卖
    """
```

---

## 5. strategies/variants/trailing_stop.py

### TrailingStopGridStrategy

网格策略 + 移动止损。

```python
class TrailingStopGridStrategy(GridStrategy):
    def __init__(self, ...):
        self.trailing_threshold = 0.02   # 2% 利润激活追踪
        self.trailing_stop = 0.01        # 1% 移动止损

    def _update_trailing_stop(price: float):
        """
        当利润 ≥ 2% 时激活追踪：
        - 记录历史最高价
        - 当价格从最高点回落 1% 时强制卖出
        """
```

---

## 6. engines/data.py

### DataEngine

```python
class DataEngine:
    def __init__(self, config: Dict[str, Any]):
        """
        初始化时自动认证聚宽（或使用 Mock 模式）。
        环境变量：JQCLOUD_USERNAME, JQCLOUD_PASSWORD
        """

    def get_current_price(self, symbol: str = "510300") -> float:
        """
        获取当前价格（含 3 次重试，间隔 2 秒）。
        失败时抛出异常或返回 Mock 价格。
        """

    def get_baseline_price(self, symbol: str = "510300") -> float:
        """获取前一交易日收盘价（作为网格基准价）"""

    def get_price_with_cache(self, symbol: str, cache_seconds: int = 10) -> float:
        """
        带缓存的价格获取，默认缓存 10 秒。
        避免高频调用 API。
        """

    def is_market_open(self) -> bool:
        """检查当前是否在交易时间内（09:30-15:00）"""

    def get_market_status(self) -> Dict[str, Any]:
        """
        返回：
            {
                "symbol": str,
                "is_open": bool,
                "price": float or None,
                "data_source": str,  # "akshare" / "joinquant" / "mock"
                "cache_hit": bool
            }
        """
```

---

## 7. engines/execution.py

### ExecutionEngine

```python
class ExecutionEngine:
    def __init__(
        self,
        risk_engine: RiskEngine,
        position_tracker: PositionTracker,
        notifier: Notifier,
        config: Dict[str, Any]
    ): ...

    def place_order(
        self,
        action: str,      # "buy" 或 "sell"
        price: float,
        quantity: int,
        symbol: str = "510300"
    ) -> Dict[str, Any]:
        """
        下单流程：
        1. RiskEngine.check_all() 验证
        2. _submit_order() 提交到聚宽
        3. PositionTracker.record_buy/sell() 记录
        4. Notifier.send_trade() 通知

        返回：
            {
                "success": bool,
                "order_id": str or None,
                "message": str
            }
        """

    def cancel_order(self, order_id: str) -> Dict[str, Any]: ...

    def get_order_status(self, order_id: str) -> Dict[str, Any]: ...

    def _submit_order(...) -> str:
        """
        内部方法：调用 jq.paper_order() 提交模拟订单。
        失败时返回 "mock_order_*"（模拟订单 ID）。
        """
```

---

## 8. engines/risk.py

### RiskEngine

```python
class RiskEngine:
    def __init__(
        self,
        position_tracker: PositionTracker,
        config: Dict[str, Any]
    ): ...

    def check_order(self, action: str, price: float, quantity: int) -> bool:
        """
        买入前检查：new_position ≤ max_position (5000 元)
        卖出前检查：无（卖出不增加风险）
        """

    def check_daily_loss(self) -> bool:
        """
        检查当日亏损是否超限。
        返回 True 表示超限（应停止交易）。
        """

    def check_total_assets(self, current_price: float) -> bool:
        """
        检查总资产是否触及止损线。
        总资产 = 持仓市值 + 现金
        总资产 < total_stop_loss (9000 元) → 永久停止
        """

    def check_all(
        self,
        action: str,
        price: float,
        quantity: int
    ) -> Tuple[bool, str]:
        """
        综合所有风控检查。
        返回：(是否通过, 失败原因)
        """

    def get_status(self) -> Dict[str, Any]:
        """
        返回：
            {
                "daily_remaining": float,   # 当日还能亏多少
                "stop_loss_line": float,    # 总资产止损线
                "position_limit": float     # 仓位上限
            }
        """
```

---

## 9. engines/metrics.py

### MetricsCalculator

```python
class MetricsCalculator:
    @staticmethod
    def calculate(
        prices: List[float],
        trades: List[Dict]
    ) -> Dict[str, float]:
        """
        计算回测指标：
        - total_return: 总收益率
        - annualized_return: 年化收益率
        - max_drawdown: 最大回撤
        - sharpe_ratio: 夏普比率
        - win_rate: 胜率
        - profit_factor: 盈亏比
        """

    @staticmethod
    def calculate_monthly_returns(
        prices: List[float],
        trades: List[Dict]
    ) -> Dict[str, float]:
        """计算月度收益率"""

    @staticmethod
    def calculate_drawdown_series(
        equity_curve: List[float]
    ) -> List[float]:
        """计算回撤序列"""
```

### MarketAnalyzer

```python
class MarketAnalyzer:
    def analyze_market_bear_bull(
        self,
        prices: List[float],
        ma_periods: List[int] = [5, 20, 60]
    ) -> str:
        """
        分析市场牛熊：
        返回："bull" / "bear" / "sideways" / "volatile"
        依据：MA 多头排列、波动率、价格动量
        """
```

---

## 10. utils/grid_calculator.py

### GridCalculator

```python
class GridCalculator:
    def __init__(
        self,
        base_price: float,
        levels: int = 10,
        spacing: float = 0.05
    ):
        """
        参数：
            base_price: 基准价（前一日收盘）
            levels: 单边档位数（总共 levels*2+1 档）
            spacing: 网格间距（百分比，如 0.05 表示 5%）
        """

    def get_levels(self) -> List[float]:
        """
        返回所有档位价格列表。
        例：base=3.80, levels=10, spacing=5%
        → [3.40, 3.49, 3.58, 3.67, 3.76, 3.80, 3.89, 3.98, 4.07, 4.16, 4.25]
        """

    def get_level_index(self, price: float) -> int:
        """
        返回价格对应的档位索引（0 = 最低档，len-1 = 最高档）
        """

    def get_price_at_level(self, index: int) -> float:
        """返回指定档位的参考价格"""
```

---

## 11. utils/position_tracker.py

### Position（数据类）

```python
@dataclass
class Position:
    symbol: str
    quantity: int       # 股数
    avg_price: float    # 加权平均买入价
    level_index: int    # 持仓所在档位
    buy_date: str       # 买入日期 "YYYY-MM-DD"
```

### PositionTracker

```python
class PositionTracker:
    def __init__(self, db_path: str = "trading.db"): ...

    def record_buy(
        self,
        symbol: str,
        price: float,
        quantity: int,
        level_index: int
    ) -> None:
        """
        记录买入：
        - 更新持仓数量和均价（加权平均）
        - 记录到 trades 表
        """

    def record_sell(
        self,
        symbol: str,
        price: float,
        quantity: int,
        level_index: int
    ) -> float:
        """
        记录卖出：
        - 按 FIFO 顺序减少持仓
        - 计算单笔盈利 = (卖出价 - 均价) × 数量
        - 记录到 trades 表
        返回盈利金额
        """

    def get_all_positions(self) -> Dict[str, Position]: ...

    def get_total_value(self, current_price: float) -> float:
        """持仓总市值 = Σ(quantity × current_price)"""

    def is_level_holding(self, level_index: int) -> bool:
        """检查某档位是否有持仓"""

    def get_trades(self) -> List[Dict]:
        """返回所有交易记录（含盈利）"""

    def get_daily_pnl(self) -> float:
        """当日已实现盈亏（当日卖出盈利之和）"""
```

---

## 12. utils/llm_service.py

### LLMService

```python
class LLMService:
    def __init__(
        self,
        provider: str,    # "minimax" / "openai" / "deepseek"
        model: str,
        api_key: str
    ): ...

    def analyze_market(
        self,
        symbol: str,
        prices: List[float],
        dates: List[str]
    ) -> Dict[str, Any]:
        """
        AI 市场分析：
        - 分析价格走势
        - 判断是否适合做网格
        - 给出策略建议
        返回解析后的分析结果字典
        """

    def analyze_market_stream(
        self,
        symbol: str,
        prices: List[float],
        dates: List[str]
    ) -> Iterator[str]:
        """
        流式版本（用于 Streamlit 实时展示）。
        Yields AI 返回的文本片段。
        """

    def recommend_strategy(
        self,
        market_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """基于市场分析推荐策略参数"""
```

---

## 13. data_sources/base.py

### BaseDataSource（抽象基类）

```python
class BaseDataSource(ABC):
    @abstractmethod
    def get_current_price(self, symbol: str) -> float: ...

    @abstractmethod
    def get_baseline_price(self, symbol: str) -> float: ...

    @abstractmethod
    def is_market_open(self) -> bool: ...

    @abstractmethod
    def get_market_status(self) -> Dict[str, Any]: ...

    @abstractmethod
    def get_historical_prices(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Tuple[List[str], List[float]]:
        """返回 (日期列表, 价格列表)"""
```

---

## 14. backtest/runner.py

### BacktestRunner

```python
class BacktestRunner:
    def __init__(
        self,
        initial_capital: float = 10000,
        grid_config: Dict[str, Any] = None,
        risk_config: Dict[str, Any] = None
    ): ...

    def run(
        self,
        price_data: List[float],
        dates: List[str]
    ) -> Dict[str, Any]:
        """
        运行回测：
        参数：
            price_data: 价格序列（与 dates 一一对应）
            dates: 日期序列
        返回：
            {
                "total_return": float,
                "annualized_return": float,
                "max_drawdown": float,
                "sharpe_ratio": float,
                "win_rate": float,
                "trade_count": int,
                "trades": List[Dict],
                "equity_curve": List[float]
            }
        """

    def generate_chart_html(self) -> str:
        """生成 Chart.js HTML 可视化（回撤图、收益曲线）"""

    def save_chart(self, filename: str = "backtest_chart.html"): ...
```

---

## 15. notification/notifier.py

### Notifier

```python
class Notifier:
    def __init__(self, server酱_key: str): ...

    def send(self, title: str, content: str) -> bool:
        """
        底层发送方法。
        返回是否发送成功。
        """

    def send_trade(
        self,
        action: str,      # "buy" 或 "sell"
        price: float,
        quantity: int,
        level_index: int,
        profit: float = None
    ) -> bool:
        """成交通知"""

    def send_risk_warning(
        self,
        warning_type: str,  # "daily_loss" / "position_limit"
        message: str
    ) -> bool:
        """风控警告"""

    def send_stop_loss(self, total_assets: float) -> bool:
        """总资产止损通知（紧急）"""

    def send_error(self, error_message: str) -> bool:
        """系统异常通知"""

    def send_daily_summary(
        self,
        daily_pnl: float,
        positions: Dict,
        trades: List[Dict],
        win_rate: float
    ) -> bool:
        """每日总结（14:55 自动发送）"""
```

---

*文档更新时间：2026-03-23*
