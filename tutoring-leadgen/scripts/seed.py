"""初始化資料庫 + 建立第一個管理員帳號。

跑:python -m scripts.seed
讀 .env / 環境變數嘅 ADMIN_EMAIL、ADMIN_PASSWORD。
可重複跑(已存在就唔會重複建立)。
"""
from app import auth, config, crud
from app.database import SessionLocal, init_db
from app.models import Competitor, ThreadsAccount


def main():
    init_db()
    db = SessionLocal()
    try:
        if not crud.get_user_by_email(db, config.ADMIN_EMAIL):
            crud.create_user(
                db, config.ADMIN_EMAIL, "Admin",
                auth.hash_password(config.ADMIN_PASSWORD), role="admin",
            )
            print(f"✅ 建立管理員:{config.ADMIN_EMAIL}")
        else:
            print(f"ℹ️  管理員已存在:{config.ADMIN_EMAIL}")

        # 範例回覆帳號 + 同行(方便即刻試)
        if not db.query(ThreadsAccount).first():
            acc = crud.add_threads_account(db, "my_tutor_hk", "我哋補習")
            crud.set_default_account(db, acc.id)
            print("✅ 建立範例 Threads 帳號:@my_tutor_hk(預設)")
        if not db.query(Competitor).first():
            crud.add_competitor(db, "best_tutor_centre")
            print("✅ 建立範例同行黑名單:@best_tutor_centre")

        print("\n完成。用上面 email + 你設嘅密碼登入。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
