"""
现代化的Web服务器

提供网格交易系统的Web监控界面
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles
from aiohttp import WSMsgType, web


class IPLogger:
    """IP访问日志记录器"""
    
    def __init__(self, max_records: int = 100):
        self.ip_records = []
        self.max_records = max_records
    
    def add_record(self, ip: str, path: str):
        """添加访问记录"""
        # 查找是否存在相同IP的记录
        for record in self.ip_records:
            if record['ip'] == ip:
                record['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                record['path'] = path
                return
        
        # 如果是新IP，添加新记录
        record = {
            'ip': ip,
            'path': path,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.ip_records.append(record)
        
        # 如果超出最大记录数，删除最早的记录
        if len(self.ip_records) > self.max_records:
            self.ip_records.pop(0)
    
    def get_records(self):
        """获取访问记录"""
        return self.ip_records


class WebServer:
    """Web服务器类"""
    
    def __init__(self, trader, config):
        self.trader = trader
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ip_logger = IPLogger()
        self.app = None
        self.websockets = set()  # 存储WebSocket连接
        self.start_time = time.time()
    
    def create_app(self) -> web.Application:
        """创建web应用"""
        app = web.Application()
        
        # 设置应用数据
        app['trader'] = self.trader
        app['config'] = self.config
        app['ip_logger'] = self.ip_logger
        app['web_server'] = self
        
        # 设置路由
        self._setup_routes(app)
        
        # 设置中间件
        app.middlewares.append(self._error_middleware)
        
        self.app = app
        return app
    
    def _setup_routes(self, app: web.Application):
        """设置路由"""
        # 静态文件路由
        static_path = Path(__file__).parent / 'static'
        if static_path.exists():
            app.router.add_static('/static/', path=static_path, name='static')
        
        # 模板路由
        app.router.add_get('/', self.handle_index)
        app.router.add_get('/trading', self.handle_trading)
        app.router.add_get('/config', self.handle_config)
        app.router.add_get('/logs', self.handle_logs)
        
        # API路由
        app.router.add_get('/status', self.handle_status)
        app.router.add_get('/api/trader-data', self.handle_trader_data)
        app.router.add_get('/trader-data', self.handle_trader_data)  # 兼容性
        app.router.add_post('/api/config', self.handle_update_config)
        app.router.add_post('/update-config', self.handle_update_config)  # 兼容性
        app.router.add_get('/api/logs', self.handle_logs_api)
        app.router.add_get('/api/symbols', self.handle_symbols)
        app.router.add_post('/api/switch-symbol', self.handle_switch_symbol)
        
        # 模拟模式专用API
        app.router.add_get('/api/simulation/config', self.handle_get_simulation_config)
        app.router.add_post('/api/simulation/config', self.handle_update_simulation_config)
        app.router.add_post('/api/simulation/reset', self.handle_reset_simulation)
        
        # WebSocket路由
        app.router.add_get('/ws', self.handle_websocket)
    
    @web.middleware
    async def _error_middleware(self, request, handler):
        """错误处理中间件"""
        try:
            # 记录IP访问
            ip = request.remote
            self.ip_logger.add_record(ip, request.path)
            
            response = await handler(request)
            return response
        except web.HTTPException as ex:
            return ex
        except Exception as e:
            self.logger.error(f"Web服务器错误: {str(e)}")
            return web.json_response(
                {'error': 'Internal server error'},
                status=500
            )
    
    async def handle_index(self, request):
        """首页处理器"""
        return await self._serve_template('index.html')
    
    async def handle_trading(self, request):
        """交易页面处理器"""
        return await self._serve_template('trading.html')
    
    async def handle_config(self, request):
        """配置页面处理器"""
        return await self._serve_template('config.html')
    
    async def handle_logs(self, request):
        """日志页面处理器"""
        return await self._serve_template('logs.html')
    
    async def _serve_template(self, template_name: str) -> web.Response:
        """服务模板文件"""
        template_path = Path(__file__).parent / 'templates' / template_name
        
        if not template_path.exists():
            return web.Response(text=f"模板文件 {template_name} 不存在", status=404)
        
        try:
            async with aiofiles.open(template_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
            
            return web.Response(text=content, content_type='text/html')
        except Exception as e:
            self.logger.error(f"读取模板文件失败: {str(e)}")
            return web.Response(text="读取模板文件失败", status=500)
    
    async def handle_status(self, request):
        """状态API处理器"""
        try:
            trader = request.app['trader']
            
            # 获取基础数据
            if not trader.initialized:
                return web.json_response({
                    'status': 'initializing',
                    'message': '系统正在初始化...'
                })
            
            # 安全获取当前价格
            try:
                current_price = await trader._get_latest_price()
            except Exception as e:
                self.logger.error(f"获取当前价格失败: {str(e)}")
                current_price = trader.current_price or 0
            
            # 安全获取余额信息
            try:
                balance = await trader.exchange.fetch_balance()
                # 动态获取交易对的基础和报价资产
                symbol_parts = trader.symbol.split('/')
                base_asset = symbol_parts[0] if len(symbol_parts) >= 2 else 'BNB'
                quote_asset = symbol_parts[1] if len(symbol_parts) >= 2 else 'USDT'
                
                quote_balance = balance.get('free', {}).get(quote_asset, 0)
                base_balance = balance.get('free', {}).get(base_asset, 0)
            except Exception as e:
                self.logger.error(f"获取余额失败: {str(e)}")
                # 默认使用USDT和当前交易对的基础资产
                symbol_parts = getattr(trader, 'symbol', 'BNB/USDT').split('/')
                base_asset = symbol_parts[0] if len(symbol_parts) >= 2 else 'BNB'
                quote_asset = symbol_parts[1] if len(symbol_parts) >= 2 else 'USDT'
                quote_balance = 0
                base_balance = 0
            
            # 安全计算总资产
            try:
                total_assets = await trader._get_total_assets()
            except Exception as e:
                self.logger.error(f"获取总资产失败: {str(e)}")
                # 手动计算总资产
                if current_price and current_price > 0:
                    total_assets = quote_balance + (base_balance * current_price)
                else:
                    total_assets = quote_balance
            
            # 安全计算盈亏
            try:
                initial_principal = getattr(trader.config, 'INITIAL_PRINCIPAL', 1000.0)
                total_profit = total_assets - initial_principal if initial_principal > 0 else 0
            except Exception as e:
                self.logger.error(f"计算盈亏失败: {str(e)}")
                total_profit = 0
            
            # 安全获取仓位比例
            try:
                position_ratio = await trader._get_position_ratio()
            except Exception as e:
                self.logger.error(f"获取仓位比例失败: {str(e)}")
                position_ratio = 0.0
            
            # 安全计算网格上下轨
            try:
                upper_band = trader._get_upper_band()
                lower_band = trader._get_lower_band()
            except Exception as e:
                self.logger.error(f"计算网格上下轨失败: {str(e)}")
                # 手动计算网格上下轨
                base_price = getattr(trader, 'base_price', current_price or 600.0)
                grid_size = getattr(trader, 'grid_size', 2.0)
                grid_multiplier = grid_size / 100.0
                upper_band = base_price * (1 + grid_multiplier)
                lower_band = base_price * (1 - grid_multiplier)
            
            # 安全获取触发阈值
            try:
                threshold = trader.config.get_flip_threshold()
            except Exception as e:
                self.logger.error(f"获取触发阈值失败: {str(e)}")
                threshold = 0.004  # 默认0.4%
            
            # 安全计算目标委托金额
            try:
                target_amount = await trader.calculate_trade_amount('buy', current_price)
            except Exception as e:
                self.logger.error(f"计算目标委托金额失败: {str(e)}")
                target_amount = 0
            
            data = {
                'status': 'running',
                'symbol': getattr(trader, 'symbol', 'BNB/USDT'),
                'current_price': current_price or 0,
                'base_price': getattr(trader, 'base_price', current_price or 600.0),
                'grid_size': getattr(trader, 'grid_size', 2.0),
                'grid_upper_band': upper_band,
                'grid_lower_band': lower_band,
                'threshold': threshold,
                'total_assets': total_assets,
                'total_profit': total_profit,
                'quote_balance': quote_balance,
                'base_balance': base_balance,
                'quote_asset': quote_asset,
                'base_asset': base_asset,
                'position_percentage': position_ratio * 100,
                'target_order_amount': target_amount,
                'last_trade_time': getattr(trader, 'last_trade_time', None),
                'last_trade_price': getattr(trader, 'last_trade_price', None),
                'uptime': time.time() - self.start_time,
                'timestamp': time.time()
            }
            
            # 广播数据到WebSocket客户端
            await self._broadcast_to_websockets(data)
            
            return web.json_response(data)
            
        except Exception as e:
            self.logger.error(f"获取状态数据失败: {str(e)}")
            # 返回基础的错误状态，确保前端不会崩溃
            return web.json_response({
                'status': 'error',
                'message': str(e),
                'symbol': 'BNB/USDT',
                'current_price': 0,
                'base_price': 600.0,
                'grid_size': 2.0,
                'grid_upper_band': 612.0,
                'grid_lower_band': 588.0,
                'threshold': 0.004,
                'total_assets': 0,
                'total_profit': 0,
                'quote_balance': 0,
                'base_balance': 0,
                'quote_asset': 'USDT',
                'base_asset': 'BNB',
                'position_percentage': 0,
                'target_order_amount': 0,
                'last_trade_time': None,
                'last_trade_price': None,
                'uptime': time.time() - self.start_time,
                'timestamp': time.time()
            }, status=200)  # 返回200状态码，避免前端显示错误
    
    async def handle_trader_data(self, request):
        """交易器详细数据API"""
        try:
            trader = request.app['trader']
            
            if not trader.initialized:
                return web.json_response({'error': '交易器未初始化'}, status=400)
            
            # 安全获取交易历史
            try:
                trade_history = trader.order_tracker.trade_history[-20:]  # 最近20笔交易
            except Exception as e:
                self.logger.error(f"获取交易历史失败: {str(e)}")
                trade_history = []
            
            # 安全获取风险数据
            try:
                risk_data = {
                    'max_drawdown': getattr(trader.config, 'MAX_DRAWDOWN', -0.15),
                    'daily_loss_limit': getattr(trader.config, 'DAILY_LOSS_LIMIT', -0.05),
                    'current_drawdown': 0,  # 需要计算
                    'position_limit': getattr(trader.config, 'MAX_POSITION_RATIO', 0.9)
                }
            except Exception as e:
                self.logger.error(f"获取风险数据失败: {str(e)}")
                risk_data = {}
            
            # 安全获取网格参数
            try:
                grid_params = getattr(trader.config, 'GRID_PARAMS', {})
            except Exception as e:
                self.logger.error(f"获取网格参数失败: {str(e)}")
                grid_params = {}
            
            # 构建配置数据 - 确保包含所有前端需要的字段
            try:
                config_data = {
                    'trading_params': {
                        'initial_principal': getattr(trader.config, 'INITIAL_PRINCIPAL', 1000.0),
                        'initial_base_price': getattr(trader.config, 'INITIAL_BASE_PRICE', 600.0),
                        'min_trade_amount': getattr(trader.config, 'MIN_TRADE_AMOUNT', 20.0),
                        'initial_grid': getattr(trader.config, 'INITIAL_GRID', 2.0),
                        'min_grid_size': getattr(trader.config, 'MIN_GRID_SIZE', 1.0),
                        'max_grid_size': getattr(trader.config, 'MAX_GRID_SIZE', 4.0),
                        'max_position_ratio': getattr(trader.config, 'MAX_POSITION_RATIO', 0.9),
                        'min_position_ratio': getattr(trader.config, 'MIN_POSITION_RATIO', 0.1),
                        'position_scale_factor': getattr(trader.config, 'POSITION_SCALE_FACTOR', 0.2),
                        'max_drawdown': getattr(trader.config, 'MAX_DRAWDOWN', -0.15),
                        'daily_loss_limit': getattr(trader.config, 'DAILY_LOSS_LIMIT', -0.05),
                        'risk_factor': getattr(trader.config, 'RISK_FACTOR', 0.1),
                        'risk_check_interval': getattr(trader.config, 'RISK_CHECK_INTERVAL', 300),
                        'max_retries': getattr(trader.config, 'MAX_RETRIES', 3),
                        'volatility_window': getattr(trader.config, 'VOLATILITY_WINDOW', 24),
                        'cooldown': getattr(trader.config, 'COOLDOWN', 60),
                        'safety_margin': getattr(trader.config, 'SAFETY_MARGIN', 0.95)
                    }
                }
                
                # 如果有to_dict方法，也尝试调用
                if hasattr(trader.config, 'to_dict'):
                    try:
                        full_config = trader.config.to_dict()
                        config_data.update(full_config)
                    except Exception as e:
                        self.logger.warning(f"调用config.to_dict()失败: {str(e)}")
                        
            except Exception as e:
                self.logger.error(f"构建配置数据失败: {str(e)}")
                # 提供基础的默认配置
                config_data = {
                    'trading_params': {
                        'initial_principal': 1000.0,
                        'initial_base_price': 600.0,
                        'min_trade_amount': 20.0,
                        'initial_grid': 2.0,
                        'min_grid_size': 1.0,
                        'max_grid_size': 4.0,
                        'max_position_ratio': 0.9,
                        'min_position_ratio': 0.1,
                        'position_scale_factor': 0.2,
                        'max_drawdown': -0.15,
                        'daily_loss_limit': -0.05,
                        'risk_factor': 0.1,
                        'risk_check_interval': 300,
                        'max_retries': 3,
                        'volatility_window': 24,
                        'cooldown': 60,
                        'safety_margin': 0.95
                    }
                }
            
            data = {
                'trade_history': trade_history,
                'risk_data': risk_data,
                'grid_params': grid_params,
                'volatility_window': getattr(trader.config, 'VOLATILITY_WINDOW', 24),
                'config': config_data
            }
            
            return web.json_response(data)
            
        except Exception as e:
            self.logger.error(f"获取交易器数据失败: {str(e)}")
            # 返回基础的默认数据，确保前端不会崩溃
            return web.json_response({
                'error': str(e),
                'trade_history': [],
                'risk_data': {},
                'grid_params': {},
                'volatility_window': 24,
                'config': {
                    'trading_params': {
                        'initial_principal': 1000.0,
                        'initial_base_price': 600.0,
                        'min_trade_amount': 20.0,
                        'initial_grid': 2.0,
                        'min_grid_size': 1.0,
                        'max_grid_size': 4.0,
                        'max_position_ratio': 0.9,
                        'min_position_ratio': 0.1,
                        'position_scale_factor': 0.2,
                        'max_drawdown': -0.15,
                        'daily_loss_limit': -0.05,
                        'risk_factor': 0.1,
                        'risk_check_interval': 300,
                        'max_retries': 3,
                        'volatility_window': 24,
                        'cooldown': 60,
                        'safety_margin': 0.95
                    }
                }
            }, status=200)
    
    async def handle_symbols(self, request):
        """获取可用交易对"""
        try:
            from src.config.symbols import AVAILABLE_SYMBOLS
            
            symbols_data = []
            for symbol, module_name in AVAILABLE_SYMBOLS.items():
                symbols_data.append({
                    'symbol': symbol,
                    'name': symbol.replace('/', ' / '),
                    'active': symbol == self.trader.symbol
                })
            
            return web.json_response({'symbols': symbols_data})
            
        except Exception as e:
            self.logger.error(f"获取交易对失败: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_switch_symbol(self, request):
        """切换交易对"""
        try:
            data = await request.json()
            new_symbol = data.get('symbol')
            
            if not new_symbol:
                return web.json_response({'error': '无效的交易对'}, status=400)
            
            from src.config.symbols import AVAILABLE_SYMBOLS
            if new_symbol not in AVAILABLE_SYMBOLS:
                return web.json_response({'error': '不支持的交易对'}, status=400)
            
            # 更新交易器配置
            self.trader.config.update_symbol(new_symbol)
            self.trader.symbol = new_symbol
            
            # 重新初始化
            await self.trader._reinitialize()
            
            return web.json_response({
                'success': True,
                'message': f'交易对已切换为 {new_symbol}'
            })
            
        except Exception as e:
            self.logger.error(f"切换交易对失败: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_update_config(self, request):
        """更新配置"""
        try:
            data = await request.json()
            self.logger.info(f"收到配置更新请求: {data}")
            
            if not data:
                return web.json_response({'error': '配置数据为空'}, status=400)
            
            # 记录更新前的配置
            old_config = {}
            updated_fields = []
            
            # 更新配置参数
            for key, value in data.items():
                if key in ['symbol']:  # 跳过只读字段
                    continue
                    
                config_key = key.upper()
                
                # 检查配置属性是否存在
                if hasattr(self.trader.config, config_key):
                    old_value = getattr(self.trader.config, config_key)
                    old_config[config_key] = old_value
                    
                    # 类型转换
                    try:
                        if isinstance(old_value, bool):
                            new_value = bool(value)
                        elif isinstance(old_value, int):
                            new_value = int(float(value))
                        elif isinstance(old_value, float):
                            new_value = float(value)
                        else:
                            new_value = str(value)
                        
                        setattr(self.trader.config, config_key, new_value)
                        updated_fields.append(f"{config_key}: {old_value} -> {new_value}")
                        
                    except (ValueError, TypeError) as e:
                        self.logger.error(f"配置字段 {config_key} 类型转换失败: {str(e)}")
                        return web.json_response({
                            'error': f'配置字段 {config_key} 的值 {value} 无效'
                        }, status=400)
                else:
                    self.logger.warning(f"未知的配置字段: {config_key}")
            
            if not updated_fields:
                return web.json_response({
                    'error': '没有有效的配置字段被更新'
                }, status=400)
            
            # 验证配置
            try:
                if hasattr(self.trader.config, 'validate_trading_config'):
                    if not self.trader.config.validate_trading_config():
                        # 恢复旧配置
                        for config_key, old_value in old_config.items():
                            setattr(self.trader.config, config_key, old_value)
                        
                        return web.json_response({
                            'error': '配置验证失败，已恢复原配置'
                        }, status=400)
            except Exception as e:
                self.logger.error(f"配置验证出错: {str(e)}")
                # 恢复旧配置
                for config_key, old_value in old_config.items():
                    setattr(self.trader.config, config_key, old_value)
                
                return web.json_response({
                    'error': f'配置验证失败: {str(e)}'
                }, status=400)
            
            # 记录成功更新的配置
            self.logger.info(f"配置更新成功: {', '.join(updated_fields)}")
            
            # 尝试保存配置到文件
            try:
                if hasattr(self.trader.config, 'save_config'):
                    self.trader.config.save_config()
                    self.logger.info("配置已保存到文件")
            except Exception as e:
                self.logger.warning(f"保存配置到文件失败: {str(e)}")
            
            # 通知交易器配置已更新
            try:
                if hasattr(self.trader, 'on_config_updated'):
                    await self.trader.on_config_updated()
            except Exception as e:
                self.logger.warning(f"通知交易器配置更新失败: {str(e)}")
            
            return web.json_response({
                'success': True,
                'message': f'配置已更新: {len(updated_fields)} 项配置生效',
                'updated_fields': updated_fields
            })
            
        except json.JSONDecodeError:
            return web.json_response({'error': '无效的JSON数据'}, status=400)
        except Exception as e:
            self.logger.error(f"更新配置失败: {str(e)}")
            return web.json_response({'error': f'更新配置失败: {str(e)}'}, status=500)
    
    async def handle_logs_api(self, request):
        """日志API处理器"""
        try:
            limit = int(request.query.get('limit', 100))
            level = request.query.get('level', '').upper()
            
            # 获取日志记录
            logs = []
            
            # 尝试从多个可能的日志文件路径读取
            possible_log_paths = [
                Path.cwd() / 'logs' / 'grid_trader.log',
                Path.cwd() / 'logs' / 'trading_system.log',
                Path.cwd() / 'grid_trader.log',
                Path.cwd() / 'trading_system.log'
            ]
            
            log_file_found = False
            for log_file_path in possible_log_paths:
                if log_file_path.exists():
                    log_file_found = True
                    try:
                        with open(log_file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            
                        # 解析最近的日志行
                        recent_lines = lines[-limit*3:] if len(lines) > limit*3 else lines
                        
                        for line in recent_lines:
                            if not line.strip():
                                continue
                                
                            # 尝试解析不同的日志格式
                            parsed_log = self._parse_log_line(line.strip())
                            if parsed_log:
                                # 过滤级别
                                if level and parsed_log['level'] != level:
                                    continue
                                logs.append(parsed_log)
                            
                    except Exception as e:
                        self.logger.error(f"读取日志文件 {log_file_path} 失败: {str(e)}")
                    
                    break  # 找到第一个可用的日志文件就停止
            
            # 如果没有从文件读取到日志，返回一些示例日志
            if not logs:
                current_time = time.time()
                self.logger.warning(f"未找到日志文件，尝试的路径: {[str(p) for p in possible_log_paths]}")
                logs = [
                    {
                        'timestamp': current_time - 300,
                        'level': 'INFO',
                        'module': 'GridTrader',
                        'message': '网格交易系统已启动'
                    },
                    {
                        'timestamp': current_time - 200,
                        'level': 'INFO',
                        'module': 'WebServer',
                        'message': 'Web服务器已启动'
                    },
                    {
                        'timestamp': current_time - 100,
                        'level': 'INFO',
                        'module': 'TradingEngine',
                        'message': '开始监控价格变化'
                    },
                    {
                        'timestamp': current_time - 50,
                        'level': 'INFO',
                        'module': 'GridTrader',
                        'message': '网格参数更新完成'
                    },
                    {
                        'timestamp': current_time - 10,
                        'level': 'WARNING',
                        'module': 'WebServer',
                        'message': f'日志文件未找到，日志文件存在: {log_file_found}'
                    }
                ]
            
            # 按时间排序并限制数量
            logs.sort(key=lambda x: x['timestamp'], reverse=True)
            logs = logs[:limit]
            
            return web.json_response({'logs': logs})
            
        except Exception as e:
            self.logger.error(f"获取日志失败: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
    
    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析日志行"""
        try:
            # 格式1: 2025-06-08 21:42:07 - TradingConfig - WARNING - 未检测到有效API密钥，启用模拟交易模式
            if ' - ' in line:
                parts = line.split(' - ', 3)
                if len(parts) >= 4:
                    timestamp_str = parts[0]
                    module = parts[1]
                    log_level = parts[2]
                    message = parts[3]
                    
                    # 解析时间戳
                    try:
                        from datetime import datetime
                        # 尝试多种时间格式
                        timestamp_formats = [
                            '%Y-%m-%d %H:%M:%S,%f',
                            '%Y-%m-%d %H:%M:%S',
                            '%m/%d/%Y %H:%M:%S',
                            '%d/%m/%Y %H:%M:%S'
                        ]
                        
                        timestamp = None
                        for fmt in timestamp_formats:
                            try:
                                timestamp = datetime.strptime(timestamp_str, fmt).timestamp()
                                break
                            except:
                                continue
                        
                        if timestamp is None:
                            timestamp = time.time()
                            
                    except:
                        timestamp = time.time()
                    
                    return {
                        'timestamp': timestamp,
                        'level': log_level.strip(),
                        'module': module.strip(),
                        'message': message.strip()
                    }
            
            # 格式2: [2025-06-08 21:42:07] INFO: GridTrader: 消息内容
            elif line.startswith('[') and ']' in line:
                bracket_end = line.find(']')
                if bracket_end > 0:
                    timestamp_str = line[1:bracket_end]
                    rest = line[bracket_end+1:].strip()
                    
                    if ':' in rest:
                        parts = rest.split(':', 2)
                        if len(parts) >= 3:
                            log_level = parts[0].strip()
                            module = parts[1].strip()
                            message = parts[2].strip()
                            
                            try:
                                from datetime import datetime
                                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').timestamp()
                            except:
                                timestamp = time.time()
                            
                            return {
                                'timestamp': timestamp,
                                'level': log_level,
                                'module': module,
                                'message': message
                            }
            
            return None
            
        except Exception as e:
            self.logger.error(f"解析日志行失败: {str(e)} | 行内容: {line}")
            return None
    
    async def handle_websocket(self, request):
        """WebSocket处理器"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # 添加到连接集合
        self.websockets.add(ws)
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_websocket_message(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_str(json.dumps({'error': 'Invalid JSON'}))
                elif msg.type == WSMsgType.ERROR:
                    self.logger.error(f'WebSocket错误: {ws.exception()}')
        except Exception as e:
            self.logger.error(f"WebSocket处理错误: {str(e)}")
        finally:
            # 从连接集合中移除
            self.websockets.discard(ws)
        
        return ws
    
    async def _handle_websocket_message(self, ws, data):
        """处理WebSocket消息"""
        message_type = data.get('type')
        
        if message_type == 'subscribe':
            # 订阅实时数据
            await ws.send_str(json.dumps({
                'type': 'subscribed',
                'message': '已订阅实时数据'
            }))
        
        elif message_type == 'get_status':
            # 获取当前状态
            status_data = await self._get_status_data()
            await ws.send_str(json.dumps({
                'type': 'status',
                'data': status_data
            }))
    
    async def _broadcast_to_websockets(self, data):
        """向所有WebSocket客户端广播数据"""
        if not self.websockets:
            return
        
        message = json.dumps({
            'type': 'update',
            'data': data
        })
        
        # 移除已关闭的连接
        closed_connections = set()
        for ws in self.websockets:
            try:
                await ws.send_str(message)
            except Exception:
                closed_connections.add(ws)
        
        # 清理关闭的连接
        for ws in closed_connections:
            self.websockets.discard(ws)
    
    async def _get_status_data(self):
        """获取状态数据（内部使用）"""
        # 这里复用handle_status的逻辑
        return {}
    
    async def handle_get_simulation_config(self, request):
        """获取模拟模式配置"""
        try:
            trader = request.app['trader']
            
            # 检查是否是模拟模式
            if not getattr(trader.config, 'SIMULATION_MODE', False):
                return web.json_response({'error': '当前不是模拟模式'}, status=400)
            
            # 动态获取当前交易对的基础和报价资产
            symbol_parts = trader.symbol.split('/')
            base_asset = symbol_parts[0] if len(symbol_parts) >= 2 else 'BNB'
            quote_asset = symbol_parts[1] if len(symbol_parts) >= 2 else 'USDT'
            
            # 获取模拟配置
            config_data = {
                'trading_mode': 'simulation',
                'symbol': trader.symbol,
                'base_asset': base_asset,
                'quote_asset': quote_asset,
                'simulation_balances': {
                    quote_asset: getattr(trader.config, f'SIMULATION_INITIAL_{quote_asset}', 1000.0),
                    base_asset: getattr(trader.config, f'SIMULATION_INITIAL_{base_asset}', 0.0),
                    'USDT': getattr(trader.config, 'SIMULATION_INITIAL_USDT', 1000.0),
                    'BNB': getattr(trader.config, 'SIMULATION_INITIAL_BNB', 0.0),
                    'ETH': getattr(trader.config, 'SIMULATION_INITIAL_ETH', 0.0),
                    'BTC': getattr(trader.config, 'SIMULATION_INITIAL_BTC', 0.0)
                },
                'current_balances': {},
                'initial_principal': getattr(trader.config, 'INITIAL_PRINCIPAL', 1000.0)
            }
            
            # 获取当前实际余额
            if hasattr(trader.exchange, 'get_simulation_balances'):
                config_data['current_balances'] = trader.exchange.get_simulation_balances()
            
            return web.json_response(config_data)
            
        except Exception as e:
            self.logger.error(f"获取模拟配置失败: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_update_simulation_config(self, request):
        """更新模拟模式配置"""
        try:
            trader = request.app['trader']
            
            # 检查是否是模拟模式
            if not getattr(trader.config, 'SIMULATION_MODE', False):
                return web.json_response({'error': '当前不是模拟模式'}, status=400)
            
            data = await request.json()
            self.logger.info(f"收到模拟配置更新请求: {data}")
            
            updated_fields = []
            
            # 获取当前值
            current_usdt = getattr(trader.config, 'SIMULATION_INITIAL_USDT', 1000.0)
            current_principal = getattr(trader.config, 'INITIAL_PRINCIPAL', 1000.0)
            
            new_usdt = current_usdt
            new_principal = current_principal
            
            # 更新模拟余额配置
            if 'simulation_balances' in data:
                balances = data['simulation_balances']
                
                # 更新配置对象
                for asset, amount in balances.items():
                    config_key = f'SIMULATION_INITIAL_{asset}'
                    if hasattr(trader.config, config_key):
                        old_value = getattr(trader.config, config_key)
                        setattr(trader.config, config_key, float(amount))
                        updated_fields.append(f"{config_key}: {old_value} -> {amount}")
                        
                        # 记录新的USDT值
                        if asset == 'USDT':
                            new_usdt = float(amount)
                
                # 更新模拟交易所余额
                if hasattr(trader.exchange, 'update_simulation_balances'):
                    await trader.exchange.update_simulation_balances(balances)
            
            # 更新初始本金
            if 'initial_principal' in data:
                old_principal = getattr(trader.config, 'INITIAL_PRINCIPAL', 1000.0)
                new_principal = float(data['initial_principal'])
                trader.config.INITIAL_PRINCIPAL = new_principal
                updated_fields.append(f"INITIAL_PRINCIPAL: {old_principal} -> {new_principal}")
            
            # 在模拟模式下，确保初始本金和USDT余额同步
            # 优先使用初始本金的值来同步USDT余额
            if 'initial_principal' in data and 'simulation_balances' in data:
                # 两者都更新，使用初始本金作为准确值
                sync_value = new_principal
                trader.config.SIMULATION_INITIAL_USDT = sync_value
                updated_fields.append(f"同步模拟USDT余额: {new_usdt} -> {sync_value}")
                
                # 同步更新模拟交易所
                if hasattr(trader.exchange, 'update_simulation_balances'):
                    sync_balances = data['simulation_balances'].copy()
                    sync_balances['USDT'] = sync_value
                    await trader.exchange.update_simulation_balances(sync_balances)
                    
            elif 'initial_principal' in data:
                # 只更新了初始本金，同步USDT余额
                trader.config.SIMULATION_INITIAL_USDT = new_principal
                updated_fields.append(f"同步模拟USDT余额: {current_usdt} -> {new_principal}")
                
                # 同步更新模拟交易所
                if hasattr(trader.exchange, 'update_simulation_balances'):
                    # 动态获取当前交易对的资产
                    symbol_parts = trader.symbol.split('/')
                    base_asset = symbol_parts[0] if len(symbol_parts) >= 2 else 'BNB'
                    quote_asset = symbol_parts[1] if len(symbol_parts) >= 2 else 'USDT'
                    
                    sync_balances = {quote_asset: new_principal}
                    # 将其他资产设为0（保持其他币种余额不变）
                    for asset in ['USDT', 'BNB', 'ETH', 'BTC']:
                        if asset != quote_asset and asset not in sync_balances:
                            sync_balances[asset] = 0
                    await trader.exchange.update_simulation_balances(sync_balances)
                    
            elif 'simulation_balances' in data and 'USDT' in data['simulation_balances']:
                # 只更新了模拟余额，同步初始本金
                trader.config.INITIAL_PRINCIPAL = new_usdt
                updated_fields.append(f"同步初始本金: {current_principal} -> {new_usdt}")
            
            # 记录更新
            if updated_fields:
                self.logger.info(f"模拟配置更新成功: {', '.join(updated_fields)}")
            
            return web.json_response({
                'success': True,
                'message': f'模拟配置已更新: {len(updated_fields)} 项配置生效',
                'updated_fields': updated_fields
            })
            
        except json.JSONDecodeError:
            return web.json_response({'error': '无效的JSON数据'}, status=400)
        except Exception as e:
            self.logger.error(f"更新模拟配置失败: {str(e)}")
            return web.json_response({'error': f'更新模拟配置失败: {str(e)}'}, status=500)
    
    async def handle_reset_simulation(self, request):
        """重置模拟账户"""
        try:
            trader = request.app['trader']
            
            # 检查是否是模拟模式
            if not getattr(trader.config, 'SIMULATION_MODE', False):
                return web.json_response({'error': '当前不是模拟模式'}, status=400)
            
            # 重置模拟交易所余额
            if hasattr(trader.exchange, 'reset_simulation_balances'):
                success = await trader.exchange.reset_simulation_balances()
                if success:
                    self.logger.info("模拟账户已重置")
                    return web.json_response({
                        'success': True,
                        'message': '模拟账户已重置到初始状态'
                    })
                else:
                    return web.json_response({'error': '重置失败'}, status=500)
            else:
                return web.json_response({'error': '模拟交易所不支持重置功能'}, status=400)
            
        except Exception as e:
            self.logger.error(f"重置模拟账户失败: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)


def create_app(trader, config) -> web.Application:
    """创建Web应用实例"""
    server = WebServer(trader, config)
    return server.create_app()


async def start_web_server(trader, config=None):
    """启动Web服务器"""
    if config is None:
        config = trader.config
    
    logger = logging.getLogger('WebServer')
    
    try:
        app = create_app(trader, config)
        
        # 启动服务器
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(
            runner, 
            host=config.WEB_HOST, 
            port=config.WEB_PORT
        )
        
        await site.start()
        
        logger.info(f"Web服务器已启动: http://{config.WEB_HOST}:{config.WEB_PORT}")
        
        # 保持服务器运行
        while True:
            await asyncio.sleep(3600)  # 每小时检查一次
            
    except Exception as e:
        logger.error(f"Web服务器启动失败: {str(e)}")
        raise 