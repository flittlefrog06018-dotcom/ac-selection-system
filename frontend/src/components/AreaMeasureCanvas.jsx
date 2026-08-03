import React, { useRef, useEffect, useState, useCallback } from 'react';

/**
 * AreaMeasureCanvas
 * 高精準 Canvas 劃框漆桶填滿與自動測量組件
 * 
 * 特點：
 * 1. 忽略內部黑色/灰色家具線條 (僅以高飽和度螢光/彩筆劃框為外框邊界)
 * 2. 比例尺設定 (參考線 cm -> px/m 換算)
 * 3. 漆桶發散填滿 (BFS + 5px 形態學膨脹補縫)
 * 4. 矩形 / 多邊形 (PLINE) 面積增設與扣除 (加選 + / 減選 -)
 * 5. 滾輪平滑放大縮小 (Zoom & Pan) 與清單即時同步
 */
export default function AreaMeasureCanvas({
  imageUrl,
  onZoneDataChange,
  className = ""
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  // --- 工具模式 ---
  // 'fill': 漆桶發散 (無視家具)
  // 'scale': 比例尺標定
  // 'rect_add': 矩形增選 (+)
  // 'rect_sub': 矩形扣除 (-)
  // 'poly_add': 多邊形連線增選 (+)
  // 'poly_sub': 多邊形連線扣除 (-)
  // 'pan': 拖曳平移
  const [activeMode, setActiveMode] = useState('fill');

  // --- 畫布平移與縮放 (Zoom & Pan) ---
  const [transform, setTransform] = useState({ scale: 1, x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [startPan, setStartPan] = useState({ x: 0, y: 0 });

  // --- 比例尺狀態 ---
  const [scaleLine, setScaleLine] = useState(null); // { x1, y1, x2, y2 }
  const [isDrawingScale, setIsDrawingScale] = useState(false);
  const [refRealCm, setRefRealCm] = useState(100); // 預設 100 cm
  const [pixelToMeterRatio, setPixelToMeterRatio] = useState(100); // 預設 100 px = 1 m

  // --- 色彩選單 ---
  const colorPalette = ["#ff5722", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899", "#f59e0b"];
  const [selectedColor, setSelectedColor] = useState(colorPalette[0]);

  // --- 空間區域資料集 ---
  const [zones, setZones] = useState([]);
  const [activeZoneId, setActiveZoneId] = useState(null);

  // --- 矩形與多邊形繪製暫存 ---
  const [rectDraft, setRectDraft] = useState(null); // { x1, y1, x2, y2 }
  const [isRectDrawing, setIsRectDrawing] = useState(false);
  const [polyPts, setPolyPts] = useState([]);

  // --- 影像資訊 ---
  const [imgObj, setImgObj] = useState(null);
  const [imgDimensions, setImgDimensions] = useState({ width: 800, height: 600 });

  // 載入底圖
  useEffect(() => {
    if (!imageUrl) return;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = imageUrl;
    img.onload = () => {
      setImgObj(img);
      setImgDimensions({ width: img.naturalWidth, height: img.naturalHeight });
    };
  }, [imageUrl]);

  // 觸發外部數據鏈異動
  const notifyZoneDataChange = useCallback((updatedZones) => {
    if (onZoneDataChange) {
      onZoneDataChange(updatedZones);
    }
  }, [onZoneDataChange]);

  // 🎯 核心演算法 1：邊界提取 (無視家具黑線，僅保留高飽和度彩筆外框) + 5px 形態學膨脹補縫
  const buildDilatedBoundaryMask = (ctx, width, height) => {
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;
    const isBoundary = new Uint8Array(width * height);

    // 1. 色彩過濾：僅將彩筆/螢光標註外框 (高飽和度 saturation > 20 && maxC > 30) 視為邊界！
    // 忽略所有黑/灰色家具線條 (maxC < 60 或飽和度低者)，使漆桶可直接越過家具！
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        const a = data[idx + 3];

        if (a < 50) continue;

        const maxC = Math.max(r, g, b);
        const minC = Math.min(r, g, b);
        const saturation = maxC === 0 ? 0 : ((maxC - minC) / maxC) * 255;

        // 僅高飽和度色塊 (螢光藍/橘/綠等標註框) 判定為牆界
        if (saturation > 20 && maxC > 30) {
          isBoundary[y * width + x] = 1;
        }
      }
    }

    // 2. 5px 形態學膨脹補縫 (Dilation) radius = 5
    const dilated = new Uint8Array(width * height);
    const radius = 5;
    const radiusSq = radius * radius;

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        if (isBoundary[y * width + x] === 1) {
          for (let dy = -radius; dy <= radius; dy++) {
            const ny = y + dy;
            if (ny < 0 || ny >= height) continue;
            for (let dx = -radius; dx <= radius; dx++) {
              const nx = x + dx;
              if (nx < 0 || nx >= width) continue;
              if (dx * dx + dy * dy <= radiusSq) {
                dilated[ny * width + nx] = 1;
              }
            }
          }
        }
      }
    }

    return dilated;
  };

  // 🎯 核心演算法 2：BFS 漆桶廣度搜尋發散
  const floodFillRoom = (startX, startY, width, height, dilatedMask) => {
    const visited = new Uint8Array(width * height);
    const queue = [startX, startY];
    let filledCount = 0;

    const maskCanvas = document.createElement('canvas');
    maskCanvas.width = width;
    maskCanvas.height = height;
    const maskCtx = maskCanvas.getContext('2d');
    const maskImgData = maskCtx.createImageData(width, height);
    const mData = maskImgData.data;

    const hex = selectedColor.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);

    let sumX = 0, sumY = 0;
    let head = 0;
    while (head < queue.length) {
      const cx = queue[head++];
      const cy = queue[head++];

      if (cx < 0 || cx >= width || cy < 0 || cy >= height) continue;
      const pos = cy * width + cx;

      if (visited[pos] === 1 || dilatedMask[pos] === 1) continue;

      visited[pos] = 1;
      filledCount++;
      sumX += cx;
      sumY += cy;

      const pIdx = pos * 4;
      mData[pIdx] = r;
      mData[pIdx + 1] = g;
      mData[pIdx + 2] = b;
      mData[pIdx + 3] = 140; // 半透明 Alpha

      queue.push(cx + 1, cy);
      queue.push(cx - 1, cy);
      queue.push(cx, cy + 1);
      queue.push(cx, cy - 1);
    }

    if (filledCount < 20) return null;

    maskCtx.putImageData(maskImgData, 0, 0);
    const sqM = (filledCount / (pixelToMeterRatio * pixelToMeterRatio)).toFixed(2);
    const ping = (sqM * 0.3025).toFixed(2);

    return {
      filledPixels: filledCount,
      maskCanvas: maskCanvas,
      maskBase64: maskCanvas.toDataURL("image/png"),
      sqMeters: parseFloat(sqM),
      ping: parseFloat(ping),
      centerX: Math.round(sumX / filledCount),
      centerY: Math.round(sumY / filledCount)
    };
  };

  // 🎯 重新估算某遮罩 Canvas 之像素量與面積
  const recalculateZoneFromCanvas = (maskCanvas, colorHex) => {
    const ctx = maskCanvas.getContext('2d');
    const w = maskCanvas.width;
    const h = maskCanvas.height;
    const imgData = ctx.getImageData(0, 0, w, h);
    const data = imgData.data;

    let filledCount = 0;
    let sumX = 0, sumY = 0;

    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] > 20) {
        filledCount++;
        const pixelIdx = i / 4;
        sumX += (pixelIdx % w);
        sumY += Math.floor(pixelIdx / w);
      }
    }

    const sqM = filledCount > 0 ? (filledCount / (pixelToMeterRatio * pixelToMeterRatio)).toFixed(2) : "0.00";
    const ping = (parseFloat(sqM) * 0.3025).toFixed(2);

    return {
      sqMeters: parseFloat(sqM),
      ping: parseFloat(ping),
      centerX: filledCount > 0 ? Math.round(sumX / filledCount) : 0,
      centerY: filledCount > 0 ? Math.round(sumY / filledCount) : 0,
      maskBase64: maskCanvas.toDataURL("image/png")
    };
  };

  // 比例尺更新
  useEffect(() => {
    if (!scaleLine) return;
    const dx = scaleLine.x2 - scaleLine.x1;
    const dy = scaleLine.y2 - scaleLine.y1;
    const pixelLength = Math.sqrt(dx * dx + dy * dy);
    if (pixelLength > 5) {
      const realMeters = refRealCm / 100;
      const ratio = pixelLength / realMeters;
      setPixelToMeterRatio(ratio);
    }
  }, [scaleLine, refRealCm]);

  // 重繪主畫布
  const redrawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imgObj) return;
    const ctx = canvas.getContext('2d');

    const w = imgDimensions.width;
    const h = imgDimensions.height;
    canvas.width = w;
    canvas.height = h;

    // 1. 底圖
    ctx.drawImage(imgObj, 0, 0, w, h);

    // 2. 所有空間遮罩圖層
    zones.forEach((zone) => {
      if (zone._maskCanvas) {
        ctx.drawImage(zone._maskCanvas, 0, 0);
      }
      if (zone.centerX && zone.centerY && zone.sqMeters > 0) {
        ctx.save();
        ctx.font = "bold 16px sans-serif";
        ctx.fillStyle = "#ffffff";
        ctx.shadowColor = "rgba(0,0,0,0.9)";
        ctx.shadowBlur = 5;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(`${zone.zoneName} (${zone.sqMeters}m² / ${zone.ping}坪)`, zone.centerX, zone.centerY);
        ctx.restore();
      }
    });

    // 3. 比例尺放樣參考線
    if (scaleLine) {
      ctx.save();
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 4;
      ctx.setLineDash([8, 6]);
      ctx.beginPath();
      ctx.moveTo(scaleLine.x1, scaleLine.y1);
      ctx.lineTo(scaleLine.x2, scaleLine.y2);
      ctx.stroke();

      ctx.fillStyle = "#0284c7";
      ctx.beginPath();
      ctx.arc(scaleLine.x1, scaleLine.y1, 6, 0, Math.PI * 2);
      ctx.arc(scaleLine.x2, scaleLine.y2, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // 4. 矩形繪製草稿 (加選/減選)
    if (rectDraft) {
      ctx.save();
      ctx.strokeStyle = activeMode.includes('add') ? '#22c55e' : '#ef4444';
      ctx.fillStyle = activeMode.includes('add') ? 'rgba(34, 197, 94, 0.25)' : 'rgba(239, 68, 68, 0.25)';
      ctx.lineWidth = 2;
      const rx = Math.min(rectDraft.x1, rectDraft.x2);
      const ry = Math.min(rectDraft.y1, rectDraft.y2);
      const rw = Math.abs(rectDraft.x2 - rectDraft.x1);
      const rh = Math.abs(rectDraft.y2 - rectDraft.y1);
      ctx.fillRect(rx, ry, rw, rh);
      ctx.strokeRect(rx, ry, rw, rh);
      ctx.restore();
    }

    // 5. 多邊形連線草稿
    if (polyPts.length > 0) {
      ctx.save();
      ctx.strokeStyle = activeMode.includes('add') ? '#22c55e' : '#ef4444';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(polyPts[0][0], polyPts[0][1]);
      for (let i = 1; i < polyPts.length; i++) {
        ctx.lineTo(polyPts[i][0], polyPts[i][1]);
      }
      ctx.stroke();

      ctx.fillStyle = '#ffffff';
      polyPts.forEach(pt => {
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 4, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();
    }
  }, [imgObj, imgDimensions, zones, scaleLine, rectDraft, polyPts, activeMode]);

  useEffect(() => {
    redrawCanvas();
  }, [redrawCanvas]);

  // 取得相對圖片之邏輯座標
  const getCanvasCoords = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);
    return { x, y };
  };

  // 處理畫布點擊與拖曳
  const handleMouseDown = (e) => {
    if (activeMode === 'pan' || e.button === 1 || e.spaceKey) {
      setIsPanning(true);
      setStartPan({ x: e.clientX - transform.x, y: e.clientY - transform.y });
      return;
    }

    const { x, y } = getCanvasCoords(e);

    if (activeMode === 'scale') {
      setIsDrawingScale(true);
      setScaleLine({ x1: x, y1: y, x2: x, y2: y });
    } else if (activeMode === 'fill') {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      const dilatedMask = buildDilatedBoundaryMask(ctx, canvas.width, canvas.height);
      const result = floodFillRoom(x, y, canvas.width, canvas.height, dilatedMask);

      if (result) {
        const newZone = {
          id: `zone_${Date.now()}`,
          zoneName: `空間區域 ${zones.length + 1}`,
          colorHex: selectedColor,
          sqMeters: result.sqMeters,
          ping: result.ping,
          maskBase64: result.maskBase64,
          centerX: result.centerX,
          centerY: result.centerY,
          _maskCanvas: result.maskCanvas
        };

        const updatedZones = [...zones, newZone];
        setZones(updatedZones);
        setActiveZoneId(newZone.id);
        notifyZoneDataChange(updatedZones);
      }
    } else if (activeMode === 'rect_add' || activeMode === 'rect_sub') {
      setIsRectDrawing(true);
      setRectDraft({ x1: x, y1: y, x2: x, y2: y });
    } else if (activeMode === 'poly_add' || activeMode === 'poly_sub') {
      setPolyPts(prev => [...prev, [x, y]]);
    }
  };

  const handleMouseMove = (e) => {
    if (isPanning) {
      setTransform(prev => ({
        ...prev,
        x: e.clientX - startPan.x,
        y: e.clientY - startPan.y
      }));
      return;
    }

    const { x, y } = getCanvasCoords(e);

    if (isDrawingScale && activeMode === 'scale') {
      setScaleLine(prev => prev ? { ...prev, x2: x, y2: y } : null);
    } else if (isRectDrawing && (activeMode === 'rect_add' || activeMode === 'rect_sub')) {
      setRectDraft(prev => prev ? { ...prev, x2: x, y2: y } : null);
    }
  };

  const handleMouseUp = () => {
    if (isPanning) {
      setIsPanning(false);
      return;
    }

    if (isDrawingScale) {
      setIsDrawingScale(false);
    }

    // 完成矩形加選或扣除
    if (isRectDrawing && rectDraft) {
      setIsRectDrawing(false);
      const targetZone = zones.find(z => z.id === activeZoneId) || zones[zones.length - 1];
      if (targetZone && targetZone._maskCanvas) {
        const maskCtx = targetZone._maskCanvas.getContext('2d');
        const rx = Math.min(rectDraft.x1, rectDraft.x2);
        const ry = Math.min(rectDraft.y1, rectDraft.y2);
        const rw = Math.abs(rectDraft.x2 - rectDraft.x1);
        const rh = Math.abs(rectDraft.y2 - rectDraft.y1);

        if (activeMode === 'rect_add') {
          const hex = targetZone.colorHex.replace('#', '');
          maskCtx.fillStyle = `rgba(${parseInt(hex.substring(0,2),16)}, ${parseInt(hex.substring(2,4),16)}, ${parseInt(hex.substring(4,6),16)}, 0.55)`;
          maskCtx.globalCompositeOperation = 'source-over';
          maskCtx.fillRect(rx, ry, rw, rh);
        } else if (activeMode === 'rect_sub') {
          maskCtx.globalCompositeOperation = 'destination-out';
          maskCtx.fillRect(rx, ry, rw, rh);
        }

        const metrics = recalculateZoneFromCanvas(targetZone._maskCanvas, targetZone.colorHex);
        const updatedZones = zones.map(z => z.id === targetZone.id ? { ...z, ...metrics } : z);
        setZones(updatedZones);
        notifyZoneDataChange(updatedZones);
      }
      setRectDraft(null);
    }
  };

  // 右鍵完成多邊形 (PLINE) 加選/扣除
  const handleContextMenu = (e) => {
    e.preventDefault();
    if (polyPts.length >= 3 && (activeMode === 'poly_add' || activeMode === 'poly_sub')) {
      const targetZone = zones.find(z => z.id === activeZoneId) || zones[zones.length - 1];
      if (targetZone && targetZone._maskCanvas) {
        const maskCtx = targetZone._maskCanvas.getContext('2d');
        maskCtx.beginPath();
        maskCtx.moveTo(polyPts[0][0], polyPts[0][1]);
        for (let i = 1; i < polyPts.length; i++) {
          maskCtx.lineTo(polyPts[i][0], polyPts[i][1]);
        }
        maskCtx.closePath();

        if (activeMode === 'poly_add') {
          const hex = targetZone.colorHex.replace('#', '');
          maskCtx.fillStyle = `rgba(${parseInt(hex.substring(0,2),16)}, ${parseInt(hex.substring(2,4),16)}, ${parseInt(hex.substring(4,6),16)}, 0.55)`;
          maskCtx.globalCompositeOperation = 'source-over';
          maskCtx.fill();
        } else if (activeMode === 'poly_sub') {
          maskCtx.globalCompositeOperation = 'destination-out';
          maskCtx.fill();
        }

        const metrics = recalculateZoneFromCanvas(targetZone._maskCanvas, targetZone.colorHex);
        const updatedZones = zones.map(z => z.id === targetZone.id ? { ...z, ...metrics } : z);
        setZones(updatedZones);
        notifyZoneDataChange(updatedZones);
      }
      setPolyPts([]);
    }
  };

  // 滾輪縮放 (Zoom)
  const handleWheel = (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    setTransform(prev => ({
      ...prev,
      scale: Math.max(0.4, Math.min(6.0, prev.scale * zoomFactor))
    }));
  };

  // 重置區域
  const handleResetZones = () => {
    setZones([]);
    setActiveZoneId(null);
    notifyZoneDataChange([]);
  };

  // 刪除單一區域
  const handleDeleteZone = (id) => {
    const updated = zones.filter(z => z.id !== id);
    setZones(updated);
    if (activeZoneId === id) setActiveZoneId(updated.length ? updated[updated.length - 1].id : null);
    notifyZoneDataChange(updated);
  };

  return (
    <div ref={containerRef} className={`flex flex-col gap-3 p-4 bg-slate-900 text-slate-100 rounded-xl border border-slate-800 shadow-2xl ${className}`}>
      {/* 頂部操作工具列 */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-slate-800/90 rounded-lg border border-slate-700">
        <div className="flex items-center gap-1.5 flex-wrap">
          {/* 工具按鈕組 */}
          <button
            onClick={() => setActiveMode('fill')}
            className={`px-3 py-1.5 rounded-md font-medium text-xs transition-all ${
              activeMode === 'fill' ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/30' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            🪣 漆桶 (無視家具)
          </button>
          <button
            onClick={() => setActiveMode('scale')}
            className={`px-3 py-1.5 rounded-md font-medium text-xs transition-all ${
              activeMode === 'scale' ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/30' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            📏 設定比例尺
          </button>

          <span className="w-px h-5 bg-slate-700 mx-1" />

          {/* 矩形加選與扣除 */}
          <button
            onClick={() => setActiveMode('rect_add')}
            className={`px-2.5 py-1.5 rounded-md font-medium text-xs transition-all ${
              activeMode === 'rect_add' ? 'bg-emerald-600 text-white shadow-lg' : 'bg-slate-700 text-emerald-400 hover:bg-slate-600'
            }`}
          >
            ➕ 矩形增選
          </button>
          <button
            onClick={() => setActiveMode('rect_sub')}
            className={`px-2.5 py-1.5 rounded-md font-medium text-xs transition-all ${
              activeMode === 'rect_sub' ? 'bg-rose-600 text-white shadow-lg' : 'bg-slate-700 text-rose-400 hover:bg-slate-600'
            }`}
          >
            ➖ 矩形扣除
          </button>

          {/* 多邊形加選與扣除 */}
          <button
            onClick={() => setActiveMode('poly_add')}
            className={`px-2.5 py-1.5 rounded-md font-medium text-xs transition-all ${
              activeMode === 'poly_add' ? 'bg-emerald-600 text-white shadow-lg' : 'bg-slate-700 text-emerald-400 hover:bg-slate-600'
            }`}
          >
            🔷 多邊形加選
          </button>
          <button
            onClick={() => setActiveMode('poly_sub')}
            className={`px-2.5 py-1.5 rounded-md font-medium text-xs transition-all ${
              activeMode === 'poly_sub' ? 'bg-rose-600 text-white shadow-lg' : 'bg-slate-700 text-rose-400 hover:bg-slate-600'
            }`}
          >
            ✂️ 多邊形扣減 (右鍵完成)
          </button>
        </div>

        {/* 比例尺數值與操作 */}
        <div className="flex items-center gap-3">
          {activeMode === 'scale' && (
            <div className="flex items-center gap-2 text-xs bg-slate-900/80 px-2.5 py-1 rounded border border-slate-700">
              <span>參照長度:</span>
              <input
                type="number"
                value={refRealCm}
                onChange={(e) => setRefRealCm(Number(e.target.value) || 100)}
                className="w-14 px-1 py-0.5 bg-slate-800 border border-slate-600 rounded text-center text-sky-400 font-mono font-bold"
              />
              <span>cm</span>
            </div>
          )}

          {/* 漆桶色彩選單 */}
          <div className="flex items-center gap-1">
            {colorPalette.map(color => (
              <button
                key={color}
                onClick={() => setSelectedColor(color)}
                style={{ backgroundColor: color }}
                className={`w-5 h-5 rounded-full transition-transform ${
                  selectedColor === color ? 'ring-2 ring-white scale-110' : 'opacity-70 hover:opacity-100'
                }`}
              />
            ))}
          </div>

          <button
            onClick={handleResetZones}
            className="px-2.5 py-1 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 rounded text-xs transition-all"
          >
            🗑️ 清除圖層
          </button>
        </div>
      </div>

      {/* 畫布視窗與滾輪縮放/平移容器 */}
      <div
        className="relative overflow-hidden border border-slate-800 rounded-lg bg-slate-950 flex items-center justify-center h-[560px] cursor-crosshair"
        onWheel={handleWheel}
      >
        <div
          style={{
            transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
            transformOrigin: 'center center',
            transition: isPanning ? 'none' : 'transform 0.05s ease-out'
          }}
          className="relative inline-block"
        >
          <canvas
            ref={canvasRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onContextMenu={handleContextMenu}
            className="max-w-none block shadow-2xl"
          />
        </div>

        {/* 縮放工具提示 */}
        <div className="absolute bottom-3 right-3 bg-slate-900/80 backdrop-blur px-3 py-1 rounded border border-slate-700 text-xs text-slate-400 flex items-center gap-2">
          <span>🔍 縮放: {(transform.scale * 100).toFixed(0)}%</span>
          <button
            onClick={() => setTransform({ scale: 1, x: 0, y: 0 })}
            className="text-sky-400 hover:underline"
          >
            100% 復原
          </button>
        </div>
      </div>

      {/* 下方空間數據表格 */}
      {zones.length > 0 && (
        <div className="flex flex-col gap-2 p-3 bg-slate-800/60 rounded-lg border border-slate-700/60">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">標示空間數據與修飾選單</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            {zones.map((zone) => (
              <div
                key={zone.id}
                onClick={() => setActiveZoneId(zone.id)}
                className={`flex items-center justify-between p-2.5 rounded-md text-xs cursor-pointer border transition-all ${
                  activeZoneId === zone.id ? 'bg-slate-700 border-sky-500 shadow-md' : 'bg-slate-800/80 border-slate-700 hover:border-slate-600'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: zone.colorHex }} />
                  <input
                    type="text"
                    value={zone.zoneName}
                    onChange={(e) => {
                      const updated = zones.map(z => z.id === zone.id ? { ...z, zoneName: e.target.value } : z);
                      setZones(updated);
                      notifyZoneDataChange(updated);
                    }}
                    className="bg-slate-900 border border-slate-600 rounded px-1.5 py-0.5 text-slate-200 text-xs w-24"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sky-400 font-mono font-bold">{zone.sqMeters} m² / {zone.ping} 坪</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteZone(zone.id);
                    }}
                    className="text-rose-400 hover:text-rose-300 px-1 text-xs"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
