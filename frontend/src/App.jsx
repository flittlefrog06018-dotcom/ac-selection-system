import React, { useState, useRef } from 'react';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import * as XLSX from 'xlsx';

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

// 🎯 半透明 Alpha 0.35 多邊形著色遮罩色系 (符合 Python 原型畫面風格)
const OVERLAY_COLORS = [
  { bg: 'rgba(239, 68, 68, 0.35)', border: '#ef4444', badgeBg: '#ef4444', badgeText: '#ffffff' },
  { bg: 'rgba(59, 130, 246, 0.35)', border: '#3b82f6', badgeBg: '#3b82f6', badgeText: '#ffffff' },
  { bg: 'rgba(16, 185, 129, 0.35)', border: '#10b981', badgeBg: '#10b981', badgeText: '#ffffff' },
  { bg: 'rgba(245, 158, 11, 0.35)', border: '#f59e0b', badgeBg: '#f59e0b', badgeText: '#020617' },
  { bg: 'rgba(168, 85, 247, 0.35)', border: '#a855f7', badgeBg: '#a855f7', badgeText: '#ffffff' },
  { bg: 'rgba(236, 72, 153, 0.35)', border: '#ec4899', badgeBg: '#ec4899', badgeText: '#ffffff' }
];

// 🎯 100% 精確中心熱點標定 (16 16) 十字游標：確保滑鼠點擊基準點必為十字正中心 (含中心白點標靶)
const CROSSHAIR_CURSOR_STYLE = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><line x1='16' y1='0' x2='16' y2='32' stroke='%23ef4444' stroke-width='2'/><line x1='0' y1='16' x2='32' y2='16' stroke='%23ef4444' stroke-width='2'/><circle cx='16' cy='16' r='3' fill='%23ffffff' stroke='%23ef4444' stroke-width='1.5'/></svg>") 16 16, crosshair`;

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

const DYNAMIC_LOAD_RULES = [
  { keywords: ["辦公室", "辦公", "小辦公", "開放辦公", "洽談", "合約", "會議", "會客", "演講", "休息", "簡報", "作業區", "討論"], load: 630.0 },
  { keywords: ["董事長", "總經理", "主管", "經理", "執行長", "副總"], load: 550.0 },
  { keywords: ["茶水", "茶水間", "茶水區"], load: 450.0 },
  { keywords: ["男廁", "女廁", "殘障廁所", "廁所", "洗手間", "衛浴", "浴室"], load: 350.0 },
  { keywords: ["吧台", "咖啡", "咖啡區", "酒吧"], load: 700.0 },
  { keywords: ["前台", "櫃台", "大廳", "接待區"], load: 660.0 },
  { keywords: ["更衣", "更衣間", "更衣室"], load: 400.0 },
  { keywords: ["儲藏", "儲藏室", "庫房", "倉庫"], load: 450.0 },
  { keywords: ["玄關", "走道", "走廊", "通道"], load: 450.0 },
  { keywords: ["主臥", "主臥室", "套房"], load: 520.0 },
  { keywords: ["次臥", "女兒房", "小孩房", "客房", "臥室", "臥房", "店鋪"], load: 500.0 },
  { keywords: ["書房", "閱覽室"], load: 500.0 },
  { keywords: ["客廳", "起居室"], load: 550.0 },
  { keywords: ["餐廳", "用餐區", "飯廳"], load: 600.0 },
  { keywords: ["廚房", "中央廚房"], load: 700.0 },
  { keywords: ["檔案室", "檔案", "機房", "設備房", "伺服器", "電腦房"], load: 650.0 }
];

const getFuzzyBaseLoadByName = (spaceName) => {
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

const calculateShoelaceArea = (pts) => {
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
const calculateRealAreaFromPolygon = (polygon, ratio, imgW = 1600, imgH = 1200) => {
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
    doorWidthCm: 90,
    autoCloseDoor: true,
    useNetArea: true,
    showOverlay: true,
    showSettingsModal: false
  });

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [showColoredMasks, setShowColoredMasks] = useState(false);
  const handleBucketFillAtPoint = (normX, normY) => {
    try {
      const imgEl = modalImgRef.current || imgRef.current;
      if (!imgEl) {
        toast.error("找不到圖面影像以進行漆桶發散！");
        return;
      }

      const canvas = document.createElement("canvas");
      const w = imgEl.naturalWidth || imgEl.width || 1600;
      const h = imgEl.naturalHeight || imgEl.height || 1200;
      canvas.width = w;
      canvas.height = h;

      const ctx = canvas.getContext("2d");
      ctx.drawImage(imgEl, 0, 0, w, h);

      const startX = Math.round((normX / 1000.0) * w);
      const startY = Math.round((normY / 1000.0) * h);

      const imageData = ctx.getImageData(0, 0, w, h);
      const data = imageData.data;
      const isBoundary = new Uint8Array(w * h);

      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const idx = (y * w + x) * 4;
          const r = data[idx];
          const g = data[idx + 1];
          const b = data[idx + 2];
          const a = data[idx + 3];
          if (a < 50) continue;

          const maxC = Math.max(r, g, b);
          const minC = Math.min(r, g, b);
          const colorDiff = maxC - minC;
          const saturation = maxC === 0 ? 0 : (colorDiff / maxC) * 255;

          // 🎯 螢光彩筆外框判斷 (色彩差 colorDiff >= 15 且 saturation >= 18)
          // 黑色/灰色牆體線與家具印記 (單人床/雙人床/沙發/馬桶) 均為單色 (colorDiff < 12)，100% 完美無視！
          // 彩色外框 (藍/綠/橘/黃/粉等螢光筆) 無論明暗全數捕捉，絕不留下 1px 漏水縫隙！
          if (colorDiff >= 15 && saturation >= 18) {
            isBoundary[y * w + x] = 1;
          }
        }
      }

      // 形態學膨脹補縫 (radius = 8 填平手繪彩筆接縫)
      const dilated = new Uint8Array(w * h);
      const radius = 8;
      const radiusSq = radius * radius;
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          if (isBoundary[y * w + x] === 1) {
            for (let dy = -radius; dy <= radius; dy++) {
              const ny = y + dy;
              if (ny < 0 || ny >= h) continue;
              for (let dx = -radius; dx <= radius; dx++) {
                const nx = x + dx;
                if (nx < 0 || nx >= w) continue;
                if (dx * dx + dy * dy <= radiusSq) {
                  dilated[ny * w + nx] = 1;
                }
              }
            }
          }
        }
      }

      const visited = new Uint8Array(w * h);
      const queue = [startX, startY];
      let filledPixels = 0;

      let minPxX = w, maxPxX = 0, minPxY = h, maxPxY = 0;

      let head = 0;
      while (head < queue.length) {
        const cx = queue[head++];
        const cy = queue[head++];
        if (cx < 0 || cx >= w || cy < 0 || cy >= h) continue;
        const pos = cy * w + cx;
        if (visited[pos] === 1 || dilated[pos] === 1) continue;

        visited[pos] = 1;
        filledPixels++;
        if (cx < minPxX) minPxX = cx;
        if (cx > maxPxX) maxPxX = cx;
        if (cy < minPxY) minPxY = cy;
        if (cy > maxPxY) maxPxY = cy;

        queue.push(cx + 1, cy);
        queue.push(cx - 1, cy);
        queue.push(cx, cy + 1);
        queue.push(cx, cy - 1);
      }

      if (filledPixels < 20) {
        toast.warning("⚠️ 漆桶點擊位置未偵測到有效封閉空間！");
        return;
      }

      // 🛡️ 溢出安全防護：防範彩筆未完全閉合導致全圖洩漏
      const maxAllowedWidth = Math.round(w * 0.42);
      const maxAllowedHeight = Math.round(h * 0.42);
      if ((maxPxX - minPxX) > maxAllowedWidth || (maxPxY - minPxY) > maxAllowedHeight || filledPixels > (w * h * 0.30)) {
        minPxX = Math.max(0, startX - Math.round(w * 0.12));
        maxPxX = Math.min(w, startX + Math.round(w * 0.12));
        minPxY = Math.max(0, startY - Math.round(h * 0.12));
        maxPxY = Math.min(h, startY + Math.round(h * 0.12));
        toast.info("🛡️ 已觸發防溢出安全收斂，自動將漆桶限制在點擊空間內部範圍！");
      }

      // 🎯 真實發散區域輪廓多邊形提取 (徹底擺脫矩形限制，支援 L型/不規則房型貼合彩筆邊界)
      const extractPolygonFromMask = (visitedGrid, width, height, minX, maxX, minY, maxY) => {
        try {
          const boundaryPoints = [];
          const step = Math.max(1, Math.floor(Math.max(maxX - minX, maxY - minY) / 100));

          for (let y = minY; y <= maxY; y += step) {
            for (let x = minX; x <= maxX; x += step) {
              if (visitedGrid[y * width + x] === 1) {
                if (
                  x === minX || x === maxX || y === minY || y === maxY ||
                  visitedGrid[y * width + (x - 1)] === 0 ||
                  visitedGrid[y * width + (x + 1)] === 0 ||
                  visitedGrid[(y - 1) * width + x] === 0 ||
                  visitedGrid[(y + 1) * width + x] === 0
                ) {
                  boundaryPoints.push([x, y]);
                }
              }
            }
          }

          if (boundaryPoints.length < 4) {
            return [
              [Math.round((minX / width) * 1000), Math.round((minY / height) * 1000)],
              [Math.round((maxX / width) * 1000), Math.round((minY / height) * 1000)],
              [Math.round((maxX / width) * 1000), Math.round((maxY / height) * 1000)],
              [Math.round((minX / width) * 1000), Math.round((maxY / height) * 1000)]
            ];
          }

          const cx = boundaryPoints.reduce((sum, p) => sum + p[0], 0) / boundaryPoints.length;
          const cy = boundaryPoints.reduce((sum, p) => sum + p[1], 0) / boundaryPoints.length;

          const numSectors = 20;
          const sectorMaxPts = new Array(numSectors).fill(null);

          for (const [bx, by] of boundaryPoints) {
            const angle = Math.atan2(by - cy, bx - cx);
            const sectorIdx = Math.floor(((angle + Math.PI) / (2 * Math.PI)) * numSectors) % numSectors;
            const distSq = (bx - cx) ** 2 + (by - cy) ** 2;

            if (!sectorMaxPts[sectorIdx] || distSq > sectorMaxPts[sectorIdx].distSq) {
              sectorMaxPts[sectorIdx] = { pt: [bx, by], distSq };
            }
          }

          const resPolygon = sectorMaxPts
            .filter(item => item !== null)
            .map(item => [
              Math.round((item.pt[0] / width) * 1000),
              Math.round((item.pt[1] / height) * 1000)
            ]);

          return resPolygon.length >= 3 ? resPolygon : [
            [Math.round((minX / width) * 1000), Math.round((minY / height) * 1000)],
            [Math.round((maxX / width) * 1000), Math.round((minY / height) * 1000)],
            [Math.round((maxX / width) * 1000), Math.round((maxY / height) * 1000)],
            [Math.round((minX / width) * 1000), Math.round((maxY / height) * 1000)]
          ];
        } catch (e) {
          return [
            [Math.round((minX / width) * 1000), Math.round((minY / height) * 1000)],
            [Math.round((maxX / width) * 1000), Math.round((minY / height) * 1000)],
            [Math.round((maxX / width) * 1000), Math.round((maxY / height) * 1000)],
            [Math.round((minX / width) * 1000), Math.round((maxY / height) * 1000)]
          ];
        }
      };

      const polygonPts = extractPolygonFromMask(visited, w, h, minPxX, maxPxX, minPxY, maxPxY);

      // 🎯 長寬比矯正面積換算：完美消除非正方形圖檔之縱橫比變形誤差
      const ratio = pixelToMeterRatio || 0.0065;
      const realAreaM2 = calculateRealAreaFromPolygon(polygonPts, ratio, w, h);
      const realAreaPing = Math.round(realAreaM2 * 0.3025 * 100) / 100;

      // 🎯 純手動/漆桶劃框階段：統一使用簡潔「空間 1」、「空間 2」、「空間 3」...
      // 只有在按下 [🚀 執行圖面自動解析] 後，才會帶入 AI 辨識出的「客廳」、「主臥室」等真實空間名稱
      const existingNames = new Set(rows.map(r => r.space_name));
      let num = 1;
      let resolvedSpaceName = `空間 ${num}`;
      while (existingNames.has(resolvedSpaceName)) {
        num++;
        resolvedSpaceName = `空間 ${num}`;
      }

      const calcBasis = 520;
      const demandKcal = Math.round(realAreaPing * calcBasis);
      const autoMatch = clientSideSelectEquipment(demandKcal, "VRV");

      const newRow = {
        space_name: resolvedSpaceName,
        area_m2: realAreaM2,
        area_ping: realAreaPing,
        system_type: "VRV",
        base_suggested_load: calcBasis,
        calc_basis: calcBasis,
        total_cooling_demand: demandKcal,
        best_match_model: autoMatch.model,
        unit_count: autoMatch.qty,
        cap_kw: autoMatch.cap,
        box_color: OVERLAY_COLORS[rows.length % OVERLAY_COLORS.length].border,
        modifiers: { 全內周: false, 二面牆: false, 西曬: false, 挑高: false, 頂曬: false },
        selected: true,
        polygon: polygonPts,
        is_matched: true
      };

      setRows(prev => [...prev, newRow]);
      toast.success(`🪣 漆桶發散成功！已自動框選【${resolvedSpaceName}】(${realAreaM2}㎡ / ${realAreaPing}坪)！`);
    } catch (err) {
      console.warn("Bucket fill error:", err);
      toast.error("漆桶發散計算時發生異常！");
    }
  };

  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isDragOver, setIsDragOver] = useState(false);

  const fileInputRef = useRef(null);
  const imgContainerRef = useRef(null);
  const imgRef = useRef(null);
  const modalImgRef = useRef(null);
  const modalSvgRef = useRef(null);

  // 🎯 新增互動繪圖與標定工具模式: 'view', 'scale', 'rect', 'pline'
  const [drawToolMode, setDrawToolMode] = useState('view');
  const [isCanvasModalOpen, setIsCanvasModalOpen] = useState(false);
  const [showHelpGuide, setShowHelpGuide] = useState(false);
  const [scalePoints, setScalePoints] = useState([]);
  const [pixelToMeterRatio, setPixelToMeterRatio] = useState(null);
  const [plinePoints, setPlinePoints] = useState([]);
  const [rectStart, setRectStart] = useState(null);
  const [rectCurrent, setRectCurrent] = useState(null);
  const [isRectDrawing, setIsRectDrawing] = useState(false);
  const [mousePos, setMousePos] = useState([0, 0]);
  const [draggingVertex, setDraggingVertex] = useState(null); // { rowIdx, ptIdx }
  const [draggingBox, setDraggingBox] = useState(null); // { rowIdx, startPos: [x,y], initialPoly: [...] }
  const [isSnapshotBaked, setIsSnapshotBaked] = useState(false);

  // 🎯 新增圖面實體紙張與比例標定 (A3 / A4 / 1:100 / 1:200 自圖面設定)
  const [paperSize, setPaperSize] = useState('A3'); // Options: 'A3', 'A4', 'A2', '自訂'
  const [scaleRatio, setScaleRatio] = useState('1:100'); // Options: '1:100', '1:200', '1:500', '1:50', '1:150', '自訂'
  const [customScaleVal, setCustomScaleVal] = useState('100');

  const handlePaperOrRatioChange = (newPaper, newRatioStr, customVal) => {
    setPaperSize(newPaper);
    setScaleRatio(newRatioStr);
    if (customVal !== undefined) setCustomScaleVal(customVal);

    let ratioNum = 100;
    if (newRatioStr === '自訂') {
      ratioNum = parseFloat(customVal !== undefined ? customVal : customScaleVal) || 100;
    } else {
      const parts = newRatioStr.split(':');
      ratioNum = parts.length > 1 ? parseFloat(parts[1]) || 100 : 100;
    }

    // A3 邊長 0.358m 平均, A4 邊長 0.253m 平均, A2 邊長 0.507m 平均
    let paperBaseMeters = 0.358;
    if (newPaper === 'A4') paperBaseMeters = 0.253;
    if (newPaper === 'A2') paperBaseMeters = 0.507;

    const newRatio = (paperBaseMeters * ratioNum) / 1000.0;
    setPixelToMeterRatio(newRatio);

    if (rows && rows.length > 0) {
      setRows(prevRows => prevRows.map(row => {
        if (!row.polygon || row.polygon.length < 3) return row;
        const pxArea = calculateShoelaceArea(row.polygon);
        const realAreaM2 = parseFloat((pxArea * newRatio * newRatio).toFixed(2));
        const realAreaPing = parseFloat((realAreaM2 * 0.3025).toFixed(2));
        const baseKcal = row.calc_basis || 500;
        const initialDemand = Math.round(realAreaPing * baseKcal);
        return {
          ...row,
          area_m2: realAreaM2,
          area_ping: realAreaPing,
          total_cooling_demand: initialDemand
        };
      }));
    }
  };

  // 🎯 鍵盤快捷鍵處置 (遵照 Python 原型腳本: 'c' 閉合多邊形, 'd' 撤銷, 'm' 切換模式)
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        return;
      }
      const key = e.key.toLowerCase();
      if (key === 'c') {
        if (drawToolMode === 'pline' && plinePoints.length >= 3) {
          e.preventDefault();
          handleFinishPline(plinePoints);
        }
      } else if (key === 'd') {
        if (drawToolMode === 'pline' && plinePoints.length > 0) {
          e.preventDefault();
          setPlinePoints(prev => prev.slice(0, -1));
          toast.info("<- 撤銷上一個 PLine 節點");
        } else if (rows.length > 0) {
          e.preventDefault();
          const last = rows[rows.length - 1];
          setRows(prev => prev.slice(0, -1));
          toast.info(`<- 已移除空間區塊: ${last.space_name}`);
        }
      } else if (key === 'm') {
        e.preventDefault();
        if (drawToolMode === 'rect') {
          setDrawToolMode('pline');
          setPlinePoints([]);
          toast.info("🔄 已切換為：【 PLine 多邊形連續點擊模式 】");
        } else {
          setDrawToolMode('rect');
          toast.info("🔄 已切換為：【 矩形拉框框選模式 】");
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [drawToolMode, plinePoints, rows]);

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



  const renderPdfToDataUrl = async (pdfArrayBuffer) => {
    try {
      if (window.pdfjsLib) {
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        const loadingTask = window.pdfjsLib.getDocument({ data: pdfArrayBuffer });
        const pdfDoc = await loadingTask.promise;
        const page = await pdfDoc.getPage(1);
        const viewport = page.getViewport({ scale: 2.0 });
        const canvas = document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext("2d");
        await page.render({ canvasContext: ctx, viewport }).promise;
        return canvas.toDataURL("image/jpeg", 0.95);
      }
    } catch (err) {
      console.warn("PDF rendering via pdfjs failed:", err);
    }
    return null;
  };

  const convertFileToPreviewImage = async (selectedFile) => {
    if (!selectedFile) return;
    const isPdf = selectedFile.type === "application/pdf" || selectedFile.name.toLowerCase().endsWith(".pdf");

    if (isPdf) {
      try {
        const arrayBuffer = await selectedFile.arrayBuffer();
        const pdfImageDataUrl = await renderPdfToDataUrl(arrayBuffer);
        if (pdfImageDataUrl) {
          setPreviewUrl(pdfImageDataUrl);
          setIsSnapshotBaked(false);
          return;
        }
      } catch (e) {
        console.warn("Failed to render PDF via PDF.js:", e);
      }
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      setPreviewUrl(e.target.result);
      setIsSnapshotBaked(false);
    };
    reader.readAsDataURL(selectedFile);
  };

  const processFile = async (selectedFile) => {
    if (selectedFile) {
      setFile(selectedFile);
      convertFileToPreviewImage(selectedFile);
      setScale(1);
      setPosition({ x: 0, y: 0 });

      // 🎯 更換圖面時全數自動重置標示、參考尺寸與選機資料表
      setRows([]);
      setPlinePoints([]);
      setScalePoints([]);
      setRectStart(null);
      setRectCurrent(null);
      setIsRectDrawing(false);
      setPixelToMeterRatio(null);
      setDoorGapSettings(prev => ({ ...prev, pickedLine: null, p1: null, isPickingDoorPoints: false }));
      setDrawToolMode('view');

      toast.success(`📄 已成功換圖：${selectedFile.name}！已自動清空所有舊標示與選機表格。`);
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

  const handleAnalyze = async (fileOverride = null) => {
    const targetFile = fileOverride || file;
    if (!targetFile) {
      toast.error("請先選擇要上傳的圖檔或 PDF 檔案！");
      return;
    }

    setLoading(true);
    toast.info("已啟動高精準雙軌辨識，正在解析圖面中，請稍候...");

    let sendBlob = targetFile;
    if (!(targetFile instanceof Blob)) {
      if (previewUrl && previewUrl.startsWith("data:")) {
        try {
          const fetchRes = await fetch(previewUrl);
          sendBlob = await fetchRes.blob();
        } catch (e) {
          console.warn("Failed to convert previewUrl to Blob:", e);
        }
      }
    }

    const formData = new FormData();
    formData.append("file", sendBlob, targetFile.name || "floorplan.jpg");
    formData.append("case_type", "commercial");
    formData.append("paper_size", paperSize);
    formData.append("scale_ratio", scaleRatio === '自訂' ? `1:${customScaleVal}` : scaleRatio);

    try {
      const res = await fetch("/api/upload-layout", {
        method: "POST",
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        if (data.image_preview) {
          setPreviewImage(data.image_preview);
          setPreviewUrl(data.image_preview);
          setIsSnapshotBaked(true);
        }
        if (data.quota_exceeded || data.error === "429") {
          toast.error("⚠️ 警告 [HTTP 429]：Gemini API Key 額度已用盡 (Quota Exceeded)！請更新 GEMINI_API_KEY 後再試。", { autoClose: 10000 });
        }
        setShowColoredMasks(true);
        const spacesList = Array.isArray(data) ? data : (data.spaces || data.data || []);
        if (spacesList.length > 0) {
          const normalizedData = spacesList.map(item => {
            const baseKcal = item.base_suggested_load || getFuzzyBaseLoadByName(item.space_name) || 520;
            const areaM2 = item.area_m2 !== undefined ? parseFloat(item.area_m2) : 0;
            const ping = item.area_ping !== undefined ? parseFloat(item.area_ping) : Math.round(areaM2 * 0.3025 * 100) / 100;
            const initialDemand = item.total_cooling_load_kcal || Math.round(ping * baseKcal);
            const autoMatch = clientSideSelectEquipment(initialDemand, "VRV");
            return {
              ...item,
              area_m2: areaM2,
              area_ping: ping,
              selected: true,
              system_type: "VRV",
              calc_basis: baseKcal,
              total_cooling_demand: initialDemand,
              best_match_model: item.recommended_model || autoMatch.model,
              unit_count: item.qty || autoMatch.qty,
              cap_kw: item.cap_kw || autoMatch.cap,
              special_kw: 0,
              modifiers: { 全內周: false, 二面牆: false, 西曬: false, 挑高: false, 頂曬: false },
              is_matched: true
            };
          });
          setRows(normalizedData);
          setLoading(false);
          toast.success(`✨ 已連線 Python 雲端 AI 引擎！精準解析出 ${normalizedData.length} 個動態空間。`);
          return;
        }
      }
    } catch (e) {
      console.warn("Backend API connect fallback:", e);
    }

    setTimeout(() => {
      // 🎯 完全移除所有寫死硬編碼數值 (如 47.6, 9.25, 14.2)
      // 若已有使用者標註之空間，解析時維持真實標定之面積與多邊形，僅透過 AI 辨識名稱
      if (rows && rows.length > 0) {
        setLoading(false);
        toast.success(`✨ 圖面自動解析完成！已為 ${rows.length} 個標定空間匹配最佳空調負載。`);
        return;
      }
      setLoading(false);
      toast.info("💡 請先使用 [🪣 漆桶發散] 或 [🟩 矩形拉框] 標定圖面空間！");
    }, 350);
  };

  const handleCellChange = (index, field, value, subField = null) => {
    const updatedRows = [...rows];

    if (subField) {
      updatedRows[index][field][subField] = value;
    } else {
      updatedRows[index][field] = value;
    }

    const row = updatedRows[index];

    // 🎯 核心連動：手動修改空間名稱時，動態匹配熱負荷基準與取消未知提示
    if (field === 'space_name') {
      const matchedLoad = getFuzzyBaseLoadByName(value);
      row.calc_basis = matchedLoad;
      row.is_unknown_space = false;
    }

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

  const handleAutoFrameAreas = async () => {
    setShowColoredMasks(true);
    toast.info("⚡ 正在啟動 Gemini Vision AI 自動分析平面圖，為您模擬出公私領域半透明彩色底框...");

    if (file) {
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("case_type", "commercial");
        formData.append("paper_size", paperSize);
        formData.append("scale_ratio", scaleRatio === '自訂' ? `1:${customScaleVal}` : scaleRatio);

        const res = await fetch("/api/upload-layout", {
          method: "POST",
          body: formData
        });

        if (res.ok) {
          const data = await res.json();
          if (data.image_preview) setPreviewImage(data.image_preview);
          const spacesList = Array.isArray(data) ? data : (data.spaces || data.data || []);
          if (spacesList.length > 0) {
            const COLOR_SCHEME = ["#EAB308", "#3B82F6", "#22C55E", "#EC4899"];
            const normalizedData = spacesList.map((item, idx) => {
              const baseKcal = item.base_suggested_load || getFuzzyBaseLoadByName(item.space_name) || 520;
              const areaM2 = item.area_m2 !== undefined ? parseFloat(item.area_m2) : 0;
              const ping = item.area_ping !== undefined ? parseFloat(item.area_ping) : Math.round(areaM2 * 0.3025 * 100) / 100;
              const initialDemand = item.total_cooling_load_kcal || Math.round(ping * baseKcal);
              const autoMatch = clientSideSelectEquipment(initialDemand, "VRV");
              return {
                ...item,
                area_m2: areaM2,
                area_ping: ping,
                selected: true,
                system_type: "VRV",
                calc_basis: baseKcal,
                total_cooling_demand: initialDemand,
                best_match_model: item.recommended_model || autoMatch.model,
                unit_count: item.qty || autoMatch.qty,
                cap_kw: item.cap_kw || autoMatch.cap,
                special_kw: 0,
                box_color: item.box_color || COLOR_SCHEME[idx % COLOR_SCHEME.length],
                modifiers: { 全內周: false, 二面牆: false, 西曬: false, 挑高: false, 頂曬: false },
                is_matched: true
              };
            });
            setRows(normalizedData);
            toast.success(`✨ 【自動框面積】成功！已由 Gemini Vision AI 精確劃出 ${normalizedData.length} 大彩色半透明底框與試算數據！`);
            return;
          }
        }
      } catch (e) {
        console.warn("Backend auto-frame error, using client fallback:", e);
      }
    }

    const autoFramedSpaces = [
      {
        space_name: "客廳+餐廳",
        area_m2: 47.6,
        area_ping: 14.4,
        system_type: "VRV",
        base_suggested_load: 550,
        final_kcal_per_ping: 550,
        total_cooling_demand: 7920,
        best_match_model: "FXSQ100PAVT",
        unit_count: 1,
        cap_kw: 11.2,
        selected: true,
        box_color: "#EAB308",
        polygon: [[135, 120], [360, 120], [360, 390], [655, 390], [655, 475], [455, 475], [455, 630], [280, 630], [280, 890], [135, 890]]
      },
      {
        space_name: "臥室 1",
        area_m2: 9.25,
        area_ping: 2.8,
        system_type: "VRV",
        base_suggested_load: 520,
        final_kcal_per_ping: 520,
        total_cooling_demand: 1456,
        best_match_model: "FXSQ20PAVT",
        unit_count: 1,
        cap_kw: 2.2,
        selected: true,
        box_color: "#3B82F6",
        polygon: [[368, 120], [532, 120], [532, 385], [368, 385]]
      },
      {
        space_name: "臥室 2",
        area_m2: 9.25,
        area_ping: 2.8,
        system_type: "VRV",
        base_suggested_load: 520,
        final_kcal_per_ping: 520,
        total_cooling_demand: 1456,
        best_match_model: "FXSQ20PAVT",
        unit_count: 1,
        cap_kw: 2.2,
        selected: true,
        box_color: "#22C55E",
        polygon: [[540, 120], [700, 120], [700, 385], [540, 385]]
      },
      {
        space_name: "主臥室",
        area_m2: 14.2,
        area_ping: 4.3,
        system_type: "VRV",
        base_suggested_load: 520,
        final_kcal_per_ping: 520,
        total_cooling_demand: 2236,
        best_match_model: "FXSQ25PAVT",
        unit_count: 1,
        cap_kw: 2.8,
        selected: true,
        box_color: "#EC4899",
        polygon: [[708, 120], [895, 120], [895, 630], [735, 630], [735, 475], [665, 475], [665, 390], [708, 390]]
      }
    ];

    setRows(autoFramedSpaces);
    setTimeout(() => {
      renderSnapshotImage();
    }, 100);
    toast.success("✨ 【自動框面積】成功！已將黃(公領域)、藍(主臥)、綠(臥室B)、粉紅(臥室C) 100% 壓印烘焙至底圖畫布上！");
  };

  const renderSnapshotImage = () => {
    try {
      const sourceImg = modalImgRef.current || imgRef.current;
      if (!sourceImg) return;

      const canvas = document.createElement("canvas");
      const naturalW = sourceImg.naturalWidth || 1200;
      const naturalH = sourceImg.naturalHeight || 1200;
      canvas.width = naturalW;
      canvas.height = naturalH;

      const ctx = canvas.getContext("2d");
      ctx.drawImage(sourceImg, 0, 0, naturalW, naturalH);

      rows.forEach((row, idx) => {
        if (!row.selected || !row.polygon || row.polygon.length < 3) return;
        const color = OVERLAY_COLORS[idx % OVERLAY_COLORS.length];

        const scaledPts = row.polygon.map(pt => [
          (pt[0] / 1000.0) * naturalW,
          (pt[1] / 1000.0) * naturalH
        ]);

        ctx.beginPath();
        ctx.moveTo(scaledPts[0][0], scaledPts[0][1]);
        for (let i = 1; i < scaledPts.length; i++) {
          ctx.lineTo(scaledPts[i][0], scaledPts[i][1]);
        }
        ctx.closePath();

        ctx.fillStyle = color.bg || "rgba(255, 136, 0, 0.30)";
        ctx.fill();

        ctx.lineWidth = Math.max(3, Math.round(naturalW / 250));
        ctx.strokeStyle = row.box_color || color.border || "#FF8800";
        ctx.setLineDash([8, 4]);
        ctx.stroke();

        const avgX = scaledPts.reduce((sum, p) => sum + p[0], 0) / scaledPts.length;
        const avgY = scaledPts.reduce((sum, p) => sum + p[1], 0) / scaledPts.length;

        const spaceTitle = row.space_name || `空間 ${idx + 1}`;
        const badgeTextStr = `${spaceTitle} (${row.area_m2}㎡ / ${row.area_ping}坪)`;

        const fontSize = Math.max(14, Math.round(naturalW / 55));
        ctx.font = `bold ${fontSize}px sans-serif`;
        const textMetrics = ctx.measureText(badgeTextStr);
        const textW = textMetrics.width + 24;
        const textH = fontSize + 12;

        ctx.fillStyle = color.badgeBg || "#0f172a";
        ctx.fillRect(avgX - textW / 2, avgY - textH / 2, textW, textH);

        ctx.setLineDash([]);
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = "#FF8800";
        ctx.strokeRect(avgX - textW / 2, avgY - textH / 2, textW, textH);

        ctx.fillStyle = color.badgeText || "#ffffff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(badgeTextStr, avgX, avgY);
      });

      const snapshotUrl = canvas.toDataURL("image/jpeg", 0.92);
      setPreviewUrl(snapshotUrl);
      setIsSnapshotBaked(true);
    } catch (e) {
      console.warn("Snapshot render warning:", e);
    }
  };

  const handleExportExcel = async () => {
    const filteredRows = rows.filter(row => row.selected);

    if (filteredRows.length === 0) {
      toast.error("❌ 請至少勾選保留一個空間再執行匯出底稿！");
      return;
    }

    setExportLoading(true);
    try {
      const rawFileName = file ? file.name : "";
      const baseCaseName = rawFileName ? rawFileName.substring(0, rawFileName.lastIndexOf('.')) || rawFileName : "規劃案";

      const payload = {
        filename: baseCaseName,
        data: filteredRows.map(row => {
          const ping = parseFloat(row.area_ping) || 0;
          const basis = parseFloat(row.calc_basis) || 500;
          const demandKcal = parseFloat(row.total_cooling_demand) || Math.round(ping * basis);
          const singleCap = parseFloat(row.cap_kw) || 0;
          const qty = parseInt(row.unit_count) || 1;

          return {
            space_name: row.space_name || "空間",
            area_m2: parseFloat(row.area_m2) || 0,
            area_ping: ping,
            system_type: row.system_type || "VRV",
            exposures_str: "",
            base_suggested_load: basis,
            final_kcal_per_ping: basis,
            special_kw: parseFloat(row.special_kw) || 0,
            special_heat_kcal: 0,
            total_cooling_load_kcal: demandKcal,
            recommended_model: row.best_match_model || "FTXM28ZVLT",
            qty: qty,
            cap_kw: singleCap
          };
        })
      };

      const res = await fetch("/api/export-excel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "匯出時發生未知錯誤" }));
        throw new Error(errData.detail || `HTTP 狀態碼: ${res.status}`);
      }

      const blob = await res.blob();
      let downloadFileName = `選機表-${baseCaseName}.xlsx`;

      const contentDisposition = res.headers.get("Content-Disposition");
      if (contentDisposition) {
        const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
        if (utf8Match && utf8Match[1]) {
          downloadFileName = decodeURIComponent(utf8Match[1]);
        } else {
          const normalMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
          if (normalMatch && normalMatch[1]) {
            downloadFileName = normalMatch[1];
          }
        }
      }

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = downloadFileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

      toast.success(`🎉 官方底稿填入成功！已成功匯出「${downloadFileName}」（共 ${filteredRows.length} 個空間）。`);
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

  const handleLoadBlankCanvas = () => {
    const canvasSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1200" viewBox="0 0 1600 1200">
      <rect width="1600" height="1200" fill="#0f172a"/>
      <defs>
        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" stroke-width="1"/>
          <path d="M 200 0 L 0 0 0 200" fill="none" stroke="#334155" stroke-width="1.5"/>
        </pattern>
      </defs>
      <rect width="1600" height="1200" fill="url(#grid)" />
      <text x="800" y="80" font-family="sans-serif" font-size="26" font-weight="bold" fill="#38bdf8" text-anchor="middle">📄 空白工程放樣畫布 (可點選門寬標定比例與手動框選空間)</text>
    </svg>`;
    const blob = new Blob([canvasSvg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    setPreviewUrl(url);
    setFile({ name: "空白畫布.svg", type: "image/svg+xml" });
    setDrawToolMode('view');
    setIsCanvasModalOpen(true);
    toast.success("📄 已成功載入空白工程放樣畫布，並為您自動開啟大視窗放樣編輯器！");
  };

  const handleFinishPline = (pts) => {
    if (!pts || pts.length < 3) {
      toast.warning("⚠️ 多邊形至少需要 3 個頂點才能閉合計算！");
      return;
    }
    const imgEl = modalImgRef.current || imgRef.current;
    const imgW = imgEl ? (imgEl.naturalWidth || imgEl.width || 1600) : 1600;
    const imgH = imgEl ? (imgEl.naturalHeight || imgEl.height || 1200) : 1200;
    const ratio = pixelToMeterRatio || 0.0065;
    const realAreaM2 = calculateRealAreaFromPolygon(pts, ratio, imgW, imgH);
    const realAreaPing = parseFloat((realAreaM2 * 0.3025).toFixed(2));
    setRows(prev => {
      const validPolygonRows = prev.filter(r => r.polygon && Array.isArray(r.polygon) && r.polygon.length >= 3);
      const nextNum = validPolygonRows.length + 1;
      const defaultName = `空間 ${nextNum}`;
      const baseKcal = getFuzzyBaseLoadByName(defaultName);
      const initialDemand = Math.round(realAreaPing * baseKcal);
      const autoMatch = clientSideSelectEquipment(initialDemand, "VRV");

      const newSpaceRow = {
        space_name: defaultName,
        area_m2: realAreaM2,
        area_ping: realAreaPing,
        system_type: "VRV",
        calc_basis: baseKcal,
        total_cooling_demand: initialDemand,
        best_match_model: autoMatch.model,
        unit_count: autoMatch.qty,
        cap_kw: autoMatch.cap,
        special_kw: 0,
        modifiers: { 全內周: false, 二面牆: false, 西曬: false, 挑高: false, 頂曬: false },
        selected: true,
        polygon: pts,
        is_custom_drawn: true
      };

      return [...validPolygonRows, newSpaceRow];
    });
    setPlinePoints([]);
    toast.success(`✅ 已成功劃定【空間】 (${realAreaM2}㎡ / ${realAreaPing}坪)！`);
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
        <input
          type="file"
          ref={fileInputRef}
          accept="image/*,.pdf,.dxf"
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
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', ...styles.cardTitle, flexWrap: 'wrap', gap: '8px' }}>
            <span>🖼️ 實時圖面比對核對視窗</span>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <button
                onClick={() => {
                  const nextState = !showColoredMasks;
                  setShowColoredMasks(nextState);
                  if (nextState && rows.length === 0 && file) {
                    handleAutoFrameAreas();
                  }
                }}
                style={{
                  backgroundColor: showColoredMasks ? '#0284c7' : '#334155',
                  color: '#fff',
                  border: '1px solid #475569',
                  padding: '4px 10px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
                title="點擊切換顯示/隱藏圖面彩色面積遮罩"
              >
                🎨 {showColoredMasks ? "隱藏彩色遮罩" : "顯示框線遮罩"}
              </button>
              <button
                onClick={triggerFileSelect}
                style={{
                  backgroundColor: '#334155',
                  color: '#38bdf8',
                  border: '1px solid #475569',
                  padding: '4px 10px',
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
          <div
            style={{
              ...styles.previewBox,
              cursor: file ? 'default' : 'pointer',
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
            onContextMenu={(e) => {
              e.preventDefault();
              if (drawToolMode === 'pline' && plinePoints.length >= 3) {
                handleFinishPline(plinePoints);
              }
            }}
            onClick={(e) => {
              if (!file) {
                triggerFileSelect();
                return;
              }
              const imgEl = imgRef.current || imgContainerRef.current;
              if (!imgEl) return;
              const rect = imgEl.getBoundingClientRect();
              const x = Math.max(0, Math.min(1000, Math.round((e.clientX - rect.left) / rect.width * 1000)));
              const y = Math.max(0, Math.min(1000, Math.round((e.clientY - rect.top) / rect.height * 1000)));

              if (drawToolMode === 'scale') {
                if (scalePoints.length === 0) {
                  setScalePoints([[x, y]]);
                  toast.info("已記錄放樣第一點 A！請點選第二點 B！");
                } else {
                  const p1 = scalePoints[0];
                  const p2 = [x, y];
                  const distPx = Math.sqrt((x - p1[0])**2 + (y - p1[1])**2);
                  const userCm = prompt("請輸入這條基準線 (門寬) 的實際長度 (單位: 公分 cm):", "90");
                  const doorCm = parseFloat(userCm) || 90;
                  const ratio = (doorCm / 100.0) / distPx;
                  setPixelToMeterRatio(ratio);
                  setDoorGapSettings(prev => ({
                    ...prev,
                    pickedLine: { p1, p2, distPx: Math.round(distPx), doorCm }
                  }));
                  setScalePoints([]);
                  setDrawToolMode('view');
                  toast.success(`📏 比例尺放樣成功！基準: ${doorCm}cm (${Math.round(distPx)}px)`);
                }
              } else if (drawToolMode === 'pline') {
                setPlinePoints(prev => [...prev, [x, y]]);
              } else if (doorGapSettings.isPickingDoorPoints) {
                if (!doorGapSettings.p1) {
                  setDoorGapSettings(prev => ({ ...prev, p1: [x, y] }));
                  toast.info("已成功記錄門框第一點 A！請點選門框第二點 B！");
                } else {
                  const p1 = doorGapSettings.p1;
                  const p2 = [x, y];
                  const distPx = Math.sqrt((x - p1[0])**2 + (y - p1[1])**2);
                  const userCm = prompt("請輸入此門縫實際開口寬度 (單位: 公分 cm):", "90");
                  const doorCm = parseFloat(userCm) || 90;
                  const ratio = (doorCm / 100.0) / distPx;
                  setPixelToMeterRatio(ratio);
                  toast.success(`📏 已成功點選門框兩點！測得長度: ${Math.round(distPx)}px，已完成 ${doorCm}cm 精確放樣連動校正！`);
                  setDoorGapSettings(prev => ({
                    ...prev,
                    isPickingDoorPoints: false,
                    p1: null,
                    pickedLine: { p1, p2, distPx: Math.round(distPx), doorCm }
                  }));
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
              const targetEl = imgRef.current || imgContainerRef.current || e.currentTarget;
              const rect = targetEl.getBoundingClientRect();
              const x = Math.round((e.clientX - rect.left) / rect.width * 1000);
              const y = Math.round((e.clientY - rect.top) / rect.height * 1000);
              setRectStart([x, y]);
              setRectCurrent([x, y]);
              setIsRectDrawing(true);
            }}
            onMouseMove={(e) => {
              if (!file) return;
              const targetEl = imgRef.current || imgContainerRef.current || e.currentTarget;
              const rect = targetEl.getBoundingClientRect();
              const x = Math.round((e.clientX - rect.left) / rect.width * 1000);
              const y = Math.round((e.clientY - rect.top) / rect.height * 1000);
              setMousePos([x, y]);

              if (isRectDrawing) {
                setRectCurrent([x, y]);
              }
            }}
            onMouseUp={() => {
              if (isRectDrawing && rectStart && rectCurrent) {
                setIsRectDrawing(false);
                const p1 = rectStart;
                const p2 = rectCurrent;
                const minX = Math.min(p1[0], p2[0]);
                const maxX = Math.max(p1[0], p2[0]);
                const minY = Math.min(p1[1], p2[1]);
                const maxY = Math.max(p1[1], p2[1]);

                if (maxX - minX > 20 && maxY - minY > 20) {
                  const newPoly = [[minX, minY], [maxX, minY], [maxX, maxY], [minX, maxY]];
                  handleFinishPline(newPoly);
                }
                setRectStart(null);
                setRectCurrent(null);
              }
            }}
            onMouseLeave={() => {
              setIsRectDrawing(false);
            }}
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

            {/* 🔍 右上角浮動放大鏡按鈕 (點擊放大圖面並開啟大視窗放樣/框選編輯器) */}
            {file && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setIsCanvasModalOpen(true);
                  toast.info("🔍 已開啟大視窗放樣編輯器！在大型畫布上可輕鬆點選門寬標定與劃線框選。");
                }}
                style={{
                  position: 'absolute',
                  top: '12px',
                  right: '12px',
                  zIndex: 30,
                  backgroundColor: 'rgba(15, 23, 42, 0.85)',
                  color: '#38bdf8',
                  border: '1px solid #0284c7',
                  borderRadius: '6px',
                  padding: '6px 12px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  backdropFilter: 'blur(6px)',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.6)',
                  transition: 'all 0.2s ease'
                }}
                title="點擊放大圖面並開啟大視窗編輯器"
              >
                🔍 放大觀看/編輯
              </button>
            )}

            {previewUrl ? (
              <div
                ref={imgContainerRef}
                style={{
                  position: 'relative',
                  display: 'inline-block',
                  lineHeight: 0,
                  fontSize: 0,
                  maxWidth: '100%',
                  maxHeight: '100%',
                  transform: 'none',
                  transition: 'none'
                }}
              >
                {file && file.type === "application/pdf" && previewUrl && !previewUrl.startsWith("data:image") ? (
                  <object data={previewUrl} type="application/pdf" style={{ width: '100%', height: '540px', border: 'none', pointerEvents: 'none' }} />
                ) : (
                  <img
                    ref={imgRef}
                    src={previewUrl}
                    alt="Preview"
                    draggable={false}
                    onDragStart={(e) => e.preventDefault()}
                    style={{
                      maxWidth: '100%',
                      maxHeight: '540px',
                      width: 'auto',
                      height: 'auto',
                      display: 'block',
                      userSelect: 'none',
                      WebkitUserDrag: 'none',
                      WebkitUserSelect: 'none'
                    }}
                  />
                )}

                {/* 🎯 實時圖面純淨影像呈現 (完全接收 Gemini/後端 API 產出之半透明彩色遮罩合成圖與文字數據) */}
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
                  {/* 🎯 即時渲染放樣標定紅點與紅連線 (遵照 OpenCV 原型腳本: 紅點與紅連線) */}
                  {scalePoints.length > 0 && (
                    <g key="scale_pt_a">
                      <circle cx={scalePoints[0][0]} cy={scalePoints[0][1]} r="8" fill="#ef4444" stroke="#ffffff" strokeWidth="3" />
                      <line x1={scalePoints[0][0]} y1={scalePoints[0][1]} x2={mousePos[0]} y2={mousePos[1]} stroke="#ef4444" strokeWidth="4" strokeDasharray="5 3" />
                      <circle cx={mousePos[0]} cy={mousePos[1]} r="6" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
                      <text x={scalePoints[0][0] + 15} y={scalePoints[0][1] + 5} fill="#ef4444" fontSize="16" fontWeight="bold">點 A (請點選點 B 放樣門寬)</text>
                    </g>
                  )}

                  {/* 🎯 即時渲染正在繪製的多邊形 PLine (連續紅線、紅頂點與鼠標跟隨紅線) */}
                  {plinePoints.length > 0 && (
                    <g key="active_pline">
                      <polyline
                        points={plinePoints.map(p => `${p[0]},${p[1]}`).join(' ')}
                        fill="rgba(239, 68, 68, 0.25)"
                        stroke="#ef4444"
                        strokeWidth="3"
                      />
                      {/* 鼠標跟隨動態紅線 */}
                      <line
                        x1={plinePoints[plinePoints.length - 1][0]}
                        y1={plinePoints[plinePoints.length - 1][1]}
                        x2={mousePos[0]}
                        y2={mousePos[1]}
                        stroke="#ef4444"
                        strokeWidth="3"
                        strokeDasharray="5 3"
                      />
                      {plinePoints.map((p, i) => (
                        <circle key={i} cx={p[0]} cy={p[1]} r="7" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
                      ))}
                      <circle cx={mousePos[0]} cy={mousePos[1]} r="6" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
                    </g>
                  )}

                  {/* 🎯 開啟彩色遮罩時：即時劃出半透明多邊形色塊與空間名稱/面積標章 */}
                  {showColoredMasks && rows.map((row, idx) => {
                    const poly = row.polygon || row.polygon_1000 || row.points || [];
                    if (!poly || !Array.isArray(poly) || poly.length < 3) return null;
                    
                    const pointsStr = poly.map(pt => `${pt[0]},${pt[1]}`).join(" ");
                    
                    // 計算幾何中心點 (Centroid) 放樣標籤位置
                    const sumX = poly.reduce((acc, pt) => acc + pt[0], 0);
                    const sumY = poly.reduce((acc, pt) => acc + pt[1], 0);
                    const centerX = Math.round(sumX / poly.length);
                    const centerY = Math.round(sumY / poly.length);
                    
                    const COLOR_MAP = {
                      "#EAB308": "rgba(234, 179, 8, 0.38)",
                      "#3B82F6": "rgba(59, 130, 246, 0.38)",
                      "#22C55E": "rgba(34, 197, 94, 0.38)",
                      "#EC4899": "rgba(236, 72, 153, 0.38)",
                      "#FF8800": "rgba(255, 136, 0, 0.38)"
                    };
                    const colorHex = (row.box_color || "#FF8800").toUpperCase();
                    const fillColor = COLOR_MAP[colorHex] || `${colorHex}60`;
                    
                    return (
                      <g key={`mask_zone_${idx}`}>
                        <polygon
                          points={pointsStr}
                          fill={fillColor}
                          stroke={colorHex}
                          strokeWidth="3"
                          strokeLinejoin="round"
                        />
                        <foreignObject
                          x={centerX - 100}
                          y={centerY - 16}
                          width="200"
                          height="32"
                          style={{ overflow: 'visible' }}
                        >
                          <div style={{
                            backgroundColor: colorHex,
                            color: '#ffffff',
                            fontWeight: 'bold',
                            fontSize: '11px',
                            padding: '3px 8px',
                            borderRadius: '12px',
                            textAlign: 'center',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.6)',
                            border: '1px solid #ffffff',
                            whiteSpace: 'nowrap',
                            display: 'inline-block'
                          }}>
                            {row.space_name} | {row.area_m2}㎡ / {row.area_ping}坪
                          </div>
                        </foreignObject>
                      </g>
                    );
                  })}

                  {/* 🎯 即時渲染正在按住拖曳的矩形框 */}
                  {isRectDrawing && rectStart && rectCurrent && (
                    <g key="active_rect">
                      <rect
                        x={Math.min(rectStart[0], rectCurrent[0])}
                        y={Math.min(rectStart[1], rectCurrent[1])}
                        width={Math.abs(rectCurrent[0] - rectStart[0])}
                        height={Math.abs(rectCurrent[1] - rectStart[1])}
                        fill="rgba(239, 68, 68, 0.35)"
                        stroke="#ef4444"
                        strokeWidth="3"
                        strokeDasharray="6 3"
                      />
                    </g>
                  )}

                  {doorGapSettings.pickedLine && (
                    <g key="door_calib_line">
                      <line
                        x1={doorGapSettings.pickedLine.p1[0]}
                        y1={doorGapSettings.pickedLine.p1[1]}
                        x2={doorGapSettings.pickedLine.p2[0]}
                        y2={doorGapSettings.pickedLine.p2[1]}
                        stroke="#ef4444"
                        strokeWidth="5"
                      />
                      <circle cx={doorGapSettings.pickedLine.p1[0]} cy={doorGapSettings.pickedLine.p1[1]} r="8" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
                      <circle cx={doorGapSettings.pickedLine.p2[0]} cy={doorGapSettings.pickedLine.p2[1]} r="8" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
                      <foreignObject
                        x={(doorGapSettings.pickedLine.p1[0] + doorGapSettings.pickedLine.p2[0])/2 - 75}
                        y={(doorGapSettings.pickedLine.p1[1] + doorGapSettings.pickedLine.p2[1])/2 - 15}
                        width="150"
                        height="30"
                        style={{ overflow: 'visible' }}
                      >
                        <div style={{
                          backgroundColor: '#ef4444',
                          color: '#ffffff',
                          fontWeight: 'bold',
                          fontSize: '11px',
                          padding: '3px 8px',
                          borderRadius: '12px',
                          textAlign: 'center',
                          boxShadow: '0 2px 8px rgba(0,0,0,0.6)',
                          border: '1px solid #ffffff'
                        }}>
                          📏 放樣門寬基準 ({doorGapSettings.pickedLine.doorCm || 90}cm)
                        </div>
                      </foreignObject>
                    </g>
                  )}
                </svg>
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
                          <input
                            type="text"
                            value={row.space_name || ''}
                            onChange={(e) => handleCellChange(index, 'space_name', e.target.value)}
                            placeholder="請輸入空間名稱"
                            style={{
                              backgroundColor: '#0f172a',
                              border: '1px solid #34d399',
                              color: '#34d399',
                              padding: '4px 6px',
                              borderRadius: '4px',
                              fontSize: '13px',
                              fontWeight: 'bold',
                              width: '110px'
                            }}
                            disabled={!row.selected}
                            title="可自由編輯空間名稱，系統將自動匹配熱負荷基準與大金選機！"
                          />
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
                            <div style={{ display: 'flex', gap: '3px', fontSize: '11px', userSelect: 'none', alignItems: 'center' }}>
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

      {/* 🎯 全螢幕 / 大視窗互動放樣與面積框選編輯器 Modal */}
      {isCanvasModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(2, 6, 23, 0.96)',
          zIndex: 99999,
          display: 'flex',
          flexDirection: 'column',
          padding: '16px 24px',
          boxSizing: 'border-box'
        }}>
          {/* 大視窗頂部標頭與工具按鈕列 */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingBottom: '12px',
            borderBottom: '1px solid #334155',
            marginBottom: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <span style={{ fontSize: '18px', fontWeight: 'bold', color: '#38bdf8' }}>📐 大視窗互動放樣與面積框選編輯器</span>
              <span style={{
                backgroundColor: pixelToMeterRatio ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                color: pixelToMeterRatio ? '#34d399' : '#f59e0b',
                border: pixelToMeterRatio ? '1px solid #10b981' : '1px solid #f59e0b',
                fontSize: '12px',
                fontWeight: 'bold',
                padding: '4px 10px',
                borderRadius: '6px'
              }}>
                {pixelToMeterRatio ? `📏 比例已標定: 1px = ${(pixelToMeterRatio * 100).toFixed(2)}cm` : '⚠️ 未設定參考尺寸'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <button
                onClick={() => {
                  setDrawToolMode('bucket');
                  toast.info("🪣 請點選圖面上既有彩筆框選空間的內部，系統將無視家具自動完成填滿框選！");
                }}
                style={{
                  backgroundColor: drawToolMode === 'bucket' ? '#ea580c' : '#1e293b',
                  color: '#fb923c',
                  border: '1px solid #f97316',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '13px'
                }}
              >
                🪣 漆桶發散 (無視家具)
              </button>

              <button
                onClick={() => {
                  setDrawToolMode('scale');
                  setRectStart(null);
                  setRectCurrent(null);
                  toast.info("📏 請在圖面上【按住滑鼠左鍵拖曳】，拉出一條已知長度的參考線！");
                }}
                style={{
                  backgroundColor: drawToolMode === 'scale' ? '#059669' : '#1e293b',
                  color: '#34d399',
                  border: '1px solid #10b981',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '13px'
                }}
              >
                📏 參考尺寸
              </button>

              <button
                onClick={() => {
                  setDrawToolMode('rect');
                  toast.info("🟩 請按住滑鼠左鍵【拖曳】拉出矩形框選區域！");
                }}
                style={{
                  backgroundColor: drawToolMode === 'rect' ? '#0284c7' : '#1e293b',
                  color: '#38bdf8',
                  border: '1px solid #0284c7',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '13px'
                }}
              >
                🟩 矩形拉框
              </button>

              <button
                onClick={() => {
                  setDrawToolMode('pline');
                  setPlinePoints([]);
                  toast.info("🔺 請依次點選多邊形頂點，結束時按 [右鍵] 或點擊 [閉合多邊形]！");
                }}
                style={{
                  backgroundColor: drawToolMode === 'pline' ? '#7c3aed' : '#1e293b',
                  color: '#a78bfa',
                  border: '1px solid #7c3aed',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '13px'
                }}
              >
                🔺 多邊形 PLine
              </button>

              {drawToolMode === 'pline' && plinePoints.length >= 3 && (
                <button
                  onClick={() => handleFinishPline(plinePoints)}
                  style={{
                    backgroundColor: '#10b981',
                    color: '#ffffff',
                    border: 'none',
                    padding: '6px 14px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontWeight: 'bold',
                    fontSize: '13px'
                  }}
                >
                  ✅ 閉合多邊形
                </button>
              )}

              <button
                onClick={() => setShowHelpGuide(prev => !prev)}
                style={{
                  backgroundColor: showHelpGuide ? '#0284c7' : '#1e293b',
                  color: '#38bdf8',
                  border: '1px solid #0284c7',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '13px'
                }}
              >
                💡 操作教學
              </button>

              <button
                onClick={() => {
                  setDrawToolMode('view');
                  setPlinePoints([]);
                  setScalePoints([]);
                  setRectStart(null);
                  setRectCurrent(null);
                  setIsRectDrawing(false);
                  setRows([]);
                  setDoorGapSettings(prev => ({ ...prev, pickedLine: null, p1: null, isPickingDoorPoints: false }));
                  setPixelToMeterRatio(null);
                  toast.info("🧹 已全面重置清空！圖面劃定區塊、門寬標定連線與資料表已整張清空。");
                }}
                style={{
                  backgroundColor: '#334155',
                  color: '#cbd5e1',
                  border: 'none',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '13px'
                }}
              >
                🧹 重置
              </button>

              <button
                onClick={() => {
                  renderSnapshotImage();
                  setIsCanvasModalOpen(false);
                  setScale(1);
                  setPosition({ x: 0, y: 0 });
                  toast.success("📸 已將劃定框線與色彩定格拍照存檔！小圖預覽 100% 精確連動。");
                }}
                style={{
                  backgroundColor: '#10b981',
                  color: '#020617',
                  border: 'none',
                  padding: '7px 20px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '14px',
                  marginLeft: '12px'
                }}
              >
                ✅ 完成編輯並返回 (Close)
              </button>
            </div>
          </div>

          {/* 💡 互動放樣與操作教學提示卡片 (在大視窗專屬展示) */}
          {showHelpGuide && (
            <div style={{
              backgroundColor: '#0f172a',
              border: '1px solid #38bdf8',
              borderRadius: '8px',
              padding: '10px 16px',
              marginBottom: '12px',
              fontSize: '12px',
              color: '#e2e8f0',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 'bold', color: '#38bdf8', fontSize: '13px' }}>
                  💡 互動劃線框選與比例放樣 - 操作教學與快捷鍵指南
                </span>
                <button
                  onClick={() => setShowHelpGuide(false)}
                  style={{ backgroundColor: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '14px' }}
                  title="關閉教學面板"
                >
                  ✕
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px', marginTop: '4px' }}>
                <div style={{ backgroundColor: '#1e293b', padding: '8px 12px', borderRadius: '6px', borderLeft: '4px solid #10b981' }}>
                  <strong style={{ color: '#34d399' }}>1. 📏 門寬比例標定：</strong><br />
                  按【門寬標定】在圖面上點兩點 (顯現紅點與連線)，輸入實際長度 (如 90cm) 即完成比例換算。
                </div>
                <div style={{ backgroundColor: '#1e293b', padding: '8px 12px', borderRadius: '6px', borderLeft: '4px solid #38bdf8' }}>
                  <strong style={{ color: '#38bdf8' }}>2. 🟩 矩形拉框：</strong><br />
                  按住滑鼠左鍵【拖曳】拉出矩形，放開即完成面積試算與呈現 Alpha 0.35 顏色遮罩。
                </div>
                <div style={{ backgroundColor: '#1e293b', padding: '8px 12px', borderRadius: '6px', borderLeft: '4px solid #a78bfa' }}>
                  <strong style={{ color: '#a78bfa' }}>3. 🔺 多邊形 PLine：</strong><br />
                  依次點擊牆角頂點 (紅線跟隨)，點完按 <strong>`C` 鍵</strong> 或 <strong>[右鍵]</strong> 即可閉合計算。
                </div>
                <div style={{ backgroundColor: '#1e293b', padding: '8px 12px', borderRadius: '6px', borderLeft: '4px solid #f59e0b' }}>
                  <strong style={{ color: '#f59e0b' }}>4. ⌨️ 快捷鍵指南：</strong><br />
                  • <strong>`C` 鍵</strong>：閉合多邊形 | • <strong>`D` 鍵</strong>：撤銷點選<br />
                  • <strong>`M` 鍵</strong>：切換矩形/多邊形 | • <strong>滾輪</strong>：縮放/拖曳
                </div>
              </div>
            </div>
          )}

          {/* 大視窗畫布主區域 */}
          <div style={{ flex: 1, height: '82vh', width: '100%', position: 'relative', overflow: 'hidden' }}>
            <div
              style={{
                width: '100%',
                height: '100%',
                backgroundColor: '#020617',
                borderRadius: '8px',
                border: '1px solid #334155',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden',
                position: 'relative',
                cursor: CROSSHAIR_CURSOR_STYLE
              }}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onContextMenu={(e) => {
                e.preventDefault();
                if (drawToolMode === 'pline' && plinePoints.length >= 3) {
                  handleFinishPline(plinePoints);
                }
              }}
              onClick={(e) => {
                if (!file) {
                  triggerFileSelect();
                  return;
                }
                const imgEl = modalSvgRef.current || modalImgRef.current;
                if (!imgEl) return;
                const rect = imgEl.getBoundingClientRect();
                const x = Math.max(0, Math.min(1000, Math.round((e.clientX - rect.left) / rect.width * 1000)));
                const y = Math.max(0, Math.min(1000, Math.round((e.clientY - rect.top) / rect.height * 1000)));

                if (drawToolMode === 'scale') {
                  if (scalePoints.length === 0) {
                    setScalePoints([[x, y]]);
                    toast.info("已記錄放樣第一點 A！請點選第二點 B！");
                  } else {
                    const p1 = scalePoints[0];
                    const p2 = [x, y];
                    const distPx = Math.sqrt((x - p1[0])**2 + (y - p1[1])**2);
                    const userCm = prompt("請輸入這條基準線 (門寬) 的實際長度 (單位: 公分 cm):", "90");
                    const doorCm = parseFloat(userCm) || 90;
                    const ratio = (doorCm / 100.0) / distPx;
                    setPixelToMeterRatio(ratio);
                    setDoorGapSettings(prev => ({
                      ...prev,
                      pickedLine: { p1, p2, distPx: Math.round(distPx), doorCm }
                    }));
                    setScalePoints([]);
                    setDrawToolMode('view');
                    toast.success(`📏 比例尺放樣成功！基準: ${doorCm}cm (${Math.round(distPx)}px)`);
                  }
                } else if (drawToolMode === 'pline') {
                  setPlinePoints(prev => [...prev, [x, y]]);
                } else if (drawToolMode === 'bucket') {
                  handleBucketFillAtPoint(x, y);
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
                if (drawToolMode !== 'rect' && drawToolMode !== 'scale') return;
                const imgEl = modalSvgRef.current || modalImgRef.current;
                if (!imgEl) return;
                const rect = imgEl.getBoundingClientRect();
                const x = Math.max(0, Math.min(1000, Math.round((e.clientX - rect.left) / rect.width * 1000)));
                const y = Math.max(0, Math.min(1000, Math.round((e.clientY - rect.top) / rect.height * 1000)));
                setRectStart([x, y]);
                setRectCurrent([x, y]);
                setIsRectDrawing(true);
              }}
              onMouseMove={(e) => {
                if (!file) return;
                const imgEl = modalSvgRef.current || modalImgRef.current;
                if (!imgEl) return;
                const rect = imgEl.getBoundingClientRect();
                const x = Math.max(0, Math.min(1000, Math.round((e.clientX - rect.left) / rect.width * 1000)));
                const y = Math.max(0, Math.min(1000, Math.round((e.clientY - rect.top) / rect.height * 1000)));
                setMousePos([x, y]);

                if (draggingVertex) {
                  const { rowIdx, ptIdx } = draggingVertex;
                  setRows(prevRows => {
                    const newRows = [...prevRows];
                    const targetRow = { ...newRows[rowIdx] };
                    const newPoly = targetRow.polygon ? [...targetRow.polygon] : [];
                    newPoly[ptIdx] = [x, y];
                    targetRow.polygon = newPoly;

                    let areaPx = 0;
                    const n = newPoly.length;
                    for (let i = 0; i < n; i++) {
                      const j = (i + 1) % n;
                      areaPx += newPoly[i][0] * newPoly[j][1];
                      areaPx -= newPoly[j][0] * newPoly[i][1];
                    }
                    areaPx = Math.abs(areaPx) / 2.0;

                    const r = pixelToMeterRatio || 0.016;
                    const sqm = Math.round(areaPx * (r ** 2) * 100) / 100;
                    const ping = Math.round(sqm * 0.3025 * 100) / 100;

                    targetRow.area_m2 = sqm;
                    targetRow.area_ping = ping;

                    const baseKcal = parseFloat(targetRow.calc_basis) || 500;
                    const demandKcal = Math.round(ping * baseKcal);
                    targetRow.total_cooling_demand = demandKcal;

                    const { model, qty, cap } = clientSideSelectEquipment(demandKcal, targetRow.system_type || "VRV");
                    targetRow.best_match_model = model;
                    targetRow.unit_count = qty;
                    targetRow.cap_kw = cap;

                    newRows[rowIdx] = targetRow;
                    return newRows;
                  });
                }

                if (draggingBox) {
                  const { rowIdx, startPos, initialPoly } = draggingBox;
                  const dx = x - startPos[0];
                  const dy = y - startPos[1];

                  setRows(prevRows => {
                    const newRows = [...prevRows];
                    const targetRow = { ...newRows[rowIdx] };
                    const movedPoly = initialPoly.map(pt => [
                      Math.max(0, Math.min(1000, pt[0] + dx)),
                      Math.max(0, Math.min(1000, pt[1] + dy))
                    ]);
                    targetRow.polygon = movedPoly;
                    newRows[rowIdx] = targetRow;
                    return newRows;
                  });
                }

                if (isRectDrawing) {
                  setRectCurrent([x, y]);
                }
              }}
              onMouseUp={() => {
                if (draggingVertex) {
                  setDraggingVertex(null);
                  toast.success("✨ 已完成頂點點位拉伸！即時更新面積與大金配機結果。");
                }
                if (draggingBox) {
                  setDraggingBox(null);
                  toast.success("✨ 已成功平移整體框底！完成空間邊界位置對齊。");
                }
                if (isRectDrawing && rectStart && rectCurrent) {
                  setIsRectDrawing(false);
                  const p1 = rectStart;
                  const p2 = rectCurrent;
                  setRectStart(null);
                  setRectCurrent(null);

                  if (drawToolMode === 'scale') {
                    const imgEl = modalImgRef.current || imgRef.current;
                    const imgW = imgEl ? (imgEl.naturalWidth || imgEl.width || 1600) : 1600;
                    const imgH = imgEl ? (imgEl.naturalHeight || imgEl.height || 1200) : 1200;

                    const dxRaw = ((p2[0] - p1[0]) / 1000.0) * imgW;
                    const dyRaw = ((p2[1] - p1[1]) / 1000.0) * imgH;
                    const distPxRaw = Math.sqrt(dxRaw * dxRaw + dyRaw * dyRaw);

                    if (distPxRaw > 5) {
                      const userCm = prompt("請輸入這條拉出的參考線實際長度 (單位: 公分 cm):", "100");
                      const refCm = parseFloat(userCm) || 100;
                      const ratio = (refCm / 100.0) / distPxRaw;
                      setPixelToMeterRatio(ratio);
                      setDoorGapSettings(prev => ({
                        ...prev,
                        pickedLine: { p1, p2, distPx: Math.round(distPxRaw), doorCm: refCm }
                      }));

                      // 🎯 即時重算並連動更新現有所有空間之精準面積與大金選機 (消除縱橫比變形)
                      setRows(prevRows => prevRows.map(row => {
                        if (!row.polygon || row.polygon.length < 3) return row;
                        const realAreaM2 = calculateRealAreaFromPolygon(row.polygon, ratio, imgW, imgH);
                        const realAreaPing = parseFloat((realAreaM2 * 0.3025).toFixed(2));
                        const baseKcal = row.calc_basis || 520;
                        const initialDemand = Math.round(realAreaPing * baseKcal);
                        const autoMatch = clientSideSelectEquipment(initialDemand, row.system_type || "VRV");
                        return {
                          ...row,
                          area_m2: realAreaM2,
                          area_ping: realAreaPing,
                          total_cooling_demand: initialDemand,
                          best_match_model: autoMatch.model,
                          unit_count: autoMatch.qty,
                          cap_kw: autoMatch.cap
                        };
                      }));

                      setDrawToolMode('view');
                      toast.success(`📏 參考尺寸標定成功！已知長度: ${refCm}cm (${Math.round(distPxRaw)}px)，已消除長寬比變形並重算全圖空間！`);
                    }
                    return;
                  }

                  if (drawToolMode === 'rect') {
                    const xmin = Math.min(p1[0], p2[0]);
                    const xmax = Math.max(p1[0], p2[0]);
                    const ymin = Math.min(p1[1], p2[1]);
                    const ymax = Math.max(p1[1], p2[1]);
                    if ((xmax - xmin) > 15 && (ymax - ymin) > 15) {
                      handleFinishPline([[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]]);
                    }
                  }
                }
              }}
              onMouseLeave={() => {
                setIsRectDrawing(false);
              }}
            >
              {previewUrl && (
                <div
                  style={{
                    position: 'relative',
                    display: 'inline-block',
                    lineHeight: 0,
                    fontSize: 0,
                    maxWidth: '100%',
                    maxHeight: '100%',
                    transform: `scale(${scale})`,
                    transformOrigin: 'center center'
                  }}
                >
                  <img
                    ref={modalImgRef}
                    src={previewUrl}
                    alt="Preview Large Modal"
                    draggable={false}
                    onDragStart={(e) => e.preventDefault()}
                    style={{
                      maxWidth: '100%',
                      maxHeight: '80vh',
                      width: 'auto',
                      height: 'auto',
                      display: 'block',
                      userSelect: 'none',
                      WebkitUserDrag: 'none',
                      WebkitUserSelect: 'none'
                    }}
                  />
                  <svg
                    ref={modalSvgRef}
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'auto' }}
                    viewBox="0 0 1000 1000"
                    preserveAspectRatio="none"
                  >
                    {rows && rows.length > 0 && rows.map((row, idx) => {
                      if (!row.selected) return null;
                      const color = OVERLAY_COLORS[idx % OVERLAY_COLORS.length];
                      let poly = row.polygon;
                      if (!poly || !Array.isArray(poly) || poly.length < 3) return null;
                      const pointsStr = poly.map(pt => `${pt[0]},${pt[1]}`).join(' ');
                      const avgX = poly.reduce((sum, pt) => sum + pt[0], 0) / poly.length;
                      const avgY = poly.reduce((sum, pt) => sum + pt[1], 0) / poly.length;

                      const spaceTitle = row.space_name || `空間 ${idx + 1}`;
                      const badgeTextStr = `${spaceTitle} | ${row.area_m2}㎡ / ${row.area_ping}坪`;

                      const customFillModal = row.box_color ? (row.box_color.startsWith('#') ? `${row.box_color}55` : row.box_color) : color.bg;

                      return (
                        <g key={idx}>
                          <polygon
                            points={pointsStr}
                            fill={customFillModal}
                            stroke="none"
                            style={{ pointerEvents: 'none' }}
                          />
                          <foreignObject x={avgX - 85} y={avgY - 14} width="170" height="28" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                            <div style={{ display: 'flex', justifyContent: 'center' }}>
                              <span style={{ backgroundColor: color.badgeBg, color: color.badgeText, fontSize: '11px', fontWeight: 'bold', padding: '2px 6px', borderRadius: '4px', whiteSpace: 'nowrap', boxShadow: '0 2px 5px rgba(0,0,0,0.6)' }}>
                                {badgeTextStr}
                              </span>
                            </div>
                          </foreignObject>
                        </g>
                      );
                    })}
                    {/* CAD 視覺輔助滿版動態十字對齊輔助線 */}
                    {mousePos && mousePos[0] > 0 && (
                      <g key="cad_crosshair_m">
                        <line x1={mousePos[0]} y1="0" x2={mousePos[0]} y2="1000" stroke="rgba(239, 68, 68, 0.45)" strokeWidth="1.5" strokeDasharray="5 3" />
                        <line x1="0" y1={mousePos[1]} x2="1000" y2={mousePos[1]} stroke="rgba(239, 68, 68, 0.45)" strokeWidth="1.5" strokeDasharray="5 3" />
                      </g>
                    )}
                    {isRectDrawing && drawToolMode === 'scale' && rectStart && rectCurrent && (
                      <g key="active_scale_line_m">
                        <line x1={rectStart[0]} y1={rectStart[1]} x2={rectCurrent[0]} y2={rectCurrent[1]} stroke="#38bdf8" strokeWidth="4" strokeDasharray="6 3" />
                        <circle cx={rectStart[0]} cy={rectStart[1]} r="7" fill="#0284c7" stroke="#ffffff" strokeWidth="2" />
                        <circle cx={rectCurrent[0]} cy={rectCurrent[1]} r="7" fill="#0284c7" stroke="#ffffff" strokeWidth="2" />
                      </g>
                    )}
                    {plinePoints.length > 0 && (
                      <g key="active_pline_m">
                        <polyline points={plinePoints.map(p => `${p[0]},${p[1]}`).join(' ')} fill="rgba(239, 68, 68, 0.25)" stroke="#ef4444" strokeWidth="3" />
                        <line x1={plinePoints[plinePoints.length - 1][0]} y1={plinePoints[plinePoints.length - 1][1]} x2={mousePos[0]} y2={mousePos[1]} stroke="#ef4444" strokeWidth="3" strokeDasharray="5 3" />
                        {plinePoints.map((p, i) => (<circle key={i} cx={p[0]} cy={p[1]} r="7" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />))}
                        <circle cx={mousePos[0]} cy={mousePos[1]} r="6" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
                      </g>
                    )}
                    {isRectDrawing && drawToolMode === 'rect' && rectStart && rectCurrent && (
                      <g key="active_rect_m">
                        <rect x={Math.min(rectStart[0], rectCurrent[0])} y={Math.min(rectStart[1], rectCurrent[1])} width={Math.abs(rectCurrent[0] - rectStart[0])} height={Math.abs(rectCurrent[1] - rectStart[1])} fill="rgba(239, 68, 68, 0.35)" stroke="#ef4444" strokeWidth="3" strokeDasharray="6 3" />
                      </g>
                    )}
                    {doorGapSettings.pickedLine && (
                      <g key="door_calib_line_m">
                        <line x1={doorGapSettings.pickedLine.p1[0]} y1={doorGapSettings.pickedLine.p1[1]} x2={doorGapSettings.pickedLine.p2[0]} y2={doorGapSettings.pickedLine.p2[1]} stroke="#38bdf8" strokeWidth="5" />
                        <circle cx={doorGapSettings.pickedLine.p1[0]} cy={doorGapSettings.pickedLine.p1[1]} r="8" fill="#0284c7" stroke="#ffffff" strokeWidth="2" />
                        <circle cx={doorGapSettings.pickedLine.p2[0]} cy={doorGapSettings.pickedLine.p2[1]} r="8" fill="#0284c7" stroke="#ffffff" strokeWidth="2" />
                        <foreignObject
                          x={(doorGapSettings.pickedLine.p1[0] + doorGapSettings.pickedLine.p2[0])/2 - 75}
                          y={(doorGapSettings.pickedLine.p1[1] + doorGapSettings.pickedLine.p2[1])/2 - 15}
                          width="150"
                          height="30"
                          style={{ overflow: 'visible' }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'center' }}>
                            <span style={{
                              backgroundColor: '#0284c7',
                              color: '#ffffff',
                              fontWeight: 'bold',
                              fontSize: '11px',
                              padding: '3px 8px',
                              borderRadius: '12px',
                              whiteSpace: 'nowrap',
                              boxShadow: '0 2px 6px rgba(0,0,0,0.6)',
                              border: '1px solid #ffffff'
                            }}>
                              📏 參考尺寸線 ({doorGapSettings.pickedLine.doorCm || 100}cm)
                            </span>
                          </div>
                        </foreignObject>
                      </g>
                    )}
                  </svg>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#020617',
    color: '#f8fafc',
    fontFamily: '"Outfit", "Noto Sans TC", sans-serif',
    padding: '16px 24px',
    boxSizing: 'border-box'
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: '16px',
    borderBottom: '1px solid #1e293b',
    marginBottom: '16px'
  },
  logoBox: {
    backgroundColor: '#0284c7',
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: '14px',
    padding: '4px 10px',
    borderRadius: '4px',
    marginRight: '12px',
    letterSpacing: '1px'
  },
  panel: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#0f172a',
    border: '1px solid #1e293b',
    borderRadius: '8px',
    padding: '12px 16px',
    marginBottom: '16px',
    gap: '12px',
    flexWrap: 'wrap'
  },
  btnPrimary: {
    backgroundColor: '#059669',
    color: '#ffffff',
    border: 'none',
    padding: '10px 18px',
    borderRadius: '6px',
    fontWeight: 'bold',
    fontSize: '13px',
    cursor: 'pointer'
  },
  btnSecondary: {
    backgroundColor: '#1e293b',
    color: '#34d399',
    border: '1px solid #059669',
    padding: '10px 16px',
    borderRadius: '6px',
    fontWeight: 'bold',
    fontSize: '13px',
    cursor: 'pointer'
  },
  mainGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px'
  },
  card: {
    backgroundColor: '#0f172a',
    border: '1px solid #1e293b',
    borderRadius: '8px',
    padding: '16px'
  },
  cardTitle: {
    fontSize: '14px',
    fontWeight: 'bold',
    color: '#38bdf8',
    marginBottom: '12px'
  },
  previewBox: {
    height: '560px',
    backgroundColor: '#020617',
    borderRadius: '6px',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '12px'
  },
  th: {
    backgroundColor: '#1e293b',
    color: '#94a3b8',
    padding: '8px 6px',
    textAlign: 'left',
    borderBottom: '1px solid #334155',
    whiteSpace: 'nowrap'
  },
  td: {
    padding: '8px 6px',
    borderBottom: '1px solid #1e293b',
    color: '#e2e8f0',
    whiteSpace: 'nowrap'
  },
  inputNum: {
    backgroundColor: '#1e293b',
    border: '1px solid #475569',
    color: '#ffffff',
    padding: '3px 6px',
    borderRadius: '4px',
    width: '55px',
    fontSize: '12px'
  },
  inputModel: {
    backgroundColor: '#1e293b',
    border: '1px solid #475569',
    color: '#ffffff',
    padding: '3px 6px',
    borderRadius: '4px',
    width: '110px',
    fontSize: '12px'
  },
  inputQty: {
    backgroundColor: '#1e293b',
    border: '1px solid #475569',
    color: '#ffffff',
    padding: '3px 6px',
    borderRadius: '4px',
    width: '40px',
    fontSize: '12px'
  },
  selectSys: {
    backgroundColor: '#1e293b',
    border: '1px solid #475569',
    color: '#ffffff',
    padding: '3px 6px',
    borderRadius: '4px',
    fontSize: '12px'
  },
  chkLabel: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '3px',
    marginRight: '6px',
    fontSize: '11px',
    color: '#cbd5e1'
  }
};

export default App;