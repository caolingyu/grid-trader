"""
日志配置模块

提供统一的日志配置和管理
"""

import logging
import os
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


def setup_logging(
    log_level: int = logging.INFO,
    log_dir: str = "logs",
    log_file: str = "trading_system.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
):
    """
    设置日志配置
    
    Args:
        log_level: 日志级别
        log_dir: 日志目录
        log_file: 日志文件名
        max_bytes: 单个日志文件最大大小
        backup_count: 备份文件数量
    """
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # 日志文件完整路径
    log_file_path = log_path / log_file
    
    # 创建日志格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 添加文件处理器（滚动日志）
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('ccxt').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"日志系统已初始化，日志文件: {log_file_path}")


class TradingLogger:
    """交易专用日志记录器"""
    
    def __init__(self, name: str, log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 创建交易专用日志文件
        self.trade_log_file = self.log_dir / f"{name}_trades.log"
        self._setup_trade_logger()
    
    def _setup_trade_logger(self):
        """设置交易日志"""
        # 创建交易日志处理器
        trade_handler = RotatingFileHandler(
            self.trade_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=10,
            encoding='utf-8'
        )
        
        # 交易日志格式
        trade_formatter = logging.Formatter(
            '%(asctime)s - TRADE - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        trade_handler.setFormatter(trade_formatter)
        trade_handler.setLevel(logging.INFO)
        
        # 创建交易日志器
        self.trade_logger = logging.getLogger(f"{self.logger.name}.trade")
        self.trade_logger.addHandler(trade_handler)
        self.trade_logger.setLevel(logging.INFO)
        
        # 防止重复日志
        self.trade_logger.propagate = False
    
    def log_trade(self, side: str, amount: float, price: float, order_id: str, **kwargs):
        """记录交易日志"""
        trade_info = {
            'side': side,
            'amount': amount,
            'price': price,
            'order_id': order_id,
            'timestamp': datetime.now().isoformat(),
            **kwargs
        }
        
        self.trade_logger.info(
            f"{side.upper()} | Amount: {amount} | Price: {price} | "
            f"Order ID: {order_id} | {kwargs}"
        )
    
    def log_signal(self, signal_type: str, current_price: float, reason: str):
        """记录交易信号"""
        self.logger.info(
            f"SIGNAL [{signal_type}] | Price: {current_price} | Reason: {reason}"
        )
    
    def log_grid_adjustment(self, old_size: float, new_size: float, reason: str):
        """记录网格调整"""
        self.logger.info(
            f"GRID ADJUST | {old_size}% -> {new_size}% | Reason: {reason}"
        )
    
    def log_risk_event(self, event_type: str, current_value: float, limit: float):
        """记录风险事件"""
        self.logger.warning(
            f"RISK EVENT [{event_type}] | Current: {current_value} | Limit: {limit}"
        ) 