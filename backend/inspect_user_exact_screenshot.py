import cv2
import numpy as np
import os

artifacts_dir = r"C:\Users\flitt\.gemini\antigravity-ide\brain\7f6b70e4-e153-4cd2-aff5-2dd9681a0b5e"
src_file = os.path.join(artifacts_dir, "media__1785672965749.jpg")
out_path = os.path.join(artifacts_dir, "exact_user_attached_picture_copy.jpg")

with open(src_file, "rb") as f:
    data = f.read()
nparr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

cv2.imwrite(out_path, img)
print(f"Successfully copied user attached screenshot to {out_path} ({img.shape[1]}x{img.shape[0]})")
