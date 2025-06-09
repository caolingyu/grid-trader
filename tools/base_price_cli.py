#!/usr/bin/env python3
"""
基准价格管理命令行工具

用于分析和设置交易对的基准价格
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.trading_config import TradingConfig
from src.core.exchange.client import ExchangeClient
from src.core.exchange.simulation_client import SimulationExchangeClient
from src.utils.base_price_manager import BasePriceManager
from src.config.symbols import get_available_symbols


async def analyze_symbol(args):
    """分析单个交易对"""
    try:
        # 初始化配置
        config = TradingConfig(symbol=args.symbol)
        
        # 初始化交易所客户端
        if args.simulation:
            exchange = SimulationExchangeClient(config)
        else:
            exchange = ExchangeClient(config)
        
        await exchange.load_markets()
        
        # 初始化基准价格管理器
        manager = BasePriceManager()
        
        # 分析价格
        result = await manager.analyze_symbol_price(exchange, args.symbol)
        
        # 显示报告
        manager.print_analysis_report(result)
        
        # 如果用户想要更新基准价格
        if args.update and "recommendations" in result:
            suggested_price = result["recommendations"].get("suggested_base_price")
            if suggested_price:
                print(f"\n🔄 准备更新基准价格为: {suggested_price:.4f}")
                confirm = input("确认更新? (y/N): ")
                if confirm.lower() == 'y':
                    success = await manager.update_symbol_base_price(args.symbol, suggested_price)
                    if success:
                        print("✅ 基准价格更新成功!")
                    else:
                        print("❌ 基准价格更新失败!")
                else:
                    print("❌ 用户取消更新")
        
        await exchange.close()
        
    except Exception as e:
        print(f"❌ 分析失败: {str(e)}")
        sys.exit(1)


async def batch_analyze(args):
    """批量分析所有交易对"""
    try:
        # 使用默认配置
        config = TradingConfig()
        
        # 初始化交易所客户端
        if args.simulation:
            exchange = SimulationExchangeClient(config)
        else:
            exchange = ExchangeClient(config)
        
        await exchange.load_markets()
        
        # 初始化基准价格管理器
        manager = BasePriceManager()
        
        # 批量分析
        print("🔍 开始批量分析所有支持的交易对...")
        batch_result = await manager.batch_analyze_all_symbols(exchange)
        
        # 显示总结
        summary = batch_result.get("summary", {})
        print(f"\n📊 批量分析总结:")
        print(f"总计交易对: {summary.get('total_symbols', 0)}")
        print(f"需要设置: {summary.get('needs_setup', 0)}")
        print(f"可直接使用: {summary.get('ready_to_use', 0)}")
        print(f"需要审核: {summary.get('needs_review', 0)}")
        print(f"分析错误: {summary.get('errors', 0)}")
        
        # 显示详细结果
        if args.verbose:
            details = batch_result.get("details", {})
            for symbol, result in details.items():
                print(f"\n{'-' * 20} {symbol} {'-' * 20}")
                manager.print_analysis_report(result)
        
        await exchange.close()
        
    except Exception as e:
        print(f"❌ 批量分析失败: {str(e)}")
        sys.exit(1)


async def list_symbols(args):
    """列出所有支持的交易对"""
    try:
        symbols = get_available_symbols()
        print("📋 支持的交易对:")
        for i, symbol in enumerate(symbols, 1):
            print(f"  {i}. {symbol}")
        
        print(f"\n总计: {len(symbols)} 个交易对")
        
        # 显示配置状态
        if args.detailed:
            print("\n📊 配置状态:")
            manager = BasePriceManager()
            for symbol in symbols:
                config_info = manager._get_symbol_config_info(symbol)
                status = "✅ 已配置" if not config_info.get("needs_setup", True) else "❌ 需要设置"
                base_price = config_info.get("current_base_price", 0)
                if base_price > 0:
                    print(f"  {symbol}: {status} (基准价: {base_price:.4f})")
                else:
                    print(f"  {symbol}: {status}")
        
    except Exception as e:
        print(f"❌ 列出交易对失败: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        description="基准价格管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 分析BNB/USDT的基准价格
  python tools/base_price_cli.py analyze --symbol BNB/USDT
  
  # 分析并自动更新基准价格
  python tools/base_price_cli.py analyze --symbol BNB/USDT --update
  
  # 批量分析所有交易对
  python tools/base_price_cli.py batch
  
  # 列出所有支持的交易对
  python tools/base_price_cli.py list
        """
    )
    
    # 全局参数
    parser.add_argument('--simulation', action='store_true', 
                       help='使用模拟模式 (不需要API密钥)')
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # analyze命令
    analyze_parser = subparsers.add_parser('analyze', help='分析指定交易对的基准价格')
    analyze_parser.add_argument('--symbol', required=True, 
                               help='交易对符号 (例如: BNB/USDT)')
    analyze_parser.add_argument('--update', action='store_true',
                               help='如果分析结果合理，自动更新基准价格')
    
    # batch命令
    batch_parser = subparsers.add_parser('batch', help='批量分析所有交易对')
    batch_parser.add_argument('--verbose', '-v', action='store_true',
                             help='显示详细分析结果')
    
    # list命令
    list_parser = subparsers.add_parser('list', help='列出所有支持的交易对')
    list_parser.add_argument('--detailed', '-d', action='store_true',
                            help='显示详细配置状态')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 运行相应命令
    if args.command == 'analyze':
        asyncio.run(analyze_symbol(args))
    elif args.command == 'batch':
        asyncio.run(batch_analyze(args))
    elif args.command == 'list':
        asyncio.run(list_symbols(args))


if __name__ == '__main__':
    main() 