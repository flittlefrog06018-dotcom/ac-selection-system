import cv2
import numpy as np
import os

artifacts_dir = r"C:\Users\flitt\.gemini\antigravity-ide\brain\7f6b70e4-e153-4cd2-aff5-2dd9681a0b5e"
out_path = os.path.join(artifacts_dir, "plan_G_final_rendered.jpg")
src_file = os.path.join(artifacts_dir, "media__1785663732202.jpg")

with open(src_file, "rb") as f:
    data = f.read()
nparr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

h, w, _ = img.shape
overlay = img.copy()

# 4 Exact Rooms matching User Red Boxes on Plan G
rooms = [
    {
        "name": "客廳+餐廳 | 54.55㎡ / 16.5坪",
        "polygon": [[80, 80], [320, 80], [320, 800], [80, 800]],
        "bgr": (8, 179, 234)  # Yellow BGR (#EAB308)
    },
    {
        "name": "臥室 1 | 10.58㎡ / 3.2坪",
        "polygon": [[330, 80], [500, 80], [500, 480], [330, 480]],
        "bgr": (153, 72, 236)  # Pink BGR (#EC4899)
    },
    {
        "name": "臥室 2 | 9.26㎡ / 2.8坪",
        "polygon": [[520, 80], [690, 80], [690, 480], [520, 480]],
        "bgr": (94, 197, 34)  # Green BGR (#22C55E)
    },
    {
        "name": "主臥室 | 14.21㎡ / 4.3坪",
        "polygon": [[700, 80], [930, 80], [930, 480], [700, 480]],
        "bgr": (246, 130, 59)  # Blue BGR (#3B82F6)
    }
]

for r in rooms:
    poly = r["polygon"]
    bgr = r["bgr"]
    pts = np.array([[(pt[0] / 1000.0) * w, (pt[1] / 1000.0) * h] for pt in poly], dtype=np.int32)
    cv2.fillPoly(overlay, [pts], bgr)
    cv2.polylines(img, [pts], isClosed=True, color=bgr, thickness=max(2, int(w / 400)))

alpha = 0.38
cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

cv2.imwrite(out_path, img)
print(f"Successfully rendered plan G image to {out_path} ({w}x{h})")
