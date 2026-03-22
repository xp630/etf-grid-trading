"""
数据源工厂 - 根据配置创建数据源实例
"""
import logging
from typing import Optional

from data_sources.base import BaseDataSource
from data_sources.akshare_source import AKShareDataSource
from data_sources.tushare_source import TushareDataSource
from engines.data import DataEngine  # 现有的聚宽数据引擎


class DataSourceFactory:
    """
    数据源工厂

    根据配置创建合适的数据源实例

    支持的数据源：
    - joinquant: 聚宽（默认）
    - akshare: AKShare免费数据
    - tushare: Tushare Pro（需要Token）
    """

    _sources = {
        'joinquant': DataEngine,
        'akshare': AKShareDataSource,
        'tushare': TushareDataSource,
    }

    @classmethod
    def create(cls, source_name: str, config: dict) -> BaseDataSource:
        """
        创建数据源实例

        Args:
            source_name: 数据源名称 ('joinquant', 'akshare', 'tushare')
            config: 配置字典

        Returns:
            数据源实例
        """
        source_class = cls._sources.get(source_name.lower())

        if source_class is None:
            logging.warning(f"未知数据源 {source_name}，使用默认的聚宽")
            source_class = DataEngine

        # 传递必要的配置
        source_config = {
            'symbol': config.get('market', {}).get('etf_code', '510300'),
        }

        if source_name.lower() == 'joinquant':
            return source_class(source_config['symbol'])
        else:
            return source_class(source_config)

    @classmethod
    def register(cls, name: str, source_class: type):
        """注册新的数据源"""
        cls._sources[name.lower()] = source_class
        logging.info(f"注册数据源: {name}")

    @classmethod
    def list_sources(cls) -> list:
        """列出所有可用的数据源"""
        return list(cls._sources.keys())
