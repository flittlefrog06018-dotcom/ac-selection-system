"""
Daikin VRV Refrigerant Piping Engine (大金 VRV 冷媒管徑與分歧頭專屬計算引擎)
嚴格遵照《VRV冷媒管徑選用工具2026.5.xlsx》與大金隨身技師拓撲計算邏輯。
提供：
1. 室內/室外機能力指數精準推導
2. 主幹管、第一分歧頭選用
3. 級聯次幹管與次分歧頭拓撲推導 (N 台內機自動推導 N-1 個分歧頭)
4. BP 箱分組 (每 3 台 RA 自動一組)
5. CAD 風格系統示意架構圖繪製 (基於 Pillow 高解析圖檔產生)
"""

import io
import re
import math
import os
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

# ==============================================================================
# 0. 基礎資料結構與能力指數表
# ==============================================================================

SIDE_DISCHARGE_OUTDOOR_CAPACITY = {
    "RSUYQ112AVT": 100.0,
    "RSUYQ125AVT": 112.5,
    "RSUYQ140AVT": 125.0,
    "RSUYQ160AVT": 150.0,
    "RXYCQ4BVLT": 100.0,
    "RXYCQ5BVLT": 112.0,
    "RXYCQ6BVLT": 125.0,
    "RXYMQ8TTLT": 200.0,
    "RXYMQ10TTLT": 223.0,
    "RXYMQ10ARYLT": 250.0,
    "RXYMQ12ARYLT": 300.0,
    "RXYMQ8TYLT": 180.0,
    "RXYMQ10TYLT": 215.0,
}

class PipingNode:
    """
    冷媒管路拓撲節點
    """
    def __init__(self, node_type: str, name: str, capacity: float = 0.0, qty: int = 1, model: str = "", room_name: str = ""):
        self.node_type = node_type  # 'main', 'joint', 'subgroup', 'bp', 'vrv', 'ra', 'sa'
        self.name = name
        self.model = model or name
        self.room_name = room_name
        self.capacity = capacity
        self.qty = qty
        self.children: List['PipingNode'] = []
        self.pipe_liquid = ""
        self.pipe_gas = ""
        self.joint_model = ""
        self.joint_role = "" # '第一分歧頭', '次分歧頭'

    def add_child(self, child: 'PipingNode'):
        self.children.append(child)

    def calculate_totals(self) -> float:
        if self.node_type in ['vrv', 'ra', 'sa']:
            return self.capacity * self.qty
        total = sum(child.calculate_totals() for child in self.children)
        self.capacity = total
        return total


# ==============================================================================
# 1. 大金冷媒規格計算核心
# ==============================================================================

class DaikinVRVPipingEngine:
    """
    大金 VRV 冷媒管徑與分歧頭獨立計算引擎
    """
    @classmethod
    def extract_capacity_index(cls, model_str: str, default_kw: float = 0.0) -> float:
        """
        提取室內機能力指數 (例如 FXDQ20 -> 20, FXDQ32 -> 32, FTHF25 -> 25)
        """
        m = re.search(r'(\d+)', str(model_str))
        if m:
            val = float(m.group(1))
            if val in [20, 22, 25, 28, 30, 32, 36, 40, 41, 50, 60, 63, 71, 80, 90, 100, 112, 125, 140, 160, 200, 250, 300]:
                return val
            if val <= 60:
                return val * 25.0
            return val
        if default_kw > 0:
            return round(default_kw * 10.0, 1)
        return 28.0

    @classmethod
    def is_side_discharge(cls, outdoor_model: str) -> bool:
        """
        判定是否為側吹型 VRV-S / mini
        """
        out_upper = str(outdoor_model).strip().upper()
        return any(k in out_upper for k in ['RSUYQ', 'RXYCQ', 'RXYMQ', 'VRV-S', 'MINI'])

    @classmethod
    def get_outdoor_capacity_index(cls, outdoor_model: str) -> float:
        """
        提取側吹型能力指數 X (依據工作表 R22-R35)
        """
        out_upper = str(outdoor_model).strip().upper()
        for k, v in SIDE_DISCHARGE_OUTDOOR_CAPACITY.items():
            if k in out_upper:
                return v
        m = re.search(r'(\d+)', out_upper)
        if m:
            val = float(m.group(1))
            if val in [112, 125, 140, 160]:
                if val == 112: return 100.0
                if val == 125: return 112.5
                if val == 140: return 125.0
                if val == 160: return 150.0
            if val <= 60:
                return val * 25.0
            return val
        return 100.0

    @classmethod
    def get_outdoor_hp(cls, outdoor_model: str) -> float:
        """
        提取室外機馬力 HP (上吹型專用)
        """
        out_upper = str(outdoor_model).strip().upper()
        m = re.search(r'(?:RXYQ|RXQ|RSUYQ|REYQ|RWEYQ|RXYMQ|RXYCQ)(\d+)', out_upper)
        if m:
            val = float(m.group(1))
            if val in [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 40, 48, 54, 60]:
                return val
            if val == 112: return 4.0
            if val == 125: return 5.0
            if val == 140: return 6.0
            if val == 160: return 6.0
        m_any = re.search(r'(\d+)', out_upper)
        if m_any:
            v = float(m_any.group(1))
            return v if v <= 60 else round(v / 25.0, 1)
        return 8.0

    # ----------------------------------------------------
    # 表 1: 第一分歧頭選用表 (室外機)
    # ----------------------------------------------------
    @classmethod
    def get_first_joint(cls, outdoor_model: str) -> str:
        """
        嚴格依據《VRV冷媒管徑選用工具2026.5.xlsx》表 1 選用第一分歧頭
        側吹型：X < 200 -> KHRP26A22T, 200 <= X <= 250 -> KHRP26A33T, X = 300 -> KHRP26A72T
        上吹型：HP = 6 -> KHRP26A22T, 8 <= HP <= 10 -> KHRP26A33T, 12 <= HP <= 22 -> KHRP26A72T, HP >= 24 -> KHRP26A73T+KHRP26M73TP
        """
        is_side = cls.is_side_discharge(outdoor_model)
        if is_side:
            x_cap = cls.get_outdoor_capacity_index(outdoor_model)
            if x_cap < 200:
                return "KHRP26A22T"
            elif x_cap <= 250:
                return "KHRP26A33T"
            else:
                return "KHRP26A72T"
        else:
            hp = cls.get_outdoor_hp(outdoor_model)
            if hp <= 6:
                return "KHRP26A22T"
            elif hp <= 10:
                return "KHRP26A33T"
            elif hp <= 22:
                return "KHRP26A72T"
            else:
                return "KHRP26A73T+KHRP26M73TP"

    # ----------------------------------------------------
    # 表 2: 次分歧頭選用表 (室內機下游標稱能力總和 X)
    # ----------------------------------------------------
    @classmethod
    def get_secondary_joint(cls, x_capacity: float) -> str:
        """
        依據表 2 (室內機標稱能力總和 X) 選用次分歧頭
        X < 200 -> KHRP26A22T
        200 <= X < 290 -> KHRP26A33T
        290 <= X < 640 -> KHRP26A72T
        640 <= X -> KHRP26A73T+KHRP26M73TP
        """
        if x_capacity < 200:
            return "KHRP26A22T"
        elif x_capacity < 290:
            return "KHRP26A33T"
        elif x_capacity < 640:
            return "KHRP26A72T"
        else:
            return "KHRP26A73T+KHRP26M73TP"

    # ----------------------------------------------------
    # 表 3: 主幹管選用表 (室外機)
    # ----------------------------------------------------
    @classmethod
    def get_main_trunk_pipe(cls, outdoor_model: str) -> Dict[str, str]:
        """
        依室外機機型判定主幹管徑 (液管 / 氣管)
        """
        is_side = cls.is_side_discharge(outdoor_model)
        if is_side:
            x_cap = cls.get_outdoor_capacity_index(outdoor_model)
            # HP <= 125 -> Ø9.5 / Ø15.9
            # 150 <= HP <= 200 -> Ø9.5 / Ø19.1
            # 215 <= HP <= 250 -> Ø9.5 / Ø22.2
            # 300 = HP -> Ø12.7 / Ø25.4
            if x_cap <= 125:
                return {"l": "Ø9.5", "g": "Ø15.9", "code": "TR2"}
            elif x_cap <= 200:
                return {"l": "Ø9.5", "g": "Ø19.1", "code": "TR3"}
            elif x_cap <= 250:
                return {"l": "Ø9.5", "g": "Ø22.2", "code": "TR4"}
            else:
                return {"l": "Ø12.7", "g": "Ø25.4", "code": "TR5"}
        else:
            hp = cls.get_outdoor_hp(outdoor_model)
            if hp <= 8:
                return {"l": "Ø9.5", "g": "Ø19.1", "code": "TR3"}
            elif hp <= 10:
                return {"l": "Ø9.5", "g": "Ø22.2", "code": "TR4"}
            elif hp <= 16:
                return {"l": "Ø12.7", "g": "Ø28.6", "code": "TR5"}
            elif hp <= 22:
                return {"l": "Ø15.9", "g": "Ø28.6", "code": "TR6"}
            elif hp <= 24:
                return {"l": "Ø15.9", "g": "Ø34.9", "code": "TR7"}
            elif hp <= 34:
                return {"l": "Ø19.1", "g": "Ø34.9", "code": "TR8"}
            else:
                return {"l": "Ø19.1", "g": "Ø41.3", "code": "TR9"}

    # ----------------------------------------------------
    # 表 4: 次幹管選用表 (室內機下游標稱能力總和 X)
    # ----------------------------------------------------
    @classmethod
    def get_sub_trunk_pipe(cls, x_capacity: float) -> Dict[str, str]:
        """
        次幹管選用表 (表 4)
        """
        if x_capacity < 150:
            return {"l": "Ø9.5", "g": "Ø15.9", "code": "TR2"}
        elif x_capacity < 200:
            return {"l": "Ø9.5", "g": "Ø19.1", "code": "TR3"}
        elif x_capacity < 290:
            return {"l": "Ø9.5", "g": "Ø22.2", "code": "TR4"}
        elif x_capacity < 420:
            return {"l": "Ø12.7", "g": "Ø28.6", "code": "TR5"}
        elif x_capacity < 640:
            return {"l": "Ø15.9", "g": "Ø28.6", "code": "TR6"}
        elif x_capacity < 920:
            return {"l": "Ø19.1", "g": "Ø34.9", "code": "TR8"}
        else:
            return {"l": "Ø19.1", "g": "Ø41.3", "code": "TR9"}

    # ----------------------------------------------------
    # 表 5: 室內機分支管選用表 (末端配管)
    # ----------------------------------------------------
    @classmethod
    def get_indoor_branch_pipe(cls, node_type: str, capacity: float) -> Dict[str, str]:
        """
        室內機分支管選用表 (表 5)
        """
        if node_type == 'ra':
            if capacity <= 30:
                return {"l": "Ø6.4", "g": "Ø9.5", "code": "RA1"}
            elif capacity <= 60:
                return {"l": "Ø6.4", "g": "Ø12.7", "code": "RA2"}
            else:
                return {"l": "Ø6.4", "g": "Ø15.9", "code": "RA3"}
        else:
            if capacity <= 28:
                return {"l": "Ø6.4", "g": "Ø9.5", "code": "TR0"}
            elif capacity <= 50:
                return {"l": "Ø6.4", "g": "Ø12.7", "code": "TR1"}
            elif capacity <= 140:
                return {"l": "Ø9.5", "g": "Ø15.9", "code": "TR2"}
            elif capacity <= 200:
                return {"l": "Ø9.5", "g": "Ø19.1", "code": "TR3"}
            else:
                return {"l": "Ø9.5", "g": "Ø22.2", "code": "TR4"}

    @classmethod
    def get_bp_trunk_pipe(cls, capacity: float) -> Dict[str, str]:
        """
        BP 箱接入 VRV 系統之入口次幹管
        """
        if capacity <= 62:
            return {"l": "Ø6.4", "g": "Ø12.7", "code": "BP1"}
        elif capacity <= 149:
            return {"l": "Ø9.5", "g": "Ø15.9", "code": "BP2"}
        elif capacity <= 208:
            return {"l": "Ø9.5", "g": "Ø19.1", "code": "BP3"}
        else:
            return {"l": "Ø9.5", "g": "Ø22.2", "code": "BP4"}

    # ----------------------------------------------------
    # VRV 系統判斷輔助函式
    # ----------------------------------------------------
    @classmethod
    def check_is_vrv(cls, outdoor_model: str, indoor_items: List[Dict[str, Any]] = None) -> bool:
        om = (outdoor_model or "").upper()
        if any(k in om for k in ['RSUYQ', 'RXYQ', 'RXQ', 'RXYMQ', 'RXMQ', 'RXSQ', 'RWEYQ', 'VRV']):
            return True
        if re.search(r'R[A-Z0-9]*Q', om):
            return True
        if indoor_items and any(str(it.get("model", "")).upper().startswith("FX") for it in indoor_items):
            return True
        return False

    # ----------------------------------------------------
    # 級聯拓撲樹構建器 (核心邏輯：N台內機推導 N-1 個分歧頭)
    # ----------------------------------------------------
    @classmethod
    def build_cascading_system(cls, outdoor_model: str, indoor_items: List[Dict[str, Any]]) -> Tuple[PipingNode, List[Dict[str, Any]]]:
        """
        構建完整 VRV 級聯配管架構：
        - 室外機 -> 主幹管 -> 第一分歧頭
        - 分出第 1 台內機，主幹線續走次幹管至次分歧頭 1
        - 分出第 2 台內機，主幹線續走次幹管至次分歧頭 2
        - ...
        - 直至末端第 N-1 與第 N 台內機
        返回：(root_node, all_joints_list)
        """
        is_vrv = cls.check_is_vrv(outdoor_model, indoor_items)
        root = PipingNode('main', outdoor_model, model=outdoor_model)
        
        # 1. 整理末端負載節點 (支援 BP 箱連續 3 台 RA 自動聚合)
        raw_units = []
        for item in indoor_items:
            m = item.get("model", "")
            r_name = item.get("room_name", "")
            qty = item.get("qty", 1)
            is_ra = any(k in m.upper() for k in ['FTX', 'CTX', 'FTHF', 'FDXV'])
            is_sa = any(k in m.upper() for k in ['FBA', 'FAA', 'FCA', 'FFA', 'FHQ'])
            n_type = 'ra' if is_ra else ('sa' if is_sa else 'vrv')
            cap = cls.extract_capacity_index(m)
            for _ in range(qty):
                node = PipingNode(n_type, m, capacity=cap, qty=1, model=m, room_name=r_name)
                p = cls.get_indoor_branch_pipe(n_type, cap)
                node.pipe_liquid, node.pipe_gas = p["l"], p["g"]
                raw_units.append(node)

        # 若包含 RA 且為 VRV 系統，每 3 台 RA 合併為一個 BP 箱節點
        endpoints: List[PipingNode] = []
        if is_vrv:
            ra_buffer = []
            bp_idx = 1
            def flush_ra():
                nonlocal bp_idx
                while ra_buffer:
                    chunk = ra_buffer[:3]
                    del ra_buffer[:3]
                    bp_name = f"BP箱-{bp_idx} ({len(chunk)}台)"
                    bp_node = PipingNode('bp', bp_name, model=bp_name)
                    for ra in chunk:
                        bp_node.add_child(ra)
                    bp_cap = sum(c.capacity for c in chunk)
                    bp_node.capacity = bp_cap
                    bp_pipe = cls.get_bp_trunk_pipe(bp_cap)
                    bp_node.pipe_liquid, bp_node.pipe_gas = bp_pipe["l"], bp_pipe["g"]
                    endpoints.append(bp_node)
                    bp_idx += 1

            for u in raw_units:
                if u.node_type == 'ra':
                    ra_buffer.append(u)
                else:
                    flush_ra()
                    endpoints.append(u)
            flush_ra()
        else:
            endpoints = raw_units

        # 計算外機主幹管
        total_sys_cap = sum(ep.capacity for ep in endpoints)
        root.capacity = total_sys_cap
        main_pipes = cls.get_main_trunk_pipe(outdoor_model)
        root.pipe_liquid, root.pipe_gas = main_pipes["l"], main_pipes["g"]

        all_joints = []
        if not is_vrv or len(endpoints) == 0:
            # 非 VRV 系統 (RA 1對1、多聯等)：直接將內機掛在外機下，無分歧頭
            for ep in endpoints:
                root.add_child(ep)
            return root, all_joints

        if len(endpoints) == 1:
            # 單台內機無須分歧頭
            root.add_child(endpoints[0])
            return root, all_joints

        # ----------------------------------------------------
        # 級聯分歧構建 (Cascade Branching)
        # N 個 endpoint 需 N - 1 個分歧頭
        # ----------------------------------------------------
        first_joint_model = cls.get_first_joint(outdoor_model)
        root.joint_model = first_joint_model
        root.joint_role = "第一分歧頭"
        all_joints.append({
            "role": "第一分歧頭",
            "model": first_joint_model,
            "stage": 1,
            "downstream_cap": total_sys_cap
        })

        # 建立級聯鏈
        current_parent = root
        for i in range(len(endpoints) - 1):
            ep_current = endpoints[i]
            is_first_stage = (i == 0)
            is_last_stage = (i == len(endpoints) - 2)

            # 當前分歧節點
            joint_model = first_joint_model if is_first_stage else cls.get_secondary_joint(
                sum(ep.capacity for ep in endpoints[i:])
            )
            joint_role = "第一分歧頭" if is_first_stage else f"次分歧頭-{i}"
            if not is_first_stage:
                all_joints.append({
                    "role": joint_role,
                    "model": joint_model,
                    "stage": i + 1,
                    "downstream_cap": sum(ep.capacity for ep in endpoints[i:])
                })

            # 建立節點結構
            # 左側分支：當前 endpoint
            current_parent.add_child(ep_current)

            if is_last_stage:
                # 最後一個分歧頭，右側直接連接最後一台內機
                ep_last = endpoints[i + 1]
                current_parent.add_child(ep_last)
            else:
                # 中間分歧頭：建立下一個次分歧節點 (代表次幹管與次分歧頭)
                remaining_cap = sum(ep.capacity for ep in endpoints[i + 1:])
                sub_pipe = cls.get_sub_trunk_pipe(remaining_cap)
                next_joint_model = cls.get_secondary_joint(remaining_cap)
                sub_joint_node = PipingNode(
                    'joint',
                    f"次分歧頭-{i+1} ({next_joint_model})",
                    capacity=remaining_cap,
                    model=next_joint_model
                )
                sub_joint_node.pipe_liquid = sub_pipe["l"]
                sub_joint_node.pipe_gas = sub_pipe["g"]
                sub_joint_node.joint_model = next_joint_model
                sub_joint_node.joint_role = f"次分歧頭-{i+1}"
                current_parent.add_child(sub_joint_node)
                current_parent = sub_joint_node

        return root, all_joints

    # ----------------------------------------------------
    # 扁平化文字樹狀清單產生器 (符合 Excel 【系統套數】格式)
    # ----------------------------------------------------
    @classmethod
    def flatten_system_to_rows(cls, outdoor_model: str, indoor_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        is_vrv = cls.check_is_vrv(outdoor_model, indoor_items)
        rows = []
        rows.append({"結構": outdoor_model, "數量": 1, "is_main": True, "node_type": "main"})

        num_units = len(indoor_items)
        for idx, item in enumerate(indoor_items):
            is_last = (idx == num_units - 1)
            pref = "└─ " if is_last else "├─ "
            m = item.get("model", "")
            c = cls.extract_capacity_index(m)
            is_in_vrv = is_vrv or m.upper().startswith("FX")
            is_in_sa = any(k in m.upper() for k in ['FBA', 'FAA', 'FCA', 'FFA', 'FHQ'])
            n_type = 'vrv' if is_in_vrv else ('sa' if is_in_sa else 'ra')
            p = cls.get_indoor_branch_pipe(n_type, c)
            tag = "[VRV]" if is_in_vrv else ("[商用]" if is_in_sa else "[家用]")
            label = f"{pref}{tag} {m} (配管: {p['l']}/{p['g']})"
            rows.append({"結構": label, "數量": item.get("qty", 1), "is_main": False, "node_type": n_type})

        return rows


# ==============================================================================
# 2. 系統示意架構圖產生器 (CAD Flowchart Diagram Generator)
# ==============================================================================

class DaikinFlowchartDiagramDrawer:
    """
    動態生成專業 CAD 風格之 VRV 冷媒管徑與分歧流程圖 (PNG 格式)
    呈現：
    - 主機方塊 (型號、馬力、主幹管管徑標籤)
    - 各級第一分歧頭、次分歧頭節點圓圈與標籤
    - 垂直次幹管與管徑標籤
    - 水平配管與室內機方框 (含空間名稱、能力)
    - 直式 (Vertical) 與 橫式 (Horizontal) 兩種架構視圖
    """
    FONT_FAMILY = "C:/Windows/Fonts/msjh.ttc" # 微軟正黑體
    FONT_FAMILY_BD = "C:/Windows/Fonts/msjhbd.ttc"

    @classmethod
    def _get_font(cls, size: int, bold: bool = False):
        try:
            if bold and os.path.exists(cls.FONT_FAMILY_BD):
                return ImageFont.truetype(cls.FONT_FAMILY_BD, size)
            if os.path.exists(cls.FONT_FAMILY):
                return ImageFont.truetype(cls.FONT_FAMILY, size)
            if os.path.exists("C:/Windows/Fonts/arial.ttf"):
                return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
        except Exception:
            pass
        return ImageFont.load_default()

    @classmethod
    def draw_system_diagram(cls, outdoor_model: str, indoor_items: List[Dict[str, Any]], custom_notes: str = "") -> io.BytesIO:
        """
        繪製直式流程圖並傳回 PNG 二進位 BytesIO 物件 (已依指示移除底部提示框)
        """
        root_node, all_joints = DaikinVRVPipingEngine.build_cascading_system(outdoor_model, indoor_items)
        is_vrv = DaikinVRVPipingEngine.check_is_vrv(outdoor_model, indoor_items)

        width = 780
        row_height = 80
        header_height = 140
        footer_height = 25
        
        num_branches = max(len(indoor_items), 2)
        height = header_height + (num_branches * row_height) + footer_height

        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        font_box = cls._get_font(13, bold=True)
        font_pipe = cls._get_font(12, bold=True)
        font_joint = cls._get_font(12, bold=True)

        COLOR_MAIN = (0, 90, 158)        # 大金深藍
        COLOR_LINE = (0, 90, 158)
        COLOR_PIPE_BG = (255, 255, 255)
        COLOR_PIPE_TEXT = (211, 47, 47)  # 紅色
        COLOR_PIPE_BORDER = (227, 242, 253)
        COLOR_JOINT_BG = (255, 255, 255)
        COLOR_JOINT_TEXT = (211, 47, 47)
        COLOR_JOINT_BORDER = (255, 205, 210)
        COLOR_BOX_BG = (248, 250, 252)

        # 1. 繪製室外機卡片 (頂部置中偏左)
        out_x, out_y = 150, 25
        out_w, out_h = 240, 52
        draw.rectangle([out_x, out_y, out_x + out_w, out_y + out_h], fill=COLOR_MAIN, outline=COLOR_MAIN)
        out_title_str = "主機 (室外機)"
        out_spec_str = f"{outdoor_model}"
        draw.text((out_x + out_w // 2, out_y + 14), out_title_str, fill=(255, 255, 255), font=font_box, anchor="mm")
        draw.text((out_x + out_w // 2, out_y + 36), out_spec_str, fill=(255, 255, 255), font=font_box, anchor="mm")

        # 2. 外機垂直主幹管引出線
        trunk_x = out_x + 50
        trunk_y1 = out_y + out_h
        trunk_y2 = trunk_y1 + 45
        draw.line([(trunk_x, trunk_y1), (trunk_x, trunk_y2)], fill=COLOR_LINE, width=3)

        # 主幹管尺寸標籤 (紅字標註)
        if is_vrv:
            main_pipe_str = f"主幹管: {root_node.pipe_liquid} / {root_node.pipe_gas}"
            draw.rectangle([trunk_x + 15, trunk_y1 + 10, trunk_x + 190, trunk_y1 + 34], fill=COLOR_PIPE_BG, outline=COLOR_PIPE_TEXT, width=1)
            draw.text((trunk_x + 102, trunk_y1 + 22), main_pipe_str, fill=COLOR_PIPE_TEXT, font=font_pipe, anchor="mm")

        # 3. 逐層繪製各分支節點與室內機
        curr_y = trunk_y2
        horizontal_line_len = 240
        box_w, box_h = 300, 48

        flat_endpoints = []
        for item in indoor_items:
            m = item.get("model", "")
            r = item.get("room_name", "空間")
            c = DaikinVRVPipingEngine.extract_capacity_index(m)
            p = DaikinVRVPipingEngine.get_indoor_branch_pipe('vrv' if (is_vrv or m.upper().startswith("FX")) else 'ra', c)
            flat_endpoints.append({
                "model": m,
                "room": r,
                "cap": c,
                "pipe_l": p["l"],
                "pipe_g": p["g"]
            })

        num_units = len(flat_endpoints)
        joint_idx = 0

        for idx, ep in enumerate(flat_endpoints):
            branch_y = curr_y + (idx * row_height)
            is_last = (idx == num_units - 1)

            # (A) 垂直幹管
            if not is_last:
                draw.line([(trunk_x, branch_y), (trunk_x, branch_y + row_height)], fill=COLOR_LINE, width=3)
                # 若為 VRV 系統，且非末端，標註次幹管管徑
                if is_vrv and idx < len(all_joints) - 1:
                    rem_cap = sum(u["cap"] for u in flat_endpoints[idx+1:])
                    sub_p = DaikinVRVPipingEngine.get_sub_trunk_pipe(rem_cap)
                    sub_p_str = f"次幹: {sub_p['l']}/{sub_p['g']}"
                    draw.rectangle([trunk_x + 12, branch_y + 24, trunk_x + 150, branch_y + 44], fill=COLOR_PIPE_BG, outline=COLOR_PIPE_BORDER, width=1)
                    draw.text((trunk_x + 81, branch_y + 34), sub_p_str, fill=COLOR_PIPE_TEXT, font=font_pipe, anchor="mm")

            # (B) 分歧頭節點 (圓圈與型號)
            if is_vrv and num_units > 1:
                if not is_last:
                    draw.ellipse([trunk_x - 6, branch_y - 6, trunk_x + 6, branch_y + 6], fill=(255, 255, 255), outline=COLOR_PIPE_TEXT, width=2)
                    j_info = all_joints[joint_idx] if joint_idx < len(all_joints) else None
                    if j_info:
                        j_label = f"{j_info['model']} [{j_info['role']}]"
                        draw.rectangle([trunk_x - 170, branch_y - 12, trunk_x - 10, branch_y + 12], fill=COLOR_JOINT_BG, outline=COLOR_JOINT_BORDER, width=1)
                        draw.text((trunk_x - 90, branch_y), j_label, fill=COLOR_JOINT_TEXT, font=font_joint, anchor="mm")
                    joint_idx += 1
                else:
                    draw.ellipse([trunk_x - 5, branch_y - 5, trunk_x + 5, branch_y + 5], fill=COLOR_LINE)
            else:
                draw.ellipse([trunk_x - 5, branch_y - 5, trunk_x + 5, branch_y + 5], fill=COLOR_LINE)

            # (C) 水平分支管
            h_x2 = trunk_x + horizontal_line_len
            draw.line([(trunk_x, branch_y), (h_x2, branch_y)], fill=COLOR_LINE, width=2)

            # 配管尺寸標註
            branch_pipe_str = f"配管: {ep['pipe_l']} / {ep['pipe_g']}"
            mid_hx = (trunk_x + h_x2) // 2
            draw.rectangle([mid_hx - 60, branch_y - 18, mid_hx + 60, branch_y - 2], fill=COLOR_PIPE_BG, outline=COLOR_PIPE_BORDER, width=1)
            draw.text((mid_hx, branch_y - 10), branch_pipe_str, fill=COLOR_PIPE_TEXT, font=font_pipe, anchor="mm")

            # (D) 室內機卡片方框
            box_x = h_x2
            box_y = branch_y - (box_h // 2)
            draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=COLOR_BOX_BG, outline=COLOR_MAIN, width=2)
            room_title = f"{ep['room']}  ({ep['model']})"
            cap_sub = f"能力指數: {ep['cap']} | 分支配管: {ep['pipe_l']} / {ep['pipe_g']}"
            draw.text((box_x + 12, box_y + 14), room_title, fill=COLOR_MAIN, font=font_box, anchor="lm")
            draw.text((box_x + 12, box_y + 34), cap_sub, fill=(100, 116, 139), font=font_pipe, anchor="lm")

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    @classmethod
    def draw_horizontal_system_diagram(cls, outdoor_model: str, indoor_items: List[Dict[str, Any]], custom_notes: str = "") -> io.BytesIO:
        """
        繪製專業 CAD 風格之 VRV 冷媒管路【橫式水平配置】示意架構圖 (PNG 格式)
        呈現：
        - 左側主機方塊 (型號、馬力、主幹管尺寸)
        - 水平延伸主幹管與各級分歧頭節點 (圓圈、型號標註、次幹管管徑)
        - 垂直引下分支配管 (含管徑標註)
        - 下方整齊排列之室內機卡片 (空間名稱、型號、能力指數)
        - 依指示完全移除備註提示框
        """
        root_node, all_joints = DaikinVRVPipingEngine.build_cascading_system(outdoor_model, indoor_items)
        is_vrv = DaikinVRVPipingEngine.check_is_vrv(outdoor_model, indoor_items)

        flat_endpoints = []
        for item in indoor_items:
            m = item.get("model", "")
            r = item.get("room_name", "空間")
            c = DaikinVRVPipingEngine.extract_capacity_index(m)
            p = DaikinVRVPipingEngine.get_indoor_branch_pipe('vrv' if (is_vrv or m.upper().startswith("FX")) else 'ra', c)
            flat_endpoints.append({
                "model": m,
                "room": r,
                "cap": c,
                "pipe_l": p["l"],
                "pipe_g": p["g"]
            })

        num_units = max(len(flat_endpoints), 1)
        unit_w = 175
        unit_h = 56
        col_gap = 40
        left_margin = 250
        right_margin = 60
        top_y = 65
        card_y = 210
        img_h = 300
        img_w = max(left_margin + num_units * (unit_w + col_gap) + right_margin - col_gap, 800)

        img = Image.new('RGB', (img_w, img_h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        font_box = cls._get_font(12, bold=True)
        font_pipe = cls._get_font(11, bold=True)
        font_small = cls._get_font(10)

        COLOR_MAIN = (0, 90, 158)        # 大金深藍
        COLOR_LINE = (0, 90, 158)
        COLOR_PIPE_BG = (255, 255, 255)
        COLOR_PIPE_TEXT = (211, 47, 47)  # 紅色標註
        COLOR_PIPE_BORDER = (227, 242, 253)
        COLOR_BOX_BG = (248, 250, 252)

        # 1. 室外機 (左側)
        out_x, out_y = 25, top_y - 28
        out_w, out_h = 160, 56
        draw.rectangle([out_x, out_y, out_x + out_w, out_y + out_h], fill=COLOR_MAIN, outline=COLOR_MAIN)
        draw.text((out_x + out_w // 2, out_y + 16), "主機 (室外機)", fill=(255, 255, 255), font=font_box, anchor="mm")
        draw.text((out_x + out_w // 2, out_y + 38), outdoor_model, fill=(255, 255, 255), font=font_box, anchor="mm")

        # 2. 室外機出管至第一分歧點
        first_node_x = left_margin + (unit_w // 2)
        draw.line([(out_x + out_w, top_y), (first_node_x, top_y)], fill=COLOR_LINE, width=3)

        if is_vrv:
            pipe_m_str = f"主幹管: {root_node.pipe_liquid}/{root_node.pipe_gas}"
            mid_m_x = (out_x + out_w + first_node_x) // 2
            draw.rectangle([mid_m_x - 65, top_y - 25, mid_m_x + 65, top_y - 5], fill=COLOR_PIPE_BG, outline=COLOR_PIPE_TEXT, width=1)
            draw.text((mid_m_x, top_y - 15), pipe_m_str, fill=COLOR_PIPE_TEXT, font=font_pipe, anchor="mm")

        # 3. 逐一計算節點 X 座標
        node_positions = [left_margin + idx * (unit_w + col_gap) + (unit_w // 2) for idx in range(num_units)]

        # 繪製各分歧節點間的水平次幹管
        for idx in range(num_units - 1):
            x1 = node_positions[idx]
            x2 = node_positions[idx + 1]
            draw.line([(x1, top_y), (x2, top_y)], fill=COLOR_LINE, width=3)
            if is_vrv and idx < len(all_joints) - 1:
                rem_cap = sum(u["cap"] for u in flat_endpoints[idx+1:])
                sub_p = DaikinVRVPipingEngine.get_sub_trunk_pipe(rem_cap)
                sub_p_str = f"次幹: {sub_p['l']}/{sub_p['g']}"
                mid_x = (x1 + x2) // 2
                draw.rectangle([mid_x - 55, top_y - 24, mid_x + 55, top_y - 6], fill=COLOR_PIPE_BG, outline=COLOR_PIPE_BORDER, width=1)
                draw.text((mid_x, top_y - 15), sub_p_str, fill=COLOR_PIPE_TEXT, font=font_small, anchor="mm")

        # 繪製各節點垂直分支與室內機卡片
        for idx, ep in enumerate(flat_endpoints):
            nx = node_positions[idx]
            is_last = (idx == num_units - 1)

            # 分歧頭節點圓圈與標籤
            if is_vrv and num_units > 1:
                if not is_last:
                    draw.ellipse([nx - 6, top_y - 6, nx + 6, top_y + 6], fill=(255, 255, 255), outline=COLOR_PIPE_TEXT, width=2)
                    j_info = all_joints[idx] if idx < len(all_joints) else None
                    if j_info:
                        j_lbl = f"{j_info['model']} [{j_info.get('role', '分歧')}]"
                        draw.rectangle([nx - 65, top_y + 12, nx + 65, top_y + 30], fill=(255, 255, 255), outline=(255, 205, 210), width=1)
                        draw.text((nx, top_y + 21), j_lbl, fill=COLOR_PIPE_TEXT, font=font_small, anchor="mm")
                else:
                    draw.ellipse([nx - 5, top_y - 5, nx + 5, top_y + 5], fill=COLOR_LINE)
            else:
                draw.ellipse([nx - 5, top_y - 5, nx + 5, top_y + 5], fill=COLOR_LINE)

            # 垂直分支配管
            v_start_y = top_y + (32 if (is_vrv and num_units > 1 and not is_last) else 0)
            draw.line([(nx, v_start_y), (nx, card_y)], fill=COLOR_LINE, width=2)

            # 垂直管標註
            p_str = f"配管: {ep['pipe_l']}/{ep['pipe_g']}"
            mid_vy = (v_start_y + card_y) // 2
            draw.rectangle([nx - 52, mid_vy - 9, nx + 52, mid_vy + 9], fill=COLOR_PIPE_BG, outline=COLOR_PIPE_BORDER, width=1)
            draw.text((nx, mid_vy), p_str, fill=COLOR_PIPE_TEXT, font=font_small, anchor="mm")

            # 室內機卡片
            bx = nx - (unit_w // 2)
            by = card_y
            draw.rectangle([bx, by, bx + unit_w, by + unit_h], fill=COLOR_BOX_BG, outline=COLOR_MAIN, width=2)
            room_title = f"{ep['room']}  ({ep['model']})"
            cap_sub = f"能力: {ep['cap']} | 分支: {ep['pipe_l']}/{ep['pipe_g']}"
            draw.text((bx + unit_w // 2, by + 18), room_title, fill=COLOR_MAIN, font=font_box, anchor="mm")
            draw.text((bx + unit_w // 2, by + 40), cap_sub, fill=(100, 116, 139), font=font_small, anchor="mm")

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf
