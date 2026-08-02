import cv2
import numpy as np
import os

artifacts_dir = r"C:\Users\flitt\.gemini\antigravity-ide\brain\7f6b70e4-e153-4cd2-aff5-2dd9681a0b5e"
src_file = os.path.join(artifacts_dir, "media__1785672967802.png")
out_path = os.path.join(artifacts_dir, "exact_user_attached_reference.jpg")

img = cv2.imread(src_file, cv2.IMREAD_COLOR)
if img is None:
    raise ValueError("Failed to read user PNG file")

cv2.imwrite(out_path, img)
print(f"Successfully converted user attached screenshot to {out_path} ({img.shape[1]}x{img.shape[0]})")
