import cv2
import numpy as np
import os

artifacts_dir = r"C:\Users\flitt\.gemini\antigravity-ide\brain\7f6b70e4-e153-4cd2-aff5-2dd9681a0b5e"
src_file = os.path.join(artifacts_dir, "media__1785671682031.jpg")
out_path = os.path.join(artifacts_dir, "new_v10_rendered.jpg")

with open(src_file, "rb") as f:
    data = f.read()
nparr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

h, w, _ = img.shape
overlay = img.copy()

# 4 Exact Rooms matching Blue Marker Outlines on new uploaded floorplan image
rooms = [
    {
        "name": "公領域 (LDKE: 客廳+餐廳+廚房+玄關) | 54.55㎡ / 16.5坪",
        "polygon": [[585, 335], [805, 335], [805, 600], [585, 600], [585, 455], [495, 455], [495, 335], [585, 335]],
        "bgr": (8, 179, 234)  # Yellow BGR (#EAB308)
    },
    {
        "name": "臥室 A (次臥 A) | 11.57㎡ / 3.5坪",
        "polygon": [[310, 310], [495, 310], [495, 395], [310, 395]],
        "bgr": (153, 72, 236)  # Pink BGR (#EC4899)
    },
    {
        "name": "主臥室 | 14.2㎡ / 4.3坪",
        "polygon": [[310, 400], [450, 400], [450, 620], [310, 620]],
        "bgr": (246, 130, 59)  # Blue BGR (#3B82F6)
    },
    {
        "name": "臥室 B (次臥 B) | 9.25㎡ / 2.8坪",
        "polygon": [[455, 460], [580, 460], [580, 610], [455, 610]],
        "bgr": (94, 197, 34)  # Green BGR (#22C55E)
    }
]

for r in rooms:
    poly = r["polygon"]
    bgr = r["bgr"]
    pts = np.array([[(pt[0] / 1000.0) * w, (pt[1] / 1000.0) * h] for pt in poly], dtype=np.int32)
    cv2.fillPoly(overlay, [pts], bgr)
    cv2.polylines(img, [pts], isClosed=True, color=bgr, thickness=max(2, int(w / 350)))

alpha = 0.42
cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

cv2.imwrite(out_path, img)
print(f"Successfully rendered new floorplan image to {out_path} ({w}x{h})")
