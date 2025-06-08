"""
基础配置类

提供环境变量管理和基础配置功能
"""

import os
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class BaseConfig:
    """基础配置类"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._load_environment_variables()
    
    def _load_environment_variables(self):
        """加载环境变量"""
        # 交易所API配置
        self.BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
        self.BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
        
        # 首先读取用户配置的交易模式
        trading_mode = os.getenv('TRADING_MODE', 'auto').lower()
        
        # 检查API密钥有效性
        placeholder_values = [
            "your_binance_api_key_here",
            "your_binance_api_secret_here", 
            "placeholder",
            "example",
            "demo",
            "test"
        ]
        
        is_real_key = (
            self.BINANCE_API_KEY and 
            self.BINANCE_API_SECRET and
            self.BINANCE_API_KEY.lower() not in placeholder_values and
            self.BINANCE_API_SECRET.lower() not in placeholder_values and
            len(self.BINANCE_API_KEY) > 20 and
            len(self.BINANCE_API_SECRET) > 20
        )
        
        # 根据配置和API密钥状态决定最终模式
        if trading_mode == 'simulation':
            # 用户明确选择模拟模式
            self.SIMULATION_MODE = True
            self.BINANCE_API_KEY = "simulation_key"
            self.BINANCE_API_SECRET = "simulation_secret"
            self.logger.info("用户配置：启用模拟交易模式")
        elif trading_mode == 'live':
            # 用户选择实盘模式，需要验证API密钥
            if is_real_key:
                self.SIMULATION_MODE = False
                self.logger.info("用户配置：启用实盘交易模式，API密钥验证通过")
            else:
                self.SIMULATION_MODE = True
                self.BINANCE_API_KEY = "simulation_key"
                self.BINANCE_API_SECRET = "simulation_secret"
                self.logger.warning("用户配置实盘模式，但API密钥无效，自动回退到模拟模式")
        else:
            # auto模式：根据API密钥自动选择
            if is_real_key:
                self.SIMULATION_MODE = False
                self.logger.info("自动模式：检测到有效API密钥，启用实盘交易模式")
            else:
                self.SIMULATION_MODE = True
                self.BINANCE_API_KEY = "simulation_key"
                self.BINANCE_API_SECRET = "simulation_secret"
                self.logger.info("自动模式：未检测到有效API密钥，启用模拟交易模式")
        
        # 模拟模式初始余额配置（可在前端修改）
        self.SIMULATION_INITIAL_USDT = self.get_env_float('SIMULATION_INITIAL_USDT', 1000.0)
        self.SIMULATION_INITIAL_BNB = self.get_env_float('SIMULATION_INITIAL_BNB', 0.0)
        self.SIMULATION_INITIAL_ETH = self.get_env_float('SIMULATION_INITIAL_ETH', 0.0)
        self.SIMULATION_INITIAL_BTC = self.get_env_float('SIMULATION_INITIAL_BTC', 0.0)
        
        # 通知配置
        self.PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')
        self.PUSHPLUS_TIMEOUT = int(os.getenv('PUSHPLUS_TIMEOUT', '5'))
        
        # 网络配置
        self.HTTP_PROXY = os.getenv('HTTP_PROXY')
        
        # 系统配置
        self.LOG_LEVEL = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
        self.DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        
        # API配置
        self.API_TIMEOUT = int(os.getenv('API_TIMEOUT', '10000'))
        self.RECV_WINDOW = int(os.getenv('RECV_WINDOW', '5000'))
        
        # Web服务器配置
        self.WEB_HOST = os.getenv('WEB_HOST', '0.0.0.0')
        self.WEB_PORT = int(os.getenv('WEB_PORT', '58080'))
    
    def get_env_float(self, key: str, default: float = 0.0) -> float:
        """安全获取环境变量中的浮点数"""
        try:
            value = os.getenv(key)
            if value is None:
                return default
            return float(value)
        except ValueError:
            self.logger.warning(f"无效的环境变量 {key}，使用默认值 {default}")
            return default
    
    def get_env_int(self, key: str, default: int = 0) -> int:
        """安全获取环境变量中的整数"""
        try:
            value = os.getenv(key)
            if value is None:
                return default
            return int(value)
        except ValueError:
            self.logger.warning(f"无效的环境变量 {key}，使用默认值 {default}")
            return default
    
    def get_env_bool(self, key: str, default: bool = False) -> bool:
        """安全获取环境变量中的布尔值"""
        value = os.getenv(key, '').lower()
        if value in ('true', '1', 'yes', 'on'):
            return True
        elif value in ('false', '0', 'no', 'off'):
            return False
        else:
            return default
    
    def validate_config(self) -> bool:
        """验证配置有效性"""
        # 在模拟模式下，不需要验证真实的API密钥
        if getattr(self, 'SIMULATION_MODE', False):
            self.logger.info("模拟模式下配置验证通过")
            return True
        
        required_fields = [
            'BINANCE_API_KEY',
            'BINANCE_API_SECRET'
        ]
        
        for field in required_fields:
            value = getattr(self, field, None)
            if not value or value.startswith('simulation_'):
                self.logger.error(f"实盘模式下必需的配置项 {field} 未正确设置")
                return False
        
        return True 