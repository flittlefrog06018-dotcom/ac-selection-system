import cv2
import numpy as np
import os

artifacts_dir = r"C:\Users\flitt\.gemini\antigravity-ide\brain\7f6b70e4-e153-4cd2-aff5-2dd9681a0b5e"
src_file = os.path.join(artifacts_dir, "media__1785670904924.jpg")
out_path = os.path.join(artifacts_dir, "plan_G_user_reference_rendered.jpg")

with open(src_file, "rb") as f:
    data = f.read()
nparr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

h, w, _ = img.shape
overlay = img.copy()

# Exact Multi-point Rooms matching User Reference Image
rooms = [
    {
        "name": "公領域 (LDKE: 客廳+餐廳+廚房+玄關)",
        "polygon": [[135, 120], [360, 120], [360, 390], [655, 390], [655, 475], [455, 475], [455, 630], [280, 630], [280, 890], [135, 890]],
        "bgr": (8, 179, 234)  # Yellow BGR (#EAB308)
    },
    {
        "name": "臥室 1",
        "polygon": [[368, 120], [532, 120], [532, 385], [368, 385]],
        "bgr": (246, 130, 59)  # Blue BGR (#3B82F6)
    },
    {
        "name": "臥室 2",
        "polygon": [[540, 120], [700, 120], [700, 385], [540, 385]],
        "bgr": (94, 197, 34)  # Green BGR (#22C55E)
    },
    {
        "name": "主臥室",
        "polygon": [[708, 120], [895, 120], [895, 630], [735, 630], [735, 475], [665, 475], [665, 390], [708, 390]],
        "bgr": (153, 72, 236)  # Pink BGR (#EC4899)
    }
]

for r in rooms:
    poly = r["polygon"]
    bgr = r["bgr"]
    pts = np.array([[(pt[0] / 1000.0) * w, (pt[1] / 1000.0) * h] for pt in poly], dtype=np.int32)
    cv2.fillPoly(overlay, [pts], bgr)
    cv2.polylines(img, [pts], isClosed=True, color=bgr, thickness=max(2, int(w / 400)))

alpha = 0.42
cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

cv2.imwrite(out_path, img)
print(f"Successfully rendered plan G reference image to {out_path}")
