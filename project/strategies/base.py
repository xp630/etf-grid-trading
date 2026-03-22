"""
策略基类 - 定义策略接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Signal:
    """交易信号"""
    action: str  # 'buy' or 'sell'
    price: float
    quantity: int
    level_index: int
    reason: str = ""


class BaseStrategy(ABC):
    """
    策略基类

    所有策略必须实现以下方法：
    - check_signals: 检查交易信号
    - execute_signals: 执行信号
    - run_once: 运行一次策略
    - get_status: 获取状态
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get('name', 'BaseStrategy')

    @abstractmethod
    def check_signals(self) -> List[Signal]:
        """检查交易信号"""
        pass

    @abstractmethod
    def execute_signals(self, signals: List[Signal]) -> List[Dict[str, Any]]:
        """执行信号"""
        pass

    @abstractmethod
    def run_once(self) -> Dict[str, Any]:
        """运行一次策略检查和执行"""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        pass

    def reset(self):
        """重置策略状态"""
        pass
