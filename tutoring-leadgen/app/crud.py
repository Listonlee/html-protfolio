"""資料庫操作（用 SQLAlchemy session）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config
from app.models import Analysis, Competitor, Post, Reply, ThreadsAccount, User


# ── Users ──
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.scalar(select(User).where(User.email == email.lower().strip()))


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))


def create_user(db: Session, email: str, name: str, hashed_pw: str, role: str = "member") -> User:
    user = User(email=email.lower().strip(), name=name, hashed_password=hashed_pw, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Threads accounts ──
def list_threads_accounts(db: Session) -> list[ThreadsAccount]:
    return list(db.scalars(select(ThreadsAccount).order_by(ThreadsAccount.created_at)))


def add_threads_account(db: Session, handle: str, display_name: str = "", notes: str = "") -> ThreadsAccount:
    handle = handle.strip().lstrip("@")
    acc = ThreadsAccount(handle=handle, display_name=display_name, notes=notes)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def toggle_threads_account(db: Session, acc_id: int):
    acc = db.get(ThreadsAccount, acc_id)
    if acc:
        acc.is_active = not acc.is_active
        db.commit()


def set_default_account(db: Session, acc_id: int):
    for acc in db.scalars(select(ThreadsAccount)):
        acc.is_default = acc.id == acc_id
    db.commit()


def default_account_handle(db: Session) -> str:
    acc = db.scalar(select(ThreadsAccount).where(ThreadsAccount.is_default == True))  # noqa: E712
    return acc.handle if acc else ""


# ── Competitors ──
def competitor_set(db: Session) -> set[str]:
    return {c.handle.lstrip("@").lower() for c in db.scalars(select(Competitor))}


def list_competitors(db: Session) -> list[Competitor]:
    return list(db.scalars(select(Competitor).order_by(Competitor.handle)))


def add_competitor(db: Session, handle: str):
    handle = handle.strip().lstrip("@").lower()
    if handle and not db.scalar(select(Competitor).where(Competitor.handle == handle)):
        db.add(Competitor(handle=handle))
        db.commit()


def remove_competitor(db: Session, comp_id: int):
    comp = db.get(Competitor, comp_id)
    if comp:
        db.delete(comp)
        db.commit()


# ── Posts / analysis / replies ──
def is_analyzed(db: Session, post_id: str) -> bool:
    return db.get(Analysis, post_id) is not None


def upsert_post_analysis(db: Session, post: dict, a: dict, model: str):
    if not db.get(Post, post["post_id"]):
        db.add(Post(
            post_id=post["post_id"], author_handle=post.get("author_handle", ""),
            content=post.get("content", ""), url=post.get("url", ""),
            posted_at=str(post.get("posted_at", "")),
        ))
    existing = db.get(Analysis, post["post_id"])
    if existing:
        db.delete(existing)
        db.flush()
    db.add(Analysis(
        post_id=post["post_id"], is_tutoring=a["is_tutoring_related"], intent=a["intent"],
        subject=a["subject"], level=a["level"], region=a["region"],
        is_competitor=a["is_competitor"], is_advertisement=a["is_advertisement"],
        lead_score=a["lead_score"], reason=a["reason"], suggested_reply=a["suggested_reply"],
        model=model,
    ))
    if not db.get(Reply, post["post_id"]):
        db.add(Reply(post_id=post["post_id"], status="pending"))
    db.commit()


def get_leads(db: Session, status="pending", min_score=None, subject=None, search=None):
    if min_score is None:
        min_score = config.LEAD_SCORE_THRESHOLD
    stmt = (
        select(Post, Analysis, Reply)
        .join(Analysis, Analysis.post_id == Post.post_id)
        .join(Reply, Reply.post_id == Post.post_id)
        .where(
            Reply.status == status,
            Analysis.is_tutoring == True,  # noqa: E712
            Analysis.intent == "looking_for_tutor",
            Analysis.is_competitor == False,  # noqa: E712
            Analysis.is_advertisement == False,  # noqa: E712
            Analysis.lead_score >= min_score,
        )
        .order_by(Analysis.lead_score.desc())
    )
    if subject:
        stmt = stmt.where(Analysis.subject == subject)
    if search:
        like = f"%{search}%"
        stmt = stmt.where((Post.content.like(like)) | (Post.author_handle.like(like)))
    return db.execute(stmt).all()


def get_lead(db: Session, post_id: str):
    return db.execute(
        select(Post, Analysis, Reply)
        .join(Analysis, Analysis.post_id == Post.post_id)
        .join(Reply, Reply.post_id == Post.post_id)
        .where(Post.post_id == post_id)
    ).first()


def update_reply(db: Session, post_id: str, status: str, final_reply: str,
                 account_handle: str = "", handled_by: str = ""):
    reply = db.get(Reply, post_id)
    if not reply:
        return
    reply.status = status
    reply.final_reply = final_reply
    if account_handle:
        reply.account_handle = account_handle
    if handled_by:
        reply.handled_by = handled_by
    if status == "sent":
        reply.sent_at = datetime.utcnow()
    db.commit()


def save_draft(db: Session, post_id: str, draft: str):
    reply = db.get(Reply, post_id)
    if reply:
        reply.final_reply = draft
        db.commit()


def lead_subjects(db: Session) -> list[str]:
    rows = db.scalars(
        select(Analysis.subject).where(
            Analysis.intent == "looking_for_tutor", Analysis.subject != ""
        ).distinct()
    )
    return sorted(set(rows))


def stats(db: Session) -> dict:
    def count(model, *conds):
        stmt = select(func.count()).select_from(model)
        for c in conds:
            stmt = stmt.where(c)
        return db.scalar(stmt) or 0

    return {
        "posts": count(Post),
        "tutoring": count(Analysis, Analysis.is_tutoring == True),  # noqa: E712
        "competitors": count(Analysis, Analysis.is_competitor == True),  # noqa: E712
        "pending": count(Reply, Reply.status == "pending"),
        "sent": count(Reply, Reply.status == "sent"),
        "ignored": count(Reply, Reply.status == "ignored"),
    }


def intent_breakdown(db: Session) -> dict:
    rows = db.execute(select(Analysis.intent, func.count()).group_by(Analysis.intent)).all()
    return {r[0]: r[1] for r in rows}


def subject_breakdown(db: Session) -> dict:
    rows = db.execute(
        select(Analysis.subject, func.count())
        .where(Analysis.intent == "looking_for_tutor", Analysis.subject != "")
        .group_by(Analysis.subject).order_by(func.count().desc())
    ).all()
    return {r[0]: r[1] for r in rows}
