"""
辅助函数模块

提供通用的辅助函数
"""

from typing import Union, Optional
from decimal import Decimal, ROUND_DOWN
import math


def format_number(
    number: Union[int, float, Decimal],
    decimals: int = 2,
    use_comma: bool = True
) -> str:
    """
    格式化数字显示
    
    Args:
        number: 要格式化的数字
        decimals: 小数位数
        use_comma: 是否使用千分位分隔符
    
    Returns:
        str: 格式化后的字符串
    """
    if number is None:
        return "--"
    
    try:
        if use_comma:
            return f"{number:,.{decimals}f}"
        else:
            return f"{number:.{decimals}f}"
    except (ValueError, TypeError):
        return "--"


def calculate_percentage(
    value: Union[int, float],
    total: Union[int, float],
    decimals: int = 2
) -> float:
    """
    计算百分比
    
    Args:
        value: 数值
        total: 总数
        decimals: 小数位数
    
    Returns:
        float: 百分比
    """
    if total == 0:
        return 0.0
    
    try:
        percentage = (value / total) * 100
        return round(percentage, decimals)
    except (ZeroDivisionError, TypeError):
        return 0.0


def safe_divide(
    numerator: Union[int, float],
    denominator: Union[int, float],
    default: float = 0.0
) -> float:
    """
    安全除法，避免除零错误
    
    Args:
        numerator: 分子
        denominator: 分母
        default: 除零时的默认值
    
    Returns:
        float: 除法结果
    """
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ValueError):
        return default


def round_down_to_precision(
    value: Union[int, float],
    precision: Union[int, float]
) -> float:
    """
    向下舍入到指定精度
    
    Args:
        value: 要舍入的值
        precision: 精度（如0.001表示精确到千分位）
    
    Returns:
        float: 舍入后的值
    """
    if precision <= 0:
        return value
    
    try:
        return float(Decimal(str(value)).quantize(
            Decimal(str(precision)),
            rounding=ROUND_DOWN
        ))
    except:
        return value


def calculate_price_change(
    current_price: float,
    previous_price: float
) -> tuple[float, float]:
    """
    计算价格变动
    
    Args:
        current_price: 当前价格
        previous_price: 之前价格
    
    Returns:
        tuple: (绝对变动, 百分比变动)
    """
    if previous_price == 0:
        return 0.0, 0.0
    
    absolute_change = current_price - previous_price
    percentage_change = (absolute_change / previous_price) * 100
    
    return absolute_change, percentage_change


def format_time_duration(seconds: int) -> str:
    """
    格式化时间持续时间
    
    Args:
        seconds: 秒数
    
    Returns:
        str: 格式化的时间字符串
    """
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分钟"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}小时{minutes}分钟"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}天{hours}小时"


def validate_trading_pair(symbol: str) -> bool:
    """
    验证交易对格式
    
    Args:
        symbol: 交易对符号
    
    Returns:
        bool: 是否为有效格式
    """
    if not symbol or not isinstance(symbol, str):
        return False
    
    # 检查是否包含斜杠
    if '/' not in symbol:
        return False
    
    # 分割基础货币和计价货币
    parts = symbol.split('/')
    if len(parts) != 2:
        return False
    
    base, quote = parts
    
    # 检查长度和字符
    if not (1 <= len(base) <= 10 and 1 <= len(quote) <= 10):
        return False
    
    if not (base.isalpha() and quote.isalpha()):
        return False
    
    return True


def calculate_grid_levels(
    base_price: float,
    grid_size: float,
    num_levels: int = 10
) -> dict:
    """
    计算网格价格层级
    
    Args:
        base_price: 基准价格
        grid_size: 网格大小（百分比）
        num_levels: 层级数量
    
    Returns:
        dict: 包含买入和卖出价格层级的字典
    """
    grid_ratio = grid_size / 100
    
    buy_levels = []
    sell_levels = []
    
    for i in range(1, num_levels + 1):
        # 买入层级（向下）
        buy_price = base_price * (1 - grid_ratio * i)
        buy_levels.append(round(buy_price, 8))
        
        # 卖出层级（向上）
        sell_price = base_price * (1 + grid_ratio * i)
        sell_levels.append(round(sell_price, 8))
    
    return {
        'base_price': base_price,
        'buy_levels': buy_levels,
        'sell_levels': sell_levels,
        'grid_size': grid_size
    }


def calculate_position_size(
    available_balance: float,
    price: float,
    position_ratio: float,
    min_amount: float = 0.0
) -> float:
    """
    计算仓位大小
    
    Args:
        available_balance: 可用余额
        price: 价格
        position_ratio: 仓位比例（0-1）
        min_amount: 最小金额
    
    Returns:
        float: 计算的仓位大小
    """
    if available_balance <= 0 or price <= 0:
        return 0.0
    
    # 计算可用金额
    available_amount = available_balance * position_ratio
    
    if available_amount < min_amount:
        return 0.0
    
    # 计算数量
    quantity = available_amount / price
    
    return quantity 