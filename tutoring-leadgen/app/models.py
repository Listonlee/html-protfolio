"""資料表定義(SQLAlchemy ORM）。

User           — 團隊登入帳號(一個 admin 主帳號 + 幾個成員)
ThreadsAccount — 用嚟回覆嘅 Threads 帳號(可管理多個)
Competitor     — 同行黑名單 handle
Post           — 爬返嘅原始 post
Analysis       — LLM 分析結果
Reply          — 半自動回覆狀態
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="member")  # admin | member
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ThreadsAccount(Base):
    __tablename__ = "threads_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # 預設回覆帳號
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Competitor(Base):
    __tablename__ = "competitors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle: Mapped[str] = mapped_column(String(120), unique=True, index=True)


class Post(Base):
    __tablename__ = "posts"
    post_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    platform: Mapped[str] = mapped_column(String(40), default="threads")
    author_handle: Mapped[str] = mapped_column(String(160), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[str] = mapped_column(String(40), default="")
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    analysis: Mapped["Analysis"] = relationship(back_populates="post", uselist=False)
    reply: Mapped["Reply"] = relationship(back_populates="post", uselist=False)


class Analysis(Base):
    __tablename__ = "analysis"
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.post_id"), primary_key=True)
    is_tutoring: Mapped[bool] = mapped_column(Boolean, default=False)
    intent: Mapped[str] = mapped_column(String(40), default="not_related", index=True)
    subject: Mapped[str] = mapped_column(String(80), default="")
    level: Mapped[str] = mapped_column(String(80), default="")
    region: Mapped[str] = mapped_column(String(80), default="")
    is_competitor: Mapped[bool] = mapped_column(Boolean, default=False)
    is_advertisement: Mapped[bool] = mapped_column(Boolean, default=False)
    lead_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    suggested_reply: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    post: Mapped["Post"] = relationship(back_populates="analysis")


class Reply(Base):
    __tablename__ = "replies"
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.post_id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    final_reply: Mapped[str] = mapped_column(Text, default="")
    account_handle: Mapped[str] = mapped_column(String(120), default="")  # 用咗邊個帳號發
    handled_by: Mapped[str] = mapped_column(String(255), default="")       # 邊個團隊成員
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    post: Mapped["Post"] = relationship(back_populates="reply")
