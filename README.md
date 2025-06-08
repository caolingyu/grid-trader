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
│   │   ├── position_controller.py
│   │   ├── order_tracker.py
│   │   └── risk_manager.py
│   └── exchange/            # 交易所相关
│       ├── client.py        # 统一客户端接口
│       └── binance_client.py # Binance实现
├── web/                     # Web界面
│   ├── server.py           # Web服务器
│   ├── templates/          # HTML模板
│   └── static/             # 静态资源
└── utils/                   # 工具类
    ├── logger.py           # 日志系统
    ├── notifications.py    # 通知服务
    └── helpers.py          # 辅助函数
```

### 🔧 技术优势

- **模块化架构** - 清晰的代码结构，便于维护和扩展
- **异步高性能** - 基于asyncio的高并发处理架构
- **智能配置系统** - 支持热更新，无需重启服务
- **订单智能追踪** - 完整的订单生命周期管理
- **企业级日志** - 结构化日志记录，便于监控和调试
- **容器化部署** - Docker支持，一键部署和扩展

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- 币安API账户
- 推荐服务器配置：2核2GB内存

### 2. 安装依赖

```bash
git clone <repository>
cd grid_trader
pip install -r requirements.txt
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

# 交易参数
INITIAL_PRINCIPAL=1000.0
INITIAL_BASE_PRICE=600.0
MIN_TRADE_AMOUNT=20.0
MAX_POSITION_RATIO=0.9
MIN_POSITION_RATIO=0.1

# 风险控制
MAX_DRAWDOWN=-0.15
DAILY_LOSS_LIMIT=-0.05

# 通知配置
PUSHPLUS_TOKEN=your_pushplus_token

# Web服务器
WEB_HOST=0.0.0.0
WEB_PORT=58080

# 系统配置
LOG_LEVEL=INFO
DEBUG_MODE=false
```

### 4. 启动系统

```bash
# 使用默认交易对 (BNB/USDT)
python main_new.py

# 指定交易对
python main_new.py ETH/USDT

# 通过环境变量指定
TRADING_SYMBOL=BTC/USDT python main_new.py
```

### 5. 访问Web界面

打开浏览器访问：`http://localhost:58080`

## 📊 功能特性

### 🔥 核心交易功能
- ✅ **智能网格交易** - 基于波动率的动态网格调整
- ✅ **多币种支持** - 支持所有主流加密货币交易对
- ✅ **自适应策略** - 根据市场情况自动优化参数
- ✅ **精准订单管理** - 毫秒级订单执行和追踪
- ✅ **仓位智能控制** - 动态仓位管理，最大化资金效率

### 🛡️ 专业风控系统
- ✅ **实时风险监控** - 持续监控账户和市场风险
- ✅ **多重安全机制** - 最大回撤、日损限制、仓位保护
- ✅ **智能止损** - 异常情况自动停止交易
- ✅ **模拟交易** - 完整的回测和模拟环境
- ✅ **风险预警** - 及时的风险提醒和通知

### 📱 现代化监控
- ✅ **实时数据面板** - WebSocket驱动的实时更新
- ✅ **交易历史分析** - 详细的交易记录和统计
- ✅ **性能指标** - 收益率、夏普比率等专业指标
- ✅ **移动端支持** - 响应式设计，随时随地监控
- ✅ **智能通知** - PushPlus集成，重要事件即时推送

## 🔧 配置说明

### 币种配置

为新币种创建配置文件 `src/config/symbols/your_symbol.py`：

```python
SYMBOL_CONFIG = {
    'grid_params': {
        'initial': 2.0,
        'min': 1.0,
        'max': 4.0,
        'volatility_threshold': {
            'ranges': [
                {'range': [0, 0.20], 'grid': 1.0},
                {'range': [0.20, 0.40], 'grid': 1.5},
                # ... 更多配置
            ]
        }
    },
    'risk_params': {
        'max_drawdown': -0.15,
        'daily_loss_limit': -0.05,
        'position_limit': 0.9
    },
    'min_trade_amount': 20.0,
    'recommended_capital': 1000.0,
}
```

### Web界面配置

Web界面支持实时配置调整：

1. 访问 `/config` 页面
2. 修改交易参数
3. 实时生效，无需重启

## 📈 性能优势

### 🚀 核心优势

- **高性能异步** - 基于asyncio，支持高并发交易执行
- **智能缓存** - 多层缓存机制，显著提升响应速度
- **实时通信** - WebSocket实时数据推送，延迟小于100ms
- **内存优化** - 精确的内存管理，长期运行稳定
- **容错设计** - 完善的异常处理和自动恢复机制

## 🔒 安全特性

- ✅ **API密钥保护** - 环境变量存储，绝不明文保存
- ✅ **请求签名验证** - 所有API请求加密签名
- ✅ **多重风险控制** - 立体化风险防护体系
- ✅ **完整审计日志** - 所有操作可追溯
- ✅ **异常自动恢复** - 故障自愈，保障系统稳定性

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

## 📝 版本特色

### 🎯 当前版本亮点
- 🚀 **企业级架构** - 模块化设计，可扩展性强
- 🧠 **智能算法** - 基于AI的动态参数调整
- 🎨 **现代化界面** - Material Design风格，用户体验优秀
- 🛡️ **专业风控** - 多重安全机制，保障资金安全
- 📡 **实时通信** - WebSocket驱动，毫秒级响应
- 📊 **深度监控** - 全方位数据分析和可视化

## ⚠️ 风险提示

- 网格交易策略适用于震荡市场
- 请充分理解策略风险
- 建议小资金测试
- 自行承担交易风险

## 🤝 贡献指南

欢迎提交Issue和Pull Request：

1. Fork项目
2. 创建特性分支
3. 提交更改
4. 发起Pull Request

## 📄 许可证

本项目采用MIT许可证 - 详见 [LICENSE](LICENSE) 文件

---

**Grid Trading System** - 专业、智能、安全的网格交易解决方案 🚀

*让量化交易更简单，让投资更智能* ✨ 