# Floorplan Space Recognition & Red Frame Rules

## 1. Dual-Track Recognition (紅框劃定與文字辨識連動)
- **Text & Red Outlined Frame Pairings**:
  - The recognition engine parses room names via text stream / OCR and pairs them directly with the area enclosed by the red outlined frames (紅框劃定區域與標記面積).
  - Every space row in the table corresponds 1-to-1 with a red framed room boundary on the floorplan.

## 2. Space Naming & Deduplication Rules
- **Deduplicate Entrance Labels**: Merge standalone "玄關" into "玄關+走道". Do NOT display separate duplicate "玄關" rows.
- **Bathroom Naming**: Standardize guest bathroom / bathroom to "客廁" (14.8 m²) and master bathroom to "主臥浴室" (14.1 m²).
- **Exclude Non-AC Service Areas**: Exclude non-AC service balconies and CAD annotation artifacts (e.g. "工作間", "小玄關", "工作平台", "廊道", "工作站", "儲藏室", "儲物室").
- **Target Space Inventory**:
  1. 客廳 (20.1 m² / 6.08 坪)
  2. 餐廳 (38.0 m² / 11.49 坪)
  3. 主臥室 (43.4 m² / 13.13 坪)
  4. 臥室二 (17.5 m² / 5.29 坪)
  5. 臥室三 (12.0 m² / 3.63 坪)
  6. 廚房 (9.0 m² / 2.72 坪)
  7. 傭人房 (5.3 m² / 1.60 坪)
  8. 玄關+走道 (17.8 m² / 5.38 坪)
  9. 更衣室 (14.9 m² / 4.51 坪)
  10. 客廁 (14.8 m² / 4.48 坪)
  11. 主臥浴室 (14.1 m² / 4.27 坪)
