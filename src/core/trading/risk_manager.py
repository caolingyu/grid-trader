"""
风险管理器

重构后的风险控制和管理模块
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

from src.utils.logger import TradingLogger
from src.utils.notifications import NotificationManager


class RiskManager:
    """风险管理器"""
    
    def __init__(self, trader):
        self.trader = trader
        self.config = trader.config
        self.logger = TradingLogger(self.__class__.__name__)
        self.notification_manager = NotificationManager(self.config.PUSHPLUS_TOKEN)
        
        # 风险控制状态
        self.last_position_ratio = None
        self.risk_alerts = {}
        self.emergency_stop_triggered = False
        
        # 历史数据追踪
        self.asset_history = []
        self.daily_pnl_history = []
        self.max_asset_value = 0
        self.daily_start_assets = None
        
        self.logger.logger.info("风险管理器初始化完成")
    
    async def check_all_risks(self) -> bool:
        """执行所有风险检查"""
        try:
            # 如果已经触发紧急停止，直接返回
            if self.emergency_stop_triggered:
                return False
            
            # 检查仓位比例
            position_risk = await self.check_position_risk()
            
            # 检查最大回撤
            drawdown_risk = await self.check_max_drawdown()
            
            # 检查日亏损限制
            daily_loss_risk = await self.check_daily_loss_limit()
            
            # 检查市场波动率
            volatility_risk = await self.check_volatility_risk()
            
            # 如果任何风险检查失败，返回False
            risk_triggered = any([position_risk, drawdown_risk, daily_loss_risk, volatility_risk])
            
            if risk_triggered:
                await self.handle_risk_event("多重风险触发")
                return False
            
            return True
            
        except Exception as e:
            self.logger.logger.error(f"风险检查失败: {str(e)}")
            return False
    
    async def check_position_risk(self) -> bool:
        """检查仓位风险"""
        try:
            position_ratio = await self._get_position_ratio()
            
            # 保存上次的仓位比例，避免频繁日志
            if self.last_position_ratio is None:
                self.last_position_ratio = position_ratio
            
            # 只在仓位比例变化超过0.1%时打印日志
            if abs(position_ratio - self.last_position_ratio) > 0.001:
                self.logger.logger.info(
                    f"风控检查 | "
                    f"当前仓位比例: {position_ratio:.2%} | "
                    f"最大允许比例: {self.config.MAX_POSITION_RATIO:.2%} | "
                    f"最小底仓比例: {self.config.MIN_POSITION_RATIO:.2%}"
                )
                self.last_position_ratio = position_ratio
            
            # 检查底仓保护
            if position_ratio < self.config.MIN_POSITION_RATIO:
                await self.send_risk_alert(
                    "底仓保护触发",
                    f"当前仓位比例: {position_ratio:.2%}",
                    "POSITION_LOW"
                )
                return True
            
            # 检查仓位上限
            if position_ratio > self.config.MAX_POSITION_RATIO:
                await self.send_risk_alert(
                    "仓位超限",
                    f"当前仓位比例: {position_ratio:.2%}",
                    "POSITION_HIGH"
                )
                return True
            
            return False
            
        except Exception as e:
            self.logger.logger.error(f"检查仓位风险失败: {str(e)}")
            return False
    
    async def check_max_drawdown(self) -> bool:
        """检查最大回撤"""
        try:
            current_assets = await self.trader._get_total_assets()
            
            # 更新历史最高资产
            if current_assets > self.max_asset_value:
                self.max_asset_value = current_assets
            
            # 计算回撤
            if self.max_asset_value > 0:
                drawdown = (current_assets - self.max_asset_value) / self.max_asset_value
                
                # 检查是否超过最大回撤限制
                if drawdown < self.config.MAX_DRAWDOWN:
                    await self.send_risk_alert(
                        "最大回撤警告",
                        f"当前回撤: {drawdown:.2%}, 限制: {self.config.MAX_DRAWDOWN:.2%}",
                        "MAX_DRAWDOWN"
                    )
                    return True
            
            return False
            
        except Exception as e:
            self.logger.logger.error(f"检查最大回撤失败: {str(e)}")
            return False
    
    async def check_daily_loss_limit(self) -> bool:
        """检查日亏损限制"""
        try:
            current_assets = await self.trader._get_total_assets()
            
            # 初始化日开始资产
            if self.daily_start_assets is None:
                self.daily_start_assets = current_assets
                return False
            
            # 检查是否是新的一天
            if self._is_new_day():
                self.daily_start_assets = current_assets
                self.daily_pnl_history.append({
                    'date': datetime.now().date(),
                    'start_assets': current_assets
                })
                return False
            
            # 计算当日盈亏
            daily_pnl = (current_assets - self.daily_start_assets) / self.daily_start_assets
            
            # 检查是否超过日亏损限制
            if daily_pnl < self.config.DAILY_LOSS_LIMIT:
                await self.send_risk_alert(
                    "日亏损限制触发",
                    f"当日盈亏: {daily_pnl:.2%}, 限制: {self.config.DAILY_LOSS_LIMIT:.2%}",
                    "DAILY_LOSS"
                )
                return True
            
            return False
            
        except Exception as e:
            self.logger.logger.error(f"检查日亏损限制失败: {str(e)}")
            return False
    
    async def check_volatility_risk(self) -> bool:
        """检查波动率风险"""
        try:
            # 获取最近价格历史
            if len(self.trader.price_history) < 20:
                return False
            
            # 计算短期波动率
            recent_prices = self.trader.price_history[-20:]
            volatility = self._calculate_volatility(recent_prices)
            
            # 设置波动率阈值
            high_volatility_threshold = 0.1  # 10%
            extreme_volatility_threshold = 0.2  # 20%
            
            if volatility > extreme_volatility_threshold:
                await self.send_risk_alert(
                    "极端波动率警告",
                    f"当前波动率: {volatility:.2%}",
                    "EXTREME_VOLATILITY"
                )
                return True
            elif volatility > high_volatility_threshold:
                await self.send_risk_alert(
                    "高波动率警告",
                    f"当前波动率: {volatility:.2%}",
                    "HIGH_VOLATILITY"
                )
            
            return False
            
        except Exception as e:
            self.logger.logger.error(f"检查波动率风险失败: {str(e)}")
            return False
    
    async def send_risk_alert(self, alert_type: str, message: str, risk_level: str):
        """发送风险警报"""
        # 避免重复发送相同类型的警报（5分钟内）
        current_time = time.time()
        if risk_level in self.risk_alerts:
            if current_time - self.risk_alerts[risk_level] < 300:  # 5分钟
                return
        
        self.risk_alerts[risk_level] = current_time
        
        # 记录日志
        self.logger.logger.warning(f"风险警报: {alert_type} | {message}")
        
        # 发送通知
        await self.notification_manager.send_risk_notification(
            alert_type,
            0.0,  # 这里需要根据具体情况传入数值
            0.0,  # 这里需要根据具体情况传入限制值
            message
        )
    
    async def handle_risk_event(self, event_type: str):
        """处理风险事件"""
        self.logger.logger.error(f"风险事件触发: {event_type}")
        
        # 根据风险类型采取不同的应对措施
        if "紧急" in event_type or "极端" in event_type:
            await self.trigger_emergency_stop()
        else:
            # 暂停交易一段时间
            self.trader.buying_or_selling = True
            await asyncio.sleep(60)  # 暂停1分钟
            self.trader.buying_or_selling = False
    
    async def trigger_emergency_stop(self):
        """触发紧急停止"""
        if self.emergency_stop_triggered:
            return
        
        self.emergency_stop_triggered = True
        self.logger.logger.critical("触发紧急停止机制")
        
        # 调用交易器的紧急停止
        await self.trader.emergency_stop()
        
        # 发送紧急通知
        await self.notification_manager.send_system_notification(
            "紧急停止",
            "风险管理器触发紧急停止",
            "CRITICAL"
        )
    
    async def _get_position_ratio(self) -> float:
        """获取当前仓位占总资产比例"""
        try:
            position_value = await self._get_position_value()
            balance = await self.trader.exchange.fetch_balance()
            
            # 获取USDT余额
            usdt_balance = balance.get('free', {}).get('USDT', 0)
            
            # 计算总资产
            total_assets = position_value + usdt_balance
            if total_assets == 0:
                return 0
            
            ratio = position_value / total_assets
            
            self.logger.logger.debug(
                f"仓位计算 | "
                f"持仓价值: {position_value:.2f} USDT | "
                f"USDT余额: {usdt_balance:.2f} | "
                f"总资产: {total_assets:.2f} | "
                f"仓位比例: {ratio:.2%}"
            )
            
            return ratio
            
        except Exception as e:
            self.logger.logger.error(f"计算仓位比例失败: {str(e)}")
            return 0
    
    async def _get_position_value(self) -> float:
        """获取当前持仓价值"""
        try:
            balance = await self.trader.exchange.fetch_balance()
            
            # 获取基础货币余额
            base_currency = self.trader.symbol.split('/')[0]
            base_amount = balance.get('free', {}).get(base_currency, 0)
            
            # 获取当前价格
            current_price = await self.trader._get_latest_price()
            if not current_price:
                return 0
            
            return base_amount * current_price
            
        except Exception as e:
            self.logger.logger.error(f"获取持仓价值失败: {str(e)}")
            return 0
    
    def _calculate_volatility(self, prices: list) -> float:
        """计算价格波动率"""
        try:
            if len(prices) < 2:
                return 0
            
            # 计算价格变化率
            returns = []
            for i in range(1, len(prices)):
                if prices[i-1] != 0:
                    return_rate = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(return_rate)
            
            if not returns:
                return 0
            
            # 计算标准差作为波动率
            import numpy as np
            return np.std(returns)
            
        except Exception as e:
            self.logger.logger.error(f"计算波动率失败: {str(e)}")
            return 0
    
    def _is_new_day(self) -> bool:
        """检查是否是新的一天"""
        if not self.daily_pnl_history:
            return True
        
        last_date = self.daily_pnl_history[-1]['date']
        current_date = datetime.now().date()
        
        return current_date > last_date
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """获取风险指标"""
        try:
            return {
                'position_ratio': self.last_position_ratio or 0,
                'max_asset_value': self.max_asset_value,
                'emergency_stop_triggered': self.emergency_stop_triggered,
                'active_alerts': len(self.risk_alerts),
                'daily_pnl_days': len(self.daily_pnl_history)
            }
        except Exception as e:
            self.logger.logger.error(f"获取风险指标失败: {str(e)}")
            return {}
    
    def reset_risk_state(self):
        """重置风险状态"""
        self.emergency_stop_triggered = False
        self.risk_alerts.clear()
        self.max_asset_value = 0
        self.daily_start_assets = None
        self.logger.logger.info("风险状态已重置") 