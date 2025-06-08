"""
交易所客户端基类

定义交易所客户端的抽象接口
"""

from abc import ABC, abstractmethod


class BaseExchangeClient(ABC):
    """交易所客户端基类"""
    
    @abstractmethod
    async def load_markets(self):
        """加载市场数据"""
        pass
    
    @abstractmethod
    async def fetch_ticker(self, symbol: str):
        """获取行情数据"""
        pass
    
    @abstractmethod
    async def fetch_balance(self, params=None):
        """获取账户余额"""
        pass
    
    @abstractmethod
    async def create_order(self, symbol: str, type: str, side: str, amount: float, price: float):
        """创建订单"""
        pass
    
    @abstractmethod
    async def close(self):
        """关闭连接"""
        pass 