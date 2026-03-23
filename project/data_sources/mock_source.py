"""
Mock数据源 - 仅测试用
"""
import random
from typing import Optional, List

from data_sources.base import BaseDataSource


class MockDataSource(BaseDataSource):
    """
    Mock 数据源

    仅用于测试。config.yaml 中明确配置 mock 时使用。
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.name = "Mock"

    def get_current_price(self) -> float:
        return self._mock_price()

    def get_baseline_price(self) -> float:
        return 3.80

    def is_market_open(self) -> bool:
        from datetime import datetime
        now = datetime.now()
        current_time = now.time()
        if now.weekday() >= 5:
            return False
        from datetime import time as dtime
        return dtime(9, 30) <= current_time <= dtime(15, 0)

    def get_market_status(self) -> dict:
        return {
            'symbol': self.symbol,
            'is_open': self.is_market_open(),
            'current_price': self._mock_price(),
            'source': 'Mock',
        }

    def get_historical_prices(self, start_date: str, end_date: str) -> List[float]:
        return [3.80, 3.82, 3.79, 3.81, 3.83]

    def get_data_info(self) -> dict:
        return {
            'source': 'Mock',
            'symbol': self.symbol,
            'is_historical': False,
            'note': 'Mock 模拟数据，仅用于测试'
        }

    def _mock_price(self) -> float:
        return round(3.80 + random.uniform(-0.05, 0.05), 3)
