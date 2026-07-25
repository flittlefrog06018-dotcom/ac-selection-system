import io
import math
import base64
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
    4. 即時繪製 Base64 高解析度圖面預覽 PNG 供前端展示
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

    def _entity_to_linestrings(self, entity: Any) -> List[LineString]:
        lines = []
        try:
            if entity.dxftype() == 'LINE':
                lines.append(LineString([entity.dxf.start[:2], entity.dxf.end[:2]]))
            elif entity.dxftype() in ['LWPOLYLINE', 'POLYLINE']:
                points = [p[:2] for p in entity.get_points()]
                if len(points) >= 2:
                    lines.append(LineString(points))
        except Exception:
            pass
        return lines

    def extract_elements(
        self,
        wall_layer_names: List[str] = ['WALL', '牆', '隔牆', 'A-WALL', 'WALLS'],
        door_layer_names: List[str] = ['DOOR', '門', 'A-DOOR', 'DOORS']
    ):
        """
        1. 兼顧圖層辨識與全圖防呆抓取的二階段線段提取邏輯 (Robust Layer Filtering)
        """
        found_wall = False
        
        for entity in self.msp:
            if entity.dxftype() in ['LINE', 'LWPOLYLINE', 'POLYLINE']:
                layer = str(entity.dxf.layer).upper()
                lines = self._entity_to_linestrings(entity)
                
                if any(w in layer for w in wall_layer_names):
                    self.wall_lines.extend(lines)
                    found_wall = True
                elif any(d in layer for d in door_layer_names):
                    self.door_lines.extend(lines)

        if not found_wall:
            print("[Backend DXF] ⚠️ 未匹配到標準 WALL 圖層名稱，啟動『全圖線段連通性防呆抓取』模式...")
            for entity in self.msp:
                if entity.dxftype() in ['LINE', 'LWPOLYLINE', 'POLYLINE']:
                    lines = self._entity_to_linestrings(entity)
                    self.wall_lines.extend(lines)

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

        total_bounds = all_boundaries.bounds if all_boundaries else (0, 0, 1000, 1000)
        minx, miny, maxx, maxy = total_bounds
        dx = (maxx - minx) if (maxx - minx) > 0 else 1.0
        dy = (maxy - miny) if (maxy - miny) > 0 else 1.0

        spaces = []
        for idx, poly in enumerate(polygons):
            area_m2 = poly.area / 1000000.0 if poly.area > 10000 else poly.area
            
            if area_m2 >= 1.5:  # 過濾碎片
                ping = round(area_m2 * 0.3025, 2)
                centroid = poly.centroid

                ext_coords = list(poly.exterior.coords)
                norm_polygon = []
                for pt in ext_coords:
                    nx = round((pt[0] - minx) / dx * 1000, 1)
                    ny = round((pt[1] - miny) / dy * 1000, 1)
                    norm_polygon.append([nx, ny])

                spaces.append({
                    "id": f"空間_{idx+1}",
                    "space_name": f"淨空間_{idx+1}",
                    "polygon": poly,
                    "norm_polygon": norm_polygon,
                    "area_m2": round(area_m2, 2),
                    "area_ping": ping,
                    "centroid_m": [centroid.x, centroid.y],
                    "centroid_norm": [round((centroid.x - minx) / dx * 1000, 1), round((centroid.y - miny) / dy * 1000, 1)]
                })

        return spaces

    def render_to_png_base64(self, virtual_thresholds: List[LineString]) -> str:
        """
        4. 即時將 CAD DXF 向量渲染為高畫質 Base64 PNG 供網頁畫布 100% 顯示
        """
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
        fig.patch.set_facecolor('#020617')
        ax.set_facecolor('#020617')

        # 繪製牆線 (亮灰線)
        for line in self.wall_lines:
            x, y = line.xy
            ax.plot(x, y, color='#cbd5e1', linewidth=1.2)

        # 繪製補門線 (藍綠虛線)
        for v_line in virtual_thresholds:
            x, y = v_line.xy
            ax.plot(x, y, color='#38bdf8', linestyle='--', linewidth=1.5)

        ax.axis('equal')
        ax.axis('off')

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, facecolor=fig.get_facecolor())
        plt.close(fig)

        buf.seek(0)
        base64_str = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{base64_str}"

class VectorSegmentationService:
    """
    高階整合 API 包裝器 (包含 DXF 數據計算與繪圖預覽 Base64 產生)
    """
    @staticmethod
    def process_dxf(dxf_bytes: bytes) -> Tuple[List[Dict[str, Any]], str]:
        analyzer = CADSpaceAnalyzer(dxf_bytes=dxf_bytes)
        analyzer.extract_elements()
        virtual_lines = analyzer.auto_seal_doors(max_door_width=1200)
        spaces = analyzer.compute_net_spaces(virtual_lines)
        preview_base64 = analyzer.render_to_png_base64(virtual_lines)
        return spaces, preview_base64
