import cv2
import numpy as np
import os

artifacts_dir = r"C:\Users\flitt\.gemini\antigravity-ide\brain\7f6b70e4-e153-4cd2-aff5-2dd9681a0b5e"
src_file = os.path.join(artifacts_dir, "media__1785671682031.jpg")
out_path = os.path.join(artifacts_dir, "blue_marker_detected.jpg")

with open(src_file, "rb") as f:
    data = f.read()
nparr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

h, w, _ = img.shape
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# Blue Marker HSV Range (Highlighter & Blue Pen Checkmarks)
lower_blue = np.array([90, 40, 40])
upper_blue = np.array([135, 255, 255])
mask = cv2.inRange(hsv, lower_blue, upper_blue)

# Morphological dilate to connect stroke gaps
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

# Find contours of blue highlighter boxes and checkmarks
contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

annotated = img.copy()
detected_boxes = []

for idx, cnt in enumerate(contours):
    area = cv2.contourArea(cnt)
    if area > 300: # Filter small noise
        x, y, bw, bh = cv2.boundingRect(cnt)
        norm_box = [[round(x / w * 1000), round(y / h * 1000)], [round((x+bw)/w * 1000), round((y+bh)/h * 1000)]]
        detected_boxes.append({
            "box_id": idx + 1,
            "area_px": area,
            "bbox_1000": norm_box
        })
        cv2.rectangle(annotated, (x, y), (x + bw, y + bh), (255, 128, 0), 2)
        cv2.putText(annotated, f"Blue Zone {idx+1}", (x, max(20, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 128, 0), 2)

cv2.imwrite(out_path, annotated)
print(f"Detected {len(detected_boxes)} blue highlighter / checkmark regions!")
for b in detected_boxes:
    print(" ", b)
