import io
import math
from typing import List, Tuple, Dict, Any
import ezdxf
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import polygonize, unary_union

class CADSpaceAnalyzer:
    """
    精確 DXF/CAD 向量空間分析與門縫自動補強服務 (使用者權威 CAD 演算法)
    1. 提取 DXF 中的牆圖層 (WALL, 牆, 隔牆, A-WALL) 與門圖層 (DOOR, 門, A-DOOR)
    2. 自動補齊門縫線 (Virtual Thresholds)，使牆體形成完全閉合區域
    3. 拓撲幾何組合 (unary_union + polygonize) 求解內淨空間面積 (Net Area m² 與 坪數)
    """

    def __init__(self, dxf_bytes: bytes = None, dxf_path: str = None):
        if dxf_bytes:
            text_stream = io.StringIO(dxf_bytes.decode("utf-8", errors="ignore"))
            self.doc = ezdxf.read(text_stream)
        elif dxf_path:
            self.doc = ezdxf.readfile(dxf_path)
        else:
            raise ValueError("必須提供 dxf_bytes 或 dxf_path")

        self.msp = self.doc.modelspace()
        self.wall_lines: List[LineString] = []
        self.door_lines: List[LineString] = []

    def extract_elements(
        self,
        wall_layer_names: List[str] = ['WALL', '牆', '隔牆', 'A-WALL'],
        door_layer_names: List[str] = ['DOOR', '門', 'A-DOOR']
    ):
        """
        1. 提取 DXF 圖檔中的牆線與門線
        """
        for entity in self.msp:
            if entity.dxftype() in ['LINE', 'LWPOLYLINE', 'POLYLINE']:
                layer = str(entity.dxf.layer).upper()
                
                lines = []
                if entity.dxftype() == 'LINE':
                    lines.append(LineString([entity.dxf.start[:2], entity.dxf.end[:2]]))
                else:  # LWPOLYLINE / POLYLINE
                    points = [p[:2] for p in entity.get_points()]
                    if len(points) >= 2:
                        lines.append(LineString(points))

                for line in lines:
                    if any(w in layer for w in wall_layer_names):
                        self.wall_lines.append(line)
                    elif any(d in layer for d in door_layer_names):
                        self.door_lines.append(line)
                    else:
                        # 預設將未分類之結構線視為潛在牆線
                        self.wall_lines.append(line)

    def auto_seal_doors(self, max_door_width: float = 1200.0) -> List[LineString]:
        """
        2. 自動補齊門縫 (Virtual Boundary)：取起終點連成門界線
        """
        virtual_thresholds = []
        for door in self.door_lines:
            coords = list(door.coords)
            if len(coords) >= 2:
                p1, p2 = coords[0], coords[-1]
                door_gap = LineString([p1, p2])
                if door_gap.length <= max_door_width and door_gap.length > 50:
                    virtual_thresholds.append(door_gap)
        return virtual_thresholds

    def compute_net_spaces(self, virtual_thresholds: List[LineString]) -> List[Dict[str, Any]]:
        """
        3. 拓撲幾何組合 + 尋找內部淨空間 (Net Area)
        """
        all_boundaries = unary_union(self.wall_lines + virtual_thresholds)
        polygons = list(polygonize(all_boundaries))

        # 計算樓層 bounds 以歸一化座標 (0~1000)
        total_bounds = all_boundaries.bounds if all_boundaries else (0, 0, 1000, 1000)
        minx, miny, maxx, maxy = total_bounds
        dx = (maxx - minx) if (maxx - minx) > 0 else 1.0
        dy = (maxy - miny) if (maxy - miny) > 0 else 1.0

        spaces = []
        for idx, poly in enumerate(polygons):
            # 假設 DXF 單位為 mm，計算 m² 與 坪數
            area_m2 = poly.area / 1000000.0 if poly.area > 10000 else poly.area
            
            if area_m2 >= 1.5:  # 過濾碎片
                ping = round(area_m2 * 0.3025, 2)
                centroid = poly.centroid

                # 歸一化 0~1000 幾何多邊形頂點點陣
                ext_coords = list(poly.exterior.coords)
                norm_polygon = []
                for pt in ext_coords:
                    nx = round((pt[0] - minx) / dx * 1000, 1)
                    ny = round((pt[1] - miny) / dy * 1000, 1)
                    norm_polygon.append([nx, ny])

                spaces.append({
                    "id": f"空間_{idx+1}",
                    "space_name": f"淨空間_{idx+1}",
                    "polygon": poly,  # Shapely 物件
                    "norm_polygon": norm_polygon,  # [[x,y], ...]
                    "area_m2": round(area_m2, 2),
                    "area_ping": ping,
                    "centroid_m": [centroid.x, centroid.y],
                    "centroid_norm": [round((centroid.x - minx) / dx * 1000, 1), round((centroid.y - miny) / dy * 1000, 1)]
                })

        return spaces

class VectorSegmentationService:
    """
    高階整合 API 包裝器
    """
    @staticmethod
    def process_dxf(dxf_bytes: bytes) -> List[Dict[str, Any]]:
        analyzer = CADSpaceAnalyzer(dxf_bytes=dxf_bytes)
        analyzer.extract_elements()
        virtual_lines = analyzer.auto_seal_doors(max_door_width=1200)
        return analyzer.compute_net_spaces(virtual_lines)
