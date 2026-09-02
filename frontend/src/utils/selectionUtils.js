import { EQUIPMENT_DB, DYNAMIC_LOAD_RULES, SA_MATCHED_PAIRS } from '../constants/acConstants.js';

// 🎯 SA 商用系統 1對1 精確欄位配對檢索 (依據 EQUIPMENT_Data.xlsx 之 indoor_units_SA only 與 outdoor_units_SA only)
export const getSaPairByIndoorModel = (indoorModel, powerSupply = null, seriesName = null) => {
  if (!indoorModel || !SA_MATCHED_PAIRS) return null;
  const cleanModel = String(indoorModel).trim();
  let matches = SA_MATCHED_PAIRS.filter(p => p.indoor.model === cleanModel);
  if (matches.length === 0) return null;

  if (seriesName) {
    const seriesMatches = matches.filter(p => p.series === seriesName || p.indoor.series === seriesName);
    if (seriesMatches.length > 0) matches = seriesMatches;
  }

  if (powerSupply) {
    const pwrMatches = matches.filter(p => p.outdoor.power_supply === powerSupply);
    if (pwrMatches.length > 0) return pwrMatches[0];
  }

  return matches[0];
};

export const getSaPairByOutdoorModel = (outdoorModel) => {
  if (!outdoorModel || !SA_MATCHED_PAIRS) return null;
  const cleanModel = String(outdoorModel).trim();
  return SA_MATCHED_PAIRS.find(p => p.outdoor.model === cleanModel) || null;
};

// 🎯 動態相容配機演算法：依據系統、系列別與室內機型式進行最佳能力單機/多機匹配 (嚴格鎖定系列別)
export const clientSideSelectEquipment = (totalDemandKcal, systemType, seriesName = null, unitTypeName = null, powerSupply = null) => {
  if (!systemType) {
    return { model: '', qty: 1, cap: 0.0 };
  }
  const totalLoadKw = totalDemandKcal / 860.0;

  // 🎯 若為 SA 系統，直接依據 SA_MATCHED_PAIRS 嚴格配對池挑選
  if (systemType === 'SA' && SA_MATCHED_PAIRS && SA_MATCHED_PAIRS.length > 0) {
    let saPool = [...SA_MATCHED_PAIRS];
    if (seriesName) {
      saPool = saPool.filter(p => p.series === seriesName || p.indoor.series === seriesName);
    }
    if (unitTypeName) {
      saPool = saPool.filter(p => p.indoor.unit_type === unitTypeName);
    }
    if (powerSupply) {
      const pwrPool = saPool.filter(p => p.outdoor.power_supply === powerSupply);
      if (pwrPool.length > 0) saPool = pwrPool;
    }
    if (saPool.length > 0) {
      // 依室內機能力排序
      saPool.sort((a, b) => a.indoor.cap_kw - b.indoor.cap_kw);
      const matched = saPool.find(p => p.indoor.cap_kw >= totalLoadKw) || saPool[saPool.length - 1];
      return {
        model: matched.indoor.model,
        qty: 1,
        cap: matched.indoor.cap_kw,
        unit_type: matched.indoor.unit_type,
        outdoor_model: matched.outdoor.model,
        power_supply: matched.outdoor.power_supply,
        col: matched.col,
        saPair: matched
      };
    }
  }

  let modelsList = EQUIPMENT_DB[systemType] || [];
  if (!modelsList || modelsList.length === 0) {
    return { model: '', qty: 1, cap: 0.0 };
  }

  if (seriesName) {
    const seriesFiltered = modelsList.filter(m => m.series === seriesName);
    if (seriesFiltered.length > 0) modelsList = seriesFiltered;
  }
  if (unitTypeName) {
    const unitFiltered = modelsList.filter(m => m.unit_type === unitTypeName);
    if (unitFiltered.length > 0) modelsList = unitFiltered;
  }

  let bestModel = null;
  let bestQty = 999;
  let bestCap = 0.0;

  for (let i = 0; i < modelsList.length; i++) {
    const singleCap = modelsList[i].cap;
    for (let qty = 1; qty <= 100; qty++) {
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

  // 🎯 絕對限制在已知過濾系列別陣列 (modelsList) 中最大能力機型，以台數擴充，絕不跳至其它系列型號
  const maxItem = modelsList[modelsList.length - 1];
  let neededQty = Math.ceil(totalLoadKw / maxItem.cap);
  if (neededQty <= 0) neededQty = 1;
  return { model: maxItem.model, qty: neededQty, cap: maxItem.cap };
};

// 🎯 細緻選機模式專用：限制下拉選單僅呈現系列別內容量落在估算需求 ±20% 範圍內的對應機型
export const getFilteredModelsForDetailMode = (systemType, seriesName, totalDemandKcal) => {
  const curSys = systemType || 'VRV';
  let allModels = EQUIPMENT_DB[curSys] || [];

  if (seriesName) {
    const seriesFiltered = allModels.filter(m => m.series === seriesName);
    if (seriesFiltered.length > 0) allModels = seriesFiltered;
  }

  if (allModels.length === 0) return [];

  const targetKw = (totalDemandKcal || 0) / 860.0;
  if (targetKw <= 0) return Array.from(new Set(allModels.map(m => m.model)));

  const minKw = targetKw * 0.8;
  const maxKw = targetKw * 1.2;

  // 過濾單機或多機組合容量落在 targetKw ±20% 範圍內的候選機型
  const filtered = allModels.filter(m => {
    const singleCap = m.cap;
    if (singleCap >= minKw && singleCap <= maxKw) return true;
    for (let qty = 2; qty <= 5; qty++) {
      const tot = singleCap * qty;
      if (tot >= minKw && tot <= maxKw) return true;
    }
    return false;
  });

  if (filtered.length > 0) {
    return Array.from(new Set(filtered.map(m => m.model)));
  }

  // 備用防護：若無落在 ±20% 者，排序最接近容量的該系列候選機型
  const sorted = [...allModels].sort((a, b) => Math.abs(a.cap - targetKw) - Math.abs(b.cap - targetKw));
  return Array.from(new Set(sorted.map(m => m.model)));
};

export const getDynamicModelCandidates = (demandKw, system, series, unitType) => {
  const sysKey = system || 'VRV';
  const allModels = EQUIPMENT_DB[sysKey] || EQUIPMENT_DB['VRV'] || [];
  let filtered = allModels;

  if (series) {
    filtered = filtered.filter(m => m.series === series);
  }
  if (unitType) {
    filtered = filtered.filter(m => m.unit_type === unitType);
  }
  if (filtered.length === 0) {
    filtered = allModels;
  }

  const kw = demandKw || 2.2;
  const minKw = kw * 0.8;
  const maxKw = kw * 1.2;
  const inRange = filtered.filter(m => m.cap >= minKw && m.cap <= maxKw);
  const result = inRange.length > 0 ? inRange : filtered;
  const sorted = [...result].sort((a, b) => a.cap - b.cap);

  return sorted.map(m => m.model);
};

export const lookupModelCapKw = (modelName) => {
  if (!modelName) return 0.0;
  const allModels = [
    ...(EQUIPMENT_DB.VRV || []),
    ...(EQUIPMENT_DB.RA || []),
    ...(EQUIPMENT_DB.SA || [])
  ];
  const matched = allModels.find(m => m.model === modelName.trim());
  return matched ? matched.cap : 0.0;
};

export const getFuzzyBaseLoadByName = (spaceName) => {
  if (!spaceName) return 500.0;
  const cleanName = spaceName.trim();
  for (const rule of DYNAMIC_LOAD_RULES) {
    for (const kw of rule.keywords) {
      if (cleanName.includes(kw) || kw.includes(cleanName)) {
        return rule.load;
      }
    }
  }
  return 500.0;
};

export const calculateShoelaceArea = (pts) => {
  if (!pts || pts.length < 3) return 0;
  let area = 0;
  for (let i = 0; i < pts.length; i++) {
    const j = (i + 1) % pts.length;
    area += pts[i][0] * pts[j][1];
    area -= pts[j][0] * pts[i][1];
  }
  return Math.abs(area) / 2.0;
};

// 🎯 消除長寬比 (Aspect Ratio) 變形之精準面積算式
export const calculateRealAreaFromPolygon = (polygon, ratio, imgW = 1600, imgH = 1200) => {
  if (!polygon || polygon.length < 3) return 0;
  const rawPoly = polygon.map(pt => [
    (pt[0] / 1000.0) * imgW,
    (pt[1] / 1000.0) * imgH
  ]);
  const rawPxArea = calculateShoelaceArea(rawPoly);
  const r = ratio || 0.0065;
  const m2 = rawPxArea * (r * r);
  return parseFloat(m2.toFixed(2));
};
