import cv2
import numpy as np
import base64
import math
import uuid
from typing import Tuple, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont

class FloorPlanVectorAnalyzer:
    """
    平面圖自動向量邊緣偵測與面積換算分析器 (OpenCV + 結構牆內緣法則)
    1. 門寬校正與紙張物理尺度換算 (Scale Calibration)
    2. HSV 著色區域鎖定 + 11x11 形態學閉運算抹平內部家具細線
    3. cv2.approxPolyDP 正交幾何多邊形逼近與面積計算 (Shoelace)
    4. 描繪 BGR (0, 136, 255) 橘色向量框線與 Centroid 標籤預覽圖生成
    """

    PAPER_SIZES_MM = {
        "A4": (297.0, 210.0),
        "A3": (420.0, 297.0),
        "A2": (594.0, 420.0)
    }

    ORANGE_BGR = (0, 136, 255)
    ORANGE_HEX = "#FF8800"

    def __init__(self, font_path: str = None):
        self.font_path = font_path

    def calculate_meters_per_pixel(
        self,
        img_shape: Tuple[int, int, int],
        paper_size: str = "A3",
        scale: str = "1:100",
        calibration_points: Dict[str, Any] = None
    ) -> float:
        """ 1. 尺度校正 (Scale Calibration) """
        if calibration_points and "p1" in calibration_points and "p2" in calibration_points:
            p1 = calibration_points["p1"]
            p2 = calibration_points["p2"]
            real_cm = float(calibration_points.get("real_cm", 90.0))
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            pixel_dist = math.sqrt(dx * dx + dy * dy)
            if pixel_dist > 0:
                return (real_cm / 100.0) / pixel_dist

        scale_val = 100.0
        if ":" in str(scale):
            try:
                scale_val = float(scale.split(":")[1])
            except Exception:
                scale_val = 100.0
        else:
            try:
                scale_val = float(scale)
            except Exception:
                scale_val = 100.0

        paper_mm_width = self.PAPER_SIZES_MM.get(paper_size.upper(), (420.0, 297.0))[0]
        real_paper_meters_width = (paper_mm_width / 1000.0) * scale_val
        img_w = img_shape[1]
        return real_paper_meters_width / float(img_w)

    def extract_structure_contours(self, img_bgr: np.ndarray) -> List[Tuple[str, np.ndarray]]:
        """ 2. HSV 色彩提取與家具線條抹平 (Morphological Closing 11x11) """
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        img_h, img_w = img_bgr.shape[:2]

        color_ranges = [
            ("空間區域", (0, 25, 120), (179, 255, 255)),
        ]

        detected_spaces = []

        for room_hint_name, lower_b, upper_b in color_ranges:
            mask = cv2.inRange(hsv, np.array(lower_b), np.array(upper_b))

            # 11x11 形態學閉運算抹平內部家具與軟裝線條
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
            closed_mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

            dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            final_mask = cv2.dilate(closed_mask, dilate_kernel, iterations=1)

            contours, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area_px = cv2.contourArea(cnt)
                if area_px < (img_h * img_w * 0.005):
                    continue
                detected_spaces.append((room_hint_name, cnt))

        return detected_spaces

    def polygon_approx_and_measure(
        self,
        contour: np.ndarray,
        m_per_px: float
    ) -> Tuple[List[List[int]], float, float]:
        """ 3. 多邊形擬合 (approxPolyDP) 與幾何換算 """
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.015 * peri, True)

        points = approx.reshape(-1, 2).tolist()
        px_area = cv2.contourArea(approx)
        sqm = round(px_area * (m_per_px ** 2), 2)
        ping = round(sqm * 0.3025, 2)

        return points, sqm, ping

    def render_preview_image(self, img_bgr: np.ndarray, results_json: List[Dict[str, Any]]) -> str:
        """ 4. 描繪 BGR (0, 136, 255) 橘色向量框線預覽圖 """
        canvas = img_bgr.copy()

        for item in results_json:
            pts = np.array(item["points"], dtype=np.int32).reshape((-1, 1, 2))
            
            overlay = canvas.copy()
            cv2.fillPoly(overlay, [pts], (0, 180, 255))
            cv2.addWeighted(overlay, 0.25, canvas, 0.75, 0, canvas)

            cv2.polylines(canvas, [pts], True, self.ORANGE_BGR, thickness=3, lineType=cv2.LINE_AA)

            M = cv2.moments(pts)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                cx, cy = pts[0][0][0], pts[0][0][1]

            label_text = f"{item['room_name']}\n{item['area_sqm']} m² ({item['area_ping']}坪)"
            
            try:
                img_pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
                draw = ImageDraw.Draw(img_pil)
                font = ImageFont.truetype(self.font_path or "arial.ttf", size=16)
                
                bbox = draw.textbbox((cx - 40, cy - 15), label_text, font=font)
                draw.rectangle(bbox, fill=(15, 23, 42, 200), outline=(255, 136, 0))
                draw.text((cx - 35, cy - 12), label_text, fill=(255, 255, 255), font=font)
                
                canvas = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            except Exception:
                cv2.putText(canvas, f"{item['room_name']} {item['area_sqm']}m2", 
                            (cx - 50, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        _, buffer = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        return "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")

    def analyze_floor_plan(
        self,
        image_input,
        paper_size: str = "A3",
        scale: str = "1:100",
        calibration_points: Dict[str, Any] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """ 主 API 對接入口 """
        if isinstance(image_input, str):
            img_bgr = cv2.imread(image_input)
        elif isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            img_bgr = image_input

        if img_bgr is None:
            raise ValueError("無法讀取有效的圖面影像數據。")

        m_per_px = self.calculate_meters_per_pixel(img_bgr.shape, paper_size, scale, calibration_points)
        raw_contours = self.extract_structure_contours(img_bgr)

        results_json = []
        for idx, (hint_name, cnt) in enumerate(raw_contours, 1):
            pts, sqm, ping = self.polygon_approx_and_measure(cnt, m_per_px)
            room_name = f"空間 {idx}"
            
            results_json.append({
                "room_id": f"room_{uuid.uuid4().hex[:6]}",
                "room_name": room_name,
                "box_color": self.ORANGE_HEX,
                "area_sqm": sqm,
                "area_ping": ping,
                "points": pts
            })

        base64_preview = self.render_preview_image(img_bgr, results_json)
        return base64_preview, results_json
