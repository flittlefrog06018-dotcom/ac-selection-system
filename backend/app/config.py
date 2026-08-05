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
    NAME_COL: int = 5              # E (室名)
    AREA_COL: int = 6              # F (面積 ㎡)
    PING_COL: int = 7              # G (坪數 P)
    LOAD_I_COL: int = 9            # I (每坪建議負荷值 kcal/hr/坪)
    LOAD_L_COL: int = 12           # L (kW/坪)
    LOAD_M_COL: int = 13           # M (總熱負荷 kW)
    LOAD_N_COL: int = 14           # N (總熱負荷 kcal/hr)
    MODEL_O_COL: int = 15          # O (室內機型)
    QTY_P_COL: int = 16            # P (室內機台數)
    CAP_KCAL_Q_COL: int = 17       # Q (單台能力 kcal/hr)
    CAP_KW_R_COL: int = 18         # R (單台能力標稱 kW)
    TOTAL_KCAL_W_COL: int = 23     # W (室內冷房總能力 kcal/hr)
    TOTAL_KW_X_COL: int = 24       # X (室內冷房總能力 kW)
    PER_PING_KCAL_AB_COL: int = 28 # AB
    PER_PING_KW_AC_COL: int = 29   # AC
    PING_PER_USRT_AD_COL: int = 30 # AD
    
    START_ROW: int = 9
    TEMPLATE_ROWS: int = 5

settings = Settings()
