"""
Baostock数据源 - 使用Baostock获取行情数据
"""
from typing import Optional, List
from datetime import datetime, timedelta
import logging

try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
except ImportError:
    BAOSTOCK_AVAILABLE = False

from data_sources.base import BaseDataSource


class BaostockDataSource(BaseDataSource):
    """
    Baostock数据源

    使用 Baostock 获取 A股/ETF 数据
    优势：免费、稳定、无需 API Key

    安装：pip install baostock
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.name = "Baostock"
        self._price_cache: Optional[float] = None
        self._cache_timestamp: float = 0
        self._logged_in = False

        if not BAOSTOCK_AVAILABLE:
            raise ImportError("Baostock未安装，请运行: pip install baostock")

        self._login()

    def _login(self):
        """登录 Baostock"""
        if not BAOSTOCK_AVAILABLE:
            raise RuntimeError("Baostock未安装")
        lg = bs.login()
        if lg.error_code != '0':
            raise RuntimeError(f"Baostock登录失败: {lg.error_msg}")
        self._logged_in = True
        logging.info("[Baostock] 登录成功")

    def _logout(self):
        """登出 Baostock"""
        if self._logged_in:
            try:
                bs.logout()
            except Exception:
                pass
            self._logged_in = False

    def _ensure_login(self):
        """确保已登录"""
        if not self._logged_in:
            self._login()

    def _to_bs_code(self, symbol: str) -> str:
        """转换代码为 Baostock 格式"""
        if symbol.startswith('51'):
            return f"sh.{symbol}"
        return f"sz.{symbol}"

    def get_current_price(self) -> float:
        """获取当前价格（最近收盘价）"""
        self._ensure_login()
        bs_code = self._to_bs_code(self.symbol)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        rs = bs.query_history_k_data_plus(
            bs_code, "date,close",
            start_date=start_date, end_date=end_date,
            frequency="d", adjust="qfq"
        )

        data_list = []
        while rs.error_code == '0' and rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            raise RuntimeError(f"Baostock返回空数据: {self.symbol}")

        price = float(data_list[-1][1])
        self._price_cache = price
        self._cache_timestamp = datetime.now().timestamp()
        return price

    def get_baseline_price(self) -> float:
        """获取基准价（前一日收盘）"""
        self._ensure_login()
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        bs_code = self._to_bs_code(self.symbol)

        rs = bs.query_history_k_data_plus(
            bs_code, "date,close",
            start_date=yesterday, end_date=yesterday,
            frequency="d", adjust="qfq"
        )

        data_list = []
        while rs.error_code == '0' and rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            raise RuntimeError(f"Baostock返回空数据（基准价）: {self.symbol}")

        return float(data_list[0][1])

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
            'source': self.name,
        }

    def get_historical_prices(self, start_date: str, end_date: str) -> List[float]:
        """获取历史价格序列"""
        self._ensure_login()
        bs_code = self._to_bs_code(self.symbol)
        rs = bs.query_history_k_data_plus(
            bs_code, "date,close",
            start_date=start_date, end_date=end_date,
            frequency="d", adjust="qfq"
        )

        data_list = []
        while rs.error_code == '0' and rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            raise RuntimeError(f"Baostock返回空历史数据: {self.symbol}")

        return [float(row[1]) for row in data_list if row[1]]

    def get_data_info(self) -> dict:
        """获取数据源信息"""
        return {
            'source': self.name,
            'symbol': self.symbol,
            'is_historical': True,
            'note': '使用 Baostock 免费数据'
        }

    def __del__(self):
        self._logout()
