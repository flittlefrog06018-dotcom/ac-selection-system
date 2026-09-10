import re
import math
from typing import List, Dict, Any
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

class EquipmentSummaryService:
    """
    大金設備統計、系統套數樹狀拓撲、D3-NET 控制通訊分析專用引擎
    獨立模組化設計，不增加主匯出程式負擔
    """

    @staticmethod
    def get_cap(model_str: str) -> int:
        n = re.search(r'(\d+)', str(model_str))
        return int(n.group(1)) if n else 0

    @staticmethod
    def get_model_series(model_str: str) -> str:
        m = re.match(r'([a-zA-Z]+)', str(model_str))
        return m.group(1).upper() if m else ""

    @classmethod
    def get_sys_weight(cls, name: str) -> int:
        name = str(name).upper()
        if "家用1對1" in name or "[家用]" in name:
            return 1
        if "家用多聯" in name:
            return 2
        if "商用" in name:
            return 3
        if "VRV" in name:
            return 4
        if "全熱" in name:
            return 5
        return 6

    @classmethod
    def get_in_label(cls, model_str: str) -> tuple:
        mn = str(model_str).upper()
        if any(k in mn for k in ['FTHF', 'FTXV', 'FTXM', 'FDXV', 'CTXZ', 'CTX']):
            return "[家用]", 1
        if mn.startswith('FX'):
            return "[VRV]", 4
        if any(k in mn for k in ['FBA', 'FCA', 'FFA', 'FCQ', 'FHQ']):
            return "[商用]", 3
        if any(k in mn for k in ['VAM', 'VKM']):
            return "[全熱]", 5
        return "[其他]", 6

    @classmethod
    def get_indoor_accessory_rules(cls) -> Dict[str, Dict[str, str]]:
        """
        參照 EQUIPMENT_Data.xlsx (包含 indoor_units 與 indoor_units_SA only 分頁)，
        動態獲取各室內機型號對應之：
        - Row 14: 轉接小P版 (adapter_p_board)
        - Row 15: 無線接收器 / APP轉接卡 (wireless_receiver)
        - Row 16: 集控轉接基板 (central_adapter_board)
        """
        rules = {}
        try:
            from app.services.equipment_db_service import EquipmentDBService
            db_srv = EquipmentDBService.get_instance()
            if not getattr(db_srv, "units", None):
                db_srv.load_equipment_db()
            for u in getattr(db_srv, "units", []):
                m = str(u.get("model", "")).strip().upper()
                if not m:
                    continue
                p_board = str(u.get("adapter_p_board") or "").strip()
                w_recv = str(u.get("wireless_receiver") or "").strip()
                c_board = str(u.get("central_adapter_board") or "").strip()
                rules[m] = {
                    "adapter_board": p_board if p_board not in ["-", "內建", "None", ""] else None,
                    "app_receiver": w_recv if w_recv not in ["-", "None", ""] else None,
                    "central_board": c_board if c_board not in ["-", "None", ""] else None,
                }
        except Exception as err:
            import logging
            logging.getLogger(__name__).warning(f"Error loading indoor accessory rules: {err}")
        return rules

    @classmethod
    def process_units_table(cls, data: List[Dict[str, Any]], is_out: bool = False) -> List[Dict[str, Any]]:
        """
        統整型號與台數，並執行：系統權重 -> 系列英文字母 -> 容量由大到小排序
        """
        if not data:
            return []

        grouped = {}
        for item in data:
            m = str(item.get("model", "")).strip().upper()
            q = int(item.get("qty", 1))
            sys_name = str(item.get("sys", "")).strip()

            if not m or m in ["-", "NONE", ""]:
                continue

            key = (m, sys_name) if is_out else m
            if key not in grouped:
                series = cls.get_model_series(m)
                cap = cls.get_cap(m)
                if is_out:
                    weight = cls.get_sys_weight(sys_name)
                    disp_name = f"[{sys_name}] {m}" if sys_name else m
                elif sys_name in ["冷媒分歧頭", "控制介面"]:
                    weight = 7 if sys_name == "冷媒分歧頭" else 8
                    disp_name = m
                else:
                    pref, weight = cls.get_in_label(m)
                    disp_name = f"{pref} {m}"

                grouped[key] = {
                    "raw_model": m,
                    "display_name": disp_name,
                    "qty": 0,
                    "series": series,
                    "cap": cap,
                    "weight": weight
                }
            grouped[key]["qty"] += q

        records = list(grouped.values())
        # 排序：權重正序 -> 系列字母正序 -> 容量倒序 (大到小)
        records.sort(key=lambda x: (x["weight"], x["series"], -x["cap"]))
        return records

    @classmethod
    def append_summary_sheets(cls, wb, rooms_data: List[Dict[str, Any]], outdoor_groups: List[Dict[str, Any]] = None):
        """
        在現有的 workbook 之後附加三個專業統計分頁：
        1. 設備統計總表
        2. 系統套數 (樹狀結構)
        3. D3-NET分析
        """
        # 樣式定義 (採用現代大金專業灰藍工程配色)
        font_header = Font(name="微軟正黑體", size=11, bold=True, color="FFFFFF")
        font_data = Font(name="微軟正黑體", size=10)
        font_bold = Font(name="微軟正黑體", size=10, bold=True)
        font_title = Font(name="微軟正黑體", size=12, bold=True, color="0F172A")
        
        fill_header = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        fill_subtotal = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        fill_card = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")
        
        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )
        border_total = Border(
            top=Side(style='thin', color='475569'),
            bottom=Side(style='double', color='0F172A')
        )

        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")

        # --- 資料歸類提取 ---
        indoor_items = []
        outdoor_items = []
        hrv_items = []
        system_tree_nodes = [] # 室外機對應室內機階層結構

        # 建立群組映射字典
        groups_map = {str(g.get("id", "")): g for g in (outdoor_groups or [])}

        # 掃描 room_data 建立外機與內機配對
        # 先按 outdoorGroupId 聚合成系統拓撲
        grouped_by_outdoor = {}
        standalone_idx = 1

        for r in rooms_data:
            m_in = str(r.get("recommended_model") or r.get("indoor_model") or r.get("best_match_model") or "").strip()
            q_in = int(r.get("qty") or r.get("unit_count") or 1)
            
            if not m_in or m_in in ["-", "NONE", ""]:
                continue

            # 內機與全熱分流
            if any(k in m_in.upper() for k in ["VAM", "VKM"]):
                hrv_items.append({"model": m_in, "qty": q_in})
            else:
                indoor_items.append({"model": m_in, "qty": q_in})

            # 外機分組歸類
            g_id = r.get("outdoorGroupId") or r.get("outdoor_group_id") or r.get("group_id")
            out_model = str(r.get("outdoor_model", "")).strip()
            out_qty = int(r.get("outdoor_qty", 1))

            if g_id and g_id in groups_map:
                g_obj = groups_map[g_id]
                out_model = str(g_obj.get("outdoor_model") or out_model).strip()
                out_qty = int(g_obj.get("outdoor_qty", 1))
                sys_key = f"group_{g_id}"
            elif g_id:
                sys_key = f"group_{g_id}"
            else:
                sys_key = f"single_{standalone_idx}"
                standalone_idx += 1

            # 推導室外機所屬系統別
            out_upper = out_model.upper()
            if any(k in out_upper for k in ['RSUYQ', 'RXQ', 'RXYQ', 'RXYMQ', 'RXYCQ', 'REYQ', 'RWEYQ']):
                sys_name = "VRV系統"
            elif any(k in out_upper for k in ['RKF', 'RZF', 'RZAC', 'RZA']):
                sys_name = "商用1對1系統"
            elif any(k in out_upper for k in ['2MXM', '3MXM', '4MXM', '5MXM', '2MXP']):
                sys_name = "家用多聯系統"
            elif any(k in out_upper for k in ['RXM', 'RXV', 'RHF', 'RX']):
                sys_name = "家用1對1系統"
            else:
                sys_name = "VRV系統" if "FX" in m_in.upper() else "空調系統"

            if sys_key not in grouped_by_outdoor:
                grouped_by_outdoor[sys_key] = {
                    "outdoor_model": out_model,
                    "outdoor_qty": out_qty,
                    "sys_name": sys_name,
                    "indoor_list": []
                }
            grouped_by_outdoor[sys_key]["indoor_list"].append({"model": m_in, "qty": q_in})

        # 收集所有室外機統計清單
        for sys_k, g_data in grouped_by_outdoor.items():
            if g_data["outdoor_model"] and g_data["outdoor_model"] != "-":
                outdoor_items.append({
                    "model": g_data["outdoor_model"],
                    "qty": g_data["outdoor_qty"],
                    "sys": g_data["sys_name"]
                })

        from app.services.equipment_db_service import EquipmentDBService
        db_srv = EquipmentDBService.get_instance()

        # 🎯 收集轉接小P板、無線接收器、集控轉接基板統計清單
        adapter_board_items = []
        try:
            acc_rules = cls.get_indoor_accessory_rules()
            for r in rooms_data:
                m_in = str(r.get("recommended_model") or r.get("indoor_model") or r.get("best_match_model") or "").strip().upper()
                q_in = int(r.get("qty") or r.get("unit_count") or 1)
                ctrl_mode = str(r.get("control_mode") or r.get("ctrl_mode") or "").strip().upper()
                if not m_in or m_in in ["-", "NONE", ""]:
                    continue
                rule = acc_rules.get(m_in, {})
                p_board = rule.get("adapter_board")
                w_recv = rule.get("app_receiver")
                c_board = rule.get("central_board")

                # 若選 APP 控制
                if "APP" in ctrl_mode:
                    if p_board:
                        adapter_board_items.append({"model": f"轉接小P板 ({p_board})", "qty": q_in, "sys": "控制介面"})
                    if w_recv and w_recv != "內建":
                        adapter_board_items.append({"model": f"APP控制卡 ({w_recv})", "qty": q_in, "sys": "控制介面"})
                    elif not w_recv and not any(k in m_in for k in ["內建", "FX"]):
                        adapter_board_items.append({"model": "APP控制卡 (BRP072C42)", "qty": q_in, "sys": "控制介面"})
                # 若選集控控制
                if "集控" in ctrl_mode or "CENTRAL" in ctrl_mode:
                    if p_board:
                        adapter_board_items.append({"model": f"轉接小P板 ({p_board})", "qty": q_in, "sys": "控制介面"})
                    if c_board:
                        adapter_board_items.append({"model": f"集控轉接基板 ({c_board})", "qty": q_in, "sys": "控制介面"})
        except Exception as act_err:
            logger.warning(f"Failed to extract control accessories: {act_err}")

        # 🎯 利用 DaikinHVACCalculator 獨立運算管徑與分歧頭 (只有 VRV 系統會用到分歧頭以及 BP 箱)
        joint_items = []
        try:
            from app.services.daikin_pipe_sizing_service import DaikinHVACCalculator, HVACNode
            pipe_calc = DaikinHVACCalculator()
            for sys_k, g_data in grouped_by_outdoor.items():
                out_m = g_data["outdoor_model"] or ""
                if not out_m or out_m == "-":
                    continue
                root_node = HVACNode('main', out_m, qty=g_data["outdoor_qty"], model=out_m)
                child_nodes = []
                is_vrv_sys = any(k in out_m.upper() for k in ['RSUYQ', 'RXYQ', 'RXQ']) or ('VRV' in g_data.get("sys_name", "").upper())

                for in_item in g_data["indoor_list"]:
                    in_m = in_item["model"]
                    in_q = in_item["qty"]
                    is_ra_unit = any(k in in_m.upper() for k in ['FTX', 'CTX', 'FTHF', 'FDXV'])
                    is_sa_unit = any(k in in_m.upper() for k in ['FBA', 'FAA', 'FCA', 'FFA', 'FHQ'])
                    if is_ra_unit:
                        n_type = 'ra'
                    elif is_sa_unit:
                        n_type = 'sa'
                    else:
                        n_type = 'vrv'
                    c_idx = pipe_calc.extract_capacity_index(in_m)
                    child_nodes.append(HVACNode(n_type, in_m, capacity=c_idx, qty=in_q, model=in_m))
                
                # 🎯 只有 VRV 系統才會用到 BP 箱與分歧頭！
                if is_vrv_sys:
                    grouped_children = pipe_calc.build_system_with_bp_boxes(child_nodes)
                    for ch in grouped_children:
                        root_node.add_child(ch)
                    pipe_calc.evaluate_tree(root_node, is_root=True)
                    
                    # 只有 VRV 系統才清點分歧頭
                    def collect_joints(node: HVACNode):
                        if node.joint_model:
                            for j_single in node.joint_model.split('+'):
                                joint_items.append({"model": j_single.strip(), "qty": 1, "sys": "冷媒分歧頭"})
                        for c_node in node.children:
                            collect_joints(c_node)
                    collect_joints(root_node)
                else:
                    # SA 商用與 RA 家用多聯/1對1：直接配管至室內機，無分歧頭、無 BP 箱！
                    for ch in child_nodes:
                        pipes = pipe_calc.get_indoor_pipe(ch.node_type, ch.capacity)
                        ch.pipe_liquid, ch.pipe_gas = pipes["l"], pipes["g"]
                        root_node.add_child(ch)
                    # 主管由室外機型號判定
                    m_pipes = pipe_calc.get_main_pipe(out_m, sum(ch.capacity for ch in child_nodes))
                    root_node.pipe_liquid, root_node.pipe_gas = m_pipes["l"], m_pipes["g"]
                    root_node.joint_model = None

                g_data["evaluated_tree"] = root_node
        except Exception as pipe_err:
            logger.warning(f"Failed to evaluate pipe sizing: {pipe_err}")

        # ========================================================
        # 0. 建立分頁【設備報價單】 (依據經理指示之報價清冊格式，緊接在主選機表之後)
        # ========================================================
        ws_quote = cls._build_quotation_sheet(
            wb, rooms_data, grouped_by_outdoor, hrv_items, joint_items, adapter_board_items, db_srv
        )

        # ========================================================
        # 1. 建立分頁【設備統計總表】
        # ========================================================
        ws1 = wb.create_sheet(title="設備統計總表")
        ws1.views.sheetView[0].showGridLines = True

        t_in = cls.process_units_table(indoor_items, is_out=False)
        t_out = cls.process_units_table(outdoor_items, is_out=True)
        t_hrv = cls.process_units_table(hrv_items, is_out=False)
        t_joint = cls.process_units_table(joint_items, is_out=False)
        t_adapter = cls.process_units_table(adapter_board_items, is_out=False)

        # 標題
        ws1.cell(row=2, column=2).value = "大金空調設備與配件統計總表"
        ws1.cell(row=2, column=2).font = Font(name="微軟正黑體", size=14, bold=True, color="0F172A")
        
        # 欄位抬頭：室內機 (B, C)、室外機 (E, F)、全熱 (H, I)、分歧頭 (K, L)、控制配件 (N, O)
        headers = [
            (2, "室內機型號"), (3, "室內機台數"),
            (5, "室外機型號"), (6, "室外機台數"),
            (8, "全熱型號"), (9, "全熱台數"),
            (11, "冷媒分歧頭型號"), (12, "分歧頭數量"),
            (14, "控制/轉接配件型號"), (15, "配件數量")
        ]
        for col_idx, h_text in headers:
            c = ws1.cell(row=4, column=col_idx)
            c.value = h_text
            c.font = font_header
            c.fill = fill_header
            c.alignment = align_center
            c.border = border_thin

        max_rows = max(len(t_in), len(t_out), len(t_hrv), len(t_joint), len(t_adapter), 1)

        for idx in range(max_rows):
            r_idx = 5 + idx
            # 室內機
            if idx < len(t_in):
                c_m = ws1.cell(row=r_idx, column=2, value=t_in[idx]["display_name"])
                c_q = ws1.cell(row=r_idx, column=3, value=t_in[idx]["qty"])
                c_m.font = font_data; c_m.alignment = align_left; c_m.border = border_thin
                c_q.font = font_data; c_q.alignment = align_center; c_q.border = border_thin

            # 室外機
            if idx < len(t_out):
                c_m = ws1.cell(row=r_idx, column=5, value=t_out[idx]["display_name"])
                c_q = ws1.cell(row=r_idx, column=6, value=t_out[idx]["qty"])
                c_m.font = font_data; c_m.alignment = align_left; c_m.border = border_thin
                c_q.font = font_data; c_q.alignment = align_center; c_q.border = border_thin

            # 全熱
            if idx < len(t_hrv):
                c_m = ws1.cell(row=r_idx, column=8, value=t_hrv[idx]["display_name"])
                c_q = ws1.cell(row=r_idx, column=9, value=t_hrv[idx]["qty"])
                c_m.font = font_data; c_m.alignment = align_left; c_m.border = border_thin
                c_q.font = font_data; c_q.alignment = align_center; c_q.border = border_thin

            # 冷媒分歧頭
            if idx < len(t_joint):
                c_m = ws1.cell(row=r_idx, column=11, value=t_joint[idx]["display_name"])
                c_q = ws1.cell(row=r_idx, column=12, value=t_joint[idx]["qty"])
                c_m.font = font_data; c_m.alignment = align_left; c_m.border = border_thin
                c_q.font = font_data; c_q.alignment = align_center; c_q.border = border_thin

            # 控制/轉接配件
            if idx < len(t_adapter):
                c_m = ws1.cell(row=r_idx, column=14, value=t_adapter[idx]["display_name"])
                c_q = ws1.cell(row=r_idx, column=15, value=t_adapter[idx]["qty"])
                c_m.font = font_data; c_m.alignment = align_left; c_m.border = border_thin
                c_q.font = font_data; c_q.alignment = align_center; c_q.border = border_thin

        # 合計列
        tot_row = 5 + max_rows
        ws1.cell(row=tot_row, column=2, value="合計").font = font_bold
        ws1.cell(row=tot_row, column=3, value=sum(x["qty"] for x in t_in)).font = font_bold
        ws1.cell(row=tot_row, column=5, value="合計").font = font_bold
        ws1.cell(row=tot_row, column=6, value=sum(x["qty"] for x in t_out)).font = font_bold
        ws1.cell(row=tot_row, column=8, value="合計").font = font_bold
        ws1.cell(row=tot_row, column=9, value=sum(x["qty"] for x in t_hrv)).font = font_bold
        ws1.cell(row=tot_row, column=11, value="合計").font = font_bold
        ws1.cell(row=tot_row, column=12, value=sum(x["qty"] for x in t_joint)).font = font_bold
        ws1.cell(row=tot_row, column=14, value="合計").font = font_bold
        ws1.cell(row=tot_row, column=15, value=sum(x["qty"] for x in t_adapter)).font = font_bold

        for col_idx in [2, 3, 5, 6, 8, 9, 11, 12, 14, 15]:
            cell = ws1.cell(row=tot_row, column=col_idx)
            cell.fill = fill_subtotal
            cell.border = border_total
            if col_idx in [3, 6, 9, 12, 15]:
                cell.alignment = align_center

        # ========================================================
        # 2. 建立分頁【系統套數】(樹狀結構與冷媒管徑分歧頭)
        # ========================================================
        ws2 = wb.create_sheet(title="系統套數")
        ws2.views.sheetView[0].showGridLines = True

        ws2.cell(row=2, column=2).value = "空調系統套數、樹狀結構與冷媒管徑選用"
        ws2.cell(row=2, column=2).font = Font(name="微軟正黑體", size=14, bold=True, color="0F172A")

        c1 = ws2.cell(row=4, column=2, value="系統結構與配管規格 (室外機 -> 主管/分歧頭 -> 配接室內機)")
        c2 = ws2.cell(row=4, column=3, value="台數")
        c1.font = font_header; c1.fill = fill_header; c1.alignment = align_left; c1.border = border_thin
        c2.font = font_header; c2.fill = fill_header; c2.alignment = align_center; c2.border = border_thin

        curr_r = 5
        sys_counter = 1

        for sys_k, g_data in grouped_by_outdoor.items():
            out_m = g_data["outdoor_model"] or "待配室外機"
            out_q = g_data["outdoor_qty"]
            sys_lbl = g_data["sys_name"]

            # 若有樹狀運算結果
            tree_root = g_data.get("evaluated_tree")
            if tree_root:
                try:
                    from app.services.daikin_pipe_sizing_service import DaikinHVACCalculator
                    pipe_calc = DaikinHVACCalculator()
                    flat_rows = pipe_calc.flatten_tree_to_rows(tree_root)
                    for r_item in flat_rows:
                        is_main = (r_item["node"].node_type == "main")
                        cell_node = ws2.cell(row=curr_r, column=2, value=f"{sys_counter}. [{sys_lbl}] {r_item['結構']}" if is_main else r_item['結構'])
                        cell_q = ws2.cell(row=curr_r, column=3, value=r_item["數量"])
                        cell_node.font = font_bold if is_main else font_data
                        cell_node.border = border_thin
                        cell_node.fill = fill_subtotal if is_main else PatternFill(fill_type=None)
                        cell_q.font = font_bold if is_main else font_data
                        cell_q.alignment = align_center
                        cell_q.border = border_thin
                        cell_q.fill = fill_subtotal if is_main else PatternFill(fill_type=None)
                        curr_r += 1
                except Exception as tr_err:
                    logger.warning(f"Flatten tree failed: {tr_err}")
            else:
                # 外機主節點
                cell_node = ws2.cell(row=curr_r, column=2, value=f"{sys_counter}. [{sys_lbl}] {out_m}")
                cell_q = ws2.cell(row=curr_r, column=3, value=out_q)
                cell_node.font = font_bold; cell_node.border = border_thin; cell_node.fill = fill_subtotal
                cell_q.font = font_bold; cell_q.alignment = align_center; cell_q.border = border_thin; cell_q.fill = fill_subtotal
                curr_r += 1

                # 聚合室內機型號
                in_grouped = {}
                for in_item in g_data["indoor_list"]:
                    m = in_item["model"]
                    in_grouped[m] = in_grouped.get(m, 0) + in_item["qty"]

                in_list = [{"model": m, "qty": q, "series": cls.get_model_series(m), "cap": cls.get_cap(m)} for m, q in in_grouped.items()]
                in_list.sort(key=lambda x: (x["series"], -x["cap"]))

                for j, in_node in enumerate(in_list):
                    pref = "    └─ " if j == len(in_list) - 1 else "    ├─ "
                    c_tree = ws2.cell(row=curr_r, column=2, value=f"{pref}{in_node['model']}")
                    c_tree_q = ws2.cell(row=curr_r, column=3, value=in_node["qty"])
                    c_tree.font = font_data; c_tree.border = border_thin
                    c_tree_q.font = font_data; c_tree_q.alignment = align_center; c_tree_q.border = border_thin
                    curr_r += 1

            # 空行隔開不同系統
            curr_r += 1
            sys_counter += 1

        # ========================================================
        # 3. 建立分頁【D3-NET分析】
        # ========================================================
        ws3 = wb.create_sheet(title="D3-NET分析")
        ws3.views.sheetView[0].showGridLines = True

        comb_in = indoor_items + hrv_items
        d3_in_table = cls.process_units_table(comb_in, is_out=False)
        
        # 僅取 VRV 室外機
        vrv_out_items = [o for o in outdoor_items if "VRV" in str(o.get("sys", "")).upper()]
        d3_out_table = cls.process_units_table(vrv_out_items, is_out=True)

        s_in = sum(x["qty"] for x in d3_in_table)
        s_out = sum(x["qty"] for x in d3_out_table)
        suggested_ports = max(math.ceil(s_in / 64) if s_in > 0 else 1, math.ceil(s_out / 10) if s_out > 0 else 1)

        ws3.cell(row=2, column=2).value = "大金 D3-NET 集中控制通訊埠分析報告"
        ws3.cell(row=2, column=2).font = Font(name="微軟正黑體", size=14, bold=True, color="0F172A")

        # 抬頭
        d3_headers = [
            (2, "室內/全熱機型號"), (3, "室內/全熱機台數"),
            (5, "VRV室外機型號"), (6, "VRV室外機台數")
        ]
        for col_idx, h_text in d3_headers:
            c = ws3.cell(row=4, column=col_idx, value=h_text)
            c.font = font_header; c.fill = fill_header; c.alignment = align_center; c.border = border_thin

        # D3-NET 計算結果資訊卡 (H, I, J 欄)
        ws3.merge_cells("H4:J4")
        card_header = ws3.cell(row=4, column=8, value="【D3-NET 通訊通道試算結果】")
        card_header.font = font_header; card_header.fill = PatternFill(start_color="0284C7", end_color="0284C7", fill_type="solid")
        card_header.alignment = align_center

        stat_labels = [
            ("VRV 室外機總台數 (上限 10台/Port)", s_out),
            ("總室內/全熱機數 (上限 64台/Port)", s_in),
            ("建議集中控制器 Port 數", f"{suggested_ports} Port")
        ]
        for s_idx, (lbl, val) in enumerate(stat_labels):
            r_stat = 5 + s_idx
            ws3.merge_cells(start_row=r_stat, start_column=8, end_row=r_stat, end_column=9)
            cl = ws3.cell(row=r_stat, column=8, value=lbl)
            cv = ws3.cell(row=r_stat, column=10, value=val)
            cl.font = font_bold; cl.fill = fill_card; cl.border = border_thin; cl.alignment = align_left
            cv.font = Font(name="微軟正黑體", size=11, bold=True, color="0284C7" if "Port" in str(val) else "0F172A")
            cv.fill = fill_card; cv.border = border_thin; cv.alignment = align_center

        # 填寫明細
        d3_max_rows = max(len(d3_in_table), len(d3_out_table), 1)
        for idx in range(d3_max_rows):
            r_idx = 5 + idx
            if idx < len(d3_in_table):
                c_m = ws3.cell(row=r_idx, column=2, value=d3_in_table[idx]["display_name"])
                c_q = ws3.cell(row=r_idx, column=3, value=d3_in_table[idx]["qty"])
                c_m.font = font_data; c_m.alignment = align_left; c_m.border = border_thin
                c_q.font = font_data; c_q.alignment = align_center; c_q.border = border_thin

            if idx < len(d3_out_table):
                c_m = ws3.cell(row=r_idx, column=5, value=d3_out_table[idx]["display_name"])
                c_q = ws3.cell(row=r_idx, column=6, value=d3_out_table[idx]["qty"])
                c_m.font = font_data; c_m.alignment = align_left; c_m.border = border_thin
                c_q.font = font_data; c_q.alignment = align_center; c_q.border = border_thin

        # D3-NET 合計列
        d3_tot_row = 5 + d3_max_rows
        ws3.cell(row=d3_tot_row, column=2, value="合計").font = font_bold
        ws3.cell(row=d3_tot_row, column=3, value=s_in).font = font_bold
        ws3.cell(row=d3_tot_row, column=5, value="合計").font = font_bold
        ws3.cell(row=d3_tot_row, column=6, value=s_out).font = font_bold

        for col_idx in [2, 3, 5, 6]:
            cell = ws3.cell(row=d3_tot_row, column=col_idx)
            cell.fill = fill_subtotal
            cell.border = border_total
            if col_idx in [3, 6]:
                cell.alignment = align_center

        # 自動調整欄寬 (自適應中文與英文)
        for ws in [ws_quote, ws1, ws2, ws3]:
            ws.column_dimensions['A'].width = 3
            for col in ws.columns:
                col_letter = get_column_letter(col[0].column)
                if col_letter == 'A':
                    continue
                max_len = 0
                for cell in col:
                    if cell.value:
                        val_str = str(cell.value)
                        # 中文字符權重 2.2，英數字 1.1
                        length = sum(2.2 if '\u4e00' <= char <= '\u9fff' else 1.1 for char in val_str)
                        if length > max_len:
                            max_len = length
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    @classmethod
    def _build_quotation_sheet(cls, wb, rooms_data, grouped_by_outdoor, hrv_items, joint_items, adapter_board_items, db_srv):
        font_header = Font(name="微軟正黑體", size=11, bold=True, color="FFFFFF")
        font_data = Font(name="微軟正黑體", size=10)
        font_bold = Font(name="微軟正黑體", size=10, bold=True)
        font_title = Font(name="微軟正黑體", size=14, bold=True, color="0F172A")
        font_section = Font(name="微軟正黑體", size=11, bold=True, color="0369A1")
        font_total = Font(name="微軟正黑體", size=12, bold=True, color="0369A1")

        fill_header = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        fill_subtotal = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        fill_section = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")

        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )
        border_total = Border(
            top=Side(style='thin', color='475569'),
            bottom=Side(style='double', color='0F172A')
        )

        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")

        ws_quote = wb.create_sheet(title="設備報價單", index=1)
        ws_quote.views.sheetView[0].showGridLines = True

        # --- 1. 彙整空調設備項目 (1對1 合併 / 1對多 拆開) ---
        equip_items = []
        item_counter_a = 1

        for sys_k, g_data in grouped_by_outdoor.items():
            out_m = (g_data.get("outdoor_model") or "").strip()
            out_q = int(g_data.get("outdoor_qty", 1))
            sys_name = g_data.get("sys_name", "空調系統")
            indoor_list = g_data.get("indoor_list", [])

            out_info = db_srv.get_outdoor_unit_info(out_m) or {}
            out_price = out_info.get("price")

            # 判斷是否為 1對1：sys_name 有 1對1 或室內機僅 1 款且外機非多聯/VRV
            is_one_to_one = ("1對1" in sys_name) or (len(indoor_list) == 1 and not any(m in out_m.upper() for m in ['2MX', '3MX', '4MX', '5MX', 'RXYQ', 'RSUYQ', 'RXQ']))

            if is_one_to_one and len(indoor_list) >= 1:
                in_item = indoor_list[0]
                in_m = in_item["model"]
                in_q = in_item["qty"]
                total_sets = max(out_q, in_q)
                
                pair_name = f"{out_m} / {in_m}"
                disp_sys = "RA 家用1對1" if "RA" in sys_name or out_m.startswith(("RX", "RK")) else ("SA 商用1對1" if "SA" in sys_name or "商用" in sys_name else "1對1空調系統")
                
                equip_items.append({
                    "item_code": f"A-{item_counter_a}",
                    "sys_cat": disp_sys,
                    "name": f"{disp_sys} ({pair_name})",
                    "qty": total_sets,
                    "unit": "組",
                    "unit_price": out_price,
                    "notes": "含室內機+室外機整組"
                })
                item_counter_a += 1
            else:
                # 1對多 (VRV 或 家用多聯)：室外機獨立、室內機獨立
                disp_sys = "VRV 系統" if "VRV" in sys_name or out_m.startswith(("RSUY", "RXY", "RXQ")) else "RA 家用多聯"
                
                if out_m and out_m != "-":
                    pwr_str = out_info.get("power_supply", "")
                    ut_str = out_info.get("unit_type", "")
                    notes_out = f"{ut_str} / {pwr_str}".strip(" /")
                    equip_items.append({
                        "item_code": f"A-{item_counter_a}",
                        "sys_cat": disp_sys,
                        "name": f"{disp_sys}室外機 ({out_m})",
                        "qty": out_q,
                        "unit": "台",
                        "unit_price": out_price,
                        "notes": notes_out or "室外機單機"
                    })
                    item_counter_a += 1

                in_model_counts = {}
                for in_item in indoor_list:
                    im = in_item["model"]
                    iq = in_item["qty"]
                    in_model_counts[im] = in_model_counts.get(im, 0) + iq

                for im, iq in in_model_counts.items():
                    in_info = db_srv.get_indoor_unit_info(im) or {}
                    in_price = in_info.get("price")
                    equip_items.append({
                        "item_code": f"A-{item_counter_a}",
                        "sys_cat": disp_sys,
                        "name": f"{disp_sys}室內機 ({im})",
                        "qty": iq,
                        "unit": "台",
                        "unit_price": in_price,
                        "notes": "室內機單機"
                    })
                    item_counter_a += 1

        # 全熱交換器 (若有)
        for hrv in (hrv_items or []):
            hm = hrv["model"]
            hq = hrv["qty"]
            equip_items.append({
                "item_code": f"A-{item_counter_a}",
                "sys_cat": "全熱交換系統",
                "name": f"大金全熱交換器 ({hm})",
                "qty": hq,
                "unit": "台",
                "unit_price": None,
                "notes": "換氣淨化"
            })
            item_counter_a += 1

        # --- 2. 彙整其他配件項目 ---
        accessory_items = []
        item_counter_b = 1

        # 有線遙控器 (VRV 與 SA 系統需額外選購)
        vrv_sa_count = 0
        for r in rooms_data:
            m_in = str(r.get("recommended_model") or r.get("indoor_model") or r.get("best_match_model") or "").strip().upper()
            sys_t = str(r.get("system_type") or r.get("system") or "").strip().upper()
            q_in = int(r.get("qty") or r.get("unit_count") or 1)
            if "VRV" in sys_t or m_in.startswith("FX") or "SA" in sys_t or m_in.startswith(("FBA", "FCA", "FAA", "FFA", "FHQ")):
                vrv_sa_count += q_in

        if vrv_sa_count > 0:
            accessory_items.append({
                "item_code": f"B-{item_counter_b}",
                "cat": "控制配件",
                "name": "液晶有線遙控器 (BRC1E63 / BRC1H61W)",
                "qty": vrv_sa_count,
                "unit": "個",
                "unit_price": None,
                "notes": "SA / VRV 室內機專用標準配置"
            })
            item_counter_b += 1

        # VRV 冷媒分歧管
        joint_counts = {}
        for j in (joint_items or []):
            jm = j["model"]
            joint_counts[jm] = joint_counts.get(jm, 0) + j.get("qty", 1)

        for jm, jq in joint_counts.items():
            accessory_items.append({
                "item_code": f"B-{item_counter_b}",
                "cat": "冷媒配件",
                "name": f"VRV 冷媒分歧管 ({jm})",
                "qty": jq,
                "unit": "套",
                "unit_price": None,
                "notes": "含原廠專用保溫材"
            })
            item_counter_b += 1

        # 查詢各室內機對應之轉接小P版、無線接收器/APP卡、集控轉接基板規則 (參照 EQUIPMENT_Data)
        acc_rules = cls.get_indoor_accessory_rules()

        # APP / 集中控制需求
        has_app = any("APP" in str(r.get("control_mode") or r.get("ctrl_mode") or "").upper() for r in rooms_data)
        has_central = any("集控" in str(r.get("control_mode") or r.get("ctrl_mode") or "") for r in rooms_data)

        # 🎯 APP 遠端控制配件精準對應 (參照 EQUIPMENT_Data 分頁之 轉接小P版 與 無線接收器)
        if has_app:
            app_receiver_counts = {}
            p_board_counts = {}
            for r in rooms_data:
                m_in = str(r.get("recommended_model") or r.get("indoor_model") or r.get("best_match_model") or "").strip().upper()
                q_in = int(r.get("qty") or r.get("unit_count") or 1)
                rule = acc_rules.get(m_in, {})

                # 1. 無線接收器 / APP 轉接卡 (Row 15)
                rec = rule.get("app_receiver")
                if rec and rec != "內建":
                    app_receiver_counts[rec] = app_receiver_counts.get(rec, 0) + q_in
                elif not rec and not any(k in m_in for k in ["內建", "FX"]):
                    app_receiver_counts["BRP072C42"] = app_receiver_counts.get("BRP072C42", 0) + q_in

                # 2. 轉接小P版 (Row 14)
                p_board = rule.get("adapter_board")
                if p_board:
                    p_board_counts[p_board] = p_board_counts.get(p_board, 0) + q_in

            for rec_m, rec_q in app_receiver_counts.items():
                accessory_items.append({
                    "cat": "控制配件",
                    "name": f"Daikin Mobile Controller APP 智慧遠端控制卡 ({rec_m})",
                    "qty": rec_q,
                    "unit": "個",
                    "unit_price": None,
                    "notes": "智慧手機雲端遠端開關與定時"
                })

            for pb_m, pb_q in p_board_counts.items():
                accessory_items.append({
                    "cat": "控制配件",
                    "name": f"原廠室內機轉接小P板 ({pb_m})",
                    "qty": pb_q,
                    "unit": "個",
                    "unit_price": None,
                    "notes": "搭配 APP 遠端控制卡專用介面基板"
                })

        # 🎯 集中控制需求配件精準對應 (參照 EQUIPMENT_Data 分頁之 集控轉接基板)
        if has_central:
            c_board_counts = {}
            for r in rooms_data:
                m_in = str(r.get("recommended_model") or r.get("indoor_model") or r.get("best_match_model") or "").strip().upper()
                q_in = int(r.get("qty") or r.get("unit_count") or 1)
                rule = acc_rules.get(m_in, {})
                c_board = rule.get("central_board")
                if c_board:
                    c_board_counts[c_board] = c_board_counts.get(c_board, 0) + q_in

            for cb_m, cb_q in c_board_counts.items():
                accessory_items.append({
                    "cat": "控制配件",
                    "name": f"集中控制轉接基板 ({cb_m})",
                    "qty": cb_q,
                    "unit": "個",
                    "unit_price": None,
                    "notes": "連接中央集中控制器專用轉接基板"
                })

            if not any("集中控制器" in it["name"] for it in accessory_items):
                accessory_items.append({
                    "cat": "控制配件",
                    "name": "大金空調中央集中控制器 (DCS302CA61)",
                    "qty": 1,
                    "unit": "台",
                    "unit_price": None,
                    "notes": "多功能中央集中控制盤"
                })

        # --- 3. 渲染報價單到工作表 ---
        ws_quote.cell(row=2, column=2, value="大金空調設備與工程配件報價清冊").font = font_title
        ws_quote.cell(row=2, column=2).alignment = align_left

        quote_headers = [
            (2, "系統類別"), (3, "設備項目與型號"),
            (4, "數量"), (5, "單位"), (6, "參考單價 (NT$)"),
            (7, "金額合計 (NT$)"), (8, "備註說明")
        ]
        for c_idx, h_txt in quote_headers:
            c = ws_quote.cell(row=4, column=c_idx, value=h_txt)
            c.font = font_header
            c.fill = fill_header
            c.alignment = align_center
            c.border = border_thin

        curr_row = 5

        # 一、空調設備
        sec1_cell = ws_quote.cell(row=curr_row, column=2, value="一、空調設備")
        sec1_cell.font = font_section
        for col_i in range(2, 9):
            ws_quote.cell(row=curr_row, column=col_i).fill = fill_section
            ws_quote.cell(row=curr_row, column=col_i).border = border_thin
        curr_row += 1

        equip_start = curr_row
        if not equip_items:
            ws_quote.cell(row=curr_row, column=3, value="無選定設備").font = font_data
            curr_row += 1
            equip_end = equip_start
        else:
            for it in equip_items:
                ws_quote.cell(row=curr_row, column=2, value=it["sys_cat"]).alignment = align_center
                ws_quote.cell(row=curr_row, column=3, value=it["name"]).alignment = align_left
                ws_quote.cell(row=curr_row, column=4, value=it["qty"]).alignment = align_center
                ws_quote.cell(row=curr_row, column=5, value=it["unit"]).alignment = align_center

                c_p = ws_quote.cell(row=curr_row, column=6)
                if it["unit_price"] is not None:
                    c_p.value = it["unit_price"]
                c_p.number_format = '#,##0'
                c_p.alignment = align_right

                c_a = ws_quote.cell(row=curr_row, column=7, value=f"=D{curr_row}*F{curr_row}")
                c_a.number_format = '#,##0'
                c_a.alignment = align_right

                ws_quote.cell(row=curr_row, column=8, value=it["notes"]).alignment = align_left

                for col_i in range(2, 9):
                    ws_quote.cell(row=curr_row, column=col_i).font = font_data
                    ws_quote.cell(row=curr_row, column=col_i).border = border_thin
                curr_row += 1
            equip_end = curr_row - 1

        # 空調設備小計
        sub_a_row = curr_row
        ws_quote.cell(row=curr_row, column=2, value="【空調設備小計】").font = font_bold
        c_sub_a = ws_quote.cell(row=curr_row, column=7, value=f"=SUM(G{equip_start}:G{equip_end})")
        c_sub_a.font = font_bold
        c_sub_a.number_format = '#,##0'
        c_sub_a.alignment = align_right
        for col_i in range(2, 9):
            c = ws_quote.cell(row=curr_row, column=col_i)
            c.fill = fill_subtotal
            c.border = border_total
        curr_row += 2

        # 二、其他配件
        sec2_cell = ws_quote.cell(row=curr_row, column=2, value="二、其他配件")
        sec2_cell.font = font_section
        for col_i in range(2, 9):
            ws_quote.cell(row=curr_row, column=col_i).fill = fill_section
            ws_quote.cell(row=curr_row, column=col_i).border = border_thin
        curr_row += 1

        acc_start = curr_row
        if not accessory_items:
            ws_quote.cell(row=curr_row, column=3, value="標準基本配備 (無額外配件)").font = font_data
            curr_row += 1
            acc_end = acc_start
        else:
            for it in accessory_items:
                ws_quote.cell(row=curr_row, column=2, value=it["cat"]).alignment = align_center
                ws_quote.cell(row=curr_row, column=3, value=it["name"]).alignment = align_left
                ws_quote.cell(row=curr_row, column=4, value=it["qty"]).alignment = align_center
                ws_quote.cell(row=curr_row, column=5, value=it["unit"]).alignment = align_center

                c_p = ws_quote.cell(row=curr_row, column=6)
                if it["unit_price"] is not None:
                    c_p.value = it["unit_price"]
                c_p.number_format = '#,##0'
                c_p.alignment = align_right

                c_a = ws_quote.cell(row=curr_row, column=7, value=f"=D{curr_row}*F{curr_row}")
                c_a.number_format = '#,##0'
                c_a.alignment = align_right

                ws_quote.cell(row=curr_row, column=8, value=it["notes"]).alignment = align_left

                for col_i in range(2, 9):
                    ws_quote.cell(row=curr_row, column=col_i).font = font_data
                    ws_quote.cell(row=curr_row, column=col_i).border = border_thin
                curr_row += 1
            acc_end = curr_row - 1

        # 其他配件小計
        sub_b_row = curr_row
        ws_quote.cell(row=curr_row, column=2, value="【其他配件小計】").font = font_bold
        c_sub_b = ws_quote.cell(row=curr_row, column=7, value=f"=SUM(G{acc_start}:G{acc_end})")
        c_sub_b.font = font_bold
        c_sub_b.number_format = '#,##0'
        c_sub_b.alignment = align_right
        for col_i in range(2, 9):
            c = ws_quote.cell(row=curr_row, column=col_i)
            c.fill = fill_subtotal
            c.border = border_total
        curr_row += 2

        # 三、工程總計
        untaxed_row = curr_row
        ws_quote.cell(row=curr_row, column=2, value="【全案設備工程未稅總計】").font = font_bold
        c_untaxed = ws_quote.cell(row=curr_row, column=7, value=f"=G{sub_a_row}+G{sub_b_row}")
        c_untaxed.font = font_bold
        c_untaxed.number_format = '#,##0'
        c_untaxed.alignment = align_right
        for col_i in range(2, 9):
            c = ws_quote.cell(row=curr_row, column=col_i)
            c.fill = fill_subtotal
            c.border = border_thin
        curr_row += 1

        tax_row = curr_row
        ws_quote.cell(row=curr_row, column=2, value="【營業稅 (5%)】").font = font_bold
        c_tax = ws_quote.cell(row=curr_row, column=7, value=f"=ROUND(G{untaxed_row}*0.05, 0)")
        c_tax.font = font_bold
        c_tax.number_format = '#,##0'
        c_tax.alignment = align_right
        for col_i in range(2, 9):
            c = ws_quote.cell(row=curr_row, column=col_i)
            c.fill = fill_subtotal
            c.border = border_thin
        curr_row += 1

        final_row = curr_row
        ws_quote.cell(row=curr_row, column=2, value="【全案設備工程含稅總價】").font = font_total
        c_final = ws_quote.cell(row=curr_row, column=7, value=f"=G{untaxed_row}+G{tax_row}")
        c_final.font = font_total
        c_final.number_format = '#,##0'
        c_final.alignment = align_right
        for col_i in range(2, 9):
            c = ws_quote.cell(row=curr_row, column=col_i)
            c.fill = fill_section
            c.border = border_total

        ws_quote.column_dimensions['A'].width = 4
        ws_quote.column_dimensions['B'].width = 16
        ws_quote.column_dimensions['C'].width = 38
        ws_quote.column_dimensions['D'].width = 10
        ws_quote.column_dimensions['E'].width = 10
        ws_quote.column_dimensions['F'].width = 18
        ws_quote.column_dimensions['G'].width = 20
        ws_quote.column_dimensions['H'].width = 28

        return ws_quote
