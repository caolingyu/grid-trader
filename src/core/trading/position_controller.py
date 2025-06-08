"""
仓位控制器

重构后的仓位控制和管理模块，支持S1策略等高级仓位管理
"""

import time
import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from src.utils.logger import TradingLogger
from src.utils.notifications import NotificationManager


class PositionController:
    """
    仓位控制器 - 基于52日高低点的仓位控制策略
    独立于主网格策略运行，不修改网格的base_price
    """
    
    def __init__(self, trader_instance):
        """
        初始化仓位控制器
        
        Args:
            trader_instance: 主 GridTrader 类的实例
        """
        self.trader = trader_instance
        self.config = trader_instance.config
        self.logger = TradingLogger(self.__class__.__name__)
        self.notification_manager = NotificationManager(self.config.PUSHPLUS_TOKEN)
        
        # S1 策略参数
        self.s1_lookback = getattr(self.config, 'S1_LOOKBACK', 52)
        self.s1_sell_target_pct = getattr(self.config, 'S1_SELL_TARGET_PCT', 0.50)
        self.s1_buy_target_pct = getattr(self.config, 'S1_BUY_TARGET_PCT', 0.70)
        
        # S1 状态变量
        self.s1_daily_high = None
        self.s1_daily_low = None
        self.s1_last_data_update_ts = 0
        self.daily_update_interval = 23.9 * 60 * 60  # 每日更新间隔
        
        # 仓位控制状态
        self.last_position_check = 0
        self.position_check_interval = 300  # 5分钟检查一次
        self.last_adjustment_time = 0
        self.adjustment_cooldown = 1800  # 30分钟调整冷却期
        
        self.logger.logger.info(
            f"仓位控制器初始化完成 | "
            f"回看期: {self.s1_lookback}天 | "
            f"卖出目标: {self.s1_sell_target_pct*100}% | "
            f"买入目标: {self.s1_buy_target_pct*100}%"
        )
    
    async def check_and_execute(self):
        """
        高频检查仓位控制条件并执行调仓
        应在主交易循环中频繁调用
        """
        try:
            current_time = time.time()
            
            # 检查是否需要更新日线数据
            await self.update_daily_s1_levels()
            
            # 检查是否需要进行仓位检查
            if current_time - self.last_position_check < self.position_check_interval:
                return
            
            self.last_position_check = current_time
            
            # 检查是否在调整冷却期内
            if current_time - self.last_adjustment_time < self.adjustment_cooldown:
                return
            
            # 检查S1策略条件
            await self._check_s1_strategy()
            
        except Exception as e:
            self.logger.logger.error(f"仓位控制检查失败: {str(e)}")
    
    async def update_daily_s1_levels(self):
        """每日检查并更新一次S1所需的52日高低价"""
        current_time = time.time()
        if current_time - self.s1_last_data_update_ts >= self.daily_update_interval:
            self.logger.logger.info("更新S1日线高低点数据...")
            await self._fetch_and_calculate_s1_levels()
    
    async def _fetch_and_calculate_s1_levels(self):
        """获取日线数据并计算52日高低点"""
        try:
            # 获取比回看期稍多的日线数据
            limit = self.s1_lookback + 2
            klines = await self.trader.exchange.fetch_ohlcv(
                self.trader.symbol,
                timeframe='1d',
                limit=limit
            )
            
            if not klines or len(klines) < self.s1_lookback + 1:
                self.logger.logger.warning(
                    f"日线数据不足 ({len(klines) if klines else 0}条)，无法更新S1水平"
                )
                return False
            
            # 使用倒数第2根K线往前数s1_lookback根来计算
            # klines[-1]是当前未完成日线，klines[-2]是昨天收盘的日线
            relevant_klines = klines[-(self.s1_lookback + 1):-1]
            
            if len(relevant_klines) < self.s1_lookback:
                self.logger.logger.warning(
                    f"有效日线数据不足 ({len(relevant_klines)}条)，需要{self.s1_lookback}条"
                )
                return False
            
            # 计算高低点 (索引2是high, 3是low)
            self.s1_daily_high = max(float(k[2]) for k in relevant_klines)
            self.s1_daily_low = min(float(k[3]) for k in relevant_klines)
            self.s1_last_data_update_ts = time.time()
            
            self.logger.logger.info(
                f"S1水平更新完成 | "
                f"高点: {self.s1_daily_high:.4f} | "
                f"低点: {self.s1_daily_low:.4f}"
            )
            return True
            
        except Exception as e:
            self.logger.logger.error(f"获取S1日线数据失败: {str(e)}")
            return False
    
    async def _check_s1_strategy(self):
        """检查S1策略条件"""
        try:
            # 确保有S1数据
            if self.s1_daily_high is None or self.s1_daily_low is None:
                return
            
            # 获取当前价格
            current_price = self.trader.current_price
            if not current_price:
                return
            
            # 计算当前价格在52日区间的位置
            price_range = self.s1_daily_high - self.s1_daily_low
            if price_range <= 0:
                return
            
            price_position = (current_price - self.s1_daily_low) / price_range
            
            # 获取当前仓位比例
            current_position_ratio = await self._get_current_position_ratio()
            
            self.logger.logger.debug(
                f"S1策略检查 | "
                f"价格位置: {price_position:.2%} | "
                f"当前仓位: {current_position_ratio:.2%}"
            )
            
            # 检查卖出条件：价格接近高点且仓位过高
            if (price_position >= 0.8 and  # 价格在80%以上位置
                current_position_ratio > self.s1_sell_target_pct):
                
                # 计算需要卖出的数量
                target_reduction = current_position_ratio - self.s1_sell_target_pct
                sell_amount = await self._calculate_adjustment_amount('sell', target_reduction)
                
                if sell_amount > 0:
                    await self._execute_s1_adjustment('sell', sell_amount)
            
            # 检查买入条件：价格接近低点且仓位过低
            elif (price_position <= 0.2 and  # 价格在20%以下位置
                  current_position_ratio < self.s1_buy_target_pct):
                
                # 计算需要买入的数量
                target_increase = self.s1_buy_target_pct - current_position_ratio
                buy_amount = await self._calculate_adjustment_amount('buy', target_increase)
                
                if buy_amount > 0:
                    await self._execute_s1_adjustment('buy', buy_amount)
            
        except Exception as e:
            self.logger.logger.error(f"S1策略检查失败: {str(e)}")
    
    async def _get_current_position_ratio(self) -> float:
        """获取当前仓位比例"""
        try:
            balance = await self.trader.exchange.fetch_balance()
            
            # 获取基础货币余额
            base_currency = self.trader.symbol.split('/')[0]
            base_balance = balance.get('free', {}).get(base_currency, 0)
            
            # 获取USDT余额
            usdt_balance = balance.get('free', {}).get('USDT', 0)
            
            # 计算总资产价值
            current_price = self.trader.current_price
            if not current_price:
                return 0
            
            base_value = base_balance * current_price
            total_value = base_value + usdt_balance
            
            if total_value <= 0:
                return 0
            
            return base_value / total_value
            
        except Exception as e:
            self.logger.logger.error(f"获取仓位比例失败: {str(e)}")
            return 0
    
    async def _calculate_adjustment_amount(self, side: str, target_ratio_change: float) -> float:
        """计算调整数量"""
        try:
            balance = await self.trader.exchange.fetch_balance()
            current_price = self.trader.current_price
            
            if not current_price:
                return 0
            
            if side == 'buy':
                # 买入：计算需要用多少USDT买入
                usdt_balance = balance.get('free', {}).get('USDT', 0)
                total_assets = await self.trader._get_total_assets()
                
                target_usdt_amount = total_assets * target_ratio_change
                available_usdt = min(usdt_balance, target_usdt_amount)
                
                if available_usdt < self.config.MIN_TRADE_AMOUNT:
                    return 0
                
                # 转换为基础货币数量
                amount = available_usdt / current_price
                return self._adjust_amount_precision(amount)
            
            else:  # sell
                # 卖出：计算需要卖出多少基础货币
                base_currency = self.trader.symbol.split('/')[0]
                base_balance = balance.get('free', {}).get(base_currency, 0)
                total_assets = await self.trader._get_total_assets()
                
                target_base_value = total_assets * target_ratio_change
                target_base_amount = target_base_value / current_price
                
                available_amount = min(base_balance, target_base_amount)
                
                if available_amount * current_price < self.config.MIN_TRADE_AMOUNT:
                    return 0
                
                return self._adjust_amount_precision(available_amount)
                
        except Exception as e:
            self.logger.logger.error(f"计算调整数量失败: {str(e)}")
            return 0
    
    def _adjust_amount_precision(self, amount: float) -> float:
        """调整数量精度"""
        if not self.trader.symbol_info:
            return round(amount, 6)
        
        # 获取最小交易单位
        limits = self.trader.symbol_info.get('limits', {})
        min_amount = limits.get('amount', {}).get('min', 0.001)
        
        # 向下取整到最小精度
        precision = len(str(min_amount).split('.')[-1]) if '.' in str(min_amount) else 0
        factor = 10 ** precision
        return math.floor(amount * factor) / factor
    
    async def _execute_s1_adjustment(self, side: str, amount: float):
        """执行S1仓位调整"""
        try:
            # 检查订单限频
            if not self.trader.order_throttler.check_rate():
                self.logger.logger.warning("订单频率超限，跳过S1调整")
                return False
            
            # 精度调整
            adjusted_amount = self._adjust_amount_precision(amount)
            if adjusted_amount <= 0:
                self.logger.logger.warning(f"调整后数量为零，跳过S1调整")
                return False
            
            # 获取当前价格
            current_price = self.trader.current_price
            if not current_price:
                self.logger.logger.error("无法获取当前价格，S1调整失败")
                return False
            
            # 检查最小订单限制
            min_notional = 10  # 默认最小名义价值
            if hasattr(self.trader, 'symbol_info') and self.trader.symbol_info:
                limits = self.trader.symbol_info.get('limits', {})
                min_notional = limits.get('cost', {}).get('min', min_notional)
            
            if adjusted_amount * current_price < min_notional:
                self.logger.logger.warning(
                    f"订单价值 {adjusted_amount * current_price:.2f} USDT "
                    f"低于最小限制 {min_notional:.2f} USDT"
                )
                return False
            
            # 检查余额
            if not await self._check_balance_for_adjustment(side, adjusted_amount, current_price):
                return False
            
            self.logger.logger.info(
                f"执行S1调整 | {side.upper()} {adjusted_amount:.6f} "
                f"{self.trader.symbol.split('/')[0]} @ {current_price:.4f}"
            )
            
            # 执行市价订单
            order = await self.trader.exchange.create_market_order(
                symbol=self.trader.symbol,
                side=side.lower(),
                amount=adjusted_amount
            )
            
            self.logger.logger.info(f"S1调整订单成功 | 订单ID: {order.get('id', 'N/A')}")
            
            # 记录交易
            if hasattr(self.trader, 'order_tracker'):
                trade_info = {
                    'timestamp': time.time(),
                    'symbol': self.trader.symbol,
                    'strategy': 'S1',
                    'side': side,
                    'price': float(order.get('average', current_price)),
                    'amount': float(order.get('filled', adjusted_amount)),
                    'cost': float(order.get('cost', adjusted_amount * current_price)),
                    'order_id': order.get('id')
                }
                self.trader.order_tracker.add_trade(trade_info)
            
            # 发送通知
            await self.notification_manager.send_trade_notification(
                side, adjusted_amount, current_price, self.trader.symbol
            )
            
            # 更新最后调整时间
            self.last_adjustment_time = time.time()
            
            # 买入后转移多余资金到理财
            if side == 'buy' and hasattr(self.trader, '_transfer_excess_funds'):
                try:
                    await self.trader._transfer_excess_funds()
                except Exception as e:
                    self.logger.logger.warning(f"转移多余资金失败: {str(e)}")
            
            return True
            
        except Exception as e:
            self.logger.logger.error(f"执行S1调整失败 ({side} {amount:.6f}): {str(e)}")
            return False
    
    async def _check_balance_for_adjustment(self, side: str, amount: float, price: float) -> bool:
        """检查调整所需余额是否充足"""
        try:
            balance = await self.trader.exchange.fetch_balance()
            
            if side == 'buy':
                # 买入需要USDT
                required_usdt = amount * price
                available_usdt = balance.get('free', {}).get('USDT', 0)
                
                if available_usdt < required_usdt:
                    self.logger.logger.warning(
                        f"USDT余额不足 | 需要: {required_usdt:.2f} | 可用: {available_usdt:.2f}"
                    )
                    
                    # 尝试从理财赎回
                    if hasattr(self.trader, '_pre_transfer_funds'):
                        try:
                            await self.trader._pre_transfer_funds(price)
                            # 重新检查余额
                            balance = await self.trader.exchange.fetch_balance()
                            available_usdt = balance.get('free', {}).get('USDT', 0)
                            
                            if available_usdt < required_usdt:
                                self.logger.logger.warning(
                                    f"赎回后USDT余额仍不足 | 可用: {available_usdt:.2f}"
                                )
                                return False
                        except Exception as e:
                            self.logger.logger.error(f"从理财赎回资金失败: {str(e)}")
                            return False
                    else:
                        return False
                
                return True
                
            else:  # sell
                # 卖出需要基础货币
                base_currency = self.trader.symbol.split('/')[0]
                available_base = balance.get('free', {}).get(base_currency, 0)
                
                if available_base < amount:
                    self.logger.logger.warning(
                        f"{base_currency}余额不足 | 需要: {amount:.6f} | 可用: {available_base:.6f}"
                    )
                    return False
                
                return True
                
        except Exception as e:
            self.logger.logger.error(f"检查余额失败: {str(e)}")
            return False
    
    def get_s1_status(self) -> Dict[str, Any]:
        """获取S1策略状态"""
        try:
            current_price = self.trader.current_price
            price_position = None
            
            if (current_price and self.s1_daily_high and self.s1_daily_low and 
                self.s1_daily_high > self.s1_daily_low):
                price_range = self.s1_daily_high - self.s1_daily_low
                price_position = (current_price - self.s1_daily_low) / price_range
            
            return {
                'enabled': True,
                'lookback_days': self.s1_lookback,
                'daily_high': self.s1_daily_high,
                'daily_low': self.s1_daily_low,
                'current_price': current_price,
                'price_position': price_position,
                'sell_target': self.s1_sell_target_pct,
                'buy_target': self.s1_buy_target_pct,
                'last_update': self.s1_last_data_update_ts,
                'last_adjustment': self.last_adjustment_time,
                'cooldown_remaining': max(0, self.adjustment_cooldown - (time.time() - self.last_adjustment_time))
            }
            
        except Exception as e:
            self.logger.logger.error(f"获取S1状态失败: {str(e)}")
            return {'enabled': False, 'error': str(e)}
    
    def reset_s1_state(self):
        """重置S1策略状态"""
        self.s1_daily_high = None
        self.s1_daily_low = None
        self.s1_last_data_update_ts = 0
        self.last_adjustment_time = 0
        self.logger.logger.info("S1策略状态已重置") 