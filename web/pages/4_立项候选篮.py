import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from datetime import datetime
from loader import pick_run, update_decision, run_dir
from exporter import build_onepager

st.set_page_config(page_title="立项候选篮 · PM 工作台", layout="wide")
insight = pick_run()
if insight is None:
    st.stop()

if insight.get("_status") == "pending":
    st.warning("⏳ 当前 run 还没有 insight.json。请到『立项概念输入』查看 skill 调用提示词并去 Claude Code 跑。")
    st.stop()

SLUG = insight.get("_slug", "")
decisions = st.session_state.get("decisions", {})

st.title("🧺 立项候选篮 · PM 工作台")
st.caption("从『机会矩阵与产品概念』勾选进来的机会汇总在此 · 一键导出 PM 立项一页纸（onepager.md）。")

opps_by_title = {o["title"]: o for o in insight.get("opportunities", [])}
basket_titles = [t for t, d in decisions.items() if d.get("in_basket") and t in opps_by_title]


def _eff(o):
    dec = decisions.get(o.get("title", ""), {})
    ov = dec.get("override_score")
    if ov:
        return ov.get("value", 0), ov.get("feasibility", 0), ov.get("differentiation", 0), True
    return o.get("value", 0), o.get("feasibility", 0), o.get("differentiation", 0), False


basket = sorted(
    [opps_by_title[t] for t in basket_titles],
    key=lambda o: -(_eff(o)[0] * _eff(o)[1] * _eff(o)[2]),
)

# ── 统计区 ───────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("篮中机会", len(basket))
verdicts = [decisions.get(o["title"], {}).get("verdict") for o in basket]
c2.metric("✅ 赞同", verdicts.count("agree"))
c3.metric("❓ 质疑", verdicts.count("doubt"))
c4.metric("❌ pass", verdicts.count("pass"))

if not basket:
    st.markdown("---")
    st.info(
        "🧺 立项候选篮还空着。\n\n"
        "去【机会矩阵与产品概念】给感兴趣的机会勾选 🧺 加入篮子，回来这里一键导出 PM 立项一页纸（onepager.md）。"
    )
    cc1, cc2 = st.columns([1, 3])
    with cc1:
        st.page_link(
            "pages/3_机会矩阵与产品概念.py",
            label="🎯 去机会矩阵与产品概念页勾选",
            icon="➡️",
            use_container_width=True,
        )
    st.stop()

st.markdown("---")

# ── 导出区 ───────────────────────────────────────────
st.markdown("### 📄 导出立项一页纸")
st.caption(f"已纳入 {len(basket)} 条机会 · 下载 / 保存按钮在左 · 想核对内容点右侧展开预览")
md = build_onepager(insight, decisions)

e1, e2 = st.columns([1, 3])
with e1:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    fname = f"onepager_pm_{SLUG}_{stamp}.md"
    st.download_button(
        "⬇ 下载 onepager.md",
        data=md.encode("utf-8"),
        file_name=fname,
        mime="text/markdown",
        use_container_width=True,
        type="primary",
    )
    if st.button("💾 保存到 run 目录", use_container_width=True):
        out = run_dir(SLUG) / "onepager_pm.md"
        out.write_text(md, encoding="utf-8")
        st.success(f"✓ {out}")
with e2:
    with st.expander("📄 展开预览 onepager.md（核对内容）", expanded=False):
        st.markdown(md)

st.markdown("---")
st.markdown("### 篮中机会卡片")
st.caption("此处可调整 PM 备注 / 移出篮子；改动实时落盘。改判断 / 覆盖打分请回『机会矩阵与产品概念』页。")


def _safe_key(title):
    return f"basket_{SLUG[:8]}_{abs(hash(title)) % (10**10)}"


VERDICT_DISP = {
    "agree": ("✅ 赞同推进", "#5E35B1"),
    "doubt": ("❓ 有质疑",   "#E0A800"),
    "pass":  ("❌ 暂不推进", "#888888"),
    "":      ("未表态",      "#999999"),
    None:    ("未表态",      "#999999"),
}

for o in basket:
    title = o["title"]
    dec = decisions.get(title, {})
    v, f, d, has_ov = _eff(o)
    label, color = VERDICT_DISP.get(dec.get("verdict") or "")

    with st.container(border=True):
        h1, h2 = st.columns([3, 1])
        with h1:
            top_mark = "★ " if title in set(insight.get("top_picks", [])) else ""
            st.markdown(f"#### {top_mark}{title}")
            st.caption(f"{o.get('from_industry','—')}　·　借机制：{o.get('mechanism','—')}")
        with h2:
            st.markdown(
                f"<div style='text-align:right'>"
                f"<span style='color:{color};font-weight:600'>{label}</span><br>"
                f"<span style='color:#666;font-size:13px'>"
                f"综合 <b>{v*f*d}</b>　(v{v} f{f} d{d}{' · PM 覆盖' if has_ov else ''})</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        if dec.get("note"):
            st.info(f"📝 {dec['note']}")

        st.markdown(f"**迁移要点**：{o.get('transfer_note','—')}")
        cd = o.get("concept_detail") or {}
        if cd:
            cc1, cc2 = st.columns(2)
            with cc1:
                st.markdown(f"**成分**：{cd.get('ingredients','—')}")
                st.markdown(f"**产品形态**：{cd.get('product_form','—')}")
            with cc2:
                st.markdown(f"**技术 / 工艺**：{cd.get('tech','—')}")
                st.markdown(f"**信任背书**：{cd.get('trust_backing','—')}")
        if o.get("taboo"):
            st.error(f"禁区：{o['taboo']}")

        k_note = f"note_{_safe_key(title)}"
        new_note = st.text_area(
            "PM 备注（实时落盘 + 进 onepager）",
            value=dec.get("note") or "",
            key=k_note,
            height=68,
            placeholder="可选",
        )
        if new_note != (dec.get("note") or ""):
            update_decision(SLUG, title, note=new_note.strip() or None)

        if st.button("从篮子中移除", key=f"rm_{_safe_key(title)}"):
            update_decision(SLUG, title, in_basket=False)
            st.rerun()
