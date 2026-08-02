import cv2
import numpy as np
import os

artifacts_dir = r"C:\Users\flitt\.gemini\antigravity-ide\brain\7f6b70e4-e153-4cd2-aff5-2dd9681a0b5e"
src_file = os.path.join(artifacts_dir, "media__1785671682031.jpg")
out_path = os.path.join(artifacts_dir, "v10_exact_wall_aligned_result.jpg")

with open(src_file, "rb") as f:
    data = f.read()
nparr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

h, w, _ = img.shape
overlay = img.copy()

# On photo media__1785671682031.jpg, the floorplan image is centered inside white margins:
# Plan bounds on photo:
# min_x = 0.245 * w, max_x = 0.905 * w
# min_y = 0.210 * h, max_y = 0.678 * h

# Let's define the 4 room polygons in local plan coordinates (0..1000 within floorplan bounds):
# Local Plan Polygons:
# 1. LDKE Yellow:
#    Entryway: x: 740..980, y: 0..270
#    Kitchen: x: 500..740, y: 0..270
#    Living/Dining: x: 500..830, y: 270..1000
#    Hallway (90cm): x: 300..500, y: 560..700
#    Polygon: [[500, 0], [980, 0], [980, 270], [830, 270], [830, 1000], [500, 1000], [500, 700], [300, 700], [300, 560], [500, 560]]

# 2. Bedroom A Pink (Top-Left):
#    Polygon: [[0, 140], [280, 140], [280, 550], [0, 550]]

# 3. Master Bed Blue (Bottom-Left):
#    Polygon: [[0, 560], [290, 560], [290, 1000], [0, 1000]]

# 4. Bedroom B Green (Bottom-Middle):
#    Polygon: [[300, 700], [490, 700], [490, 1000], [300, 1000]]

def map_plan_to_photo(local_pts, w_img, h_img):
    # Floorplan bounds on paper photo
    plan_left = 0.245 * w_img
    plan_right = 0.905 * w_img
    plan_top = 0.210 * h_img
    plan_bottom = 0.678 * h_img
    
    plan_w = plan_right - plan_left
    plan_h = plan_bottom - plan_top
    
    photo_pts = []
    for lx, ly in local_pts:
        px = plan_left + (lx / 1000.0) * plan_w
        py = plan_top + (ly / 1000.0) * plan_h
        photo_pts.append([int(px), int(py)])
    return np.array(photo_pts, dtype=np.int32)

rooms = [
    {
        "name": "公領域 (LDKE: 客廳+餐廳+廚房&玄關整合+90cm走道)",
        "local_poly": [[500, 0], [980, 0], [980, 270], [830, 270], [830, 1000], [500, 1000], [500, 700], [300, 700], [300, 560], [500, 560]],
        "bgr": (8, 179, 234),   # Yellow BGR (#EAB308)
        "stroke_bgr": (0, 140, 180)
    },
    {
        "name": "臥室 A (次臥 A)",
        "local_poly": [[0, 140], [280, 140], [280, 550], [0, 550]],
        "bgr": (153, 72, 236),  # Pink BGR (#EC4899)
        "stroke_bgr": (120, 40, 190)
    },
    {
        "name": "主臥室",
        "local_poly": [[0, 560], [290, 560], [290, 1000], [0, 1000]],
        "bgr": (246, 130, 59),  # Blue BGR (#3B82F6)
        "stroke_bgr": (190, 90, 30)
    },
    {
        "name": "臥室 B (次臥 B)",
        "local_poly": [[300, 700], [490, 700], [490, 1000], [300, 1000]],
        "bgr": (94, 197, 34),   # Green BGR (#22C55E)
        "stroke_bgr": (60, 150, 20)
    }
]

for r in rooms:
    pts = map_plan_to_photo(r["local_poly"], w, h)
    bgr = r["bgr"]
    stroke_bgr = r["stroke_bgr"]
    cv2.fillPoly(overlay, [pts], bgr)
    cv2.polylines(img, [pts], isClosed=True, color=stroke_bgr, thickness=2)

alpha = 0.38
cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

cv2.imwrite(out_path, img)
print(f"Successfully rendered wall aligned image to {out_path} ({w}x{h})")
