"""
配置管理模块

提供统一的配置管理，支持多币种和环境变量配置
"""

from .base_config import BaseConfig
from .trading_config import TradingConfig

__all__ = ['BaseConfig', 'TradingConfig'] 