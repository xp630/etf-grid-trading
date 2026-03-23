"""
数据源工厂 - 根据配置创建数据源实例
"""
import logging
from typing import Dict

from data_sources.base import BaseDataSource
from data_sources.akshare_source import AKShareDataSource
from data_sources.baostock_source import BaostockDataSource
from data_sources.joinquant_source import JoinQuantDataSource
from data_sources.mock_source import MockDataSource


class DataSourceFactory:
    """
    数据源工厂

    根据配置创建合适的数据源实例。
    config.yaml 中指定什么就用什么，不自己降级。
    auto 模式按优先级尝试：joinquant → akshare → baostock，都失败才报错。

    支持的数据源：
    - joinquant: 聚宽（需要 JQCLOUD_USERNAME/JQCLOUD_PASSWORD）
    - akshare: AKShare 免费数据（需要安装 akshare）
    - baostock: Baostock 免费数据（需要安装 baostock）
    - mock: 仅测试用（config.yaml 明确配置 mock 时使用）
    """

    _sources: Dict[str, type] = {
        'joinquant': JoinQuantDataSource,
        'akshare': AKShareDataSource,
        'baostock': BaostockDataSource,
        'mock': MockDataSource,
    }

    # auto 模式的 fallback 顺序
    _auto_order = ['joinquant', 'akshare', 'baostock']

    @classmethod
    def create(cls, source_name: str, config: dict = None) -> BaseDataSource:
        """
        创建数据源实例。

        Args:
            source_name: 数据源名称 ('joinquant', 'akshare', 'baostock', 'mock', 'auto')
            config: 配置字典

        Returns:
            BaseDataSource 实例

        Raises:
            RuntimeError: 指定数据源不可用时抛出
        """
        source_name = (source_name or 'mock').lower()

        if source_name == 'auto':
            return cls._create_auto(config)
        elif source_name == 'mock':
            logging.info("[DataSourceFactory] 使用 mock 数据源（明确配置）")
            return MockDataSource(config)
        else:
            return cls._create_single(source_name, config)

    @classmethod
    def _create_single(cls, source_name: str, config: dict = None) -> BaseDataSource:
        """创建单一指定数据源，失败则抛出异常"""
        source_class = cls._sources.get(source_name)
        if source_class is None:
            raise ValueError(f"未知数据源: {source_name}，可选值: {list(cls._sources.keys())}")

        logging.info(f"[DataSourceFactory] 创建数据源: {source_class.__name__}")

        if source_name == 'joinquant':
            symbol = (config or {}).get('market', {}).get('etf_code', '510300') if config else '510300'
            return source_class(symbol)
        else:
            return source_class(config)

    @classmethod
    def _create_auto(cls, config: dict = None) -> BaseDataSource:
        """auto 模式：按优先级尝试各数据源，直到成功"""
        last_error = None

        for source_name in cls._auto_order:
            try:
                logging.info(f"[DataSourceFactory] auto 模式尝试: {source_name}")
                ds = cls._create_single(source_name, config)
                # 测试连通性
                ds.get_current_price()
                logging.info(f"[DataSourceFactory] auto 模式成功: {source_name}")
                return ds
            except Exception as e:
                logging.warning(f"[DataSourceFactory] {source_name} 不可用: {e}")
                last_error = e
                continue

        raise RuntimeError(
            f"所有数据源都不可用（已尝试: {cls._auto_order}），"
            f"最后错误: {last_error}"
        )

    @classmethod
    def register(cls, name: str, source_class: type):
        """注册新的数据源"""
        cls._sources[name.lower()] = source_class
        logging.info(f"[DataSourceFactory] 注册数据源: {name}")

    @classmethod
    def list_sources(cls) -> list:
        """列出所有可用的数据源"""
        return list(cls._sources.keys())
