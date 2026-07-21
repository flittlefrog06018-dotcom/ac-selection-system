# 空調選機自動化系統 (AC Selection Automation System)

本專案是一個專為空調工程師設計的內部網頁系統，能夠自動化讀取平面圖面、計算熱負荷、並從產品資料庫中自動媒合推薦最合適的室內外機型號。

## 專案目錄結構

```
ac-selection-system/
├── backend/                  # Python FastAPI 後端
│   ├── app/
│   │   ├── api/routes.py     # API 路由 (上傳、重新計算、Excel匯出)
│   │   ├── services/
│   │   │   ├── gemini_service.py # Gemini 視覺辨識介面 (已預留 API 串接與 mock 邏輯)
│   │   │   ├── calc_service.py   # 熱負荷計算邏輯
│   │   │   ├── selection_service.py # 產品媒合邏輯
│   │   │   └── export_service.py # openpyxl Excel 匯出邏輯
│   │   └── config.py         # 系統參數設定與各空間預設負荷值 (W/m²)
│   ├── product_database/     # 存放空調規格 CSV 或 Excel 檔案
│   │   └── ac_products_template.csv # 產品規格範本檔
│   ├── main.py               # 後端啟動入口點
│   └── requirements.txt      # 後端相依套件清單
└── frontend/                 # React + Vite 前端
    ├── src/
    │   ├── App.jsx           # 前端 UI 主程式 (包含上傳、表格編輯、Excel匯出呼叫)
    │   ├── index.css         # 系統 UI 設計樣式表 (極致冰藍 Glassmorphic 風格)
    │   └── main.jsx
    ├── index.html
    ├── vite.config.js        # Vite 設定檔 (配置有 API 代理 proxy)
    └── package.json          # 前端相依套件清單
```

---

## 快速啟動指南

### 第一步：啟動 FastAPI 後端

1. 開啟終端機（Terminal）並切換至 `backend` 資料夾：
   ```bash
   cd backend
   ```

2. 建議建立 Python 虛擬環境：
   ```bash
   python -m venv venv
   # Windows 啟用虛擬環境
   .\venv\Scripts\activate
   ```

3. 安裝相依套件：
   ```bash
   pip install -r requirements.txt
   ```

4. （選填）設定您的 Google Gemini API Key：
   ```bash
   # Windows PowerShell
   $env:GEMINI_API_KEY="您的_GEMINI_API_KEY"
   ```
   *註：若未設定 API Key，系統會自動切換為 Mock 測試模式，輸出模擬的辨識結果以供開發測試。*

5. 啟動後端伺服器：
   ```bash
   python main.py
   ```
   伺服器將在 `http://localhost:8000` 啟動，您可以瀏覽 `http://localhost:8000/docs` 查看自動生成的 Swagger API 文件。

### 第二步：啟動 React 前端 (需先安裝 Node.js)

1. 開啟另一個終端機，切換至 `frontend` 資料夾：
   ```bash
   cd frontend
   ```

2. 安裝套件：
   ```bash
   npm install
   ```

3. 啟動前端開發伺服器：
   ```bash
   npm run dev
   ```
   開啟瀏覽器訪問 `http://localhost:5173` 即可開始使用！

---

## 自動選機邏輯與資料庫說明

1. **產品規格檔**：請將您的空調產品清單存為 Excel (`.xlsx`, `.xls`) 或 CSV 檔案，放在 `backend/product_database/` 資料夾內。
2. **規格欄位要求**：檔案中必須包含以下欄位（大小寫不敏感）：
   - `Model`：機型名稱
   - `SystemType`：家用、商用、VRV
   - `IndoorOutdoor`：Indoor (室內機) 或 Outdoor (室外機)
   - `UnitStyle`：壁掛、崁入、吊隱、側吹、上吹
   - `Capacity_kW`：冷房額定能力 (單位: kW)
3. **媒合規則**：後端會根據空間所算出的設計負荷（kW），自動在符合篩選條件的機型池中，尋找「`Capacity_kW` 大於且最接近設計負荷」的機型。
