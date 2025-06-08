"""
订单跟踪器

重构后的订单跟踪和交易历史管理模块
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.utils.logger import TradingLogger


class OrderThrottler:
    """订单限频器"""

    def __init__(self, limit: int = 10, interval: int = 60):
        self.order_timestamps = []
        self.limit = limit
        self.interval = interval

    def check_rate(self) -> bool:
        """检查订单频率是否超限"""
        current_time = time.time()
        self.order_timestamps = [
            t for t in self.order_timestamps if current_time - t < self.interval
        ]

        if len(self.order_timestamps) >= self.limit:
            return False

        self.order_timestamps.append(current_time)
        return True


class OrderTracker:
    """订单跟踪器"""

    def __init__(self, data_dir: str = "data"):
        self.logger = TradingLogger(self.__class__.__name__)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 文件路径
        self.history_file = self.data_dir / "trade_history.json"
        self.backup_file = self.data_dir / "trade_history.backup.json"
        self.archive_dir = self.data_dir / "archives"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        # 状态变量
        self.order_states = {}
        self.trade_count = 0
        self.orders = {}
        self.trade_history = []
        self.max_archive_months = 12

        # 加载历史数据
        self.load_trade_history()
        self.clean_old_archives()

    def log_order(self, order: Dict[str, Any]):
        """记录订单状态"""
        self.order_states[order["id"]] = {"created": datetime.now(), "status": "open"}

    def add_order(self, order: Dict[str, Any]):
        """添加新订单到跟踪器"""
        try:
            order_id = order["id"]
            self.orders[order_id] = {
                "order": order,
                "created_at": datetime.now(),
                "status": order["status"],
                "profit": 0,
            }
            self.trade_count += 1
            self.logger.logger.info(
                f"订单已添加到跟踪器 | ID: {order_id} | 状态: {order['status']}"
            )
        except Exception as e:
            self.logger.logger.error(f"添加订单失败: {str(e)}")
            raise

    def reset(self):
        """重置跟踪器"""
        self.trade_count = 0
        self.orders.clear()
        self.logger.logger.info("订单跟踪器已重置")

    def get_trade_history(self) -> List[Dict[str, Any]]:
        """获取交易历史"""
        return self.trade_history

    def load_trade_history(self):
        """从文件加载历史交易记录"""
        try:
            if self.history_file.exists():
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.trade_history = json.load(f)
                self.logger.logger.info(
                    f"加载了 {len(self.trade_history)} 条历史交易记录"
                )
        except Exception as e:
            self.logger.logger.error(f"加载历史交易记录失败: {str(e)}")
            self.trade_history = []

    def save_trade_history(self):
        """将当前交易历史保存到文件"""
        try:
            # 先备份当前文件
            self.backup_history()

            # 保存当前记录
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.trade_history, f, ensure_ascii=False, indent=2)

            self.logger.logger.info(
                f"已将 {len(self.trade_history)} 条交易记录保存到 {self.history_file}"
            )
        except Exception as e:
            self.logger.logger.error(f"保存交易记录失败: {str(e)}")

    def backup_history(self):
        """备份交易历史"""
        try:
            if self.history_file.exists():
                import shutil

                shutil.copy2(self.history_file, self.backup_file)
                self.logger.logger.info("交易历史备份成功")
        except Exception as e:
            self.logger.logger.error(f"备份交易历史失败: {str(e)}")

    def add_trade(self, trade: Dict[str, Any]):
        """添加交易记录（自动去重）"""
        # 去重检查
        if any(t["order_id"] == trade.get("order_id") for t in self.trade_history):
            self.logger.logger.debug(f"重复 order_id {trade.get('order_id')} 已忽略")
            return

        # 验证必要字段
        required_fields = ["timestamp", "side", "price", "amount", "order_id"]
        for field in required_fields:
            if field not in trade:
                self.logger.logger.error(f"交易记录缺少必要字段: {field}")
                return

        # 验证数据类型
        try:
            trade["timestamp"] = float(trade["timestamp"])
            trade["price"] = float(trade["price"])
            trade["amount"] = float(trade["amount"])
        except (ValueError, TypeError) as e:
            self.logger.logger.error(f"交易记录数据类型错误: {str(e)}")
            return

        self.logger.logger.info(f"添加交易记录: {trade}")
        self.trade_history.append(trade)

        # 保持历史记录数量限制
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]

        # 保存到文件
        self.save_trade_history()

    def update_order(self, order_id: str, status: str, profit: float = 0):
        """更新订单状态"""
        if order_id in self.orders:
            self.orders[order_id]["status"] = status
            self.orders[order_id]["profit"] = profit
            if status == "closed":
                self.logger.logger.info(f"订单已关闭 | ID: {order_id} | 利润: {profit}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取交易统计信息"""
        try:
            if not self.trade_history:
                return {
                    "total_trades": 0,
                    "win_rate": 0,
                    "total_profit": 0,
                    "avg_profit": 0,
                    "max_profit": 0,
                    "max_loss": 0,
                    "profit_factor": 0,
                    "consecutive_wins": 0,
                    "consecutive_losses": 0,
                }

            total_trades = len(self.trade_history)
            winning_trades = len(
                [t for t in self.trade_history if t.get("profit", 0) > 0]
            )
            total_profit = sum(t.get("profit", 0) for t in self.trade_history)
            profits = [t.get("profit", 0) for t in self.trade_history]

            # 计算最大连续盈利和亏损
            current_streak = 1
            max_win_streak = 0
            max_loss_streak = 0

            for i in range(1, len(profits)):
                if (profits[i] > 0 and profits[i - 1] > 0) or (
                    profits[i] < 0 and profits[i - 1] < 0
                ):
                    current_streak += 1
                else:
                    if profits[i - 1] > 0:
                        max_win_streak = max(max_win_streak, current_streak)
                    else:
                        max_loss_streak = max(max_loss_streak, current_streak)
                    current_streak = 1

            return {
                "total_trades": total_trades,
                "win_rate": winning_trades / total_trades if total_trades > 0 else 0,
                "total_profit": total_profit,
                "avg_profit": total_profit / total_trades if total_trades > 0 else 0,
                "max_profit": max(profits) if profits else 0,
                "max_loss": min(profits) if profits else 0,
                "profit_factor": sum(p for p in profits if p > 0)
                / abs(sum(p for p in profits if p < 0))
                if sum(p for p in profits if p < 0) != 0
                else 0,
                "consecutive_wins": max_win_streak,
                "consecutive_losses": max_loss_streak,
            }
        except Exception as e:
            self.logger.logger.error(f"计算统计信息失败: {str(e)}")
            return {}

    def archive_old_trades(self):
        """归档旧的交易记录"""
        try:
            if len(self.trade_history) > 1000:
                # 归档前500条记录
                archive_trades = self.trade_history[:500]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_file = self.archive_dir / f"trades_archive_{timestamp}.json"

                with open(archive_file, "w", encoding="utf-8") as f:
                    json.dump(archive_trades, f, ensure_ascii=False, indent=2)

                # 保留最近500条记录
                self.trade_history = self.trade_history[500:]
                self.save_trade_history()

                self.logger.logger.info(
                    f"已归档 {len(archive_trades)} 条交易记录到 {archive_file}"
                )
        except Exception as e:
            self.logger.logger.error(f"归档交易记录失败: {str(e)}")

    def clean_old_archives(self):
        """清理旧的归档文件"""
        try:
            archive_files = list(self.archive_dir.glob("trades_archive_*.json"))
            if len(archive_files) > self.max_archive_months:
                # 按创建时间排序，删除最旧的文件
                archive_files.sort(key=lambda x: x.stat().st_ctime)
                files_to_delete = archive_files[: -self.max_archive_months]

                for file_path in files_to_delete:
                    file_path.unlink()
                    self.logger.logger.info(f"已删除旧归档文件: {file_path}")
        except Exception as e:
            self.logger.logger.error(f"清理旧归档文件失败: {str(e)}")

    def analyze_trades(self, days: int = 30) -> Dict[str, Any]:
        """分析指定天数内的交易表现"""
        try:
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            recent_trades = [
                t for t in self.trade_history if t["timestamp"] > cutoff_time
            ]

            if not recent_trades:
                return {"period_days": days, "trades": 0}

            total_profit = sum(t.get("profit", 0) for t in recent_trades)
            winning_trades = len([t for t in recent_trades if t.get("profit", 0) > 0])

            return {
                "period_days": days,
                "trades": len(recent_trades),
                "total_profit": total_profit,
                "win_rate": winning_trades / len(recent_trades),
                "avg_profit_per_trade": total_profit / len(recent_trades),
                "daily_avg_profit": total_profit / days,
            }
        except Exception as e:
            self.logger.logger.error(f"分析交易表现失败: {str(e)}")
            return {}

    def export_trades(self, format: str = "csv") -> str:
        """导出交易记录"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if format.lower() == "csv":
                import csv

                filename = f"trades_export_{timestamp}.csv"
                filepath = self.data_dir / filename

                with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                    if self.trade_history:
                        fieldnames = self.trade_history[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(self.trade_history)

                self.logger.logger.info(f"交易记录已导出到 {filepath}")
                return str(filepath)

            else:  # JSON格式
                filename = f"trades_export_{timestamp}.json"
                filepath = self.data_dir / filename

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(self.trade_history, f, ensure_ascii=False, indent=2)

                self.logger.logger.info(f"交易记录已导出到 {filepath}")
                return str(filepath)

        except Exception as e:
            self.logger.logger.error(f"导出交易记录失败: {str(e)}")
            return ""
