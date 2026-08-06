import logging
from typing import Dict, Any, Tuple
from app.services.equipment_db_service import EquipmentDBService

logger = logging.getLogger(__name__)

class SelectionService:
    @classmethod
    def match_units(cls, system_type: str, required_load_kw: float, unit_type: str = None, series: str = None) -> Dict[str, Any]:
        """
        Matches equipment dynamically using EquipmentDBService (+/- 20% filter & Qty expansion).
        """
        eq_service = EquipmentDBService.get_instance()
        match_res = eq_service.auto_select_indoor_unit_dynamic(
            total_load_kw=required_load_kw,
            system=system_type,
            unit_type=unit_type,
            series=series
        )
        
        return {
            "indoor_model": match_res["model"],
            "qty": match_res["qty"],
            "indoor_capacity_kw": match_res["cap_kw"],
            "indoor_capacity_kcal": match_res["cap_kcal"],
            "total_capacity_kw": match_res["total_cap_kw"],
            "total_capacity_kcal": match_res["total_cap_kcal"],
            "nominal_cap": match_res["nominal_cap"],
            "power_supply": match_res["power_supply"],
            "power_consumption_kw": match_res["power_consumption_kw"],
            "dimensions": match_res["dimensions"],
            "unit_type": match_res["unit_type"],
            "series": match_res["series"],
            "system": match_res["system"]
        }

    @staticmethod
    def auto_select_equipment_v15(total_load_kw: float, system_type: str) -> Tuple[str, int, float]:
        eq_service = EquipmentDBService.get_instance()
        res = eq_service.auto_select_indoor_unit_dynamic(total_load_kw, system_type)
        return res["model"], res["qty"], res["cap_kw"]
