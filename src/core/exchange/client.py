"""
统一交易所客户端

基于原有exchange_client.py重构，提供更好的模块化和扩展性
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Optional

import ccxt.async_support as ccxt

from .base import BaseExchangeClient


def create_exchange_client(config):
    """工厂函数：根据配置创建交易所客户端"""
    if getattr(config, "SIMULATION_MODE", False):
        # 延迟导入避免循环依赖
        from .simulation_client import SimulationExchangeClient

        return SimulationExchangeClient(config)
    else:
        return ExchangeClient(config)


class ExchangeClient(BaseExchangeClient):
    """Binance交易所客户端实现"""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._verify_credentials()

        # 获取代理配置
        proxy = config.HTTP_PROXY

        # 初始化交易所实例
        self.exchange = ccxt.binance(
            {
                "apiKey": config.BINANCE_API_KEY,
                "secret": config.BINANCE_API_SECRET,
                "enableRateLimit": True,
                "timeout": config.API_TIMEOUT,
                "options": {
                    "defaultType": "spot",
                    "fetchMarkets": {
                        "spot": True,
                        "margin": False,
                        "swap": False,
                        "future": False,
                    },
                    "fetchCurrencies": False,
                    "recvWindow": config.RECV_WINDOW,
                    "adjustForTimeDifference": True,
                    "warnOnFetchOpenOrdersWithoutSymbol": False,
                    "createMarketBuyOrderRequiresPrice": False,
                },
                "aiohttp_proxy": proxy,
                "verbose": config.DEBUG_MODE,
            }
        )

        if proxy:
            self.logger.info(f"使用代理: {proxy}")

        self.logger.setLevel(config.LOG_LEVEL)
        self.logger.info("交易所客户端初始化完成")

        # 初始化状态
        self.markets_loaded = False
        self.time_diff = 0
        self.balance_cache = {"timestamp": 0, "data": None}
        self.funding_balance_cache = {"timestamp": 0, "data": {}}
        self.cache_ttl = 30  # 缓存有效期（秒）

    def _verify_credentials(self):
        """验证API密钥是否存在"""
        # 在模拟模式下跳过验证
        if getattr(self.config, "SIMULATION_MODE", False):
            return

        if not self.config.BINANCE_API_KEY or not self.config.BINANCE_API_SECRET:
            error_msg = "缺少必需的API密钥配置"
            self.logger.critical(error_msg)
            raise EnvironmentError(error_msg)

    async def load_markets(self):
        """加载市场数据"""
        try:
            # 先同步时间
            await self.sync_time()

            # 添加重试机制
            max_retries = 3
            for i in range(max_retries):
                try:
                    await self.exchange.load_markets()
                    self.markets_loaded = True
                    _ = self.exchange.market(self.config.symbol)
                    self.logger.info(f"市场数据加载成功 | 交易对: {self.config.symbol}")
                    return True
                except Exception:
                    if i == max_retries - 1:
                        raise
                    self.logger.warning(f"加载市场数据失败，重试 {i + 1}/{max_retries}")
                    await asyncio.sleep(2)

        except Exception as e:
            self.logger.error(f"加载市场数据失败: {str(e)}")
            self.markets_loaded = False
            raise

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: Optional[int] = None
    ):
        """获取K线数据"""
        try:
            params = {}
            if limit:
                params["limit"] = limit
            return await self.exchange.fetch_ohlcv(symbol, timeframe, params=params)
        except Exception as e:
            self.logger.error(f"获取K线数据失败: {str(e)}")
            raise

    async def fetch_ticker(self, symbol: str):
        """获取行情数据"""
        self.logger.debug(f"获取行情数据 {symbol}...")
        start = datetime.now()
        try:
            # 使用市场ID进行请求
            market = self.exchange.market(symbol)
            ticker = await self.exchange.fetch_ticker(market["id"])
            latency = (datetime.now() - start).total_seconds()
            self.logger.debug(
                f"获取行情成功 | 延迟: {latency:.3f}s | 最新价: {ticker['last']}"
            )
            return ticker
        except Exception as e:
            self.logger.error(f"获取行情失败: {str(e)}")
            self.logger.debug(f"请求参数: symbol={symbol}")
            raise

    async def fetch_funding_balance(self):
        """获取理财账户余额"""
        now = time.time()

        # 如果缓存有效，直接返回缓存数据
        if now - self.funding_balance_cache["timestamp"] < self.cache_ttl:
            return self.funding_balance_cache["data"]

        try:
            # 使用Simple Earn API
            result = await self.exchange.sapi_get_simple_earn_flexible_position()
            self.logger.debug(f"理财账户原始数据: {result}")
            balances = {}

            # 处理返回的数据结构
            data = result.get("rows", []) if isinstance(result, dict) else result

            for item in data:
                asset = item["asset"]
                amount = float(item.get("totalAmount", 0) or item.get("amount", 0))
                balances[asset] = amount

            # 只在余额发生显著变化时打印日志
            if not self.funding_balance_cache.get("data"):
                self.logger.info(f"理财账户余额: {balances}")
            else:
                # 检查是否有显著变化（超过0.1%）
                old_balances = self.funding_balance_cache["data"]
                significant_change = False
                for asset, amount in balances.items():
                    old_amount = old_balances.get(asset, 0)
                    if old_amount == 0:
                        if amount != 0:
                            significant_change = True
                            break
                    elif abs((amount - old_amount) / old_amount) > 0.001:  # 0.1%的变化
                        significant_change = True
                        break

                if significant_change:
                    self.logger.info(f"理财账户余额更新: {balances}")

            # 更新缓存
            self.funding_balance_cache = {"timestamp": now, "data": balances}

            return balances
        except Exception as e:
            self.logger.error(f"获取理财账户余额失败: {str(e)}")
            return {}

    async def fetch_balance(self, params=None):
        """获取账户余额（含缓存机制）"""
        now = time.time()
        if now - self.balance_cache["timestamp"] < self.cache_ttl:
            return self.balance_cache["data"]

        try:
            params = params or {}
            params["timestamp"] = int(time.time() * 1000) + self.time_diff
            balance = await self.exchange.fetch_balance(params)

            # 获取理财账户余额
            funding_balance = await self.fetch_funding_balance()

            # 合并现货和理财余额
            for asset, amount in funding_balance.items():
                if asset not in balance["total"]:
                    balance["total"][asset] = 0
                if asset not in balance["free"]:
                    balance["free"][asset] = 0
                balance["total"][asset] += amount

            self.logger.debug(f"账户余额概要: {balance['total']}")
            self.balance_cache = {"timestamp": now, "data": balance}
            return balance
        except Exception as e:
            self.logger.error(f"获取余额失败: {str(e)}")
            # 出错时不抛出异常，而是返回一个空的但结构完整的余额字典
            return {"free": {}, "used": {}, "total": {}}

    async def create_order(
        self, symbol: str, type: str, side: str, amount: float, price: float
    ):
        """创建订单"""
        try:
            # 在下单前重新同步时间
            await self.sync_time()
            # 添加时间戳到请求参数
            params = {
                "timestamp": int(time.time() * 1000) + self.time_diff,
                "recvWindow": self.config.RECV_WINDOW,
            }

            order = await self.exchange.create_order(
                symbol, type, side, amount, price, params
            )
            self.logger.info(
                f"订单创建成功: {order['id']} | {side} {amount} {symbol} @ {price}"
            )
            return order
        except Exception as e:
            self.logger.error(f"创建订单失败: {str(e)}")
            raise

    async def create_market_order(
        self, symbol: str, side: str, amount: float, params: Optional[Dict] = None
    ):
        """创建市价订单"""
        try:
            await self.sync_time()

            order_params = {
                "timestamp": int(time.time() * 1000) + self.time_diff,
                "recvWindow": self.config.RECV_WINDOW,
            }

            if params:
                order_params.update(params)

            order = await self.exchange.create_market_order(
                symbol, side, amount, order_params
            )
            self.logger.info(
                f"市价订单创建成功: {order['id']} | {side} {amount} {symbol}"
            )
            return order
        except Exception as e:
            self.logger.error(f"创建市价订单失败: {str(e)}")
            raise

    async def fetch_order(self, order_id: str, symbol: str, params=None):
        """获取订单信息"""
        try:
            return await self.exchange.fetch_order(order_id, symbol, params)
        except Exception as e:
            self.logger.error(f"获取订单信息失败: {str(e)}")
            raise

    async def fetch_open_orders(self, symbol: str):
        """获取未完成订单"""
        return await self.exchange.fetch_open_orders(symbol)

    async def cancel_order(self, order_id: str, symbol: str, params=None):
        """取消订单"""
        try:
            result = await self.exchange.cancel_order(order_id, symbol, params)
            self.logger.info(f"订单取消成功: {order_id}")
            return result
        except Exception as e:
            self.logger.error(f"取消订单失败: {str(e)}")
            raise

    async def close(self):
        """关闭交易所连接"""
        try:
            await self.exchange.close()
            self.logger.info("交易所连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭连接失败: {str(e)}")

    async def sync_time(self):
        """同步服务器时间"""
        try:
            server_time = await self.exchange.fetch_time()
            local_time = int(time.time() * 1000)
            self.time_diff = server_time - local_time
            self.logger.debug(f"时间同步完成，时差: {self.time_diff}ms")
        except Exception as e:
            self.logger.warning(f"时间同步失败: {str(e)}")

    async def fetch_order_book(self, symbol: str, limit: int = 5):
        """获取订单簿"""
        try:
            return await self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            self.logger.error(f"获取订单簿失败: {str(e)}")
            raise

    async def fetch_my_trades(self, symbol: str, limit: int = 10):
        """获取我的交易记录"""
        try:
            return await self.exchange.fetch_my_trades(symbol, limit=limit)
        except Exception as e:
            self.logger.error(f"获取交易记录失败: {str(e)}")
            raise

    async def transfer_to_spot(self, asset: str, amount: float):
        """从理财转到现货"""
        try:
            # 获取产品ID
            product_id = await self.get_flexible_product_id(asset)
            if not product_id:
                raise ValueError(f"未找到 {asset} 的理财产品")

            # 执行赎回
            result = await self.exchange.sapi_post_simple_earn_flexible_redeem(
                {"productId": product_id, "amount": amount, "destAccount": "SPOT"}
            )

            self.logger.info(f"理财赎回成功: {amount} {asset}")
            return result
        except Exception as e:
            self.logger.error(f"理财赎回失败: {str(e)}")
            raise

    async def get_flexible_product_id(self, asset: str):
        """获取理财产品ID"""
        try:
            products = await self.exchange.sapi_get_simple_earn_flexible_list(
                {"asset": asset}
            )

            if products and len(products) > 0:
                return products[0]["productId"]
            return None
        except Exception as e:
            self.logger.error(f"获取理财产品ID失败: {str(e)}")
            return None
