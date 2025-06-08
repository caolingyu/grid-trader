"""
币种特定配置模块

为不同交易对提供定制化的配置参数
"""

from typing import Dict, Any

# 可用的交易对配置
AVAILABLE_SYMBOLS = {
    'BNB/USDT': 'bnb_usdt',
    'ETH/USDT': 'eth_usdt',
    'BTC/USDT': 'btc_usdt',
}

def get_symbol_config_module(symbol: str) -> str:
    """获取币种配置模块名"""
    return AVAILABLE_SYMBOLS.get(symbol, 'template') 