import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
from loader import pick_run, update_decision

st.set_page_config(page_title="机会矩阵与产品概念", layout="wide")
insight = pick_run()
if insight is None:
    st.stop()

if insight.get("_status") == "pending":
    st.warning("⏳ 当前 run 还没有 insight.json。请到『立项概念输入』查看 skill 调用提示词并去 Claude Code 跑。")
    st.stop()

st.title("机会矩阵与产品概念 · PM 决策台")
st.caption(
    "气泡图（综合对比） → 全部机会（按综合分 / 按行业分组可切换）。"
    "每条机会底部可标注 PM 判断 / 备注 / 覆盖打分 / 加入立项候选篮——所有改动实时落盘。"
)

opps_all = insight.get("opportunities", [])
if not opps_all:
    st.info("无机会数据。")
    st.stop()

SLUG = insight.get("_slug", "")
decisions = st.session_state.get("decisions", {})
top_picks_list = insight.get("top_picks", [])
top_titles = set(top_picks_list)


def _top_rank(title):
    """返回 Top 排名（1-based），不在 Top 中返回 None。"""
    try:
        return top_picks_list.index(title) + 1
    except ValueError:
        return None


def _eff(o):
    """优先 PM 覆盖分，否则用分析师分。"""
    dec = decisions.get(o.get("title", ""), {})
    ov = dec.get("override_score")
    if ov:
        return ov.get("value", 0), ov.get("feasibility", 0), ov.get("differentiation", 0), True
    return o.get("value", 0), o.get("feasibility", 0), o.get("differentiation", 0), False


# ── 过滤：按侧栏候选行业 ─────────────────────────────
selected = st.session_state.get("selected_industries", [])
all_inds = [i.get("name", "") for i in insight.get("industries", [])]
if selected and len(selected) < len(all_inds):
    opps = [o for o in opps_all if any(s in o.get("from_industry", "") for s in selected)]
    st.info(
        f"已按侧栏候选过滤：{len(selected)}/{len(all_inds)} 行业　·　"
        f"机会 {len(opps)}/{len(opps_all)}"
    )
else:
    opps = opps_all
    st.caption(
        f"显示全部 {len(opps)} 条机会"
        f"（候选行业 {len(selected) if selected else len(all_inds)}/{len(all_inds)}）"
    )

if not opps:
    st.warning("过滤后无条目；请在侧栏调整候选行业。")
    st.stop()


# ── 气泡图（综合对比，用 effective score）────────────
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

rows = []
for idx, o in enumerate(opps):
    v, f, d, ov = _eff(o)
    dec = decisions.get(o.get("title", ""), {})
    num = CIRCLED[idx] if idx < len(CIRCLED) else f"{idx+1}"
    rows.append({
        "编号": num,
        "title": o.get("title", "—"),
        "from_industry": o.get("from_industry", "—"),
        "mechanism": o.get("mechanism", "—"),
        "value": v, "feasibility": f, "differentiation": d,
        "综合分": v * f * d,
        "类型": "红海" if o.get("is_red_ocean") else "蓝海",
        "Top": "★ Top" if o.get("title") in top_titles else "",
        "🧺": "已入篮" if dec.get("in_basket") else "",
        "PM覆盖": "PM" if ov else "",
    })
df = pd.DataFrame(rows)

fig = px.scatter(
    df,
    x="feasibility", y="value", size="differentiation",
    color="类型", color_discrete_map={"蓝海": "#5E35B1", "红海": "#FF8C42"},
    hover_data={
        "编号": True, "title": True, "from_industry": True, "mechanism": True,
        "综合分": True, "Top": True, "🧺": True, "PM覆盖": True,
        "value": False, "feasibility": False, "differentiation": True, "类型": False,
    },
    text="编号", size_max=45,
)
fig.update_traces(textposition="middle center", textfont=dict(size=16, color="white"))
fig.update_layout(
    xaxis=dict(title="可行性 →", range=[0.5, 5.5], dtick=1, gridcolor="#E8E0F5"),
    yaxis=dict(title="增量价值 →", range=[0.5, 5.5], dtick=1, gridcolor="#E8E0F5"),
    height=520, plot_bgcolor="#FFFFFF", paper_bgcolor="#F8F5FF",
    legend=dict(orientation="h", y=-0.12),
)
st.plotly_chart(fig, use_container_width=True)

# 序号 → 标题对照（紧贴气泡图，默认展开） ──
with st.expander("📑 序号 → 机会对照（hover 气泡也能看）", expanded=True):
    legend_df = df[["编号", "title", "from_industry", "综合分", "类型", "Top", "🧺", "PM覆盖"]].rename(
        columns={"title": "机会", "from_industry": "来源行业"}
    )
    st.dataframe(legend_df, use_container_width=True, hide_index=True, height=min(38 + 35 * len(df), 320))
st.caption("分数已含 PM 覆盖打分（如有）；🧺=已入立项篮。鼠标悬停气泡看完整信息。")

with st.expander("排序总表（按综合分）", expanded=False):
    show = df.sort_values("综合分", ascending=False)[
        ["Top", "🧺", "PM覆盖", "title", "from_industry", "mechanism",
         "value", "feasibility", "differentiation", "综合分", "类型"]
    ].rename(columns={
        "title": "机会", "from_industry": "来源行业", "mechanism": "底层机制",
        "value": "价值", "feasibility": "可行性", "differentiation": "差异化",
    })
    st.dataframe(show, use_container_width=True, hide_index=True)

st.markdown("---")


# ── PM 控件回调 ──────────────────────────────────────
def _safe_key(title):
    return f"{SLUG[:8]}_{abs(hash(title)) % (10**10)}"


def _on_verdict_change(title):
    k = f"verdict_{_safe_key(title)}"
    val = st.session_state.get(k, "") or ""
    update_decision(SLUG, title, verdict=val if val else None)


def _on_basket_change(title):
    k = f"basket_{_safe_key(title)}"
    val = bool(st.session_state.get(k, False))
    update_decision(SLUG, title, in_basket=val)


def _on_note_change(title):
    k = f"note_{_safe_key(title)}"
    val = (st.session_state.get(k, "") or "").strip()
    update_decision(SLUG, title, note=val or None)


def _on_override(title):
    sk = _safe_key(title)
    v = st.session_state.get(f"ovv_{sk}")
    f = st.session_state.get(f"ovf_{sk}")
    d = st.session_state.get(f"ovd_{sk}")
    if v and f and d:
        update_decision(
            SLUG, title,
            override_score={"value": int(v), "feasibility": int(f), "differentiation": int(d)},
        )


# ── 高亮框工具函数 ──────────────────────────────────
def _chip(label, value, bg, fg):
    """短字段（行内）：圆角胶囊。"""
    safe = (value or "—").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f"<span style='display:inline-block;background:{bg};color:{fg};"
        f"padding:4px 12px;border-radius:14px;font-size:13px;margin:2px 6px 2px 0;"
        f"line-height:1.5;border:1px solid {fg}22'>"
        f"<span style='opacity:0.75;margin-right:6px;font-weight:600'>{label}</span>"
        f"{safe}</span>"
    )


def _callout(label, value, bg, border, label_color="#666"):
    """长字段（块级）：左侧 accent 边 + 浅色底。"""
    safe = (value or "—").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f"<div style='background:{bg};border-left:3px solid {border};"
        f"padding:10px 14px;border-radius:4px;margin:6px 0 10px 0'>"
        f"<div style='color:{label_color};font-size:12px;margin-bottom:4px;"
        f"font-weight:600;letter-spacing:0.3px'>{label}</div>"
        f"<div style='color:#1A1A1A;font-size:14px;line-height:1.65'>{safe}</div>"
        f"</div>"
    )


# 配色（浅紫商务风为主，4 个 concept_detail 各自区分）
COLORS = {
    "industry": ("#F0EAFA", "#5E35B1"),   # 紫
    "mechanism": ("#E0F2F1", "#00796B"),  # 青
    "transfer": ("#F8F5FF", "#5E35B1"),   # 浅紫
    "ingredients": ("#FFF8E1", "#F57C00"),  # 食材黄
    "tech": ("#E3F2FD", "#1976D2"),       # 蓝
    "form": ("#F3E5F5", "#7B1FA2"),       # 深紫
    "trust": ("#E8F5E9", "#2E7D32"),      # 绿
}


def render_concept_detail(cd):
    if not cd:
        st.caption("尚未填写 concept_detail；真跑结果会自动带上。")
        return
    l, r = st.columns(2)
    bg, br = COLORS["ingredients"]
    with l:
        st.markdown(_callout("成分", cd.get("ingredients"), bg, br), unsafe_allow_html=True)
        bg2, br2 = COLORS["form"]
        st.markdown(_callout("产品形态", cd.get("product_form"), bg2, br2), unsafe_allow_html=True)
    with r:
        bg3, br3 = COLORS["tech"]
        st.markdown(_callout("技术 / 工艺", cd.get("tech"), bg3, br3), unsafe_allow_html=True)
        bg4, br4 = COLORS["trust"]
        st.markdown(_callout("信任背书方式", cd.get("trust_backing"), bg4, br4), unsafe_allow_html=True)


VERDICT_OPTS = ["", "agree", "doubt", "pass"]
VERDICT_LABELS = {"": "未表态", "agree": "✅ 赞同", "doubt": "❓ 质疑", "pass": "❌ pass"}


def render_pm_controls(o):
    title = o.get("title", "")
    dec = decisions.get(title, {})
    sk = _safe_key(title)

    st.markdown("##### 🎯 PM 决策")
    c1, c2 = st.columns([3, 1])
    with c1:
        cur_v = dec.get("verdict") or ""
        if cur_v not in VERDICT_OPTS:
            cur_v = ""
        st.radio(
            "判断", options=VERDICT_OPTS,
            format_func=lambda x: VERDICT_LABELS[x],
            index=VERDICT_OPTS.index(cur_v),
            key=f"verdict_{sk}",
            horizontal=True,
            on_change=_on_verdict_change, args=(title,),
            label_visibility="collapsed",
        )
    with c2:
        st.checkbox(
            "🧺 加入立项篮",
            value=bool(dec.get("in_basket")),
            key=f"basket_{sk}",
            on_change=_on_basket_change, args=(title,),
        )

    st.text_area(
        "PM 备注（为什么 / 怎么落 / 要验证啥 — 会进 onepager）",
        value=dec.get("note") or "",
        key=f"note_{sk}",
        on_change=_on_note_change, args=(title,),
        height=68, placeholder="可选；导出立项一页纸时会带上",
    )

    ov = dec.get("override_score") or {}
    has_ov = bool(ov)
    with st.expander(
        ("🎚 PM 覆盖打分（已覆盖）" if has_ov else "🎚 PM 覆盖打分"),
        expanded=has_ov,
    ):
        oc1, oc2, oc3 = st.columns(3)
        with oc1:
            st.slider("增量价值", 1, 5,
                      value=int(ov.get("value", o.get("value", 3) or 3)),
                      key=f"ovv_{sk}", on_change=_on_override, args=(title,))
        with oc2:
            st.slider("可行性", 1, 5,
                      value=int(ov.get("feasibility", o.get("feasibility", 3) or 3)),
                      key=f"ovf_{sk}", on_change=_on_override, args=(title,))
        with oc3:
            st.slider("差异化", 1, 5,
                      value=int(ov.get("differentiation", o.get("differentiation", 3) or 3)),
                      key=f"ovd_{sk}", on_change=_on_override, args=(title,))
        if has_ov:
            st.caption(
                f"分析师原评：v{o.get('value','?')} f{o.get('feasibility','?')} d{o.get('differentiation','?')}　·　"
                f"PM 覆盖中"
            )
            if st.button("恢复分析师评分", key=f"clear_ov_{sk}"):
                update_decision(SLUG, title, override_score=None)
                st.rerun()


def render_opportunity(o, expanded=False):
    if not o:
        return
    title = o.get("title", "—")
    dec = decisions.get(title, {})
    v, f, d, has_ov = _eff(o)
    rank = _top_rank(title)

    badges = []
    if rank:
        badges.append(f"★{rank}")
    if dec.get("in_basket"):
        badges.append("🧺")
    if dec.get("verdict") == "agree":
        badges.append("✅")
    elif dec.get("verdict") == "doubt":
        badges.append("❓")
    elif dec.get("verdict") == "pass":
        badges.append("❌")
    if has_ov:
        badges.append("PM")
    head = f"{' '.join(badges)} {title}　·　综合 {v * f * d}"

    with st.expander(head.strip(), expanded=expanded):
        m = st.columns(4)
        m[0].metric("增量价值", v); m[1].metric("可行性", f)
        m[2].metric("差异化", d); m[3].metric("综合分", v * f * d)
        if has_ov:
            st.caption(
                f"_(PM 覆盖；分析师原评 v{o.get('value','?')} f{o.get('feasibility','?')} d{o.get('differentiation','?')})_"
            )
        if o.get("is_red_ocean"):
            st.warning("红海机会 · 价值高但易被竞品照抄")

        # 行内 chip：来源行业 + 底层机制
        bg_i, fg_i = COLORS["industry"]
        bg_m, fg_m = COLORS["mechanism"]
        st.markdown(
            _chip("来源行业", o.get("from_industry"), bg_i, fg_i)
            + _chip("底层机制", o.get("mechanism"), bg_m, fg_m),
            unsafe_allow_html=True,
        )

        # 块级 callout：迁移要点
        bg_t, br_t = COLORS["transfer"]
        st.markdown(_callout("迁移要点", o.get("transfer_note"), bg_t, br_t), unsafe_allow_html=True)

        st.markdown("**产品概念方向**")
        render_concept_detail(o.get("concept_detail"))
        if o.get("taboo"):
            st.error(f"禁区 / 风险：{o['taboo']}")

        st.markdown("---")
        render_pm_controls(o)


# ── 候选行业的全部机会 ───────────────────────────────
st.markdown("## 候选行业的全部机会")
st.caption("★1/★2/★3=分析师 Top 排名｜🧺=已入立项篮｜✅❓❌=PM 判断｜PM=已覆盖打分　·　默认只展开 ★1，其他点击展开")

mode = st.radio(
    "排列方式",
    ["按综合分", "按行业分组"],
    horizontal=True,
    label_visibility="collapsed",
)

if mode == "按综合分":
    opps_sorted = sorted(
        opps, key=lambda o: -(_eff(o)[0] * _eff(o)[1] * _eff(o)[2])
    )
    for o in opps_sorted:
        # Top picks 默认展开，其他折叠
        render_opportunity(o, expanded=(top_picks_list and o.get("title") == top_picks_list[0]))
else:
    ind_by_name = {i["name"]: i for i in insight.get("industries", [])}
    display_inds = [n for n in all_inds if n in (selected or all_inds)]
    for ind_name in display_inds:
        ind = ind_by_name.get(ind_name)
        if not ind:
            continue
        related = sorted(
            [o for o in opps if ind_name in o.get("from_industry", "")],
            key=lambda x: -(_eff(x)[0] * _eff(x)[1] * _eff(x)[2]),
        )
        if not related:
            continue
        st.markdown(f"### {ind_name}　·　{len(related)} 条")
        st.caption(f"借鉴焦点：{ind.get('borrow', '—')}")
        for o in related:
            render_opportunity(o, expanded=(top_picks_list and o.get("title") == top_picks_list[0]))

# ── 底部提示 → 立项篮 ────────────────────────────────
st.markdown("---")
basket_n = sum(1 for v in decisions.values() if v.get("in_basket"))
if basket_n:
    st.success(f"🧺 立项篮中有 **{basket_n}** 条机会 — 去『立项篮』页一键导出 onepager.md")
else:
    st.info("勾选机会的 🧺 加入立项篮，在『立项篮』页可一键导出 PM 立项一页纸（onepager.md）。")
