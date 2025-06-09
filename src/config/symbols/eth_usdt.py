"""
ETH/USDT 交易对配置

针对ETH/USDT的特定参数配置
"""

SYMBOL_CONFIG = {
    # 网格参数配置
    'grid_params': {
        'initial': 2.5,  # ETH波动较大，使用稍大的网格
        'min': 1.5,
        'max': 5.0,
        'volatility_threshold': {
            'ranges': [
                {'range': [0, 0.15], 'grid': 1.5},
                {'range': [0.15, 0.30], 'grid': 2.0},
                {'range': [0.30, 0.50], 'grid': 2.5},
                {'range': [0.50, 0.70], 'grid': 3.0},
                {'range': [0.70, 0.90], 'grid': 3.5},
                {'range': [0.90, 1.20], 'grid': 4.0},
                {'range': [1.20, 999], 'grid': 5.0}
            ]
        }
    },
    
    # 风险参数配置
    'risk_params': {
        'max_drawdown': -0.20,  # ETH可承受更大回撤
        'daily_loss_limit': -0.08,
        'position_limit': 0.85
    },
    
    # 交易参数
    'min_trade_amount': 30.0,  # ETH最小交易金额稍大
    'position_scale_factor': 0.25,
    'max_position_ratio': 0.85,
    'min_position_ratio': 0.15,
    
    # 初始基准价格配置 (如果为0或不设置，将智能计算)
    'initial_base_price': 0.0,  # 使用智能计算
    
    # 币种特定描述
    'description': 'ETH/USDT 网格交易配置 - 适用于高波动性交易',
    'recommended_capital': 2000.0,  # 推荐最小资金
    'tick_size': 0.01,  # 最小价格变动
    'step_size': 0.0001,   # 最小数量变动
} 