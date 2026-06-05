"""LLM 分析層（provider 抽象 + retry + schema 正規化）。

analyze_post(text, author_handle) -> (dict, model_str)，固定 schema：
  is_tutoring_related, intent, subject, level, region,
  is_competitor, is_advertisement, lead_score, reason, suggested_reply

Provider：
  mock       — 關鍵詞啟發式，唔使 key，即刻 demo
  gemini     — Google Gemini（OpenAI-compatible endpoint）
  openrouter — OpenRouter（將來轉去淨係改 config）
"""
import json
import logging
import time
from typing import Optional, Tuple

import config

log = logging.getLogger("leadgen.llm")

INTENTS = {"looking_for_tutor", "selling_tutoring", "discussion", "not_related"}

SYSTEM_PROMPT = """你係一個補習中介嘅銷售助手。你會收到一則社交平台 (Threads) 嘅 post，
要判斷佢同「補習 / 搵補習老師」嘅關係，幫公司主動搵客，但要避開同行。

請只輸出一個 JSON object，欄位如下：
- is_tutoring_related (bool): 係咪同學生/補習有關
- intent (string): 以下其中一個
    "looking_for_tutor"  搵緊補習（目標客）
    "selling_tutoring"   賣補習服務（同行，要避開）
    "discussion"         純討論/分享，冇即時需求
    "not_related"        同補習無關
- subject (string): 科目，例如「中學數學」，冇就 ""
- level (string): 程度，例如「中三」「小三」「DSE」，冇就 ""
- region (string): 地區，冇就 ""
- is_competitor (bool): 係咪同行/補習中心喺度賣服務
- is_advertisement (bool): 係咪廣告/自我推銷
- lead_score (number): 0~1，幾大機會係值得跟進嘅真客
- reason (string): 一句中文解釋你嘅判斷
- suggested_reply (string): 如果係 looking_for_tutor，寫一句友善、唔硬銷、口語化嘅中文回覆草稿；否則 ""

只輸出 JSON，唔好有其他文字。"""


def analyze_post(text: str, author_handle: Optional[str] = None) -> Tuple[dict, str]:
    """回傳 (分析結果 dict, 用咗邊個 model 字串)。"""
    if config.LLM_PROVIDER == "mock":
        data, model = _analyze_mock(text), "mock-heuristic"
    else:
        data, model = _analyze_openai_compatible(text)

    data = _normalize(data)
    # 黑名單 handle：直接覆寫成同行，唔理 AI 點判
    if author_handle and author_handle.lstrip("@").lower() in config.load_competitors():
        data["is_competitor"] = True
        data["intent"] = "selling_tutoring"
        data["reason"] = "喺同行黑名單"
    return data, model


def _normalize(d: dict) -> dict:
    """保證所有欄位齊全 + 型別正確 + lead_score 夾喺 0~1，
    令 model 偶爾漏欄位都唔會搞冧 pipeline。"""
    out = {
        "is_tutoring_related": bool(d.get("is_tutoring_related", False)),
        "intent": d.get("intent") if d.get("intent") in INTENTS else "not_related",
        "subject": str(d.get("subject") or ""),
        "level": str(d.get("level") or ""),
        "region": str(d.get("region") or ""),
        "is_competitor": bool(d.get("is_competitor", False)),
        "is_advertisement": bool(d.get("is_advertisement", False)),
        "reason": str(d.get("reason") or ""),
        "suggested_reply": str(d.get("suggested_reply") or ""),
    }
    try:
        out["lead_score"] = max(0.0, min(1.0, float(d.get("lead_score", 0))))
    except (TypeError, ValueError):
        out["lead_score"] = 0.0
    return out


def _client_and_model():
    from openai import OpenAI

    if config.LLM_PROVIDER == "gemini":
        if not config.GEMINI_API_KEY:
            raise RuntimeError("LLM_PROVIDER=gemini 但未設 GEMINI_API_KEY")
        return (
            OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_BASE_URL),
            config.GEMINI_MODEL,
        )
    if config.LLM_PROVIDER == "openrouter":
        if not config.OPENROUTER_API_KEY:
            raise RuntimeError("LLM_PROVIDER=openrouter 但未設 OPENROUTER_API_KEY")
        return (
            OpenAI(
                api_key=config.OPENROUTER_API_KEY,
                base_url=config.OPENROUTER_BASE_URL,
            ),
            config.OPENROUTER_MODEL,
        )
    raise RuntimeError(f"未知 LLM_PROVIDER: {config.LLM_PROVIDER}")


def _analyze_openai_compatible(text: str, max_retries: int = 3) -> Tuple[dict, str]:
    client, model = _client_and_model()
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            return _parse_json(resp.choices[0].message.content), model
        except Exception as e:  # noqa: BLE001  網絡/額度/parse 都喺度兜底
            last_err = e
            wait = 2 ** attempt
            log.warning("LLM 第 %d 次失敗:%s（%ds 後重試）", attempt, e, wait)
            if attempt < max_retries:
                time.sleep(wait)
    raise RuntimeError(f"LLM 連續 {max_retries} 次失敗:{last_err}")


def _parse_json(raw: Optional[str]) -> dict:
    if not raw:
        raise ValueError("LLM 回傳空白")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        # 萬一包咗 markdown code fence，抽返中間 { ... }
        s = raw.strip().strip("`")
        s = s[s.find("{"): s.rfind("}") + 1]
        return json.loads(s)


# ── Mock 啟發式：唔使任何 key，即刻 demo 到 ──
_LOOKING = ["搵補習", "搵緊補習", "求補習", "想搵", "邊個補", "補得好", "請問點搵",
            "搵個補習", "搵tutor", "搵 tutor", "有冇推介", "推介"]
_SELLING = ["報名", "首堂", "半價", "名額", "whatsapp", "狀元", "本中心", "招生", "🔥", "即時報名"]
_SUBJECTS = {
    "數學": "數學", "math": "數學", "英文": "英文", "english": "英文",
    "中文": "中文", "物理": "物理", "phonics": "Phonics", "中英數": "中英數",
}


def _analyze_mock(text: str) -> dict:
    t = text.lower()
    has_tutor_kw = any(k in text for k in ["補習", "tutor", "補數", "補英", "補中", "dse"]) or "dse" in t
    is_selling = any(k in text or k in t for k in _SELLING)
    is_looking = any(k in text or k.lower() in t for k in _LOOKING)

    subject = ""
    for k, v in _SUBJECTS.items():
        if k in text or k in t:
            subject = v
            break

    level = ""
    for lv in ["小一", "小二", "小三", "小四", "小五", "小六",
               "中一", "中二", "中三", "中四", "中五", "中六", "DSE", "呈分試"]:
        if lv in text or lv.lower() in t:
            level = lv
            break

    if not has_tutor_kw:
        intent, score = "not_related", 0.05
    elif is_selling:
        intent, score = "selling_tutoring", 0.1
    elif is_looking:
        intent, score = "looking_for_tutor", 0.85
    else:
        intent, score = "discussion", 0.3

    reply = ""
    if intent == "looking_for_tutor":
        subj_txt = subject or "相關科目"
        reply = (
            f"你好~見到你想搵{subj_txt}嘅補習老師。我哋有經驗豐富、"
            f"專補{level or ''}{subj_txt}嘅老師，可以按學生程度配對，"
            f"想了解多啲歡迎 DM 我哋傾下 😊"
        )

    return {
        "is_tutoring_related": has_tutor_kw,
        "intent": intent,
        "subject": subject,
        "level": level,
        "region": "九龍" if "九龍" in text else ("香港" if "香港" in text else ""),
        "is_competitor": is_selling,
        "is_advertisement": is_selling,
        "lead_score": score,
        "reason": f"啟發式判斷:intent={intent}",
        "suggested_reply": reply,
    }
