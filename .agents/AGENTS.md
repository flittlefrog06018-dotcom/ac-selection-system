# Track A Floorplan Recognition General Principles (軌道 A 圖面辨識通用原則)

## 1. Dynamic Text & OCR Extraction (動態文字流與光學 OCR 解析)
- **Zero Hardcoding Policy (嚴禁死背或硬編碼)**:
  - All room names, geometric areas, and HVAC load values MUST be dynamically parsed algorithmically from the drawing's text stream or OCR image pixels.
  - Never use static memorized arrays or filename-based hardcoded mock lists.

## 2. Spatial Proximity & Red Outlined Polyline Pairing (空間鄰近性與紅框區域匹配)
- **Bounding Box Proximity Matching**:
  - The recognition algorithm extracts room text tokens `[\u4e00-\u9fff]` and area value tokens (`m²`, `㎡`, `P`, `坪`).
  - Each room name is paired with its geometrically nearest area number or red outlined polyline boundary using spatial coordinate distance calculation $(x, y, w, h)$.

## 3. Algorithmic Deduplication & Standardization (演算法動態去重與正名)
- **Entrance Label Consolidation**: If a drawing contains partial entrance text tokens, merge standalone "玄關" into "玄關+走道" to prevent duplicate row creation.
- **Bathroom Label Standardization**: Map guest bathroom / bathroom labels ("浴室", "客浴室") to "客廁", and master bathroom labels to "主臥浴室".
- **HVAC Non-Target Noise Filtering**: Filter out non-AC service balconies and CAD annotation artifacts (e.g. "工作間", "小玄關", "工作平台", "廊道", "工作站", "儲藏室", "儲物室").
