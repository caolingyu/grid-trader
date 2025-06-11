# Grid Trading System - 专业网格交易系统

> 🚀 **企业级** - 高性能、多币种、智能化的加密货币网格交易系统

一个基于 Python 的专业自动化网格交易系统，专为加密货币交易设计。采用模块化架构，支持多币种配置，提供现代化的Web监控界面和智能风险管理。

## ✨ 核心亮点

### 🎯 智能交易引擎
- **多币种支持** - 无缝支持BNB/USDT、ETH/USDT、BTC/USDT等主流交易对
- **动态网格调整** - 基于市场波动率自动调整网格间距，最大化收益
- **智能仓位管理** - 自适应仓位控制，优化资金利用率
- **实时价格追踪** - 毫秒级价格监控，精准捕捉交易机会

### 🛡️ 专业风险控制
- **多层风险防护** - 最大回撤、日亏损限制、仓位保护等多重安全机制
- **实时风险监控** - 持续监控市场波动和账户状态
- **智能熔断机制** - 异常情况下自动停止交易，保护资金安全
- **模拟交易模式** - 完整的模拟环境，零风险策略验证

### 🌐 现代化Web界面
- **实时监控面板** - WebSocket驱动的实时数据更新
- **极简设计风格** - Material Design风格，黑白灰配色，专业美观
- **响应式布局** - 完美支持桌面和移动设备
- **一键配置管理** - Web界面直接调整所有交易参数

### 🏗️ 架构设计

```
src/
├── config/                    # 配置管理
│   ├── base_config.py        # 基础配置
│   ├── trading_config.py     # 交易配置  
│   └── symbols/              # 币种特定配置
│       ├── bnb_usdt.py      # BNB/USDT配置
│       ├── eth_usdt.py      # ETH/USDT配置
│       └── template.py       # 配置模板
├── core/                     # 核心业务逻辑
│   ├── trading/             # 交易相关
│   │   ├── grid_trader.py   # 网格交易器
│   │   ├── position_controller.py  # 仓位控制器
│   │   ├── order_tracker.py # 订单跟踪器
│   │   └── risk_manager.py  # 风险管理器
│   └── exchange/            # 交易所相关
│       ├── client.py        # 统一客户端接口
│       ├── base.py          # 基础交易所类
│       └── simulation_client.py  # 模拟交易客户端
├── data/                    # 数据管理
│   └── storage.py          # 数据存储
├── utils/                   # 工具类
│   ├── logger.py           # 日志系统
│   ├── notifications.py    # 通知服务
│   ├── helpers.py          # 辅助函数
│   ├── price_calculator.py # 价格计算器
│   └── base_price_manager.py  # 基准价格管理
└── web/                     # Web界面
    ├── server.py           # Web服务器
    ├── templates/          # HTML模板
    └── static/             # 静态资源
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.13+
- 币安API账户（可选，支持模拟模式）
- 推荐服务器配置：2核2GB内存

### 2. 安装依赖

本项目使用 [uv](https://docs.astral.sh/uv/) 进行 Python 环境和依赖管理：

```bash
# 安装 uv (如果还没有安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目
git clone <repository>
cd grid_trader

# 使用 uv 创建虚拟环境并安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows
```

### 3. 环境配置

创建 `.env` 文件：

```env
# 交易模式配置 (重要！)
TRADING_MODE=simulation  # auto/simulation/live
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# 模拟交易配置
SIMULATION_INITIAL_USDT=1000.0
SIMULATION_INITIAL_BNB=0.0
SIMULATION_INITIAL_ETH=0.0
SIMULATION_INITIAL_BTC=0.0

# 交易参数
INITIAL_PRINCIPAL=1000.0
INITIAL_BASE_PRICE=0.0
MIN_TRADE_AMOUNT=20.0
MAX_POSITION_RATIO=0.9
MIN_POSITION_RATIO=0.1

# 风险控制
MAX_DRAWDOWN=-0.15
DAILY_LOSS_LIMIT=-0.05

# 通知配置
PUSHPLUS_TOKEN=your_pushplus_token
PUSHPLUS_TIMEOUT=5

# Web服务器
WEB_HOST=0.0.0.0
WEB_PORT=58080

# 系统配置
LOG_LEVEL=INFO
DEBUG_MODE=false
API_TIMEOUT=10000
RECV_WINDOW=5000
```

### 4. 启动系统

```bash
# 使用 uv 运行 (推荐)
uv run python main.py

# 或者激活虚拟环境后运行
source .venv/bin/activate
python main.py

# 指定交易对
uv run python main.py ETH/USDT

# 通过环境变量指定
TRADING_SYMBOL=BTC/USDT uv run python main.py
```

### 5. 访问Web界面

打开浏览器访问：`http://localhost:58080`

## 🔧 配置说明

### 交易模式

系统支持三种交易模式：

- **`auto`** - 自动模式：根据API密钥自动选择实盘或模拟模式
- **`simulation`** - 模拟模式：使用虚拟资金进行模拟交易
- **`live`** - 实盘模式：使用真实API进行实盘交易

### 币种配置

为新币种创建配置文件 `src/config/symbols/your_symbol.py`：

```python
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
    
    # 初始基准价格配置 (如果为0或不设置，将智能计算)
    'initial_base_price': 0.0,
    
    # 币种特定描述
    'description': 'YOUR_SYMBOL 网格交易配置',
    'recommended_capital': 1000.0,  # 推荐最小资金
    'tick_size': 0.0001,  # 最小价格变动
    'step_size': 0.001,   # 最小数量变动
}
```

### Web界面配置

Web界面支持实时配置调整：

1. 访问 `/config` 页面
2. 修改交易参数
3. 实时生效，无需重启

## 🐳 Docker部署

```bash
# 构建镜像
docker build -t grid-trader:v2 .

# 运行容器
docker run -d \
  --name grid-trader \
  --env-file .env \
  -p 58080:58080 \
  grid-trader:v2
```

## 🛠️ 开发环境

使用 uv 管理开发环境：

```bash
# 安装开发依赖
uv add --dev pytest black isort mypy

# 代码格式化
uv run black src/
uv run isort src/

# 类型检查
uv run mypy src/

# 运行测试
uv run pytest
```

## ⚠️ 风险提示

- 网格交易策略适用于震荡市场
- 请充分理解策略风险
- 建议小资金测试
- 自行承担交易风险

## 🤝 贡献指南

欢迎提交Issue和Pull Request：

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 发起Pull Request

## 📄 许可证

本项目采用MIT许可证 - 详见 [LICENSE](LICENSE) 文件

---

**Grid Trading System** - 专业、智能、安全的网格交易解决方案 🚀

*让量化交易更简单，让投资更智能* ✨ 