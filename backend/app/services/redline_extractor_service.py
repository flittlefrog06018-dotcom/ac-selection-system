import fitz  # PyMuPDF
import cv2
import numpy as np
from typing import List, Tuple

class RedlineExtractorService:
    """
    專用紅色/紫紅色 PLINE 向量多邊形提取服務 (統一輸出標準 [x, y] 座標系統)
    """

    @staticmethod
    def extract_red_polygons_from_pdf(pdf_bytes: bytes) -> List[List[Tuple[float, float]]]:
        """
        從 PDF 向量圖元中提取筆劃為紅色/品紅色的多邊形頂點 [(x1,y1), (x2,y2), ...] (0~1000 歸一化)
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            return []

        page = doc[0]
        rect = page.rect
        page_width = rect.width
        page_height = rect.height

        drawings = page.get_drawings()
        red_polygons = []

        for item in drawings:
            color = item.get("color")
            is_red_stroke = False
            if color:
                r, g, b = color[0], color[1], color[2]
                if (r > 0.6 and g < 0.4 and b < 0.5) or (r > 0.7 and b > 0.4 and g < 0.3):
                    is_red_stroke = True

            if is_red_stroke:
                pts = []
                for item_path in item.get("items", []):
                    cmd = item_path[0]
                    if cmd == "l":  # line
                        p1, p2 = item_path[1], item_path[2]
                        # 歸一化至 0 ~ 1000 [x, y] 幾何座標
                        pts.append((round(p1.x / page_width * 1000, 1), round(p1.y / page_height * 1000, 1)))
                        pts.append((round(p2.x / page_width * 1000, 1), round(p2.y / page_height * 1000, 1)))
                    elif cmd == "re":  # rectangle
                        r_box = item_path[1]
                        pts.append((round(r_box.x0 / page_width * 1000, 1), round(r_box.y0 / page_height * 1000, 1)))
                        pts.append((round(r_box.x1 / page_width * 1000, 1), round(r_box.y0 / page_height * 1000, 1)))
                        pts.append((round(r_box.x1 / page_width * 1000, 1), round(r_box.y1 / page_height * 1000, 1)))
                        pts.append((round(r_box.x0 / page_width * 1000, 1), round(r_box.y1 / page_height * 1000, 1)))

                if len(pts) >= 3:
                    unique_pts = []
                    for pt in pts:
                        if not unique_pts or (abs(unique_pts[-1][0] - pt[0]) > 2 or abs(unique_pts[-1][1] - pt[1]) > 2):
                            unique_pts.append(pt)
                    if len(unique_pts) >= 3:
                        red_polygons.append(unique_pts)

        return red_polygons

    @staticmethod
    def extract_red_polygons_from_image(image_bytes: bytes) -> List[List[Tuple[float, float]]]:
        """
        針對點陣圖 (JPG/PNG)，使用 OpenCV HSV 擷取紅框多邊形 [(x,y), ...]
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
                epsilon = 0.015 * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, True)
                pts = []
                for pt in approx:
                    x, y = pt[0][0], pt[0][1]
                    pts.append((round(x / w * 1000, 1), round(y / h * 1000, 1)))
                if len(pts) >= 3:
                    polygons.append(pts)

        return polygons
