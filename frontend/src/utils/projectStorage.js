/**
 * 大金空調選型自動化系統 - 案場快照與專案儲存模組 (Project Storage)
 * 支援 IndexedDB 本機快速存檔 / 讀取，以及可攜式 .daikin 專案檔匯出 / 匯入
 */

const DB_NAME = 'DaikinACProjectsDB';
const DB_VERSION = 1;
const STORE_NAME = 'projects';

/**
 * 初始化或開啟 IndexedDB
 */
export function openProjectDB() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      reject(new Error('您的瀏覽器不支援 IndexedDB'));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        store.createIndex('savedAt', 'savedAt', { unique: false });
        store.createIndex('projectName', 'projectName', { unique: false });
      }
    };

    request.onsuccess = (event) => {
      resolve(event.target.result);
    };

    request.onerror = (event) => {
      reject(event.target.error);
    };
  });
}

/**
 * 將 Blob URL 轉換成 Base64 Data URL (供可攜式專案檔保存圖面)
 */
export async function blobUrlToBase64(blobUrl) {
  if (!blobUrl) return null;
  if (blobUrl.startsWith('data:')) return blobUrl;
  try {
    const res = await fetch(blobUrl);
    const blob = await res.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } catch (err) {
    console.warn('轉換底圖 Base64 失敗，將略過底圖快照:', err);
    return null;
  }
}

/**
 * 儲存專案至本地 IndexedDB
 */
export async function saveProjectToIndexedDB(projectData) {
  const db = await openProjectDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    // 確保有唯一 ID
    const record = {
      ...projectData,
      id: projectData.id || `proj_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
      savedAt: projectData.savedAt || new Date().toISOString()
    };

    const request = store.put(record);

    request.onsuccess = () => {
      resolve(record);
    };

    request.onerror = (event) => {
      reject(event.target.error);
    };
  });
}

/**
 * 取得本機所有儲存的案場專案（依存檔時間倒序）
 */
export async function getAllProjectsFromIndexedDB() {
  const db = await openProjectDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.getAll();

    request.onsuccess = (event) => {
      const projects = event.target.result || [];
      // 依存檔時間最新優先排序
      projects.sort((a, b) => new Date(b.savedAt) - new Date(a.savedAt));
      resolve(projects);
    };

    request.onerror = (event) => {
      reject(event.target.error);
    };
  });
}

/**
 * 依 ID 取得單一案場專案
 */
export async function getProjectByIdFromIndexedDB(id) {
  const db = await openProjectDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.get(id);

    request.onsuccess = (event) => {
      resolve(event.target.result || null);
    };

    request.onerror = (event) => {
      reject(event.target.error);
    };
  });
}

/**
 * 刪除本機指定的案場專案
 */
export async function deleteProjectFromIndexedDB(id) {
  const db = await openProjectDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.delete(id);

    request.onsuccess = () => {
      resolve(true);
    };

    request.onerror = (event) => {
      reject(event.target.error);
    };
  });
}

/**
 * 下載 .daikin 專案檔 (MIME: application/json)
 */
export function downloadDaikinFile(projectData, customFileName) {
  const cleanName = (customFileName || projectData.projectName || '大金選機專案')
    .replace(/[\\/:*?"<>|]/g, '_')
    .trim();
  const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const fileName = `${cleanName}_${dateStr}.daikin`;

  const jsonString = JSON.stringify(projectData, null, 2);
  const blob = new Blob([jsonString], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  return fileName;
}

/**
 * 讀取並驗證使用者上傳的 .daikin 專案檔
 */
export function readDaikinFile(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      reject(new Error('未選擇檔案'));
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target.result;
        const data = JSON.parse(text);
        if (!data || (!data.rows && !data.polygons && !data.projectName)) {
          reject(new Error('無效的專案檔格式 (缺少必要選型或圖面欄位)'));
          return;
        }
        resolve(data);
      } catch (err) {
        reject(new Error(`專案檔解析失敗: ${err.message}`));
      }
    };
    reader.onerror = (err) => {
      reject(new Error(`讀取檔案發生錯誤: ${err}`));
    };
    reader.readAsText(file);
  });
}
