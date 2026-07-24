import math
from typing import List, Tuple, Dict, Any
import ezdxf
from shapely.geometry import LineString, Polygon, MultiLineString, Point
from shapely.ops import polygonize, unary_union

class VectorSegmentationService:
    """
    第一階段 CAD/DXF 向量圖資核心演算法：
    1. 使用 ezdxf 提取向量牆體圖元 (LINE, ARC, LWPOLYLINE)
    2. 使用 Shapely 自動尋找牆體開口並補齊門縫線 (Door Gap Closure)
    3. 自動生成閉合多邊形並求解純內淨面積 (Net Area Calculation)
    """

    @staticmethod
    def extract_lines_from_dxf_bytes(dxf_bytes: bytes) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """
        利用 ezdxf 從 DXF 檔位元流提取所有向量線段 (x1, y1) -> (x2, y2)
        """
        import io
        text_stream = io.StringIO(dxf_bytes.decode("utf-8", errors="ignore"))
        doc = ezdxf.read(text_stream)
        msp = doc.modelspace()

        raw_lines = []

        # 1. 提取 LINE
        for e in msp.query('LINE'):
            p1 = (e.dxf.start.x, e.dxf.start.y)
            p2 = (e.dxf.end.x, e.dxf.end.y)
            raw_lines.append((p1, p2))

        # 2. 提取 LWPOLYLINE 節點
        for e in msp.query('LWPOLYLINE'):
            points = list(e.get_points(format='xy'))
            for i in range(len(points) - 1):
                raw_lines.append((points[i], points[i+1]))
            if e.is_closed and len(points) > 2:
                raw_lines.append((points[-1], points[0]))

        return raw_lines

    @staticmethod
    def auto_close_door_gaps(
        lines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        min_door_dist: float = 600.0,  # 門寬最小範圍 (mm)
        max_door_dist: float = 1200.0  # 門寬最大範圍 (mm)
    ) -> Tuple[List[LineString], List[LineString]]:
        """
        利用 Shapely 搜尋牆體懸空端點，自動補齊門縫橋接線段 (Bridge Lines)
        """
        shapely_lines = [LineString([p1, p2]) for p1, p2 in lines if p1 != p2]
        if not shapely_lines:
            return [], []

        # 收集所有端點
        endpoints = []
        for line in shapely_lines:
            coords = list(line.coords)
            endpoints.append(Point(coords[0]))
            endpoints.append(Point(coords[-1]))

        # 自動尋找距離在 60cm ~ 120cm 之間的缺口端點對 (門縫開口)
        door_bridge_lines = []
        n = len(endpoints)
        visited = set()

        for i in range(n):
            for j in range(i + 1, n):
                p_i = endpoints[i]
                p_j = endpoints[j]
                dist = p_i.distance(p_j)
                
                # 若端點間距介於標準門寬 (600mm ~ 1200mm)
                if min_door_dist <= dist <= max_door_dist:
                    pair_key = tuple(sorted([i, j]))
                    if pair_key not in visited:
                        visited.add(pair_key)
                        bridge = LineString([p_i.coords[0], p_j.coords[0]])
                        door_bridge_lines.append(bridge)

        # 結合原牆體線條與補強門縫線
        all_lines = shapely_lines + door_bridge_lines
        return all_lines, door_bridge_lines

    @staticmethod
    def calculate_net_areas_from_lines(
        all_lines: List[LineString],
        scale_mm_to_m: float = 0.001
    ) -> List[Dict[str, Any]]:
        """
        使用 Shapely polygonize 自動轉化為閉合區域並計算內淨面積
        """
        if not all_lines:
            return []

        merged_lines = unary_union(all_lines)
        polygons = list(polygonize(merged_lines))

        spaces = []
        for idx, poly in enumerate(polygons):
            # 轉換為公尺與坪數 (預設單位 mm -> m)
            area_m2 = poly.area * (scale_mm_to_m ** 2)
            
            # 過濾微小雜訊孔洞 (如 < 1.0 m²)
            if area_m2 >= 1.0:
                ping = round(area_m2 * 0.3025, 2)
                bounds = poly.bounds
                centroid = poly.centroid
                
                spaces.append({
                    "space_id": f"spatial_{idx+1}",
                    "name": f"淨空間 {idx+1}",
                    "area_m2": round(area_m2, 2),
                    "ping": ping,
                    "bounds": [bounds[0], bounds[1], bounds[2], bounds[3]],
                    "centroid": [centroid.x, centroid.y],
                    "is_large_space": area_m2 >= 75.0  # 是否需要 Anti-Gravity 劃線切割提示
                })

        return spaces
