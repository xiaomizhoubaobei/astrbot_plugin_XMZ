import os
import json
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("borrow_manager", "YourName", "借钱记账插件（带利息计算）", "1.0.0", "https://github.com/yourrepo")
class BorrowManager(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 获取当前文件的上级目录，然后在其下创建一个 plugins_data 文件夹
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        self.data_dir = os.path.join(parent_dir, "plugins_data", "borrow_manager")
        os.makedirs(self.data_dir, exist_ok=True)
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

    # 其他方法保持不变