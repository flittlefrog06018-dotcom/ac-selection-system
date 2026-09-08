"""
Daikin BOM and Pipe Generator (大金設備清點與冷媒管徑/分歧頭拓撲產生器)
合併原設備統計與 D3-NET 計算，以及 VRV 上吹型/側吹型管徑與分歧頭推導運算。
"""
import pandas as pd
import re
import os
import math
import glob
from typing import Dict, List, Any

# ==============================================================================
# 1. 拓撲節點與管徑選用運算引擎 (依據《VRV冷媒管徑選用工具2026.5.xlsx》)
# ==============================================================================
class HVACNode:
    def __init__(self, node_type: str, name: str, capacity: float = 0.0, qty: int = 1, model: str = ""):
        self.node_type = node_type # 'main', 'subgroup', 'bp', 'vrv', 'ra'
        self.name = name
        self.model = model or name
        self.capacity = capacity
        self.qty = qty
        self.children: List['HVACNode'] = []
        self.pipe_liquid = ""
        self.pipe_gas = ""
        self.joint_model = ""

    def add_child(self, child_node: 'HVACNode'):
        self.children.append(child_node)

    def calculate_totals(self) -> float:
        if self.node_type in ['vrv', 'ra']:
            return self.capacity * self.qty
        total = sum(child.calculate_totals() for child in self.children)
        self.capacity = total
        return total


class DaikinHVACCalculator:
    @staticmethod
    def extract_capacity_index(model_str: str, default_kw: float = 0.0) -> float:
        m = re.search(r'(\d+)', str(model_str))
        if m:
            val = float(m.group(1))
            if val in [20, 22, 25, 28, 32, 36, 40, 41, 50, 60, 63, 71, 80, 90, 100, 112, 125, 140, 160, 200, 250, 300]:
                return val
            if val <= 60:
                return val * 25.0
            return val
        if default_kw > 0:
            return round(default_kw * 10.0, 1)
        return 28.0

    @staticmethod
    def extract_outdoor_hp(outdoor_model: str) -> float:
        out_upper = str(outdoor_model).strip().upper()
        m = re.search(r'(?:RXYQ|RXQ|RSUYQ|REYQ|RWEYQ|RXYMQ|RXYCQ)(\d+)', out_upper)
        if m:
            val = float(m.group(1))
            if val in [112, 125, 140, 160]:
                return val
            if val in [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 40, 48, 54, 60]:
                return val
        m_any = re.search(r'(\d+)', out_upper)
        if m_any:
            v = float(m_any.group(1))
            return v if v <= 60 else round(v / 25.0, 1)
        return 8.0

    @staticmethod
    def is_side_discharge(outdoor_model: str) -> bool:
        out_upper = str(outdoor_model).strip().upper()
        return any(k in out_upper for k in ['RSUYQ', 'RXYCQ', 'RXYMQ', 'VRV-S', 'MINI'])

    def get_main_pipe(self, outdoor_model: str, capacity_sum: float) -> Dict[str, str]:
        is_side = self.is_side_discharge(outdoor_model)
        hp = self.extract_outdoor_hp(outdoor_model)

        if is_side:
            if hp <= 125 or hp <= 6:
                return {"l": "Ø9.5", "g": "Ø15.9", "code": "TR2"}
            elif hp <= 200 or hp <= 8:
                return {"l": "Ø9.5", "g": "Ø19.1", "code": "TR3"}
            elif hp <= 250 or hp <= 10:
                return {"l": "Ø9.5", "g": "Ø22.2", "code": "TR4"}
            else:
                return {"l": "Ø12.7", "g": "Ø25.4", "code": "TR5"}
        else:
            if hp <= 8:
                return {"l": "Ø9.5", "g": "Ø19.1", "code": "TR3"}
            elif hp <= 10:
                return {"l": "Ø9.5", "g": "Ø22.2", "code": "TR4"}
            elif hp <= 16:
                return {"l": "Ø12.7", "g": "Ø28.6", "code": "TR5"}
            elif hp <= 22:
                return {"l": "Ø15.9", "g": "Ø28.6", "code": "TR6"}
            elif hp <= 24:
                return {"l": "Ø15.9", "g": "Ø34.9", "code": "TR7"}
            elif hp <= 34:
                return {"l": "Ø19.1", "g": "Ø34.9", "code": "TR8"}
            else:
                return {"l": "Ø19.1", "g": "Ø41.3", "code": "TR9"}

    def get_first_joint(self, outdoor_model: str) -> str:
        is_side = self.is_side_discharge(outdoor_model)
        hp = self.extract_outdoor_hp(outdoor_model)
        if is_side:
            if hp < 200 and hp < 8:
                return "KHRP26A22T"
            elif hp <= 250 or hp <= 10:
                return "KHRP26A33T"
            else:
                return "KHRP26A72T"
        else:
            if hp <= 6:
                return "KHRP26A22T"
            elif hp <= 10:
                return "KHRP26A33T"
            elif hp <= 22:
                return "KHRP26A72T"
            else:
                return "KHRP26A73T+KHRP26M73TP"

    def get_sub_pipe(self, x_capacity: float) -> Dict[str, str]:
        if x_capacity < 150:
            return {"l": "Ø9.5", "g": "Ø15.9", "code": "TR2"}
        elif x_capacity < 200:
            return {"l": "Ø9.5", "g": "Ø19.1", "code": "TR3"}
        elif x_capacity < 290:
            return {"l": "Ø9.5", "g": "Ø22.2", "code": "TR4"}
        elif x_capacity < 420:
            return {"l": "Ø12.7", "g": "Ø28.6", "code": "TR5"}
        elif x_capacity < 640:
            return {"l": "Ø15.9", "g": "Ø28.6", "code": "TR6"}
        elif x_capacity < 920:
            return {"l": "Ø19.1", "g": "Ø34.9", "code": "TR8"}
        else:
            return {"l": "Ø19.1", "g": "Ø41.3", "code": "TR9"}

    def get_joint(self, x_capacity: float) -> str:
        if x_capacity < 200:
            return "KHRP26A22T"
        elif x_capacity < 290:
            return "KHRP26A33T"
        elif x_capacity < 640:
            return "KHRP26A72T"
        else:
            return "KHRP26A73T+KHRP26M73TP"

    def get_indoor_pipe(self, node_type: str, capacity: float) -> Dict[str, str]:
        if node_type == 'ra':
            if capacity <= 36:
                return {"l": "Ø6.4", "g": "Ø9.5"}
            elif capacity <= 71:
                return {"l": "Ø6.4", "g": "Ø12.7"}
            else:
                return {"l": "Ø6.4", "g": "Ø15.9"}
        else:
            if capacity <= 50:
                return {"l": "Ø6.4", "g": "Ø12.7"}
            elif capacity <= 140:
                return {"l": "Ø9.5", "g": "Ø15.9"}
            elif capacity <= 200:
                return {"l": "Ø9.5", "g": "Ø19.1"}
            else:
                return {"l": "Ø9.5", "g": "Ø22.2"}

    def get_bp_pipe(self, capacity: float) -> Dict[str, str]:
        return self.get_sub_pipe(capacity)

    def build_system_with_bp_boxes(self, indoor_nodes: List[HVACNode]) -> List[HVACNode]:
        processed = []
        ra_buffer = []

        def flush_ra():
            nonlocal ra_buffer
            bp_count = 1
            while ra_buffer:
                chunk = ra_buffer[:3]
                del ra_buffer[:3]
                total_qty = sum(c.qty for c in chunk)
                bp = HVACNode('bp', f"BP箱-{bp_count} ({total_qty}台)")
                for ra in chunk:
                    bp.add_child(ra)
                processed.append(bp)
                bp_count += 1

        for node in indoor_nodes:
            if node.node_type == 'ra':
                ra_buffer.append(node)
            else:
                flush_ra()
                processed.append(node)
        flush_ra()
        return processed

    def evaluate_tree(self, node: HVACNode, is_root: bool = True):
        node.calculate_totals()
        if node.node_type in ['vrv', 'ra']:
            pipes = self.get_indoor_pipe(node.node_type, node.capacity)
            node.pipe_liquid, node.pipe_gas = pipes["l"], pipes["g"]
        elif node.node_type == 'bp':
            pipes = self.get_bp_pipe(node.capacity)
            node.pipe_liquid, node.pipe_gas = pipes["l"], pipes["g"]
            node.joint_model = self.get_joint(node.capacity)
            for child in node.children:
                self.evaluate_tree(child, is_root=False)
        elif node.node_type in ['subgroup', 'main']:
            if is_root:
                pipes = self.get_main_pipe(node.model, node.capacity)
                node.joint_model = self.get_first_joint(node.model)
            else:
                pipes = self.get_sub_pipe(node.capacity)
                if node.children:
                    node.joint_model = self.get_joint(node.capacity)
            node.pipe_liquid, node.pipe_gas = pipes["l"], pipes["g"]
            for child in node.children:
                self.evaluate_tree(child, is_root=False)

    def flatten_tree_to_dataframe_rows(self, node: HVACNode, sn: str, prefix: str = "", is_last: bool = True, is_root: bool = True) -> List[Dict[str, Any]]:
        rows = []
        col_struct = f"{sn}_系統結構"
        col_qty = f"{sn}_數量"

        if is_root:
            joint_info = f" | 主分歧: {node.joint_model}" if node.joint_model else ""
            pipe_info = f"主管: {node.pipe_liquid}/{node.pipe_gas}" if node.pipe_liquid else ""
            specs = f" ({pipe_info}{joint_info})" if (pipe_info or joint_info) else ""
            node_label = f"{node.name}{specs}"
            rows.append({col_struct: node_label, col_qty: node.qty})

            for idx, child in enumerate(node.children):
                last_child = (idx == len(node.children) - 1)
                rows.extend(self.flatten_tree_to_dataframe_rows(child, sn, prefix="", is_last=last_child, is_root=False))
        else:
            branch = "    └─ " if is_last else "    ├─ "
            joint_info = f" | 分歧: {node.joint_model}" if node.joint_model else ""
            
            if node.node_type == 'bp':
                pipe_info = f"次幹: {node.pipe_liquid}/{node.pipe_gas}"
                tag = "[BP箱] "
            elif node.node_type == 'ra':
                pipe_info = f"配管: {node.pipe_liquid}/{node.pipe_gas}"
                tag = "[家用] "
            else:
                pipe_info = f"配管: {node.pipe_liquid}/{node.pipe_gas}"
                tag = "[VRV] "

            specs = f" ({pipe_info}{joint_info})"
            node_label = f"{prefix}{branch}{tag}{node.name}{specs}"
            rows.append({col_struct: node_label, col_qty: node.qty})

            new_prefix = prefix + ("        " if is_last else "    │   ")
            for idx, child in enumerate(node.children):
                last_child = (idx == len(node.children) - 1)
                rows.extend(self.flatten_tree_to_dataframe_rows(child, sn, prefix=new_prefix, is_last=last_child, is_root=False))

        return rows


# ==============================================================================
# 2. 工具函數與原始 BOM 萃取邏輯 (完全保留原本格式與權重排序)
# ==============================================================================
def get_cap(s):
    n = re.search(r'(\d+)', str(s))
    return int(n.group(1)) if n else 0

def get_model_series(s):
    m = re.match(r'([a-zA-Z]+)', str(s))
    return m.group(1) if m else ""

def get_sys_weight(name):
    name = str(name).upper()
    if "家用1對1" in name or "[家用]" in name: return 1
    if "家用多聯" in name: return 2
    if "商用" in name: return 3
    if "VRV" in name: return 4
    if "全熱" in name: return 5
    return 6

def get_in_label(mn):
    mn = str(mn).upper()
    if any(k in mn for k in ['FTHF', 'FTXV', 'FTXM', 'FDXV', 'CTXZ', 'CTX']): return "[家用]", 1
    if mn.startswith('FX'): return "[VRV]", 4 
    if any(k in mn for k in ['FBA', 'FCA', 'FFA']): return "[商用]", 3
    if any(k in mn for k in ['VAM', 'VKM']): return "[全熱]", 5
    return "[其他]", 6

def process_table(data, name, is_out=False):
    if not data: return pd.DataFrame(columns=[f'{name}型號', f'{name}台數'])
    dfc = pd.DataFrame(data)
    dfc['series'] = dfc['型號'].apply(get_model_series)
    dfc['c'] = dfc['型號'].apply(get_cap)

    if is_out:
        dfc['w'] = dfc['sys'].apply(get_sys_weight)
        res = dfc.groupby(['w', 'sys', 'series', '型號', 'c'])['台數'].sum().reset_index()
        res = res.sort_values(['w', 'series', 'c'], ascending=[True, True, False])
        res[f'{name}型號'] = "[" + res['sys'] + "] " + res['型號']
    else:
        dfc['info'] = dfc['型號'].apply(get_in_label)
        dfc['pref'] = dfc['info'].apply(lambda x: x[0])
        dfc['w'] = dfc['info'].apply(lambda x: x[1])
        res = dfc.groupby(['w', 'pref', 'series', '型號', 'c'])['台數'].sum().reset_index()
        res = res.sort_values(['w', 'series', 'c'], ascending=[True, True, False])
        res[f'{name}型號'] = res['pref'] + " " + res['型號']
        
    res[f'{name}台數'] = res['台數']
    return res[[f'{name}型號', f'{name}台數']]

def get_col_width(df, col_idx):
    try:
        column_data = df.iloc[:, col_idx]
        col_name = str(df.columns[col_idx])
        header_text = "" if ("Unnamed" in col_name or "sep_" in col_name) else col_name
        max_len = sum(2.4 if '\u4e00' <= c <= '\u9fff' else 1.2 for c in header_text)
        for val in column_data.astype(str).tolist():
            if val == 'nan' or val == '': continue
            length = sum(2.4 if '\u4e00' <= c <= '\u9fff' else 1.2 for c in val)
            if length > max_len: max_len = length
        return min(max_len + 4, 60)
    except: return 10


# ==============================================================================
# 3. 主執行流程
# ==============================================================================
def main():
    all_files = glob.glob("*.xlsx")
    target_files = [f for f in all_files if "-設備統計結果" not in f and not f.startswith("~$")]

    if not target_files:
        print("💡 目前目錄下未找到待處理的 .xlsx 選機表檔案。")
        return

    calc = DaikinHVACCalculator()

    for F in target_files:
        try:
            print(f"🔍 正在處理: {F}")
            b_name = os.path.splitext(F)[0]
            out_f = f"{b_name}-設備統計結果.xlsx"
            
            xls = pd.ExcelFile(F, engine='openpyxl')
            visible_sheets = []
            for s in xls.book.worksheets:
                if s.sheet_state == 'visible':
                    sn = s.title
                    if not any(k in sn for k in ['不要刪', '檢討', '統計', 'Sheet', '新風', '設備庫']):
                        visible_sheets.append(sn)
            
            f1_list, f2_list, f3_list = [], [], []

            for sn in visible_sheets:
                print(f"  📖 讀取分頁: {sn}")
                df = pd.read_excel(xls, sheet_name=sn, header=None).astype(str).replace('nan', '')
                
                in_m_idx, in_q_idx = -1, -1
                for r in range(min(15, len(df))):
                    row_vals = df.iloc[r].tolist()
                    for c, val in enumerate(row_vals):
                        v = str(val).strip()
                        if "室內機型號" in v: in_m_idx = c
                        if "室內機台數" in v: in_q_idx = c
                
                if in_m_idx == -1: in_m_idx = 13
                if in_q_idx == -1: in_q_idx = 14

                il, ol, hl, pts = [], [], [], []

                for r in range(len(df)):
                    row = df.iloc[r].tolist()
                    mi = row[in_m_idx].strip()
                    if mi and any(x.isdigit() for x in mi) and '型號' not in mi:
                        nm = f"FXMQ{mi}" if mi.replace('.', '').isdigit() else mi
                        try: il.append({'型號': nm.upper(), '台數': int(float(row[in_q_idx]))})
                        except: pass

                    for c, cell in enumerate(row):
                        v = cell.strip().upper()
                        if len(v) < 3: continue
                        st = ""
                        if any(k in v for k in ['RSUYQ', 'RXQ', 'RXYQ', 'RXYMQ', 'RXYCQ', 'REYQ', 'RWEYQ']): st = "VRV系統"
                        elif any(k in v for k in ['RKF', 'RZF', 'RZAC', 'RZA']): st = "商用1對1系統"
                        elif any(k in v for k in ['RXM', 'RXV', 'RHF']): st = "家用1對1系統"
                        elif any(k in v for k in ['2MXM', '3MXM', '4MXM', '2MXP']): st = "家用多聯系統"
                        
                        if st:
                            try:
                                q = 0
                                for o in range(1, 5):
                                    if c+o < len(row) and row[c+o].strip().replace('.','').isdigit():
                                        q = int(float(row[c+o].strip())); break
                                if q > 0:
                                    ol.append({'型號': v, '台數': q, 'sys': st})
                                    pts.append({'row': r, 'model': v, 'sys': st, 'qty': q, 'col': in_m_idx, 'q_col': in_q_idx})
                            except: pass
                        
                        if any(k in v for k in ['VAM', 'VKM']):
                            try:
                                q = 0
                                for o in range(1, 5):
                                    if c+o < len(row) and row[c+o].strip().replace('.','').isdigit():
                                        q = int(float(row[c+o].strip())); break
                                if q > 0: hl.append({'型號': v, '台數': q})
                            except: pass

                # A. 設備統計總表
                t_in = process_table(il, "室內機")
                t_out = process_table(ol, "室外機", is_out=True)
                t_hrv = process_table(hl, "全熱")

                title1 = pd.DataFrame([[f"【區域：{sn}】", '','','','','','','']], columns=['室內機型號','室內機台數',' ','室外機型號','室外機台數','  ','全熱型號','全熱台數'])
                block1 = pd.concat([
                    pd.concat([t_in, pd.DataFrame({'室內機型號':['合計'], '室內機台數':[t_in['室內機台數'].sum()]})], ignore_index=True),
                    pd.DataFrame({' ':['']}),
                    pd.concat([t_out, pd.DataFrame({'室外機型號':['合計'], '室外機台數':[t_out['室外機台數'].sum()]})], ignore_index=True),
                    pd.DataFrame({'  ':['']}),
                    pd.concat([t_hrv, pd.DataFrame({'全熱型號':['合計'], '全熱台數':[t_hrv['全熱台數'].sum()]})], ignore_index=True)
                ], axis=1).fillna('')
                f1_list.extend([title1, block1, pd.DataFrame([['']*8], columns=title1.columns)])

                # B. 系統套數 (使用 HVACNode 樹狀拓撲與管徑選型計算)
                tree_rows = []
                for i, p in enumerate(pts):
                    outdoor_title = f"{i+1}. [{p['sys']}] {p['model']}"
                    out_node = HVACNode(node_type="main", name=outdoor_title, qty=p['qty'], model=p['model'])
                    
                    next_r = pts[i+1]['row'] if i+1 < len(pts) else len(df)
                    sub = []
                    for rx in range(p['row'], next_r):
                        m_sub = df.iloc[rx][p['col']].strip()
                        if m_sub and any(x.isdigit() for x in m_sub) and '型號' not in m_sub:
                            n_sub = f"FXMQ{m_sub}" if m_sub.replace('.','').isdigit() else m_sub
                            try:
                                q_val = int(float(df.iloc[rx][p['q_col']]))
                                sub.append({'M': n_sub.upper(), 'Q': q_val})
                            except: pass
                    
                    if sub:
                        # 依型號聚合台數
                        sub_df = pd.DataFrame(sub).groupby('M')['Q'].sum().reset_index()
                        sub_nodes = []
                        for _, r_in in sub_df.iterrows():
                            mod_name = r_in['M']
                            c_idx = calc.extract_capacity_index(mod_name)
                            n_type = "ra" if any(k in mod_name for k in ['FTX', 'FDX', 'CTX']) else "vrv"
                            in_node = HVACNode(node_type=n_type, name=mod_name, capacity=c_idx, qty=int(r_in['Q']), model=mod_name)
                            sub_nodes.append(in_node)

                        # BP 箱自動組裝 (每 3 台 RA 自動一組)
                        packaged_nodes = calc.build_system_with_bp_boxes(sub_nodes)
                        for c_node in packaged_nodes:
                            out_node.add_child(c_node)

                    # 評估整棵樹 (主幹管、第一分歧頭、次幹管、後續分歧頭、分支配管)
                    calc.evaluate_tree(out_node)
                    # 展平為文字行
                    flattened = calc.flatten_tree_to_dataframe_rows(out_node, sn)
                    tree_rows.extend(flattened)
                    tree_rows.append({f"{sn}_系統結構": "", f"{sn}_數量": ""})

                f2_list.append(pd.DataFrame(tree_rows))
                f2_list.append(pd.DataFrame({"": [""]})) 

                # C. D3-NET分析
                comb_in = il + hl
                d3_in = process_table(comb_in, "室內/全熱機")
                vrv_o = [o for o in ol if o['sys'] == "VRV系統"]
                d3_out = process_table(vrv_o, "VRV室外機", is_out=True)
                s_in, s_out = d3_in['室內/全熱機台數'].sum(), d3_out['VRV室外機台數'].sum()
                pn = max(math.ceil(s_in/64) if s_in>0 else 1, math.ceil(s_out/10) if s_out>0 else 1)
                
                summary = pd.DataFrame({"VRV室外機總數": [s_out], "總室內機數": [s_in], "建議Port數": [pn]})
                title3 = pd.DataFrame([[f"【區域：{sn}】", '','','','','','','','']], columns=['室內/全熱機型號','室內/全熱機台數','    ','VRV室外機型號','VRV室外機台數','     ','VRV室外機總數','總室內機數','建議Port數'])
                block3 = pd.concat([
                    pd.concat([d3_in, pd.DataFrame({'室內/全熱機型號':['合計'], '室內/全熱機台數':[d3_in['室內/全熱機台數'].sum()]})], ignore_index=True),
                    pd.DataFrame({'    ':['']}),
                    pd.concat([d3_out, pd.DataFrame({'VRV室外機型號':['合計'], 'VRV室外機台數':[d3_out['VRV室外機台數'].sum()]})], ignore_index=True),
                    pd.DataFrame({'     ':['']}),
                    summary
                ], axis=1).fillna('')
                f3_list.extend([title3, block3, pd.DataFrame([['']*9], columns=title3.columns)])

            # 寫入 Excel
            with pd.ExcelWriter(out_f, engine='xlsxwriter') as writer:
                for d_list, sheet in [(f1_list, '設備統計總表'), (f2_list, '系統套數'), (f3_list, 'D3-NET分析')]:
                    if d_list:
                        res = pd.concat(d_list, axis=(1 if sheet=='系統套數' else 0)).fillna('')
                        if sheet == '系統套數':
                            res.columns = ["" if ("Unnamed" in str(c) or "sep_" in str(c)) else c for c in res.columns]
                        res.to_excel(writer, index=False, sheet_name=sheet)
                        for i in range(len(res.columns)):
                            writer.sheets[sheet].set_column(i, i, get_col_width(res, i))

            print(f"✅ 管徑與分歧頭拓撲統計完成: {out_f}")
        except Exception as e:
            import traceback
            print(f"❌ 處理錯誤: {e}")
            print(traceback.format_exc())

    input("✨ 處理完成，按 Enter 結束...")

if __name__ == '__main__':
    main()
