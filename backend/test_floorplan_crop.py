import cv2
import numpy as np
import glob
import os

files = glob.glob("temp/*.*")

def read_img_unicode(fpath):
    try:
        with open(fpath, "rb") as f:
            data = f.read()
        nparr = np.frombuffer(data, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        return None

for fpath in files:
    if not (fpath.endswith(".jpg") or fpath.endswith(".png")):
        continue
    img = read_img_unicode(fpath)
    if img is None:
        continue
    h, w, _ = img.shape
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 30, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    box_x, box_y, box_w, box_h = 0, 0, w, h
    if contours:
        # Filter contours by size
        large_pts = []
        for c in contours:
            if cv2.contourArea(c) > 20:
                large_pts.append(c)
        if large_pts:
            all_pts = np.vstack(large_pts)
            x, y, bw, bh = cv2.boundingRect(all_pts)
            if bw > w * 0.3 and bh > h * 0.3:
                box_x, box_y, box_w, box_h = x, y, bw, bh
    
    fname = os.path.basename(fpath)
    print(f"File: {fname} | Img: {w}x{h} | Floorplan BBox: x={box_x}, y={box_y}, w={box_w}, h={box_h} ({(box_w/w)*100:.1f}% x {(box_h/h)*100:.1f}%)")
