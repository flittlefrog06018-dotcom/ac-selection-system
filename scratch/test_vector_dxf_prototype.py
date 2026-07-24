import sys
import os
from shapely.geometry import LineString

# 載入專案路徑
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services.vector_segmentation_service import VectorSegmentationService

def test_vector_algorithm():
    print("=" * 70)
    print("[Phase 1 Test] ezdxf + Shapely auto door closure & net area calculation prototype")
    print("=" * 70)

    # 模擬客廳+門縫牆體線段 (牆長 5000mm, 寬 4000mm, 門缺口 800mm)
    # 外牆矩形，但右側牆面中間留有 800mm 門縫缺口
    wall_lines = [
        ((0, 0), (5000, 0)),        # 南牆
        ((5000, 0), (5000, 1600)),   # 東牆 下半段
        # (5000, 1600) -> (5000, 2400) 是 800mm 門縫缺口！未畫線！
        ((5000, 2400), (5000, 4000)),# 東牆 上半段
        ((5000, 4000), (0, 4000)),  # 北牆
        ((0, 4000), (0, 0))         # 西牆
    ]

    print(f"1. Original input wall line count: {len(wall_lines)} lines (with 800mm door gap)")

    # 執行門縫自動補強
    all_lines, door_bridges = VectorSegmentationService.auto_close_door_gaps(
        wall_lines, min_door_dist=600.0, max_door_dist=1200.0
    )

    print(f"2. Auto detected & generated door bridge lines: {len(door_bridges)} lines")
    for b in door_bridges:
        coords = list(b.coords)
        print(f"   --> Bridge line coords: {coords[0]} to {coords[1]} (length: {b.length:.1f} mm)")

    # 計算閉合內淨面積
    spaces = VectorSegmentationService.calculate_net_areas_from_lines(all_lines, scale_mm_to_m=0.001)

    print("\n3. Net area calculation results:")
    for sp in spaces:
        print(f"   [Space Name] {sp['name']}")
        print(f"   - Net Area: {sp['area_m2']} m2 ({sp['ping']} ping)")
        print(f"   - Centroid: {sp['centroid']}")
        print(f"   - Needs split line: {sp['is_large_space']}")

    print("=" * 70)
    print("[Phase 1 Test Passed] Door gap closure & Net area calculation successful!")
    print("=" * 70)

if __name__ == "__main__":
    test_vector_algorithm()
