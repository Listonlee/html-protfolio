"""Pipeline:爬 → 去重 → LLM 分析 → 入庫。可由 web endpoint 或 cron script 觸發。"""
import logging

from sqlalchemy.orm import Session

from app import config, crud
from app.services import llm, scraper

log = logging.getLogger("leadgen.pipeline")


def run_pipeline(db: Session, limit: int = 0, reanalyze: bool = False) -> dict:
    competitors = crud.competitor_set(db)
    posts = scraper.fetch_posts()
    if limit:
        posts = posts[:limit]

    new = skipped = failed = leads = 0
    for post in posts:
        pid = post["post_id"]
        if not reanalyze and crud.is_analyzed(db, pid):
            skipped += 1
            continue
        try:
            analysis, model = llm.analyze_post(post["content"], post.get("author_handle"), competitors)
        except Exception as e:  # noqa: BLE001
            failed += 1
            log.error("分析失敗 %s:%s", pid, e)
            continue

        crud.upsert_post_analysis(db, post, analysis, model)
        new += 1
        if (analysis["intent"] == "looking_for_tutor" and not analysis["is_competitor"]
                and not analysis["is_advertisement"]
                and analysis["lead_score"] >= config.LEAD_SCORE_THRESHOLD):
            leads += 1

    result = {"scanned": len(posts), "new": new, "skipped": skipped, "failed": failed, "leads": leads}
    log.info("pipeline 完成:%s", result)
    return result
