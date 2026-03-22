"""
AKShare数据源 - 使用AKShare获取行情数据
"""
from typing import Optional, List
from datetime import datetime, timedelta
import logging

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

from data_sources.base import BaseDataSource


class AKShareDataSource(BaseDataSource):
    """
    AKShare数据源

    使用AKShare获取A股/ETF实时和历史数据
    优势：免费、无需API密钥、支持多种数据源

    安装：pip install akshare
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.name = "AKShare"
        self._price_cache: Optional[float] = None
        self._cache_timestamp: float = 0

        if not AKSHARE_AVAILABLE:
            logging.warning("AKShare未安装，请运行: pip install akshare")

    def get_current_price(self) -> float:
        """获取当前价格（实时）"""
        if not AKSHARE_AVAILABLE:
            return self._get_mock_price()

        try:
            # 实时价格
            if self.symbol.startswith('51'):
                # ETF
                df = ak.fund_etf_hist_em(
                    symbol=self.symbol,
                    period="daily",
                    start_date=(datetime.now() - timedelta(days=7)).strftime('%Y%m%d'),
                    end_date=datetime.now().strftime('%Y%m%d'),
                    adjust="qfq"
                )
            else:
                # 股票
                df = ak.stock_zh_a_hist(
                    symbol=self.symbol,
                    period="daily",
                    start_date=(datetime.now() - timedelta(days=7)).strftime('%Y%m%d'),
                    end_date=datetime.now().strftime('%Y%m%d'),
                    adjust="qfq"
                )

            if not df.empty:
                price = float(df.iloc[-1]['收盘'])
                self._price_cache = price
                self._cache_timestamp = datetime.now().timestamp()
                return price

        except Exception as e:
            logging.error(f"AKShare获取价格失败: {e}")

        return self._get_mock_price()

    def get_baseline_price(self) -> float:
        """获取基准价（前一日收盘）"""
        if not AKSHARE_AVAILABLE:
            return self._get_mock_price()

        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

            if self.symbol.startswith('51'):
                df = ak.fund_etf_hist_em(
                    symbol=self.symbol,
                    period="daily",
                    start_date=yesterday,
                    end_date=yesterday,
                    adjust="qfq"
                )
            else:
                df = ak.stock_zh_a_hist(
                    symbol=self.symbol,
                    period="daily",
                    start_date=yesterday,
                    end_date=yesterday,
                    adjust="qfq"
                )

            if not df.empty:
                return float(df.iloc[-1]['收盘'])

        except Exception as e:
            logging.error(f"AKShare获取基准价失败: {e}")

        return self._get_mock_price()

    def is_market_open(self) -> bool:
        """检查市场是否开盘"""
        now = datetime.now()
        current_time = now.time()

        # 周一到周五 9:30-15:00
        if now.weekday() >= 5:  # 周六周日
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
        if not AKSHARE_AVAILABLE:
            return []

        try:
            if self.symbol.startswith('51'):
                df = ak.fund_etf_hist_em(
                    symbol=self.symbol,
                    period="daily",
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', ''),
                    adjust="qfq"
                )
            else:
                df = ak.stock_zh_a_hist(
                    symbol=self.symbol,
                    period="daily",
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', ''),
                    adjust="qfq"
                )

            return df['收盘'].tolist()

        except Exception as e:
            logging.error(f"AKShare获取历史数据失败: {e}")
            return []

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
            'note': '使用AKShare免费数据'
        }
