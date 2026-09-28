# 大金空調選機自動化系統 - 版本存檔記錄 (Version Release Log)

- **版本編號 (Version)**: v2.22.0
- **存檔日期 (Release Date)**: 2026-09-28 17:35
- **系統名稱**: Daikin AC Selection Automation System
- **線上站台**: https://ac-selection-system.vercel.app/

---

## 🎯 本次存檔重點項目摘要 (Summary of Milestones)

### 1. 匯出選機表分頁白名單強制隱藏 (Exported Workbook Sheet Visibility Control)
- **僅保留三大主要分頁**：
  - 匯出之 Excel 活頁簿僅保留**【選機】**、**【設備報價單】**與**【系統套數】**為可見分頁（`sheet_state = "visible"`）。
  - 自動隱藏**【設備統計總表】**、**【D3-NET分析】**及系統內部資料庫等非必要分頁（`sheet_state = "hidden"`）。
- **後端與前端雙軌全面實作**：
  - 後端 `ExportService.generate_excel_report` 於存檔前執行活頁簿全域過濾與啟用工作表指定（確保 active sheet 為可見的選機分頁，避免檔案開啟告警）。
  - 前端離線 fallback 匯出邏輯（`exportExcelClientSideFallback`）同步保持完全一致的隱藏與分頁配置。

### 2. 設備報價單分頁空調設備依容量升冪與室外機置頂排列 (Quotation Sheet Equipment Sorting)
- **家用多聯室外機優先置頂**：
  - 室外機一律集中排在空調設備清單最上方，並依照冷房能力由小至大嚴格排列（例如：`2MXP50ZVLT` $\rightarrow$ `2MXP85ZVLT`）。
- **家用多聯室內機接續其後**：
  - 室內機接續排在室外機下方，並同樣依照冷房能力由小至大嚴格排列（例如：`FTHF20ZVLT` $\rightarrow$ `FTHF25ZVLT` $\rightarrow$ `FTHF40ZVLT`）。
- **智能容量提取解析器 (Capacity Extractor)**：
  - 整合設備資料庫（`EQUIPMENT_Data.xlsx`）標準容量數值與正則數字代碼解析，精確相容多聯機型號（支援過濾 2MXP / 3MXM / 4MXM 前綴後抓取實質級數）。

### 3. VRV 系統室外機同套配機邏輯校準 (VRV Single System Grouping)
- 校正 VRV 系統室內機同套合併與室外機選配機制，避免多個同系統空間被誤切為不同室外機，確保同一套 VRV 系統歸屬同一台主機群組。

### 4. 控制配件清單與報價金額全面連動 (Accessory Pricing Integration)
- 智慧手機 APP 遠端控制卡（`BRP072C42` / `BRP084C45`）與原廠轉接小 P 板（`BRP067A42` / `BRP980B42`）對應室內機機型精準清點與計價。
- 伶俐智能管理器（`DCPF01`）選配件金額自動計入報價單其他配件小計與總價。

---

## 🔒 核心原則遵照 (Zero Modification to Floorplan Recognition)
- 圖面辨識演算法、空間 OCR 坐標萃取、幾何多邊形面積換算與紅框區域匹配邏輯及程式**完全維持原樣，零變動**。
