import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import { HRV_UNITS_DB, matchHrvUnit } from '../constants/acConstants';

/**
 * 全熱交換器選型表格組件 (Heat Recovery Ventilator Table)
 * 1. 提供空間勾選欄位 (含表頭全選/取消全選)
 * 2. 支援滑鼠右鍵點擊切換/選定需要全熱的空間
 * 3. 依據選定空間動態計算需求風量，加總風量、全熱型號、台數、PM2.5濾網垂直跨列合併 (rowSpan)
 * 4. 內建 PM2.5 濾網欄位提供即時點擊勾選 Checkbox
 * 5. 寬度自適應 100%，無水平滾動條，不需左右拖曳
 */
export default function HeatRecoveryVentilatorTable({
  rows = [],
  hrvState = { selectedIndices: [], airflowBasisMap: {}, hasPm25: false },
  setHrvState = null
}) {
  // 本地/全域 State 雙向支援
  const [localSelectedIndices, setLocalSelectedIndices] = useState(() => 
    rows.map((_, idx) => idx)
  );
  const [localAirflowBasisMap, setLocalAirflowBasisMap] = useState({});
  const [localHasPm25, setLocalHasPm25] = useState(false);
  const [contextMenu, setContextMenu] = useState({ show: false, x: 0, y: 0, targetIndex: null });

  // 同步全域或本地
  const selectedIndices = hrvState && Array.isArray(hrvState.selectedIndices)
    ? hrvState.selectedIndices
    : localSelectedIndices;

  const airflowBasisMap = hrvState && hrvState.airflowBasisMap
    ? hrvState.airflowBasisMap
    : localAirflowBasisMap;

  const hasPm25 = hrvState && hrvState.hasPm25 !== undefined
    ? hrvState.hasPm25
    : localHasPm25;

  const updateHrvState = (updater) => {
    if (setHrvState) {
      setHrvState(prev => {
        const next = typeof updater === 'function' ? updater(prev || {}) : updater;
        return next;
      });
    } else {
      if (updater.selectedIndices !== undefined) setLocalSelectedIndices(updater.selectedIndices);
      if (updater.airflowBasisMap !== undefined) setLocalAirflowBasisMap(updater.airflowBasisMap);
      if (updater.hasPm25 !== undefined) setLocalHasPm25(updater.hasPm25);
    }
  };

  // 初始掛載若未設定選定空間且未明確清空，預設全選
  useEffect(() => {
    if (rows.length > 0 && (!hrvState.selectedIndices || (hrvState.selectedIndices.length === 0 && !hrvState.hasCleared))) {
      const allIdx = rows.map((_, i) => i);
      updateHrvState(prev => ({
        ...prev,
        selectedIndices: allIdx,
        hasCleared: false
      }));
    }
  }, [rows.length]);

  // 單列勾選切換
  const handleToggleRowSelection = (index, e) => {
    if (e) e.stopPropagation();
    const isSelected = selectedIndices.includes(index);
    const nextIndices = isSelected
      ? selectedIndices.filter(i => i !== index)
      : [...selectedIndices, index];
    
    updateHrvState(prev => ({
      ...prev,
      selectedIndices: nextIndices,
      hasCleared: nextIndices.length === 0
    }));

    const spaceName = rows[index]?.space_name || `空間 ${index + 1}`;
    if (!isSelected) {
      toast.info(`🌀 已將【${spaceName}】納入全熱交換器規劃！`, { autoClose: 1500 });
    } else {
      toast.warn(`⚪ 已取消【${spaceName}】的全熱交換器規劃。`, { autoClose: 1500 });
    }
  };

  // 表頭全選/取消全選
  const handleToggleSelectAll = () => {
    const isAllSelected = selectedIndices.length === rows.length;
    const nextIndices = isAllSelected ? [] : rows.map((_, i) => i);
    updateHrvState(prev => ({
      ...prev,
      selectedIndices: nextIndices,
      hasCleared: isAllSelected
    }));
    if (!isAllSelected) {
      toast.success(`🌀 已全選所有 ${rows.length} 個空間納入全熱交換器！`);
    } else {
      toast.info('⚪ 已取消全選所有空間。');
    }
  };

  // 風量規劃基準變更
  const handleAirflowBasisChange = (index, val) => {
    const nextMap = {
      ...airflowBasisMap,
      [index]: val
    };
    updateHrvState(prev => ({
      ...prev,
      airflowBasisMap: nextMap
    }));
  };

  // PM2.5 濾網切換
  const handleTogglePm25 = (e) => {
    const nextVal = e.target.checked;
    updateHrvState(prev => ({
      ...prev,
      hasPm25: nextVal
    }));
    if (nextVal) {
      toast.success('🌿 已為全熱交換器勾選【內建 PM2.5 濾網】！');
    } else {
      toast.info('⚪ 已取消內建 PM2.5 濾網。');
    }
  };

  // 滑鼠右鍵事件
  const handleRowContextMenu = (e, index) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      show: true,
      x: e.clientX,
      y: e.clientY,
      targetIndex: index
    });
  };

  // 關閉右鍵選單
  useEffect(() => {
    const handleClickOutside = () => {
      if (contextMenu.show) setContextMenu({ show: false, x: 0, y: 0, targetIndex: null });
    };
    window.addEventListener('click', handleClickOutside);
    return () => window.removeEventListener('click', handleClickOutside);
  }, [contextMenu.show]);

  // 計算每個空間的預估人數與風量
  const spaceCalculations = rows.map((row, index) => {
    const areaM2 = parseFloat(row.area_m2) || ((parseFloat(row.area_ping) || 0) / 0.3025) || 0;
    const areaPing = parseFloat(row.area_ping) || (areaM2 > 0 ? areaM2 * 0.3025 : 0);
    const estimatedPeople = areaM2 > 0 ? Math.ceil(areaM2 / 5.0) : 1;
    const currentBasisVal = airflowBasisMap[index] !== undefined ? airflowBasisMap[index] : 30;
    const indoorDemandAirflow = estimatedPeople * currentBasisVal;
    const isSelected = selectedIndices.includes(index);

    return {
      index,
      spaceName: (row.space_name || row.room_name || row.name || `空間 ${index + 1}`).trim(),
      areaM2,
      areaPing,
      estimatedPeople,
      currentBasisVal,
      indoorDemandAirflow,
      isSelected
    };
  });

  // 加總風量：嚴格根據使用者「選定的空間」決定總風量
  const totalAirflow = spaceCalculations
    .filter(sp => sp.isSelected)
    .reduce((acc, sp) => acc + sp.indoorDemandAirflow, 0);

  // 根據加總風量比對大金 HRV 規格資料庫
  const matchedHrv = totalAirflow > 0 ? matchHrvUnit(totalAirflow) : null;

  const selectedCount = selectedIndices.length;
  const isAllSelected = rows.length > 0 && selectedCount === rows.length;

  const styles = {
    container: {
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      width: '100%',
      animation: 'fadeIn 0.2s ease-in-out'
    },
    headerBanner: {
      backgroundColor: 'rgba(14, 165, 233, 0.08)',
      border: '1px solid rgba(14, 165, 233, 0.3)',
      borderRadius: '8px',
      padding: '10px 16px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '12px',
      flexWrap: 'wrap'
    },
    bannerTitle: {
      fontSize: '13.5px',
      fontWeight: 'bold',
      color: '#38bdf8',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    },
    statsBadge: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '12px',
      fontSize: '12.5px',
      color: '#cbd5e1'
    },
    tableWrapper: {
      width: '100%',
      overflowX: 'hidden',
      borderRadius: '8px',
      border: '1px solid #334155',
      backgroundColor: '#0b1329',
      boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)'
    },
    table: {
      width: '100%',
      tableLayout: 'fixed',
      borderCollapse: 'collapse',
      textAlign: 'left',
      fontSize: '13px'
    },
    th: {
      backgroundColor: '#0f172a',
      color: '#94a3b8',
      padding: '10px 8px',
      fontWeight: 'bold',
      fontSize: '12.5px',
      borderBottom: '1.5px solid #334155',
      userSelect: 'none',
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    },
    td: {
      padding: '9px 8px',
      borderBottom: '1px solid #1e293b',
      color: '#f8fafc',
      fontSize: '13px',
      verticalAlign: 'middle',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    },
    mergedTd: {
      padding: '14px 10px',
      borderBottom: '1px solid #334155',
      borderLeft: '1.5px solid rgba(56, 189, 248, 0.25)',
      backgroundColor: 'rgba(15, 23, 42, 0.75)',
      verticalAlign: 'middle',
      textAlign: 'center'
    },
    checkbox: {
      cursor: 'pointer',
      width: '16px',
      height: '16px',
      accentColor: '#0ea5e9'
    },
    basisInput: {
      backgroundColor: '#0f172a',
      color: '#f8fafc',
      border: '1px solid #475569',
      borderRadius: '4px',
      padding: '3px 6px',
      width: '46px',
      textAlign: 'center',
      fontSize: '12.5px',
      fontWeight: 'bold',
      outline: 'none'
    },
    contextMenu: {
      position: 'fixed',
      top: `${contextMenu.y}px`,
      left: `${contextMenu.x}px`,
      backgroundColor: '#1e293b',
      border: '1px solid #0ea5e9',
      borderRadius: '8px',
      boxShadow: '0 10px 30px rgba(0, 0, 0, 0.8), 0 0 15px rgba(14, 165, 233, 0.3)',
      zIndex: 99999,
      padding: '6px',
      minWidth: '200px',
      display: 'flex',
      flexDirection: 'column',
      gap: '4px'
    },
    contextMenuItem: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      padding: '8px 12px',
      color: '#f8fafc',
      fontSize: '12.5px',
      borderRadius: '4px',
      cursor: 'pointer',
      transition: 'background-color 0.15s ease'
    }
  };

  const isCurrentlySelected = contextMenu.targetIndex !== null && selectedIndices.includes(contextMenu.targetIndex);

  return (
    <div style={styles.container}>
      {/* 頂部全熱交換器即時統計與快速狀態列 */}
      <div style={styles.headerBanner}>
        <div style={styles.bannerTitle}>
          <span>🌀 全熱交換器規劃選型表</span>
          <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 'normal' }}>
            （支援勾選與按滑鼠右鍵選定全熱空間，加總風量動態匹配型號）
          </span>
        </div>

        <div style={styles.statsBadge}>
          <span>
            選定空間：<strong style={{ color: selectedCount > 0 ? '#38bdf8' : '#94a3b8' }}>{selectedCount} / {rows.length} 間</strong>
          </span>
          <span>|</span>
          <span>
            加總風量：<strong style={{ color: totalAirflow > 0 ? '#34d399' : '#94a3b8', fontSize: '13.5px' }}>
              {totalAirflow.toLocaleString()} m³/hr
            </strong>
          </span>
          <span>|</span>
          <span>
            全熱推薦型號：
            <strong style={{ color: matchedHrv ? '#c084fc' : '#94a3b8', fontSize: '13.5px' }}>
              {matchedHrv ? matchedHrv.model : '尚未選定空間'}
            </strong>
          </span>
          {matchedHrv && (
            <>
              <span>|</span>
              <span>
                耗電：<strong style={{ color: '#facc15' }}>{matchedHrv.power_kw} kW</strong>
              </span>
            </>
          )}
        </div>
      </div>

      {/* 選型清單表格：100% 寬度、無水平拖曳軸 */}
      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              {/* 1. 項次 (勾選) */}
              <th style={{ ...styles.th, width: '56px', textAlign: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                  <input
                    type="checkbox"
                    checked={isAllSelected}
                    onChange={handleToggleSelectAll}
                    style={styles.checkbox}
                    title={isAllSelected ? "取消全選所有空間" : "全選所有空間"}
                  />
                  <span>項次</span>
                </div>
              </th>

              {/* 2. 空間名稱 */}
              <th style={{ ...styles.th, width: '15%' }}>空間名稱</th>

              {/* 3. 面積 */}
              <th style={{ ...styles.th, width: '14%', textAlign: 'center' }}>面積(㎡/坪數)</th>

              {/* 4. 預計人數 */}
              <th style={{ ...styles.th, width: '9%', textAlign: 'center', color: '#38bdf8' }} title="以 5㎡/人 計算，小數自動無條件進位">
                預計人數
              </th>

              {/* 5. 風量規劃基準 */}
              <th style={{ ...styles.th, width: '15%', textAlign: 'center', color: '#f59e0b' }} title="預設 30 m³/hr/人，可自行手動修改">
                風量規劃基準
              </th>

              {/* 6. 室內需求風量 */}
              <th style={{ ...styles.th, width: '13%', textAlign: 'center', color: '#34d399' }} title="室內需求風量 = 預計人數 × 風量規劃基準">
                室內需求風量
              </th>

              {/* 7. 加總風量 (合併欄位) */}
              <th style={{ ...styles.th, width: '11%', textAlign: 'center', color: '#10b981', borderLeft: '1.5px solid #334155' }}>
                加總風量
              </th>

              {/* 8. 全熱型號 (合併欄位) */}
              <th style={{ ...styles.th, width: '13%', textAlign: 'center', color: '#c084fc' }}>
                全熱型號
              </th>

              {/* 9. 台數 (合併欄位) */}
              <th style={{ ...styles.th, width: '7%', textAlign: 'center' }}>
                台數
              </th>

              {/* 10. 內建PM2.5濾網 (合併欄位，可勾選) */}
              <th style={{ ...styles.th, width: '11%', textAlign: 'center', color: '#34d399' }}>
                內建PM2.5濾網
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan="10" style={{ ...styles.td, textAlign: 'center', padding: '36px', color: '#64748b' }}>
                  目前尚無空間資料。請先於圖面上載入圖面並完成空間辨識或框選。
                </td>
              </tr>
            ) : (
              spaceCalculations.map((calc, index) => {
                const isSelected = calc.isSelected;
                const isFirstRow = index === 0;
                const totalRows = spaceCalculations.length;

                return (
                  <tr
                    key={index}
                    onContextMenu={(e) => handleRowContextMenu(e, index)}
                    style={{
                      backgroundColor: isSelected
                        ? (index % 2 === 1 ? 'rgba(14, 165, 233, 0.08)' : 'rgba(14, 165, 233, 0.04)')
                        : (index % 2 === 1 ? '#0f172a' : '#0b1329'),
                      borderLeft: isSelected ? '3px solid #0ea5e9' : '3px solid transparent',
                      transition: 'background-color 0.15s ease',
                      cursor: 'context-menu'
                    }}
                  >
                    {/* 1. 勾選 + 項次 */}
                    <td style={{ ...styles.td, textAlign: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={(e) => handleToggleRowSelection(index, e)}
                          style={styles.checkbox}
                          title={isSelected ? "點擊取消納入全熱規劃" : "點擊納入全熱規劃"}
                        />
                        <span style={{ fontWeight: 'bold', color: isSelected ? '#38bdf8' : '#64748b' }}>
                          {index + 1}
                        </span>
                      </div>
                    </td>

                    {/* 2. 空間名稱 */}
                    <td style={{ ...styles.td, fontWeight: 'bold' }}>
                      <span style={{ color: isSelected ? '#f8fafc' : '#64748b' }}>
                        {calc.spaceName}
                      </span>
                    </td>

                    {/* 3. 面積 */}
                    <td style={{ ...styles.td, textAlign: 'center' }}>
                      <span style={{ color: isSelected ? '#cbd5e1' : '#64748b' }}>
                        {calc.areaM2.toFixed(1)} ㎡ / {calc.areaPing.toFixed(1)} 坪
                      </span>
                    </td>

                    {/* 4. 預計人數 */}
                    <td style={{ ...styles.td, textAlign: 'center' }}>
                      <span style={{
                        color: isSelected ? '#38bdf8' : '#64748b',
                        fontWeight: 'bold',
                        backgroundColor: isSelected ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                        padding: '2px 8px',
                        borderRadius: '4px'
                      }}>
                        {calc.estimatedPeople} 人
                      </span>
                    </td>

                    {/* 5. 風量規劃基準 */}
                    <td style={{ ...styles.td, textAlign: 'center' }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <input
                          type="number"
                          min="10"
                          max="120"
                          step="5"
                          disabled={!isSelected}
                          value={calc.currentBasisVal}
                          onChange={(e) => handleAirflowBasisChange(index, parseInt(e.target.value) || 30)}
                          style={{
                            ...styles.basisInput,
                            opacity: isSelected ? 1 : 0.45,
                            cursor: isSelected ? 'text' : 'not-allowed'
                          }}
                        />
                        <span style={{ fontSize: '11.5px', color: isSelected ? '#94a3b8' : '#475569' }}>
                          m³/hr/人
                        </span>
                      </div>
                    </td>

                    {/* 6. 室內需求風量 */}
                    <td style={{ ...styles.td, textAlign: 'center' }}>
                      <span style={{
                        color: isSelected ? '#34d399' : '#475569',
                        fontWeight: 'bold'
                      }}>
                        {isSelected ? `${calc.indoorDemandAirflow.toLocaleString()} m³/hr` : '-'}
                      </span>
                    </td>

                    {/* ======================================================== */}
                    {/* 7 ~ 10. 全熱交換器整組屬性：垂直合併 (rowSpan) 成單一儲存格 */}
                    {/* ======================================================== */}
                    {isFirstRow && (
                      <>
                        {/* 7. 加總風量 (合併儲存格) */}
                        <td
                          rowSpan={totalRows}
                          style={{
                            ...styles.mergedTd,
                            backgroundColor: totalAirflow > 0 ? 'rgba(16, 185, 129, 0.08)' : 'rgba(15, 23, 42, 0.8)'
                          }}
                        >
                          {totalAirflow > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px' }}>
                              <span style={{
                                color: '#34d399',
                                fontWeight: 'bold',
                                fontSize: '15px'
                              }}>
                                {totalAirflow.toLocaleString()}
                              </span>
                              <span style={{ fontSize: '11px', color: '#6ee7b7' }}>m³/hr</span>
                              <span style={{ fontSize: '10.5px', color: '#94a3b8', marginTop: '2px' }}>
                                (已選 {selectedCount} 空間)
                              </span>
                            </div>
                          ) : (
                            <span style={{ color: '#475569' }}>-</span>
                          )}
                        </td>

                        {/* 8. 全熱型號 (合併儲存格) */}
                        <td rowSpan={totalRows} style={styles.mergedTd}>
                          {matchedHrv ? (
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                              <span style={{
                                color: '#c084fc',
                                fontWeight: 'bold',
                                fontSize: '13.5px',
                                backgroundColor: 'rgba(192, 132, 252, 0.15)',
                                padding: '5px 10px',
                                borderRadius: '6px',
                                border: '1px solid rgba(192, 132, 252, 0.35)',
                                letterSpacing: '0.5px'
                              }}>
                                {matchedHrv.model}
                              </span>
                              <span style={{ fontSize: '11px', color: '#a855f7' }}>
                                風量 {matchedHrv.airflow} CMH
                              </span>
                            </div>
                          ) : (
                            <span style={{ color: '#475569' }}>尚未選定空間</span>
                          )}
                        </td>

                        {/* 9. 台數 (合併儲存格) */}
                        <td rowSpan={totalRows} style={styles.mergedTd}>
                          {matchedHrv ? (
                            <span style={{ fontWeight: 'bold', color: '#f8fafc', fontSize: '13.5px' }}>
                              1 台
                            </span>
                          ) : (
                            <span style={{ color: '#475569' }}>-</span>
                          )}
                        </td>

                        {/* 10. 內建PM2.5濾網 (合併儲存格，直接提供勾選 Checkbox) */}
                        <td rowSpan={totalRows} style={styles.mergedTd}>
                          <label
                            style={{
                              display: 'inline-flex',
                              flexDirection: 'column',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '6px',
                              cursor: 'pointer',
                              userSelect: 'none',
                              padding: '8px 10px',
                              borderRadius: '6px',
                              backgroundColor: hasPm25 ? 'rgba(16, 185, 129, 0.18)' : 'rgba(51, 65, 85, 0.4)',
                              border: hasPm25 ? '1.5px solid #10b981' : '1px solid #475569',
                              transition: 'all 0.2s ease'
                            }}
                            title="勾選是否需要內建 PM2.5 濾網"
                          >
                            <input
                              type="checkbox"
                              checked={hasPm25}
                              onChange={handleTogglePm25}
                              style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: '#10b981' }}
                            />
                            <span style={{
                              fontSize: '12px',
                              fontWeight: 'bold',
                              color: hasPm25 ? '#34d399' : '#94a3b8',
                              whiteSpace: 'nowrap'
                            }}>
                              {hasPm25 ? '✓ 需要' : '未勾選'}
                            </span>
                          </label>
                        </td>
                      </>
                    )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 滑鼠右鍵 Context Menu */}
      {contextMenu.show && (
        <div style={styles.contextMenu}>
          <div
            style={styles.contextMenuItem}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#334155'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            onClick={() => {
              if (contextMenu.targetIndex !== null) {
                handleToggleRowSelection(contextMenu.targetIndex);
              }
              setContextMenu({ show: false, x: 0, y: 0, targetIndex: null });
            }}
          >
            <span>{isCurrentlySelected ? '✕' : '✓'}</span>
            <span>{isCurrentlySelected ? '取消此空間之全熱規劃' : '納入全熱交換器規劃'}</span>
          </div>

          <div style={{ height: '1px', backgroundColor: '#334155', margin: '2px 0' }} />

          <div
            style={styles.contextMenuItem}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#334155'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            onClick={() => {
              const all = rows.map((_, i) => i);
              updateHrvState(prev => ({ ...prev, selectedIndices: all, hasCleared: false }));
              toast.success('🌀 已將全部空間納入全熱交換器！');
              setContextMenu({ show: false, x: 0, y: 0, targetIndex: null });
            }}
          >
            <span>⊞</span>
            <span>全部空間納入全熱</span>
          </div>

          <div
            style={styles.contextMenuItem}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#334155'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            onClick={() => {
              updateHrvState(prev => ({ ...prev, selectedIndices: [], hasCleared: true }));
              toast.info('⚪ 已取消全部空間之全熱規劃。');
              setContextMenu({ show: false, x: 0, y: 0, targetIndex: null });
            }}
          >
            <span>⊟</span>
            <span>清空全部全熱規劃</span>
          </div>
        </div>
      )}
    </div>
  );
}
