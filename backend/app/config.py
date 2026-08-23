import os
try:
    from dotenv import load_dotenv
    env_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.env"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        os.path.join(os.getcwd(), "config.env"),
        os.path.join(os.getcwd(), ".env")
    ]
    for p in env_paths:
        if os.path.exists(p):
            load_dotenv(p, override=True)
except ImportError:
    pass

class Settings:
    # Gemini API settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    
    # Port configuration
    PORT: int = int(os.getenv("PORT", 8000))
    
    # File name constants
    TEMPLATE_NAME: str = "選機表-.xlsx"
    LOAD_DB_NAME: str = "空調負荷基準表.xlsx"
    
    # Project types mapping
    PROJECT_TYPES: dict[str, str] = {
        "1": "住宅&社宅",
        "2": "飯店",
        "3": "辦公室", 
        "4": "商業設施",
        "5": "工廠",
        "6": "醫院", 
        "7": "學校",
        "8": "宗教關係",
        "9": "銀行"
    }
    
    # Excel Column Positioning Settings (Aligned with exact user template screenshot)
    NAME_COL: int = 4              # D (室名)
    AREA_COL: int = 5              # E (面積 ㎡)
    PING_COL: int = 6              # F (坪數 P)
    LOAD_H_COL: int = 8            # H (每坪建議負荷值 kcal/hr/坪)
    LOAD_K_COL: int = 11           # K (kW/坪)
    LOAD_L_COL: int = 12           # L (總熱負荷 kW)
    LOAD_M_COL: int = 13           # M (總熱負荷 kcal/hr)
    MODEL_N_COL: int = 14          # N (室內機型號)
    QTY_O_COL: int = 15            # O (室內機台數)
    CAP_KCAL_P_COL: int = 16       # P (冷房能力 kcal/hr)
    CAP_KW_Q_COL: int = 17         # Q (冷房能力 kW)
    NOMINAL_R_COL: int = 18        # R (標稱能力 - EQUIPMENT_Data 第6列)
    POWER_S_COL: int = 19          # S (電源)
    POWER_CON_T_COL: int = 20      # T (單台耗電量 kW)
    CURRENT_U_COL: int = 21        # U (單台最大電流 A)
    DIM_V_COL: int = 22            # V (尺寸 mm HxWxD)
    TOTAL_KCAL_W_COL: int = 23     # W (室內冷房能力小計 kcal/hr)
    TOTAL_KW_X_COL: int = 24       # X (室內冷房能力小計 kW)
    PER_PING_KCAL_AB_COL: int = 28 # AB
    PER_PING_KW_AC_COL: int = 29   # AC
    PING_PER_USRT_AD_COL: int = 30 # AD
    
    START_ROW: int = 9
    TEMPLATE_ROWS: int = 5

settings = Settings()
