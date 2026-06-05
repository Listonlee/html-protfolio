"""核心邏輯測試(唔需要任何 API key,用 mock provider)。

跑:python test_logic.py   或   pytest test_logic.py
"""
import config
import db
import llm


def test_mock_classifies_looking_for_tutor():
    a, _ = llm.analyze_post("想搵個補習老師補中三數學，有冇推介？", "@parent")
    assert a["intent"] == "looking_for_tutor"
    assert a["subject"] == "數學"
    assert a["lead_score"] >= config.LEAD_SCORE_THRESHOLD
    assert a["suggested_reply"]  # 有草稿


def test_mock_detects_competitor_selling():
    a, _ = llm.analyze_post("🔥本中心專補 DSE，首堂半價，即時報名！", "@centre")
    assert a["intent"] == "selling_tutoring"
    assert a["is_competitor"] is True
    assert a["lead_score"] < config.LEAD_SCORE_THRESHOLD


def test_mock_ignores_unrelated():
    a, _ = llm.analyze_post("今日去咗食壽司好正🍣", "@foodie")
    assert a["intent"] == "not_related"
    assert a["is_tutoring_related"] is False


def test_blocklist_overrides_to_competitor():
    handle = config.load_competitors()
    assert handle, "competitors.txt 應該至少有一個 sample handle"
    sample = next(iter(handle))
    # 即使內容似搵補習,黑名單 handle 都要變成同行
    a, _ = llm.analyze_post("想搵補習老師補數學", f"@{sample}")
    assert a["is_competitor"] is True
    assert a["intent"] == "selling_tutoring"


def test_normalize_clamps_and_fills():
    out = llm._normalize({"lead_score": 5, "intent": "garbage"})
    assert out["lead_score"] == 1.0          # 夾返 0~1
    assert out["intent"] == "not_related"    # 非法 intent → fallback
    assert "suggested_reply" in out          # 欄位齊全


def test_dedup_in_scraper():
    import scraper
    dup = [{"post_id": "x", "content": "a"}, {"post_id": "x", "content": "a"}]
    assert len(scraper._dedup(dup)) == 1


def test_lead_filter_end_to_end(tmp_path=None):
    """入幾條唔同 post,確認 get_leads 只攞到真目標客。"""
    import tempfile
    import pathlib
    # 用臨時 DB,唔污染正式 leadgen.db
    config.DB_PATH = pathlib.Path(tempfile.mkdtemp()) / "test.db"
    db.init_db()

    samples = [
        ("p1", "@a", "想搵補習老師補中三數學，有冇推介？"),   # lead
        ("p2", "@b", "🔥本中心首堂半價即時報名"),              # competitor
        ("p3", "@c", "今日食壽司好正🍣"),                       # unrelated
    ]
    for pid, handle, content in samples:
        db.insert_post({"post_id": pid, "author_handle": handle, "content": content,
                        "url": "http://x", "posted_at": "2026-06-05"})
        a, m = llm.analyze_post(content, handle)
        db.save_analysis(pid, a, m)

    leads = db.get_leads()
    assert len(leads) == 1
    assert leads[0]["post_id"] == "p1"


def _run_all():
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ✅ {name}")
            passed += 1
    print(f"\n{passed} 個測試全部通過 🎉")


if __name__ == "__main__":
    _run_all()
