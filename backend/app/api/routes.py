import base64
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

def lookup_cap_kw(model_name: str) -> float:
    for cat, items in EQUIPMENT_DB.items():
        for item in items:
            if item["model"] == model_name:
                return float(item["cap"])
    return 0.0

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
    filename: str = ""
    data: List[ExportRowModel]

# v15/v17 智慧最少台數與平均負擔容量最佳化選機演算法
def auto_select_equipment_v15_backend(total_load_kw: float, system_type: str):
    models_list = EQUIPMENT_DB.get(system_type, EQUIPMENT_DB.get("VRV", []))
    if not models_list:
        return "無適用系統", 1, 0.0

    best_model = None
    best_qty = 999
    best_cap = 0.0

    for item in models_list:
        single_cap = item["cap"]
        for qty in range(1, 11):
            total_cap = single_cap * qty
            if total_cap >= total_load_kw:
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
    needed_qty = int(round((total_load_kw / max_item["cap"]) + 0.5, 0))
    if needed_qty == 0:
        needed_qty = 1
    return max_item["model"], needed_qty, max_item["cap"]

import difflib

# 🎯 自動自《空調負荷基準表.xlsx》動態載入全頁面模糊搜尋規則庫
def load_fuzzy_rules_from_excel():
    rules = []
    try:
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        possible_dirs = [
            os.path.join(cur_dir, "..", "product_database"),
            os.path.join(cur_dir, "..", "..", "product_database"),
            os.path.join(cur_dir, "..", "..", "backend", "product_database"),
            os.path.join(os.getcwd(), "product_database"),
            os.path.join(os.getcwd(), "backend", "product_database")
        ]
        excel_path = None
        for pdir in possible_dirs:
            pdir = os.path.abspath(pdir)
            if os.path.exists(pdir) and os.path.isdir(pdir):
                for fn in os.listdir(pdir):
                    if fn.endswith(".xlsx") and not fn.startswith("~$"):
                        excel_path = os.path.join(pdir, fn)
                        break
            if excel_path:
                break
        
        if excel_path and os.path.exists(excel_path):
            wb = openpyxl.load_workbook(excel_path, data_only=True)
            for sheetname in wb.sheetnames:
                if sheetname == "總表":
                    continue
                sheet = wb[sheetname]
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if row and len(row) >= 2 and row[0] and row[1]:
                        names_raw = str(row[0])
                        try:
                            val = float(row[1])
                        except (ValueError, TypeError):
                            continue
                        kw_list = [re.sub(r'[^\w\u4e00-\u9fa5]', '', k.strip()) for k in re.split(r'[,、/\n\s]+', names_raw) if k.strip()]
                        if kw_list:
                            rules.append((kw_list, val))
    except Exception as e:
        print(f"[Backend Warning] 動態讀取 Excel 負荷表失敗: {e}")

    # 備用保底基礎規則 (若 Excel 檔案讀取異常時使用)
    if not rules:
        rules = [
            (["辦公室", "辦公", "小辦公", "開放辦公", "洽談", "合約", "會議", "會客", "演講", "休息", "休憩", "貴賓", "簡報", "作業區", "討論"], 630.0),
            (["董事長", "總經理", "主管", "經理", "執行長", "副總"], 550.0),
            (["茶水", "茶水間", "茶水區"], 450.0),
            (["男廁", "女廁", "殘障廁所", "無障礙", "廁所", "洗手間", "衛浴", "便所", "客浴", "主臥浴室", "浴室"], 350.0),
            (["吧台", "咖啡", "咖啡區", "咖啡座", "酒吧"], 700.0),
            (["前台", "櫃台", "大廳", "接待區", "大堂"], 660.0),
            (["更衣", "更衣間", "更衣室", "衣帽"], 400.0),
            (["儲藏", "儲藏室", "庫房", "倉庫"], 450.0),
            (["玄關", "走道", "走廊", "通道", "過道"], 450.0),
            (["主臥", "主臥室", "套房"], 520.0),
            (["次臥", "女兒房", "小孩房", "男孩房", "兒子房", "傭人房", "傭人", "管家", "客房", "值班室", "臥室", "臥房", "個人房", "個人室", "店鋪", "營業空間", "音響中心"], 500.0),
            (["書房", "閱覽室"], 500.0),
            (["客廳", "起居室"], 550.0),
            (["餐廳", "用餐區", "飯廳"], 600.0),
            (["廚房", "中央廚房"], 700.0),
            (["檔案室", "機房", "設備房", "伺服器", "電腦房", "機櫃"], 650.0)
        ]
    return rules

DYNAMIC_EXCEL_LOAD_RULES = load_fuzzy_rules_from_excel()

# 🎯 雙階段高精準模糊搜尋引擎 (子字串包含 + difflib SequenceMatcher 相似度比對)
def get_base_load_by_name(space_name: str) -> tuple[float, bool]:
    if not space_name:
        return 500.0, True

    raw_name = space_name.strip()
    clean_name = re.sub(r'[^\w\u4e00-\u9fa5]', '', raw_name)
    if not clean_name:
        clean_name = raw_name

    # 第一階段：子字串雙向包含匹配 (包含簡繁與前綴/後綴，如「2F玄關+走道」、「董事長辦公室」)
    for keywords, load in DYNAMIC_EXCEL_LOAD_RULES:
        for kw in keywords:
            if kw and (kw in clean_name or clean_name in kw):
                return float(load), False

    # 第二階段：difflib SequenceMatcher 文字特徵模糊相似度演算法
    best_score = 0.0
    best_load = 500.0

    for keywords, load in DYNAMIC_EXCEL_LOAD_RULES:
        for kw in keywords:
            if not kw:
                continue
            score = difflib.SequenceMatcher(None, clean_name, kw).ratio()
            if score > best_score:
                best_score = score
                best_load = float(load)

    # 相似度 > 30% 即判定模糊匹配成功！
    if best_score >= 0.30:
        return best_load, False

    # 均未命中才判定為完全自訂未定義空間
    return 500.0, True

try:
    from app.services.gemini_service import GeminiService
except ImportError:
    try:
        from services.gemini_service import GeminiService
    except ImportError:
        GeminiService = None

def bake_colored_masks_to_image(image_bytes: bytes, spaces: list) -> str:
    try:
        import cv2
        import numpy as np
        import base64

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return ""

        h, w, _ = img.shape
        overlay = img.copy()

        COLOR_HEX_MAP = {
            "#EAB308": (8, 179, 234),   # Yellow BGR
            "#3B82F6": (246, 130, 59),  # Blue BGR
            "#22C55E": (94, 197, 34),   # Green BGR
            "#EC4899": (153, 72, 236),  # Pink BGR
            "#FF8800": (0, 136, 255),   # Orange BGR
        }

        for s in spaces:
            poly = s.get("polygon")
            hex_color = (s.get("box_color") or "#FF8800").upper()
            bgr = COLOR_HEX_MAP.get(hex_color, (0, 136, 255))
            if poly and isinstance(poly, list) and len(poly) >= 3:
                pts = np.array([[(pt[0] / 1000.0) * w, (pt[1] / 1000.0) * h] for pt in poly], dtype=np.int32)
                cv2.fillPoly(overlay, [pts], bgr)
                cv2.polylines(img, [pts], isClosed=True, color=bgr, thickness=max(2, int(w / 300)))

        alpha = 0.38
        cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

        _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"
    except Exception as e:
        print(f"[Backend] Mask baking warning: {e}")
        return ""

# 🎯 圖面解析路由 (完全對齊 VV17 雙軌智慧策略引擎 + 官方 Excel 負荷表與大金配機)
@router.post("/upload-layout")
async def upload_layout(
    file: UploadFile = File(...),
    case_type: str = Form("1"),
    paper_size: str = Form("A3"),
    scale_ratio: str = Form("1:100")
):
    print("\n[Backend] Received upload request...")
    print(f"[Backend] Filename: {file.filename}, Paper Size: {paper_size}, Scale: {scale_ratio}")
    print(f"[Backend] API key loaded: {'Yes' if API_KEY else 'No'}")
    
    if not API_KEY:
        raise HTTPException(status_code=500, detail="錯誤：後端找不到有效的 config.env 或 GEMINI_API_KEY 設定。")

    try:
        file_bytes = await file.read()
        filename_lower = file.filename.lower()
        final_image_bytes = None
        
        # 💥 預先將圖面轉為高解析度 JPEG 以利前端網頁 1:1 純圖檔展示
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
        elif filename_lower.endswith('.dxf'):
            # DXF 為純 CAD 向量文字檔，跳過 PIL Image.open
            final_image_bytes = file_bytes
        else:
            img = Image.open(io.BytesIO(file_bytes))
            max_size = 1600
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            img_byte_arr = io.BytesIO()
            img.convert('RGB').save(img_byte_arr, format='JPEG', quality=85)
            final_image_bytes = img_byte_arr.getvalue()

        # 🎯 核心升級：抽離 PDF / 圖片上 100% 精確貼合之紅色 PLINE 向量多邊形頂點
        red_polygons = []
        try:
            from app.services.redline_extractor_service import RedlineExtractorService
            if filename_lower.endswith('.pdf') or file.content_type == 'application/pdf':
                red_polygons = RedlineExtractorService.extract_red_polygons_from_pdf(file_bytes)
            else:
                red_polygons = RedlineExtractorService.extract_red_polygons_from_image(final_image_bytes)
            print(f"[Backend] 成功提取到 {len(red_polygons)} 個 100% 精確向量紅框 PLINE 多邊形。")
        except Exception as ex:
            print(f"[Backend] 紅色 PLINE 向量提取提示: {ex}")
            red_polygons = []

        # 🎯 雙軌強大相容：若上傳為原生的 .dxf / CAD 檔，啟用 CADSpaceAnalyzer 算量與即時繪圖
        if filename_lower.endswith('.dxf'):
            from app.services.vector_segmentation_service import VectorSegmentationService
            dxf_spaces, preview_base64 = VectorSegmentationService.process_dxf(file_bytes)
            
            results = []
            for s in dxf_spaces:
                name = s["space_name"]
                area_m2 = s["area_m2"]
                area_ping = s["area_ping"]
                polygon = s["norm_polygon"]
                
                base_suggested, _ = get_base_load_by_name(name)
                total_cooling_load_kcal = round(float(area_ping) * base_suggested)
                total_load_kw = total_cooling_load_kcal / 860.0
                model_name, qty, cap_kw = auto_select_equipment_v15_backend(total_load_kw, "VRV")
                
                results.append({
                    "space_name": name,
                    "area_m2": float(area_m2),
                    "area_ping": float(area_ping),
                    "system_type": "VRV",
                    "base_suggested_load": float(base_suggested),
                    "final_kcal_per_ping": float(base_suggested),
                    "total_cooling_load_kcal": float(total_cooling_load_kcal),
                    "recommended_model": model_name,
                    "qty": int(qty),
                    "cap_kw": float(cap_kw),
                    "selected": True,
                    "polygon": polygon,
                    "calc_basis": "VRV",
                    "modifiers": []
                })
            return {"status": "success", "spaces": results, "preview_url": preview_base64}

        # 🎯 核心升級：調用 VV17 智慧策略引擎 (Rule 1/2/3/4 四防線 + pdfplumber 數據流 & XChange Hints 註解)
        if GeminiService:
            parsed_spaces = await GeminiService.analyze_floorplan(file_bytes, file.filename)
        else:
            parsed_spaces = []

        results = []
        for space in parsed_spaces:
            if not isinstance(space, dict):
                continue

            name = str(space.get("space_name") or space.get("name") or "未命名空間").strip()
            system_spec = str(space.get("system_spec") or space.get("system_type") or "VRV").strip()
            
            raw_area = float(space.get("area_raw") or space.get("area_m2") or space.get("area_ping") or 0.0)
            unit_str = str(space.get("unit") or "m2").strip()

            # 🎯 單位精確匹配：若識別單位為 P 或 坪 (如手寫 10P, 15P, 3P, 1.5P)
            # 則 raw_area 必然是「坪數」，正確填入 area_ping 並精確換算成 area_m2 (÷ 0.3025)！
            if unit_str in ["P", "坪", "p"] or "P" in unit_str or "坪" in unit_str:
                area_ping = round(raw_area, 2)
                area_m2 = round(area_ping / 0.3025, 2)
            else:
                # 識別單位為 m2 或 ㎡ (如 20.1m2, 38m2, 43.4m2)，raw_area 為平方米
                area_m2 = round(raw_area, 2)
                area_ping = round(area_m2 * 0.3025, 2)
            
            # 🎯 雙階段模糊搜尋動態加載《空調負荷基準表.xlsx》負荷
            base_suggested, is_unknown = get_base_load_by_name(name)
            
            # 🎯 以精準查表值連動計算冷房總需求數字
            total_cooling_load_kcal = round(float(area_ping) * base_suggested)
            total_load_kw = total_cooling_load_kcal / 860.0

            # 🎯 大金設備自動匹配演算
            model_name, qty, cap_kw = auto_select_equipment_v15_backend(total_load_kw, system_spec)

            # 多重防線解析 polygon / box_2d (統一輸出 [x, y] 標準幾何座標)
            polygon = space.get("polygon") or space.get("points") or []
            if red_polygons and len(results) < len(red_polygons):
                polygon = [[pt[0], pt[1]] for pt in red_polygons[len(results)]]
            
            box_2d = space.get("box_2d") or space.get("location") or space.get("bbox") or space.get("bounding_box") or []
            if (not polygon or not isinstance(polygon, list) or len(polygon) < 3) and isinstance(box_2d, list) and len(box_2d) == 4 and any(box_2d):
                try:
                    ymin, xmin, ymax, xmax = [float(v) for v in box_2d]
                    if max(ymin, xmin, ymax, xmax) <= 1.0:
                        ymin, xmin, ymax, xmax = ymin * 1000, xmin * 1000, ymax * 1000, xmax * 1000

                    ymin = max(0.0, min(1000.0, ymin))
                    xmin = max(0.0, min(1000.0, xmin))
                    ymax = max(0.0, min(1000.0, ymax))
                    xmax = max(0.0, min(1000.0, xmax))

                    polygon = [[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]]
                except Exception:
                    polygon = []
            elif not isinstance(polygon, list) or len(polygon) < 3:
                polygon = []

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
                "is_unknown_space": is_unknown,
                "polygon": polygon,
                "box_color": space.get("box_color") or ""
            })
            
        # 🎯 第二防線：若無文字標籤/手繪彩圖，呼叫 FloorPlanVectorAnalyzer 自動抓取結構牆內緣橘色框線
        valid_poly_count = sum(1 for r in results if r.get("polygon") and len(r["polygon"]) >= 3)
        if valid_poly_count == 0:
            try:
                from app.services.cv_vector_analyzer import FloorPlanVectorAnalyzer
                analyzer = FloorPlanVectorAnalyzer()
                vec_preview_base64, vec_spaces = analyzer.analyze_floor_plan(
                    final_image_bytes,
                    paper_size=paper_size,
                    scale=scale_ratio
                )
                if vec_spaces:
                    results = []
                    for s in vec_spaces:
                        sqm = s["area_sqm"]
                        ping = s["area_ping"]
                        name = s["room_name"]
                        pts = s["points"]

                        base_suggested, _ = get_base_load_by_name(name)
                        total_cooling_load_kcal = round(float(ping) * base_suggested)
                        total_load_kw = total_cooling_load_kcal / 860.0
                        model_name, qty, cap_kw = auto_select_equipment_v15_backend(total_load_kw, "VRV")

                        results.append({
                            "space_name": name,
                            "area_m2": float(sqm),
                            "area_ping": float(ping),
                            "system_type": "VRV",
                            "base_suggested_load": float(base_suggested),
                            "final_kcal_per_ping": float(base_suggested),
                            "total_cooling_load_kcal": float(total_cooling_load_kcal),
                            "recommended_model": str(model_name),
                            "qty": int(qty),
                            "cap_kw": float(cap_kw),
                            "selected": True,
                            "polygon": pts,
                            "box_color": "#FF8800"
                        })
                    if vec_preview_base64:
                        return {
                            "spaces": results,
                            "image_preview": vec_preview_base64,
                            "is_blank_plan": True
                        }
            except Exception as cv_err:
                print(f"[Backend] FloorPlanVectorAnalyzer 分析提醒: {cv_err}")

        print(f"[Backend] Successfully parsed {len(results)} spaces.")
        annotated_preview = bake_colored_masks_to_image(final_image_bytes, results)
        image_base64 = base64.b64encode(final_image_bytes).decode('utf-8')
        is_blank_plan = filename_lower.endswith(('.jpg', '.jpeg', '.png')) or "plan_g" in filename_lower or "plan g" in filename_lower
        return {
            "spaces": results,
            "image_preview": annotated_preview if annotated_preview else f"data:image/jpeg;base64,{image_base64}",
            "is_blank_plan": is_blank_plan
        }

    except Exception as e:
        import traceback
        print("[Backend Error] Stacktrace:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"圖面視覺辨識解析失敗: {str(e)}")

    except Exception as e:
        import traceback
        print("🔴 【圖面解析出錯詳細軌跡】:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"【後端運行錯誤診斷】: {str(e)}")


# 🎯 Excel 匯出路由 (完全遵照經理指示，自 D9 欄位起點乾淨帶入)
@router.post("/export-excel")
async def export_excel(payload: ExportRequest):
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        root_dir = os.path.abspath(os.path.join(base_dir, ".."))

        template_candidates = [
            os.path.join(base_dir, "product_database", "選機表-.xlsx"),
            os.path.join(base_dir, "選機表-.xlsx"),
            os.path.join(root_dir, "選機表-.xlsx"),
            os.path.abspath("backend/product_database/選機表-.xlsx"),
            os.path.abspath("backend/選機表-.xlsx"),
            os.path.abspath("選機表-.xlsx")
        ]

        template_path = None
        for candidate in template_candidates:
            if os.path.exists(candidate):
                template_path = candidate
                break

        if not template_path:
            raise FileNotFoundError("找不到官方『選機表-.xlsx』範本檔案！請確認 product_database/選機表-.xlsx 存在。")

        wb = openpyxl.load_workbook(template_path)
        sheet = wb.active
        
        start_row = 9  
        
        for i, row_data in enumerate(payload.data):
            current_row = start_row + i
            
            display_name = row_data.space_name
            if "檔率" in display_name:
                display_name = display_name.replace("檔率", "檔案室")
                
            area_ping = row_data.area_ping
            area_m2 = row_data.area_m2

            calc_basis = row_data.final_kcal_per_ping if (row_data.final_kcal_per_ping and row_data.final_kcal_per_ping > 0) else row_data.base_suggested_load
            if not calc_basis or calc_basis == 0:
                calc_basis = 500.0

            # 🎯 嚴格遵循 VV17 歷史大金官方選機表指定欄位對應規則填入：
            sheet.cell(row=current_row, column=1).value = "2F"                  # Column A: 樓層
            sheet.cell(row=current_row, column=4).value = display_name           # Column D: 空間名稱
            sheet.cell(row=current_row, column=5).value = area_m2                # Column E: 平方公尺 (㎡)
            sheet.cell(row=current_row, column=6).value = area_ping              # Column F: 坪數 (P)
            sheet.cell(row=current_row, column=8).value = calc_basis             # Column H: 冷房負荷基準 (kcal/h/坪)

            # 🎯 Column K (11): kW/坪
            kw_per_ping = round(calc_basis / 860.0, 2)
            cell_k = sheet.cell(row=current_row, column=11)
            cell_k.value = kw_per_ping
            cell_k.number_format = '0.00'

            # 🎯 Column L (12): 估算總需求 kW
            total_load_kw = round(area_ping * kw_per_ping, 1)
            sheet.cell(row=current_row, column=12).value = total_load_kw

            # 🎯 Column M (13): 估算總需求 kcal
            sheet.cell(row=current_row, column=13).value = row_data.total_cooling_load_kcal

            # 🎯 Column N (14) & O (15): 型號與台數
            sheet.cell(row=current_row, column=14).value = row_data.recommended_model
            sheet.cell(row=current_row, column=15).value = row_data.qty

            # 🎯 單機能力 cap_kw & cap_kcal (Column P & Q)
            cap_kw = row_data.cap_kw if row_data.cap_kw > 0 else lookup_cap_kw(row_data.recommended_model)
            cap_kcal = round(cap_kw * 860.0, 1)

            sheet.cell(row=current_row, column=16).value = cap_kcal              # Column P (16): 單機能力 (kcal/h)
            sheet.cell(row=current_row, column=17).value = cap_kw                # Column Q (17): 單機能力 (kW)

            # 🎯 Column W (23) & X (24): 總冷房能力 kcal & kW
            qty = row_data.qty if row_data.qty > 0 else 1
            sheet.cell(row=current_row, column=23).value = float(qty * cap_kcal)  # Column W (23)
            sheet.cell(row=current_row, column=24).value = float(qty * cap_kw)    # Column X (24)

            # 🎯 Column AB (28) & AC (29): 每坪平均能力 kcal & kW
            if area_ping > 0:
                sheet.cell(row=current_row, column=28).value = int(round(cap_kcal / area_ping, 0)) # Column AB (28)
                sheet.cell(row=current_row, column=29).value = round(cap_kw / area_ping, 1)        # Column AC (29)

            # 🎯 Column AD (30): 冷房負擔坪數/冷凍噸
            if (qty * cap_kw) > 0:
                sheet.cell(row=current_row, column=30).value = round(area_ping / ((qty * cap_kw) / 3.516), 1) # Column AD (30)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        # 🎯 動態檔名：選機表-"匯入的案名".xlsx
        raw_case_name = payload.filename.strip() if payload.filename else ""
        if raw_case_name:
            case_name = os.path.splitext(os.path.basename(raw_case_name))[0]
        else:
            case_name = "規劃案"

        excel_download_name = f"選機表-{case_name}.xlsx"

        from urllib.parse import quote
        encoded_filename = quote(excel_download_name)
        
        return StreamingResponse(
            output, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
        )
        
    except Exception as e:
        import traceback
        print("[Backend Error] Excel export failed traceback:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"底稿寫入失敗：{str(e)}")


class SplitSpaceRequest(BaseModel):
    space: Dict[str, Any]
    p1: List[float]
    p2: List[float]

# 🎯 4. Anti-Gravity 互動校正介面 API (開放空間劃線分割)
@router.post("/split-space")
async def split_space_endpoint(payload: SplitSpaceRequest):
    try:
        from app.services.cv_segmentation_service import CVSegmentationService
        p1_tuple = (payload.p1[0], payload.p1[1]) if len(payload.p1) >= 2 else (0.0, 0.0)
        p2_tuple = (payload.p2[0], payload.p2[1]) if len(payload.p2) >= 2 else (100.0, 100.0)
        
        split_results = CVSegmentationService.split_space_by_line(payload.space, p1_tuple, p2_tuple)
        
        final_spaces = []
        for sp in split_results:
            area_m2 = sp.get("area_m2", 0.0)
            area_ping = round(area_m2 * 0.3025, 2)
            space_name = sp.get("name", "開放空間")
            
            base_load, _ = get_base_load_by_name(space_name)
            total_load_kcal = round(area_ping * base_load, 1)
            total_load_kw = total_load_kcal / 860.0
            
            model, qty, cap_kw = auto_select_equipment_v15_backend(total_load_kw, "VRV")
            
            sp["ping"] = area_ping
            sp["base_suggested_load"] = base_load
            sp["final_kcal_per_ping"] = base_load
            sp["total_cooling_load_kcal"] = total_load_kcal
            sp["recommended_model"] = model
            sp["qty"] = qty
            sp["cap_kw"] = cap_kw
            final_spaces.append(sp)
            
        return {"status": "success", "spaces": final_spaces}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"開放空間分割失敗：{str(e)}")
