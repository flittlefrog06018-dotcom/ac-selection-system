import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Legacy EQUIPMENT_DB specs
EQUIPMENT_DB = {
    "RA": [
        {"model": "FTXM22ZVLT", "cap": 2.2}, {"model": "FTXM28ZVLT", "cap": 2.8},
        {"model": "FTXM36ZVLT", "cap": 3.5}, {"model": "FTXM41ZVLT", "cap": 4.1},
        {"model": "FTXM50ZVLT", "cap": 5.0}, {"model": "FTXM60ZVLT", "cap": 6.0},
        {"model": "FTXM71ZVLT", "cap": 7.2}, {"model": "FTXM80ZVLT", "cap": 8.0},
        {"model": "FTXM90ZVLT", "cap": 8.7}
    ],
    "SA": [
        {"model": "FBA71BVLT", "cap": 7.2}, {"model": "FBA100BVLT", "cap": 10.1},
        {"model": "FBA125BVLT", "cap": 12.5}, {"model": "FBA140BVLT", "cap": 13.3}
    ],
    "VRV": [
        {"model": "FXSQ20PAVT", "cap": 2.2}, {"model": "FXSQ25PAVT", "cap": 2.8},
        {"model": "FXSQ32PAVT", "cap": 3.6}, {"model": "FXSQ40PAVT", "cap": 4.5},
        {"model": "FXSQ50PAVT", "cap": 5.6}, {"model": "FXSQ63PAVT", "cap": 7.1},
        {"model": "FXSQ80PAVT", "cap": 9.0}, {"model": "FXSQ100PAVT", "cap": 11.2},
        {"model": "FXSQ125PAVT", "cap": 14.0}, {"model": "FXSQ140PAVT", "cap": 16.0}
    ]
}

class SelectionService:
    @classmethod
    def match_units(cls, system_type: str, required_load_kw: float) -> Dict[str, Any]:
        """
        Maps system type to RA/SA/VRV and executes auto_select_equipment_v15.
        """
        # Map frontend system selections to legacy database tags
        sys_mapped = "VRV"
        if system_type in ["家用", "RA", "住宅&社宅"]:
            sys_mapped = "RA"
        elif system_type in ["商用", "SA", "商業設施"]:
            sys_mapped = "SA"
        elif system_type in ["VRV"]:
            sys_mapped = "VRV"
        else:
            # Fallback check
            if "住宅" in system_type:
                sys_mapped = "RA"
            elif "辦公" in system_type or "商業" in system_type:
                sys_mapped = "SA"
                
        model, qty, cap_kw = cls.auto_select_equipment_v15(required_load_kw, sys_mapped)
        
        return {
            "indoor_model": model,
            "qty": qty,
            "indoor_capacity_kw": cap_kw,
            "indoor_capacity_kcal": round(cap_kw * 860.0, 1),
            "total_capacity_kw": round(qty * cap_kw, 1),
            "total_capacity_kcal": round(qty * cap_kw * 860.0, 1)
        }

    @staticmethod
    def auto_select_equipment_v15(total_load_kw: float, system_type: str) -> Tuple[str, int, float]:
        """
        Matches equipment based on the v15 capacity-combination search algorithm.
        """
        models_list = EQUIPMENT_DB.get(system_type, EQUIPMENT_DB["VRV"])
        best_model = None
        best_qty = 999
        best_cap = 0.0
        
        # Test unit counts from 1 up to 10
        for item in models_list:
            single_cap = item["cap"]
            for qty in range(1, 11):
                total_cap = single_cap * qty
                if total_cap >= total_load_kw:
                    if qty < best_qty:
                        best_qty = qty
                        best_model = item["model"]
                        best_cap = single_cap
                        break
                    elif qty == best_qty:
                        if best_model is None or single_cap < best_cap:
                            best_qty = qty
                            best_model = item["model"]
                            best_cap = single_cap
                        break
                        
        if best_model is not None:
            return best_model, best_qty, best_cap
            
        # Fallback if load is larger than 10 of the largest model capacity
        max_item = models_list[-1]
        needed_qty = int(round((total_load_kw / max_item["cap"]) + 0.5, 0))
        if needed_qty == 0: 
            needed_qty = 1
        return max_item["model"], needed_qty, max_item["cap"]
