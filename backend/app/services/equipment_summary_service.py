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

        # 🎯 收集轉接小P板、無線接收器、集控轉接基板統計清單
        adapter_board_items = []
        try:
            from app.services.equipment_db_service import EquipmentDBService
            db_srv = EquipmentDBService.get_instance()
            for r in rooms_data:
                m_in = str(r.get("recommended_model") or r.get("indoor_model") or r.get("best_match_model") or "").strip()
                q_in = int(r.get("qty") or r.get("unit_count") or 1)
                ctrl_mode = str(r.get("control_mode") or r.get("ctrl_mode") or "").strip()
                if not m_in or m_in in ["-", "NONE", ""]:
                    continue
                in_spec = db_srv.get_indoor_unit_info(m_in) or {}
                p_board = in_spec.get("adapter_p_board", "-")
                w_recv = in_spec.get("wireless_receiver", "-")
                c_board = in_spec.get("central_adapter_board", "-")

                # 若選 APP 控制
                if "APP" in ctrl_mode.upper():
                    if p_board and p_board not in ["-", "內建", "None", ""]:
                        adapter_board_items.append({"model": f"轉接小P板 ({p_board})", "qty": q_in, "sys": "控制介面"})
                    if w_recv and w_recv not in ["-", "內建", "None", ""]:
                        adapter_board_items.append({"model": f"無線接收器 ({w_recv})", "qty": q_in, "sys": "控制介面"})
                # 若選集控控制
                if "集控" in ctrl_mode or "CENTRAL" in ctrl_mode.upper():
                    if p_board and p_board not in ["-", "內建", "None", ""]:
                        adapter_board_items.append({"model": f"轉接小P板 ({p_board})", "qty": q_in, "sys": "控制介面"})
                    if c_board and c_board not in ["-", "None", ""]:
                        adapter_board_items.append({"model": f"集控轉接基板 ({c_board})", "qty": q_in, "sys": "控制介面"})
        except Exception as act_err:
            logger.warning(f"Failed to extract control accessories: {act_err}")

        # 🎯 利用 DaikinHVACCalculator 獨立運算管徑與分歧頭
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
                for in_item in g_data["indoor_list"]:
                    in_m = in_item["model"]
                    in_q = in_item["qty"]
                    is_ra_unit = any(k in in_m.upper() for k in ['FTX', 'CTX', 'FTHF', 'FDXV'])
                    n_type = 'ra' if is_ra_unit else 'vrv'
                    c_idx = pipe_calc.extract_capacity_index(in_m)
                    child_nodes.append(HVACNode(n_type, in_m, capacity=c_idx, qty=in_q, model=in_m))
                
                # 自動 BP 箱分組 (每 3 台 RA 壁掛聚類)
                grouped_children = pipe_calc.build_system_with_bp_boxes(child_nodes)
                for ch in grouped_children:
                    root_node.add_child(ch)
                
                # 遞迴運算管徑與分歧頭
                pipe_calc.evaluate_tree(root_node, is_root=True)
                g_data["evaluated_tree"] = root_node

                # 提取分歧頭進行數量清點
                def collect_joints(node: HVACNode):
                    if node.joint_model:
                        for j_single in node.joint_model.split('+'):
                            joint_items.append({"model": j_single.strip(), "qty": 1, "sys": "冷媒分歧頭"})
                    for c_node in node.children:
                        collect_joints(c_node)
                collect_joints(root_node)
        except Exception as pipe_err:
            logger.warning(f"Failed to evaluate pipe sizing: {pipe_err}")

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
        for ws in [ws1, ws2, ws3]:
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
