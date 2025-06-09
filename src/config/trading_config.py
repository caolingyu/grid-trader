"""
交易配置类

提供交易相关的配置管理，支持多币种和动态参数调整
"""

import os
import logging
from typing import Any, Dict, List, Optional

from .base_config import BaseConfig


class TradingConfig(BaseConfig):
    """交易配置类"""

    def __init__(self, symbol: str = None):
        super().__init__()
        # 如果没有指定交易对，使用环境变量或默认值
        self.symbol = symbol or os.getenv('TRADING_SYMBOL', 'BNB/USDT')
        self._load_trading_config()
        self._load_symbol_specific_config()

    def _load_trading_config(self):
        """加载交易相关配置"""
        # 基础交易参数
        self.MIN_TRADE_AMOUNT = self.get_env_float("MIN_TRADE_AMOUNT", 20.0)
        self.COOLDOWN = self.get_env_int("COOLDOWN", 60)
        self.SAFETY_MARGIN = self.get_env_float("SAFETY_MARGIN", 0.95)

        # 仓位管理
        self.MAX_POSITION_RATIO = self.get_env_float("MAX_POSITION_RATIO", 0.9)
        self.MIN_POSITION_RATIO = self.get_env_float("MIN_POSITION_RATIO", 0.1)
        self.MIN_POSITION_PERCENT = self.get_env_float("MIN_POSITION_PERCENT", 0.05)
        self.MAX_POSITION_PERCENT = self.get_env_float("MAX_POSITION_PERCENT", 0.15)
        self.POSITION_SCALE_FACTOR = self.get_env_float("POSITION_SCALE_FACTOR", 0.2)

        # 风险管理
        self.MAX_DRAWDOWN = self.get_env_float("MAX_DRAWDOWN", -0.15)
        self.DAILY_LOSS_LIMIT = self.get_env_float("DAILY_LOSS_LIMIT", -0.05)
        self.RISK_FACTOR = self.get_env_float("RISK_FACTOR", 0.1)
        self.RISK_CHECK_INTERVAL = self.get_env_int("RISK_CHECK_INTERVAL", 300)

        # 网格参数
        self.INITIAL_GRID = self.get_env_float("INITIAL_GRID", 2.0)
        self.MIN_GRID_SIZE = self.get_env_float("MIN_GRID_SIZE", 1.0)
        self.MAX_GRID_SIZE = self.get_env_float("MAX_GRID_SIZE", 4.0)

        # 初始配置
        self.INITIAL_PRINCIPAL = self.get_env_float("INITIAL_PRINCIPAL", 0.0)
        # 初始基准价格现在从币种配置文件获取，不再从环境变量读取
        self.INITIAL_BASE_PRICE = 0.0  # 默认值，将在币种配置中设置

        # 系统参数
        self.MAX_RETRIES = self.get_env_int("MAX_RETRIES", 5)
        self.VOLATILITY_WINDOW = self.get_env_int("VOLATILITY_WINDOW", 24)
        self.AUTO_ADJUST_BASE_PRICE = self.get_env_bool("AUTO_ADJUST_BASE_PRICE", False)

        # 构建风险参数字典
        self.RISK_PARAMS = {
            "max_drawdown": self.MAX_DRAWDOWN,
            "daily_loss_limit": self.DAILY_LOSS_LIMIT,
            "position_limit": self.MAX_POSITION_RATIO,
        }

        # 构建网格参数字典
        self.GRID_PARAMS = {
            "initial": self.INITIAL_GRID,
            "min": self.MIN_GRID_SIZE,
            "max": self.MAX_GRID_SIZE,
            "volatility_threshold": self._get_default_volatility_thresholds(),
        }

        # 动态时间间隔参数
        self.DYNAMIC_INTERVAL_PARAMS = {
            "volatility_to_interval_hours": [
                {"range": [0, 0.20], "interval_hours": 1.0},
                {"range": [0.20, 0.40], "interval_hours": 0.5},
                {"range": [0.40, 0.80], "interval_hours": 0.25},
                {"range": [0.80, 999], "interval_hours": 0.125},
            ],
            "default_interval_hours": 1.0,
        }

    def _get_default_volatility_thresholds(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取默认的波动率阈值配置"""
        return {
            "ranges": [
                {"range": [0, 0.20], "grid": 1.0},
                {"range": [0.20, 0.40], "grid": 1.5},
                {"range": [0.40, 0.60], "grid": 2.0},
                {"range": [0.60, 0.80], "grid": 2.5},
                {"range": [0.80, 1.00], "grid": 3.0},
                {"range": [1.00, 1.20], "grid": 3.5},
                {"range": [1.20, 999], "grid": 4.0},
            ]
        }

    def _load_symbol_specific_config(self):
        """加载币种特定配置"""
        try:
            # 尝试导入币种特定配置
            symbol_key = self.symbol.replace("/", "_").lower()
            config_module = f"src.config.symbols.{symbol_key}"

            try:
                import importlib

                symbol_config = importlib.import_module(config_module)
                self._apply_symbol_config(symbol_config)
                self.logger.info(f"已加载 {self.symbol} 的特定配置")
            except ImportError:
                self.logger.info(f"未找到 {self.symbol} 的特定配置，使用默认配置")

        except Exception as e:
            self.logger.warning(f"加载币种配置时出错: {str(e)}")

    def _apply_symbol_config(self, symbol_config):
        """应用币种特定配置"""
        if hasattr(symbol_config, "SYMBOL_CONFIG"):
            config = symbol_config.SYMBOL_CONFIG

            # 更新网格参数
            if "grid_params" in config:
                self.GRID_PARAMS.update(config["grid_params"])

            # 更新风险参数
            if "risk_params" in config:
                self.RISK_PARAMS.update(config["risk_params"])

            # 更新初始基准价格
            if "initial_base_price" in config:
                self.INITIAL_BASE_PRICE = float(config["initial_base_price"])

            # 更新其他参数
            for key, value in config.items():
                if key not in ["grid_params", "risk_params", "initial_base_price"] and hasattr(
                    self, key.upper()
                ):
                    setattr(self, key.upper(), value)

    def get_flip_threshold(self) -> float:
        """获取翻转阈值"""
        return (self.INITIAL_GRID / 5) / 100

    def update_symbol(self, new_symbol: str):
        """更新交易对"""
        self.symbol = new_symbol
        self._load_symbol_specific_config()
        self.logger.info(f"交易对已更新为: {new_symbol}")

    def get_grid_size_by_volatility(self, volatility: float) -> float:
        """根据波动率获取网格大小"""
        ranges = self.GRID_PARAMS["volatility_threshold"]["ranges"]

        for range_config in ranges:
            min_vol, max_vol = range_config["range"]
            if min_vol <= volatility < max_vol:
                return range_config["grid"]

        # 如果没有匹配的范围，返回最大网格
        return ranges[-1]["grid"]

    def get_interval_by_volatility(self, volatility: float) -> float:
        """根据波动率获取调整间隔（小时）"""
        ranges = self.DYNAMIC_INTERVAL_PARAMS["volatility_to_interval_hours"]

        for range_config in ranges:
            min_vol, max_vol = range_config["range"]
            if min_vol <= volatility < max_vol:
                return range_config["interval_hours"]

        return self.DYNAMIC_INTERVAL_PARAMS["default_interval_hours"]

    def validate_trading_config(self) -> bool:
        """验证交易配置"""
        if not super().validate_config():
            return False

        # 验证仓位比例
        if self.MIN_POSITION_RATIO >= self.MAX_POSITION_RATIO:
            self.logger.error("底仓比例不能大于或等于最大仓位比例")
            return False

        # 验证网格参数
        if self.MIN_GRID_SIZE > self.MAX_GRID_SIZE:
            self.logger.error("网格最小值不能大于最大值")
            return False

        # 验证最小交易金额
        if self.MIN_TRADE_AMOUNT <= 0:
            self.logger.error("最小交易金额必须大于0")
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        return {
            "symbol": self.symbol,
            "trading_params": {
                "min_trade_amount": self.MIN_TRADE_AMOUNT,
                "initial_grid": self.INITIAL_GRID,
                "max_position_ratio": self.MAX_POSITION_RATIO,
                "min_position_ratio": self.MIN_POSITION_RATIO,
                "max_drawdown": self.MAX_DRAWDOWN,
                "daily_loss_limit": self.DAILY_LOSS_LIMIT,
            },
            "grid_params": self.GRID_PARAMS,
            "risk_params": self.RISK_PARAMS,
            "dynamic_interval_params": self.DYNAMIC_INTERVAL_PARAMS,
        }

    def __repr__(self) -> str:
        return f"TradingConfig(symbol='{self.symbol}', grid={self.INITIAL_GRID}%)"
