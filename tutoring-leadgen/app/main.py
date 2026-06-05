"""FastAPI web app:登入認證 + 審核台 + 帳號管理 + pipeline 觸發。

本機跑:  uvicorn app.main:app --reload
Cloud Run:由 Dockerfile 嘅 uvicorn 啟動。
"""
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from app import auth, config, crud
from app.database import get_db, init_db
from app.models import User
from app.services import pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="補習主動搵客")
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, https_only=config.COOKIE_SECURE)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def _startup():
    init_db()


@app.exception_handler(401)
async def _redirect_login(request: Request, exc):
    """未登入訪問受保護頁面 → 帶去登入頁(而唔係彈 JSON 401)。"""
    return RedirectResponse("/login", status_code=302)


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ─────────────────────── 認證 ───────────────────────
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...),
          db: Session = Depends(get_db)):
    user = auth.authenticate(db, email, password)
    if not user:
        return RedirectResponse("/login?error=帳號或密碼錯誤", status_code=302)
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=302)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# ─────────────────────── 審核台 ───────────────────────
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, status: str = "pending", min_score: float = None,
              subject: str = "", search: str = "",
              user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    if min_score is None:
        min_score = config.LEAD_SCORE_THRESHOLD
    rows = crud.get_leads(db, status=status, min_score=min_score,
                          subject=subject or None, search=search or None)
    leads = [{
        "post_id": p.post_id, "author_handle": p.author_handle, "content": p.content,
        "url": p.url, "posted_at": p.posted_at, "subject": a.subject, "level": a.level,
        "lead_score": a.lead_score, "reason": a.reason,
        "draft": r.final_reply or a.suggested_reply, "status": r.status,
        "account_handle": r.account_handle, "handled_by": r.handled_by,
    } for p, a, r in rows]

    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "leads": leads, "stats": crud.stats(db),
        "status": status, "min_score": min_score, "subject": subject, "search": search,
        "subjects": crud.lead_subjects(db),
        "accounts": [acc for acc in crud.list_threads_accounts(db) if acc.is_active],
        "default_account": crud.default_account_handle(db),
        "threshold": config.LEAD_SCORE_THRESHOLD,
    })


@app.post("/leads/{post_id}/action")
def lead_action(post_id: str, request: Request, action: str = Form(...),
                draft: str = Form(""), account: str = Form(""),
                user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    if action == "send":
        crud.update_reply(db, post_id, "sent", draft, account, user.email)
    elif action == "ignore":
        crud.update_reply(db, post_id, "ignored", draft, handled_by=user.email)
    elif action == "save":
        crud.save_draft(db, post_id, draft)
    elif action == "regenerate":
        lead = crud.get_lead(db, post_id)
        if lead:
            p, _a, _r = lead
            from app.services import llm
            new_a, _ = llm.analyze_post(p.content, p.author_handle, crud.competitor_set(db))
            crud.save_draft(db, post_id, new_a["suggested_reply"] or draft)
    return RedirectResponse("/?" + _qs(request), status_code=302)


# ─────────────────────── 分析 ───────────────────────
@app.get("/analytics", response_class=HTMLResponse)
def analytics(request: Request, user: User = Depends(auth.current_user),
              db: Session = Depends(get_db)):
    s = crud.stats(db)
    processed = s["sent"] + s["ignored"]
    return templates.TemplateResponse(request, "analytics.html", {
        "user": user, "stats": s,
        "intents": crud.intent_breakdown(db), "subjects": crud.subject_breakdown(db),
        "send_rate": round(s["sent"] / processed * 100) if processed else 0,
    })


# ─────────────────────── 帳號 / 設定（admin）───────────────────────
@app.get("/accounts", response_class=HTMLResponse)
def accounts_page(request: Request, user: User = Depends(auth.require_admin),
                  db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "accounts.html", {
        "user": user,
        "threads_accounts": crud.list_threads_accounts(db),
        "users": crud.list_users(db), "competitors": crud.list_competitors(db),
        "config_warnings": config.validate(),
        "providers": {"scraper": config.SCRAPER_PROVIDER, "llm": config.LLM_PROVIDER},
    })


@app.post("/accounts/threads/add")
def add_threads(handle: str = Form(...), display_name: str = Form(""), notes: str = Form(""),
                user: User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    crud.add_threads_account(db, handle, display_name, notes)
    return RedirectResponse("/accounts", status_code=302)


@app.post("/accounts/threads/{acc_id}/toggle")
def toggle_threads(acc_id: int, user: User = Depends(auth.require_admin),
                   db: Session = Depends(get_db)):
    crud.toggle_threads_account(db, acc_id)
    return RedirectResponse("/accounts", status_code=302)


@app.post("/accounts/threads/{acc_id}/default")
def default_threads(acc_id: int, user: User = Depends(auth.require_admin),
                    db: Session = Depends(get_db)):
    crud.set_default_account(db, acc_id)
    return RedirectResponse("/accounts", status_code=302)


@app.post("/accounts/users/add")
def add_user(email: str = Form(...), name: str = Form(""), password: str = Form(...),
             role: str = Form("member"), user: User = Depends(auth.require_admin),
             db: Session = Depends(get_db)):
    if not crud.get_user_by_email(db, email):
        crud.create_user(db, email, name, auth.hash_password(password), role)
    return RedirectResponse("/accounts", status_code=302)


@app.post("/competitors/add")
def add_comp(handle: str = Form(...), user: User = Depends(auth.require_admin),
             db: Session = Depends(get_db)):
    crud.add_competitor(db, handle)
    return RedirectResponse("/accounts", status_code=302)


@app.post("/competitors/{comp_id}/remove")
def remove_comp(comp_id: int, user: User = Depends(auth.require_admin),
                db: Session = Depends(get_db)):
    crud.remove_competitor(db, comp_id)
    return RedirectResponse("/accounts", status_code=302)


# ─────────────────────── 觸發 pipeline ───────────────────────
@app.post("/tasks/run")
def trigger_pipeline(request: Request, limit: int = 0, reanalyze: bool = False,
                     db: Session = Depends(get_db)):
    """兩種方式可觸發:
       1) 登入嘅 admin(由審核台撳「立即爬文」)
       2) Cloud Scheduler 帶 header X-Pipeline-Token = PIPELINE_TOKEN
    """
    token = request.headers.get("X-Pipeline-Token", "")
    authorized = bool(config.PIPELINE_TOKEN) and token == config.PIPELINE_TOKEN
    if not authorized:
        uid = request.session.get("user_id")
        u = db.get(User, uid) if uid else None
        authorized = bool(u and u.role == "admin")
    if not authorized:
        raise HTTPException(status_code=403, detail="冇權限觸發 pipeline")

    result = pipeline.run_pipeline(db, limit=limit, reanalyze=reanalyze)
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return result


def _qs(request: Request) -> str:
    """保留 dashboard 嘅篩選參數(redirect 返去同一畫面)。"""
    keep = {k: v for k, v in request.query_params.items()
            if k in ("status", "min_score", "subject", "search")}
    return "&".join(f"{k}={v}" for k, v in keep.items())
