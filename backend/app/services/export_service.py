import os
import io
import logging
from typing import List, Dict, Any
import openpyxl

from app.config import settings

logger = logging.getLogger(__name__)

# 🎯 大金全熱交換器規格資料庫 (參照 EQUIPMENT_Data 之 HRV 分頁)
HRV_UNITS_DB = [
    {"model": "VAM150HVLT", "airflow": 150, "power_supply": "1φ, 220V, 60Hz", "power_kw": 0.06, "dimensions": "278×551×810", "price": 34600.0, "pm25_filter_model": "BAFH510A250", "pm25_filter_price": 2500.0},
    {"model": "VAM250HVLT", "airflow": 250, "power_supply": "1φ, 220V, 60Hz", "power_kw": 0.06, "dimensions": "278×551×810", "price": 36800.0, "pm25_filter_model": "BAFH510A250", "pm25_filter_price": 2500.0},
    {"model": "VAM350HVLT", "airflow": 350, "power_supply": "1φ, 220V, 60Hz", "power_kw": 0.12, "dimensions": "306×800×879", "price": 42700.0, "pm25_filter_model": "BAFH510A350", "pm25_filter_price": 3200.0},
    {"model": "VAM500HVLT", "airflow": 500, "power_supply": "1φ, 220V, 60Hz", "power_kw": 0.20, "dimensions": "338×832×973", "price": 45800.0, "pm25_filter_model": "BAFH510A650", "pm25_filter_price": 5500.0},
    {"model": "VAM650HVLT", "airflow": 650, "power_supply": "1φ, 220V, 60Hz", "power_kw": 0.34, "dimensions": "338×832×973", "price": 51800.0, "pm25_filter_model": "BAFH510A650", "pm25_filter_price": 5500.0},
    {"model": "VAM800HVLT", "airflow": 800, "power_supply": "1φ, 220V, 60Hz", "power_kw": 0.38, "dimensions": "387×1,012×1,110", "price": 69100.0, "pm25_filter_model": "BAFH510A2000", "pm25_filter_price": 6500.0},
    {"model": "VAM1000HVLT", "airflow": 1000, "power_supply": "1φ, 220V, 60Hz", "power_kw": 0.38, "dimensions": "387×1,012×1,110", "price": 81300.0, "pm25_filter_model": "BAFH510A2000", "pm25_filter_price": 6500.0},
    {"model": "VAM1500HVLT", "airflow": 1500, "power_supply": "1φ, 220V, 60Hz", "power_kw": 0.76, "dimensions": "785×1,012×1,110", "price": 122700.0, "pm25_filter_model": "BAFH510A2000+BAFH510A2000", "pm25_filter_price": 13000.0},
    {"model": "VAM2000HVLT", "airflow": 2000, "power_supply": "1φ, 220V, 60Hz", "power_kw": 0.76, "dimensions": "785×1,012×1,110", "price": 150000.0, "pm25_filter_model": "BAFH510A2000+BAFH510A2000", "pm25_filter_price": 13000.0},
]

class ExportService:
    @classmethod
    def get_template_path(cls) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        root_dir = os.path.dirname(base_dir)
        candidates = [
            os.path.join(base_dir, "product_database", settings.TEMPLATE_NAME),
            os.path.join(base_dir, settings.TEMPLATE_NAME),
            os.path.join(root_dir, settings.TEMPLATE_NAME),
            os.path.join(root_dir, "backend", "product_database", settings.TEMPLATE_NAME),
            os.path.abspath("backend/product_database/選機表-.xlsx"),
            os.path.abspath("product_database/選機表-.xlsx"),
            os.path.abspath("選機表-.xlsx")
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return candidates[0]

    @classmethod
    def generate_excel_report(cls, rooms_data: List[Dict[str, Any]], outdoor_groups: List[Dict[str, Any]] = None, selected_controllers: List[str] = None, custom_piping_trees: Dict[str, Any] = None, custom_piping_diagram_images: Dict[str, str] = None, hrv_config: Dict[str, Any] = None) -> io.BytesIO:
        """
        Loads the template Excel sheet '選機表-.xlsx', maps properties,
        and performs vertical cell merging (rowspan) for outdoor unit cards.
        """
        template_path = cls.get_template_path()
        
        if not os.path.exists(template_path):
            logger.warning(f"Excel template file {settings.TEMPLATE_NAME} not found at {template_path}. Generating simple output.")
            return cls._generate_fallback_excel(rooms_data)
            
        try:
            wb = openpyxl.load_workbook(template_path)
            ws = wb.active
            
            from openpyxl.styles import Alignment
            align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
            
            start_row = settings.START_ROW
            
            from app.services.equipment_db_service import EquipmentDBService
            db_service = EquipmentDBService.get_instance()

            # 🎯 核心規格：flat_rows_to_render 嚴格為全場勾選之選定空間 (rooms_data)，不重複，不上贅列！
            flat_rows_to_render = rooms_data or []
            group_spans = [] # 室外機併機縱向跨列合併描述

            # 🎯 計算全熱交換器選型與各空間規劃數據 (EQUIPMENT_Data HRV 分頁)
            import math
            hrv_cfg = hrv_config or {}
            is_hrv_enabled = bool(hrv_cfg.get("enabled", True))
            raw_sel = hrv_cfg.get("selected_indices")
            has_cleared = bool(hrv_cfg.get("has_cleared", False))

            # 🎯 若使用者未勾選啟用全熱、已清空或選擇不選全熱，則徹底不啟用全熱計算
            if not is_hrv_enabled or has_cleared or raw_sel == []:
                hrv_sel_set = set()
            elif raw_sel is not None and len(raw_sel) > 0:
                hrv_sel_set = set(raw_sel)
            else:
                hrv_sel_set = set()  # 預設不啟用全熱，避免非預期自動全選
            basis_map = hrv_cfg.get("airflow_basis_map") or {}
            people_map = hrv_cfg.get("people_map") or {}

            def _resolve_ppl(idx: int, area_m2: float) -> int:
                raw = people_map.get(str(idx), people_map.get(idx))
                try:
                    n = int(raw)
                    if n >= 1:
                        return n
                except (TypeError, ValueError):
                    pass
                return math.ceil(area_m2 / 5.0) if area_m2 > 0 else 1

            has_pm25 = bool(hrv_cfg.get("has_pm25", False))

            total_hrv_airflow = 0
            if hrv_sel_set:
                for s_idx, r in enumerate(flat_rows_to_render):
                    a_m2 = float(r.get("area_m2") or 0.0)
                    if a_m2 <= 0 and float(r.get("area_ping") or 0.0) > 0:
                        a_m2 = float(r.get("area_ping")) / 0.3025
                    ppl = _resolve_ppl(s_idx, a_m2)
                    b_val = float(basis_map.get(str(s_idx), basis_map.get(s_idx, 30.0)))
                    if s_idx in hrv_sel_set:
                        total_hrv_airflow += int(ppl * b_val)

            matched_hrv = None
            if total_hrv_airflow > 0:
                for item in sorted(HRV_UNITS_DB, key=lambda x: x["airflow"]):
                    if item["airflow"] >= total_hrv_airflow:
                        matched_hrv = item
                        break
                if not matched_hrv and HRV_UNITS_DB:
                    matched_hrv = HRV_UNITS_DB[-1]

            # 🎯 掃描連續具備相同 outdoorGroupId 之列進行縱向跨列合併
            i = 0
            while i < len(flat_rows_to_render):
                room = flat_rows_to_render[i]
                g_id = room.get("outdoorGroupId") or room.get("outdoor_group_id") or room.get("group_id")
                
                if g_id:
                    j = i
                    while j + 1 < len(flat_rows_to_render) and (flat_rows_to_render[j + 1].get("outdoorGroupId") or flat_rows_to_render[j + 1].get("outdoor_group_id") or flat_rows_to_render[j + 1].get("group_id")) == g_id:
                        j += 1
                    
                    s_r = start_row + i
                    e_r = start_row + j
                    group_spaces = flat_rows_to_render[i:j+1]
                    
                    if e_r > s_r: # 2 台以上空間合併
                        for s in group_spaces:
                            s["_in_group"] = True
                            
                        matched_g = next((g for g in (outdoor_groups or []) if g.get("id") == g_id or g.get("group_id") == g_id), None)
                        out_model = str(matched_g.get("outdoor_model") if matched_g else room.get("outdoor_model", "")).strip()
                        out_qty = int(matched_g.get("outdoor_qty", 1) if matched_g else room.get("outdoor_qty", 1))
                        
                        sum_indoor_kw = sum(float(s.get("indoor_capacity_kw", s.get("cap_kw", 0.0))) * int(s.get("qty", s.get("unit_count", 1))) for s in group_spaces)
                        outdoor_info = db_service.get_outdoor_unit_info(out_model)
                        out_kw = float(matched_g.get("outdoor_cap_kw", 0.0)) if matched_g else (float(outdoor_info.get("cap_kw", 0.0)) if outdoor_info else 0.0)
                        
                        conn_ratio = round((sum_indoor_kw / out_kw) * 100, 1) if out_kw > 0 else 0.0
                        conn_ratio_str = f"{conn_ratio}%" if out_kw > 0 else "-"
                        
                        group_is_ra = any(
                            str(s.get("series", "")).strip().upper() == "RA"
                            or "RA" in str(s.get("system_type", s.get("system", ""))).strip().upper()
                            or str(s.get("recommended_model") or s.get("indoor_model") or "").upper().startswith(("FTX", "CTX"))
                            or out_model.upper().startswith(("2MX", "3MX", "4MX", "5MX", "RX"))
                            for s in group_spaces
                        )
                        
                        group_spans.append({
                            "start_row": s_r,
                            "end_row": e_r,
                            "outdoor_model": out_model,
                            "outdoor_qty": out_qty,
                            "conn_ratio_str": conn_ratio_str,
                            "outdoor_info": outdoor_info,
                            "fallback_cap_kw": out_kw,
                            "is_ra": group_is_ra,
                            "system_type": "RA" if group_is_ra else "VRV"
                        })
                        i = j + 1
                    else:
                        room["_in_group"] = False
                        i += 1
                else:
                    room["_in_group"] = False
                    i += 1

            # 🎯 動態偵測官方底稿中原本預設的空間列數（預設為 49 列，從第 9 列至第 57 列）
            template_rows = 0
            for r in range(start_row, ws.max_row + 1):
                if ws.cell(row=r, column=9).value or ws.cell(row=r, column=33).value:
                    template_rows += 1
                else:
                    break
            if template_rows == 0:
                template_rows = settings.TEMPLATE_ROWS or 49

            actual_count = len(flat_rows_to_render)
            if actual_count > template_rows:
                insert_count = actual_count - template_rows
                ws.insert_rows(start_row + template_rows, insert_count)
                for r_offset in range(insert_count):
                    target_row = start_row + template_rows + r_offset
                    for c in range(1, ws.max_column + 1):
                        ws.cell(row=target_row, column=c)._style = ws.cell(row=start_row, column=c)._style
            elif actual_count < template_rows:
                for m in list(ws.merged_cells.ranges):
                    if m.min_row > start_row + actual_count - 1:
                        ws.merged_cells.remove(m)
                extra_rows = ws.max_row - (start_row + actual_count) + 1
                if extra_rows > 0:
                    ws.delete_rows(start_row + actual_count, extra_rows)
                        
            # Write rooms data
            for i, room in enumerate(flat_rows_to_render):
                row_idx = start_row + i
                
                # 🎯 空間名稱 (室名)：優先取得有文字的名稱，確保絕不為空白
                name = str(room.get("space_name") or room.get("room_name") or room.get("name") or "").strip()
                if not name:
                    name = f"空間 {i + 1}"
                
                # 🎯 面積 (㎡) 與 坪數 (P)：自動雙向補全與換算
                area_m2 = float(room.get("area_m2") or 0.0)
                raw_ping = room.get("area_ping") or room.get("ping_val") or room.get("ping")
                ping_val = float(raw_ping) if raw_ping is not None and float(raw_ping) > 0 else (round(area_m2 * 0.3025, 2) if area_m2 > 0 else 0.0)
                
                # 🎯 每坪負荷基準 (kcal/hr/坪)
                final_suggested_kcal_per_ping = float(room.get("calc_basis") or room.get("final_suggested_kcal_per_ping") or room.get("base_suggested_load") or 600.0)
                kw_per_ping = round(final_suggested_kcal_per_ping / 860.0, 2)
                
                # 🎯 總熱負荷 kcal/hr 與 kW
                raw_total_kcal = room.get("total_cooling_load_kcal") or room.get("total_cooling_demand") or room.get("total_load_kcal")
                total_load_kcal = float(raw_total_kcal) if raw_total_kcal is not None and float(raw_total_kcal) > 0 else round(ping_val * final_suggested_kcal_per_ping)
                
                raw_total_kw = room.get("total_load_kw")
                total_load_kw = round(float(raw_total_kw), 1) if raw_total_kw is not None and float(raw_total_kw) > 0 else round(total_load_kcal / 860.0, 1)
                
                # 🎯 室內機型號
                matched_model = str(room.get("recommended_model") or room.get("indoor_model") or room.get("best_match_model") or "").strip()
                matched_upper = matched_model.upper()

                series_val = str(room.get("series", "")).strip().upper()
                sys_raw = str(room.get("system_type", room.get("system", ""))).strip().upper()
                
                # 🎯 嚴謹判斷是否為 RA 系統 (家用壁掛/家用多聯)
                # 絕對防護：凡室內機為大金 VRV (FX 開頭) 或系統/系列為 VRV 者，絕不可誤判為 RA！
                is_vrv_in = matched_upper.startswith("FX") or ("VRV" in sys_raw) or (series_val == "VRV")
                out_m_upper = str(room.get("outdoor_model", "")).upper()
                is_ra_outdoor = (
                    out_m_upper.startswith(("2MX", "3MX", "4MX", "5MX"))
                    or (out_m_upper.startswith("RX") and not out_m_upper.startswith(("RXYQ", "RXQ", "RXYMQ", "RXMQ", "RWEYQ")))
                )
                is_ra = (not is_vrv_in) and (
                    series_val == "RA"
                    or "RA" in sys_raw
                    or matched_upper.startswith(("FTX", "FTK", "FTV", "CTK", "CTX", "FDX", "CDX", "FVX", "FLX"))
                    or str(room.get("indoor_type", "")).find("壁掛") != -1
                    or is_ra_outdoor
                )
                system_type = "RA" if is_ra else ("VRV" if (is_vrv_in or matched_upper.startswith("FX")) else ("SA" if ("SA" in sys_raw or matched_upper.startswith(("FBA", "FCQ", "FHQ"))) else "VRV"))
                
                # 🎯 台數
                qty = int(room.get("qty") or room.get("unit_count") or 1)
                
                # 🎯 載入室內機 EQUIPMENT_Data 規格資訊
                indoor_info = db_service.get_indoor_unit_info(matched_model)
                
                # 🎯 室內機冷房能力 (kW 與 kcal/hr)
                raw_cap_kw = room.get("cap_kw") or room.get("indoor_capacity_kw")
                cap_kw = float(raw_cap_kw) if raw_cap_kw is not None and float(raw_cap_kw) > 0 else (float(indoor_info.get("cap_kw", 0.0)) if indoor_info else 0.0)
                
                raw_cap_kcal = room.get("indoor_capacity_kcal")
                cap_kcal = float(raw_cap_kcal) if raw_cap_kcal is not None and float(raw_cap_kcal) > 0 else round(cap_kw * 860.0, 1)
                
                # 🎯 經理指定室內機電源判斷規則：
                # 只有室內機為 VRV 系統，或是商用 1 對 1 的風管型 (型號是 FBA) 時會需要使用獨立電源 (1φ, 220V, 60Hz)，
                # 其餘的室內機皆使用外機供電，所以在室內機的電源欄位中以 "-" 標示即可。
                if "VRV" in system_type or matched_upper.startswith("FX") or matched_upper.startswith("FBA"):
                    power_supply = "1φ, 220V, 60Hz"
                else:
                    power_supply = "-"
                    
                # 🎯 標稱能力 (能力指數)：僅在 VRV 系統時存在與填寫，RA (家用) / SA (商用) 系統統一為 "-"
                if not is_ra and ("VRV" in system_type or is_vrv_in):
                    raw_nom = indoor_info.get("nominal_cap") if indoor_info else None
                    if not raw_nom or str(raw_nom).strip() in ["-", "None", ""]:
                        import re
                        m_cap = re.search(r"FX[A-Z]+(\d+)", matched_upper)
                        if m_cap:
                            raw_nom = int(m_cap.group(1))
                    if raw_nom is not None and str(raw_nom).strip() not in ["-", "None", ""]:
                        try:
                            if "." in str(raw_nom):
                                nominal_cap_val = float(raw_nom)
                            else:
                                nominal_cap_val = int(raw_nom)
                        except (ValueError, TypeError):
                            nominal_cap_val = str(raw_nom).strip()
                    else:
                        nominal_cap_val = cap_kw
                else:
                    nominal_cap_val = "-"

                # 🎯 經理指示 1：家用壁掛式 (RA系統) 無標稱能力和耗電量數值，維持 "-" 即可
                if is_ra:
                    nominal_cap_val = "-"
                    power_consumption_kw = "-"
                    indoor_current_a = "-"
                else:
                    power_consumption_kw = room.get("power_consumption_kw") if room.get("power_consumption_kw") and room.get("power_consumption_kw") != "-" else (indoor_info.get("power_consumption_kw", "-") if indoor_info else "-")
                    indoor_current_a = indoor_info.get("mca", "-") if indoor_info else "-"

                dimensions = room.get("dimensions") if room.get("dimensions") and room.get("dimensions") != "-" else (indoor_info.get("dimensions", "-") if indoor_info else "-")

                # Write to exact column mappings (Aligned with user screenshot)
                ws.cell(row=row_idx, column=settings.NAME_COL).value = name             # D: 室名
                ws.cell(row=row_idx, column=settings.AREA_COL).value = area_m2          # E: 面積 ㎡
                ws.cell(row=row_idx, column=settings.PING_COL).value = ping_val         # F: 坪數 P
                ws.cell(row=row_idx, column=settings.LOAD_H_COL).value = final_suggested_kcal_per_ping # H: 建議負荷 (kcal/hr/坪)
                
                # 🎯 補足 Col I 與 Col J 公式與數值，確保絕不出現空白
                cell_i = ws.cell(row=row_idx, column=settings.LOAD_I_COL)               # I: 每坪建議負荷值 (kcal/hr/㎡)
                cell_i.value = f"=H{row_idx}*0.3025"
                cell_i.number_format = '0'
                
                cell_j = ws.cell(row=row_idx, column=settings.LOAD_J_COL)               # J: 每坪建議負荷值 (W/㎡)
                cell_j.value = f"=H{row_idx}/0.86*0.3025"
                cell_j.number_format = '#,##0.00_ '

                cell_k = ws.cell(row=row_idx, column=settings.LOAD_K_COL)
                cell_k.value = kw_per_ping
                cell_k.number_format = '0.00'
                
                cell_l = ws.cell(row=row_idx, column=settings.LOAD_L_COL)
                cell_l.value = total_load_kw   # L: 總負荷 kW
                cell_l.number_format = '0.0'
                ws.cell(row=row_idx, column=settings.LOAD_M_COL).value = total_load_kcal # M: 總負荷 kcal
                
                # 🎯 室內機修正欄位 (N ~ V)
                ws.cell(row=row_idx, column=14).value = matched_model            # N: 室內機型號
                ws.cell(row=row_idx, column=15).value = qty                      # O: 室內機台數
                ws.cell(row=row_idx, column=16).value = cap_kcal                 # P: 冷房能力 (kcal/hr)
                ws.cell(row=row_idx, column=17).value = cap_kw                   # Q: 冷房能力 (kW)
                ws.cell(row=row_idx, column=18).value = nominal_cap_val          # R: 標稱能力 (僅 VRV 填寫能力指數，RA/SA 為 -)
                ws.cell(row=row_idx, column=19).value = power_supply             # S: 電源
                ws.cell(row=row_idx, column=20).value = power_consumption_kw     # T: 單台耗電量 (kW)
                ws.cell(row=row_idx, column=21).value = indoor_current_a         # U: 單台最大電流 (A)
                ws.cell(row=row_idx, column=22).value = dimensions               # V: 尺寸 mm (H×W×D)
                
                ws.cell(row=row_idx, column=settings.TOTAL_KCAL_W_COL).value = float(qty * cap_kcal)
                ws.cell(row=row_idx, column=settings.TOTAL_KW_X_COL).value = float(qty * cap_kw)
                
                # 🎯 標稱能力小計 (Col Y, 25)：僅 VRV 有能力指數小計，其餘系統 (RA/SA) 維持 "-"
                cell_y = ws.cell(row=row_idx, column=settings.SUBTOTAL_NOMINAL_Y_COL)
                if not is_ra and "VRV" in system_type and isinstance(nominal_cap_val, (int, float)):
                    cell_y.value = f"=R{row_idx}*O{row_idx}"
                    cell_y.number_format = 'General'
                else:
                    cell_y.value = "-"

                # 🎯 耗電量小計 kW (Col Z, 26)：RA (家用壁掛) 或無耗電量者維持 "-"
                cell_z = ws.cell(row=row_idx, column=settings.SUBTOTAL_POWER_Z_COL)
                if not is_ra and power_consumption_kw not in ["-", "", "None", None]:
                    try:
                        pwr_f = float(power_consumption_kw)
                        cell_z.value = f"=O{row_idx}*T{row_idx}"
                        cell_z.number_format = '0.0'
                    except (ValueError, TypeError):
                        cell_z.value = "-"
                else:
                    cell_z.value = "-"

                # 🎯 每坪平均負荷值 (Col AA, 27) (kcal/hr/㎡)
                cell_aa = ws.cell(row=row_idx, column=settings.PER_M2_KCAL_AA_COL)
                cell_aa.value = f"=AB{row_idx}*0.3025"
                cell_aa.number_format = '0'

                if ping_val > 0:
                    ws.cell(row=row_idx, column=settings.PER_PING_KCAL_AB_COL).value = int(round(cap_kcal / ping_val, 0))
                    ws.cell(row=row_idx, column=settings.PER_PING_KW_AC_COL).value = round(cap_kw / ping_val, 1)
                
                if (qty * cap_kw) > 0:
                    ws.cell(row=row_idx, column=settings.PING_PER_USRT_AD_COL).value = round(ping_val / ((qty * cap_kw) / 3.516), 1)

                # 🎯 單機/未分組空間之室外機欄位直接填入 (AE ~ AO)
                if not room.get("_in_group", False):
                    out_model = room.get("outdoor_model", "").strip()
                    if not out_model:
                        # 嘗試由內機型號或衍生名推導
                        if matched_upper.startswith("FTHF"):
                            out_model = "RHF" + matched_upper[4:]
                        elif matched_upper.startswith("FTXM"):
                            if "80" in matched_upper:
                                out_model = "RXM80ZVLT"
                            elif "90" in matched_upper:
                                out_model = "RXM90ZVLT"
                            else:
                                out_model = "RXM" + matched_upper[4:]
                        elif matched_upper.startswith("FTXV"):
                            if "XVLT" in matched_upper:
                                out_model = "RXM" + matched_upper[4:]
                            else:
                                out_model = "RXV" + matched_upper[4:]
                        elif matched_upper.startswith("FDXV"):
                            for c in ["22", "28", "36", "41", "50", "60", "71"]:
                                if c in matched_upper:
                                    out_model = f"RXV{c}ZVLT"
                                    break
                            if not out_model:
                                out_model = "RXV50ZVLT"
                        elif matched_upper.startswith("FBA"):
                            out_model = matched_upper.replace("FBA", "RZA")
                        else:
                            out_model = matched_upper
                            
                    out_info = db_service.get_outdoor_unit_info(out_model)
                    if not out_info and out_model:
                        out_info = db_service.get_outdoor_unit_info(out_model.strip().upper())

                    out_cap_kw = float(out_info.get("cap_kw", cap_kw)) if out_info else cap_kw
                    out_cap_kcal = round(out_cap_kw * 860.0, 1) if out_cap_kw > 0 else "-"
                    out_nominal = out_info.get("nominal_cap", "-") if (out_info and "VRV" in system_type) else "-"
                    out_pwr_con = out_info.get("power_consumption_kw", "-") if out_info else "-"
                    out_pwr_sup = out_info.get("power_supply", "-") if out_info else "-"
                    out_mca = out_info.get("mca", "-") if out_info else "-"
                    out_mfa = out_info.get("mfa", "-") if out_info else "-"
                    out_dim = out_info.get("dimensions", "-") if out_info else "-"

                    ws.cell(row=row_idx, column=31).value = out_model if out_model else "-"   # AE: 室外機型號 (第4列)
                    ws.cell(row=row_idx, column=32).value = int(room.get("outdoor_qty", 1))   # AF: 室外機台數 (以選型台數為主)
                    ws.cell(row=row_idx, column=33).value = out_cap_kcal                     # AG: 冷房能力 (kcal/hr)
                    ws.cell(row=row_idx, column=34).value = out_cap_kw                       # AH: 冷房能力 (kW) (第5列)
                    ws.cell(row=row_idx, column=35).value = out_nominal                      # AI: 標稱能力 (僅 VRV 填寫能力指數，RA/SA 為 -)
                    
                    # 🎯 經理指示 2：RA 系統不需要提供連結率，請維持 "-" 即可
                    ws.cell(row=row_idx, column=36).value = "-" if (is_ra or "RA" in system_type) else "100%"

                    # 🎯 經理指示 3：提供室外機耗電量、電源、電路最大電流、保險絲最大電流及尺寸 (參照 EQUIPMENT_Data)
                    cell_ak = ws.cell(row=row_idx, column=37)
                    try:
                        cell_ak.value = float(out_pwr_con)
                        cell_ak.number_format = '0.00'
                    except (ValueError, TypeError):
                        cell_ak.value = out_pwr_con

                    ws.cell(row=row_idx, column=38).value = out_pwr_sup

                    cell_am = ws.cell(row=row_idx, column=39)
                    try:
                        cell_am.value = float(out_mca)
                        cell_am.number_format = '0.0'
                    except (ValueError, TypeError):
                        cell_am.value = out_mca

                    cell_an = ws.cell(row=row_idx, column=40)
                    try:
                        cell_an.value = int(float(out_mfa))
                    except (ValueError, TypeError):
                        cell_an.value = out_mfa

                    ws.cell(row=row_idx, column=41).value = out_dim

                # 🎯 填入備註 (Col 42, AP)：若選 APP 或集控，帶入轉接小P板與無線接收器/集控轉接基板型號
                ctrl_mode = str(room.get("control_mode") or room.get("ctrl_mode") or "").strip()
                if ctrl_mode and ctrl_mode != "無" and indoor_info:
                    p_board = indoor_info.get("adapter_p_board", "-")
                    w_recv = indoor_info.get("wireless_receiver", "-")
                    c_board = indoor_info.get("central_adapter_board", "-")
                    notes = []
                    if "APP" in ctrl_mode.upper():
                        sub = []
                        if p_board and p_board not in ["-", "內建", "None", ""]:
                            sub.append(f"小P板:{p_board}")
                        if w_recv and w_recv not in ["-", "None", ""]:
                            sub.append(f"無線接收:{w_recv}")
                        if sub:
                            notes.append(f"APP({', '.join(sub)})")
                        elif w_recv == "內建":
                            notes.append("APP(內建無線)")
                    if "集控" in ctrl_mode or "CENTRAL" in ctrl_mode.upper():
                        sub = []
                        if p_board and p_board not in ["-", "內建", "None", ""]:
                            sub.append(f"小P板:{p_board}")
                        if c_board and c_board not in ["-", "None", ""]:
                            sub.append(f"集控板:{c_board}")
                        if sub:
                            notes.append(f"集控({', '.join(sub)})")
                    if notes:
                        ws.cell(row=row_idx, column=42).value = " | ".join(notes)
                        ws.cell(row=row_idx, column=42).alignment = align_center

                # 🎯 全熱交換器規劃欄位 (Col 43 ~ 53: AQ ~ BA)
                # 只有在使用者選擇啟用全熱且已配對出全熱設備時才填寫
                if matched_hrv and hrv_sel_set:
                    a_m2_val = float(room.get("area_m2") or 0.0)
                    if a_m2_val <= 0 and float(room.get("area_ping") or 0.0) > 0:
                        a_m2_val = float(room.get("area_ping")) / 0.3025
                    est_ppl = _resolve_ppl(i, a_m2_val)
                    b_val = float(basis_map.get(str(i), basis_map.get(i, 30.0)))
                    req_airflow = int(est_ppl * b_val)
                    is_this_hrv = i in hrv_sel_set

                    ws.cell(row=row_idx, column=43).value = "5m2/人"
                    ws.cell(row=row_idx, column=44).value = est_ppl
                    ws.cell(row=row_idx, column=45).value = "30CMH/人"
                    ws.cell(row=row_idx, column=46).value = req_airflow

                    # 僅在首列填入全案全熱交換器規格，後續執行跨列合併 (Merge Cells Col 47 ~ 53)
                    if i == 0:
                        ws.cell(row=row_idx, column=47).value = total_hrv_airflow
                        ws.cell(row=row_idx, column=48).value = matched_hrv["model"]
                        ws.cell(row=row_idx, column=49).value = 1
                        ws.cell(row=row_idx, column=50).value = matched_hrv["power_kw"]
                        ws.cell(row=row_idx, column=51).value = matched_hrv["power_supply"]
                        ws.cell(row=row_idx, column=52).value = matched_hrv["dimensions"]
                        ws.cell(row=row_idx, column=53).value = "需要" if has_pm25 else "-"

                    for c_col in range(43, 54):
                        ws.cell(row=row_idx, column=c_col).alignment = align_center
                else:
                    # 🎯 未選全熱時，清空儲存格內容
                    for c_col in range(43, 54):
                        ws.cell(row=row_idx, column=c_col).value = None

            # 🎯 確保選機表第 8 列表頭 BA 欄位標記為 PM2.5濾網 (若有全熱)
            if matched_hrv and hrv_sel_set:
                ws.cell(row=8, column=53).value = "PM2.5濾網"

            # 🎯 全熱交換器跨列合併：Col 47 ~ 53 (AU ~ BA: 加總風量、型號、台數、耗電、電源、尺寸、PM2.5)
            if len(flat_rows_to_render) > 1 and matched_hrv and hrv_sel_set:
                hrv_start_row = start_row
                hrv_end_row = start_row + len(flat_rows_to_render) - 1
                for hrv_col in range(47, 54):
                    ws.merge_cells(start_row=hrv_start_row, end_row=hrv_end_row, start_column=hrv_col, end_column=hrv_col)
                    ws.cell(row=hrv_start_row, column=hrv_col).alignment = align_center

            # 🎯 依使用者需求：未選全熱時，於選機表徹底隱藏全熱相關欄位 (Col 43 ~ 53: AQ ~ BA)
            if not matched_hrv or not hrv_sel_set:
                from openpyxl.utils import get_column_letter
                for col_idx in range(43, 54):
                    col_letter = get_column_letter(col_idx)
                    ws.column_dimensions[col_letter].hidden = True

            # 🎯 執行室外機群組縱向跨列合併與 EQUIPMENT_Data 對應填入 (openpyxl Rowspan Engine)
            for span in group_spans:
                s_r = span["start_row"]
                e_r = span["end_row"]
                out_info = span["outdoor_info"]
                
                out_model = span["outdoor_model"]
                out_qty = span["outdoor_qty"]
                conn_ratio_str = span["conn_ratio_str"]
                group_sys = str(span.get("system_type", "VRV")).upper()
                
                out_cap_kw = float(out_info.get("cap_kw", span["fallback_cap_kw"])) if out_info else span["fallback_cap_kw"]
                out_cap_kcal = round(out_cap_kw * 860.0, 1) if out_cap_kw > 0 else "-"
                out_nominal = out_info.get("nominal_cap", "-") if (out_info and "VRV" in group_sys) else "-"
                out_pwr_con = out_info.get("power_consumption_kw", "-") if out_info else "-"
                out_pwr_sup = out_info.get("power_supply", "-") if out_info else "-"
                out_mca = out_info.get("mca", "-") if out_info else "-"
                out_mfa = out_info.get("mfa", "-") if out_info else "-"
                out_dim = out_info.get("dimensions", "-") if out_info else "-"

                # 🎯 經理指示 2：RA 系統不需要提供連結率，維持 "-" 即可
                conn_ratio_display = "-" if "RA" in group_sys else conn_ratio_str

                # 填寫室外機專屬 11 個欄位 (AE ~ AO, Columns 31 ~ 41)
                ws.cell(row=s_r, column=31).value = out_model       # AE: 室外機型號 (第4列)
                ws.cell(row=s_r, column=32).value = out_qty         # AF: 室外機台數 (以選型台數為主)
                ws.cell(row=s_r, column=33).value = out_cap_kcal     # AG: 冷房能力 (kcal/hr)
                ws.cell(row=s_r, column=34).value = out_cap_kw       # AH: 冷房能力 (kW) (第5列)
                ws.cell(row=s_r, column=35).value = out_nominal      # AI: 標稱能力 (第6列)
                ws.cell(row=s_r, column=36).value = conn_ratio_display # AJ: 連結率 %
                
                cell_ak = ws.cell(row=s_r, column=37)
                try:
                    cell_ak.value = float(out_pwr_con)
                    cell_ak.number_format = '0.00'
                except (ValueError, TypeError):
                    cell_ak.value = out_pwr_con

                ws.cell(row=s_r, column=38).value = out_pwr_sup

                cell_am = ws.cell(row=s_r, column=39)
                try:
                    cell_am.value = float(out_mca)
                    cell_am.number_format = '0.0'
                except (ValueError, TypeError):
                    cell_am.value = out_mca

                cell_an = ws.cell(row=s_r, column=40)
                try:
                    cell_an.value = int(float(out_mfa))
                except (ValueError, TypeError):
                    cell_an.value = out_mfa

                ws.cell(row=s_r, column=41).value = out_dim
                
                # 縱向跨列合併對齊
                for col_c in range(31, 42):
                    if e_r > s_r:
                        ws.merge_cells(start_row=s_r, end_row=e_r, start_column=col_c, end_column=col_c)
                    ws.cell(row=s_r, column=col_c).alignment = align_center

            # 🎯 整合設備統計總表、系統套數樹狀拓撲、D3-NET 分析分頁 (獨立模組化調用)
            try:
                from app.services.equipment_summary_service import EquipmentSummaryService
                hrv_summary_info = None
                if matched_hrv:
                    hrv_summary_info = {
                        "model": matched_hrv["model"],
                        "airflow": matched_hrv["airflow"],
                        "price": matched_hrv["price"],
                        "has_pm25": has_pm25,
                        "pm25_filter_model": matched_hrv.get("pm25_filter_model", ""),
                        "pm25_filter_price": matched_hrv.get("pm25_filter_price", 0.0),
                        "total_airflow": total_hrv_airflow
                    }

                EquipmentSummaryService.append_summary_sheets(
                    wb,
                    flat_rows_to_render,
                    outdoor_groups,
                    selected_controllers=selected_controllers,
                    custom_piping_trees=custom_piping_trees,
                    custom_piping_diagram_images=custom_piping_diagram_images,
                    hrv_info=hrv_summary_info
                )
            except Exception as summary_err:
                logger.error(f"Failed to generate summary sheets: {summary_err}")

                        # 🎯 匯出的選機表中，選機分頁若出現整欄都是 "-" 時，直接隱藏該欄位，如果有其中一項有數值，則保留該欄位
            from openpyxl.utils import get_column_letter
            for col_idx in range(4, 43):
                col_letter = get_column_letter(col_idx)
                has_val = False
                for r in range(start_row, start_row + len(flat_rows_to_render)):
                    v = ws.cell(row=r, column=col_idx).value
                    v_str = str(v).strip() if v is not None else ""
                    if v_str and v_str not in ["-", "None", "", "none"]:
                        has_val = True
                        break
                if not has_val:
                    ws.column_dimensions[col_letter].hidden = True

            # 🎯 匯出的選機表分頁僅保留"選機"、"設備報價單"和"系統套數"即可，其餘的選積分頁請隱藏
            allowed_visible_titles = {"選機", "選機表", "設備報價單", "系統套數"}
            for sheet in wb.worksheets:
                if sheet.title in allowed_visible_titles:
                    sheet.sheet_state = "visible"
                else:
                    sheet.sheet_state = "hidden"

            # 確保啟用中的工作表為可見的工作表
            for title in ["選機", "選機表", "設備報價單", "系統套數"]:
                if title in wb.sheetnames:
                    wb.active = wb[title]
                    break

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Failed to export using Excel template: {e}")
            return cls._generate_fallback_excel(rooms_data)

    @classmethod
    def _generate_fallback_excel(cls, rooms_data: List[Dict[str, Any]]) -> io.BytesIO:
        """
        Creates a basic spreadsheet if the template is not present.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "選機結果表"
        
        headers = ["空間名稱", "面積 (m2)", "坪數", "每坪kcal", "每坪kW", "設計負荷(kW)", "設計負荷(kcal)", "機型", "數量", "單台能力(kW)"]
        for idx, h in enumerate(headers, 1):
            ws.cell(row=1, column=idx).value = h
            
        for r_idx, room in enumerate(rooms_data, 2):
            ws.cell(row=r_idx, column=1).value = room.get("room_name")
            ws.cell(row=r_idx, column=2).value = room.get("area_m2")
            ws.cell(row=r_idx, column=3).value = room.get("ping_val")
            ws.cell(row=r_idx, column=4).value = room.get("final_suggested_kcal_per_ping")
            ws.cell(row=r_idx, column=5).value = room.get("kw_per_ping")
            ws.cell(row=r_idx, column=6).value = room.get("total_load_kw")
            ws.cell(row=r_idx, column=7).value = room.get("total_load_kcal")
            ws.cell(row=r_idx, column=8).value = room.get("indoor_model")
            ws.cell(row=r_idx, column=9).value = room.get("qty")
            ws.cell(row=r_idx, column=10).value = room.get("indoor_capacity_kw")
            
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output
