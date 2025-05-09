import os
import json
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Star, register
from astrbot.api import logger

@register("borrow_manager", "YourName", "借钱记账插件（带利息计算）", "1.0.0", "https://github.com/yourrepo")
class BorrowManager(Star):
    def __init__(self, context):
        super().__init__(context)
        # 获取当前文件所在的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建 data 文件夹的路径
        self.data_dir = os.path.join(current_dir, "data")
        # 确保 data 文件夹存在
        os.makedirs(self.data_dir, exist_ok=True)
        # 构建数据文件的路径
        self.data_file = os.path.join(self.data_dir, "borrow_records.json")
        self.borrow_records = self._load_records()

    def _load_records(self):
        """加载借款记录"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading borrow records: {e}")
                return {"borrowers": {}, "transactions": []}
        return {"borrowers": {}, "transactions": []}

    def _save_records(self):
        """保存借款记录"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.borrow_records, f, ensure_ascii=False, indent=4, default=str)
        except Exception as e:
            logger.error(f"Error saving borrow records: {e}")

    @filter.command("add_borrow")
    async def add_borrow(self, event: AstrMessageEvent, amount: float, person: str, daily_rate: float = 0.0):
        """
        添加借款记录，格式：/add_borrow 金额 借款人 [日利率]
        日利率可选，默认为0（无息）
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if person not in self.borrow_records["borrowers"]:
            self.borrow_records["borrowers"][person] = {
                "amount": amount,
                "daily_rate": daily_rate,
                "time": timestamp
            }
        else:
            # 如果借款人已存在，只更新金额和时间，保留原有日利率
            self.borrow_records["borrowers"][person]["amount"] += amount
            self.borrow_records["borrowers"][person]["time"] = timestamp

        # 添加交易记录
        self.borrow_records["transactions"].append({
            "person": person,
            "amount": amount,
            "type": "borrow",
            "daily_rate": daily_rate,
            "time": timestamp
        })

        self._save_records()
        yield event.plain_result(f"已添加借款记录：{person} 借了 {amount} 元，日利率 {daily_rate * 100}%")

    @filter.command("query_borrow")
    async def query_borrow(self, event: AstrMessageEvent, person: str = None):
        """查询借款记录，格式：/query_borrow 或 /query_borrow 借款人"""
        current_time = datetime.now()
        if person:
            if person in self.borrow_records["borrowers"]:
                record = self.borrow_records["borrowers"][person]
                borrow_time = datetime.strptime(record["time"], "%Y-%m-%d %H:%M:%S")
                days_passed = (current_time - borrow_time).days
                interest = record["amount"] * record["daily_rate"] * days_passed
                total_owed = record["amount"] + interest
                result = (
                    f"{person} 目前共借了 {record['amount']} 元，"
                    f"日利率 {record['daily_rate'] * 100}%，"
                    f"借款天数 {days_passed} 天，"
                    f"利息 {interest:.2f} 元，"
                    f"总计欠款 {total_owed:.2f} 元"
                )
                yield event.plain_result(result)
            else:
                yield event.plain_result(f"没有找到 {person} 的借款记录")
        else:
            if not self.borrow_records["borrowers"]:
                yield event.plain_result("目前没有借款记录")
            else:
                result = "借款记录：\n"
                for person, record in self.borrow_records["borrowers"].items():
                    borrow_time = datetime.strptime(record["time"], "%Y-%m-%d %H:%M:%S")
                    days_passed = (current_time - borrow_time).days
                    interest = record["amount"] * record["daily_rate"] * days_passed
                    total_owed = record["amount"] + interest
                    result += (
                        f"{person}: 借款 {record['amount']} 元，"
                        f"日利率 {record['daily_rate'] * 100}%，"
                        f"借款天数 {days_passed} 天，"
                        f"利息 {interest:.2f} 元，"
                        f"总计欠款 {total_owed:.2f} 元\n"
                    )
                yield event.plain_result(result.strip())

    @filter.command("repay")
    async def repay(self, event: AstrMessageEvent, amount: float, person: str):
        """记录还款操作，格式：/repay 金额 借款人"""
        if person in self.borrow_records["borrowers"]:
            record = self.borrow_records["borrowers"][person]
            borrow_time = datetime.strptime(record["time"], "%Y-%m-%d %H:%M:%S")
            days_passed = (datetime.now() - borrow_time).days
            interest = record["amount"] * record["daily_rate"] * days_passed
            total_owed = record["amount"] + interest

            if amount >= total_owed:
                remaining = amount - total_owed
                del self.borrow_records["borrowers"][person]

                # 添加交易记录
                self.borrow_records["transactions"].append({
                    "person": person,
                    "amount": amount,
                    "type": "repay",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                if remaining > 0:
                    yield event.plain_result(
                        f"{person} 还款 {amount} 元，已还清所有借款，多还了 {remaining:.2f} 元"
                    )
                else:
                    yield event.plain_result(f"{person} 还款 {amount} 元，已还清所有借款")
            else:
                # 只减少本金部分，利息需要重新计算
                record["amount"] -= amount

                # 添加交易记录
                self.borrow_records["transactions"].append({
                    "person": person,
                    "amount": amount,
                    "type": "repay",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                self._save_records()
                yield event.plain_result(f"{person} 还款 {amount} 元，剩余本金 {record['amount']:.2f} 元")
        else:
            yield event.plain_result(f"没有找到 {person} 的借款记录，无法还款")

    @filter.command("query_detail")
    async def query_detail(self, event: AstrMessageEvent):
        """查询所有交易详细记录，格式：/query_detail"""
        if not self.borrow_records["transactions"]:
            yield event.plain_result("目前没有交易记录")
        else:
            result = "交易详细记录：\n"
            for transaction in self.borrow_records["transactions"]:
                if transaction["type"] == "borrow":
                    result += (
                        f"时间: {transaction['time']}, "
                        f"借款人: {transaction['person']}, "
                        f"借款金额: {transaction['amount']:.2f} 元, "
                        f"日利率: {transaction['daily_rate'] * 100}%, "
                        f"类型: 借款\n"
                    )
                else:
                    result += (
                        f"时间: {transaction['time']}, "
                        f"借款人: {transaction['person']}, "
                        f"还款金额: {transaction['amount']:.2f} 元, "
                        f"类型: 还款\n"
                    )
            yield event.plain_result(result.strip())