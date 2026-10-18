import React, { useState, useEffect, useMemo, useRef } from 'react';
import { toast } from 'react-toastify';
import { OUTDOOR_UNITS_DB } from '../constants/acConstants';

/**
 * 依型號提取能力指數 (Capacity Index)
 * FXDQ20 -> 20, FXDQ32 -> 32, FXDQ50 -> 50, FXDQ63 -> 63, FXDQ80 -> 80
 */
function getCapIndexFromModel(modelName = '') {
  if (!modelName) return 20.0;
  const clean = String(modelName).trim().toUpperCase();
  const match = clean.match(/(?:FXDQ|FXSQ|FTXV|FTXM|FTX|FCQ|FHA|FXYP|FXAQ|FXNQ|FXMQ|FXEQ|FXHQ)(\d{2,3})/i);
  if (match) {
    const num = parseInt(match[1], 10);
    if (num === 63) return 62.5;
    return num;
  }
  const anyNum = clean.match(/(\d+)/);
  if (anyNum) {
    const n = parseInt(anyNum[1], 10);
    if (n in [20, 22, 25, 28, 32, 36, 40, 50, 60, 63, 71, 80, 90, 100, 112, 125, 140]) return n;
  }
  return 20.0;
}

/**
 * 依室外機型號提取 HP
 */
function getOutdoorHpFromModel(outdoorModel = '') {
  if (!outdoorModel) return 8.0;
  const clean = String(outdoorModel).trim().toUpperCase();
  const match = clean.match(/(?:RXYQ|RXQ|RSUYQ|REYQ|RWEYQ|RXYMQ|RXYCQ|RZQ)(\d+)/);
  if (match) {
    const val = parseInt(match[1], 10);
    if (val === 112) return 4.5;
    if (val === 125) return 5.0;
    if (val === 140) return 5.0;
    if (val === 160) return 6.0;
    if (val === 200 || val === 224) return 8.0;
    if (val === 250 || val === 280) return 10.0;
    if (val === 335) return 12.0;
    if (val === 400) return 14.0;
    if (val === 450) return 16.0;
    if (val === 500) return 18.0;
    if (val > 500) return Math.round(val / 25.0);
    return val;
  }
  return 8.0;
}

function isSideDischarge(outdoorModel = '') {
  const clean = String(outdoorModel).trim().toUpperCase();
  return /RSUYQ|RXYCQ|RXYMQ|VRV-S|MINI/.test(clean);
}

/**
 * 1. 主幹管徑選用 (室外機至第1分歧頭) - 大金原廠標準
 */
function getMainPipeSize(outdoorModel = '') {
  const clean = String(outdoorModel).trim().toUpperCase();
  if (isSideDischarge(clean)) {
    const match = clean.match(/(\d+)/);
    if (match) {
      const val = parseInt(match[1], 10);
      if (val <= 125) return { liquid: 'Φ9.5', gas: 'Φ15.9', text: 'Φ9.5 / Φ15.9' };
      if (val <= 200) return { liquid: 'Φ9.5', gas: 'Φ19.1', text: 'Φ9.5 / Φ19.1' };
      if (val <= 250) return { liquid: 'Φ9.5', gas: 'Φ22.2', text: 'Φ9.5 / Φ22.2' };
      return { liquid: 'Φ12.7', gas: 'Φ25.4', text: 'Φ12.7 / Φ25.4' };
    }
    return { liquid: 'Φ9.5', gas: 'Φ15.9', text: 'Φ9.5 / Φ15.9' };
  }

  const hp = getOutdoorHpFromModel(outdoorModel);
  if (hp <= 8) return { liquid: 'Φ9.5', gas: 'Φ19.1', text: 'Φ9.5 / Φ19.1' };
  if (hp <= 10) return { liquid: 'Φ9.5', gas: 'Φ22.2', text: 'Φ9.5 / Φ22.2' };
  if (hp <= 16) return { liquid: 'Φ12.7', gas: 'Φ28.6', text: 'Φ12.7 / Φ28.6' };
  if (hp <= 22) return { liquid: 'Φ15.9', gas: 'Φ28.6', text: 'Φ15.9 / Φ28.6' };
  if (hp <= 24) return { liquid: 'Φ15.9', gas: 'Φ34.9', text: 'Φ15.9 / Φ34.9' };
  if (hp <= 34) return { liquid: 'Φ19.1', gas: 'Φ34.9', text: 'Φ19.1 / Φ34.9' };
  return { liquid: 'Φ19.1', gas: 'Φ41.3', text: 'Φ19.1 / Φ41.3' };
}

/**
 * 2. 分歧頭選用表 (依下游能力指數總和 X)
 */
function getJointModel(xCapacity = 0) {
  if (xCapacity < 200) return { model: 'KHRP26A22T', short: '22T' };
  if (xCapacity < 290) return { model: 'KHRP26A33T', short: '33T' };
  if (xCapacity < 640) return { model: 'KHRP26A72T', short: '72T' };
  return { model: 'KHRP26A73T', short: '73T' };
}

/**
 * 3. 次幹管管徑 (依下游能力指數總和 X)
 */
function getSubPipeSize(xCapacity = 0) {
  if (xCapacity < 150) return { liquid: 'Φ9.5', gas: 'Φ15.9', text: 'Φ9.5 / Φ15.9' };
  if (xCapacity < 200) return { liquid: 'Φ9.5', gas: 'Φ19.1', text: 'Φ9.5 / Φ19.1' };
  if (xCapacity < 290) return { liquid: 'Φ9.5', gas: 'Φ22.2', text: 'Φ9.5 / Φ22.2' };
  if (xCapacity < 420) return { liquid: 'Φ12.7', gas: 'Φ28.6', text: 'Φ12.7 / Φ28.6' };
  if (xCapacity < 640) return { liquid: 'Φ15.9', gas: 'Φ28.6', text: 'Φ15.9 / Φ28.6' };
  if (xCapacity < 920) return { liquid: 'Φ19.1', gas: 'Φ34.9', text: 'Φ19.1 / Φ34.9' };
  return { liquid: 'Φ19.1', gas: 'Φ41.3', text: 'Φ19.1 / Φ41.3' };
}

/**
 * 4. 室內機末端配管 (依單機能力指數)
 */
function getIndoorBranchPipeSize(capacityIndex = 20) {
  if (capacityIndex <= 50) {
    return { liquid: 'Φ6.4', gas: 'Φ12.7', text: 'Φ6.4 / Φ12.7' };
  }
  if (capacityIndex <= 140) {
    return { liquid: 'Φ9.5', gas: 'Φ15.9', text: 'Φ9.5 / Φ15.9' };
  }
  return { liquid: 'Φ9.5', gas: 'Φ19.1', text: 'Φ9.5 / Φ19.1' };
}

export default function RefrigerantPipingDiagram({ rows = [], outdoorGroups = [], initialTrees = null, onSavePipingTree, onSavePipingDiagramImage }) {
  // 當前選取的室外機系統 ID
  const [selectedSysId, setSelectedSysId] = useState('sys-default');
  
  // 編輯完成狀態 (預設藍底「編輯完成」，點擊後變綠底「✓ 編輯完成」)
  const [isDiagramConfirmed, setIsDiagramConfirmed] = useState(false);

  // 樹狀結構存儲：{ [sysId]: Array<Item> }
  const [systemTrees, setSystemTrees] = useState(initialTrees && Object.keys(initialTrees).length > 0 ? initialTrees : {});

  // 拖曳狀態
  const [draggedItem, setDraggedItem] = useState(null); // { item, fromBranchId: null | string }

  const svgRef = useRef(null);

  // 1. 初始化各系統樹結構 (僅篩選 VRV 系統群組)
  const vrvOutdoorGroups = useMemo(() => {
    return (outdoorGroups || []).filter(g => {
      const isVrvSys = (g.system_type || '').toUpperCase() === 'VRV';
      const isVrvModel = g.outdoor_model && (
        g.outdoor_model.startsWith('RXQ') ||
        g.outdoor_model.startsWith('RXYQ') ||
        g.outdoor_model.startsWith('RSUYQ') ||
        g.outdoor_model.startsWith('RWEYQ')
      );
      return isVrvSys || isVrvModel;
    });
  }, [outdoorGroups]);

  useEffect(() => {
    // 找出所有 VRV 系統
    let systems = [];
    if (vrvOutdoorGroups.length > 0) {
      systems = vrvOutdoorGroups.map(g => ({
        id: g.id,
        name: g.name || `VRV 系統 (${g.outdoor_model})`,
        outdoor_model: g.outdoor_model || 'RXYQ8AYLT',
        outdoor_cap_kw: g.outdoor_cap_kw || 22.4,
        outdoor_count: g.outdoor_count || 1,
        system_type: 'VRV'
      }));
    } else {
      systems = [{
        id: 'sys-default',
        name: 'VRV 系統 1',
        outdoor_model: 'RXYQ8AYLT',
        outdoor_cap_kw: 22.4,
        outdoor_count: 1,
        system_type: 'VRV'
      }];
    }

    setSystemTrees(prevTrees => {
      const baseTrees = (Object.keys(prevTrees).length > 0)
        ? prevTrees
        : ((initialTrees && Object.keys(initialTrees).length > 0) ? initialTrees : {});
      const nextTrees = { ...baseTrees };
      systems.forEach(sys => {
        // 如果該系統已存在自訂拓撲，保留其結構，否則由 rows 自動建構單層預設
        if (!nextTrees[sys.id]) {
          const sysSpaces = rows.filter(r => (r.outdoorGroupId === sys.id) || (!r.outdoorGroupId && systems.length === 1 && (r.system_type === 'VRV' || r.best_match_model?.startsWith('FX'))));
          const initialItems = sysSpaces.map((r, idx) => ({
            id: `indoor-${sys.id}-${idx}-${Date.now()}`,
            type: 'indoor',
            space_name: r.space_name || `空間 ${idx + 1}`,
            model: r.best_match_model || 'FXDQ20PDNVT',
            cap_index: getCapIndexFromModel(r.best_match_model),
            cap_kw: r.cap_kw || 2.2,
            qty: r.unit_count || 1
          }));
          nextTrees[sys.id] = initialItems;
        }
      });
      if (onSavePipingTree) {
        onSavePipingTree(nextTrees);
      }
      return nextTrees;
    });

    if (systems.length > 0 && (!selectedSysId || !systems.some(s => s.id === selectedSysId))) {
      setSelectedSysId(systems[0].id);
    }
  }, [rows, vrvOutdoorGroups]);

  // 當前選取系統資訊
  const currentSysInfo = useMemo(() => {
    const matched = vrvOutdoorGroups.find(g => g.id === selectedSysId);
    if (matched) return matched;
    return {
      id: selectedSysId,
      name: 'VRV 系統 1',
      outdoor_model: 'RXYQ8AYLT',
      outdoor_cap_kw: 22.4,
      outdoor_count: 1,
      system_type: 'VRV'
    };
  }, [vrvOutdoorGroups, selectedSysId]);

  // 當前系統的樹狀拓撲清單
  const currentItems = systemTrees[selectedSysId] || [];

  // 更新當前系統的樹
  const updateCurrentTree = (newItems) => {
    setSystemTrees(prev => {
      const next = {
        ...prev,
        [selectedSysId]: newItems
      };
      if (onSavePipingTree) {
        onSavePipingTree(next);
      }
      return next;
    });
  };

  // ---------------------------------------------------------
  // 操作：新增次分歧群組 (Sub-Branch)
  // ---------------------------------------------------------
  const handleAddSubBranch = () => {
    const newBranchId = `branch-${Date.now()}`;
    const newBranch = {
      id: newBranchId,
      type: 'sub_branch',
      name: '次分歧網絡 (Sub-Branch)',
      children: []
    };
    updateCurrentTree([...currentItems, newBranch]);
    toast.success("✅ 已建立新的「次分歧網絡 (Sub-Branch)」，可將室內機拖曳移入！");
  };

  // ---------------------------------------------------------
  // 操作：在次分歧群組內增加室內機
  // ---------------------------------------------------------
  const handleAddIndoorToBranch = (branchId) => {
    const newIndoor = {
      id: `indoor-${Date.now()}`,
      type: 'indoor',
      space_name: '新室內機',
      model: 'FXDQ20PDNVT',
      cap_index: 20.0,
      cap_kw: 2.2,
      qty: 1
    };
    const nextItems = currentItems.map(item => {
      if (item.id === branchId && item.type === 'sub_branch') {
        return { ...item, children: [...item.children, newIndoor] };
      }
      return item;
    });
    updateCurrentTree(nextItems);
  };

  // ---------------------------------------------------------
  // 操作：在主幹新增室內機
  // ---------------------------------------------------------
  const handleAddIndoorToMain = () => {
    const newIndoor = {
      id: `indoor-${Date.now()}`,
      type: 'indoor',
      space_name: `室內機 ${currentItems.length + 1}`,
      model: 'FXDQ20PDNVT',
      cap_index: 20.0,
      cap_kw: 2.2,
      qty: 1
    };
    updateCurrentTree([...currentItems, newIndoor]);
  };

  // ---------------------------------------------------------
  // 操作：刪除次分歧群組 (將裡面的室內機釋回主幹)
  // ---------------------------------------------------------
  const handleDeleteSubBranch = (branchId) => {
    const branch = currentItems.find(i => i.id === branchId);
    if (!branch) return;
    const releasedChildren = branch.children || [];
    const nextItems = [];
    currentItems.forEach(item => {
      if (item.id === branchId) {
        nextItems.push(...releasedChildren);
      } else {
        nextItems.push(item);
      }
    });
    updateCurrentTree(nextItems);
    toast.info("已解散該次分歧網絡，所屬室內機已自動釋回主幹階層！");
  };

  // ---------------------------------------------------------
  // 操作：刪除單台室內機
  // ---------------------------------------------------------
  const handleDeleteIndoor = (indoorId, fromBranchId = null) => {
    if (fromBranchId) {
      const nextItems = currentItems.map(item => {
        if (item.id === fromBranchId) {
          return { ...item, children: item.children.filter(c => c.id !== indoorId) };
        }
        return item;
      });
      updateCurrentTree(nextItems);
    } else {
      updateCurrentTree(currentItems.filter(i => i.id !== indoorId));
    }
  };

  // ---------------------------------------------------------
  // 操作：變更室內機型號
  // ---------------------------------------------------------
  const handleChangeIndoorModel = (indoorId, newModel, fromBranchId = null) => {
    const newIndex = getCapIndexFromModel(newModel);
    if (fromBranchId) {
      const nextItems = currentItems.map(item => {
        if (item.id === fromBranchId) {
          return {
            ...item,
            children: item.children.map(c => c.id === indoorId ? { ...c, model: newModel, cap_index: newIndex } : c)
          };
        }
        return item;
      });
      updateCurrentTree(nextItems);
    } else {
      const nextItems = currentItems.map(item => item.id === indoorId ? { ...item, model: newModel, cap_index: newIndex } : item);
      updateCurrentTree(nextItems);
    }
  };

  // ---------------------------------------------------------
  // 拖曳處理：支援移入次分歧、移出次分歧、排序
  // ---------------------------------------------------------
  const handleDragStart = (e, item, fromBranchId = null) => {
    setDraggedItem({ item, fromBranchId });
    e.dataTransfer.setData('text/plain', item.id);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDropIntoBranch = (e, targetBranchId) => {
    e.preventDefault();
    e.stopPropagation();
    if (!draggedItem) return;
    const { item, fromBranchId } = draggedItem;
    if (item.type !== 'indoor') return; // 僅支援拖曳室內機
    if (fromBranchId === targetBranchId) return; // 留在同一個群組

    // 從原本位置移除
    let filteredTree = currentItems.map(it => {
      if (it.id === fromBranchId) {
        return { ...it, children: it.children.filter(c => c.id !== item.id) };
      }
      return it;
    }).filter(it => it.id !== item.id);

    // 加入目標次分歧網絡
    filteredTree = filteredTree.map(it => {
      if (it.id === targetBranchId) {
        return { ...it, children: [...it.children, item] };
      }
      return it;
    });

    updateCurrentTree(filteredTree);
    setDraggedItem(null);
    toast.success(`↪️ 已將【${item.space_name || item.model}】移入次分歧網絡！`);
  };

  const handleDropIntoMain = (e) => {
    e.preventDefault();
    if (!draggedItem) return;
    const { item, fromBranchId } = draggedItem;
    if (!fromBranchId) return; // 本來就在主幹

    // 從原次分歧移除
    const nextTree = currentItems.map(it => {
      if (it.id === fromBranchId) {
        return { ...it, children: it.children.filter(c => c.id !== item.id) };
      }
      return it;
    });
    // 加入主幹最末
    nextTree.push(item);
    updateCurrentTree(nextTree);
    setDraggedItem(null);
    toast.info(`↩️ 已將【${item.space_name || item.model}】移回主幹第一階層！`);
  };

  // ---------------------------------------------------------
  // 拓撲樹能力與管徑試算 (向下自底向上遞迴)
  // ---------------------------------------------------------
  const topologyCalculations = useMemo(() => {
    // 主機主幹
    const outdoorModel = currentSysInfo.outdoor_model || 'RXYQ8AYLT';
    const mainPipe = getMainPipeSize(outdoorModel);
    const outdoorHp = getOutdoorHpFromModel(outdoorModel);

    // 計算每個節點的下游能力指數總和 X
    // currentItems: [ {type: 'indoor', ...}, {type: 'sub_branch', children: [...]} ]
    const branchCalculations = [];
    let runningTotalX = 0;

    // 我們自底向上/自後往前計算每一段次幹管的下游總能力
    const totalCount = currentItems.length;
    const downstreamSums = new Array(totalCount).fill(0);

    for (let i = totalCount - 1; i >= 0; i--) {
      const it = currentItems[i];
      let nodeCap = 0;
      if (it.type === 'indoor') {
        nodeCap = (it.cap_index || 20.0) * (it.qty || 1);
      } else if (it.type === 'sub_branch') {
        nodeCap = (it.children || []).reduce((acc, c) => acc + ((c.cap_index || 20.0) * (c.qty || 1)), 0);
      }
      runningTotalX += nodeCap;
      downstreamSums[i] = runningTotalX;
    }

    // 依序建立每個節點的配管與分歧規格
    for (let i = 0; i < totalCount; i++) {
      const it = currentItems[i];
      const downstreamX = downstreamSums[i];
      const pipeToNext = i < totalCount - 1 ? getSubPipeSize(downstreamSums[i + 1]) : null;

      const mainJoint = getJointModel(downstreamX);

      if (it.type === 'indoor') {
        const branchPipe = getIndoorBranchPipeSize(it.cap_index);
        branchCalculations.push({
          type: 'indoor',
          data: it,
          downstreamX,
          mainJoint,
          branchPipe,
          pipeToNext
        });
      } else if (it.type === 'sub_branch') {
        // 次分歧頭選型：依該次分歧內所有室內機能力指數加總
        const subBranchTotalX = (it.children || []).reduce((acc, c) => acc + ((c.cap_index || 20.0) * (c.qty || 1)), 0);
        const joint = getJointModel(subBranchTotalX);
        const pipeToBranch = getSubPipeSize(subBranchTotalX);

        // 子室內機末端管徑
        const childrenPipes = (it.children || []).map(child => ({
          child,
          branchPipe: getIndoorBranchPipeSize(child.cap_index)
        }));

        branchCalculations.push({
          type: 'sub_branch',
          data: it,
          downstreamX,
          mainJoint,
          subBranchTotalX,
          joint,
          pipeToBranch,
          childrenPipes,
          pipeToNext
        });
      }
    }

    return {
      outdoorModel,
      outdoorHp,
      mainPipe,
      totalCapacityIndex: runningTotalX,
      branches: branchCalculations
    };
  }, [currentItems, currentSysInfo]);

  // 🎯 自動擷取 SVG 圖像為 PNG Base64DataURL 傳給父組件，確保 Excel 內嵌圖與 UI 介面 100% 同步
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!svgRef.current) return;
      try {
        const svgElement = svgRef.current;
        const svgString = new XMLSerializer().serializeToString(svgElement);
        const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
        const URL = window.URL || window.webkitURL || window;
        const blobURL = URL.createObjectURL(svgBlob);

        const image = new Image();
        image.onload = () => {
          const canvas = document.createElement('canvas');
          const attrW = parseInt(svgElement.getAttribute('width')) || 720;
          const attrH = parseInt(svgElement.getAttribute('height')) || 540;
          const w = svgElement.clientWidth || attrW;
          const h = svgElement.clientHeight || attrH;
          canvas.width = w;
          canvas.height = h;
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = '#020617';
          ctx.fillRect(0, 0, w, h);
          ctx.drawImage(image, 0, 0, w, h);
          const pngDataUrl = canvas.toDataURL('image/png');
          URL.revokeObjectURL(blobURL);
          if (onSavePipingDiagramImage) {
            if (selectedSysId) onSavePipingDiagramImage(selectedSysId, pngDataUrl);
            onSavePipingDiagramImage('sys-default', pngDataUrl);
          }
        };
        image.src = blobURL;
      } catch (err) {
        console.warn('Svg capture failed:', err);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [topologyCalculations, currentItems, selectedSysId, onSavePipingDiagramImage]);

  // 可選室內機型號清單
  const indoorModelOptions = [
    { label: 'VRV 20 型 (2.2kW)', value: 'FXDQ20PDNVT' },
    { label: 'VRV 25 型 (2.8kW)', value: 'FXDQ25PDNVT' },
    { label: 'VRV 32 型 (3.6kW)', value: 'FXDQ32PDNVT' },
    { label: 'VRV 40 型 (4.5kW)', value: 'FXDQ40PDNVT' },
    { label: 'VRV 50 型 (5.6kW)', value: 'FXDQ50NDNVT' },
    { label: 'VRV 63 型 (7.1kW)', value: 'FXDQ63NDNVT' },
    { label: 'VRV 80 型 (9.0kW)', value: 'FXMQ80PVMT' },
    { label: 'VRV 100 型 (11.2kW)', value: 'FXMQ100PVMT' },
    { label: 'VRV 125 型 (14.0kW)', value: 'FXMQ125PVMT' },
    { label: 'VRV 140 型 (16.0kW)', value: 'FXMQ140PVMT' }
  ];

  // ---------------------------------------------------------
  // 操作：調整上下順序
  // ---------------------------------------------------------
  const handleMoveItem = (index, direction, parentBranchId = null) => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (!parentBranchId) {
      if (targetIndex < 0 || targetIndex >= currentItems.length) return;
      const nextItems = [...currentItems];
      const temp = nextItems[index];
      nextItems[index] = nextItems[targetIndex];
      nextItems[targetIndex] = temp;
      updateCurrentTree(nextItems);
    } else {
      const nextItems = currentItems.map(item => {
        if (item.id === parentBranchId && item.type === 'sub_branch') {
          const children = [...item.children];
          if (targetIndex < 0 || targetIndex >= children.length) return item;
          const temp = children[index];
          children[index] = children[targetIndex];
          children[targetIndex] = temp;
          return { ...item, children };
        }
        return item;
      });
      updateCurrentTree(nextItems);
    }
  };

  // ---------------------------------------------------------
  // 操作：新增次分歧群組 (Sub-Branch) 於指定空間位置後
  // ---------------------------------------------------------
  const handleAddSubBranchAt = (insertIndex) => {
    const newBranchId = `branch-${Date.now()}`;
    const newBranch = {
      id: newBranchId,
      type: 'sub_branch',
      name: '次分歧網絡 (Sub-Branch)',
      children: []
    };
    const nextItems = [...currentItems];
    nextItems.splice(insertIndex + 1, 0, newBranch);
    updateCurrentTree(nextItems);
    toast.success("✅ 已在該空間位置新增「次分歧網絡」，可拖曳或新增室內機！");
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(360px, 1fr) minmax(500px, 1.8fr)', gap: '16px', minHeight: '620px', animation: 'fadeIn 0.2s ease-in-out' }}>
      
      {/* ---------------- 左側：階層與網絡編輯控制面版 ---------------- */}
      <div style={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '10px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        
        {/* 系統切換與說明 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #1e293b', paddingBottom: '10px' }}>
          <div>
            <span style={{ fontSize: '15px', fontWeight: 'bold', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>📐 冷媒系統流程圖編輯</span>
            </span>
            <div style={{ fontSize: '11.5px', color: '#94a3b8', marginTop: '2px' }}>
              可拖曳卡片移動室內機階層，或使用上下按鈕調整順序
            </div>
          </div>

          {vrvOutdoorGroups.length > 1 && (
            <select
              value={selectedSysId}
              onChange={(e) => setSelectedSysId(e.target.value)}
              style={{ backgroundColor: '#1e293b', color: '#38bdf8', border: '1px solid #38bdf8', borderRadius: '6px', padding: '4px 8px', fontSize: '12px', fontWeight: 'bold' }}
            >
              {vrvOutdoorGroups.map((g, idx) => (
                <option key={g.id || idx} value={g.id}>{g.name || `VRV 系統 ${idx + 1}`}</option>
              ))}
            </select>
          )}
        </div>

        {/* 提示資訊 */}
        <div style={{ backgroundColor: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: '6px', padding: '8px 10px', fontSize: '12px', color: '#cbd5e1', lineHeight: '1.4' }}>
          💡 <strong>操作說明：</strong><br />
          • <strong>主幹直連內機</strong>：位於最外層卡片清單中，可按 ⬆️ ⬇️ 調整順序。<br />
          • <strong>次分歧網絡</strong>：可在各空間內直接點擊「+次分歧群組」建立並拖曳/移入室內機。
        </div>

        {/* 樹狀結構拖曳與排序清單 */}
        <div
          onDragOver={handleDragOver}
          onDrop={handleDropIntoMain}
          style={{
            flex: 1,
            overflowY: 'auto',
            maxHeight: '560px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            padding: '4px'
          }}
        >
          {currentItems.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 10px', color: '#64748b', fontSize: '13px' }}>
              此系統目前無室內機。
            </div>
          ) : (
            currentItems.map((item, index) => {
              // 1. 第一階層室內機卡片
              if (item.type === 'indoor') {
                return (
                  <div
                    key={item.id}
                    draggable={true}
                    onDragStart={(e) => handleDragStart(e, item, null)}
                    style={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #475569',
                      borderRadius: '8px',
                      padding: '10px 12px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      cursor: 'grab',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
                        <span style={{ color: '#38bdf8', fontWeight: 'bold', fontSize: '14px', width: '22px' }}>
                          {index + 1}
                        </span>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1 }}>
                          <span style={{ fontSize: '12px', color: '#f8fafc', fontWeight: 'bold' }}>{item.space_name}</span>
                          <select
                            value={item.model}
                            onChange={(e) => handleChangeIndoorModel(item.id, e.target.value, null)}
                            style={{
                              backgroundColor: '#0f172a',
                              color: '#34d399',
                              border: '1px solid #334155',
                              borderRadius: '4px',
                              padding: '4px 6px',
                              fontSize: '13px',
                              fontWeight: 'bold',
                              width: '100%',
                              maxWidth: '180px'
                            }}
                          >
                            {indoorModelOptions.map(opt => (
                              <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '11px', color: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.15)', padding: '2px 6px', borderRadius: '4px', border: '1px solid #f59e0b', whiteSpace: 'nowrap' }}>
                          {item.cap_index} 型
                        </span>

                        {/* 上下排序按鈕 */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <button
                            type="button"
                            disabled={index === 0}
                            onClick={(e) => { e.stopPropagation(); handleMoveItem(index, 'up', null); }}
                            style={{
                              backgroundColor: index === 0 ? '#334155' : '#0284c7',
                              border: 'none',
                              color: '#ffffff',
                              borderRadius: '3px',
                              padding: '1px 6px',
                              fontSize: '10px',
                              cursor: index === 0 ? 'not-allowed' : 'pointer',
                              opacity: index === 0 ? 0.4 : 1
                            }}
                            title="向上調整順序"
                          >
                            ▲
                          </button>
                          <button
                            type="button"
                            disabled={index === currentItems.length - 1}
                            onClick={(e) => { e.stopPropagation(); handleMoveItem(index, 'down', null); }}
                            style={{
                              backgroundColor: index === currentItems.length - 1 ? '#334155' : '#0284c7',
                              border: 'none',
                              color: '#ffffff',
                              borderRadius: '3px',
                              padding: '1px 6px',
                              fontSize: '10px',
                              cursor: index === currentItems.length - 1 ? 'not-allowed' : 'pointer',
                              opacity: index === currentItems.length - 1 ? 0.4 : 1
                            }}
                            title="向下調整順序"
                          >
                            ▼
                          </button>
                        </div>

                        <button
                          type="button"
                          onClick={() => handleDeleteIndoor(item.id, null)}
                          style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', color: '#f87171', borderRadius: '4px', padding: '4px 8px', cursor: 'pointer', fontSize: '12px' }}
                          title="移除此室內機"
                        >
                          🗑️
                        </button>
                      </div>
                    </div>

                    {/* 直接加在各空間內的「+ 次分歧群組」按鈕 */}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '4px', borderTop: '1px stroke #334155' }}>
                      <button
                        type="button"
                        onClick={() => handleAddSubBranchAt(index)}
                        style={{
                          backgroundColor: 'rgba(245, 158, 11, 0.15)',
                          border: '1px solid #f59e0b',
                          color: '#fbbf24',
                          borderRadius: '4px',
                          padding: '3px 8px',
                          fontSize: '11px',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                      >
                        ＋ 次分歧群組
                      </button>
                    </div>
                  </div>
                );
              }

              // 2. 第二階層：次分歧網絡 (Sub-Branch)
              if (item.type === 'sub_branch') {
                const subX = (item.children || []).reduce((acc, c) => acc + ((c.cap_index || 20.0) * (c.qty || 1)), 0);
                const subJoint = getJointModel(subX);

                return (
                  <div
                    key={item.id}
                    onDragOver={handleDragOver}
                    onDrop={(e) => handleDropIntoBranch(e, item.id)}
                    style={{
                      backgroundColor: 'rgba(14, 165, 233, 0.06)',
                      border: '1.5px solid #0284c7',
                      borderRadius: '8px',
                      padding: '10px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px'
                    }}
                  >
                    {/* 次分歧標題列 */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 'bold', fontSize: '13px', color: '#38bdf8' }}>
                          次分歧網絡 (Sub-Branch)
                        </span>
                        <span style={{ fontSize: '10.5px', color: '#ec4899', backgroundColor: 'rgba(236, 72, 153, 0.15)', padding: '2px 6px', borderRadius: '4px', border: '1px solid #ec4899', fontWeight: 'bold' }}>
                          分歧頭: {subJoint.short} ({subJoint.model})
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {/* 上下排序按鈕 */}
                        <button
                          type="button"
                          disabled={index === 0}
                          onClick={(e) => { e.stopPropagation(); handleMoveItem(index, 'up', null); }}
                          style={{
                            backgroundColor: index === 0 ? '#334155' : '#0284c7',
                            border: 'none',
                            color: '#ffffff',
                            borderRadius: '3px',
                            padding: '2px 6px',
                            fontSize: '10px',
                            cursor: index === 0 ? 'not-allowed' : 'pointer',
                            opacity: index === 0 ? 0.4 : 1
                          }}
                          title="向上調整次分歧順序"
                        >
                          ▲
                        </button>
                        <button
                          type="button"
                          disabled={index === currentItems.length - 1}
                          onClick={(e) => { e.stopPropagation(); handleMoveItem(index, 'down', null); }}
                          style={{
                            backgroundColor: index === currentItems.length - 1 ? '#334155' : '#0284c7',
                            border: 'none',
                            color: '#ffffff',
                            borderRadius: '3px',
                            padding: '2px 6px',
                            fontSize: '10px',
                            cursor: index === currentItems.length - 1 ? 'not-allowed' : 'pointer',
                            opacity: index === currentItems.length - 1 ? 0.4 : 1
                          }}
                          title="向下調整次分歧順序"
                        >
                          ▼
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDeleteSubBranch(item.id)}
                          style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', color: '#f87171', borderRadius: '4px', padding: '2px 6px', cursor: 'pointer', fontSize: '11px' }}
                          title="解散此分歧並將室內機釋回主幹"
                        >
                          🗑️ 刪除分歧
                        </button>
                      </div>
                    </div>

                    {/* 次分歧內的室內機列表 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', minHeight: '40px', padding: '4px', backgroundColor: 'rgba(15, 23, 42, 0.6)', borderRadius: '6px' }}>
                      {(item.children || []).length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '12px', color: '#64748b', fontSize: '12px', border: '1px dashed #334155', borderRadius: '4px' }}>
                          ⬇️ 請將上方室內機卡片「拖曳至此處」以加入次分歧
                        </div>
                      ) : (
                        item.children.map((child, cIdx) => (
                          <div
                            key={child.id}
                            draggable={true}
                            onDragStart={(e) => handleDragStart(e, child, item.id)}
                            style={{
                              backgroundColor: '#1e293b',
                              border: '1px solid #334155',
                              borderRadius: '6px',
                              padding: '6px 10px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              gap: '6px',
                              cursor: 'grab'
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1 }}>
                              <span style={{ color: '#a855f7', fontWeight: 'bold', fontSize: '12px' }}>
                                ↳ {cIdx + 1}
                              </span>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', flex: 1 }}>
                                <span style={{ fontSize: '11px', color: '#f8fafc', fontWeight: 'bold' }}>{child.space_name}</span>
                                <select
                                  value={child.model}
                                  onChange={(e) => handleChangeIndoorModel(child.id, e.target.value, item.id)}
                                  style={{
                                    backgroundColor: '#0f172a',
                                    color: '#34d399',
                                    border: '1px solid #334155',
                                    borderRadius: '4px',
                                    padding: '2px 4px',
                                    fontSize: '12px',
                                    fontWeight: 'bold',
                                    maxWidth: '160px'
                                  }}
                                >
                                  {indoorModelOptions.map(opt => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                  ))}
                                </select>
                              </div>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <span style={{ fontSize: '10px', color: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.15)', padding: '1px 5px', borderRadius: '3px', border: '1px solid #f59e0b' }}>
                                {child.cap_index} 型
                              </span>

                              {/* 子樹順序按鈕 */}
                              <button
                                type="button"
                                disabled={cIdx === 0}
                                onClick={(e) => { e.stopPropagation(); handleMoveItem(cIdx, 'up', item.id); }}
                                style={{
                                  backgroundColor: cIdx === 0 ? '#334155' : '#6b21a8',
                                  border: 'none',
                                  color: '#ffffff',
                                  borderRadius: '2px',
                                  padding: '1px 4px',
                                  fontSize: '9px',
                                  cursor: cIdx === 0 ? 'not-allowed' : 'pointer',
                                  opacity: cIdx === 0 ? 0.4 : 1
                                }}
                                title="向上調整順序"
                              >
                                ▲
                              </button>
                              <button
                                type="button"
                                disabled={cIdx === (item.children || []).length - 1}
                                onClick={(e) => { e.stopPropagation(); handleMoveItem(cIdx, 'down', item.id); }}
                                style={{
                                  backgroundColor: cIdx === (item.children || []).length - 1 ? '#334155' : '#6b21a8',
                                  border: 'none',
                                  color: '#ffffff',
                                  borderRadius: '2px',
                                  padding: '1px 4px',
                                  fontSize: '9px',
                                  cursor: cIdx === (item.children || []).length - 1 ? 'not-allowed' : 'pointer',
                                  opacity: cIdx === (item.children || []).length - 1 ? 0.4 : 1
                                }}
                                title="向下調整順序"
                              >
                                ▼
                              </button>

                              <button
                                type="button"
                                onClick={() => handleDeleteIndoor(child.id, item.id)}
                                style={{ backgroundColor: 'transparent', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: '12px' }}
                                title="移除"
                              >
                                ✕
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>

                    {/* 次分歧底部按鈕 */}
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        type="button"
                        onClick={() => handleAddIndoorToBranch(item.id)}
                        style={{
                          flex: 1,
                          backgroundColor: '#0f172a',
                          border: '1px dashed #38bdf8',
                          color: '#38bdf8',
                          borderRadius: '4px',
                          padding: '5px',
                          fontSize: '11.5px',
                          fontWeight: 'bold',
                          cursor: 'pointer'
                        }}
                      >
                        ＋ 加內機
                      </button>
                    </div>
                  </div>
                );
              }

              return null;
            })
          )}
        </div>
      </div>

      {/* ---------------- 右側：即時 SVG 冷媒管拓撲流程圖 ---------------- */}
      <div style={{ backgroundColor: '#020617', border: '1px solid #334155', borderRadius: '10px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px', overflowX: 'auto' }}>
        
        {/* 頂部標題、總計與「編輯完成」按鈕 (未確認為藍底，確認後變綠底) */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #1e293b', paddingBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '15px', fontWeight: 'bold', color: '#38bdf8' }}>
              📊 冷媒系統流程示意圖
            </span>
            <span style={{ fontSize: '11px', color: '#94a3b8', backgroundColor: '#0f172a', padding: '3px 8px', borderRadius: '4px', border: '1px solid #334155' }}>
              總能力指數: <strong style={{ color: '#34d399' }}>{topologyCalculations.totalCapacityIndex}</strong>
            </span>
            <span style={{ fontSize: '11.5px', color: '#cbd5e1' }}>
              主幹管徑：<strong style={{ color: '#f97316' }}>{topologyCalculations.mainPipe.text}</strong>
            </span>
          </div>

          <button
            type="button"
            onClick={() => {
              setIsDiagramConfirmed(prev => !prev);
              if (!isDiagramConfirmed) {
                toast.success("✅ 冷媒流程圖已編輯完成並確認套用！");
              } else {
                toast.info("ℹ️ 已取消確認狀態，可重新進行圖面編輯。");
              }
            }}
            style={{
              backgroundColor: isDiagramConfirmed ? '#10b981' : '#0284c7',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              padding: '6px 16px',
              fontSize: '13px',
              fontWeight: 'bold',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: isDiagramConfirmed ? '0 2px 6px rgba(16, 185, 129, 0.4)' : '0 2px 6px rgba(2, 132, 199, 0.4)',
              transition: 'all 0.2s ease'
            }}
          >
            {isDiagramConfirmed ? '✓ 編輯完成' : '編輯完成'}
          </button>
        </div>

        {/* SVG 圖表繪製區 (適度緊湊版面，全覽無裁切) */}
        <div style={{ flex: 1, minHeight: '520px', overflowY: 'auto', overflowX: 'auto', padding: '10px', display: 'flex', justifyContent: 'flex-start' }}>
          {(() => {
            const rowHeight = 75;
            let totalVisualRows = 0;
            topologyCalculations.branches.forEach(b => {
              if (b.type === 'indoor') {
                totalVisualRows += 1;
              } else if (b.type === 'sub_branch') {
                totalVisualRows += Math.max(1, (b.data.children || []).length);
              }
            });

            const svgHeight = Math.max(540, totalVisualRows * rowHeight + 120);
            const svgWidth = 720;

            const mainStartX = 90;
            const mainStartY = 90;

            let currentY = mainStartY + 25;

            return (
              <svg ref={svgRef} width={svgWidth} height={svgHeight} style={{ fontFamily: 'sans-serif', userSelect: 'none' }}>
                <defs>
                  <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
                    <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.5" />
                  </filter>
                </defs>

                {/* 1. 左上角室外機卡片 (呈現完整室外機型號如 RSUYQ125AVET) */}
                <g transform={`translate(${mainStartX - 55}, 12)`}>
                  <rect
                    width="140"
                    height="54"
                    rx="6"
                    fill="#0284c7"
                    stroke="#38bdf8"
                    strokeWidth="1.5"
                    filter="url(#shadow)"
                  />
                  {(() => {
                    const m = (topologyCalculations.outdoorModel || '').toUpperCase();
                    const isHideHp = /RSUYQ(112|125|140|160)/.test(m);
                    const titleText = isHideHp ? "主機" : `主機 (${topologyCalculations.outdoorHp} HP)`;
                    return (
                      <text x="70" y="22" fill="#ffffff" fontSize="12" fontWeight="bold" textAnchor="middle">
                        {titleText}
                      </text>
                    );
                  })()}
                  <text x="70" y="41" fill="#e0f2fe" fontSize="11" fontWeight="bold" textAnchor="middle">
                    {topologyCalculations.outdoorModel}
                  </text>
                </g>

                {/* 2. 主幹管第一段 (室外機出發) */}
                <line
                  x1={mainStartX}
                  y1={66}
                  x2={mainStartX}
                  y2={currentY}
                  stroke="#0284c7"
                  strokeWidth="3.5"
                />

                {/* 主幹管管徑標籤 (橘色文字，完全避開室外機卡片) */}
                <g transform={`translate(${mainStartX + 14}, 82)`}>
                  <rect x="-4" y="-11" width="105" height="20" rx="4" fill="#0f172a" stroke="#f97316" strokeWidth="1" />
                  <text x="48" y="3" fill="#f97316" fontSize="11" fontWeight="bold" textAnchor="middle">
                    {topologyCalculations.mainPipe.text}
                  </text>
                </g>

                {/* 3. 遍歷渲染各分支節點 */}
                {topologyCalculations.branches.map((b, bIdx) => {
                  const nodeY = currentY;
                  const mainJoint = b.mainJoint || getJointModel(b.downstreamX || 20);

                  // ---------------- 分支 A: 單台室內機 ----------------
                  if (b.type === 'indoor') {
                    const indoorEndLineX = mainStartX + 170;
                    currentY += rowHeight;

                    return (
                      <g key={bIdx}>
                        {/* 主幹垂直段 */}
                        {bIdx < topologyCalculations.branches.length - 1 && (
                          <line
                            x1={mainStartX}
                            y1={nodeY}
                            x2={mainStartX}
                            y2={currentY}
                            stroke="#0284c7"
                            strokeWidth="3"
                          />
                        )}

                        {/* 次幹管徑標籤 (橘色文字) */}
                        {b.pipeToNext && (
                          <g transform={`translate(${mainStartX + 12}, ${nodeY + 34})`}>
                            <rect x="-4" y="-11" width="95" height="18" rx="3" fill="#0f172a" stroke="#fb923c" strokeWidth="0.8" />
                            <text x="43" y="2" fill="#f97316" fontSize="10" fontWeight="bold" textAnchor="middle">
                              {b.pipeToNext.text}
                            </text>
                          </g>
                        )}

                        {/* 主幹分歧點型號徽章 (最後一台/分支不需要分歧頭) */}
                        {bIdx < topologyCalculations.branches.length - 1 && (
                          <g transform={`translate(${mainStartX - 42}, ${nodeY - 12})`}>
                            <rect x="0" y="0" width="38" height="24" rx="5" fill="#0f172a" stroke="#f43f5e" strokeWidth="1.5" />
                            <text x="19" y="16" fill="#f43f5e" fontSize="11" fontWeight="bold" textAnchor="middle">
                              {mainJoint.short}
                            </text>
                          </g>
                        )}

                        {/* 水平分支管線 */}
                        <line
                          x1={mainStartX}
                          y1={nodeY}
                          x2={indoorEndLineX}
                          y2={nodeY}
                          stroke="#0284c7"
                          strokeWidth="2.5"
                        />

                        {/* 末端管徑標籤 (橘色) */}
                        <g transform={`translate(${mainStartX + 55}, ${nodeY - 8})`}>
                          <text x="0" y="0" fill="#f97316" fontSize="11" fontWeight="bold">
                            {b.branchPipe.text}
                          </text>
                        </g>

                        {/* 室內機卡片 (字體大小皆為 12px) */}
                        <g transform={`translate(${indoorEndLineX}, ${nodeY - 20})`}>
                          <rect
                            width="140"
                            height="40"
                            rx="5"
                            fill="#0f172a"
                            stroke="#0284c7"
                            strokeWidth="1.5"
                          />
                          <text x="70" y="16" fill="#38bdf8" fontSize="12" fontWeight="bold" textAnchor="middle">
                            VRV {b.data.cap_index} 型
                          </text>
                          <text x="70" y="32" fill="#f8fafc" fontSize="12" fontWeight="bold" textAnchor="middle">
                            {b.data.space_name}
                          </text>
                        </g>
                      </g>
                    );
                  }

                  // ---------------- 分支 B: 次分歧網絡 (Sub-Branch) ----------------
                  if (b.type === 'sub_branch') {
                    const jointBadgeX = mainStartX + 120;
                    const subTreeStartX = jointBadgeX + 45;
                    const children = b.childrenPipes || [];
                    const subSpan = Math.max(1, children.length);

                    const subStartY = nodeY;
                    const subEndY = nodeY + (subSpan - 1) * rowHeight;
                    currentY += subSpan * rowHeight;

                    return (
                      <g key={bIdx}>
                        {/* 主幹垂直段 */}
                        {bIdx < topologyCalculations.branches.length - 1 && (
                          <line
                            x1={mainStartX}
                            y1={nodeY}
                            x2={mainStartX}
                            y2={currentY}
                            stroke="#0284c7"
                            strokeWidth="3"
                          />
                        )}

                        {/* 次幹管徑標籤 (橘色) */}
                        {b.pipeToNext && (
                          <g transform={`translate(${mainStartX + 12}, ${nodeY + 34})`}>
                            <rect x="-4" y="-11" width="95" height="18" rx="3" fill="#0f172a" stroke="#fb923c" strokeWidth="0.8" />
                            <text x="43" y="2" fill="#f97316" fontSize="10" fontWeight="bold" textAnchor="middle">
                              {b.pipeToNext.text}
                            </text>
                          </g>
                        )}

                        {/* 主幹分歧頭標籤 (粉紅徽章，最後一台/分支不需要分歧頭) */}
                        {bIdx < topologyCalculations.branches.length - 1 && (
                          <g transform={`translate(${mainStartX - 42}, ${nodeY - 12})`}>
                            <rect x="0" y="0" width="38" height="24" rx="5" fill="#0f172a" stroke="#f43f5e" strokeWidth="1.5" />
                            <text x="19" y="16" fill="#f43f5e" fontSize="11" fontWeight="bold" textAnchor="middle">
                              {mainJoint.short}
                            </text>
                          </g>
                        )}

                        {/* 水平引線 */}
                        <line
                          x1={mainStartX}
                          y1={nodeY}
                          x2={jointBadgeX}
                          y2={nodeY}
                          stroke="#0284c7"
                          strokeWidth="2.5"
                        />

                        {/* 引線管徑標籤 (橘色) */}
                        <g transform={`translate(${mainStartX + 20}, ${nodeY - 8})`}>
                          <text x="0" y="0" fill="#f97316" fontSize="10" fontWeight="bold">
                            {b.pipeToBranch.text}
                          </text>
                        </g>

                        {/* 次分歧頭徽章 (粉紅 22T, 33T) */}
                        <g transform={`translate(${jointBadgeX}, ${nodeY - 14})`}>
                          <rect
                            width="38"
                            height="28"
                            rx="5"
                            fill="#0f172a"
                            stroke="#ec4899"
                            strokeWidth="1.5"
                          />
                          <text x="19" y="18" fill="#ec4899" fontSize="11" fontWeight="bold" textAnchor="middle">
                            {b.joint.short}
                          </text>
                        </g>

                        {/* 次分歧頭出發的垂直子樹 */}
                        {children.length > 1 && (
                          <line
                            x1={subTreeStartX}
                            y1={subStartY}
                            x2={subTreeStartX}
                            y2={subEndY}
                            stroke="#0284c7"
                            strokeWidth="2.5"
                          />
                        )}

                        {/* 子室內機分支 */}
                        {children.map((cObj, cIdx) => {
                          const childY = subStartY + cIdx * rowHeight;
                          const childCardX = subTreeStartX + 130;

                          return (
                            <g key={cIdx}>
                              {cIdx === 0 && (
                                <line
                                  x1={jointBadgeX + 38}
                                  y1={nodeY}
                                  x2={subTreeStartX}
                                  y2={nodeY}
                                  stroke="#0284c7"
                                  strokeWidth="2.5"
                                />
                              )}

                              <circle cx={subTreeStartX} cy={childY} r="3.5" fill="#f43f5e" />

                              <line
                                x1={subTreeStartX}
                                y1={childY}
                                x2={childCardX}
                                y2={childY}
                                stroke="#0284c7"
                                strokeWidth="2.5"
                              />

                              {/* 子分支管徑 (橘色) */}
                              <g transform={`translate(${subTreeStartX + 25}, ${childY - 8})`}>
                                <text x="0" y="0" fill="#f97316" fontSize="10" fontWeight="bold">
                                  {cObj.branchPipe.text}
                                </text>
                              </g>

                              {/* 子室內機卡片 (字體大小皆為 12px) */}
                              <g transform={`translate(${childCardX}, ${childY - 20})`}>
                                <rect
                                  width="140"
                                  height="40"
                                  rx="5"
                                  fill="#0f172a"
                                  stroke="#a855f7"
                                  strokeWidth="1.5"
                                />
                                <text x="70" y="16" fill="#c084fc" fontSize="12" fontWeight="bold" textAnchor="middle">
                                  VRV {cObj.child.cap_index} 型
                                </text>
                                <text x="70" y="32" fill="#f8fafc" fontSize="12" fontWeight="bold" textAnchor="middle">
                                  {cObj.child.space_name}
                                </text>
                              </g>
                            </g>
                          );
                        })}
                      </g>
                    );
                  }

                  return null;
                })}
              </svg>
            );
          })()}
        </div>
      </div>

    </div>
  );
}
