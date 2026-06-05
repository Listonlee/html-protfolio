"""爬文層。提供統一 fetch_posts()，內部按 provider 切換。

mock  — 內置樣本數據（唔使 key，即刻 demo）
apify — 用 Apify Threads scraper actor 真係爬
"""
from typing import List

import config

# ── Mock 樣本：模擬 Threads 上唔同類型嘅 post ──
_MOCK_POSTS = [
    {
        "post_id": "mock-1",
        "author_handle": "@worried_mom_hk",
        "content": "個仔升中三數學跟唔上，想搵個補習老師，邊個補中學數學補得好？九龍區有冇推介？",
        "url": "https://www.threads.net/@worried_mom_hk/post/mock-1",
        "posted_at": "2026-06-05T09:12:00",
    },
    {
        "post_id": "mock-2",
        "author_handle": "@dse_fighter",
        "content": "DSE 英文 reading 好弱，求補習！想搵 native 或者經驗豐富嘅 tutor，online 都得",
        "url": "https://www.threads.net/@dse_fighter/post/mock-2",
        "posted_at": "2026-06-05T08:40:00",
    },
    {
        "post_id": "mock-3",
        "author_handle": "@best_tutor_centre",
        "content": "🔥本中心專補 DSE 數學英文，狀元師資，首堂半價！WhatsApp 9XXX XXXX 即時報名！名額有限！",
        "url": "https://www.threads.net/@best_tutor_centre/post/mock-3",
        "posted_at": "2026-06-05T08:00:00",
    },
    {
        "post_id": "mock-4",
        "author_handle": "@foodie_kelly",
        "content": "今日去咗中環食壽司，好正！推介俾大家～🍣",
        "url": "https://www.threads.net/@foodie_kelly/post/mock-4",
        "posted_at": "2026-06-05T07:30:00",
    },
    {
        "post_id": "mock-5",
        "author_handle": "@anxious_dad",
        "content": "女兒小三呈分試成績麻麻，想搵個有耐性嘅補習老師補中英數，請問點搵好？",
        "url": "https://www.threads.net/@anxious_dad/post/mock-5",
        "posted_at": "2026-06-05T07:05:00",
    },
    {
        "post_id": "mock-6",
        "author_handle": "@study_tips_daily",
        "content": "分享下我自己讀書嘅心得，其實補唔補習唔重要，最緊要係溫習方法...",
        "url": "https://www.threads.net/@study_tips_daily/post/mock-6",
        "posted_at": "2026-06-05T06:50:00",
    },
]


def fetch_posts() -> List[dict]:
    if config.SCRAPER_PROVIDER == "apify":
        return _fetch_apify()
    return _fetch_mock()


def _fetch_mock() -> List[dict]:
    return [dict(p) for p in _MOCK_POSTS]


def _fetch_apify() -> List[dict]:
    """用 Apify actor 真係爬 Threads。

    注意：唔同 actor 嘅 input/output 欄位名可能唔一樣，
    用之前要對返你揀嗰隻 actor 嘅文件調整 mapping。
    """
    from apify_client import ApifyClient

    if not config.APIFY_API_TOKEN:
        raise RuntimeError("SCRAPER_PROVIDER=apify 但未設 APIFY_API_TOKEN")

    client = ApifyClient(config.APIFY_API_TOKEN)
    run = client.actor(config.APIFY_ACTOR).call(
        run_input={
            "searchQueries": config.SEARCH_KEYWORDS,
            "resultsLimit": 100,
        }
    )

    posts = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        pid = item.get("id") or item.get("postId") or item.get("url")
        if not pid:
            continue
        posts.append(
            {
                "post_id": str(pid),
                "author_handle": item.get("ownerUsername") or item.get("username"),
                "content": item.get("text") or item.get("caption") or "",
                "url": item.get("url"),
                "posted_at": item.get("timestamp") or item.get("publishedAt"),
            }
        )
    return posts
