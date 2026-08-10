import os
import io
import logging
from typing import List, Dict, Any
import openpyxl

from app.config import settings

logger = logging.getLogger(__name__)

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
    def generate_excel_report(cls, rooms_data: List[Dict[str, Any]], outdoor_groups: List[Dict[str, Any]] = None) -> io.BytesIO:
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
            
            # Flatten rooms based on outdoor_groups if provided, else use rooms_data directly
            flat_rows_to_render = []
            group_spans = [] # List of (start_row, end_row, outdoor_model, conn_ratio, diversity)
            
            if outdoor_groups and len(outdoor_groups) > 0:
                current_idx = 0
                for group in outdoor_groups:
                    group_spaces = group.get("spaces", [])
                    if not group_spaces:
                        continue
                    g_start = start_row + current_idx
                    g_end = g_start + len(group_spaces) - 1
                    
                    sum_indoor_kw = sum(float(s.get("indoor_capacity_kw", s.get("cap_kw", 0.0))) * int(s.get("qty", s.get("unit_count", 1))) for s in group_spaces)
                    outdoor_kw = float(group.get("outdoor_cap_kw", 0.0))
                    diversity = float(group.get("diversity_factor", 100))
                    conn_ratio = round((sum_indoor_kw / outdoor_kw) * 100, 1) if outdoor_kw > 0 else 0.0
                    
                    group_spans.append({
                        "start_row": g_start,
                        "end_row": g_end,
                        "outdoor_model": group.get("outdoor_model", "室外機"),
                        "conn_ratio": f"{conn_ratio}%",
                        "diversity": f"{diversity}%"
                    })
                    
                    for s in group_spaces:
                        flat_rows_to_render.append(s)
                        current_idx += 1
                        
                # Add any remaining ungrouped spaces
                if rooms_data:
                    rendered_names = {s.get("room_name", s.get("space_name", "")) for s in flat_rows_to_render}
                    for r in rooms_data:
                        r_name = r.get("room_name", r.get("space_name", ""))
                        if r_name not in rendered_names:
                            flat_rows_to_render.append(r)
                            current_idx += 1
            else:
                flat_rows_to_render = rooms_data or []

            # If the number of spaces exceeds the template placeholder rows, insert rows dynamically
            template_rows = settings.TEMPLATE_ROWS
            if len(flat_rows_to_render) > template_rows:
                for _ in range(len(flat_rows_to_render) - template_rows):
                    ws.insert_rows(start_row + template_rows - 1)
                    for c in range(1, ws.max_column + 1):
                        ws.cell(row=start_row + template_rows - 1, column=c)._style = ws.cell(row=start_row, column=c)._style
                        
            # Write rooms data
            for i, room in enumerate(flat_rows_to_render):
                row_idx = start_row + i
                
                name = room.get("room_name", room.get("space_name", "")).strip()
                area_m2 = float(room.get("area_m2", 0.0))
                ping_val = float(room.get("ping_val", room.get("area_ping", 0.0)))
                
                final_suggested_kcal_per_ping = float(room.get("final_suggested_kcal_per_ping", room.get("calc_basis", 500.0)))
                kw_per_ping = float(room.get("kw_per_ping", round(final_suggested_kcal_per_ping / 860.0, 2)))
                total_load_kcal = float(room.get("total_load_kcal", room.get("total_cooling_demand", Math.round(ping_val * final_suggested_kcal_per_ping) if 'Math' in str(type(ping_val)) else round(ping_val * final_suggested_kcal_per_ping))))
                total_load_kw = float(room.get("total_load_kw", round(total_load_kcal / 860.0, 2)))
                
                matched_model = room.get("indoor_model", room.get("best_match_model", ""))
                qty = int(room.get("qty", room.get("unit_count", 1)))
                cap_kw = float(room.get("indoor_capacity_kw", room.get("cap_kw", 0.0)))
                cap_kcal = float(room.get("indoor_capacity_kcal", round(cap_kw * 860.0, 1)))
                
                nominal_cap = room.get("nominal_cap", "-")
                power_supply = room.get("power_supply", "-")
                power_consumption_kw = room.get("power_consumption_kw", "-")
                dimensions = room.get("dimensions", "-")

                # Write to exact column mappings
                ws.cell(row=row_idx, column=settings.NAME_COL).value = name
                ws.cell(row=row_idx, column=settings.AREA_COL).value = area_m2
                ws.cell(row=row_idx, column=settings.PING_COL).value = ping_val
                ws.cell(row=row_idx, column=settings.LOAD_H_COL).value = final_suggested_kcal_per_ping  
                
                cell_k = ws.cell(row=row_idx, column=settings.LOAD_K_COL)
                cell_k.value = kw_per_ping
                cell_k.number_format = '0.00'
                
                ws.cell(row=row_idx, column=settings.LOAD_L_COL).value = total_load_kw
                ws.cell(row=row_idx, column=settings.LOAD_M_COL).value = total_load_kcal           
                
                ws.cell(row=row_idx, column=14).value = matched_model            
                ws.cell(row=row_idx, column=15).value = qty                        
                ws.cell(row=row_idx, column=16).value = cap_kcal
                ws.cell(row=row_idx, column=17).value = cap_kw
                ws.cell(row=row_idx, column=18).value = nominal_cap
                ws.cell(row=row_idx, column=19).value = power_supply
                ws.cell(row=row_idx, column=20).value = power_consumption_kw
                ws.cell(row=row_idx, column=22).value = dimensions
                
                ws.cell(row=row_idx, column=settings.TOTAL_KCAL_W_COL).value = float(qty * cap_kcal)
                ws.cell(row=row_idx, column=settings.TOTAL_KW_X_COL).value = float(qty * cap_kw)
                
                if ping_val > 0:
                    ws.cell(row=row_idx, column=settings.PER_PING_KCAL_AB_COL).value = int(round(cap_kcal / ping_val, 0))
                    ws.cell(row=row_idx, column=settings.PER_PING_KW_AC_COL).value = round(cap_kw / ping_val, 1)
                
                if (qty * cap_kw) > 0:
                    ws.cell(row=row_idx, column=settings.PING_PER_USRT_AD_COL).value = round(ping_val / ((qty * cap_kw) / 3.516), 1)

            # 🎯 執行縱向跨列合併 (openpyxl Rowspan Engine)
            for span in group_spans:
                s_r = span["start_row"]
                e_r = span["end_row"]
                
                ws.cell(row=s_r, column=31).value = span["outdoor_model"]
                ws.cell(row=s_r, column=32).value = span["conn_ratio"]
                ws.cell(row=s_r, column=33).value = span["diversity"]
                
                if e_r > s_r:
                    ws.merge_cells(start_row=s_r, end_row=e_r, start_column=31, end_column=31)
                    ws.merge_cells(start_row=s_r, end_row=e_r, start_column=32, end_column=32)
                    ws.merge_cells(start_row=s_r, end_row=e_r, start_column=33, end_column=33)
                    
                    ws.cell(row=s_r, column=31).alignment = align_center
                    ws.cell(row=s_r, column=32).alignment = align_center
                    ws.cell(row=s_r, column=33).alignment = align_center

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
