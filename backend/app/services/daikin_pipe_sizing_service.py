import re
import math
from typing import List, Dict, Any, Optional

class HVACNode:
    """
    大金空調拓撲樹節點 (支援室外機 main、分歧節點 subgroup、BP箱 bp、室內機 vrv/ra)
    """
    def __init__(self, node_type: str, name: str, capacity: float = 0.0, qty: int = 1, model: str = ""):
        self.node_type = node_type # 'main', 'subgroup', 'bp', 'vrv', 'ra'
        self.name = name
        self.model = model or name
        self.capacity = capacity   # 能力指數 (Capacity Index)
        self.qty = qty
        self.children: List['HVACNode'] = []
        self.pipe_liquid = ""
        self.pipe_gas = ""
        self.joint_model = ""

    def add_child(self, child_node: 'HVACNode'):
        self.children.append(child_node)

    def calculate_totals(self) -> float:
        """
        自底向上計算累計能力指數
        """
        if self.node_type in ['vrv', 'ra']:
            return self.capacity * self.qty
        total = sum(child.calculate_totals() for child in self.children)
        self.capacity = total
        return total


class DaikinHVACCalculator:
    """
    嚴格依據《VRV冷媒管徑選用工具2026.5.xlsx》的管徑與分歧頭計算器
    """
    @staticmethod
    def extract_capacity_index(model_str: str, default_kw: float = 0.0) -> float:
        """
        從型號提取能力指數 (例如 FXDQ32 -> 32, FTXV28 -> 28, FTXV22 -> 22)
        若為 HP 馬力或 kW 則做適當轉換
        """
        m = re.search(r'(\d+)', str(model_str))
        if m:
            val = float(m.group(1))
            # 若型號數字為 22, 28, 32, 40, 50, 63, 80, 100, 125, 140, 200, 250 即為能力指數
            if val in [20, 22, 25, 28, 32, 36, 40, 41, 50, 60, 63, 71, 80, 90, 100, 112, 125, 140, 160, 200, 250, 300]:
                return val
            # 若大於 1000 可能為 kcal 或風量
            if val <= 60: # 可能是馬力 HP
                return val * 25.0
            return val
        if default_kw > 0:
            return round(default_kw * 10.0, 1)
        return 28.0

    @staticmethod
    def extract_outdoor_hp(outdoor_model: str) -> float:
        """
        從室外機型號提取 HP 或能力指數
        """
        out_upper = str(outdoor_model).strip().upper()
        # 例如 RXYQ8AYLT -> 8 HP, RXYQ10AYLT -> 10 HP, RXYQ14AYLT -> 14 HP
        m = re.search(r'(?:RXYQ|RXQ|RSUYQ|REYQ|RWEYQ|RXYMQ|RXYCQ)(\d+)', out_upper)
        if m:
            val = float(m.group(1))
            # 若為 RSUYQ112 -> 112 即 4HP, RSUYQ140 -> 140 即 6HP
            if val in [112, 125, 140, 160]:
                return val # 側吹能力指數
            if val in [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 40, 48, 54, 60]:
                return val
        # 尋找任意數字
        m_any = re.search(r'(\d+)', out_upper)
        if m_any:
            v = float(m_any.group(1))
            return v if v <= 60 else round(v / 25.0, 1)
        return 8.0

    @staticmethod
    def is_side_discharge(outdoor_model: str) -> bool:
        """
        判定是否為側吹型 (VRV-S, VRV mini, RSUYQ, RXYCQ, RXYMQ)
        """
        out_upper = str(outdoor_model).strip().upper()
        return any(k in out_upper for k in ['RSUYQ', 'RXYCQ', 'RXYMQ', 'VRV-S', 'MINI'])

    # ----------------------------------------------------
    # 1. 主幹管選用 (室外機至第一分歧頭)
    # ----------------------------------------------------
    def get_main_pipe(self, outdoor_model: str, capacity_sum: float) -> Dict[str, str]:
        """
        依室外機機型判定主幹管徑 (液管 / 氣管)
        """
        is_side = self.is_side_discharge(outdoor_model)
        hp = self.extract_outdoor_hp(outdoor_model)

        if is_side:
            # 側吹型 VRV-S 主幹管選用表 (表 3)
            # HP <= 125 (4~6HP) -> Ø9.5 / Ø15.9
            # 150 <= HP <= 200 (6~8HP) -> Ø9.5 / Ø19.1
            # 215 <= HP <= 250 (10HP) -> Ø9.5 / Ø22.2
            # 300 = HP (12HP) -> Ø12.7 / Ø25.4
            if hp <= 125 or hp <= 6:
                return {"l": "Ø9.5", "g": "Ø15.9", "code": "TR2"}
            elif hp <= 200 or hp <= 8:
                return {"l": "Ø9.5", "g": "Ø19.1", "code": "TR3"}
            elif hp <= 250 or hp <= 10:
                return {"l": "Ø9.5", "g": "Ø22.2", "code": "TR4"}
            else:
                return {"l": "Ø12.7", "g": "Ø25.4", "code": "TR5"}
        else:
            # 上吹型 VRV 主幹管選用表 (表 3)
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
    # 2. 第一分歧頭選用 (表 1)
    # ----------------------------------------------------
    def get_first_joint(self, outdoor_model: str) -> str:
        """
        依室外機容量選用第一分歧頭
        """
        is_side = self.is_side_discharge(outdoor_model)
        hp = self.extract_outdoor_hp(outdoor_model)

        if is_side:
            # 側吹型表 1
            if hp < 200 and hp < 8:
                return "KHRP26A22T"
            elif hp <= 250 or hp <= 10:
                return "KHRP26A33T"
            else:
                return "KHRP26A72T"
        else:
            # 上吹型表 1
            if hp <= 6:
                return "KHRP26A22T"
            elif hp <= 10:
                return "KHRP26A33T"
            elif hp <= 22:
                return "KHRP26A72T"
            else:
                return "KHRP26A73T+KHRP26M73TP"

    # ----------------------------------------------------
    # 3. 次幹管選用 (表 4 - 依下游標稱能力總和 X)
    # ----------------------------------------------------
    def get_sub_pipe(self, x_capacity: float) -> Dict[str, str]:
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
    # 4. 後續分歧頭選用 (表 2 - 依下游標稱能力總和 X)
    # ----------------------------------------------------
    def get_joint(self, x_capacity: float) -> str:
        """
        分歧頭選用表 (表 2)
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
    # 5. 室內機分支管選用 (表 5 - 末端配管)
    # ----------------------------------------------------
    def get_indoor_pipe(self, node_type: str, capacity: float) -> Dict[str, str]:
        """
        室內機分支管選用表 (表 5) 及家用壁掛專用管徑
        """
        if node_type == 'ra':
            # 家用壁掛機配管
            if capacity <= 36:
                return {"l": "Ø6.4", "g": "Ø9.5", "code": "RA1"}
            elif capacity <= 71:
                return {"l": "Ø6.4", "g": "Ø12.7", "code": "RA2"}
            else:
                return {"l": "Ø6.4", "g": "Ø15.9", "code": "RA3"}
        else:
            # VRV 室內機分支管
            if capacity <= 50:
                return {"l": "Ø6.4", "g": "Ø12.7", "code": "TR1"}
            elif capacity <= 140:
                return {"l": "Ø9.5", "g": "Ø15.9", "code": "TR2"}
            elif capacity <= 200:
                return {"l": "Ø9.5", "g": "Ø19.1", "code": "TR3"}
            else:
                return {"l": "Ø9.5", "g": "Ø22.2", "code": "TR4"}

    def get_bp_pipe(self, capacity: float) -> Dict[str, str]:
        """
        BP箱接入 VRV 主系統之次幹管 (通常 BP 箱 3 台容量在 60~120 之間)
        """
        return self.get_sub_pipe(capacity)

    # ----------------------------------------------------
    # 6. BP 箱分組構建器 (每 3 台 RA 自動一組)
    # ----------------------------------------------------
    def build_system_with_bp_boxes(self, indoor_nodes: List[HVACNode]) -> List[HVACNode]:
        processed = []
        ra_buffer = []

        def flush_ra():
            nonlocal ra_buffer
            bp_count = 1
            while ra_buffer:
                chunk = ra_buffer[:3]
                del ra_buffer[:3]
                total_qty = sum(c.qty for c in chunk)
                bp_name = f"BP箱-{bp_count} ({total_qty}台)"
                bp = HVACNode('bp', bp_name)
                for ra in chunk:
                    bp.add_child(ra)
                processed.append(bp)
                bp_count += 1

        for node in indoor_nodes:
            if node.node_type == 'ra':
                ra_buffer.append(node)
            else:
                flush_ra()
                processed.append(node)
        flush_ra()
        return processed

    # ----------------------------------------------------
    # 7. 遞迴計算整棵樹的管徑與分歧頭
    # ----------------------------------------------------
    def evaluate_tree(self, node: HVACNode, is_root: bool = True):
        node.calculate_totals()

        if node.node_type in ['vrv', 'ra']:
            pipes = self.get_indoor_pipe(node.node_type, node.capacity)
            node.pipe_liquid, node.pipe_gas = pipes["l"], pipes["g"]

        elif node.node_type == 'bp':
            pipes = self.get_bp_pipe(node.capacity)
            node.pipe_liquid, node.pipe_gas = pipes["l"], pipes["g"]
            node.joint_model = self.get_joint(node.capacity)
            for child in node.children:
                self.evaluate_tree(child, is_root=False)

        elif node.node_type in ['subgroup', 'main']:
            if is_root:
                pipes = self.get_main_pipe(node.model, node.capacity)
                node.joint_model = self.get_first_joint(node.model)
            else:
                pipes = self.get_sub_pipe(node.capacity)
                if node.children:
                    node.joint_model = self.get_joint(node.capacity)

            node.pipe_liquid, node.pipe_gas = pipes["l"], pipes["g"]
            for child in node.children:
                self.evaluate_tree(child, is_root=False)

    # ----------------------------------------------------
    # 8. 將 HVACNode 樹展平為報表文字列
    # ----------------------------------------------------
    def flatten_tree_to_rows(self, node: HVACNode, prefix: str = "", is_last: bool = True, is_root: bool = True) -> List[Dict[str, Any]]:
        rows = []
        if is_root:
            joint_info = f" | 主分歧: {node.joint_model}" if node.joint_model else ""
            pipe_info = f"主管: {node.pipe_liquid}/{node.pipe_gas}" if node.pipe_liquid else ""
            specs = f" ({pipe_info}{joint_info})" if (pipe_info or joint_info) else ""
            node_label = f"{node.name}{specs}"
            rows.append({"結構": node_label, "數量": node.qty, "node": node})

            for idx, child in enumerate(node.children):
                last_child = (idx == len(node.children) - 1)
                rows.extend(self.flatten_tree_to_rows(child, prefix="", is_last=last_child, is_root=False))
        else:
            branch = "└─ " if is_last else "├─ "
            joint_info = f" | 分歧: {node.joint_model}" if node.joint_model else ""
            
            if node.node_type == 'bp':
                pipe_info = f"次幹: {node.pipe_liquid}/{node.pipe_gas}"
                tag = "[BP箱] "
            elif node.node_type == 'ra':
                pipe_info = f"配管: {node.pipe_liquid}/{node.pipe_gas}"
                tag = "[家用] "
            else:
                pipe_info = f"配管: {node.pipe_liquid}/{node.pipe_gas}"
                tag = "[VRV] "

            specs = f" ({pipe_info}{joint_info})"
            node_label = f"{prefix}{branch}{tag}{node.name}{specs}"
            rows.append({"結構": node_label, "數量": node.qty, "node": node})

            new_prefix = prefix + ("    " if is_last else "│   ")
            for idx, child in enumerate(node.children):
                last_child = (idx == len(node.children) - 1)
                rows.extend(self.flatten_tree_to_rows(child, prefix=new_prefix, is_last=last_child, is_root=False))

        return rows
