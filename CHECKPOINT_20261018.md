# 大金空調選機自動化系統 - 版本存檔記錄 (Version Release Log)

- **版本編號 (Version)**: v2.26.0
- **存檔日期 (Release Date)**: 2026-10-18 22:50
- **系統名稱**: Daikin AC Selection Automation System
- **線上站台**: https://ac-selection-system.vercel.app/

---

## 🎯 本次存檔重點項目摘要 (Summary of Milestones)

### 1. 流程圖主機規格標記客製化 (VRV Outdoor Unit Model HP Label Customization)
- **RSUYQ 機型 HP 隱藏規則**：
  - `RSUYQ112AVT`、`RSUYQ125AVT`、`RSUYQ140AVT`、`RSUYQ160AVT` 機型卡片標題簡化為「`主機`」（不帶馬力 HP 數值）。
  - 其餘大金 VRV 設備（如 `RXYQ`、`RXQ` 等側吹/頂吹標準商用機型）維持完整呈現「`主機 (X HP)`」。
- **前端繪圖與後端 CAD 向量流程圖同步更新**：
  - 前端 `RefrigerantPipingDiagram.jsx` 向量圖層與後端 `DaikinFlowchartDiagramDrawer` 同步遵循此標記規則。

### 2. 系統套數分頁次分歧管 2 組結構完整化 (VRV Secondary Branch Joint Topology)
- **拓撲結構階層校準**：
  - 修正 VRV 樹狀平坦化邏輯（`flatten_custom_tree_to_rows`），精準呈現主幹次幹管分歧點次分歧頭（KHRP26A22T）與次分歧網絡次分歧頭（KHRP26A22T），合計完整列出 **2 組次分歧頭**。
  - 修正次分歧頭之 `is_main: False` 屬性，徹底移除錯誤的 `[VRV系統]` 重複前綴髒標記。

### 3. 冷媒管路示意架構圖 100% 完整嵌入 (Refrigerant Diagram Excel Embedding)
- **修復後端圖片嵌入流程中斷問題**：
  - `equipment_summary_service.py` 補全 `import io` 與 `logger` 初始化宣告，根除 `NameError`。
  - 支援優先將 UI 介面所呈現的冷媒流程圖即時繪製為向量 PNG 嵌入至【系統套數】分頁 `E4` 儲存格，並保留後端高解析直式與橫式流程圖作為雙重保障。

### 4. 側邊欄收折展開 0 偏移保障 (Floorplan Container DOM Lifecycle Fix)
- **常駐 DOM 取代條件銷毀**：
  - 圖面預覽區改以 CSS `display` 切換顯隱，杜絕 React 三元運算符 Unmount/Mount 銷毀節點造成的長寬比失調。
  - 加入展開 CSS 動畫完成後（320ms / 500ms）多階尺寸校準，確保 100%~500% 縮放倍率下，底圖與空間 SVG 框選多邊形 100% 嚴密重合、0 偏移。

### 5. 專案庫與快照持久化系統 (IndexedDB Local Project Archive & Daikin File Portability)
- 支援本機 IndexedDB 快照庫與 `.daikin` 專案檔匯出/匯入，可隨時還原所有空間、比例尺與設備選型。
- 移除「更換圖檔保護視窗」中冗餘之「保留現有空間（僅更換底圖）」選項。
- 統一頂部與底部室外機電源，移除「電腦版」與「手機板」字樣，統一為專業正式版本。

---

## 🔒 核心原則遵照 (Zero Modification to Floorplan Recognition)
- 圖面辨識演算法、空間 OCR 坐標萃取、幾何多邊形面積換算、紅框區域匹配邏輯、現有室內機/室外機選型匹配函數**完全維持原樣，零變動**。
