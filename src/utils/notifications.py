"""
通知模块

提供PushPlus等通知服务
"""

import asyncio
import logging
import aiohttp
from typing import Optional


logger = logging.getLogger(__name__)


async def send_notification(
    message: str,
    title: str = "网格交易通知",
    pushplus_token: Optional[str] = None,
    timeout: int = 5
) -> bool:
    """
    发送通知消息
    
    Args:
        message: 消息内容
        title: 消息标题
        pushplus_token: PushPlus令牌
        timeout: 超时时间
    
    Returns:
        bool: 发送是否成功
    """
    if not pushplus_token:
        # 尝试从环境变量获取
        import os
        pushplus_token = os.getenv('PUSHPLUS_TOKEN')
    
    if not pushplus_token:
        logger.debug("未配置PushPlus令牌，跳过通知发送")
        return False
    
    try:
        url = "http://www.pushplus.plus/send"
        data = {
            "token": pushplus_token,
            "title": title,
            "content": message,
            "template": "html"
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 200:
                        logger.debug(f"通知发送成功: {title}")
                        return True
                    else:
                        logger.warning(f"通知发送失败: {result.get('msg', '未知错误')}")
                        return False
                else:
                    logger.warning(f"通知发送失败: HTTP {response.status}")
                    return False
    
    except asyncio.TimeoutError:
        logger.warning("通知发送超时")
        return False
    except Exception as e:
        logger.warning(f"通知发送异常: {str(e)}")
        return False


class NotificationManager:
    """通知管理器"""
    
    def __init__(self, pushplus_token: Optional[str] = None, default_timeout: int = 5):
        self.pushplus_token = pushplus_token
        self.default_timeout = default_timeout
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def send_trade_notification(
        self,
        side: str,
        amount: float,
        price: float,
        symbol: str,
        profit: Optional[float] = None
    ):
        """发送交易通知"""
        emoji = "🟢" if side.lower() == "buy" else "🔴"
        
        message = f"""
        {emoji} <b>交易执行</b>
        
        <b>交易对:</b> {symbol}
        <b>方向:</b> {side.upper()}
        <b>数量:</b> {amount:.6f}
        <b>价格:</b> {price:.4f} USDT
        <b>总价值:</b> {amount * price:.2f} USDT
        """
        
        if profit is not None:
            profit_emoji = "📈" if profit >= 0 else "📉"
            message += f"\n<b>盈亏:</b> {profit_emoji} {profit:.2f} USDT"
        
        await send_notification(
            message,
            title=f"{symbol} 交易通知",
            pushplus_token=self.pushplus_token,
            timeout=self.default_timeout
        )
    
    async def send_risk_notification(
        self,
        risk_type: str,
        current_value: float,
        limit_value: float,
        action: str = "监控"
    ):
        """发送风险通知"""
        message = f"""
        ⚠️ <b>风险警告</b>
        
        <b>风险类型:</b> {risk_type}
        <b>当前值:</b> {current_value:.2%}
        <b>限制值:</b> {limit_value:.2%}
        <b>采取行动:</b> {action}
        """
        
        await send_notification(
            message,
            title="风险警告",
            pushplus_token=self.pushplus_token,
            timeout=self.default_timeout
        )
    
    async def send_system_notification(
        self,
        event: str,
        details: str,
        level: str = "INFO"
    ):
        """发送系统通知"""
        level_emoji = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅"
        }.get(level, "ℹ️")
        
        message = f"""
        {level_emoji} <b>系统通知</b>
        
        <b>事件:</b> {event}
        <b>详情:</b> {details}
        <b>时间:</b> {asyncio.get_event_loop().time()}
        """
        
        await send_notification(
            message,
            title="系统通知",
            pushplus_token=self.pushplus_token,
            timeout=self.default_timeout
        ) 