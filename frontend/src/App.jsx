import React, { useState } from 'react';
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

  for (let i = 0; i < modelsList.length; i++) {
    if (modelsList[i].cap >= totalLoadKw) {
      return { model: modelsList[i].model, qty: 1 };
    }
  }

  const maxItem = modelsList[modelsList.length - 1];
  const neededQty = Math.ceil(totalLoadKw / maxItem.cap);

  return { model: maxItem.model, qty: neededQty > 0 ? neededQty : 1 };
};

function App() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPreviewUrl(URL.createObjectURL(selectedFile));
      setScale(1);
      setPosition({ x: 0, y: 0 });
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

      // 🎯 優化：移除干擾視線的特殊空間黃色警告彈窗，改為表格內紅字直接警示

      const normalizedData = data.map(item => {
        const baseKcal = item.base_suggested_load || 500;
        const ping = parseFloat(item.area_ping) || 0;
        const initialDemand = item.total_cooling_load_kcal || (ping * baseKcal);
        const autoMatch = clientSideSelectEquipment(initialDemand, item.system_type || "VRV");

        return {
          ...item,
          selected: true,
          system_type: item.system_type || "VRV",
          calc_basis: baseKcal,
          total_cooling_demand: initialDemand,
          best_match_model: autoMatch.model,
          unit_count: autoMatch.qty,
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

    // 🎯 核心自定義修改連動：取使用者當下輸入的基準值，若為空則保底 0
    const baseKcal = parseFloat(row.calc_basis) === 0 ? 0 : (parseFloat(row.calc_basis) || 500);
    const specialKw = parseFloat(row.special_kw) || 0;
    const specialTotalKcal = specialKw * 860.0;
    const specialKcalPerPing = ping > 0 ? specialTotalKcal / ping : 0;

    const adjustedBaseKcal = baseKcal * (1 + pctSum);
    const finalSuggestedKcal = adjustedBaseKcal + specialKcalPerPing;
    const newDemand = Math.round(ping * finalSuggestedKcal * 10) / 10;

    row.total_cooling_demand = newDemand;

    // 當變更的不是型號手打或台數時，一律自動重新配對最合適的大金機型與台數
    if (field !== 'best_match_model' && field !== 'unit_count') {
      const { model, qty } = clientSideSelectEquipment(newDemand, row.system_type);
      row.best_match_model = model;
      row.unit_count = qty;
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

      const response = await fetch("http://127.0.0.1:8000/api/export-excel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: finalPayload }),
      });
      if (!response.ok) throw new Error("匯出底稿失敗");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = "空調選機規劃表_已套印.xlsx";
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      toast.success(`🎉 官方底稿填入成功！已成功匯出共 ${filteredRows.length} 個勾選空間。`);
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
        <input type="file" accept="image/*,.pdf" onChange={handleFileChange} style={{ color: '#94a3b8', fontSize: '14px' }} />
        <button onClick={handleAnalyze} disabled={loading} style={styles.btnPrimary}>
          {loading ? "⚡ AI 正在全力計算中..." : "🚀 執行圖面自動解析"}
        </button>
        <button onClick={handleExportExcel} disabled={exportLoading || rows.length === 0} style={styles.btnSecondary}>
          {exportLoading ? "⏳ 正在產生檔案..." : "📊 導出至官方「選機表-.xlsx」"}
        </button>
      </section>

      <div style={styles.mainGrid}>
        <section style={styles.card}>
          <div style={styles.cardTitle}>🖼️ 實時圖面比對核對視窗 (滾輪縮放/拖曳)</div>
          <div
            style={{ ...styles.previewBox, cursor: isDragging ? 'grabbing' : 'grab', position: 'relative' }}
            onWheel={(e) => {
              e.preventDefault();
              const zoom = e.deltaY < 0 ? 0.15 : -0.15;
              setScale(prev => Math.max(0.5, Math.min(5, prev + zoom)));
            }}
            onMouseDown={(e) => {
              setIsDragging(true);
              setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
            }}
            onMouseMove={(e) => {
              if (!isDragging) return;
              setPosition({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
            }}
            onMouseUp={() => setIsDragging(false)}
            onMouseLeave={() => setIsDragging(false)}
          >
            {previewUrl ? (
              file && file.type === "application/pdf" ? (
                <object data={previewUrl} type="application/pdf" style={{ width: '100%', height: '100%', border: 'none' }} />
              ) : (
                <img
                  src={previewUrl}
                  alt="Preview"
                  style={{
                    maxWidth: '100%',
                    maxHeight: '100%',
                    objectFit: 'contain',
                    transform: `scale(${scale}) translate(${position.x / scale}px, ${position.y / scale}px)`,
                    transition: isDragging ? 'none' : 'transform 0.1s ease'
                  }}
                />
              )
            ) : (
              <span style={{ color: '#475569', fontSize: '13px' }}>尚未載入圖面</span>
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
                  <th style={styles.th}>大金室內機型號</th>
                  <th style={styles.th}>台數</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan="11" style={{ textAlign: 'center', padding: '50px', color: '#94a3b8' }}>🔄 正在啟用雙軌影像引擎分析，請稍候...</td></tr>
                ) : rows.length === 0 ? (
                  <tr><td colSpan="11" style={{ textAlign: 'center', padding: '30px', color: '#475569' }}>暫無數據。請上傳圖面並執行解析。</td></tr>
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
                          <div style={{ display: 'flex', gap: '3px', fontSize: '11px', userSelect: 'none' }}>
                            <span onClick={() => moveRow(index, 'up')} style={{ cursor: 'pointer', opacity: index === 0 ? 0.2 : 0.8 }} title="上移">🔼</span>
                            <span onClick={() => moveRow(index, 'down')} style={{ cursor: 'pointer', opacity: index === rows.length - 1 ? 0.2 : 0.8 }} title="下移">🔽</span>
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
                        {/* 🎯 關鍵優化：如果是未定義空間 (is_unknown_space)，輸入框文字直接強制變為紅色粗體！並支援隨時自定義數值 */}
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

                      <td style={styles.td}>
                        <input
                          type="text"
                          value={row.best_match_model}
                          onChange={(e) => handleCellChange(index, 'best_match_model', e.target.value)}
                          style={styles.inputModel}
                          disabled={!row.selected}
                        />
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