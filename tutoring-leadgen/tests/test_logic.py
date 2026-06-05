"""核心邏輯測試(免 key,用 mock provider + 臨時 SQLite)。

跑:python -m tests.test_logic   或   pytest tests/
"""
import os
import tempfile

# 用臨時 DB,唔污染正式資料(要喺 import database 前設好)
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"

from app import auth, crud  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.services import llm, scraper  # noqa: E402


def test_mock_classifies_looking_for_tutor():
    a, _ = llm.analyze_post("想搵個補習老師補中三數學，有冇推介？", "@parent")
    assert a["intent"] == "looking_for_tutor"
    assert a["subject"] == "數學"
    assert a["lead_score"] >= 0.7
    assert a["suggested_reply"]


def test_mock_detects_competitor():
    a, _ = llm.analyze_post("🔥本中心專補 DSE 數學，首堂半價即時報名！", "@centre")
    assert a["intent"] == "selling_tutoring"
    assert a["is_competitor"]


def test_blocklist_overrides():
    a, _ = llm.analyze_post("想搵補習老師補數學", "@evil_rival", competitors={"evil_rival"})
    assert a["is_competitor"]
    assert a["intent"] == "selling_tutoring"


def test_normalize_clamps():
    out = llm._normalize({"lead_score": 9, "intent": "bad"})
    assert out["lead_score"] == 1.0
    assert out["intent"] == "not_related"


def test_password_hash_roundtrip():
    h = auth.hash_password("s3cret")
    assert auth.verify_password("s3cret", h)
    assert not auth.verify_password("wrong", h)


def test_dedup():
    dup = [{"post_id": "x", "content": "a"}, {"post_id": "x", "content": "a"}]
    assert len(scraper._dedup(dup)) == 1


def test_pipeline_and_leads_end_to_end():
    from app.services import pipeline
    init_db()
    db = SessionLocal()
    try:
        crud.add_competitor(db, "best_tutor_centre")
        result = pipeline.run_pipeline(db)
        assert result["leads"] == 3          # 3 個目標客
        leads = crud.get_leads(db)
        assert len(leads) == 3
        # competitor mock-3 唔應該喺 leads 入面
        ids = {p.post_id for p, _a, _r in leads}
        assert "mock-3" not in ids
    finally:
        db.close()


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
