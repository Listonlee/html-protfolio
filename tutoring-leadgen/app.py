"""半自動審核 UI（Streamlit）。

流程:pipeline 入庫 → 你喺度睇 leads → 改 AI 草稿 → 一鍵複製 → 開原 post 親手貼。
MVP 唔會自動 post（避封號）:確認後按「標記已發送」記錄。

啟動:streamlit run app.py
"""
import streamlit as st

import config
import db
import llm

st.set_page_config(page_title="補習主動搵客 — 審核台", page_icon="🎯", layout="wide")
db.init_db()

st.title("🎯 補習主動搵客 — 審核台")
st.caption(
    f"Scraper: `{config.SCRAPER_PROVIDER}` ・ LLM: `{config.LLM_PROVIDER}` ・ "
    f"lead 門檻: `{config.LEAD_SCORE_THRESHOLD}`　|　"
    f"半自動:確認後請親自去原 post 回覆(避封號)"
)

# ── 頂部統計 ──
s = db.stats()
c = st.columns(6)
c[0].metric("爬到 post", s["posts"])
c[1].metric("補習相關", s["tutoring"])
c[2].metric("同行(已避)", s["competitors"])
c[3].metric("待審核", s["pending"])
c[4].metric("已發送", s["sent"])
c[5].metric("已忽略", s["ignored"])

tab_review, tab_analytics, tab_settings = st.tabs(["📋 審核 leads", "📊 分析", "⚙️ 設定"])


# ─────────────────────────────────────────────────────────────
# 審核分頁
# ─────────────────────────────────────────────────────────────
with tab_review:
    f = st.columns([1.2, 1.2, 1.2, 2.4])
    status = f[0].selectbox(
        "狀態", ["pending", "sent", "ignored"],
        format_func={"pending": "⏳ 待審核", "sent": "✅ 已發送", "ignored": "🚫 已忽略"}.get,
    )
    min_score = f[1].slider("最低 score", 0.0, 1.0, config.LEAD_SCORE_THRESHOLD, 0.05)
    subjects = ["全部"] + db.lead_subjects()
    subject = f[2].selectbox("科目", subjects)
    search = f[3].text_input("🔎 搜尋內容 / 作者", "")

    leads = db.get_leads(
        status=status,
        min_score=min_score,
        subject=None if subject == "全部" else subject,
        search=search or None,
    )
    st.subheader(f"符合條件嘅 leads:{len(leads)} 個")

    if not leads:
        st.info("暫時冇符合條件嘅 lead。行 `python pipeline.py run` 爬多啲,或調低門檻。")

    for lead in leads:
        pid = lead["post_id"]
        with st.container(border=True):
            head = st.columns([3, 1.3, 0.7])
            head[0].markdown(f"**{lead['author_handle'] or '(無 handle)'}**")
            head[1].markdown(f"科目 `{lead['subject'] or '—'}`　程度 `{lead['level'] or '—'}`")
            head[2].markdown(f"### `{lead['lead_score']:.2f}`")

            st.markdown(f"> {lead['content']}")
            st.caption(f"🤖 {lead['reason']}　·　{lead['posted_at'] or ''}")

            if status == "pending":
                key = f"reply-{pid}"
                if key not in st.session_state:
                    st.session_state[key] = lead["final_reply"] or lead["suggested_reply"] or ""

                st.text_area("回覆草稿(可改)", key=key, height=90)

                # 一鍵複製:st.code 右上角自帶 copy icon
                with st.expander("📋 一鍵複製草稿"):
                    st.code(st.session_state[key], language=None)

                btns = st.columns([1, 1, 1, 1.4])
                if lead["url"]:
                    btns[0].link_button("↗ 開原 post", lead["url"], use_container_width=True)
                if btns[1].button("♻️ 重新生成", key=f"regen-{pid}", use_container_width=True):
                    a, _ = llm.analyze_post(lead["content"], lead["author_handle"])
                    st.session_state[key] = a["suggested_reply"] or st.session_state[key]
                    db.save_draft(pid, st.session_state[key])
                    st.rerun()
                if btns[2].button("✅ 已發送", key=f"send-{pid}", type="primary",
                                  use_container_width=True):
                    db.update_reply(pid, "sent", st.session_state[key])
                    st.toast("已標記發送!記得去原 post 貼上回覆 👆")
                    st.rerun()
                if btns[3].button("🚫 忽略", key=f"ignore-{pid}", use_container_width=True):
                    db.update_reply(pid, "ignored", st.session_state[key])
                    st.toast("已忽略")
                    st.rerun()
                st.caption("「已發送」唔會自動 post;請複製草稿親自去原 post 回覆(避封號)。")
            else:
                st.text_area("最終回覆", value=lead["final_reply"] or "",
                             key=f"final-{pid}", height=70, disabled=True)
                if lead["url"]:
                    st.link_button("↗ 開原 post", lead["url"])


# ─────────────────────────────────────────────────────────────
# 分析分頁
# ─────────────────────────────────────────────────────────────
with tab_analytics:
    st.subheader("意圖分佈")
    intents = db.intent_breakdown()
    if intents:
        label = {
            "looking_for_tutor": "🎯 搵補習", "selling_tutoring": "🏢 同行",
            "discussion": "💬 討論", "not_related": "➖ 無關",
        }
        st.bar_chart({label.get(k, k): v for k, v in intents.items()})
    else:
        st.info("未有數據,先行 `python pipeline.py run`。")

    st.subheader("熱門科目(搵補習)")
    subs = db.subject_breakdown()
    if subs:
        st.bar_chart(subs)
    else:
        st.caption("未有科目數據。")

    s2 = db.stats()
    total = s2["sent"] + s2["ignored"]
    if total:
        st.metric("發送率(已發送 / 已處理)", f"{s2['sent'] / total * 100:.0f}%")


# ─────────────────────────────────────────────────────────────
# 設定分頁
# ─────────────────────────────────────────────────────────────
with tab_settings:
    st.subheader("目前設定")
    st.json({
        "scraper_provider": config.SCRAPER_PROVIDER,
        "llm_provider": config.LLM_PROVIDER,
        "lead_score_threshold": config.LEAD_SCORE_THRESHOLD,
        "search_keywords": config.SEARCH_KEYWORDS,
        "results_limit": config.RESULTS_LIMIT,
    })
    st.caption("以上由 `.env` 控制,改完重新啟動 app 生效。")

    warnings = config.validate()
    if warnings:
        for w in warnings:
            st.warning(w)
    else:
        st.success("設定檢查通過 ✅")

    st.divider()
    st.subheader("🚫 同行黑名單")
    st.caption("喺呢張名單上嘅作者,即使 AI 判斷係搵補習都會被隔走。")
    comps = sorted(config.load_competitors())
    st.write(", ".join(f"@{c}" for c in comps) if comps else "(空)")
    new_comp = st.text_input("加入同行 handle", placeholder="@some_tutor_centre")
    if st.button("➕ 加入黑名單"):
        if new_comp.strip():
            config.add_competitor(new_comp)
            st.toast(f"已加入 {new_comp}")
            st.rerun()
