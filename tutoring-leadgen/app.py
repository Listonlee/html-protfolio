"""半自動審核 UI（Streamlit）。

流程:pipeline 入庫 → 你喺度睇 leads → 改 AI 草稿 → 「標記已發送」/「忽略」。
MVP 唔會自動 post（避封號）:確認後你親自去原 post 貼上回覆。

啟動:streamlit run app.py
"""
import streamlit as st

import config
import db

st.set_page_config(page_title="補習主動搵客 — 審核台", page_icon="🎯", layout="wide")

db.init_db()

st.title("🎯 補習主動搵客 — 審核台")
st.caption(
    f"Scraper: `{config.SCRAPER_PROVIDER}` ・ LLM: `{config.LLM_PROVIDER}` ・ "
    f"lead 門檻: `{config.LEAD_SCORE_THRESHOLD}`　|　半自動模式:確認後請親自去原 post 回覆"
)

# ── 統計 ──
s = db.stats()
c = st.columns(6)
c[0].metric("爬到 post", s["posts"])
c[1].metric("補習相關", s["tutoring"])
c[2].metric("同行(已避)", s["competitors"])
c[3].metric("待審核", s["pending"])
c[4].metric("已發送", s["sent"])
c[5].metric("已忽略", s["ignored"])

st.divider()

# ── 篩選 ──
left, right = st.columns([3, 1])
status = right.selectbox(
    "顯示狀態", ["pending", "sent", "ignored"],
    format_func={"pending": "⏳ 待審核", "sent": "✅ 已發送", "ignored": "🚫 已忽略"}.get,
)
min_score = right.slider("最低 lead score", 0.0, 1.0, config.LEAD_SCORE_THRESHOLD, 0.05)

leads = db.get_leads(status=status, min_score=min_score)
left.subheader(f"符合條件嘅 leads:{len(leads)} 個")

if not leads:
    st.info("暫時冇符合條件嘅 lead。試下行 `python pipeline.py` 爬多啲,或者調低門檻。")

for lead in leads:
    with st.container(border=True):
        head = st.columns([3, 1, 1])
        head[0].markdown(f"**{lead['author_handle']}**　·　[原 post 連結]({lead['url']})")
        head[1].markdown(f"科目:`{lead['subject'] or '—'}`　程度:`{lead['level'] or '—'}`")
        head[2].markdown(f"### `{lead['lead_score']:.2f}`")

        st.markdown(f"> {lead['content']}")
        st.caption(f"🤖 AI 判斷:{lead['reason']}")

        if status == "pending":
            draft = lead["final_reply"] or lead["suggested_reply"] or ""
            reply_text = st.text_area(
                "回覆草稿(可改)", value=draft, key=f"reply-{lead['post_id']}", height=100
            )
            btns = st.columns([1, 1, 3])
            if btns[0].button("✅ 標記已發送", key=f"send-{lead['post_id']}", type="primary"):
                db.update_reply(lead["post_id"], "sent", reply_text)
                st.toast("已標記發送!記得去原 post 貼上回覆 👆")
                st.rerun()
            if btns[1].button("🚫 忽略", key=f"ignore-{lead['post_id']}"):
                db.update_reply(lead["post_id"], "ignored", reply_text)
                st.toast("已忽略")
                st.rerun()
            btns[2].caption("「標記已發送」唔會自動 post;請複製上面草稿,親自去原 post 回覆(避封號)。")
        else:
            st.text_area(
                "最終回覆", value=lead["final_reply"] or "", key=f"final-{lead['post_id']}",
                height=80, disabled=True,
            )
