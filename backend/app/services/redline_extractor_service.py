import fitz  # PyMuPDF
import cv2
import numpy as np
from typing import List, Tuple
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

class RedlineExtractorService:
    """
    專用多邊形 (L型/凹型/多元形狀) 向量紅框提取服務
    支援任意形狀多邊形：L 型 (6頂點)、凹字型、凸多邊形，絕不退化為簡易長方形。
    """

    @staticmethod
    def extract_red_polygons_from_pdf(pdf_bytes: bytes) -> List[List[Tuple[float, float]]]:
        """
        從 PDF 的向量圖元中，將所有紅色筆劃 (Stroke Red) 線段聚合成閉合的 L型/凹型 多邊形頂點
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            return []

        page = doc[0]
        rect = page.rect
        page_width = rect.width
        page_height = rect.height

        drawings = page.get_drawings()
        red_lines = []

        for item in drawings:
            color = item.get("color")
            is_red_stroke = False
            if color:
                r, g, b = color[0], color[1], color[2]
                if (r > 0.6 and g < 0.4 and b < 0.5) or (r > 0.7 and b > 0.4 and g < 0.3):
                    is_red_stroke = True

            if is_red_stroke:
                for item_path in item.get("items", []):
                    cmd = item_path[0]
                    if cmd == "l":  # 直線
                        p1, p2 = item_path[1], item_path[2]
                        x1 = round(p1.x / page_width * 1000, 1)
                        y1 = round(p1.y / page_height * 1000, 1)
                        x2 = round(p2.x / page_width * 1000, 1)
                        y2 = round(p2.y / page_height * 1000, 1)
                        if (x1, y1) != (x2, y2):
                            red_lines.append(LineString([(x1, y1), (x2, y2)]))
                    elif cmd == "re":  # 矩形框
                        r_box = item_path[1]
                        x0 = round(r_box.x0 / page_width * 1000, 1)
                        y0 = round(r_box.y0 / page_height * 1000, 1)
                        x1 = round(r_box.x1 / page_width * 1000, 1)
                        y1 = round(r_box.y1 / page_height * 1000, 1)
                        red_lines.append(LineString([(x0, y0), (x1, y0)]))
                        red_lines.append(LineString([(x1, y0), (x1, y1)]))
                        red_lines.append(LineString([(x1, y1), (x0, y1)]))
                        red_lines.append(LineString([(x0, y1), (x0, y0)]))

        if not red_lines:
            return []

        # 使用 Shapely 將相連的紅線段聚合成多邊形 (相容 L型、凹型與複雜形狀)
        merged = unary_union(red_lines)
        polygons = list(polygonize(merged))
        
        red_polygons = []
        for poly in polygons:
            # 取得多邊形的外部閉合頂點邊界
            coords = list(poly.exterior.coords)
            # 簡化重複頂點
            simplified_pts = []
            for pt in coords:
                x, y = round(pt[0], 1), round(pt[1], 1)
                if not simplified_pts or (abs(simplified_pts[-1][0] - x) > 1 or abs(simplified_pts[-1][1] - y) > 1):
                    simplified_pts.append((x, y))
            
            # 去除首尾重複點
            if len(simplified_pts) > 3 and simplified_pts[0] == simplified_pts[-1]:
                simplified_pts.pop()

            if len(simplified_pts) >= 3:
                red_polygons.append(simplified_pts)

        return red_polygons

    @staticmethod
    def extract_red_polygons_from_image(image_bytes: bytes) -> List[List[Tuple[float, float]]]:
        """
        針對點陣圖 (JPG/PNG)，使用 OpenCV 色綵通道抓取任意多邊形 (L型/凹型)
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return []

        h, w = img.shape[:2]
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        mask1 = cv2.inRange(hsv, np.array([0, 70, 70]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([160, 70, 70]), np.array([180, 255, 255]))
        mask3 = cv2.inRange(hsv, np.array([140, 50, 70]), np.array([165, 255, 255]))
        mask = mask1 | mask2 | mask3

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polygons = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > (w * h * 0.002):
                # 採用較精細的多邊形逼近 (不限制點數，可精確描繪 L型與凹型)
                epsilon = 0.008 * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, True)
                pts = []
                for pt in approx:
                    x, y = pt[0][0], pt[0][1]
                    pts.append((round(x / w * 1000, 1), round(y / h * 1000, 1)))
                if len(pts) >= 3:
                    polygons.append(pts)

        return polygons
