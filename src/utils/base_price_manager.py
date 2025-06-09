"""
基准价格管理工具

提供基准价格的查看、设置和分析功能
"""

import asyncio
import logging
from typing import Dict, Any
from src.utils.price_calculator import PriceCalculator
from src.config.symbols import get_available_symbols, is_symbol_supported


class BasePriceManager:
    """基准价格管理器"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.price_calculator = PriceCalculator()

    async def analyze_symbol_price(self, exchange, symbol: str) -> Dict[str, Any]:
        """分析指定交易对的价格信息"""
        try:
            self.logger.info(f"开始分析 {symbol} 的价格信息...")
            
            # 获取价格分析
            analysis = await self.price_calculator.get_price_analysis(exchange, symbol)
            
            # 获取币种配置信息
            config_info = self._get_symbol_config_info(symbol)
            
            # 组合结果
            result = {
                "symbol": symbol,
                "is_supported": is_symbol_supported(symbol),
                "config_info": config_info,
                "price_analysis": analysis,
                "recommendations": self._generate_recommendations(analysis, config_info)
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"分析 {symbol} 价格信息失败: {str(e)}")
            return {"error": str(e)}

    def _get_symbol_config_info(self, symbol: str) -> Dict[str, Any]:
        """获取币种配置信息"""
        try:
            if not is_symbol_supported(symbol):
                return {
                    "has_config": False,
                    "current_base_price": 0.0,
                    "needs_setup": True
                }
            
            # 尝试加载币种配置
            symbol_key = symbol.replace("/", "_").lower()
            try:
                import importlib
                config_module = importlib.import_module(f"src.config.symbols.{symbol_key}")
                symbol_config = config_module.SYMBOL_CONFIG
                
                return {
                    "has_config": True,
                    "current_base_price": symbol_config.get("initial_base_price", 0.0),
                    "description": symbol_config.get("description", ""),
                    "recommended_capital": symbol_config.get("recommended_capital", 1000.0),
                    "needs_setup": symbol_config.get("initial_base_price", 0.0) <= 0
                }
            except ImportError:
                return {
                    "has_config": False,
                    "current_base_price": 0.0,
                    "needs_setup": True
                }
                
        except Exception as e:
            self.logger.error(f"获取 {symbol} 配置信息失败: {str(e)}")
            return {"error": str(e)}

    def _generate_recommendations(self, price_analysis: Dict, config_info: Dict) -> Dict[str, Any]:
        """生成推荐建议"""
        recommendations = {
            "action": "unknown",
            "suggested_base_price": None,
            "reasoning": "",
            "risk_level": "medium"
        }
        
        try:
            if not price_analysis or "recommended_base_price" not in price_analysis:
                recommendations.update({
                    "action": "manual_setup",
                    "reasoning": "无法获取历史价格数据，建议手动设置基准价格"
                })
                return recommendations
            
            recommended_price = price_analysis["recommended_base_price"]
            current_price = price_analysis.get("current_price")
            
            if not recommended_price or not current_price:
                recommendations.update({
                    "action": "manual_setup",
                    "reasoning": "价格数据不完整，建议手动设置基准价格"
                })
                return recommendations
            
            # 计算价格偏离
            deviation = abs(recommended_price - current_price) / current_price
            
            recommendations["suggested_base_price"] = recommended_price
            
            if deviation < 0.05:  # 5%以内
                recommendations.update({
                    "action": "use_calculated",
                    "reasoning": f"计算价格与市场价格接近(偏离{deviation:.1%})，可直接使用",
                    "risk_level": "low"
                })
            elif deviation < 0.15:  # 15%以内
                recommendations.update({
                    "action": "use_calculated_with_caution",
                    "reasoning": f"计算价格偏离市场价格{deviation:.1%}，建议谨慎使用",
                    "risk_level": "medium"
                })
            else:  # 超过15%
                recommendations.update({
                    "action": "manual_review",
                    "reasoning": f"计算价格偏离市场价格{deviation:.1%}，建议手动审核",
                    "risk_level": "high"
                })
                
        except Exception as e:
            recommendations.update({
                "action": "error",
                "reasoning": f"分析过程出错: {str(e)}"
            })
        
        return recommendations

    async def update_symbol_base_price(self, symbol: str, base_price: float) -> bool:
        """更新币种配置文件中的基准价格"""
        try:
            if not is_symbol_supported(symbol):
                self.logger.error(f"不支持的交易对: {symbol}")
                return False
            
            symbol_key = symbol.replace("/", "_").lower()
            config_file_path = f"src/config/symbols/{symbol_key}.py"
            
            # 读取当前配置文件
            try:
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 更新基准价格
                import re
                pattern = r"'initial_base_price':\s*[\d.]+,?"
                new_line = f"'initial_base_price': {base_price},"
                
                if re.search(pattern, content):
                    # 如果存在，替换
                    new_content = re.sub(pattern, new_line, content)
                else:
                    # 如果不存在，在合适位置添加
                    # 在交易参数部分添加
                    pattern = r"(\s+# 交易参数\s*\n)"
                    replacement = f"\\1    'initial_base_price': {base_price},\n    \n"
                    new_content = re.sub(pattern, replacement, content)
                
                # 写回文件
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                self.logger.info(f"已更新 {symbol} 的基准价格为: {base_price}")
                return True
                
            except FileNotFoundError:
                self.logger.error(f"配置文件不存在: {config_file_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新 {symbol} 基准价格失败: {str(e)}")
            return False

    async def batch_analyze_all_symbols(self, exchange) -> Dict[str, Any]:
        """批量分析所有支持的交易对"""
        results = {}
        supported_symbols = get_available_symbols()
        
        self.logger.info(f"开始批量分析 {len(supported_symbols)} 个交易对...")
        
        for symbol in supported_symbols:
            try:
                self.logger.info(f"分析 {symbol}...")
                results[symbol] = await self.analyze_symbol_price(exchange, symbol)
                # 添加延迟避免API限流
                await asyncio.sleep(0.5)
            except Exception as e:
                self.logger.error(f"分析 {symbol} 失败: {str(e)}")
                results[symbol] = {"error": str(e)}
        
        # 生成总结报告
        summary = self._generate_batch_summary(results)
        
        return {
            "summary": summary,
            "details": results,
            "timestamp": asyncio.get_event_loop().time()
        }

    def _generate_batch_summary(self, results: Dict) -> Dict[str, Any]:
        """生成批量分析总结"""
        summary = {
            "total_symbols": len(results),
            "needs_setup": 0,
            "ready_to_use": 0,
            "needs_review": 0,
            "errors": 0
        }
        
        for symbol, result in results.items():
            if "error" in result:
                summary["errors"] += 1
            elif "recommendations" in result:
                action = result["recommendations"].get("action", "unknown")
                if action in ["manual_setup", "manual_review"]:
                    summary["needs_setup"] += 1
                elif action == "use_calculated":
                    summary["ready_to_use"] += 1
                else:
                    summary["needs_review"] += 1
        
        return summary

    def print_analysis_report(self, analysis_result: Dict[str, Any]):
        """打印分析报告"""
        if "error" in analysis_result:
            print(f"❌ 分析失败: {analysis_result['error']}")
            return
        
        symbol = analysis_result.get("symbol", "未知")
        print(f"\n📊 {symbol} 价格分析报告")
        print("=" * 50)
        
        # 基本信息
        config_info = analysis_result.get("config_info", {})
        print(f"🔧 配置状态: {'✅ 已配置' if config_info.get('has_config') else '❌ 未配置'}")
        
        current_base = config_info.get("current_base_price", 0)
        if current_base > 0:
            print(f"📌 当前基准价格: {current_base:.4f}")
        else:
            print("📌 当前基准价格: 未设置")
        
        # 价格分析
        price_analysis = analysis_result.get("price_analysis", {})
        if price_analysis:
            current_price = price_analysis.get("current_price")
            if current_price:
                print(f"💰 当前市场价格: {current_price:.4f}")
            
            calculated_prices = price_analysis.get("calculated_prices", {})
            if calculated_prices:
                print("\n📈 计算价格:")
                for method, price in calculated_prices.items():
                    print(f"  {method}: {price:.4f}")
            
            recommended = price_analysis.get("recommended_base_price")
            if recommended:
                print(f"\n🎯 推荐基准价格: {recommended:.4f}")
        
        # 建议
        recommendations = analysis_result.get("recommendations", {})
        if recommendations:
            action = recommendations.get("action", "unknown")
            reasoning = recommendations.get("reasoning", "")
            risk_level = recommendations.get("risk_level", "medium")
            
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk_level, "⚪")
            
            print(f"\n💡 建议操作: {action}")
            print(f"📝 建议理由: {reasoning}")
            print(f"{risk_emoji} 风险等级: {risk_level}")
        
        print("=" * 50) 