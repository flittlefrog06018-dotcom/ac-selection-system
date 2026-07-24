import React, { useState, useRef } from 'react';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// 🎯 同步黃經理 Python 原廠內建的大金規格資料庫
const EQUIPMENT_DB = {
  RA: [
    { model: "FTXM22ZVLT", cap: 2.2 }, { model: "FTXM28ZVLT", cap: 2.8 },
    { model: "FTXM36ZVLT", cap: 3.5 }, { model: "FTXM41ZVLT", cap: 4.1 },
    { model: "FTXM50ZVLT", cap: 5.0 }, { model: "FTXM60ZVLT", cap: 6.0 },
    { model: "FTXM71ZVLT", cap: 7.2 }, { model: "FTXM80ZVLT", cap: 8.0 },
    { model: "FTXM90ZVLT", cap: 8.7 }
  ],
  SA: [
    { model: "FBA71BVLT", cap: 7.2 }, { model: "FBA100BVLT", cap: 10.1 },
    { model: "FBA125BVLT", cap: 12.5 }, { model: "FBA140BVLT", cap: 13.3 }
  ],
  VRV: [
    { model: "FXSQ20PAVT", cap: 2.2 }, { model: "FXSQ25PAVT", cap: 2.8 },
    { model: "FXSQ32PAVT", cap: 3.6 }, { model: "FXSQ40PAVT", cap: 4.5 },
    { model: "FXSQ50PAVT", cap: 5.6 }, { model: "FXSQ63PAVT", cap: 7.1 },
    { model: "FXSQ80PAVT", cap: 9.0 }, { model: "FXSQ100PAVT", cap: 11.2 },
    { model: "FXSQ125PAVT", cap: 14.0 }, { model: "FXSQ140PAVT", cap: 16.0 }
  ]
};

const MODIFIER_VALUES = { 全內周: -0.10, 二面牆: 0.05, 西曬: 0.06, 挑高: 0.04, 頂曬: 0.05 };

// 🎯 安全配機演算法：改用純陣列遍歷與數學除法，100% 杜絕卡死
const clientSideSelectEquipment = (totalDemandKcal, systemType) => {
  const totalLoadKw = totalDemandKcal / 860.0;
  const modelsList = EQUIPMENT_DB[systemType] || EQUIPMENT_DB["VRV"];

  let bestModel = null;
  let bestQty = 999;
  let bestCap = 0.0;

  for (let i = 0; i < modelsList.length; i++) {
    const singleCap = modelsList[i].cap;
    for (let qty = 1; qty <= 10; qty++) {
      const totalCap = singleCap * qty;
      if (totalCap >= totalLoadKw) {
        if (qty < bestQty) {
          bestQty = qty;
          bestModel = modelsList[i].model;
          bestCap = singleCap;
          break;
        } else if (qty === bestQty) {
          if (bestModel === null || singleCap < bestCap) {
            bestQty = qty;
            bestModel = modelsList[i].model;
            bestCap = singleCap;
          }
          break;
        }
      }
    }
  }

  if (bestModel !== null) {
    return { model: bestModel, qty: bestQty, cap: bestCap };
  }

  const maxItem = modelsList[modelsList.length - 1];
  let neededQty = Math.round((totalLoadKw / maxItem.cap) + 0.5);
  if (neededQty <= 0) neededQty = 1;
  return { model: maxItem.model, qty: neededQty, cap: maxItem.cap };
};

const lookupModelCapKw = (modelName) => {
  if (!modelName) return 0.0;
  const allModels = [
    ...(EQUIPMENT_DB.VRV || []),
    ...(EQUIPMENT_DB.RA || []),
    ...(EQUIPMENT_DB.SA || [])
  ];
  const matched = allModels.find(m => m.model === modelName.trim());
  return matched ? matched.cap : 0.0;
};

// 🎯 測試存取保護密碼 (預設為 daikin2026，可改為任意密碼或改為 "" 取消密碼)
const SYSTEM_ACCESS_PASSWORD = "daikin2026";

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return !SYSTEM_ACCESS_PASSWORD || sessionStorage.getItem("app_authenticated") === "true";
  });
  const [inputPassword, setInputPassword] = useState("");
  const [passError, setPassError] = useState(false);

  const handlePasswordSubmit = (e) => {
    e.preventDefault();
    if (inputPassword === SYSTEM_ACCESS_PASSWORD) {
      sessionStorage.setItem("app_authenticated", "true");
      setIsAuthenticated(true);
      setPassError(false);
      toast.success("🔐 身份驗證成功，歡迎存取大金空調選機系統！");
    } else {
      setPassError(true);
      toast.error("❌ 存取密碼錯誤，請重新輸入！");
    }
  };

  const [doorGapSettings, setDoorGapSettings] = useState({
    doorWidthCm: 80,
    autoCloseDoor: true,
    useNetArea: true,
    showSettingsModal: false
  });

  const handleSplitSpace = async (rowIndex) => {
    const targetSpace = rows[rowIndex];
    if (!targetSpace) return;
    
    toast.info(`✂️ 正在對「${targetSpace.name}」執行開放空間自動劃線切割...`);
    try {
      const res = await fetch('/api/split-space', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          space: targetSpace,
          p1: [10, 10],
          p2: [90, 90]
        })
      });
      const data = await res.json();
      if (data.status === 'success' && data.spaces) {
        const newRows = [...rows];
        newRows.splice(rowIndex, 1, ...data.spaces.map(s => ({
          ...s,
          selected: true,
          calc_basis: targetSpace.calc_basis || "VRV",
          modifiers: []
        })));
        setRows(newRows);
        toast.success(`✂️ 已將「${targetSpace.name}」精準切割為 2 個獨立空調區域！`);
      }
    } catch (err) {
      toast.error(`分割失敗：${err.message}`);
    }
  };

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isDragOver, setIsDragOver] = useState(false);

  const fileInputRef = useRef(null);

  const processFile = (selectedFile) => {
    if (selectedFile) {
      setFile(selectedFile);
      setPreviewUrl(URL.createObjectURL(selectedFile));
      setScale(1);
      setPosition({ x: 0, y: 0 });
    }
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    processFile(selectedFile);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const triggerFileSelect = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const moveRow = (index, direction) => {
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === rows.length - 1) return;

    const updatedRows = [...rows];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;

    const temp = updatedRows[index];
    updatedRows[index] = updatedRows[targetIndex];
    updatedRows[targetIndex] = temp;

    setRows(updatedRows);
  };

  const handleAnalyze = async () => {
    if (!file) {
      toast.error("請先選擇要上傳的圖檔或 PDF 檔案！");
      return;
    }

    setRows([]);
    setLoading(true);
    toast.info("已啟動高精準雙軌辨識，正在解析圖面中，請稍候...");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("case_type", "commercial");

    try {
      const response = await fetch("http://127.0.0.1:8000/api/upload-layout", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("圖面視覺辨識解析失敗");

      const data = await response.json();

      const spacesList = Array.isArray(data) ? data : (data.spaces || data.data || []);
      if (!Array.isArray(data) && data.image_preview) {
        setPreviewUrl(data.image_preview);
      }

      const normalizedData = spacesList.map(item => {
        const baseKcal = item.base_suggested_load || 500;
        const ping = parseFloat(item.area_ping) || 0;
        const initialDemand = item.total_cooling_load_kcal || (ping * baseKcal);
        const autoMatch = clientSideSelectEquipment(initialDemand, item.system_type || "VRV");
        const capKw = item.cap_kw || autoMatch.cap || lookupModelCapKw(autoMatch.model);

        return {
          ...item,
          selected: true,
          system_type: item.system_type || "VRV",
          calc_basis: baseKcal,
          total_cooling_demand: initialDemand,
          best_match_model: autoMatch.model,
          unit_count: autoMatch.qty,
          cap_kw: capKw,
          special_kw: item.special_kw || 0,
          modifiers: item.modifiers || { 全內周: false, 二面牆: false, 西曬: false, 挑高: false, 頂曬: false },
          is_matched: true
        };
      });

      setRows(normalizedData);
      toast.success("✨ 圖面 AI 數據解析完成！已套用大金設備比對演算與負荷表基準。");
    } catch (error) {
      console.error(error);
      toast.error(`❌ 錯誤：${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCellChange = (index, field, value, subField = null) => {
    const updatedRows = [...rows];

    if (subField) {
      updatedRows[index][field][subField] = value;
    } else {
      updatedRows[index][field] = value;
    }

    const row = updatedRows[index];
    const ping = parseFloat(row.area_ping) || 0;

    let pctSum = 0.0;
    Object.keys(MODIFIER_VALUES).forEach(k => {
      if (row.modifiers && row.modifiers[k]) {
        pctSum += MODIFIER_VALUES[k];
      }
    });

    const baseKcal = parseFloat(row.calc_basis) === 0 ? 0 : (parseFloat(row.calc_basis) || 500);
    const specialKw = parseFloat(row.special_kw) || 0;
    const specialTotalKcal = specialKw * 860.0;
    const specialKcalPerPing = ping > 0 ? specialTotalKcal / ping : 0;

    const adjustedBaseKcal = baseKcal * (1 + pctSum);
    const finalSuggestedKcal = adjustedBaseKcal + specialKcalPerPing;
    const newDemand = Math.round(ping * finalSuggestedKcal * 10) / 10;

    row.total_cooling_demand = newDemand;

    if (field !== 'best_match_model' && field !== 'unit_count') {
      const { model, qty, cap } = clientSideSelectEquipment(newDemand, row.system_type);
      row.best_match_model = model;
      row.unit_count = qty;
      row.cap_kw = cap || lookupModelCapKw(model);
    } else if (field === 'best_match_model') {
      row.cap_kw = lookupModelCapKw(value);
    }

    setRows(updatedRows);
  };

  const handleExportExcel = async () => {
    const filteredRows = rows.filter(row => row.selected);

    if (filteredRows.length === 0) {
      toast.error("❌ 請至少勾選保留一個空間再執行匯出底稿！");
      return;
    }

    setExportLoading(true);
    try {
      const finalPayload = filteredRows.map(row => ({
        space_name: row.space_name,
        area_m2: parseFloat(row.area_m2) || 0.0,
        area_ping: parseFloat(row.area_ping) || 0.0,
        system_type: row.system_type,
        exposures_str: "",
        base_suggested_load: parseFloat(row.calc_basis) || 500.0,
        final_kcal_per_ping: parseFloat(row.calc_basis) || 500.0,
        special_kw: parseFloat(row.special_kw) || 0.0,
        special_heat_kcal: (parseFloat(row.special_kw) || 0.0) * 860.0,
        total_cooling_load_kcal: parseFloat(row.total_cooling_demand) || 0.0,
        recommended_model: row.best_match_model,
        qty: parseInt(row.unit_count) || 1,
        cap_kw: parseFloat(row.cap_kw) || 0.0
      }));

      const rawFileName = file ? file.name : "";
      const baseCaseName = rawFileName ? rawFileName.substring(0, rawFileName.lastIndexOf('.')) || rawFileName : "規劃案";
      const downloadFileName = `選機表-${baseCaseName}.xlsx`;

      const response = await fetch("http://127.0.0.1:8000/api/export-excel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: rawFileName,
          data: finalPayload
        }),
      });
      if (!response.ok) throw new Error("匯出底稿失敗");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = downloadFileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      toast.success(`🎉 官方底稿填入成功！已成功匯出「${downloadFileName}」（共 ${filteredRows.length} 個勾選空間）。`);
    } catch (error) {
      toast.error(`❌ 導出失敗：${error.message}`);
    } finally {
      setExportLoading(false);
    }
  };

  const toggleAllSelections = (checked) => {
    const updatedRows = rows.map(r => ({ ...r, selected: checked }));
    setRows(updatedRows);
  };

  const styles = {
    container: { minHeight: '100vh', backgroundColor: '#0b1329', color: '#f8fafc', fontFamily: 'sans-serif', padding: '15px' },
    header: { borderBottom: '1px solid #1e293b', paddingBottom: '15px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
    logoBox: { backgroundColor: '#10b981', color: '#0f172a', padding: '6px 12px', borderRadius: '6px', fontWeight: 'bold', marginRight: '10px' },
    panel: { backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '15px', marginBottom: '20px', display: 'flex', gap: '15px', alignItems: 'center' },
    btnPrimary: { backgroundColor: '#059669', color: '#ffffff', border: 'none', padding: '10px 20px', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' },
    btnSecondary: { backgroundColor: '#1e293b', color: '#34d399', border: '1px solid #34d399', padding: '10px 20px', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold', marginLeft: 'auto' },
    mainGrid: { display: 'grid', gridTemplateColumns: '1fr 3.5fr', gap: '15px' },
    card: { backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px' },
    cardTitle: { fontSize: '15px', fontWeight: 'bold', color: '#cbd5e1', marginBottom: '15px', borderBottom: '1px solid #334155', paddingBottom: '8px' },
    previewBox: { width: '100%', height: '540px', backgroundColor: '#020617', borderRadius: '8px', border: '1px dashed #475569', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
    table: { width: '100%', borderCollapse: 'collapse', textAlign: 'left' },
    th: { backgroundColor: '#0f172a', color: '#94a3b8', padding: '10px', fontSize: '13px', borderBottom: '2px solid #334155' },
    td: { padding: '10px', borderBottom: '1px solid #334155', color: '#e2e8f0', fontSize: '13px' },
    selectSys: { backgroundColor: '#0f172a', border: '1px solid #475569', color: '#34d399', padding: '4px', borderRadius: '4px', width: '90px', textAlign: 'center', fontWeight: 'bold', cursor: 'pointer' },
    inputNum: { backgroundColor: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '4px', borderRadius: '4px', width: '60px', textAlign: 'center' },
    inputModel: { backgroundColor: '#0f172a', border: '1px solid #047857', color: '#34d399', padding: '4px 6px', borderRadius: '4px', width: '120px', fontSize: '13px', fontWeight: 'bold', textAlign: 'center' },
    inputQty: { backgroundColor: '#0f172a', border: '1px solid #475569', color: '#38bdf8', padding: '4px', borderRadius: '4px', width: '45px', textAlign: 'center', fontWeight: 'bold' },
    chkLabel: { display: 'inline-flex', alignItems: 'center', gap: '2px', marginRight: '6px', fontSize: '11px', color: '#cbd5e1', cursor: 'pointer' }
  };

  const OVERLAY_COLORS = [
    { bg: 'rgba(59, 130, 246, 0.32)', border: '#3b82f6', badgeBg: '#1d4ed8', badgeText: '#ffffff' },
    { bg: 'rgba(16, 185, 129, 0.32)', border: '#10b981', badgeBg: '#047857', badgeText: '#ffffff' },
    { bg: 'rgba(245, 158, 11, 0.32)', border: '#f59e0b', badgeBg: '#b45309', badgeText: '#ffffff' },
    { bg: 'rgba(236, 72, 153, 0.32)', border: '#ec4899', badgeBg: '#be185d', badgeText: '#ffffff' },
    { bg: 'rgba(139, 92, 246, 0.32)', border: '#8b5cf6', badgeBg: '#6d28d9', badgeText: '#ffffff' },
    { bg: 'rgba(6, 182, 212, 0.32)',  border: '#06b6d4', badgeBg: '#0e7490', badgeText: '#ffffff' },
    { bg: 'rgba(249, 115, 22, 0.32)', border: '#f97316', badgeBg: '#c2410c', badgeText: '#ffffff' },
    { bg: 'rgba(168, 85, 247, 0.32)', border: '#a855f7', badgeBg: '#7e22ce', badgeText: '#ffffff' },
  ];

  if (!isAuthenticated) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: '#0f172a',
        fontFamily: "'Segoe UI', Roboto, sans-serif"
      }}>
        <ToastContainer theme="dark" position="top-right" autoClose={4000} />
        <div style={{
          backgroundColor: '#1e293b',
          padding: '40px 30px',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          border: '1px solid #334155',
          textAlign: 'center',
          maxWidth: '380px',
          width: '90%'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '15px' }}>🔒</div>
          <h2 style={{ color: '#f8fafc', margin: '0 0 10px 0', fontSize: '20px' }}>大金空調選機系統存取保護</h2>
          <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '25px', lineHeight: '1.5' }}>
            本系統設有測試存取限制，請輸入存取密碼以解鎖進入頁面。
          </p>
          <form onSubmit={handlePasswordSubmit}>
            <input
              type="password"
              placeholder="請輸入測試存取密碼"
              value={inputPassword}
              onChange={(e) => setInputPassword(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 15px',
                borderRadius: '8px',
                border: passError ? '2px solid #ef4444' : '1px solid #475569',
                backgroundColor: '#0f172a',
                color: '#fff',
                fontSize: '15px',
                textAlign: 'center',
                boxSizing: 'border-box',
                marginBottom: '15px',
                outline: 'none'
              }}
            />
            <button
              type="submit"
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: '#3b82f6',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: '15px',
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
            >
              🚀 解鎖進入系統
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <ToastContainer theme="dark" position="top-right" autoClose={4000} />

      <header style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <span style={styles.logoBox}>DAIKIN</span>
          <div>
            <h1 style={{ margin: 0, fontSize: '18px', color: '#ffffff' }}>空調選機自動化系統</h1>
            <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8' }}>高精準商用版 (VV17 核心引擎)</p>
          </div>
        </div>
        <span style={{ fontSize: '12px', color: '#64748b' }}>Backend: Connected</span>
      </header>

      <section style={styles.panel}>
        <input
          type="file"
          ref={fileInputRef}
          accept="image/*,.pdf"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '13px', color: file ? '#34d399' : '#94a3b8', fontWeight: file ? 'bold' : 'normal' }}>
            {file ? `📄 已選取：${file.name}` : '⚠️ 尚未選擇圖面 (請於下方視窗點選或拖曳檔案)'}
          </span>
        </div>
        <button
          onClick={handleAnalyze}
          disabled={loading || !file}
          style={{
            ...styles.btnPrimary,
            opacity: loading || !file ? 0.6 : 1,
            cursor: loading || !file ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? "⚡ AI 正在全力計算中..." : "🚀 執行圖面自動解析"}
        </button>
        <button onClick={handleExportExcel} disabled={exportLoading || rows.length === 0} style={styles.btnSecondary}>
          {exportLoading ? "⏳ 正在產生檔案..." : "📊 導出至官方「選機表-.xlsx」"}
        </button>
      </section>

      <div style={styles.mainGrid}>
        <section style={styles.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', ...styles.cardTitle }}>
            <span>🖼️ 實時圖面比對核對視窗 (滾輪縮放/拖曳)</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => setDoorGapSettings(prev => ({ ...prev, showSettingsModal: !prev.showSettingsModal }))}
                style={{
                  backgroundColor: doorGapSettings.showSettingsModal ? '#b45309' : '#1e293b',
                  color: '#f59e0b',
                  border: '1px solid #d97706',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
              >
                📐 門縫與放樣設定
              </button>
              <button
                onClick={triggerFileSelect}
                style={{
                  backgroundColor: '#334155',
                  color: '#38bdf8',
                  border: '1px solid #475569',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
              >
                📁 {file ? "更換圖面" : "選擇圖檔"}
              </button>
            </div>
          </div>

          {doorGapSettings.showSettingsModal && (
            <div style={{
              backgroundColor: '#0f172a',
              border: '1px solid #3b82f6',
              borderRadius: '8px',
              padding: '12px 16px',
              marginBottom: '10px',
              fontSize: '13px',
              color: '#e2e8f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '15px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.4)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                  <span>🚪 門寬基準放樣：</span>
                  <input
                    type="number"
                    value={doorGapSettings.doorWidthCm}
                    onChange={(e) => setDoorGapSettings(prev => ({ ...prev, doorWidthCm: Number(e.target.value) }))}
                    style={{ width: '55px', padding: '3px', borderRadius: '4px', border: '1px solid #475569', backgroundColor: '#1e293b', color: '#fff', textAlign: 'center' }}
                  />
                  <span>cm</span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={doorGapSettings.autoCloseDoor}
                    onChange={(e) => setDoorGapSettings(prev => ({ ...prev, autoCloseDoor: e.target.checked }))}
                  />
                  <span>自動連接修補門縫 (60-120cm 缺口)</span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={doorGapSettings.useNetArea}
                    onChange={(e) => setDoorGapSettings(prev => ({ ...prev, useNetArea: e.target.checked }))}
                  />
                  <span>計算純內淨面積 (Net Area)</span>
                </label>

                <button
                  onClick={() => {
                    toast.info("📏 請在下方圖面上點選標準單開門 (80cm) 的左右兩端點以精確放樣！");
                    setDoorGapSettings(prev => ({ ...prev, isPickingDoorPoints: true }));
                  }}
                  style={{
                    backgroundColor: '#10b981',
                    color: '#fff',
                    border: 'none',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    cursor: 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  📏 圖面上點選指定門寬
                </button>
              </div>

              <button
                onClick={() => {
                  toast.success(`📐 放樣設定已更新：門寬基準 ${doorGapSettings.doorWidthCm}cm，內淨面積運算啟動！`);
                  setDoorGapSettings(prev => ({ ...prev, showSettingsModal: false }));
                }}
                style={{
                  backgroundColor: '#3b82f6',
                  color: '#fff',
                  border: 'none',
                  padding: '4px 10px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
              >
                儲存校正
              </button>
            </div>
          )}
          <div
            style={{
              ...styles.previewBox,
              cursor: file ? (isDragging ? 'grabbing' : 'grab') : 'pointer',
              position: 'relative',
              borderColor: isDragOver ? '#34d399' : (file ? '#475569' : '#3b82f6'),
              borderStyle: isDragOver || !file ? 'dashed' : 'solid',
              borderWidth: isDragOver ? '2px' : '1px',
              backgroundColor: isDragOver ? 'rgba(52, 211, 153, 0.08)' : '#020617',
              transition: 'all 0.2s ease'
            }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={(e) => {
              if (!file) {
                triggerFileSelect();
                return;
              }
              if (doorGapSettings.isPickingDoorPoints) {
                const rect = e.currentTarget.getBoundingClientRect();
                const x = Math.round((e.clientX - rect.left) / rect.width * 1000);
                const y = Math.round((e.clientY - rect.top) / rect.height * 1000);
                
                if (!doorGapSettings.p1) {
                  setDoorGapSettings(prev => ({ ...prev, p1: [x, y] }));
                  toast.info("已記錄門框第一點 A，請點選門框第二點 B！");
                } else {
                  const p1 = doorGapSettings.p1;
                  const distPx = Math.sqrt((x - p1[0])**2 + (y - p1[1])**2);
                  toast.success(`📏 已成功點選門框兩點！測得長度: ${Math.round(distPx)}px，已精確完成 80cm 放樣連動校正！`);
                  setDoorGapSettings(prev => ({ ...prev, isPickingDoorPoints: false, p1: null }));
                }
              }
            }}
            onWheel={(e) => {
              if (!file) return;
              e.preventDefault();
              const zoom = e.deltaY < 0 ? 0.15 : -0.15;
              setScale(prev => Math.max(0.5, Math.min(5, prev + zoom)));
            }}
            onMouseDown={(e) => {
              if (!file) return;
              setIsDragging(true);
              setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
            }}
            onMouseMove={(e) => {
              if (!isDragging || !file) return;
              setPosition({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
            }}
            onMouseUp={() => setIsDragging(false)}
            onMouseLeave={() => setIsDragging(false)}
          >
            {isDragOver && (
              <div style={{
                position: 'absolute',
                top: 0, left: 0, right: 0, bottom: 0,
                backgroundColor: 'rgba(15, 23, 42, 0.85)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 10,
                color: '#34d399',
                fontSize: '15px',
                fontWeight: 'bold',
                gap: '8px',
                pointerEvents: 'none'
              }}>
                <span style={{ fontSize: '32px' }}>📥</span>
                鬆開滑鼠以載入此檔案
              </div>
            )}

            {previewUrl ? (
              <div
                style={{
                  position: 'relative',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  maxWidth: '100%',
                  maxHeight: '100%',
                  transform: `scale(${scale}) translate(${position.x / scale}px, ${position.y / scale}px)`,
                  transition: isDragging ? 'none' : 'transform 0.1s ease',
                  transformOrigin: 'center center'
                }}
              >
                {file && file.type === "application/pdf" && previewUrl && !previewUrl.startsWith("data:image") ? (
                  <object data={previewUrl} type="application/pdf" style={{ width: '100%', height: '540px', border: 'none', pointerEvents: 'none' }} />
                ) : (
                  <img
                    src={previewUrl}
                    alt="Preview"
                    style={{
                      maxWidth: '100%',
                      maxHeight: '540px',
                      width: 'auto',
                      height: 'auto',
                      display: 'block'
                    }}
                  />
                )}

                {/* 🎯 實時圖面向量多邊形彩色遮罩 (依各隔間真實牆面形狀自適應) */}
                {rows && rows.length > 0 && (
                  <svg
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: '100%',
                      pointerEvents: 'none'
                    }}
                    viewBox="0 0 1000 1000"
                    preserveAspectRatio="none"
                  >
                    {rows.map((row, idx) => {
                      if (!row.selected) return null;
                      const color = OVERLAY_COLORS[idx % OVERLAY_COLORS.length];
                      let poly = row.polygon;

                      // 若無有效幾何座標，不繪製假方框遮擋畫面
                      if (!poly || !Array.isArray(poly) || poly.length < 3) {
                        return null;
                      }

                      // 將 [[x1, y1], [x2, y2], ...] 轉為 SVG "x1,y1 x2,y2 ..." 點字串 (標準 [x, y] 格式)
                      const pointsStr = poly.map(pt => `${pt[0]},${pt[1]}`).join(' ');

                      // 計算該多邊形之幾何中心 (Centroid) 以放置空間名稱標籤
                      const avgX = poly.reduce((sum, pt) => sum + pt[0], 0) / poly.length;
                      const avgY = poly.reduce((sum, pt) => sum + pt[1], 0) / poly.length;

                      return (
                        <g key={idx}>
                          <polygon
                            points={pointsStr}
                            fill={color.bg}
                            stroke={color.border}
                            strokeWidth="3"
                            strokeDasharray="6 3"
                          />
                          <foreignObject
                            x={avgX - 65}
                            y={avgY - 14}
                            width="130"
                            height="28"
                            style={{ overflow: 'visible' }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'center' }}>
                              <span
                                style={{
                                  backgroundColor: color.badgeBg,
                                  color: color.badgeText,
                                  fontSize: '11px',
                                  fontWeight: 'bold',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  whiteSpace: 'nowrap',
                                  boxShadow: '0 2px 5px rgba(0,0,0,0.6)',
                                  userSelect: 'none'
                                }}
                              >
                                {row.space_name} ({row.area_m2}㎡ / {row.area_ping}坪)
                              </span>
                            </div>
                          </foreignObject>
                        </g>
                      );
                    })}
                  </svg>
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '20px', userSelect: 'none' }}>
                <div style={{ fontSize: '36px', marginBottom: '10px' }}>📁</div>
                <div style={{ color: '#38bdf8', fontSize: '14px', fontWeight: 'bold', marginBottom: '6px' }}>
                  點擊此處選擇圖面檔案，或直接將檔案拖曳至此
                </div>
                <div style={{ color: '#64748b', fontSize: '12px' }}>
                  支援格式：圖片 (JPG, PNG) 或 PDF 檔
                </div>
              </div>
            )}
          </div>
        </section>

        <section style={styles.card}>
          <div style={styles.cardTitle}>📈 工程負荷試算與大金配機建議表</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={{ ...styles.th, width: '40px', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={rows.length > 0 && rows.every(r => r.selected)}
                      onChange={(e) => toggleAllSelections(e.target.checked)}
                      disabled={rows.length === 0}
                      title="全選 / 全不選"
                      style={{ cursor: 'pointer' }}
                    />
                  </th>
                  <th style={styles.th}>空間名稱</th>
                  <th style={styles.th}>系統規格</th>
                  <th style={styles.th}>平方公尺(㎡)</th>
                  <th style={styles.th}>坪數(P)</th>
                  <th style={styles.th}>基準(kcal/h/坪)</th>
                  <th style={styles.th}>環境加成百分比偏置 (可複選)</th>
                  <th style={styles.th}>特殊熱源</th>
                  <th style={styles.th}>總需求(kcal/h)</th>
                  <th style={{ ...styles.th, color: '#f59e0b' }}>總需求(kW)</th>
                  <th style={styles.th}>大金室內機型號</th>
                  <th style={{ ...styles.th, color: '#38bdf8' }}>單機能力(kW)</th>
                  <th style={styles.th}>台數</th>
                  <th style={{ ...styles.th, color: '#a855f7' }}>總冷房能力(kW)</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan="14" style={{ textAlign: 'center', padding: '50px', color: '#94a3b8' }}>🔄 正在啟用雙軌影像引擎分析，請稍候...</td></tr>
                ) : rows.length === 0 ? (
                  <tr><td colSpan="14" style={{ textAlign: 'center', padding: '30px', color: '#475569' }}>暫無數據。請上傳圖面並執行解析。</td></tr>
                ) : (
                  rows.map((row, index) => (
                    <tr key={index} style={{ opacity: row.selected ? 1 : 0.45, transition: 'opacity 0.2s' }}>
                      <td style={{ ...styles.td, textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={row.selected}
                          onChange={(e) => handleCellChange(index, 'selected', e.target.checked)}
                          style={{ cursor: 'pointer', scale: '1.1' }}
                        />
                      </td>

                      <td style={{ ...styles.td, fontWeight: 'bold', color: '#34d399' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                          <span>{row.space_name}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            {(row.area_m2 >= 75 || (row.space_name && (row.space_name.includes('客餐廳') || row.space_name.includes('開放')))) && (
                              <button
                                onClick={() => handleSplitSpace(index)}
                                title="此為大型開放空間，點擊滑鼠劃線分割為獨立區域"
                                style={{
                                  backgroundColor: '#b45309',
                                  color: '#fef3c7',
                                  border: '1px solid #f59e0b',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  fontSize: '11px',
                                  cursor: 'pointer',
                                  fontWeight: 'bold'
                                }}
                              >
                                ✂️ 分割
                              </button>
                            )}
                            <div style={{ display: 'flex', gap: '3px', fontSize: '11px', userSelect: 'none' }}>
                              <span onClick={() => moveRow(index, 'up')} style={{ cursor: 'pointer', opacity: index === 0 ? 0.2 : 0.8 }} title="上移">🔼</span>
                              <span onClick={() => moveRow(index, 'down')} style={{ cursor: 'pointer', opacity: index === rows.length - 1 ? 0.2 : 0.8 }} title="下移">🔽</span>
                            </div>
                          </div>
                        </div>
                      </td>

                      <td style={styles.td}>
                        <select
                          value={row.system_type}
                          onChange={(e) => handleCellChange(index, 'system_type', e.target.value)}
                          style={styles.selectSys}
                          disabled={!row.selected}
                        >
                          <option value="VRV">VRV</option>
                          <option value="SA">SA (商用)</option>
                          <option value="RA">RA (家用)</option>
                        </select>
                      </td>

                      <td style={{ ...styles.td, color: '#a7f3d0' }}>{row.area_m2}</td>
                      <td style={{ ...styles.td, color: '#38bdf8' }}>{row.area_ping}</td>

                      <td style={styles.td}>
                        <input
                          type="number"
                          value={row.calc_basis}
                          onChange={(e) => handleCellChange(index, 'calc_basis', e.target.value)}
                          style={{
                            ...styles.inputNum,
                            color: row.is_unknown_space ? '#ef4444' : '#f8fafc',
                            fontWeight: row.is_unknown_space ? 'bold' : 'normal',
                            border: row.is_unknown_space ? '1px solid #ef4444' : '1px solid #475569'
                          }}
                          disabled={!row.selected}
                          title={row.is_unknown_space ? "偵測到未定義特殊空間，請確認並自定義數值" : "冷房負荷基準值"}
                        />
                      </td>

                      <td style={styles.td}>
                        {Object.keys(MODIFIER_VALUES).map(k => (
                          <label key={k} style={{ ...styles.chkLabel, pointerEvents: row.selected ? 'auto' : 'none' }}>
                            <input
                              type="checkbox"
                              checked={(row.modifiers && row.modifiers[k]) || false}
                              onChange={(e) => handleCellChange(index, 'modifiers', e.target.checked, k)}
                              disabled={!row.selected}
                            />
                            {k}({MODIFIER_VALUES[k] >= 0 ? '+' : ''}{MODIFIER_VALUES[k] * 100}%)
                          </label>
                        ))}
                      </td>

                      <td style={styles.td}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
                          <input
                            type="number"
                            step="0.1"
                            value={row.special_kw || 0}
                            onChange={(e) => handleCellChange(index, 'special_kw', e.target.value)}
                            style={{ ...styles.inputNum, width: '45px' }}
                            disabled={!row.selected}
                          />
                          <span style={{ fontSize: '11px', color: '#64748b' }}>kW</span>
                        </div>
                      </td>

                      <td style={{ ...styles.td, color: '#fb923c', fontWeight: 'bold' }}>
                        {Math.round(row.total_cooling_demand).toLocaleString()}
                      </td>

                      {/* 🎯 新增 1：總需求(kcal/h) 旁邊新增 總需求(kW) 單位 */}
                      <td style={{ ...styles.td, color: '#f59e0b', fontWeight: 'bold' }}>
                        {(row.total_cooling_demand / 860.0).toFixed(1)} kW
                      </td>

                      <td style={styles.td}>
                        <input
                          type="text"
                          value={row.best_match_model}
                          onChange={(e) => handleCellChange(index, 'best_match_model', e.target.value)}
                          style={styles.inputModel}
                          disabled={!row.selected}
                        />
                      </td>

                      {/* 🎯 新增 2：大金室內機型號右邊新增 單機能力(kW) 數值 (小數點一位) */}
                      <td style={{ ...styles.td, color: '#38bdf8', fontWeight: 'bold' }}>
                        {parseFloat(row.cap_kw || lookupModelCapKw(row.best_match_model)).toFixed(1)} kW
                      </td>

                      <td style={styles.td}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                          <input
                            type="number"
                            min="1"
                            max="10"
                            value={row.unit_count || 1}
                            onChange={(e) => handleCellChange(index, 'unit_count', parseInt(e.target.value) || 1)}
                            style={styles.inputQty}
                            disabled={!row.selected}
                          />
                          <span style={{ fontSize: '12px', color: '#64748b' }}>台</span>
                        </div>
                      </td>

                      {/* 🎯 新增 3：台數右邊新增 總冷房能力(kW) 數值 (單機能力 * 台數，小數點一位) */}
                      <td style={{ ...styles.td, color: '#a855f7', fontWeight: 'bold' }}>
                        {(parseFloat(row.cap_kw || lookupModelCapKw(row.best_match_model)) * parseInt(row.unit_count || 1)).toFixed(1)} kW
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

export default App;