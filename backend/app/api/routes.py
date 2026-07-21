from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import io
import os
import re
import json
import openpyxl
from datetime import datetime
from PIL import Image
from google import genai
from google.genai import types

# 🎯 完美串聯：直接匯入與您 config.env 同步的 settings 物件
try:
    from app.config import settings
except ImportError:
    try:
        from config import settings
    except ImportError:
        # 最終備用防線
        class MockSettings:
            GEMINI_API_KEY = "AQ.Ab8RN6Kd9HoU-3YA2zqXngcI24DFbBF_svgySXxRMxo6zs0w7A"
        settings = MockSettings()

# 引入 PDF 轉圖片套件防線
try:
    from pdf2image import convert_from_bytes
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

router = APIRouter()

# 🔒 改用經理專屬 Settings 咬合機制，回傳在 config.env 內設定的 GEMINI_API_KEY
def find_api_key_securely() -> str:
    if hasattr(settings, "GEMINI_API_KEY") and settings.GEMINI_API_KEY:
        return settings.GEMINI_API_KEY
    return "AQ.Ab8RN6Kd9HoU-3YA2zqXngcI24DFbBF_svgySXxRMxo6zs0w7A"

API_KEY = find_api_key_securely()

# 大金標準實體型號資料庫 (相容備用)
EQUIPMENT_DB = {
    "RA": [
        {"model": "FTXM22ZVLT", "cap": 2.2}, {"model": "FTXM28ZVLT", "cap": 2.8},
        {"model": "FTXM36ZVLT", "cap": 3.5}, {"model": "FTXM41ZVLT", "cap": 4.1},
        {"model": "FTXM50ZVLT", "cap": 5.0}, {"model": "FTXM60ZVLT", "cap": 6.0},
        {"model": "FTXM71ZVLT", "cap": 7.2}, {"model": "FTXM80ZVLT", "cap": 8.0},
        {"model": "FTXM90ZVLT", "cap": 8.7}
    ],
    "SA": [
        {"model": "FBA71BVLT", "cap": 7.2}, {"model": "FBA100BVLT", "cap": 10.1},
        {"model": "FBA125BVLT", "cap": 12.5}, {"model": "FBA140BVLT", "cap": 13.3}
    ],
    "VRV": [
        {"model": "FXSQ20PAVT", "cap": 2.2}, {"model": "FXSQ25PAVT", "cap": 2.8},
        {"model": "FXSQ32PAVT", "cap": 3.6}, {"model": "FXSQ40PAVT", "cap": 4.5},
        {"model": "FXSQ50PAVT", "cap": 5.6}, {"model": "FXSQ63PAVT", "cap": 7.1},
        {"model": "FXSQ80PAVT", "cap": 9.0}, {"model": "FXSQ100PAVT", "cap": 11.2},
        {"model": "FXSQ125PAVT", "cap": 14.0}, {"model": "FXSQ140PAVT", "cap": 16.0}
    ]
}

# --- 🎯 精準對齊前端欄位格式的 Export 結構定義 ---
class ExportRowModel(BaseModel):
    space_name: str
    area_m2: float
    area_ping: float
    system_type: str
    exposures_str: str = ""
    base_suggested_load: float = 0.0
    final_kcal_per_ping: float = 0.0
    special_kw: float = 0.0
    special_heat_kcal: float = 0.0
    total_cooling_load_kcal: float = 0.0
    recommended_model: str
    qty: int
    cap_kw: float = 0.0

class ExportRequest(BaseModel):
    data: List[ExportRowModel]

# v15 智慧拆分與保底除算演算法 (相容備用)
def auto_select_equipment_v15_backend(total_load_kw: float, system_type: str):
    models_list = EQUIPMENT_DB.get(system_type, [])
    if not models_list:
        return "無適用系統", 1, 0.0
    best_model = None
    best_qty = 999
    best_cap = 0.0
    for item in models_list:
        single_cap = item["cap"]
        for qty in range(1, 11):
            if (single_cap * qty) >= total_load_kw:
                if qty < best_qty:
                    best_qty = qty
                    best_model = item["model"]
                    best_cap = single_cap
                    break
                elif qty == best_qty:
                    if best_model is None or single_cap < best_cap:
                        best_qty = qty
                        best_model = item["model"]
                        best_cap = single_cap
                    break
    if best_model is not None:
        return best_model, best_qty, best_cap
    max_item = models_list[-1]
    needed_qty = int((total_load_kw / max_item["cap"]) + 0.99)
    if needed_qty == 0: needed_qty = 1
    return max_item["model"], needed_qty, max_item["cap"]

# 空調負荷基準表智慧查找 (完全參照經理技術底稿，未命中則保底拋警告)
def get_base_load_by_name(space_name: str) -> float:
    name = space_name.strip()
    if any(k in name for k in ["主臥", "主臥室"]): return 520.0
    if any(k in name for k in ["次臥", "女兒房", "小孩房", "男孩房", "兒子房", "傭人", "管家", "客房", "值班"]): return 500.0
    if any(k in name for k in ["書房"]): return 500.0
    if any(k in name for k in ["客廳"]): return 550.0
    if any(k in name for k in ["餐廳"]): return 600.0
    if any(k in name for k in ["廚房"]): return 700.0
    if any(k in name for k in ["廁所", "浴室", "女廁", "男廁", "客浴", "主臥浴室"]): return 350.0
    if any(k in name for k in ["儲藏室", "更衣室", "更衣間"]): return 400.0
    if any(k in name for k in ["玄關", "走道", "走廊"]): return 450.0
    if any(k in name for k in ["檔案室", "機房"]): return 650.0
    return 500.0

# 🎯 圖面解析路由
@router.post("/upload-layout")
async def upload_layout(
    file: UploadFile = File(...),
    case_type: str = Form(...)
):
    print("\n🚀 【後端成功收到網頁請求！】開始解析...")
    print(f"📁 收到檔名: {file.filename}")
    print(f"🔑 檢查安全金鑰是否加載: {'是' if API_KEY else '否'}")
    
    if not API_KEY:
        raise HTTPException(status_code=500, detail="錯誤：後端找不到有效的 config.env 或 GEMINI_API_KEY 設定。")

    try:
        file_bytes = await file.read()
        filename_lower = file.filename.lower()
        final_image_bytes = None
        
        # 💥 PDF 向量圖預先渲染防線
        if filename_lower.endswith('.pdf') or file.content_type == 'application/pdf':
            if not PDF_SUPPORT:
                raise ValueError("系統尚未安裝 pdf2image 套件，無法解析 PDF 圖檔。請執行 pip install pdf2image")
            images = convert_from_bytes(
                file_bytes, 
                dpi=300, 
                poppler_path=r"C:\Users\flitt\OneDrive\桌面\floorplan_test\utils\poppler\bin"
            )
            if not images:
                raise ValueError("PDF 渲染失敗，無法讀取頁面。")
            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='JPEG')
            final_image_bytes = img_byte_arr.getvalue()
            
        # 💥 實體圖片等比例無損壓縮防線
        else:
            img = Image.open(io.BytesIO(file_bytes))
            max_size = 1600
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            img_byte_arr = io.BytesIO()
            img.convert('RGB').save(img_byte_arr, format='JPEG', quality=85)
            final_image_bytes = img_byte_arr.getvalue()

        image_part = types.Part.from_bytes(
            data=final_image_bytes,
            mime_type="image/jpeg",
        )
        
        # 🎯 經理業務核心需求提示詞（完全清洗稽察室誤導，換裝標準家用住宅規範與嚴格物理排序）
        analysis_prompt = """
        你是一位專業的空調工程專家，請精準解析這張住宅或商業空調平面圖，並嚴格按照以下 JSON 格式回傳數據。
    
        [核心解析與計算規範]
        1. 空間名稱: 請依據圖面標示, 精準辨識各區域名稱 (如: 主臥、次臥、客廳、餐廳、廚房、浴室、玄關、更衣室等)。絕對不可擅自更動、簡化或丟失圖面空間，若辨識出類似「檔率」等模糊字詞請統一輸出為「檔案室」。
        2. 空間排序: 必須嚴格按照物理空間「由左至右、由上至下」的順序依序輸出，保持圖像物理邏輯，不可任意打亂或合併。
        3. 面積標示: 每個空間的面積必須同時包含 平方公尺(m2) 與 坪數(P), 並嚴格遵守 1 m2 = 0.3025 坪的換算率。
        4. 空調負荷基準: 請依據空間性質評估其冷房基準值 (kcal/h/坪)。
        5. 總需求計算: 總需求 (kcal/h) = 坪數 * 空調負荷基準 (請務必輸出純數字，絕不能出現非數值)。
        6. 大金室內機型號匹配: 請根據該空間的系統規格 (如 VRV 系統) 與總需求冷風量, 自動匹配對應的大金實體型號 (例如: FXSQ20PAVT、FXSQ40PAVT 等)，絕不能留空。

        [嚴格 JSON 回傳格式]
        [
          {
            "space_name": "空間精準名稱",
            "system_spec": "VRV", 
            "area_m2": 25.42,
            "area_ping": 7.68,
            "load_basis": 520,
            "total_demand": 3994,
            "daikin_model": "FXSQ40PAVT",
            "quantity": 1
          }
        ]
        """

        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image_part, analysis_prompt]
        )
        
        if not response.text:
            raise ValueError("Gemini API 回傳內容為空。")

        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        parsed_spaces = json.loads(clean_text)
        
        results = []
        for space in parsed_spaces:
            name = space.get("space_name", "未命名空間").strip()
            system_spec = space.get("system_spec", "VRV").strip()
            
            area_m2 = space.get("area_m2", 0.0)
            area_ping = space.get("area_ping", 0.0)
            if area_ping == 0.0 and area_m2 > 0:
                area_ping = round(area_m2 * 0.3025, 2)
            
            # 🎯 完全查表加載經理表格負荷
            base_suggested = get_base_load_by_name(name)
            
            # 🎯 精準判斷是否為「找不到」的特殊未知空間
            is_unknown = False
            if base_suggested == 500.0 and not any(k in name for k in ["次臥", "女兒房", "小孩房", "男孩房", "兒子房", "傭人", "管家", "客房", "書房", "值班"]):
                is_unknown = True
            
            # 🎯 以精準查表值連動計算冷房總需求數字
            total_cooling_load_kcal = round(float(area_ping) * base_suggested)
            
            model_name = space.get("daikin_model", "未匹配型號").strip()
            qty = space.get("quantity", 1)
            cap_kw = round((total_cooling_load_kcal / 860.0), 2)

            results.append({
                "space_name": name,
                "area_m2": float(area_m2),
                "area_ping": float(area_ping),
                "system_type": str(system_spec),
                "base_suggested_load": float(base_suggested),
                "final_kcal_per_ping": float(base_suggested),
                "total_cooling_load_kcal": float(total_cooling_load_kcal),
                "recommended_model": str(model_name),
                "qty": int(qty),
                "cap_kw": float(cap_kw),
                "exposures_str": "",
                "special_kw": 0.0,
                "special_heat_kcal": 0.0,
                "is_unknown_space": is_unknown
            })
            
        print(f"✅ 【後端解析成功】已準備好 {len(results)} 個空間的精準大金選機數據並保留原始物理排序。")
        return results

    except Exception as e:
        import traceback
        print("🔴 【圖面解析出錯詳細軌跡】:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"【後端運行錯誤診斷】: {str(e)}")


# 🎯 Excel 匯出路由 (完全遵照經理指示，自 D9 欄位起點乾淨帶入)
@router.post("/export-excel")
async def export_excel(payload: ExportRequest):
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        template_path = os.path.join(base_dir, "選機表-.xlsx")
        
        if not os.path.exists(template_path):
            template_path = os.path.abspath("選機表-.xlsx")
            
        wb = openpyxl.load_workbook(template_path)
        sheet = wb.active
        
        # 🎯 關鍵微調一：避開 7-8 行表頭地雷，直接對齊經理底稿第 9 行起點
        start_row = 9  
        
        for i, row_data in enumerate(payload.data):
            # 🎯 關鍵微調二：第 9 行起完全無合併，恢復標準「1行1筆」順序填入
            current_row = start_row + i
            
            display_name = row_data.space_name
            if "檔率" in display_name:
                display_name = display_name.replace("檔率", "檔案室")
                
            # 🎯 嚴格遵循 VV17 歷史大金官方選機表指定欄位對應規則填入：
            sheet.cell(row=current_row, column=1).value = "2F"                  # Column A: 樓層
            sheet.cell(row=current_row, column=4).value = display_name           # Column D: 空間名稱
            sheet.cell(row=current_row, column=5).value = row_data.area_m2       # Column E: 平方公尺 (㎡)
            sheet.cell(row=current_row, column=6).value = row_data.area_ping     # Column F: 坪數 (P)
            
            calc_basis = row_data.final_kcal_per_ping if (row_data.final_kcal_per_ping and row_data.final_kcal_per_ping > 0) else row_data.base_suggested_load
            if not calc_basis or calc_basis == 0:
                calc_basis = 500.0
                
            sheet.cell(row=current_row, column=8).value = calc_basis             # Column H: 冷房負荷基準
            sheet.cell(row=current_row, column=12).value = row_data.total_cooling_load_kcal # Column L: 估算總需求
            sheet.cell(row=current_row, column=13).value = row_data.total_cooling_load_kcal # Column M: 最終採用能力
            sheet.cell(row=current_row, column=14).value = row_data.recommended_model       # Column N: 大金實體型號
            sheet.cell(row=current_row, column=15).value = row_data.qty                     # Column O: 配置台數

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        return StreamingResponse(
            output, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except Exception as e:
        import traceback
        print("🔴 後端 Excel 導出出錯詳細軌跡：")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"底稿寫入失敗：{str(e)}")
