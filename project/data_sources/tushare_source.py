"""
Tushare数据源 - 使用Tushare获取行情数据
"""
from typing import Optional, List
from datetime import datetime, timedelta
import logging

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

from data_sources.base import BaseDataSource


class TushareDataSource(BaseDataSource):
    """
    Tushare数据源

    使用Tushare Pro获取A股/ETF数据
    优势：数据全面、质量高

    安装：pip install tushare
    配置：需要设置Tushare Token

    使用方式：
    1. 注册Tushare账号: https://tushare.pro
    2. 获取Token
    3. 设置环境变量 TUSHARE_TOKEN
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.name = "Tushare"
        self._price_cache: Optional[float] = None
        self._cache_timestamp: float = 0

        # 从环境变量获取token
        import os
        self.token = os.environ.get('TUSHARE_TOKEN', '')

        if TUSHARE_AVAILABLE and self.token:
            ts.set_token(self.token)
            self.pro = ts.pro_api()
        else:
            logging.warning("Tushare Token未设置，请设置环境变量 TUSHARE_TOKEN")
            self.pro = None

    def get_current_price(self) -> float:
        """获取当前价格"""
        if not TUSHARE_AVAILABLE or not self.pro:
            return self._get_mock_price()

        try:
            # 转换ETF代码为Tushare格式
            ts_code = self._to_ts_code(self.symbol)

            df = self.pro.daily(
                ts_code=ts_code,
                trade_date=datetime.now().strftime('%Y%m%d')
            )

            if not df.empty:
                price = float(df.iloc[0]['close'])
                self._price_cache = price
                self._cache_timestamp = datetime.now().timestamp()
                return price

        except Exception as e:
            logging.error(f"Tushare获取价格失败: {e}")

        return self._get_mock_price()

    def get_baseline_price(self) -> float:
        """获取基准价（前一日收盘）"""
        if not TUSHARE_AVAILABLE or not self.pro:
            return self._get_mock_price()

        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            ts_code = self._to_ts_code(self.symbol)

            df = self.pro.daily(
                ts_code=ts_code,
                trade_date=yesterday
            )

            if not df.empty:
                return float(df.iloc[0]['close'])

        except Exception as e:
            logging.error(f"Tushare获取基准价失败: {e}")

        return self._get_mock_price()

    def is_market_open(self) -> bool:
        """检查市场是否开盘"""
        now = datetime.now()
        current_time = now.time()

        if now.weekday() >= 5:
            return False

        from datetime import time as dtime
        if current_time < dtime(9, 30) or current_time > dtime(15, 0):
            return False

        return True

    def get_market_status(self) -> dict:
        """获取市场状态"""
        return {
            'symbol': self.symbol,
            'is_open': self.is_market_open(),
            'current_price': self._price_cache,
            'source': self.name
        }

    def get_historical_prices(self, start_date: str, end_date: str) -> List[float]:
        """获取历史价格序列"""
        if not TUSHARE_AVAILABLE or not self.pro:
            return []

        try:
            ts_code = self._to_ts_code(self.symbol)

            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', '')
            )

            # 按日期排序
            df = df.sort_values('trade_date')

            return df['close'].tolist()

        except Exception as e:
            logging.error(f"Tushare获取历史数据失败: {e}")
            return []

    def _to_ts_code(self, symbol: str) -> str:
        """转换代码为Tushare格式"""
        if symbol.startswith('51'):
            return f"{symbol}.SH"  # 上交所ETF
        else:
            return f"{symbol}.SZ"  # 深交所

    def _get_mock_price(self) -> float:
        """Mock价格（备用）"""
        import random
        return round(3.80 + random.uniform(-0.1, 0.1), 3)

    def get_data_info(self) -> dict:
        """获取数据源信息"""
        return {
            'source': self.name,
            'symbol': self.symbol,
            'is_historical': True,
            'note': '使用Tushare Pro数据，需要Token'
        }
