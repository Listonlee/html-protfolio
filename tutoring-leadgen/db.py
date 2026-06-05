"""SQLite 資料層。本機跑,免外部 DB。

三張表(對應 design doc):
  posts    — 爬返嚟嘅原始 post
  analysis — LLM 分析結果
  replies  — 半自動回覆狀態(pending/sent/ignored)
"""
import sqlite3
from contextlib import contextmanager
from typing import Optional

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    post_id       TEXT PRIMARY KEY,
    platform      TEXT NOT NULL DEFAULT 'threads',
    author_handle TEXT,
    content       TEXT,
    url           TEXT,
    posted_at     TEXT,
    scraped_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analysis (
    post_id         TEXT PRIMARY KEY REFERENCES posts(post_id),
    is_tutoring     INTEGER,
    intent          TEXT,
    subject         TEXT,
    level           TEXT,
    region          TEXT,
    is_competitor   INTEGER,
    is_advertisement INTEGER,
    lead_score      REAL,
    reason          TEXT,
    suggested_reply TEXT,
    model           TEXT,
    analyzed_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS replies (
    post_id     TEXT PRIMARY KEY REFERENCES posts(post_id),
    status      TEXT DEFAULT 'pending',  -- pending | sent | ignored
    final_reply TEXT,
    sent_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_analysis_intent ON analysis(intent);
CREATE INDEX IF NOT EXISTS idx_analysis_score  ON analysis(lead_score);
CREATE INDEX IF NOT EXISTS idx_replies_status  ON replies(status);
"""

_LEAD_COLS = """
    p.post_id, p.author_handle, p.content, p.url, p.posted_at,
    a.intent, a.subject, a.level, a.region, a.lead_score,
    a.reason, a.suggested_reply, a.is_competitor, a.is_advertisement,
    r.status, r.final_reply
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def post_exists(post_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM posts WHERE post_id = ?", (post_id,)
        ).fetchone()
        return row is not None


def is_analyzed(post_id: str) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM analysis WHERE post_id = ?", (post_id,)
        ).fetchone() is not None


def insert_post(post: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO posts
               (post_id, platform, author_handle, content, url, posted_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                post["post_id"],
                post.get("platform", "threads"),
                post.get("author_handle"),
                post.get("content"),
                post.get("url"),
                post.get("posted_at"),
            ),
        )


def save_analysis(post_id: str, a: dict, model: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO analysis
               (post_id, is_tutoring, intent, subject, level, region,
                is_competitor, is_advertisement, lead_score, reason,
                suggested_reply, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                post_id,
                int(bool(a.get("is_tutoring_related"))),
                a.get("intent"),
                a.get("subject"),
                a.get("level"),
                a.get("region"),
                int(bool(a.get("is_competitor"))),
                int(bool(a.get("is_advertisement"))),
                float(a.get("lead_score", 0)),
                a.get("reason"),
                a.get("suggested_reply"),
                model,
            ),
        )
        # 每條分析過嘅 post 都開一行 reply(pending),re-analyze 唔會洗走已有狀態
        conn.execute(
            "INSERT OR IGNORE INTO replies (post_id, status) VALUES (?, 'pending')",
            (post_id,),
        )


def get_lead(post_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            f"""SELECT {_LEAD_COLS}
                FROM posts p
                JOIN analysis a ON a.post_id = p.post_id
                JOIN replies  r ON r.post_id = p.post_id
                WHERE p.post_id = ?""",
            (post_id,),
        ).fetchone()
        return dict(row) if row else None


def get_leads(
    status: str = "pending",
    min_score: Optional[float] = None,
    subject: Optional[str] = None,
    search: Optional[str] = None,
):
    """攞符合搵客條件嘅 leads,按 lead_score 由高到低。"""
    if min_score is None:
        min_score = config.LEAD_SCORE_THRESHOLD

    where = [
        "r.status = ?",
        "a.is_tutoring = 1",
        "a.intent = 'looking_for_tutor'",
        "a.is_competitor = 0",
        "a.is_advertisement = 0",
        "a.lead_score >= ?",
    ]
    params: list = [status, min_score]
    if subject:
        where.append("a.subject = ?")
        params.append(subject)
    if search:
        where.append("(p.content LIKE ? OR p.author_handle LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT {_LEAD_COLS}
                FROM posts p
                JOIN analysis a ON a.post_id = p.post_id
                JOIN replies  r ON r.post_id = p.post_id
                WHERE {' AND '.join(where)}
                ORDER BY a.lead_score DESC, p.posted_at DESC""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def lead_subjects() -> list[str]:
    """所有 lead 出現過嘅科目(畀 dashboard 做 filter)。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT subject FROM analysis
               WHERE intent='looking_for_tutor' AND subject != ''
               ORDER BY subject"""
        ).fetchall()
        return [r[0] for r in rows]


def update_reply(post_id: str, status: str, final_reply: str = None):
    with get_conn() as conn:
        conn.execute(
            """UPDATE replies
               SET status = ?, final_reply = ?,
                   sent_at = CASE WHEN ?='sent' THEN datetime('now') ELSE sent_at END
               WHERE post_id = ?""",
            (status, final_reply, status, post_id),
        )


def save_draft(post_id: str, draft: str):
    """淨係儲草稿,唔改狀態(畀 dashboard「儲返先」用)。"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE replies SET final_reply = ? WHERE post_id = ?",
            (draft, post_id),
        )


def intent_breakdown() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT intent, COUNT(*) FROM analysis GROUP BY intent"
        ).fetchall()
        return {r[0]: r[1] for r in rows}


def subject_breakdown() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT subject, COUNT(*) FROM analysis
               WHERE intent='looking_for_tutor' AND subject != ''
               GROUP BY subject ORDER BY COUNT(*) DESC"""
        ).fetchall()
        return {r[0]: r[1] for r in rows}


def stats() -> dict:
    with get_conn() as conn:
        def n(sql, *p):
            return conn.execute(sql, p).fetchone()[0]

        return {
            "posts": n("SELECT COUNT(*) FROM posts"),
            "tutoring": n("SELECT COUNT(*) FROM analysis WHERE is_tutoring=1"),
            "competitors": n("SELECT COUNT(*) FROM analysis WHERE is_competitor=1"),
            "pending": n("SELECT COUNT(*) FROM replies WHERE status='pending'"),
            "sent": n("SELECT COUNT(*) FROM replies WHERE status='sent'"),
            "ignored": n("SELECT COUNT(*) FROM replies WHERE status='ignored'"),
        }
