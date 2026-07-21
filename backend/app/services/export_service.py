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
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "product_database",
            settings.TEMPLATE_NAME
        )

    @classmethod
    def generate_excel_report(cls, rooms_data: List[Dict[str, Any]]) -> io.BytesIO:
        """
        Loads the template Excel sheet '選機表-.xlsx', inserts rows dynamically if needed,
        maps properties to exact column indexes, and outputs a BytesIO stream.
        """
        template_path = cls.get_template_path()
        
        if not os.path.exists(template_path):
            logger.warning(f"Excel template file {settings.TEMPLATE_NAME} not found at {template_path}. Generating simple output.")
            return cls._generate_fallback_excel(rooms_data)
            
        try:
            wb = openpyxl.load_workbook(template_path)
            ws = wb.active
            
            start_row = settings.START_ROW
            template_rows = settings.TEMPLATE_ROWS
            
            # If the number of spaces exceeds the template placeholder rows, insert rows dynamically
            if len(rooms_data) > template_rows:
                for _ in range(len(rooms_data) - template_rows):
                    ws.insert_rows(start_row + template_rows - 1)
                    # Copy styles from the standard template row
                    for c in range(1, ws.max_column + 1):
                        ws.cell(row=start_row + template_rows - 1, column=c)._style = ws.cell(row=start_row, column=c)._style
                        
            # Write rooms data
            for i, room in enumerate(rooms_data):
                row_idx = start_row + i
                
                name = room.get("room_name", "").strip()
                area_m2 = float(room.get("area_m2", 0.0))
                ping_val = float(room.get("ping_val", 0.0))
                
                final_suggested_kcal_per_ping = float(room.get("final_suggested_kcal_per_ping", 0.0))
                kw_per_ping = float(room.get("kw_per_ping", 0.0))
                total_load_kw = float(room.get("total_load_kw", 0.0))
                total_load_kcal = float(room.get("total_load_kcal", 0.0))
                
                matched_model = room.get("indoor_model", "")
                qty = int(room.get("qty", 1))
                cap_kw = float(room.get("indoor_capacity_kw", 0.0))
                cap_kcal = float(room.get("indoor_capacity_kcal", 0.0))
                
                # Write to exact column mappings (from your script)
                ws.cell(row=row_idx, column=settings.NAME_COL).value = name
                ws.cell(row=row_idx, column=settings.AREA_COL).value = area_m2
                ws.cell(row=row_idx, column=settings.PING_COL).value = ping_val
                ws.cell(row=row_idx, column=settings.LOAD_H_COL).value = final_suggested_kcal_per_ping  
                
                cell_k = ws.cell(row=row_idx, column=settings.LOAD_K_COL)
                cell_k.value = kw_per_ping
                cell_k.number_format = '0.00'
                
                ws.cell(row=row_idx, column=settings.LOAD_L_COL).value = total_load_kw
                ws.cell(row=row_idx, column=settings.LOAD_M_COL).value = total_load_kcal           
                ws.cell(row=row_idx, column=settings.MODEL_N_COL).value = matched_model            
                ws.cell(row=row_idx, column=settings.QTY_O_COL).value = qty                        
                ws.cell(row=row_idx, column=settings.CAP_KCAL_P_COL).value = cap_kcal
                ws.cell(row=row_idx, column=settings.CAP_KW_Q_COL).value = cap_kw
                
                ws.cell(row=row_idx, column=settings.TOTAL_KCAL_W_COL).value = float(qty * cap_kcal)
                ws.cell(row=row_idx, column=settings.TOTAL_KW_X_COL).value = float(qty * cap_kw)
                
                if ping_val > 0:
                    ws.cell(row=row_idx, column=settings.PER_PING_KCAL_AB_COL).value = int(round(cap_kcal / ping_val, 0))
                    ws.cell(row=row_idx, column=settings.PER_PING_KW_AC_COL).value = round(cap_kw / ping_val, 1)
                
                if (qty * cap_kw) > 0:
                    # USRT conversion ratio: 1 USRT = 3.516 kW
                    ws.cell(row=row_idx, column=settings.PING_PER_USRT_AD_COL).value = round(ping_val / ((qty * cap_kw) / 3.516), 1)

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
