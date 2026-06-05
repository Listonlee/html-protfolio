"""每日 pipeline：爬文 → 去重 → LLM 分析 → 入庫。

本機跑：
    python pipeline.py

之後睇結果 / 審核：
    streamlit run app.py
"""
import config
import db
import llm
import scraper


def run():
    db.init_db()
    print(f"[pipeline] scraper={config.SCRAPER_PROVIDER}  llm={config.LLM_PROVIDER}")

    posts = scraper.fetch_posts()
    print(f"[pipeline] 爬到 {len(posts)} 條 post")

    new_count = 0
    for post in posts:
        pid = post["post_id"]
        if db.post_exists(pid):  # 去重：爬過嘅 skip
            continue

        db.insert_post(post)
        analysis, model = llm.analyze_post(post["content"])
        db.save_analysis(pid, analysis, model)
        new_count += 1

        flag = "🎯" if (
            analysis.get("intent") == "looking_for_tutor"
            and not analysis.get("is_competitor")
            and analysis.get("lead_score", 0) >= config.LEAD_SCORE_THRESHOLD
        ) else "  "
        print(f"  {flag} [{analysis.get('intent'):<18}] "
              f"score={analysis.get('lead_score'):.2f}  {post['content'][:30]}…")

    print(f"[pipeline] 新處理 {new_count} 條")
    s = db.stats()
    print(f"[pipeline] 累計:posts={s['posts']} 補習相關={s['tutoring']} "
          f"同行={s['competitors']} 待審核={s['pending']}")


if __name__ == "__main__":
    run()
