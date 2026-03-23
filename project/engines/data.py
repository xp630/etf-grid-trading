"""
数据引擎 - 封装聚宽数据API
"""
import os
import time
from typing import Optional

import yaml

# 注意：实际使用时需要安装joinquant-sdk
# 这里使用占位符，实际部署时替换为真实API调用
try:
    import jqdatasdk as jq
    JQ_AVAILABLE = True
except ImportError:
    JQ_AVAILABLE = False
    jq = None


def _load_config():
    """从config.yaml加载配置"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


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
        self._data_date: str = None  # 数据日期（用于标注数据来源）

        # 聚宽认证（认证失败时自动切换Mock模式）
        self._use_mock = True  # 默认Mock模式
        if JQ_AVAILABLE:
            # 优先从环境变量读取，fallback 到 config.yaml
            username = os.environ.get('JQCLOUD_USERNAME')
            password = os.environ.get('JQCLOUD_PASSWORD')
            if not username or not password:
                cfg = _load_config()
                creds = cfg.get('credentials', {})
                username = username or creds.get('username', '')
                password = password or creds.get('password', '')
            if username and password:
                try:
                    jq.auth(username, password)
                    self._use_mock = False  # 认证成功，关闭Mock模式
                except Exception as e:
                    print(f"[DataEngine] 聚宽认证失败 ({e})，切换到Mock模式")
                    self._use_mock = True

        # 聚宽证券代码格式：ETF需要添加 .XSHG 后缀
        symbol_str = str(symbol)
        if symbol_str.startswith('51') and '.' not in symbol_str:
            self.full_symbol = f"{symbol_str}.XSHG"
        else:
            self.full_symbol = symbol_str

        # 初始化时获取可用日期范围
        self._init_date_range()

    def _init_date_range(self):
        """
        初始化日期范围 - 动态计算聚宽账号可访问的日期范围

        聚宽账号限制：距今15个月前 至 距今最近3个月
        通过实际查询来确定账号的有效日期范围
        """
        from datetime import datetime, timedelta

        today = datetime.now()

        # 计算3个月前的日期（使用月份减法）
        three_months_ago = self._subtract_months(today, 3)
        # 如果是周末，退回到上周五
        if three_months_ago.weekday() == 5:  # 周六
            three_months_ago -= timedelta(days=1)
        elif three_months_ago.weekday() == 6:  # 周日
            three_months_ago -= timedelta(days=2)

        theoretical_max = three_months_ago.strftime('%Y-%m-%d')

        # 计算15个月前的日期
        fifteen_months_ago = self._subtract_months(today, 15)
        theoretical_min = fifteen_months_ago.strftime('%Y-%m-%d')

        print(f"[DataEngine] 理论数据范围: {theoretical_min} ~ {theoretical_max}")

        # 通过实际查询验证账号的真实有效范围
        if not self._use_mock:
            try:
                all_days = jq.get_all_trade_days()
                # 找到理论范围内最后一个有效交易日
                actual_max = None
                for d in reversed(all_days):
                    if d.strftime('%Y-%m-%d') <= theoretical_max:
                        actual_max = d.strftime('%Y-%m-%d')
                        break

                # 验证这个日期是否真的可以访问（可能会超出账号权限）
                # 如果失败，持续往前找直到找到有效日期
                if actual_max:
                    verified_max = None
                    for d in reversed(all_days):
                        if d.strftime('%Y-%m-%d') > actual_max:
                            continue
                        try:
                            jq.get_price(self.full_symbol, end_date=d.strftime('%Y-%m-%d'), count=1, frequency='daily')
                            verified_max = d.strftime('%Y-%m-%d')
                            break
                        except Exception:
                            continue

                    if verified_max:
                        actual_max = verified_max
                    else:
                        # 找不到任何有效日期，使用理论最大值
                        actual_max = theoretical_max

                self._max_date = actual_max or theoretical_max
                self._min_date = theoretical_min
            except Exception as e:
                print(f"[DataEngine] 无法获取交易日期列表，使用理论范围: {e}")
                self._max_date = theoretical_max
                self._min_date = theoretical_min
        else:
            self._max_date = theoretical_max
            self._min_date = theoretical_min

        print(f"[DataEngine] 数据可用范围: {self._min_date} ~ {self._max_date}")

    def _subtract_months(self, date, months):
        """
        计算日期减去指定月数后的日期

        Args:
            date: datetime对象
            months: 要减去的月数

        Returns:
            减去指定月数后的日期
        """
        from datetime import datetime
        # 计算目标月份
        year = date.year
        month = date.month - months
        day = date.day

        while month <= 0:
            month += 12
            year -= 1

        # 处理目标月份天数少于原日期天数的情况（如3月31日 -> 2月没有31日）
        import calendar
        max_day = calendar.monthrange(year, month)[1]
        if day > max_day:
            day = max_day

        return datetime(year, month, day)

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
                if not self._use_mock:
                    # 使用get_price获取最后可用价格（不需要实时权限）
                    df = jq.get_price(self.full_symbol, end_date=self._max_date, count=1, frequency='daily')
                    price = df['close'].iloc[-1]
                    self._data_date = self._max_date
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
        获取基准价（最后可用收盘价）

        Returns:
            基准价
        """
        if not self._use_mock:
            # 获取最近一个交易日的数据（使用账号权限范围内的日期）
            all_days = jq.get_all_trade_days()
            # 找到在可访问范围内的最后交易日
            latest_valid = None
            for d in reversed(all_days):
                if d.strftime('%Y-%m-%d') <= self._max_date:
                    latest_valid = d.strftime('%Y-%m-%d')
                    break
            if not latest_valid:
                # 如果没找到，使用可访问范围的最大日期
                latest_valid = self._max_date

            df = jq.get_price(self.full_symbol, end_date=latest_valid, count=1, frequency='daily')
            self._data_date = latest_valid
            return df['close'].iloc[0]
        else:
            # Mock数据（测试用）
            self._data_date = 'mock'
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
        from utils.market_calendar import get_market_calendar
        return get_market_calendar().is_market_open()

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
            'cache_age': time.time() - self._cache_timestamp if self._cache_timestamp else None,
            'data_date': self._data_date,
            'data_source': 'JoinQuant历史数据' if not self._use_mock else 'Mock模拟数据',
            'data_range': f'{self._min_date} ~ {self._max_date}' if not self._use_mock else None
        }

    def get_data_info(self) -> dict:
        """
        获取数据来源信息（用于API返回）

        Returns:
            数据来源信息字典
        """
        return {
            'data_date': self._data_date,
            'data_source': 'JoinQuant历史数据' if not self._use_mock else 'Mock模拟数据',
            'data_range': f'{self._min_date} ~ {self._max_date}' if not self._use_mock else None,
            'is_historical': not self._use_mock
        }