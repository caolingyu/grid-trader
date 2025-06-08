#!/usr/bin/env python3
"""
重构后的网格交易主程序

支持多币种配置和模块化架构
"""

import sys
import os
import asyncio
import logging
import signal
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config.base_config import BaseConfig
from src.config.trading_config import TradingConfig
from src.core.exchange.client import create_exchange_client
from src.core.trading.grid_trader import GridTrader
from src.utils.logger import setup_logging
from src.utils.notifications import NotificationManager
from src.data.storage import DataStorage
from src.web.server import WebServer


class GridTradingBot:
    """网格交易机器人主类"""
    
    def __init__(self, symbol: str = None):
        # 交易对配置（可通过环境变量TRADING_SYMBOL或参数指定）
        self.symbol = symbol or os.getenv('TRADING_SYMBOL', 'BNB/USDT')
        self.running = False
        self.trader = None
        self.exchange = None
        self.web_server = None
        self.logger = None
        
        # 初始化组件
        self._setup_components()
    
    def _setup_components(self):
        """初始化组件"""
        # 设置日志
        setup_logging()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 加载配置
        self.config = TradingConfig(self.symbol)
        
        # 初始化数据存储
        self.storage = DataStorage(f"data/{self.symbol.replace('/', '_')}")
        
        # 初始化通知管理器
        self.notification_manager = NotificationManager(
            self.config.PUSHPLUS_TOKEN if hasattr(self.config, 'PUSHPLUS_TOKEN') else None
        )
        
        self.logger.info(f"网格交易机器人初始化完成 | 交易对: {self.symbol}")
    
    async def _run_services(self):
        """并发运行Web服务器和交易循环"""
        from aiohttp import web
        
        # 创建Web应用
        app = self.web_server.create_app()
        
        # 创建任务
        tasks = []
        
        # Web服务器任务
        web_task = asyncio.create_task(
            self._start_web_server(app)
        )
        tasks.append(web_task)
        
        # 交易循环任务
        trading_task = asyncio.create_task(
            self.trader.main_loop()
        )
        tasks.append(trading_task)
        
        self.logger.info(f"Web服务器启动在 http://{self.config.WEB_HOST}:{self.config.WEB_PORT}")
        self.logger.info("所有服务已启动")
        
        # 等待任务完成
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.logger.error(f"服务运行错误: {str(e)}")
            raise
    
    async def _start_web_server(self, app):
        """启动Web服务器"""
        from aiohttp import web
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(
            runner,
            self.config.WEB_HOST,
            self.config.WEB_PORT
        )
        
        await site.start()
        
        # 保持运行直到停止
        while self.running:
            await asyncio.sleep(1)
        
        await runner.cleanup()
    
    async def start(self):
        """启动交易机器人"""
        try:
            self.logger.info("正在启动网格交易机器人...")
            
            # 初始化交易所客户端
            self.exchange = create_exchange_client(self.config)
            await self.exchange.load_markets()
            
            # 初始化网格交易器
            self.trader = GridTrader(self.exchange, self.config)
            await self.trader.initialize()
            
            # 初始化Web服务器
            self.web_server = WebServer(self.trader, self.config)
            
            # 发送启动通知
            await self.notification_manager.send_system_notification(
                "交易机器人启动",
                f"交易对: {self.symbol}\n基准价: {self.trader.base_price}\n网格大小: {self.trader.grid_size}%",
                "SUCCESS"
            )
            
            self.running = True
            self.logger.info("网格交易机器人启动成功")
            
            # 启动Web服务器和交易循环
            await self._run_services()
            
        except Exception as e:
            self.logger.error(f"启动失败: {str(e)}")
            await self.notification_manager.send_system_notification(
                "启动失败",
                str(e),
                "ERROR"
            )
            raise
    
    async def stop(self):
        """停止交易机器人"""
        self.logger.info("正在停止网格交易机器人...")
        self.running = False
        
        try:
            if self.trader:
                await self.trader.emergency_stop()
            
            if self.exchange:
                await self.exchange.close()
            
            await self.notification_manager.send_system_notification(
                "交易机器人停止",
                f"交易对: {self.symbol}",
                "INFO"
            )
            
            self.logger.info("网格交易机器人已停止")
            
        except Exception as e:
            self.logger.error(f"停止过程中出错: {str(e)}")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"收到信号 {signum}，准备停止...")
        self.running = False
        # 触发程序退出
        import os
        os._exit(0)


async def main():
    """主函数"""
    # 解析命令行参数
    symbol = None
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    
    # 创建交易机器人
    bot = GridTradingBot(symbol)
    
    # 设置信号处理
    signal.signal(signal.SIGINT, bot._signal_handler)
    signal.signal(signal.SIGTERM, bot._signal_handler)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止...")
        await bot.stop()
    except Exception as e:
        print(f"运行错误: {str(e)}")
        await bot.stop()
        sys.exit(1)


if __name__ == "__main__":
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("错误: 需要Python 3.8或更高版本")
        sys.exit(1)
    
    # 运行主程序
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序异常退出: {str(e)}")
        sys.exit(1) 