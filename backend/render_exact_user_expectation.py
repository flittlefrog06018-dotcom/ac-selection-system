import cv2
import numpy as np
import os

artifacts_dir = r"C:\Users\flitt\.gemini\antigravity-ide\brain\7f6b70e4-e153-4cd2-aff5-2dd9681a0b5e"
src_file = os.path.join(artifacts_dir, "media__1785671682031.jpg")
out_path = os.path.join(artifacts_dir, "v10_user_exact_expected_result.jpg")

with open(src_file, "rb") as f:
    data = f.read()
nparr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

h, w, _ = img.shape
overlay = img.copy()

rooms = [
    {
        "name": "公領域 (LDKE)",
        "polygon": [[590, 240], [905, 240], [905, 395], [805, 395], [805, 815], [585, 815], [585, 590], [460, 590], [460, 525], [590, 525]],
        "bgr": (8, 179, 234)  # Yellow BGR (#EAB308)
    },
    {
        "name": "臥室 A (次臥 A)",
        "polygon": [[310, 310], [490, 310], [490, 520], [310, 520]],
        "bgr": (153, 72, 236)  # Pink BGR (#EC4899)
    },
    {
        "name": "主臥室",
        "polygon": [[310, 525], [455, 525], [455, 840], [310, 840]],
        "bgr": (246, 130, 59)  # Blue BGR (#3B82F6)
    },
    {
        "name": "臥室 B (次臥 B)",
        "polygon": [[460, 590], [580, 590], [580, 825], [460, 825]],
        "bgr": (94, 197, 34)  # Green BGR (#22C55E)
    }
]

for r in rooms:
    poly = r["polygon"]
    bgr = r["bgr"]
    pts = np.array([[(pt[0] / 1000.0) * w, (pt[1] / 1000.0) * h] for pt in poly], dtype=np.int32)
    cv2.fillPoly(overlay, [pts], bgr)
    cv2.polylines(img, [pts], isClosed=True, color=(30, 45, 45), thickness=3)

alpha = 0.40
cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

cv2.imwrite(out_path, img)
print(f"Successfully rendered exact expected result to {out_path} ({w}x{h})")
