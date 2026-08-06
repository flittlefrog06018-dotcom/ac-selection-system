import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any, Optional

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.equipment_db_service import EquipmentDBService
from app.services.export_service import ExportService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EquipmentSelectionGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("空調動態選機與報表匯出系統 (EQUIPMENT_Data 核心版)")
        self.root.geometry("1100x700")
        
        self.db_service = EquipmentDBService.get_instance()
        self.spaces_data: List[Dict[str, Any]] = [
            {"room_name": "董事長室", "area_m2": 35.5, "ping_val": 10.74, "final_suggested_kcal_per_ping": 550, "total_load_kw": 6.9, "total_load_kcal": 5907},
            {"room_name": "總經理室", "area_m2": 23.2, "ping_val": 7.02, "final_suggested_kcal_per_ping": 550, "total_load_kw": 4.5, "total_load_kcal": 3861},
            {"room_name": "辦公室", "area_m2": 34.6, "ping_val": 10.47, "final_suggested_kcal_per_ping": 630, "total_load_kw": 7.7, "total_load_kcal": 6596},
            {"room_name": "合約洽談區", "area_m2": 27.3, "ping_val": 8.26, "final_suggested_kcal_per_ping": 630, "total_load_kw": 6.1, "total_load_kcal": 5204},
            {"room_name": "吧台區", "area_m2": 31.2, "ping_val": 9.44, "final_suggested_kcal_per_ping": 700, "total_load_kw": 7.7, "total_load_kcal": 6608},
        ]
        self.rows_widgets = []
        
        # Initial database check and load
        if not self.db_service.load_equipment_db(raise_error_on_missing=False):
            err_msg = f"❌ 找不到設備資料庫檔案 EQUIPMENT_Data.xlsx！\n請確定將檔案放置於專案根目錄或 backend/product_database/ 資料夾。"
            messagebox.showerror("資料庫讀取失敗", err_msg)
            
        self._build_ui()

    def _build_ui(self):
        # Top Global Selection Panel
        top_frame = ttk.LabelFrame(self.root, text="🌐 全局預設選機設定 (全專案預設套用)", padding=10)
        top_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(top_frame, text="選擇預設系統:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.global_sys_cb = ttk.Combobox(top_frame, values=self.db_service.get_systems(), state="readonly", width=12)
        self.global_sys_cb.grid(row=0, column=1, padx=5, pady=5)
        if self.db_service.get_systems():
            self.global_sys_cb.current(0)
            
        ttk.Label(top_frame, text="選擇預設型式:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.global_type_cb = ttk.Combobox(top_frame, values=self.db_service.get_unit_types(self.global_sys_cb.get()), state="readonly", width=12)
        self.global_type_cb.grid(row=0, column=3, padx=5, pady=5)
        if self.global_type_cb['values']:
            self.global_type_cb.current(0)

        ttk.Label(top_frame, text="選擇預設系列別:").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.global_series_cb = ttk.Combobox(top_frame, values=self.db_service.get_series(self.global_sys_cb.get(), self.global_type_cb.get()), state="readonly", width=15)
        self.global_series_cb.grid(row=0, column=5, padx=5, pady=5)
        if self.global_series_cb['values']:
            self.global_series_cb.current(0)
            
        btn_apply_all = ttk.Button(top_frame, text="⚡ 全局套用至所有空間", command=self.apply_global_defaults)
        btn_apply_all.grid(row=0, column=6, padx=15, pady=5)
        
        # Event bindings for global cascading
        self.global_sys_cb.bind("<<ComboboxSelected>>", self._on_global_sys_change)
        self.global_type_cb.bind("<<ComboboxSelected>>", self._on_global_type_change)

        # Middle Table Panel
        mid_frame = ttk.LabelFrame(self.root, text="🏢 各空間動態審查與層級選單 (±20% 容量限縮)", padding=10)
        mid_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Canvas & Scrollbar
        canvas = tk.Canvas(mid_frame)
        scrollbar = ttk.Scrollbar(mid_frame, orient="vertical", command=canvas.yview)
        scroll_content = ttk.Frame(canvas)
        scroll_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Table Headers
        headers = ["空間名稱", "坪數", "需求kW", "系統", "型式", "系列別", "型號 (±20%範圍限縮)", "台數", "單機kW", "總能力kW"]
        for col_i, h in enumerate(headers):
            lbl = ttk.Label(scroll_content, text=h, font=("Microsoft JhengHei", 9, "bold"))
            lbl.grid(row=0, column=col_i, padx=5, pady=5, sticky="w")
            
        # Render Space Rows
        for idx, space in enumerate(self.spaces_data, start=1):
            self._render_space_row(scroll_content, idx, space)
            
        # Bottom Action Bar
        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill="x", padx=10, pady=5)
        
        btn_export = ttk.Button(bottom_frame, text="📊 匯出至「選機表-.xlsx」官方報表", command=self.export_excel)
        btn_export.pack(side="right", padx=5)

    def _on_global_sys_change(self, event=None):
        sys_val = self.global_sys_cb.get()
        types = self.db_service.get_unit_types(sys_val)
        self.global_type_cb['values'] = types
        if types:
            self.global_type_cb.current(0)
        self._on_global_type_change()

    def _on_global_type_change(self, event=None):
        sys_val = self.global_sys_cb.get()
        type_val = self.global_type_cb.get()
        series_list = self.db_service.get_series(sys_val, type_val)
        self.global_series_cb['values'] = series_list
        if series_list:
            self.global_series_cb.current(0)

    def apply_global_defaults(self):
        sys_val = self.global_sys_cb.get()
        type_val = self.global_type_cb.get()
        series_val = self.global_series_cb.get()
        
        for w in self.rows_widgets:
            w['sys_cb'].set(sys_val)
            self._update_row_types(w)
            w['type_cb'].set(type_val)
            self._update_row_series(w)
            w['series_cb'].set(series_val)
            self._recalc_row_match(w)
            
        messagebox.showinfo("成功", "已將全域設備設定成功套用到所有空間！")

    def _render_space_row(self, parent, row_idx: int, space: Dict[str, Any]):
        ttk.Label(parent, text=space["room_name"], width=12).grid(row=row_idx, column=0, padx=5, pady=4)
        ttk.Label(parent, text=f"{space['ping_val']} 坪", width=8).grid(row=row_idx, column=1, padx=5, pady=4)
        ttk.Label(parent, text=f"{space['total_load_kw']} kW", width=8).grid(row=row_idx, column=2, padx=5, pady=4)
        
        # System Combobox
        sys_cb = ttk.Combobox(parent, values=self.db_service.get_systems(), state="readonly", width=8)
        sys_cb.grid(row=row_idx, column=3, padx=4, pady=4)
        if sys_cb['values']:
            sys_cb.current(0)
            
        # Type Combobox
        type_cb = ttk.Combobox(parent, values=self.db_service.get_unit_types(sys_cb.get()), state="readonly", width=10)
        type_cb.grid(row=row_idx, column=4, padx=4, pady=4)
        if type_cb['values']:
            type_cb.current(0)

        # Series Combobox
        series_cb = ttk.Combobox(parent, values=self.db_service.get_series(sys_cb.get(), type_cb.get()), state="readonly", width=12)
        series_cb.grid(row=row_idx, column=5, padx=4, pady=4)
        if series_cb['values']:
            series_cb.current(0)
            
        # Model Combobox (Filtered +/- 20%)
        model_cb = ttk.Combobox(parent, state="readonly", width=16)
        model_cb.grid(row=row_idx, column=6, padx=4, pady=4)
        
        # Qty Spinbox
        qty_sp = ttk.Spinbox(parent, from_=1, to=20, width=4)
        qty_sp.grid(row=row_idx, column=7, padx=4, pady=4)
        qty_sp.set(1)

        # Cap Labels
        cap_lbl = ttk.Label(parent, text="- kW", width=8)
        cap_lbl.grid(row=row_idx, column=8, padx=4, pady=4)
        
        tot_lbl = ttk.Label(parent, text="- kW", width=8)
        tot_lbl.grid(row=row_idx, column=9, padx=4, pady=4)
        
        row_dict = {
            "space": space,
            "sys_cb": sys_cb,
            "type_cb": type_cb,
            "series_cb": series_cb,
            "model_cb": model_cb,
            "qty_sp": qty_sp,
            "cap_lbl": cap_lbl,
            "tot_lbl": tot_lbl,
            "full_models_map": {}
        }
        self.rows_widgets.append(row_dict)

        # Event bindings
        sys_cb.bind("<<ComboboxSelected>>", lambda e: self._on_row_sys_change(row_dict))
        type_cb.bind("<<ComboboxSelected>>", lambda e: self._on_row_type_change(row_dict))
        series_cb.bind("<<ComboboxSelected>>", lambda e: self._on_row_series_change(row_dict))
        model_cb.bind("<<ComboboxSelected>>", lambda e: self._on_row_model_change(row_dict))
        qty_sp.bind("<Change>", lambda e: self._on_row_qty_change(row_dict))
        
        # Initial calculation
        self._recalc_row_match(row_dict)

    def _update_row_types(self, w):
        sys_val = w['sys_cb'].get()
        types = self.db_service.get_unit_types(sys_val)
        w['type_cb']['values'] = types
        if types:
            w['type_cb'].current(0)
            
    def _update_row_series(self, w):
        sys_val = w['sys_cb'].get()
        type_val = w['type_cb'].get()
        series = self.db_service.get_series(sys_val, type_val)
        w['series_cb']['values'] = series
        if series:
            w['series_cb'].current(0)

    def _on_row_sys_change(self, w):
        self._update_row_types(w)
        self._update_row_series(w)
        self._recalc_row_match(w)

    def _on_row_type_change(self, w):
        self._update_row_series(w)
        self._recalc_row_match(w)

    def _on_row_series_change(self, w):
        self._recalc_row_match(w)

    def _recalc_row_match(self, w):
        space = w['space']
        load_kw = space['total_load_kw']
        sys_val = w['sys_cb'].get()
        type_val = w['type_cb'].get()
        series_val = w['series_cb'].get()
        
        # Run auto selection algorithm
        res = self.db_service.auto_select_indoor_unit_dynamic(
            total_load_kw=load_kw,
            system=sys_val,
            unit_type=type_val,
            series=series_val
        )
        
        w['qty_sp'].set(res['qty'])
        
        # Populate candidate models +/- 20%
        target_single = load_kw / res['qty']
        candidate_objs = self.db_service.get_models_filtered(sys_val, type_val, series_val, target_single)
        
        models_display = [f"{u['model']} ({u['cap_kw']}kW)" for u in candidate_objs]
        w['model_cb']['values'] = models_display
        w['full_models_map'] = {f"{u['model']} ({u['cap_kw']}kW)": u for u in candidate_objs}
        
        matched_str = f"{res['model']} ({res['cap_kw']}kW)"
        if matched_str in w['full_models_map']:
            w['model_cb'].set(matched_str)
        elif models_display:
            w['model_cb'].current(0)
            
        self._update_cap_labels(w)

    def _on_row_model_change(self, w):
        self._update_cap_labels(w)

    def _on_row_qty_change(self, w):
        self._update_cap_labels(w)

    def _update_cap_labels(self, w):
        sel_display = w['model_cb'].get()
        unit_obj = w['full_models_map'].get(sel_display)
        try:
            qty = int(w['qty_sp'].get())
        except ValueError:
            qty = 1
            
        if unit_obj:
            cap_kw = unit_obj['cap_kw']
            tot_kw = round(cap_kw * qty, 1)
            w['cap_lbl'].config(text=f"{cap_kw} kW")
            w['tot_lbl'].config(text=f"{tot_kw} kW")
        else:
            w['cap_lbl'].config(text="- kW")
            w['tot_lbl'].config(text="- kW")

    def export_excel(self):
        export_data = []
        for w in self.rows_widgets:
            space = w['space']
            sel_display = w['model_cb'].get()
            unit_obj = w['full_models_map'].get(sel_display, {})
            try:
                qty = int(w['qty_sp'].get())
            except ValueError:
                qty = 1
                
            cap_kw = unit_obj.get("cap_kw", 2.2)
            cap_kcal = round(cap_kw * 860.0, 1)
            kw_per_ping = round(space["final_suggested_kcal_per_ping"] / 860.0, 2)
            
            export_data.append({
                "room_name": space["room_name"],
                "area_m2": space["area_m2"],
                "ping_val": space["ping_val"],
                "final_suggested_kcal_per_ping": space["final_suggested_kcal_per_ping"],
                "kw_per_ping": kw_per_ping,
                "total_load_kw": space["total_load_kw"],
                "total_load_kcal": space["total_load_kcal"],
                "indoor_model": unit_obj.get("model", "FXSQ28PAVT"),
                "qty": qty,
                "indoor_capacity_kw": cap_kw,
                "indoor_capacity_kcal": cap_kcal,
                "nominal_cap": unit_obj.get("nominal_cap", "-"),
                "power_supply": unit_obj.get("power_supply", "-"),
                "power_consumption_kw": unit_obj.get("power_consumption_kw", "-"),
                "dimensions": unit_obj.get("dimensions", "-"),
            })

        try:
            buf = ExportService.generate_excel_report(export_data)
            out_filename = filedialog.asksaveasfilename(
                title="儲存選機表報表",
                defaultextension=".xlsx",
                initialfile="選機表-規劃案.xlsx",
                filetypes=[("Excel Files", "*.xlsx")]
            )
            if out_filename:
                with open(out_filename, "wb") as f:
                    f.write(buf.getvalue())
                messagebox.showinfo("成功", f"🎉 選機表已成功匯出至：\n{out_filename}")
        except Exception as e:
            messagebox.showerror("匯出失敗", f"寫入選機表報表時發生錯誤：\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = EquipmentSelectionGUI(root)
    root.mainloop()
