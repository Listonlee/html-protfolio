"""每日 pipeline + CLI。

用法:
    python pipeline.py run                 # 爬 → 去重 → 分析 → 入庫
    python pipeline.py run --limit 20      # 只處理頭 20 條
    python pipeline.py run --dry-run       # 只分析唔入庫(試效果)
    python pipeline.py run --reanalyze     # 連已分析過嘅都重新分析
    python pipeline.py check               # 驗證設定 + 測 Apify/LLM 連線
    python pipeline.py stats               # 睇累計統計

跑完開審核台:
    streamlit run app.py
"""
import argparse
import sys

import config
import db
import llm
import scraper

log = config.setup_logging()


def cmd_run(args):
    db.init_db()
    log.info("scraper=%s  llm=%s  dry_run=%s  reanalyze=%s",
             config.SCRAPER_PROVIDER, config.LLM_PROVIDER, args.dry_run, args.reanalyze)

    posts = scraper.fetch_posts()
    if args.limit:
        posts = posts[: args.limit]
    log.info("攞到 %d 條 post", len(posts))

    new, skipped, failed, leads = 0, 0, 0, 0
    for post in posts:
        pid = post["post_id"]
        if not args.reanalyze and db.is_analyzed(pid):
            skipped += 1
            continue
        try:
            analysis, model = llm.analyze_post(post["content"], post.get("author_handle"))
        except Exception as e:  # noqa: BLE001  單條失敗唔好搞冧成個 run
            failed += 1
            log.error("分析失敗 %s:%s", pid, e)
            continue

        is_lead = (
            analysis["intent"] == "looking_for_tutor"
            and not analysis["is_competitor"]
            and not analysis["is_advertisement"]
            and analysis["lead_score"] >= config.LEAD_SCORE_THRESHOLD
        )
        if is_lead:
            leads += 1

        if not args.dry_run:
            db.insert_post(post)
            db.save_analysis(pid, analysis, model)
        new += 1

        flag = "🎯" if is_lead else "  "
        log.info("  %s [%-18s] score=%.2f  %s",
                 flag, analysis["intent"], analysis["lead_score"], post["content"][:28])

    log.info("完成:新處理 %d ・ 跳過(已分析) %d ・ 失敗 %d ・ 當中目標客 %d",
             new, skipped, failed, leads)
    if args.dry_run:
        log.info("(dry-run:冇寫入 DB)")
    else:
        s = db.stats()
        log.info("累計:posts=%d 補習相關=%d 同行=%d 待審核=%d",
                 s["posts"], s["tutoring"], s["competitors"], s["pending"])


def cmd_check(args):
    print("🔍 檢查設定…")
    warnings = config.validate()
    if warnings:
        for w in warnings:
            print(f"  ⚠️  {w}")
    else:
        print("  ✅ 設定 OK")

    print(f"\n🕷️  Scraper provider = {config.SCRAPER_PROVIDER}")
    try:
        posts = scraper.fetch_posts()
        print(f"  ✅ 爬到 {len(posts)} 條(示例:{posts[0]['content'][:24] if posts else '—'}…)")
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ 爬文失敗:{e}")

    print(f"\n🤖 LLM provider = {config.LLM_PROVIDER}")
    try:
        a, model = llm.analyze_post("想搵個補習老師補中三數學，有冇推介？", "@test_user")
        print(f"  ✅ 分析 OK(model={model}):intent={a['intent']} score={a['lead_score']:.2f}")
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ LLM 失敗:{e}")

    comps = config.load_competitors()
    print(f"\n🚫 同行黑名單:{len(comps)} 個 → {', '.join(sorted(comps)) or '(空)'}")


def cmd_stats(args):
    db.init_db()
    s = db.stats()
    print("📊 累計統計")
    for k, label in [
        ("posts", "爬到 post"), ("tutoring", "補習相關"), ("competitors", "同行(已避)"),
        ("pending", "待審核"), ("sent", "已發送"), ("ignored", "已忽略"),
    ]:
        print(f"  {label:<12} {s[k]}")
    print("\n  意圖分佈:")
    for intent, cnt in db.intent_breakdown().items():
        print(f"    {intent:<18} {cnt}")
    sub = db.subject_breakdown()
    if sub:
        print("\n  熱門科目(搵補習):")
        for subj, cnt in sub.items():
            print(f"    {subj:<10} {cnt}")


def main():
    parser = argparse.ArgumentParser(description="補習主動搵客 pipeline")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="爬→分析→入庫")
    p_run.add_argument("--limit", type=int, default=0, help="只處理頭 N 條")
    p_run.add_argument("--dry-run", action="store_true", help="只分析唔入庫")
    p_run.add_argument("--reanalyze", action="store_true", help="連已分析嘅都重做")
    p_run.set_defaults(func=cmd_run)

    sub.add_parser("check", help="驗證設定 + 測連線").set_defaults(func=cmd_check)
    sub.add_parser("stats", help="睇累計統計").set_defaults(func=cmd_stats)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        # 預設行為 = run(向後兼容 `python pipeline.py`)
        args = parser.parse_args(["run"])
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
