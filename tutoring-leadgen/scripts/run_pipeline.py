"""CLI 觸發 pipeline(畀 cron / Cloud Scheduler 用,或本機手動跑)。

跑:python -m scripts.run_pipeline
    python -m scripts.run_pipeline --limit 20 --reanalyze
"""
import argparse
import logging

from app.database import SessionLocal, init_db
from app.services import pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--reanalyze", action="store_true")
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        result = pipeline.run_pipeline(db, limit=args.limit, reanalyze=args.reanalyze)
        print("完成:", result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
