"""
交易对配置模板

新币种配置的模板文件
"""

SYMBOL_CONFIG = {
    # 网格参数配置
    'grid_params': {
        'initial': 2.0,
        'min': 1.0,
        'max': 4.0,
        'volatility_threshold': {
            'ranges': [
                {'range': [0, 0.20], 'grid': 1.0},
                {'range': [0.20, 0.40], 'grid': 1.5},
                {'range': [0.40, 0.60], 'grid': 2.0},
                {'range': [0.60, 0.80], 'grid': 2.5},
                {'range': [0.80, 1.00], 'grid': 3.0},
                {'range': [1.00, 1.20], 'grid': 3.5},
                {'range': [1.20, 999], 'grid': 4.0}
            ]
        }
    },
    
    # 风险参数配置
    'risk_params': {
        'max_drawdown': -0.15,
        'daily_loss_limit': -0.05,
        'position_limit': 0.9
    },
    
    # 交易参数
    'min_trade_amount': 20.0,
    'position_scale_factor': 0.2,
    'max_position_ratio': 0.9,
    'min_position_ratio': 0.1,
    
    # 币种特定描述
    'description': '默认交易配置模板',
    'recommended_capital': 1000.0,
    'tick_size': 0.0001,
    'step_size': 0.001,
} 