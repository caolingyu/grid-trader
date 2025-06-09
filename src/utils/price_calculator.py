"""
价格计算工具

提供智能基准价格计算功能
"""

import asyncio
import logging
import statistics
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class PriceCalculator:
    """价格计算工具类"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def calculate_smart_base_price(
        self, 
        exchange, 
        symbol: str, 
        method: str = "sma_7d",
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[float]:
        """
        智能计算基准价格
        
        Args:
            exchange: 交易所客户端
            symbol: 交易对符号
            method: 计算方法 ('sma_7d', 'ema_7d', 'median_7d', 'support_resistance', 'bollinger_middle')
            params: 计算参数
            
        Returns:
            计算得出的基准价格，如果失败返回None
        """
        try:
            self.logger.info(f"开始智能计算基准价格 | 交易对: {symbol} | 方法: {method}")
            
            if method == "sma_7d":
                return await self._calculate_sma_base_price(exchange, symbol, 7)
            elif method == "ema_7d":
                return await self._calculate_ema_base_price(exchange, symbol, 7)
            elif method == "median_7d":
                return await self._calculate_median_base_price(exchange, symbol, 7)
            elif method == "support_resistance":
                return await self._calculate_support_resistance_base_price(exchange, symbol)
            elif method == "bollinger_middle":
                return await self._calculate_bollinger_middle_price(exchange, symbol)
            else:
                self.logger.warning(f"未知的计算方法: {method}，使用默认7日均价")
                return await self._calculate_sma_base_price(exchange, symbol, 7)
                
        except Exception as e:
            self.logger.error(f"智能计算基准价格失败: {str(e)}")
            return None

    async def _calculate_sma_base_price(self, exchange, symbol: str, days: int) -> Optional[float]:
        """计算简单移动平均价格作为基准价格"""
        try:
            # 获取日线数据
            klines = await exchange.fetch_ohlcv(symbol, timeframe='1d', limit=days + 2)
            
            if not klines or len(klines) < days:
                self.logger.warning(f"K线数据不足，无法计算{days}日均价")
                return None
            
            # 取最近days天的收盘价，排除今天的不完整数据
            closes = [float(kline[4]) for kline in klines[-days-1:-1]]
            
            if len(closes) < days:
                self.logger.warning(f"有效数据不足: {len(closes)} < {days}")
                return None
            
            sma_price = statistics.mean(closes)
            self.logger.info(f"计算{days}日简单移动平均价格: {sma_price:.4f}")
            
            return sma_price
            
        except Exception as e:
            self.logger.error(f"计算SMA基准价格失败: {str(e)}")
            return None

    async def _calculate_ema_base_price(self, exchange, symbol: str, days: int) -> Optional[float]:
        """计算指数移动平均价格作为基准价格"""
        try:
            # 获取更多数据以确保EMA计算准确
            klines = await exchange.fetch_ohlcv(symbol, timeframe='1d', limit=days * 2 + 2)
            
            if not klines or len(klines) < days:
                self.logger.warning(f"K线数据不足，无法计算{days}日EMA")
                return None
            
            # 取收盘价，排除今天的不完整数据
            closes = [float(kline[4]) for kline in klines[:-1]]
            
            if len(closes) < days:
                return None
            
            # 计算EMA
            multiplier = 2 / (days + 1)
            ema = closes[0]  # 初始值
            
            for price in closes[1:]:
                ema = (price * multiplier) + (ema * (1 - multiplier))
            
            self.logger.info(f"计算{days}日指数移动平均价格: {ema:.4f}")
            
            return ema
            
        except Exception as e:
            self.logger.error(f"计算EMA基准价格失败: {str(e)}")
            return None

    async def _calculate_median_base_price(self, exchange, symbol: str, days: int) -> Optional[float]:
        """计算中位数价格作为基准价格"""
        try:
            klines = await exchange.fetch_ohlcv(symbol, timeframe='1d', limit=days + 2)
            
            if not klines or len(klines) < days:
                self.logger.warning(f"K线数据不足，无法计算{days}日中位数")
                return None
            
            # 取最近days天的收盘价，排除今天的不完整数据
            closes = [float(kline[4]) for kline in klines[-days-1:-1]]
            
            if len(closes) < days:
                return None
            
            median_price = statistics.median(closes)
            self.logger.info(f"计算{days}日中位数价格: {median_price:.4f}")
            
            return median_price
            
        except Exception as e:
            self.logger.error(f"计算中位数基准价格失败: {str(e)}")
            return None

    async def _calculate_support_resistance_base_price(self, exchange, symbol: str) -> Optional[float]:
        """基于支撑阻力位计算基准价格"""
        try:
            # 获取较长时间的数据来识别支撑阻力位
            klines = await exchange.fetch_ohlcv(symbol, timeframe='4h', limit=168)  # 4小时*168 = 28天
            
            if not klines or len(klines) < 50:
                self.logger.warning("数据不足，无法计算支撑阻力位")
                return None
            
            # 提取高点和低点
            highs = [float(kline[2]) for kline in klines]
            lows = [float(kline[3]) for kline in klines]
            closes = [float(kline[4]) for kline in klines]
            
            # 识别局部高低点
            support_levels = []
            resistance_levels = []
            
            # 简单的局部极值识别
            window = 5
            for i in range(window, len(klines) - window):
                # 检查是否为局部高点
                if all(highs[i] >= highs[j] for j in range(i-window, i+window+1) if j != i):
                    resistance_levels.append(highs[i])
                    
                # 检查是否为局部低点
                if all(lows[i] <= lows[j] for j in range(i-window, i+window+1) if j != i):
                    support_levels.append(lows[i])
            
            if not support_levels and not resistance_levels:
                # 如果没有识别到明显的支撑阻力位，使用近期均价
                return statistics.mean(closes[-7:])
            
            # 计算当前价格附近的关键位
            current_price = closes[-1]
            
            # 找到最接近当前价格的支撑和阻力位
            nearby_supports = [s for s in support_levels if abs(s - current_price) / current_price < 0.1]
            nearby_resistances = [r for r in resistance_levels if abs(r - current_price) / current_price < 0.1]
            
            if nearby_supports and nearby_resistances:
                # 如果有附近的支撑和阻力位，取中间值
                base_price = (max(nearby_supports) + min(nearby_resistances)) / 2
            elif nearby_supports:
                # 只有支撑位，基准价格稍高于支撑位
                base_price = max(nearby_supports) * 1.01
            elif nearby_resistances:
                # 只有阻力位，基准价格稍低于阻力位
                base_price = min(nearby_resistances) * 0.99
            else:
                # 没有附近的关键位，使用近期均价
                base_price = statistics.mean(closes[-7:])
            
            self.logger.info(f"基于支撑阻力位计算基准价格: {base_price:.4f}")
            
            return base_price
            
        except Exception as e:
            self.logger.error(f"计算支撑阻力位基准价格失败: {str(e)}")
            return None

    async def _calculate_bollinger_middle_price(self, exchange, symbol: str, period: int = 20) -> Optional[float]:
        """计算布林带中轨作为基准价格"""
        try:
            klines = await exchange.fetch_ohlcv(symbol, timeframe='4h', limit=period + 5)
            
            if not klines or len(klines) < period:
                self.logger.warning(f"数据不足，无法计算{period}期布林带")
                return None
            
            # 取收盘价
            closes = [float(kline[4]) for kline in klines[-period:]]
            
            # 计算中轨（简单移动平均）
            middle_band = statistics.mean(closes)
            
            self.logger.info(f"计算布林带中轨价格({period}期): {middle_band:.4f}")
            
            return middle_band
            
        except Exception as e:
            self.logger.error(f"计算布林带中轨基准价格失败: {str(e)}")
            return None

    async def get_price_analysis(self, exchange, symbol: str) -> Dict[str, Any]:
        """获取价格分析信息"""
        try:
            analysis = {}
            
            # 计算多种基准价格
            methods = ["sma_7d", "ema_7d", "median_7d", "bollinger_middle"]
            prices = {}
            
            for method in methods:
                price = await self.calculate_smart_base_price(exchange, symbol, method)
                if price:
                    prices[method] = price
            
            # 获取当前价格
            try:
                ticker = await exchange.fetch_ticker(symbol)
                current_price = ticker['last'] if ticker and 'last' in ticker else None
            except:
                current_price = None
            
            analysis.update({
                "calculated_prices": prices,
                "current_price": current_price,
                "recommended_base_price": None,
                "price_range": None
            })
            
            # 推荐基准价格（多种方法的加权平均）
            if prices:
                valid_prices = list(prices.values())
                analysis["recommended_base_price"] = statistics.mean(valid_prices)
                analysis["price_range"] = {
                    "min": min(valid_prices),
                    "max": max(valid_prices),
                    "std": statistics.stdev(valid_prices) if len(valid_prices) > 1 else 0
                }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"获取价格分析失败: {str(e)}")
            return {}

    def validate_base_price(self, base_price: float, current_price: float, max_deviation: float = 0.2) -> bool:
        """
        验证基准价格是否合理
        
        Args:
            base_price: 计算出的基准价格
            current_price: 当前市场价格
            max_deviation: 最大偏离比例
            
        Returns:
            是否合理
        """
        try:
            if not base_price or not current_price:
                return False
            
            deviation = abs(base_price - current_price) / current_price
            
            if deviation > max_deviation:
                self.logger.warning(
                    f"基准价格偏离过大: 基准价格={base_price:.4f}, "
                    f"当前价格={current_price:.4f}, 偏离={deviation:.2%}"
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证基准价格失败: {str(e)}")
            return False 