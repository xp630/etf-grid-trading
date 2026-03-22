"""
数据源基类 - 定义数据源接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime


class BaseDataSource(ABC):
    """
    数据源基类

    所有数据源必须实现以下方法：
    - get_current_price: 获取当前价格
    - get_baseline_price: 获取基准价（前一日收盘）
    - is_market_open: 检查市场是否开盘
    - get_market_status: 获取市场状态
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.symbol = self.config.get('symbol', '510300')

    @abstractmethod
    def get_current_price(self) -> float:
        """获取当前价格"""
        pass

    @abstractmethod
    def get_baseline_price(self) -> float:
        """获取基准价（前一日收盘）"""
        pass

    @abstractmethod
    def is_market_open(self) -> bool:
        """检查市场是否开盘"""
        pass

    @abstractmethod
    def get_market_status(self) -> dict:
        """获取市场状态"""
        pass

    @abstractmethod
    def get_historical_prices(self, start_date: str, end_date: str) -> List[float]:
        """获取历史价格序列"""
        pass

    def get_data_info(self) -> dict:
        """获取数据源信息"""
        return {
            'source': self.__class__.__name__,
            'symbol': self.symbol,
            'is_historical': True
        }
