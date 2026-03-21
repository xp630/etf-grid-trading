"""
数据引擎 - 封装聚宽数据API
"""
import time
from typing import Optional

# 注意：实际使用时需要安装joinquant-sdk
# 这里使用占位符，实际部署时替换为真实API调用
try:
    import jqdatasdk as jq
    JQ_AVAILABLE = True
except ImportError:
    JQ_AVAILABLE = False
    jq = None


class DataEngine:
    """
    数据引擎

    负责从聚宽获取行情数据，包含：
    - 当前价格获取
    - 基准价获取（前一日收盘）
    - 重试机制
    """

    def __init__(self, symbol: str, retry_times: int = 3, retry_interval: float = 2.0):
        """
        初始化数据引擎

        Args:
            symbol: ETF代码，如 '510300'
            retry_times: 失败重试次数
            retry_interval: 重试间隔（秒）
        """
        self.symbol = symbol
        self.retry_times = retry_times
        self.retry_interval = retry_interval
        self._price_cache: Optional[float] = None
        self._cache_timestamp: float = 0

    def get_current_price(self) -> float:
        """
        获取当前价格（带重试）

        Returns:
            当前价格

        Raises:
            Exception: 重试3次后仍失败
        """
        last_error = None

        for attempt in range(self.retry_times):
            try:
                if JQ_AVAILABLE:
                    price = jq.get_price(self.symbol, frequency='current')
                else:
                    # Mock数据（测试用）
                    price = self._mock_price()

                self._price_cache = price
                self._cache_timestamp = time.time()
                return price

            except Exception as e:
                last_error = e
                if attempt < self.retry_times - 1:
                    time.sleep(self.retry_interval)
                    continue
                else:
                    raise Exception(
                        f"Failed to get price after {self.retry_times} attempts: {e}"
                    )

        raise last_error

    def get_baseline_price(self) -> float:
        """
        获取基准价（前一日收盘价）

        Returns:
            基准价
        """
        if JQ_AVAILABLE:
            return jq.get_yesterday_close(self.symbol)
        else:
            # Mock数据（测试用）
            return 3.80

    def get_price_with_cache(self, cache_seconds: float = 10) -> float:
        """
        获取价格（带缓存，避免频繁请求）

        Args:
            cache_seconds: 缓存有效期（秒）

        Returns:
            当前价格
        """
        now = time.time()

        if self._price_cache and (now - self._cache_timestamp) < cache_seconds:
            return self._price_cache

        return self.get_current_price()

    def _mock_price(self) -> float:
        """
        Mock价格生成（测试用）

        实际部署时应删除此方法
        """
        import random
        return round(3.80 + random.uniform(-0.1, 0.1), 3)

    def is_market_open(self) -> bool:
        """
        检查市场是否开盘

        Returns:
            是否开盘
        """
        from datetime import datetime, time as dtime

        now = datetime.now()
        current_time = now.time()

        # 简单判断：工作日9:30-15:00为开盘时间
        market_open = dtime(9, 30)
        market_close = dtime(15, 0)

        return (
            now.weekday() < 5 and  # 周一到周五
            market_open <= current_time <= market_close
        )

    def get_market_status(self) -> dict:
        """
        获取市场状态

        Returns:
            市场状态信息
        """
        return {
            'symbol': self.symbol,
            'is_open': self.is_market_open(),
            'current_price': self._price_cache,
            'cache_age': time.time() - self._cache_timestamp if self._cache_timestamp else None
        }