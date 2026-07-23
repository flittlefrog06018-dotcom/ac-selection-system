# 大金空調選機自動化系統 - 極輕量雲端架構與未來升級藍圖 (Roadmap)

## 📌 核心規劃原則
1. **零檔案儲存負擔**：圖面解析與 Excel 產出在瀏覽器與快取中完成，客戶直接下載，後端不佔用雲端硬碟空間（0 MB 儲存負擔）。
2. **免重部署線上資料同步**：參數與基準表直接連動線上試算表/儲存桶，修改即刻生效。
3. **極輕量登入日誌**：僅記錄登入人與時間，維護費用最低。

---

## 🎯 需求 1：線上直接更新資料庫 (免重新部署程式)
* **方案選項 A (推薦)**：Google Sheets API 線上試算表連動
  - 將《空調負荷基準表》與《選機表》放在 Google Drive 上。
  - 管理員隨時在 Google Sheet 修改基準與型號，網站背景自動同步最新數據。
* **方案選項 B**：雲端儲存區 (Cloud Storage) 覆蓋上傳
  - 於管理員介面開放單鍵上傳最新 Excel，自動覆蓋雲端 Storage 檔案，秒級生效。

---

## 🎯 需求 2：超輕量登入紀錄 (Login Audit Log)
* **資料庫設計 (僅記錄必要資訊)**：
  ```sql
  CREATE TABLE login_logs (
      id SERIAL PRIMARY KEY,
      user_name VARCHAR(100) NOT NULL,
      login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      ip_address VARCHAR(45)
  );
  ```
* **容量控制**：一萬筆紀錄佔用空間小於 5 MB，完全在免費雲端資料庫 (如 Supabase / Firebase) 額度內。
* **流程**：客戶登入時紀錄時間 $\rightarrow$ 線上進行選機與圖面解析 $\rightarrow$ 瀏覽器端直接下載 Excel $\rightarrow$ 不佔用伺服器硬碟。

---

## 🚀 未來雲端部署建議組合 (Production Stack)
- **前端**：Vercel / Netlify (免費託管 React 前端)
- **後端**：Render / Railway (免費/低成本託管 FastAPI 後端)
- **登入日誌資料庫**：Supabase / Firebase (免費層即夠用)
- **基準表同步**：Google Sheets API / Cloud Storage

---
*文件建立時間：2026-07-24*
