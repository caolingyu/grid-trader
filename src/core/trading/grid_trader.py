"""
网格交易器

重构后的网格交易核心逻辑，支持多币种和模块化设计
"""

import asyncio
import time
from typing import Optional

import numpy as np

from src.utils.helpers import (
    round_down_to_precision,
)
from src.utils.logger import TradingLogger
from src.utils.notifications import NotificationManager

from .order_tracker import OrderThrottler, OrderTracker
from .position_controller import PositionController
from .risk_manager import RiskManager


class GridTrader:
    """网格交易器主类"""

    def __init__(self, exchange, config):
        """初始化网格交易器"""
        self.exchange = exchange
        self.config = config
        self.symbol = config.symbol
        self.base_price = config.INITIAL_BASE_PRICE
        self.grid_size = config.INITIAL_GRID

        # 状态变量
        self.initialized = False
        self.highest = None
        self.lowest = None
        self.current_price = None
        self.total_assets = 0
        self.last_trade_time = None
        self.last_trade_price = None
        self.price_history = []
        self.last_grid_adjust_time = time.time()
        self.buying_or_selling = False

        # 订单管理
        self.active_orders = {"buy": None, "sell": None}
        self.monitored_orders = []
        self.pending_orders = {}
        self.order_timestamps = {}

        # 组件初始化
        self.logger = TradingLogger(self.__class__.__name__)
        self.notification_manager = NotificationManager(config.PUSHPLUS_TOKEN)
        self.order_tracker = OrderTracker(f"data/{self.symbol.replace('/', '_')}")
        self.order_throttler = OrderThrottler()
        self.risk_manager = RiskManager(self)
        self.position_controller = PositionController(self)

        # 交易参数
        self.ORDER_TIMEOUT = 10
        self.MIN_TRADE_INTERVAL = 30
        self.balance_check_interval = 60
        self.last_balance_check = 0

        # 缓存
        self.funding_balance_cache = {"timestamp": 0, "data": {}}
        self.funding_cache_ttl = 60

        # 市场信息
        self.symbol_info = None

        self.logger.logger.info(f"网格交易器初始化完成 | 交易对: {self.symbol}")

    async def initialize(self):
        """初始化交易器"""
        if self.initialized:
            return

        self.logger.logger.info("正在初始化网格交易器...")

        try:
            # 加载市场数据
            await self._load_market_data()

            # 检查和划转资金
            await self._check_and_transfer_initial_funds()

            # 设置基准价格
            await self._setup_base_price()

            # 同步交易历史
            await self._sync_recent_trades()

            self.initialized = True
            self.logger.logger.info(f"交易器初始化完成 | 基准价: {self.base_price}")

            # 发送启动通知
            await self.notification_manager.send_system_notification(
                "交易器启动",
                f"交易对: {self.symbol}\n基准价: {self.base_price}\n网格大小: {self.grid_size}%",
                "SUCCESS",
            )

        except Exception as e:
            self.initialized = False
            self.logger.logger.error(f"初始化失败: {str(e)}")
            await self.notification_manager.send_system_notification(
                "初始化失败", str(e), "ERROR"
            )
            raise

    async def _load_market_data(self):
        """加载市场数据"""
        retry_count = 0
        max_retries = 3

        while not self.exchange.markets_loaded and retry_count < max_retries:
            try:
                await self.exchange.load_markets()
                await asyncio.sleep(1)
                break
            except Exception as e:
                self.logger.logger.warning(f"加载市场数据失败: {str(e)}")
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                await asyncio.sleep(2)

        self.symbol_info = self.exchange.exchange.market(self.symbol)
        self.logger.logger.info("市场数据加载完成")

    async def _setup_base_price(self):
        """设置基准价格"""
        # 优先使用币种配置中的基准价格
        if self.config.INITIAL_BASE_PRICE > 0:
            self.base_price = self.config.INITIAL_BASE_PRICE
            self.logger.logger.info(f"使用币种配置基准价: {self.base_price}")
        else:
            # 如果未配置基准价格，使用智能计算
            self.logger.logger.info("未配置基准价格，开始智能计算...")
            await self._calculate_smart_base_price()

        if self.base_price is None or self.base_price <= 0:
            raise ValueError("无法获取有效的基准价格")

        # 记录价格差异
        market_price = await self._get_latest_price()
        if market_price:
            price_diff = (market_price - self.base_price) / self.base_price * 100
            self.logger.logger.info(
                f"市场价格: {market_price:.4f} | 基准价格: {self.base_price:.4f} | 价差: {price_diff:+.2f}%"
            )

    async def _calculate_smart_base_price(self):
        """智能计算基准价格"""
        try:
            from src.utils.price_calculator import PriceCalculator
            
            calculator = PriceCalculator()
            
            # 尝试多种计算方法
            methods = ["sma_7d", "ema_7d", "median_7d", "bollinger_middle"]
            calculated_prices = []
            
            for method in methods:
                price = await calculator.calculate_smart_base_price(
                    self.exchange, self.symbol, method
                )
                if price and price > 0:
                    calculated_prices.append(price)
                    self.logger.logger.info(f"{method}计算结果: {price:.4f}")
            
            if calculated_prices:
                # 使用多种方法的平均值作为基准价格
                import statistics
                self.base_price = statistics.mean(calculated_prices)
                self.logger.logger.info(f"智能计算基准价格: {self.base_price:.4f} (基于{len(calculated_prices)}种方法)")
                
                # 验证基准价格合理性
                current_price = await self._get_latest_price()
                if current_price and calculator.validate_base_price(self.base_price, current_price):
                    self.logger.logger.info("基准价格验证通过")
                else:
                    self.logger.logger.warning("基准价格偏离较大，使用当前市场价格")
                    self.base_price = current_price
            else:
                # 如果智能计算失败，使用当前市场价格
                self.logger.logger.warning("智能计算失败，使用当前市场价格")
                self.base_price = await self._get_latest_price()
                
        except Exception as e:
            self.logger.logger.error(f"智能计算基准价格失败: {str(e)}")
            # 降级使用当前市场价格
            self.base_price = await self._get_latest_price()
            if self.base_price:
                self.logger.logger.info(f"降级使用实时市场价格: {self.base_price}")

    async def _get_latest_price(self) -> Optional[float]:
        """获取最新价格"""
        try:
            ticker = await self.exchange.fetch_ticker(self.symbol)
            if ticker and "last" in ticker:
                return ticker["last"]
            self.logger.logger.error("获取价格失败: 返回数据格式不正确")
            return self.base_price
        except Exception as e:
            self.logger.logger.error(f"获取最新价格失败: {str(e)}")
            return self.base_price

    def _get_upper_band(self) -> float:
        """获取网格上轨"""
        return self.base_price * (1 + self.grid_size / 100)

    def _get_lower_band(self) -> float:
        """获取网格下轨"""
        return self.base_price * (1 - self.grid_size / 100)

    def _reset_extremes(self):
        """重置极值记录"""
        if self.highest is not None or self.lowest is not None:
            self.logger.logger.debug(
                f"重置极值 | highest={self.highest} lowest={self.lowest}"
            )
        self.highest = None
        self.lowest = None

    async def _sync_recent_trades(self, limit: int = 50):
        """同步最近交易记录"""
        try:
            latest_fills = await self.exchange.fetch_my_trades(self.symbol, limit=limit)
            if not latest_fills:
                self.logger.logger.info("未获取到交易记录")
                return

            # 聚合交易记录
            aggregated = {}
            for trade in latest_fills:
                order_id = trade.get("order") or trade.get("orderId")
                if not order_id:
                    continue

                price = float(trade.get("price", 0))
                amount = float(trade.get("amount", 0))
                cost = float(trade.get("cost") or price * amount)

                if order_id not in aggregated:
                    aggregated[order_id] = {
                        "timestamp": trade["timestamp"] / 1000,
                        "side": trade["side"],
                        "amount": 0.0,
                        "cost": 0.0,
                    }

                aggregated[order_id]["amount"] += amount
                aggregated[order_id]["cost"] += cost
                aggregated[order_id]["timestamp"] = min(
                    aggregated[order_id]["timestamp"], trade["timestamp"] / 1000
                )

            # 过滤小额交易
            valid_trades = {
                oid: info
                for oid, info in aggregated.items()
                if info["cost"] >= self.config.MIN_TRADE_AMOUNT
            }

            self.logger.logger.info(f"同步交易记录完成: {len(valid_trades)} 笔有效交易")

        except Exception as e:
            self.logger.logger.error(f"同步交易记录失败: {str(e)}")

    async def main_loop(self):
        """主交易循环"""
        self.logger.logger.info("启动主交易循环")

        while True:
            try:
                if not self.initialized:
                    await asyncio.sleep(5)
                    continue

                # 获取当前价格
                self.current_price = await self._get_latest_price()
                if not self.current_price:
                    await asyncio.sleep(5)
                    continue

                # 检查交易信号
                await self._check_trading_signals()

                # 检查网格调整
                await self._check_grid_adjustment()

                # 检查风险控制
                risk_check_result = await self.risk_manager.check_all_risks()
                if not risk_check_result:
                    continue

                # 检查仓位控制
                await self.position_controller.check_and_execute()

                # 更新资产信息
                await self._update_total_assets()

                # 计算动态间隔
                interval = await self._calculate_dynamic_interval()
                await asyncio.sleep(interval)

            except Exception as e:
                self.logger.logger.error(f"主循环错误: {str(e)}")
                await asyncio.sleep(10)

    async def _check_trading_signals(self):
        """检查交易信号"""
        if self.buying_or_selling:
            return

        try:
            # 检查买入信号
            buy_signal = await self._check_buy_signal()
            if buy_signal:
                await self._execute_buy_order()
                return

            # 检查卖出信号
            sell_signal = await self._check_sell_signal()
            if sell_signal:
                await self._execute_sell_order()
                return

        except Exception as e:
            self.logger.logger.error(f"检查交易信号失败: {str(e)}")

    async def _check_buy_signal(self) -> bool:
        """检查买入信号"""
        if not self.current_price:
            return False

        lower_band = self._get_lower_band()
        threshold = self.config.get_flip_threshold()

        # 价格跌破下轨 + 阈值
        if self.current_price <= lower_band * (1 - threshold):
            self.logger.log_signal(
                "BUY", self.current_price, f"价格跌破下轨 {lower_band:.4f}"
            )
            return True

        return False

    async def _check_sell_signal(self) -> bool:
        """检查卖出信号"""
        if not self.current_price:
            return False

        upper_band = self._get_upper_band()
        threshold = self.config.get_flip_threshold()

        # 价格突破上轨 + 阈值
        if self.current_price >= upper_band * (1 + threshold):
            self.logger.log_signal(
                "SELL", self.current_price, f"价格突破上轨 {upper_band:.4f}"
            )
            return True

        return False

    async def _execute_buy_order(self):
        """执行买入订单"""
        try:
            self.buying_or_selling = True

            # 计算交易金额
            amount = await self.calculate_trade_amount("buy", self.current_price)
            if amount <= 0:
                self.logger.logger.warning("买入金额不足")
                return

            # 创建市价订单
            order = await self.exchange.create_market_order(self.symbol, "buy", amount)

            self.logger.log_trade("buy", amount, self.current_price, order["id"])

            # 记录交易到跟踪器
            trade_record = {
                "timestamp": time.time(),
                "symbol": self.symbol,
                "side": "buy",
                "amount": amount,
                "price": self.current_price,
                "cost": amount * self.current_price,
                "order_id": order["id"],
                "strategy": "grid",
            }
            self.order_tracker.add_trade(trade_record)

            # 发送交易通知
            await self.notification_manager.send_trade_notification(
                "buy", amount, self.current_price, self.symbol
            )

            # 调整网格
            await self._adjust_grid_after_trade("buy")

        except Exception as e:
            self.logger.logger.error(f"执行买入订单失败: {str(e)}")
        finally:
            self.buying_or_selling = False

    async def _execute_sell_order(self):
        """执行卖出订单"""
        try:
            self.buying_or_selling = True

            # 计算交易金额
            amount = await self.calculate_trade_amount("sell", self.current_price)
            if amount <= 0:
                self.logger.logger.warning("卖出数量不足")
                return

            # 创建市价订单
            order = await self.exchange.create_market_order(self.symbol, "sell", amount)

            self.logger.log_trade("sell", amount, self.current_price, order["id"])

            # 记录交易到跟踪器
            trade_record = {
                "timestamp": time.time(),
                "symbol": self.symbol,
                "side": "sell",
                "amount": amount,
                "price": self.current_price,
                "cost": amount * self.current_price,
                "order_id": order["id"],
                "strategy": "grid",
            }
            self.order_tracker.add_trade(trade_record)

            # 发送交易通知
            await self.notification_manager.send_trade_notification(
                "sell", amount, self.current_price, self.symbol
            )

            # 调整网格
            await self._adjust_grid_after_trade("sell")

        except Exception as e:
            self.logger.logger.error(f"执行卖出订单失败: {str(e)}")
        finally:
            self.buying_or_selling = False

    async def calculate_trade_amount(self, side: str, price: float) -> float:
        """计算交易金额"""
        try:
            balance = await self.exchange.fetch_balance()

            if side == "buy":
                # 买入：使用USDT余额
                usdt_balance = balance.get("free", {}).get("USDT", 0)
                max_amount = usdt_balance * self.config.MAX_POSITION_PERCENT
                min_amount = self.config.MIN_TRADE_AMOUNT

                if max_amount < min_amount:
                    return 0

                # 计算可买入的数量
                amount = max_amount / price
                return self._adjust_amount_precision(amount)

            else:  # sell
                # 卖出：使用基础货币余额
                base_currency = self.symbol.split("/")[0]
                base_balance = balance.get("free", {}).get(base_currency, 0)

                # 计算可卖出的数量
                max_amount = base_balance * self.config.MAX_POSITION_PERCENT
                return self._adjust_amount_precision(max_amount)

        except Exception as e:
            self.logger.logger.error(f"计算交易金额失败: {str(e)}")
            return 0

    def _adjust_amount_precision(self, amount: float) -> float:
        """调整数量精度"""
        if not self.symbol_info:
            return round(amount, 6)

        # 获取最小交易单位
        min_amount = (
            self.symbol_info.get("limits", {}).get("amount", {}).get("min", 0.001)
        )
        _ = len(str(min_amount).split(".")[-1]) if "." in str(min_amount) else 0

        return round_down_to_precision(amount, min_amount)

    async def _adjust_grid_after_trade(self, side: str):
        """交易后调整网格"""
        try:
            # 更新基准价格为当前价格
            old_base = self.base_price
            self.base_price = self.current_price

            self.logger.log_grid_adjustment(
                old_base, self.base_price, f"交易后调整 ({side})"
            )

            # 重置极值
            self._reset_extremes()

        except Exception as e:
            self.logger.logger.error(f"调整网格失败: {str(e)}")

    async def _check_grid_adjustment(self):
        """检查是否需要调整网格大小"""
        try:
            # 计算波动率
            volatility = await self._calculate_volatility()
            if volatility is None:
                return

            # 根据波动率获取建议网格大小
            suggested_grid = self.config.get_grid_size_by_volatility(volatility)

            # 如果建议网格与当前网格差异较大，则调整
            if abs(suggested_grid - self.grid_size) > 0.5:
                old_grid = self.grid_size
                self.grid_size = suggested_grid

                self.logger.log_grid_adjustment(
                    old_grid,
                    self.grid_size,
                    f"波动率调整 (volatility: {volatility:.2%})",
                )

        except Exception as e:
            self.logger.logger.error(f"检查网格调整失败: {str(e)}")

    async def _calculate_volatility(self) -> Optional[float]:
        """计算价格波动率"""
        try:
            # 获取历史K线数据
            ohlcv = await self.exchange.fetch_ohlcv(
                self.symbol, "1h", limit=self.config.VOLATILITY_WINDOW
            )

            if len(ohlcv) < 2:
                return None

            # 计算收益率
            closes = [candle[4] for candle in ohlcv]  # 收盘价
            returns = []

            for i in range(1, len(closes)):
                ret = (closes[i] - closes[i - 1]) / closes[i - 1]
                returns.append(ret)

            # 计算标准差（波动率）
            if len(returns) > 0:
                volatility = np.std(returns) * np.sqrt(24)  # 年化波动率
                return volatility

            return None

        except Exception as e:
            self.logger.logger.error(f"计算波动率失败: {str(e)}")
            return None

    async def _calculate_dynamic_interval(self) -> float:
        """计算动态调整间隔"""
        try:
            volatility = await self._calculate_volatility()
            if volatility is None:
                return 60  # 默认60秒

            # 根据波动率获取间隔
            interval_hours = self.config.get_interval_by_volatility(volatility)
            return interval_hours * 3600  # 转换为秒

        except Exception as e:
            self.logger.logger.error(f"计算动态间隔失败: {str(e)}")
            return 60

    async def _update_total_assets(self):
        """更新总资产"""
        try:
            balance = await self.exchange.fetch_balance()

            # 计算总资产（以USDT计价）
            total_usdt = balance.get("total", {}).get("USDT", 0)

            # 获取基础货币余额并转换为USDT
            base_currency = self.symbol.split("/")[0]
            base_balance = balance.get("total", {}).get(base_currency, 0)

            if base_balance > 0 and self.current_price:
                total_usdt += base_balance * self.current_price

            self.total_assets = total_usdt

        except Exception as e:
            self.logger.logger.error(f"更新总资产失败: {str(e)}")

    async def _get_position_ratio(self) -> float:
        """获取当前仓位比例"""
        try:
            balance = await self.exchange.fetch_balance()
            base_currency = self.symbol.split("/")[0]
            base_balance = balance.get("total", {}).get(base_currency, 0)

            if self.total_assets <= 0 or not self.current_price:
                return 0.0

            base_value = base_balance * self.current_price
            return base_value / self.total_assets

        except Exception as e:
            self.logger.logger.error(f"获取仓位比例失败: {str(e)}")
            return 0.0

    async def _check_and_transfer_initial_funds(self):
        """检查并划转初始资金"""
        # 这里需要实现资金划转逻辑
        pass

    async def _get_total_assets(self) -> float:
        """获取总资产"""
        await self._update_total_assets()
        return self.total_assets

    async def emergency_stop(self):
        """紧急停止"""
        self.logger.logger.warning("执行紧急停止")
        self.buying_or_selling = False

        # 取消所有挂单
        try:
            open_orders = await self.exchange.fetch_open_orders(self.symbol)
            for order in open_orders:
                await self.exchange.cancel_order(order["id"], self.symbol)
                self.logger.logger.info(f"已取消订单: {order['id']}")
        except Exception as e:
            self.logger.logger.error(f"取消订单失败: {str(e)}")

        await self.notification_manager.send_system_notification(
            "紧急停止", "交易器已紧急停止", "WARNING"
        )

    async def _reinitialize(self):
        """重新初始化"""
        self.logger.logger.info("重新初始化交易器")
        self.initialized = False
        await self.initialize()
