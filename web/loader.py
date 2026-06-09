"""跨行业洞察 web — 共享数据加载层。"""
from pathlib import Path
import json
from datetime import datetime
import streamlit as st

RUNS_DIR = Path("~/AI/cross-industry-insight/runs").expanduser()
DECISIONS_FILE = "decisions.json"
INPUT_FILE = "input.json"
INSIGHT_FILE = "insight.json"
PROMPT_FILE = "_prompt.md"


_SIDEBAR_CSS = """
<style>
/* ── 侧栏整体：浅紫渐变 + 右侧细边 ─────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F8F5FF 0%, #FFFFFF 55%);
    border-right: 1px solid #E0D6F2;
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 0.8rem; }

/* ── 顶部品牌徽标（注入到导航上方） ─────────────────────── */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"]::before {
    content: "🌐  跨行业洞察 · PM 立项 App";
    display: block;
    padding: 14px 16px;
    margin: 4px 10px 14px 10px;
    font-size: 12.5px;
    font-weight: 700;
    letter-spacing: 0.3px;
    color: #5E35B1;
    background: linear-gradient(135deg, #EDE3FA 0%, #FFFFFF 100%);
    border-left: 3px solid #5E35B1;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(94,53,177,0.08);
}

/* ── 导航容器 ─────────────────────────────────────────── */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul {
    padding: 0 10px;
}

/* 单个导航链接：卡片化 */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li {
    margin: 4px 0;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a {
    padding: 10px 14px !important;
    border-radius: 8px !important;
    border: 1px solid #E6DDF5 !important;
    background: rgba(255,255,255,0.75);
    box-shadow: 0 1px 2px rgba(94,53,177,0.04);
    transition: all 0.15s ease;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a:hover {
    background: #F0EAFA !important;
    border-color: #C9B8E8 !important;
    transform: translateX(2px);
}

/* 选中态（覆盖多种 streamlit 版本的 selector） */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a[aria-current="page"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li[aria-current="page"] > a,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li.st-emotion-cache-active a {
    background: linear-gradient(135deg, #5E35B1 0%, #7E57C2 100%) !important;
    border-color: #5E35B1 !important;
    box-shadow: 0 3px 10px rgba(94,53,177,0.28) !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a[aria-current="page"] *,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li[aria-current="page"] > a * {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

/* ── 自定义区分隔线：浅紫虚线 ──────────────────────────── */
section[data-testid="stSidebar"] hr {
    border: none;
    border-top: 1px dashed #D9CFEE;
    margin: 14px 6px;
}

/* ── selectbox / multiselect：紫边 + hover 阴影 ───────── */
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    border: 1.5px solid #D9CFEE !important;
    border-radius: 8px !important;
    background: #FFFFFF !important;
    transition: all 0.15s ease;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div:hover {
    border-color: #7E57C2 !important;
    box-shadow: 0 2px 8px rgba(94,53,177,0.12) !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within {
    border-color: #5E35B1 !important;
    box-shadow: 0 0 0 3px rgba(94,53,177,0.12) !important;
}

/* ── multiselect 选中标签：浅紫胶囊 ────────────────────── */
section[data-testid="stSidebar"] [data-baseweb="tag"] {
    background: #EDE3FA !important;
    color: #4527A0 !important;
    border-radius: 12px !important;
}

/* ── 侧栏 label 加点重量 ───────────────────────────────── */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    font-weight: 600 !important;
    color: #4A3870 !important;
}
</style>
"""


def inject_sidebar_style():
    """注入侧栏视觉样式。每次 pick_run 时调用（幂等）。"""
    st.markdown(_SIDEBAR_CSS, unsafe_allow_html=True)


def list_runs():
    """返回 [(slug, label, path, is_demo, status)]，按 mtime 倒序。

    status:
      - "ready"   : 有 insight.json
      - "pending" : 仅有 input.json（PM 已录入，等 skill 跑）
    """
    if not RUNS_DIR.exists():
        return []
    out = []
    for d in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        insight_path = d / INSIGHT_FILE
        input_path = d / INPUT_FILE
        if insight_path.exists():
            out.append((d.name, _label(d.name, "ready"), insight_path, d.name.startswith("demo-"), "ready"))
        elif input_path.exists():
            out.append((d.name, _label(d.name, "pending"), input_path, False, "pending"))
    return out


def _label(slug, status):
    base = slug[5:] if slug.startswith("demo-") else slug
    parts = base.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 8:
        name, d = parts[0], parts[1]
        date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    else:
        name, date = base, ""
    pfx = "[DEMO] " if slug.startswith("demo-") else ""
    sfx = "  ⏳ 待生成" if status == "pending" else ""
    body = f"{pfx}{name}  ·  {date}" if date else f"{pfx}{name}"
    return f"{body}{sfx}"


def make_slug(concept: str) -> str:
    """concept → kebab-slug-YYYYMMDD"""
    import re
    base = re.sub(r"[\s_/]+", "-", concept.strip().lower())
    base = re.sub(r"[^\w一-鿿\-]+", "", base)[:40] or "untitled"
    date = datetime.now().strftime("%Y%m%d")
    return f"{base}-{date}"


def run_dir(slug: str) -> Path:
    return RUNS_DIR / slug


def load_input(slug: str) -> dict:
    p = run_dir(slug) / INPUT_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_input(slug: str, data: dict) -> Path:
    d = run_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    p = d / INPUT_FILE
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def write_prompt(slug: str, data: dict) -> Path:
    """生成给 PM 复制到 Claude Code 的 skill 调用提示词。"""
    d = run_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    p = d / PROMPT_FILE
    concept = data.get("concept", "")
    weakness = data.get("current_weakness", "")
    user_ = data.get("user", "")
    objective = data.get("objective", "")
    args = " | ".join(x for x in [concept, weakness, user_, objective] if x)
    body = f"""# Skill 调用提示词

复制下面整段到 Claude Code（确保已在新会话里）：

```
请用 cross-industry-insight skill 处理这个升级立项，run slug 必须用 `{slug}`（覆盖默认日期 slug）：

ARGUMENTS: {args}

baseline 已由 PM 在 web 端确定：
- 现款产品：{data.get('current_product', '—')}
- 现款短板 / 升级诉求：{weakness or '—'}
- 决策人：{data.get('decision_maker', '—')}
- 使用者：{user_ or '—'}
- 长期目标：{objective or '—'}

请把最终 insight.json 写到 ~/AI/cross-industry-insight/runs/{slug}/insight.json。
跑完告诉我，我去 web 端 8504 看产物 + 在『立项候选篮』导出 onepager。
```

完成条件：`runs/{slug}/insight.json` 落盘。Dashboard 会自动检测到。
"""
    p.write_text(body, encoding="utf-8")
    return p


def load_decisions(slug: str) -> dict:
    if not slug:
        return {}
    p = run_dir(slug) / DECISIONS_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_decisions(slug: str, decisions: dict) -> Path:
    if not slug:
        return None
    d = run_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    p = d / DECISIONS_FILE
    p.write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def update_decision(slug: str, title: str, **fields) -> None:
    """合并字段到指定机会的决策记录并落盘。值为 None 时移除该字段。"""
    decs = st.session_state.get("decisions") or load_decisions(slug)
    rec = decs.setdefault(title, {})
    for k, v in fields.items():
        if v is None:
            rec.pop(k, None)
        else:
            rec[k] = v
    rec["updated_at"] = datetime.now().isoformat(timespec="seconds")
    st.session_state.decisions = decs
    save_decisions(slug, decs)


def pick_run():
    """侧边栏 run 选择器 + baseline 摘要，返回 insight dict（无 run 时 None）。

    返回结构：
      - ready  : 完整 insight.json + 注入 _slug / _is_demo / _status='ready'
      - pending: {"_status":"pending", "_slug":slug, "baseline":{...来自 input.json}, "concept":..., "_input":input_dict}
    """
    inject_sidebar_style()
    runs = list_runs()
    if not runs:
        st.sidebar.info("尚无立项。请到『立项概念输入』新建一个。")
        return None
    labels = [r[1] for r in runs]
    slugs = [r[0] for r in runs]
    default_idx = 0
    if "run_slug" in st.session_state and st.session_state.run_slug in slugs:
        default_idx = slugs.index(st.session_state.run_slug)
    idx = st.sidebar.selectbox(
        "选择立项", options=range(len(runs)), index=default_idx,
        format_func=lambda i: labels[i],
        help="一个『立项』= 一次完整的概念→洞察→决策→导 onepager 流程，对应 runs/<slug>/ 下的产物",
    )
    slug, _label_, path, is_demo, status = runs[idx]
    st.session_state.run_slug = slug
    # 切 run 时清掉旧 decisions 缓存
    if st.session_state.get("decisions_slug") != slug:
        st.session_state.decisions = load_decisions(slug)
        st.session_state.decisions_slug = slug

    if status == "pending":
        input_data = load_input(slug)
        insight = {
            "_status": "pending",
            "_slug": slug,
            "_is_demo": False,
            "_input": input_data,
            "concept": input_data.get("concept", "—"),
            "generated_at": "（待生成）",
            "baseline": {
                "current_product": input_data.get("current_product", "—"),
                "current_weakness": input_data.get("current_weakness", "—"),
                "decision_maker": input_data.get("decision_maker", "—"),
                "user": input_data.get("user", "—"),
            },
            "mother_needs": input_data.get("mother_needs", []),
            "industries": [],
            "opportunities": [],
            "top_picks": [],
        }
        _render_concept_card(
            insight.get("concept", "—"),
            status_tag="待生成",
            status_note="跑完 skill 后此立项自动变 ready",
        )
        return insight

    with open(path, encoding="utf-8") as f:
        insight = json.load(f)
    insight["_slug"] = slug
    insight["_is_demo"] = is_demo
    insight["_status"] = "ready"
    _render_concept_card(
        insight.get("concept", "—"),
        gen_date=insight.get("generated_at", "—"),
        status_tag="DEMO 占位" if is_demo else None,
        status_note="待真跑替换" if is_demo else None,
    )
    _render_baseline_card(insight.get("baseline", {}))

    # PM 决策计数 → 立项候选篮 metric 卡
    decs = st.session_state.get("decisions", {})
    basket_n = sum(1 for v in decs.values() if v.get("in_basket"))
    _render_basket_metric(basket_n)

    # 对标行业筛选 multi-select：机会矩阵 / 产品概念 的过滤源
    industries = insight.get("industries", [])
    all_names = [ind.get("name", "") for ind in industries]
    if all_names:
        st.sidebar.markdown("---")
        if "selected_industries" not in st.session_state:
            st.session_state.selected_industries = all_names
        # 若切了立项，行业名变了 → 把 state 里不存在的剔掉
        st.session_state.selected_industries = [
            n for n in st.session_state.selected_industries if n in all_names
        ] or all_names
        st.sidebar.multiselect(
            "对标行业筛选",
            options=all_names,
            key="selected_industries",
            help="勾选哪些行业纳入下游『机会矩阵与产品概念』页。默认全选。",
        )
    return insight


# ───────────────────────────────────────────────────────────
#  侧栏卡片渲染 helper
# ───────────────────────────────────────────────────────────

def _esc(s):
    return (s or "—").replace("<", "&lt;").replace(">", "&gt;")


def _render_concept_card(concept, gen_date=None, status_tag=None, status_note=None):
    """立项概念卡片（紫渐变 + 大字概念 + 日期/状态副信息）。"""
    concept_safe = _esc(concept)
    tag_html = ""
    if status_tag:
        tag_html = (
            f"<span style='display:inline-block;background:#FFF3CD;color:#856404;"
            f"font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;"
            f"margin-left:6px;vertical-align:middle'>⏳ {_esc(status_tag)}</span>"
        )

    meta_html = ""
    if gen_date:
        meta_html = (
            f"<div style='font-size:11px;color:#999;margin-top:8px'>"
            f"📅 分析于 {_esc(gen_date)}"
            f"</div>"
        )
    if status_note:
        meta_html += (
            f"<div style='font-size:11px;color:#856404;margin-top:6px;font-style:italic'>"
            f"{_esc(status_note)}"
            f"</div>"
        )

    st.sidebar.markdown(
        f"<div style='background:linear-gradient(135deg,#EDE3FA 0%,#FFFFFF 100%);"
        f"border:1px solid #D9CFEE;border-left:3px solid #5E35B1;"
        f"border-radius:10px;padding:14px 16px;margin:10px 0 6px 0;"
        f"box-shadow:0 1px 3px rgba(94,53,177,0.08)'>"
        f"<div style='font-size:10.5px;color:#7E57C2;font-weight:700;"
        f"letter-spacing:0.8px;text-transform:uppercase'>立项概念{tag_html}</div>"
        f"<div style='font-size:15px;color:#1A1A1A;font-weight:600;"
        f"margin-top:5px;line-height:1.4'>{concept_safe}</div>"
        f"{meta_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_baseline_card(b):
    """现状基线卡片 — 4 行紧凑 label+value。"""
    def _row(label, value, last=False):
        border = "" if last else "border-bottom:1px dashed #F0EAFA;"
        return (
            f"<div style='display:flex;align-items:flex-start;gap:10px;"
            f"padding:7px 0;{border}'>"
            f"<span style='flex:0 0 44px;font-size:11px;color:#7E57C2;"
            f"font-weight:600;padding-top:2px'>{label}</span>"
            f"<span style='flex:1;font-size:12.5px;color:#333;line-height:1.55'>"
            f"{_esc(value)}</span>"
            f"</div>"
        )

    rows = (
        _row("现款", b.get("current_product", "—"))
        + _row("短板", b.get("current_weakness", "—"))
        + _row("决策人", b.get("decision_maker", "—"))
        + _row("使用者", b.get("user", "—"), last=True)
    )

    st.sidebar.markdown(
        f"<div style='background:#FFFFFF;border:1px solid #E6DDF5;border-radius:10px;"
        f"padding:10px 14px 6px;margin:10px 0;box-shadow:0 1px 2px rgba(94,53,177,0.04)'>"
        f"<div style='font-size:10.5px;color:#7E57C2;font-weight:700;"
        f"letter-spacing:0.8px;text-transform:uppercase;margin-bottom:2px'>"
        f"📋 现状基线</div>"
        f"{rows}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_basket_metric(n):
    """立项候选篮 metric 卡片。n=0 时显示空态。"""
    if n > 0:
        st.sidebar.markdown(
            f"<div style='background:linear-gradient(135deg,#5E35B1 0%,#7E57C2 100%);"
            f"color:#FFFFFF;border-radius:10px;padding:12px 16px;margin:12px 0;"
            f"box-shadow:0 3px 10px rgba(94,53,177,0.25);"
            f"display:flex;align-items:center;justify-content:space-between'>"
            f"<div>"
            f"<div style='font-size:10.5px;opacity:0.9;font-weight:700;"
            f"letter-spacing:0.8px;text-transform:uppercase'>立项候选篮</div>"
            f"<div style='font-size:11.5px;opacity:0.95;margin-top:2px'>已勾选机会</div>"
            f"</div>"
            f"<div style='font-size:26px;font-weight:700;line-height:1'>"
            f"🧺 {n}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            f"<div style='background:#FAFAFA;border:1px dashed #D9CFEE;border-radius:10px;"
            f"padding:10px 14px;margin:12px 0;color:#999;font-size:12px;text-align:center'>"
            f"🧺 立项候选篮 · 暂无机会"
            f"</div>",
            unsafe_allow_html=True,
        )
