"""
JoinQuant数据源 - 使用聚宽API获取行情数据
"""
from typing import Optional, List
from datetime import datetime, timedelta
import logging

try:
    import jqdatasdk as jq
    JQ_AVAILABLE = True
except ImportError:
    JQ_AVAILABLE = False

from data_sources.base import BaseDataSource


class JoinQuantDataSource(BaseDataSource):
    """
    聚宽数据源

    使用 JoinQuant API 获取 A股/ETF 数据
    优势：数据权威、支持模拟交易

    安装：pip install jqdatasdk
    配置：设置 JQCLOUD_USERNAME 和 JQCLOUD_PASSWORD 环境变量
    """

    def __init__(self, symbol: str = '510300'):
        super().__init__({'symbol': symbol})
        self.name = "JoinQuant"
        self._price_cache: Optional[float] = None
        self._cache_timestamp: float = 0
        self._data_date: str = None
        self._authenticated = False

        # 聚宽证券代码格式
        symbol_str = str(self.symbol)
        if symbol_str.startswith('51') and '.' not in symbol_str:
            self.full_symbol = f"{symbol_str}.XSHG"
        else:
            self.full_symbol = symbol_str

        self._authenticate()
        self._init_date_range()

    def _authenticate(self):
        """聚宽认证"""
        if not JQ_AVAILABLE:
            raise ImportError("jqdatasdk 未安装，请运行: pip install jqdatasdk")

        import os
        username = os.environ.get('JQCLOUD_USERNAME')
        password = os.environ.get('JQCLOUD_PASSWORD')

        if not username or not password:
            raise RuntimeError("未设置 JQCLOUD_USERNAME/JQCLOUD_PASSWORD 环境变量")

        try:
            jq.auth(username, password)
            self._authenticated = True
            logging.info("[JoinQuant] 认证成功")
        except Exception as e:
            raise RuntimeError(f"聚宽认证失败: {e}")

    def _init_date_range(self):
        """初始化可访问的日期范围"""
        today = datetime.now()
        theoretical_max = self._subtract_months(today, 3)
        theoretical_min = self._subtract_months(today, 15)

        if theoretical_max.weekday() == 5:
            theoretical_max -= timedelta(days=1)
        elif theoretical_max.weekday() == 6:
            theoretical_max -= timedelta(days=2)

        self._max_date = theoretical_max.strftime('%Y-%m-%d')
        self._min_date = theoretical_min.strftime('%Y-%m-%d')

    def _subtract_months(self, date, months):
        from calendar import monthrange
        year = date.year
        month = date.month - months
        day = date.day
        while month <= 0:
            month += 12
            year -= 1
        max_day = monthrange(year, month)[1]
        if day > max_day:
            day = max_day
        return datetime(year, month, day)

    def get_current_price(self) -> float:
        """获取当前价格"""
        df = jq.get_price(
            self.full_symbol,
            end_date=self._max_date,
            count=1,
            frequency='daily'
        )
        price = float(df['close'].iloc[-1])
        self._price_cache = price
        self._cache_timestamp = datetime.now().timestamp()
        self._data_date = self._max_date
        return price

    def get_baseline_price(self) -> float:
        """获取基准价（前一日收盘）"""
        all_days = jq.get_all_trade_days()
        latest_valid = None
        for d in reversed(all_days):
            if d.strftime('%Y-%m-%d') <= self._max_date:
                latest_valid = d.strftime('%Y-%m-%d')
                break
        latest_valid = latest_valid or self._max_date

        df = jq.get_price(
            self.full_symbol,
            end_date=latest_valid,
            count=1,
            frequency='daily'
        )
        self._data_date = latest_valid
        return float(df['close'].iloc[0])

    def is_market_open(self) -> bool:
        """检查市场是否开盘"""
        now = datetime.now()
        current_time = now.time()
        if now.weekday() >= 5:
            return False
        from datetime import time as dtime
        return dtime(9, 30) <= current_time <= dtime(15, 0)

    def get_market_status(self) -> dict:
        """获取市场状态"""
        return {
            'symbol': self.symbol,
            'is_open': self.is_market_open(),
            'current_price': self._price_cache,
            'data_date': self._data_date,
            'source': self.name,
            'data_range': f'{self._min_date} ~ {self._max_date}',
            'is_historical': True,
        }

    def get_historical_prices(self, start_date: str, end_date: str) -> List[float]:
        """获取历史价格序列"""
        df = jq.get_price(
            self.full_symbol,
            start_date=start_date,
            end_date=end_date,
            frequency='daily'
        )
        return df['close'].tolist()

    def get_data_info(self) -> dict:
        """获取数据源信息"""
        return {
            'source': self.name,
            'symbol': self.symbol,
            'data_date': self._data_date,
            'data_range': f'{self._min_date} ~ {self._max_date}',
            'is_historical': True,
        }
