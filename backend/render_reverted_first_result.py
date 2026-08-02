import cv2
import numpy as np
import os

artifacts_dir = r"C:\Users\flitt\.gemini\antigravity-ide\brain\7f6b70e4-e153-4cd2-aff5-2dd9681a0b5e"
src_file = os.path.join(artifacts_dir, "media__1785671682031.jpg")
out_path = os.path.join(artifacts_dir, "reverted_first_result.jpg")

with open(src_file, "rb") as f:
    data = f.read()
nparr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

h, w, _ = img.shape
overlay = img.copy()

# The 4 Exact Room Polygons from the First Original Result requested by User
rooms = [
    {
        "name": "公領域 (LDKE: 客廳+餐廳+廚房+玄關)",
        "polygon": [[575, 280], [870, 280], [870, 400], [770, 400], [770, 710], [575, 710], [575, 540], [670, 540], [670, 380], [575, 380]],
        "bgr": (8, 179, 234)  # Yellow BGR (#EAB308)
    },
    {
        "name": "臥室 A (次臥 A)",
        "polygon": [[240, 300], [420, 300], [420, 480], [240, 480]],
        "bgr": (153, 72, 236)  # Pink BGR (#EC4899)
    },
    {
        "name": "主臥室",
        "polygon": [[240, 485], [420, 485], [420, 710], [240, 710]],
        "bgr": (246, 130, 59)  # Blue BGR (#3B82F6)
    },
    {
        "name": "臥室 B (次臥 B)",
        "polygon": [[425, 485], [570, 485], [570, 710], [425, 710]],
        "bgr": (94, 197, 34)  # Green BGR (#22C55E)
    }
]

for r in rooms:
    poly = r["polygon"]
    bgr = r["bgr"]
    pts = np.array([[(pt[0] / 1000.0) * w, (pt[1] / 1000.0) * h] for pt in poly], dtype=np.int32)
    cv2.fillPoly(overlay, [pts], bgr)
    cv2.polylines(img, [pts], isClosed=True, color=bgr, thickness=max(2, int(w / 350)))

alpha = 0.38
cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

cv2.imwrite(out_path, img)
print(f"Successfully rendered reverted first result to {out_path} ({w}x{h})")
