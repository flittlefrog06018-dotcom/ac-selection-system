import os
import re
from typing import Dict, Any, List
from app.config import Settings

SYSTEM_PROMPT = """
你是一位資深的「DAIKIN 大金空調智慧選機與管路拓撲自動化系統」工程顧問小助手。
你的職責是用繁體中文、專業、親切且簡明扼要地回答使用者對於本系統的操作指引與大金暖通空調技術疑問。

【本系統的核心操作五步驟】
1. 圖面辨識：上傳平面圖 (JPG/PNG/PDF)。使用「1. 📏 參考尺寸」點選已知門框兩點輸入 90cm 進行微米級放樣標定；或使用「2. 🪣 填滿空間」、「3. 🟩 矩形拉框」、「4. 🔺 多邊形 PLine」圈選房間。點擊「🚀 執行圖面自動解析」透過 AI 讀取空間名稱與計算坪數。
2. 負荷估算：可設定空間高度、頂樓、西曬等熱源條件，系統依每坪 kcal/h（如客廳 600~650, 臥室 500~550）試算冷房負荷。
3. 室內機選用：系統依需求冷房能力自動推薦最佳大金室內機型號（支援橫綱、大關、經典系列及 VRV FXDQ/FXSQ 等）。
4. 室外機選用：智慧成組，依總容量與連線率自動推薦家用多聯（2MXP/3MXM/4MXM）或 VRV 系統主機（RSUYQ/RXYQ），電源同步維持一致。
5. 控制與冷媒拓撲：在「製作冷媒流程圖」分頁可拖曳卡片建立「次分歧網絡 (Sub-Branch)」，系統自動計算第一分歧頭與次分歧管（KHRP26A22T），一鍵匯出大金原廠標準 Excel 試算表（選機、設備報價單、系統套數流程圖）。

【回答原則】
1. 嚴格使用繁體中文回答，口氣專業友善。
2. 避免給出長篇大論的廢話，直接給予最核心的操作步驟與具體機型建議。
3. 若使用者詢問快捷鍵：告知 C 鍵為閉合多邊形、Z 鍵撤銷上一步、X 鍵切換拉框工具、滑鼠中鍵按住平移、滾輪縮放。
"""

# 內建離線專業知識庫 (Fallback)
OFFLINE_QA = [
    (r"(門寬|比例|放樣|尺寸|尺度)", "📏 **比例放樣操作指引**：\n1. 點擊工具列【1. 📏 參考尺寸】。\n2. 在圖面上的標準房門兩側頂點依序點選起點與終點。\n3. 在跳出的提示框輸入門寬長度（標準通常為 90cm）。\n4. 系統將自動完成全圖 1px = X cm 標定，並即時連動所有空間面積與冷房負荷！"),
    (r"(次分歧|分歧頭|分歧管|拓撲|管徑)", "❄️ **VRV 冷媒分歧管拓撲指引**：\n1. 切換至【製作冷媒流程圖】Tab。\n2. 系統依據大金《VRV冷媒管徑選用工具》自動計算下游能力總和 (X 值)。\n3. 欲將次臥或書房合併次分歧，點擊【+次分歧群組】，並將室內機卡片拖曳移入。\n4. 系統自動生成主幹次幹管分歧點 (KHRP26A22T) 與網絡內部次分歧頭 (共2組)，並即時繪製向量 CAD 流程圖！"),
    (r"(西曬|頂樓|挑高|熱源|熱負荷|估算|kcal|坪數)", "🔥 **熱負荷計算基準建議**：\n• 一般臥室/書房：約 500 ~ 550 kcal/h/坪\n• 客廳/餐廳/開放空間：約 600 ~ 650 kcal/h/坪\n• 頂樓或大面西曬玻璃：建議加成 100 ~ 200 kcal/h/坪 (可設定為 700~750 kcal/h)\n可在第二步驟【負荷估算】直接點選空間卡片調整計算基準！"),
    (r"(匯出|報價單|excel|存檔|備份|daikin)", "📊 **報價單匯出與專案備份指南**：\n• **匯出 Excel 報價表**：點擊右上角綠色按鈕【📥 匯出完整選機與報價表 (.xlsx)】，直出含【選機】、【設備報價單 (室外機置頂)】與【系統套數 (含冷媒圖面)】的三合一商業試算表。\n• **專案暫存與匯入**：點擊【💾 儲存專案】存入本機快照；或下載【.daikin 專案檔】，即可在任何電腦隨時載入完整空間與選機！"),
    (r"(快捷鍵|滑鼠|操作|怎麼用)", "⌨️ **實用操作快捷鍵秘笈**：\n• `C` 鍵：多邊形繪製時快速閉合曲線\n• `Z` 鍵：回到上一步（撤銷上一點或空間）\n• `X` 鍵：快速循環切換 🪣填滿 / 🟩矩形 / 🔺多邊形\n• `滑鼠中鍵按住拖曳`：平移圖面視角 (Move/Pan)\n• `滑鼠滾輪滾動`：即時縮放圖面比例 (50%~500%)")
]

class CopilotService:
    @classmethod
    def answer_query(cls, question: str, chat_history: List[Dict[str, str]] = None) -> str:
        question = question.strip()
        if not question:
            return "您好！我是大金空調智慧選機顧問，請問有什麼空調選型、配管拓撲或操作上的問題需要協助嗎？"

        # 優先嘗試調用 Google Gemini API
        api_key = Settings.GEMINI_API_KEY
        if api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                
                # 組合 Prompt 與上下文
                contents = [
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=f"{SYSTEM_PROMPT}\n\n使用者問題: {question}")]
                    )
                ]

                # 嘗試呼叫合適模型
                models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
                for m_name in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=m_name,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                temperature=0.3,
                                max_output_tokens=600
                            )
                        )
                        if response and response.text:
                            return response.text.strip()
                    except Exception as mod_err:
                        err_str = str(mod_err)
                        if "429" in err_str or "404" in err_str:
                            continue
                        break
            except Exception as e:
                pass

        # 若 API 無法連線或額度耗盡，啟用內建專家規則庫解答
        for pattern, reply in OFFLINE_QA:
            if re.search(pattern, question, re.IGNORECASE):
                return reply

        return f"💡 關於「{question}」：\n建議您依照上方五步標準流程：\n1. 先於圖面校正 90cm 門寬基準。\n2. 點擊【🚀 執行圖面自動解析】自動辨識房間與計算坪數。\n3. 在選機表格確認大金機型配對與室外機分組。\n4. 如有 VRV 配管需求，切換至【製作冷媒流程圖】調整次分歧網絡。\n最後點擊右上角【📥 匯出完整選機與報價表】即可取得正式文件！"
