from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import os
import json

@register("palace_diplomacy", "祁筱欣", "宫群建交管理插件", "1.0.0")
class PalaceDiplomacyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.diplomatic_relations = {}  # {group_id: {(palace1_name, palace2_name): relation_dict}}
        self.data_file = os.path.join(os.path.dirname(__file__), "palace_relations.json")
        self.group_list = []  # 所有群列表
        self.current_group_id = None  # 当前操作群id

    async def initialize(self):
        """初始化宫群外交关系数据"""
        # 加载外交关系数据
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 读取为 group_id -> {(palace1_name, palace2_name): relation_dict}
                    self.diplomatic_relations = {}
                    self.group_list = list(data.keys())
                    for group_id, group_data in data.items():
                        self.diplomatic_relations[group_id] = {}
                        for item in group_data:
                            key = (item["palace1_name"], item["palace2_name"])
                            self.diplomatic_relations[group_id][key] = item
                logger.info("外交关系数据已加载")
            except Exception as e:
                logger.error(f"外交关系数据加载失败: {e}")
        else:
            logger.info("未找到外交关系数据文件，初始化为空")
        logger.info("宫群建交管理插件已加载")
        if self.group_list:
            self.current_group_id = self.group_list[0]

    @filter.command("add_relation")
    async def add_relation(self, event: AstrMessageEvent):
        """添加宫群外交关系，支持建交书截图（图片消息）"""
        group_id = getattr(event, "group_id", "")
        if not group_id:
            yield event.plain_result("本插件仅支持群聊使用，私聊不可用。")
            return
        if group_id not in self.diplomatic_relations:
            self.diplomatic_relations[group_id] = {}
        args = event.message_str.split()
        if len(args) < 4:
            yield event.plain_result("用法: /add_relation [群名称] [群号] [对方建交官] [我方建交官] [建交书截图(可选)]")
            return
        palace1_name, palace1_id, diplomat2, diplomat1 = args[0], args[1], args[2], args[3]
        screenshot = None
        if hasattr(event, "message") and hasattr(event.message, "elements"):
            for elem in event.message.elements:
                if getattr(elem, "type", None) == "image":
                    screenshot = getattr(elem, "file_id", None) or getattr(elem, "url", None)
                    break
        if not screenshot and len(args) > 4:
            screenshot = args[4]
        key = (palace1_name, palace1_id)
        relation = {
            "palace1_name": palace1_name,
            "palace2_name": palace1_id,
            "diplomat2": diplomat2,
            "diplomat1": diplomat1,
            "screenshot": screenshot
        }
        self.diplomatic_relations[group_id][key] = relation
        await self.save_relations()
        msg = f"已建立外交关系: {palace1_name}({palace1_id}) ↔ {diplomat2}（对方建交官）/{diplomat1}（我方建交官）"
        if screenshot:
            if screenshot.startswith("http") or screenshot.startswith("file"):
                msg += f"\n建交书截图: {screenshot}"
            else:
                msg += f"\n建交书截图: [图片] {screenshot}"
        yield event.plain_result(msg)

    @filter.command("list_relations")
    async def list_relations(self, event: AstrMessageEvent):
        """列出所有建交国名称及序号，支持分页，每页10条，可通过参数指定页码"""
        group_id = getattr(event, "group_id", "")
        if not group_id:
            yield event.plain_result("本插件仅支持群聊使用，私聊不可用。")
            return
        group_relations = self.diplomatic_relations.get(group_id, {})
        if not group_relations:
            yield event.plain_result("当前没有外交关系")
            return
        relations_list = list(group_relations.values())
        if not relations_list:
            yield event.plain_result("当前没有外交关系")
            return
        args = event.message_str.strip().split()
        page = 1
        if args and args[0].isdigit():
            page = int(args[0])
        page_size = 10
        total = len(relations_list)
        total_pages = (total + page_size - 1) // page_size
        if page < 1 or page > total_pages:
            yield event.plain_result(f"页码超出范围，当前共 {total_pages} 页")
            return
        start = (page - 1) * page_size
        end = start + page_size
        msg_lines = [f"当前建交国列表（第{page}/{total_pages}页，总数{total}）:"]
        for idx, v in enumerate(relations_list[start:end], start=start):
            msg_lines.append(f"{idx+1}. {v['palace1_name']}({v['palace2_name']})")
        msg_lines.append(f"\n可通过 /relation_detail [序号|建交国名称] 查询详细信息\n用法: /list_relations [页码]，每页10条")
        yield event.plain_result("\n".join(msg_lines))

    @filter.command("relation_detail")
    async def relation_detail(self, event: AstrMessageEvent):
        """根据序号或建交国名称查询详细建交信息，支持图片展示"""
        group_id = getattr(event, "group_id", "")
        if not group_id:
            yield event.plain_result("本插件仅支持群聊使用，私聊不可用。")
            return
        group_relations = self.diplomatic_relations.get(group_id, {})
        arg = event.message_str.strip()
        if not arg:
            yield event.plain_result("用法: /relation_detail [序号|建交国名称]")
            return
        relations_list = list(group_relations.values())
        detail = None
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(relations_list):
                detail = relations_list[idx]
        else:
            for v in relations_list:
                if v['palace1_name'] == arg:
                    detail = v
                    break
        if not detail:
            yield event.plain_result("未找到对应的建交国信息")
            return
        info = [
            f"- 建交国名称: {detail['palace1_name']}",
            f"- 群号: {detail['palace2_name']}",
            f"- 对方建交官: {detail['diplomat2']}",
            f"- 我方建交官: {detail['diplomat1']}"
        ]
        if detail.get('screenshot'):
            screenshot = detail['screenshot']
            if screenshot.startswith("http") or screenshot.startswith("file"):
                info.append(f"- 建交书截图: {screenshot}")
            else:
                info.append(f"- 建交书截图: [图片] {screenshot}")
        yield event.plain_result("\n".join(info))

    @filter.command("qun")
    async def qun_command(self, event: AstrMessageEvent):
        """群管理命令: qun list/序号/群名/群号，支持分页，每页10条，可通过参数指定页码"""
        args = event.message_str.strip().split()
        if not args or args[0] == "list":
            # 展示所有群列表，分页
            self.group_list = list(self.diplomatic_relations.keys())
            if not self.group_list:
                yield event.plain_result("暂无群数据")
                return
            page = 1
            if len(args) > 1 and args[1].isdigit():
                page = int(args[1])
            page_size = 10
            total = len(self.group_list)
            total_pages = (total + page_size - 1) // page_size
            if page < 1 or page > total_pages:
                yield event.plain_result(f"页码超出范围，当前共 {total_pages} 页")
                return
            start = (page - 1) * page_size
            end = start + page_size
            msg_lines = [f"群列表（第{page}/{total_pages}页，总数{total}）:"]
            for idx, gid in enumerate(self.group_list[start:end], start=start):
                msg_lines.append(f"{idx+1}. 群号: {gid}")
            msg_lines.append("\n可用 qun [序号|群号] 切换当前操作群\n用法: qun list [页码]，每页10条")
            yield event.plain_result("\n".join(msg_lines))
            return
        # 切换当前群
        target = args[0]
        self.group_list = list(self.diplomatic_relations.keys())
        if not self.group_list:
            yield event.plain_result("暂无群数据")
            return
        gid = None
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(self.group_list):
                gid = self.group_list[idx]
        else:
            for g in self.group_list:
                if g == target:
                    gid = g
                    break
        if not gid:
            yield event.plain_result("未找到对应群号")
            return
        self.current_group_id = gid
        yield event.plain_result(f"已切换到群 {gid}，可用 list 查询建交信息")

    @filter.command("list")
    async def list_command(self, event: AstrMessageEvent):
        """在当前群下列出建交国，或查详细建交信息，支持分页，每页10条，可通过参数指定页码"""
        if not self.current_group_id:
            yield event.plain_result("请先用 qun 命令选择群")
            return
        args = event.message_str.strip().split()
        group_relations = self.diplomatic_relations.get(self.current_group_id, {})
        relations_list = list(group_relations.values())
        if not args or not args[0] or args[0].isdigit():
            # 仅列出建交国，支持分页
            page = 1
            if args and args[0].isdigit():
                page = int(args[0])
            page_size = 10
            total = len(relations_list)
            total_pages = (total + page_size - 1) // page_size
            if total == 0:
                yield event.plain_result("当前没有外交关系")
                return
            if page < 1 or page > total_pages:
                yield event.plain_result(f"页码超出范围，当前共 {total_pages} 页")
                return
            start = (page - 1) * page_size
            end = start + page_size
            msg_lines = [f"群 {self.current_group_id} 建交国列表（第{page}/{total_pages}页，总数{total}）:"]
            for idx, v in enumerate(relations_list[start:end], start=start):
                msg_lines.append(f"{idx+1}. {v['palace1_name']}({v['palace2_name']})")
            msg_lines.append("\n可用 list [序号|群号] 查询详细建交信息\n用法: list [页码]，每页10条")
            yield event.plain_result("\n".join(msg_lines))
            return
        # 查询详细建交信息
        arg = args[0]
        detail = None
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(relations_list):
                detail = relations_list[idx]
        else:
            for v in relations_list:
                if v['palace2_name'] == arg:
                    detail = v
                    break
        if not detail:
            yield event.plain_result("未找到对应建交信息")
            return
        info = [
            f"- 建交国名称: {detail['palace1_name']}",
            f"- 群号: {detail['palace2_name']}",
            f"- 对方建交官: {detail['diplomat2']}",
            f"- 我方建交官: {detail['diplomat1']}"
        ]
        if detail.get('screenshot'):
            screenshot = detail['screenshot']
            if screenshot.startswith("http") or screenshot.startswith("file"):
                info.append(f"- 建交书截图: {screenshot}")
            else:
                info.append(f"- 建交书截图: [图片] {screenshot}")
        yield event.plain_result("\n".join(info))

    @filter.command("edit_relation")
    async def edit_relation(self, event: AstrMessageEvent):
        """根据序号或名称修改建交关系，参数顺序: [序号|建交国名称] [群名称] [群号] [对方建交官] [我方建交官] [建交书截图(可选)]"""
        group_id = getattr(event, "group_id", "")
        if not group_id:
            yield event.plain_result("本插件仅支持群聊使用，私聊不可用。")
            return
        group_relations = self.diplomatic_relations.get(group_id, {})
        args = event.message_str.strip().split()
        if len(args) < 5:
            yield event.plain_result("用法: /edit_relation [序号|建交国名称] [群名称] [群号] [对方建交官] [我方建交官] [建交书截图(可选)]")
            return
        target = args[0]
        relations_list = list(group_relations.values())
        detail = None
        key = None
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(relations_list):
                detail = relations_list[idx]
        else:
            for v in relations_list:
                if v['palace1_name'] == target:
                    detail = v
                    break
        if not detail:
            yield event.plain_result("未找到对应的建交国信息")
            return
        # 找到原key
        for k, v in group_relations.items():
            if v is detail:
                key = k
                break
        if not key:
            yield event.plain_result("数据异常，无法定位建交关系")
            return
        palace1_name, palace1_id, diplomat2, diplomat1 = args[1], args[2], args[3], args[4]
        screenshot = None
        if hasattr(event, "message") and hasattr(event.message, "elements"):
            for elem in event.message.elements:
                if getattr(elem, "type", None) == "image":
                    screenshot = getattr(elem, "file_id", None) or getattr(elem, "url", None)
                    break
        if not screenshot and len(args) > 5:
            screenshot = args[5]
        new_key = (palace1_name, palace1_id)
        relation = {
            "palace1_name": palace1_name,
            "palace2_name": palace1_id,
            "diplomat2": diplomat2,
            "diplomat1": diplomat1,
            "screenshot": screenshot
        }
        # 删除旧key，插入新key
        del self.diplomatic_relations[group_id][key]
        self.diplomatic_relations[group_id][new_key] = relation
        await self.save_relations()
        msg = f"已修改外交关系: {palace1_name}({palace1_id}) ↔ {diplomat2}（对方建交官）/{diplomat1}（我方建交官）"
        if screenshot:
            if screenshot.startswith("http") or screenshot.startswith("file"):
                msg += f"\n建交书截图: {screenshot}"
            else:
                msg += f"\n建交书截图: [图片] {screenshot}"
        yield event.plain_result(msg)

    @filter.command("delete_relation")
    async def delete_relation(self, event: AstrMessageEvent):
        """根据序号或名称删除建交关系"""
        group_id = getattr(event, "group_id", "")
        if not group_id:
            yield event.plain_result("本插件仅支持群聊使用，私聊不可用。")
            return
        group_relations = self.diplomatic_relations.get(group_id, {})
        arg = event.message_str.strip()
        if not arg:
            yield event.plain_result("用法: /delete_relation [序号|建交国名称]")
            return
        relations_list = list(group_relations.values())
        detail = None
        key = None
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(relations_list):
                detail = relations_list[idx]
        else:
            for v in relations_list:
                if v['palace1_name'] == arg:
                    detail = v
                    break
        if not detail:
            yield event.plain_result("未找到对应的建交国信息")
            return
        for k, v in group_relations.items():
            if v is detail:
                key = k
                break
        if not key:
            yield event.plain_result("数据异常，无法定位建交关系")
            return
        del self.diplomatic_relations[group_id][key]
        await self.save_relations()
        # 删除后刷新 relations_list，确保序号连续
        group_relations = self.diplomatic_relations.get(group_id, {})
        relations_list = list(group_relations.values())
        yield event.plain_result("已删除建交关系\n当前建交国数量: {}".format(len(relations_list)))

    async def terminate(self):
        """保存宫群外交关系数据"""
        await self.save_relations()
        logger.info("宫群建交管理插件已卸载")

    async def save_relations(self):
        """保存外交关系到文件"""
        try:
            # 保存为 group_id -> [relation_dict, ...]
            data = {gid: list(relations.values()) for gid, relations in self.diplomatic_relations.items()}
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("外交关系数据已保存")
        except Exception as e:
            logger.error(f"外交关系数据保存失败: {e}")