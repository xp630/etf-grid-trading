"""
数据引擎 - 封装数据源接口
"""
import time
from typing import Optional

from data_sources.factory import DataSourceFactory
from data_sources.base import BaseDataSource


class DataEngine:
    """
    数据引擎

    负责从配置的数据源获取行情数据。
    实际数据获取委托给 BaseDataSource 实现。
    """

    def __init__(self, config: dict):
        """
        初始化数据引擎

        Args:
            config: 完整配置字典（含 data_source.market 等节点）
        """
        self.config = config
        self.symbol = config.get('market', {}).get('etf_code', '510300')

        # 通过工厂创建数据源，由工厂处理 auto fallback 链
        source_name = config.get('data_source', {}).get('index', 'auto')
        self._source: BaseDataSource = DataSourceFactory.create(source_name, config)

        self._price_cache: Optional[float] = None
        self._cache_timestamp: float = 0

    def get_current_price(self) -> float:
        """
        获取当前价格（带缓存）

        Returns:
            当前价格
        """
        price = self._source.get_current_price()
        self._price_cache = price
        self._cache_timestamp = time.time()
        return price

    def get_baseline_price(self) -> float:
        """
        获取基准价（前一日收盘）

        Returns:
            基准价
        """
        return self._source.get_baseline_price()

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

    def is_market_open(self) -> bool:
        """
        检查市场是否开盘

        Returns:
            是否开盘
        """
        return self._source.is_market_open()

    def get_market_status(self) -> dict:
        """
        获取市场状态

        Returns:
            市场状态信息
        """
        return self._source.get_market_status()

    def get_data_info(self) -> dict:
        """
        获取数据来源信息（用于API返回）

        Returns:
            数据来源信息字典
        """
        return self._source.get_data_info()
