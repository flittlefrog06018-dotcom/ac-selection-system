import os

class Settings:
    # Gemini API settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
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
    
    # Excel Column Positioning Settings (from your script)
    NAME_COL: int = 4              # D
    AREA_COL: int = 5              # E
    PING_COL: int = 6              # F
    LOAD_H_COL: int = 8            # H
    LOAD_K_COL: int = 11           # K
    LOAD_L_COL: int = 12           # L
    LOAD_M_COL: int = 13           # M
    MODEL_N_COL: int = 14          # N
    QTY_O_COL: int = 15            # O
    CAP_KCAL_P_COL: int = 16       # P
    CAP_KW_Q_COL: int = 17         # Q
    TOTAL_KCAL_W_COL: int = 23     # W
    TOTAL_KW_X_COL: int = 24       # X
    PER_PING_KCAL_AB_COL: int = 28 # AB
    PER_PING_KW_AC_COL: int = 29   # AC
    PING_PER_USRT_AD_COL: int = 30 # AD
    
    START_ROW: int = 9
    TEMPLATE_ROWS: int = 5

settings = Settings()
