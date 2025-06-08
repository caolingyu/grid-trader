"""
模拟交易所客户端

提供模拟交易功能，用于测试和演示
使用真实价格数据，但模拟账户余额和交易执行
"""

import asyncio
import logging
import time
import random
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from .base import BaseExchangeClient


class SimulationExchangeClient(BaseExchangeClient):
    """模拟交易所客户端"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.markets_loaded = False
        
        # 模拟市场数据
        self.market_data = {}
        self.price_data = {}
        self.order_book = {}
        
        # 模拟账户（从配置读取初始余额）
        self.initial_balances = {
            'USDT': getattr(config, 'SIMULATION_INITIAL_USDT', 1000.0),
            'BNB': getattr(config, 'SIMULATION_INITIAL_BNB', 0.0),
            'ETH': getattr(config, 'SIMULATION_INITIAL_ETH', 0.0),
            'BTC': getattr(config, 'SIMULATION_INITIAL_BTC', 0.0)
        }
        self.balances = self.initial_balances.copy()
        
        # 模拟订单管理
        self.orders = {}
        self.order_id_counter = 1
        self.trade_history = []
        
        # 真实价格数据API配置
        self.binance_api_base = "https://api.binance.com"
        self.price_cache = {}  # 价格缓存
        self.cache_duration = 5  # 缓存5秒
        
        # 交易对映射（模拟交易所格式 -> Binance格式）
        self.symbol_map = {
            'BNB/USDT': 'BNBUSDT',
            'ETH/USDT': 'ETHUSDT', 
            'BTC/USDT': 'BTCUSDT'
        }
        
        # 备用价格（网络异常时使用）
        self.fallback_prices = {
            'BNB/USDT': 600.0,
            'ETH/USDT': 3000.0,
            'BTC/USDT': 60000.0
        }
        
        self.logger.info("模拟交易所客户端初始化完成")
        self.logger.info(f"模拟账户初始余额: {self.initial_balances}")
    
    async def load_markets(self):
        """加载模拟市场数据"""
        try:
            # 模拟市场信息
            self.market_data = {
                'BNB/USDT': {
                    'id': 'BNBUSDT',
                    'symbol': 'BNB/USDT',
                    'base': 'BNB',
                    'quote': 'USDT',
                    'limits': {
                        'amount': {'min': 0.01, 'max': 10000},
                        'price': {'min': 0.01, 'max': 100000},
                        'cost': {'min': 10, 'max': 1000000}
                    },
                    'precision': {
                        'amount': 2,
                        'price': 2
                    }
                },
                'ETH/USDT': {
                    'id': 'ETHUSDT',
                    'symbol': 'ETH/USDT',
                    'base': 'ETH',
                    'quote': 'USDT',
                    'limits': {
                        'amount': {'min': 0.001, 'max': 1000},
                        'price': {'min': 0.01, 'max': 100000},
                        'cost': {'min': 10, 'max': 1000000}
                    },
                    'precision': {
                        'amount': 3,
                        'price': 2
                    }
                },
                'BTC/USDT': {
                    'id': 'BTCUSDT',
                    'symbol': 'BTC/USDT',
                    'base': 'BTC',
                    'quote': 'USDT',
                    'limits': {
                        'amount': {'min': 0.00001, 'max': 100},
                        'price': {'min': 0.01, 'max': 1000000},
                        'cost': {'min': 10, 'max': 10000000}
                    },
                    'precision': {
                        'amount': 5,
                        'price': 2
                    }
                }
            }
            
            # 初始化价格数据（使用备用价格，后续通过API更新）
            for symbol in self.market_data:
                fallback_price = self.fallback_prices[symbol]
                self.price_data[symbol] = {
                    'last': fallback_price,
                    'bid': fallback_price * 0.999,
                    'ask': fallback_price * 1.001,
                    'high': fallback_price * 1.05,
                    'low': fallback_price * 0.95,
                    'volume': 0,
                    'timestamp': time.time() * 1000,
                    'last_update': 0
                }
            
            self.markets_loaded = True
            self.logger.info(f"模拟市场数据加载完成，支持 {len(self.market_data)} 个交易对")
            
        except Exception as e:
            self.logger.error(f"加载模拟市场数据失败: {str(e)}")
            raise
    
    async def fetch_ticker(self, symbol: str):
        """获取真实行情数据（模拟交易模式）"""
        try:
            if symbol not in self.price_data:
                raise ValueError(f"不支持的交易对: {symbol}")
            
            # 获取真实价格数据
            await self._fetch_real_price(symbol)
            
            ticker = self.price_data[symbol].copy()
            ticker['symbol'] = symbol
            
            self.logger.debug(f"真实行情: {symbol} = {ticker['last']:.4f}")
            return ticker
            
        except Exception as e:
            self.logger.error(f"获取行情失败: {str(e)}")
            # 使用缓存或备用价格
            ticker = self.price_data[symbol].copy()
            ticker['symbol'] = symbol
            return ticker
    
    async def fetch_balance(self, params=None):
        """获取模拟账户余额"""
        try:
            balance = {
                'free': self.balances.copy(),
                'used': {asset: 0.0 for asset in self.balances},
                'total': self.balances.copy()
            }
            
            self.logger.debug(f"模拟余额: {balance['total']}")
            return balance
            
        except Exception as e:
            self.logger.error(f"获取模拟余额失败: {str(e)}")
            return {'free': {}, 'used': {}, 'total': {}}
    
    async def create_order(self, symbol: str, type: str, side: str, amount: float, price: float):
        """创建模拟订单"""
        try:
            order_id = str(self.order_id_counter)
            self.order_id_counter += 1
            
            # 检查余额
            if not await self._check_balance_for_order(symbol, side, amount, price):
                raise ValueError("余额不足")
            
            # 创建订单
            order = {
                'id': order_id,
                'symbol': symbol,
                'type': type,
                'side': side,
                'amount': amount,
                'price': price,
                'filled': 0.0,
                'remaining': amount,
                'status': 'open',
                'timestamp': time.time() * 1000,
                'fee': {'cost': 0, 'currency': 'USDT'}
            }
            
            self.orders[order_id] = order
            
            # 模拟订单执行
            if type == 'market':
                await self._execute_market_order(order)
            else:
                # 限价单暂时直接执行
                await self._execute_limit_order(order)
            
            self.logger.info(f"模拟订单创建: {order_id} | {side} {amount} {symbol} @ {price}")
            return order
            
        except Exception as e:
            self.logger.error(f"创建模拟订单失败: {str(e)}")
            raise
    
    async def create_market_order(self, symbol: str, side: str, amount: float, params: Optional[Dict] = None):
        """创建模拟市价订单"""
        # 获取当前价格
        ticker = await self.fetch_ticker(symbol)
        price = ticker['last']
        
        return await self.create_order(symbol, 'market', side, amount, price)
    
    async def fetch_order(self, order_id: str, symbol: str, params=None):
        """获取模拟订单信息"""
        try:
            if order_id not in self.orders:
                raise ValueError(f"订单不存在: {order_id}")
            
            return self.orders[order_id]
            
        except Exception as e:
            self.logger.error(f"获取模拟订单失败: {str(e)}")
            raise
    
    async def fetch_open_orders(self, symbol: str):
        """获取模拟未完成订单"""
        open_orders = [
            order for order in self.orders.values()
            if order['symbol'] == symbol and order['status'] == 'open'
        ]
        return open_orders
    
    async def cancel_order(self, order_id: str, symbol: str, params=None):
        """取消模拟订单"""
        try:
            if order_id not in self.orders:
                raise ValueError(f"订单不存在: {order_id}")
            
            order = self.orders[order_id]
            order['status'] = 'canceled'
            
            self.logger.info(f"模拟订单取消: {order_id}")
            return order
            
        except Exception as e:
            self.logger.error(f"取消模拟订单失败: {str(e)}")
            raise
    
    async def fetch_my_trades(self, symbol: str, limit: int = 10):
        """获取模拟交易历史"""
        trades = [
            trade for trade in self.trade_history
            if trade['symbol'] == symbol
        ]
        return trades[-limit:] if trades else []
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: Optional[int] = None):
        """获取真实K线数据"""
        try:
            limit = limit or 100
            
            # 获取Binance交易对符号
            binance_symbol = self.symbol_map.get(symbol)
            if not binance_symbol:
                raise ValueError(f"不支持的交易对: {symbol}")
            
            # 从Binance API获取K线数据
            url = f"{self.binance_api_base}/api/v3/klines"
            params = {
                "symbol": binance_symbol,
                "interval": self._convert_timeframe(timeframe),
                "limit": limit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 转换数据格式
                        ohlcv = []
                        for kline in data:
                            timestamp = float(kline[0])
                            open_price = float(kline[1])
                            high_price = float(kline[2])
                            low_price = float(kline[3])
                            close_price = float(kline[4])
                            volume = float(kline[5])
                            
                            ohlcv.append([timestamp, open_price, high_price, low_price, close_price, volume])
                        
                        self.logger.debug(f"获取真实K线数据: {symbol} {timeframe} {len(ohlcv)}条")
                        return ohlcv
                    else:
                        raise ValueError(f"API请求失败: {response.status}")
            
        except Exception as e:
            self.logger.error(f"获取K线数据失败: {str(e)}")
            # 返回空数据或使用备用数据
            return []
    
    async def close(self):
        """关闭模拟连接"""
        self.logger.info("模拟交易所连接已关闭")
    
    async def _fetch_real_price(self, symbol: str):
        """获取真实价格数据"""
        try:
            current_time = time.time()
            cache_key = f"{symbol}_price"
            
            # 检查缓存
            if cache_key in self.price_cache:
                cached_data, cache_time = self.price_cache[cache_key]
                if current_time - cache_time < self.cache_duration:
                    return  # 使用缓存数据
            
            # 获取Binance交易对符号
            binance_symbol = self.symbol_map.get(symbol)
            if not binance_symbol:
                self.logger.warning(f"未找到交易对映射: {symbol}")
                return
            
            # 从Binance API获取价格
            url = f"{self.binance_api_base}/api/v3/ticker/24hr"
            params = {"symbol": binance_symbol}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 解析价格数据
                        last_price = float(data['lastPrice'])
                        bid_price = float(data['bidPrice'])
                        ask_price = float(data['askPrice'])
                        high_price = float(data['highPrice'])
                        low_price = float(data['lowPrice'])
                        volume = float(data['volume'])
                        
                        # 更新价格数据
                        self.price_data[symbol].update({
                            'last': last_price,
                            'bid': bid_price,
                            'ask': ask_price,
                            'high': high_price,
                            'low': low_price,
                            'volume': volume,
                            'timestamp': time.time() * 1000,
                            'last_update': current_time
                        })
                        
                        # 更新缓存
                        self.price_cache[cache_key] = (self.price_data[symbol].copy(), current_time)
                        
                        self.logger.debug(f"获取真实价格: {symbol} = {last_price:.4f}")
                    else:
                        self.logger.warning(f"API请求失败: {response.status}")
                        
        except asyncio.TimeoutError:
            self.logger.warning(f"获取价格超时: {symbol}")
        except Exception as e:
            self.logger.warning(f"获取真实价格失败: {symbol} - {str(e)}")
            # 如果获取失败，保持现有价格数据不变
    
    async def _check_balance_for_order(self, symbol: str, side: str, amount: float, price: float) -> bool:
        """检查订单余额是否充足"""
        base_currency = symbol.split('/')[0]
        quote_currency = symbol.split('/')[1]
        
        if side == 'buy':
            # 买入需要报价货币
            required = amount * price
            available = self.balances.get(quote_currency, 0)
            return available >= required
        else:
            # 卖出需要基础货币
            available = self.balances.get(base_currency, 0)
            return available >= amount
    
    async def _execute_market_order(self, order: Dict[str, Any]):
        """执行模拟市价订单"""
        symbol = order['symbol']
        side = order['side']
        amount = order['amount']
        
        # 获取当前价格
        ticker = await self.fetch_ticker(symbol)
        execution_price = ticker['ask'] if side == 'buy' else ticker['bid']
        
        # 更新订单状态
        order['price'] = execution_price
        order['filled'] = amount
        order['remaining'] = 0
        order['status'] = 'closed'
        
        # 更新余额
        await self._update_balances(symbol, side, amount, execution_price)
        
        # 记录交易
        await self._record_trade(order)
    
    async def _execute_limit_order(self, order: Dict[str, Any]):
        """执行模拟限价订单（简化为立即执行）"""
        symbol = order['symbol']
        side = order['side']
        amount = order['amount']
        price = order['price']
        
        # 更新订单状态
        order['filled'] = amount
        order['remaining'] = 0
        order['status'] = 'closed'
        
        # 更新余额
        await self._update_balances(symbol, side, amount, price)
        
        # 记录交易
        await self._record_trade(order)
    
    async def _update_balances(self, symbol: str, side: str, amount: float, price: float):
        """更新模拟余额"""
        base_currency = symbol.split('/')[0]
        quote_currency = symbol.split('/')[1]
        
        if side == 'buy':
            # 买入：减少报价货币，增加基础货币
            cost = amount * price
            self.balances[quote_currency] -= cost
            self.balances[base_currency] += amount
        else:
            # 卖出：减少基础货币，增加报价货币
            revenue = amount * price
            self.balances[base_currency] -= amount
            self.balances[quote_currency] += revenue
        
        self.logger.debug(f"余额更新: {side} {amount} {symbol} @ {price}")
    
    async def _record_trade(self, order: Dict[str, Any]):
        """记录模拟交易"""
        trade = {
            'id': order['id'],
            'order': order['id'],
            'symbol': order['symbol'],
            'type': order['type'],
            'side': order['side'],
            'amount': order['filled'],
            'price': order['price'],
            'cost': order['filled'] * order['price'],
            'fee': order['fee'],
            'timestamp': order['timestamp']
        }
        
        self.trade_history.append(trade)
        self.logger.debug(f"交易记录: {trade}")
    
    def _timeframe_to_seconds(self, timeframe: str) -> int:
        """将时间框架转换为秒数"""
        timeframe_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400
        }
        return timeframe_map.get(timeframe, 3600)
    
    def _convert_timeframe(self, timeframe: str) -> str:
        """转换时间框架格式为Binance API格式"""
        timeframe_map = {
            '1m': '1m',
            '5m': '5m', 
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d'
        }
        return timeframe_map.get(timeframe, '1h')
    
    @property
    def exchange(self):
        """模拟exchange属性，返回市场信息"""
        class MockExchange:
            def market(self, symbol):
                return self.parent.market_data.get(symbol, {})
        
        mock = MockExchange()
        mock.parent = self
        return mock 

    async def update_simulation_balances(self, new_balances: Dict[str, float]):
        """更新模拟账户余额配置"""
        try:
            # 更新初始余额和当前余额
            for asset, amount in new_balances.items():
                if asset in ['USDT', 'BNB', 'ETH', 'BTC']:
                    self.initial_balances[asset] = float(amount)
                    self.balances[asset] = float(amount)
            
            self.logger.info(f"模拟账户余额已更新: {self.initial_balances}")
            return True
        except Exception as e:
            self.logger.error(f"更新模拟账户余额失败: {str(e)}")
            return False
    
    def get_simulation_balances(self) -> Dict[str, float]:
        """获取当前模拟账户余额配置"""
        return self.initial_balances.copy()
    
    async def reset_simulation_balances(self):
        """重置模拟账户余额到初始状态"""
        try:
            self.balances = self.initial_balances.copy()
            self.logger.info("模拟账户余额已重置到初始状态")
            return True
        except Exception as e:
            self.logger.error(f"重置模拟账户余额失败: {str(e)}")
            return False 