"""
中国A股市场日历工具
"""
from datetime import datetime, timedelta
from typing import List, Set
import logging

try:
    import pandas as pd
    import chinese_calendar as cc
    CHINESE_CALENDAR_AVAILABLE = True
except ImportError:
    CHINESE_CALENDAR_AVAILABLE = False


class MarketCalendar:
    """
    中国A股市场日历

    用于判断是否为交易日、获取交易日列表等
    """

    # A股主要节假日（每年固定日期，非精确）
    # 实际应以交易所公告为准
    KNOWN_HOLIDAYS = {
        # 元旦
        (1, 1): "元旦",
        # 春节（每年不同，需动态计算）
        # 清明节（每年不同）
        # 劳动节
        (5, 1): "劳动节",
        # 国庆节
        (10, 1): "国庆节",
        (10, 2): "国庆节",
        (10, 3): "国庆节",
    }

    def __init__(self):
        self._holidays_loaded = False
        self._holidays: Set[datetime] = set()
        self._trade_days: Set[datetime] = set()

    def _load_holidays(self, year: int = None):
        """加载节假日数据"""
        if year is None:
            year = datetime.now().year

        if self._holidays_loaded:
            return

        if CHINESE_CALENDAR_AVAILABLE:
            try:
                # 使用chinese_calendar库获取节假日
                self._holidays = set(cc.get_holidays(year))
                self._trade_days = set(cc.get_workdays(year))
                self._holidays_loaded = True
                logging.info(f"加载{year}年节假日: {len(self._holidays)}个")
                return
            except Exception as e:
                logging.warning(f"chinese_calendar加载失败: {e}")

        # 使用已知节假日
        self._holidays = self._get_known_holidays(year)
        self._holidays_loaded = True

    def _get_known_holidays(self, year: int) -> set:
        """获取已知节假日"""
        holidays = set()
        for (month, day), name in self.KNOWN_HOLIDAYS.items():
            try:
                holidays.add(datetime(year, month, day))
            except ValueError:
                pass  # 忽略无效日期
        return holidays

    def is_trade_day(self, date: datetime) -> bool:
        """
        判断是否为交易日

        Args:
            date: 日期

        Returns:
            是否为交易日
        """
        self._load_holidays(date.year)

        # 周末不是交易日
        if date.weekday() >= 5:
            return False

        # 节假日不是交易日
        # 清理时间部分，只保留日期
        date_only = datetime(date.year, date.month, date.day)
        if date_only in self._holidays:
            return False

        return True

    def is_market_open(self, date: datetime = None) -> bool:
        """
        判断市场是否开盘

        Args:
            date: 日期，默认为当前时间

        Returns:
            市场是否开盘
        """
        if date is None:
            date = datetime.now()

        # 检查是否为交易日
        if not self.is_trade_day(date):
            return False

        # 检查交易时间
        current_time = date.time()
        from datetime import time as dtime

        # 上午: 9:30 - 11:30
        # 下午: 13:00 - 15:00
        morning_open = dtime(9, 30)
        morning_close = dtime(11, 30)
        afternoon_open = dtime(13, 0)
        afternoon_close = dtime(15, 0)

        is_trading_time = (
            (morning_open <= current_time <= morning_close) or
            (afternoon_open <= current_time <= afternoon_close)
        )

        return is_trading_time

    def get_next_trade_day(self, date: datetime) -> datetime:
        """
        获取下一个交易日

        Args:
            date: 开始日期

        Returns:
            下一个交易日
        """
        next_date = date + timedelta(days=1)

        while not self.is_trade_day(next_date):
            next_date += timedelta(days=1)

            # 防止无限循环
            if (next_date - date).days > 365:
                return date

        return next_date

    def get_prev_trade_day(self, date: datetime) -> datetime:
        """
        获取上一个交易日

        Args:
            date: 开始日期

        Returns:
            上一个交易日
        """
        prev_date = date - timedelta(days=1)

        while not self.is_trade_day(prev_date):
            prev_date -= timedelta(days=1)

            # 防止无限循环
            if (date - prev_date).days > 365:
                return date

        return prev_date

    def get_trade_days_between(self, start: datetime, end: datetime) -> List[datetime]:
        """
        获取两个日期之间的所有交易日

        Args:
            start: 开始日期
            end: 结束日期

        Returns:
            交易日列表
        """
        trade_days = []
        current = start

        while current <= end:
            if self.is_trade_day(current):
                trade_days.append(current)
            current += timedelta(days=1)

        return trade_days


# 全局单例
_market_calendar = None


def get_market_calendar() -> MarketCalendar:
    """获取市场日历单例"""
    global _market_calendar
    if _market_calendar is None:
        _market_calendar = MarketCalendar()
    return _market_calendar


def is_market_open(date: datetime = None) -> bool:
    """判断市场是否开盘（快捷函数）"""
    return get_market_calendar().is_market_open(date)


def is_trade_day(date: datetime) -> bool:
    """判断是否为交易日（快捷函数）"""
    return get_market_calendar().is_trade_day(date)
