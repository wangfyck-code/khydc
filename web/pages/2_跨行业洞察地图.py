import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
import urllib.parse
import streamlit as st
import pandas as pd
from loader import pick_run


# ── 品牌跳转链接 ──────────────────────────────────────────
# 用 search/列表 URL 而不是 LLM 产具体 URL，避免幻觉。
# 这一版尽量跳"品牌相关页"（天猫品牌列表 / 抖音品牌账号 / 微博官博 / 百度搜「品牌+官网」），第一条结果通常就是官方。
_SEARCH_PLATFORMS = [
    ("天猫",   "https://list.tmall.com/search_product.htm?q={q}",        "#FF4E00"),
    ("京东",   "https://search.jd.com/Search?keyword={q}&enc=utf-8",     "#E1251B"),
    ("小红书", "https://www.xiaohongshu.com/search_result?keyword={q}",  "#FF2442"),
    ("抖音号", "https://www.douyin.com/search/{q}?type=user",            "#000000"),
    ("微博号", "https://s.weibo.com/user?q={q}",                         "#E6162D"),
    ("B站",    "https://search.bilibili.com/all?keyword={q}",            "#00A1D6"),
    ("百度",   "https://www.baidu.com/s?wd={q}",                         "#2932E1"),
]


def _brand_inline_links_html(brand_name: str) -> str:
    """品牌名旁边的紧凑直跳按钮：🌐 找官网 + 📰 最新资讯。"""
    if not brand_name or brand_name == "—":
        return ""
    q = urllib.parse.quote_plus(brand_name)
    # Google "BRAND 官网" 第一条通常就是品牌官网
    url_site = f"https://www.google.com/search?q={q}+%E5%AE%98%E7%BD%91"
    # 百度新闻 + 时间排序，给最新资讯
    url_news = f"https://news.baidu.com/ns?word={q}&rn=20&from=news"
    return (
        f"<a href='{url_site}' target='_blank' rel='noopener noreferrer' "
        f"style='display:inline-block;padding:1px 9px;margin-left:8px;"
        f"font-size:10.5px;font-weight:600;color:#1976D2;"
        f"background:#E3F2FD;border:1px solid #1976D255;"
        f"border-radius:10px;text-decoration:none;vertical-align:middle'>"
        f"🌐 官网</a>"
        f"<a href='{url_news}' target='_blank' rel='noopener noreferrer' "
        f"style='display:inline-block;padding:1px 9px;margin-left:5px;"
        f"font-size:10.5px;font-weight:600;color:#E65100;"
        f"background:#FFF3E0;border:1px solid #FB8C0055;"
        f"border-radius:10px;text-decoration:none;vertical-align:middle'>"
        f"📰 资讯</a>"
    )


def _brand_search_links_html(brand_name: str) -> str:
    """生成品牌的多平台直跳链接条 HTML（天猫品牌列表/京东/小红书/抖音号/微博号/B站/百度）。"""
    if not brand_name or brand_name == "—":
        return ""
    q = urllib.parse.quote_plus(brand_name)
    chips = ""
    for name, tpl, color in _SEARCH_PLATFORMS:
        url = tpl.format(q=q)
        chips += (
            f"<a href='{url}' target='_blank' rel='noopener noreferrer' "
            f"style='display:inline-block;padding:3px 10px;margin:3px 5px 3px 0;"
            f"font-size:11px;font-weight:600;color:{color};"
            f"background:#FFFFFF;border:1px solid {color}44;"
            f"border-radius:11px;text-decoration:none;"
            f"transition:all 0.15s ease'>"
            f"🔗 {name}</a>"
        )
    return (
        f"<div style='margin-top:10px;padding-top:8px;border-top:1px dashed #E6DDF5;"
        f"display:flex;align-items:center;flex-wrap:wrap;gap:0'>"
        f"<span style='color:#7E57C2;font-size:10.5px;font-weight:700;"
        f"letter-spacing:0.5px;margin-right:8px'>🔗 直跳品牌相关页</span>"
        f"{chips}"
        f"</div>"
    )


# 行业关键词 → (emoji, iconify noto 图标名)
# emoji 用于 tab 标签（streamlit tab 不接 HTML）
# noto 用于 banner 大图标（Iconify CDN 拉彩色 SVG）
ICON_RULES = [
    # —— 第一优先：具体品类 / 形态 ——
    (r"婴幼|奶粉|母婴|宝宝|配方奶",                   "🍼", "noto:baby-bottle"),
    (r"医疗|医院|诊所|临床|特膳|术后|医学营养|医用|处方", "🏥", "noto:hospital"),
    (r"运动|健身|蛋白粉|肌肉|训练|可穿戴|健身app",     "💪", "noto:flexed-biceps"),
    (r"护肤|个护|美容|化妆|microbiome",                "✨", "noto:sparkles"),
    (r"功能性饮料|饮品|饮料|酵素|奶茶|咖啡|果汁|气泡水", "🥤", "noto:cup-with-straw"),
    (r"代餐|轻食|低卡|减脂|瘦身|体重管理",             "🥗", "noto:green-salad"),
    (r"GLP|减重|肥胖",                                  "⚖️", "noto:balance-scale"),
    (r"鲜食|预制|冷链|有机|鲜肉",                       "🥩", "noto:cut-of-meat"),
    (r"口腔|牙|洁齿",                                   "🦷", "noto:tooth"),
    (r"零食|休闲食品|烘焙",                             "🍪", "noto:cookie"),
    (r"老年|银发|抗衰",                                 "🧓", "noto:older-person"),
    (r"宠物|犬|猫|狗",                                  "🐾", "noto:paw-prints"),
    (r"App|订阅|智能|数字|平台|SaaS",                   "📱", "noto:mobile-phone"),
    # —— 兜底：通用功能词 ——
    (r"保健品|营养补充|补剂|维生素",                    "💊", "noto:pill"),
    (r"益生菌|益生元|肠道|微生态|发酵|菌株|后生元",     "🦠", "noto:microbe"),
]
DEFAULT_ICON = ("🏷", "noto:bookmark-tabs")


def _industry_icon(name: str):
    """返回 (emoji, noto_iconify_name)。"""
    if not name:
        return DEFAULT_ICON
    for pattern, emoji, noto in ICON_RULES:
        if re.search(pattern, name):
            return (emoji, noto)
    return DEFAULT_ICON


def _icon_img_html(noto_name: str, size: int = 56) -> str:
    """Iconify CDN 彩色 SVG。"""
    return (
        f"<img src='https://api.iconify.design/{noto_name}.svg' "
        f"width='{size}' height='{size}' "
        f"style='flex-shrink:0;display:block' alt='industry-icon'/>"
    )

st.set_page_config(page_title="跨行业洞察地图", layout="wide")
insight = pick_run()
if insight is None:
    st.stop()

st.title("跨行业洞察地图 · 对标行业拆解")
st.caption(
    "每个 tab：十维度当下切片 → 发展历程 → 行业现状 → 数据验证 → 可迁移机会 → **可参考借鉴**（借鉴焦点 + 宠物痛点分析）。"
    "结论放最后——前面看完了演化全貌再下结论，比一上来就说『借 X』更有说服力。"
)

industries = insight.get("industries", [])
if not industries:
    st.info("无对标行业数据。")
    st.stop()

DIM_LABELS = {
    "pain_point": "🎯 用户想解决什么问题",
    "target_user": "👥 谁会买，买给谁用",
    "narrative": "💬 怎么跟用户讲故事",
    "ingredient_tech": "🧪 用什么成分/技术做",
    "product_form": "📦 长什么样（剂型/包装）",
    "evidence": "🔬 凭什么让人信（数据/认证）",
    "price_band": "💰 卖多少钱",
    "business_model": "🏪 在哪卖、怎么卖",
    "competitors": "🏆 头部品牌都是谁",
    "regulation": "⚠️ 不能碰的红线",
}

# 三组分类：用户视角 / 产品视角 / 商业视角
DIM_GROUPS = [
    {
        "title": "👤 用户视角",
        "hint": "对标的是谁、解决什么问题、用什么话术沟通",
        "color": "#1976D2",
        "bg": "#E3F2FD",
        "keys": ["pain_point", "target_user", "narrative"],
    },
    {
        "title": "🧬 产品视角",
        "hint": "成分工艺、产品形态、信任背书三件套——做啥东西、长啥样、凭啥让人信",
        "color": "#7B1FA2",
        "bg": "#F3E5F5",
        "keys": ["ingredient_tech", "product_form", "evidence"],
    },
    {
        "title": "💼 商业视角",
        "hint": "定价、渠道、竞品、监管——卖多少钱、在哪卖、谁占了山头、什么不能碰",
        "color": "#2E7D32",
        "bg": "#E8F5E9",
        "keys": ["price_band", "business_model", "competitors", "regulation"],
    },
]


def render_borrow(ind):
    borrow = ind.get("borrow", "—")
    link = ind.get("pet_pain_link", "")
    st.markdown("### 可参考借鉴")
    html = (
        f"<div style='padding:18px 22px;border-radius:8px;"
        f"background:#FFF4E6;border-left:4px solid #FF8C42;line-height:1.7'>"
        f"<div style='color:#888;font-size:13px;margin-bottom:6px'>借鉴焦点</div>"
        f"<div style='color:#1A1A1A;font-size:16px;font-weight:600;"
        f"margin-bottom:16px'>{borrow}</div>"
    )
    if link:
        html += (
            f"<div style='border-top:1px dashed #EAD2B5;padding-top:14px'>"
            f"<div style='color:#888;font-size:13px;margin-bottom:6px'>"
            f"基于宠物行业痛点的分析</div>"
            f"<div style='color:#333;font-size:14px'>{link}</div>"
            f"</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_dimensions(ind):
    """十维度按 用户/产品/商业 三视角分组渲染，每组带『看这组为了啥』提示。"""
    st.markdown("### 🔍 这个行业现在长什么样（十维快照）")
    st.caption(
        "PM 视角：要做跨行业借鉴前，先把对标行业的『当下现状』看清楚——分三视角，"
        "每个视角下 3-4 个观察维度，每条一句话。"
    )
    dims = ind.get("dimensions", {})

    def _esc(s):
        return (s or "—").replace("<", "&lt;").replace(">", "&gt;")

    for group in DIM_GROUPS:
        color = group["color"]
        bg = group["bg"]
        # 组标题 + 一句"看这组为了啥"
        st.markdown(
            f"<div style='margin:14px 0 6px 0;display:flex;align-items:baseline;gap:10px'>"
            f"<span style='color:{color};font-size:14px;font-weight:700;"
            f"letter-spacing:0.3px'>{group['title']}</span>"
            f"<span style='color:#888;font-size:12px'>· {group['hint']}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        # 组内维度卡片
        rows_html = ""
        for key in group["keys"]:
            label = DIM_LABELS.get(key, key)
            value = dims.get(key, "—") or "—"
            rows_html += (
                f"<div style='display:flex;align-items:flex-start;gap:14px;"
                f"padding:9px 14px;border-top:1px dashed #FFFFFF99'>"
                f"<span style='flex:0 0 175px;color:{color};font-size:12.5px;"
                f"font-weight:600;line-height:1.5'>{label}</span>"
                f"<span style='flex:1;color:#1A1A1A;font-size:13.5px;line-height:1.6'>"
                f"{_esc(value)}</span>"
                f"</div>"
            )
        st.markdown(
            f"<div style='background:{bg};border-left:3px solid {color};"
            f"border-radius:6px;padding:4px 4px 8px 4px'>"
            f"{rows_html}</div>",
            unsafe_allow_html=True,
        )


def render_data_validation(ind):
    dv = ind.get("data_validation", [])
    if not dv:
        return
    st.markdown("**数据验证**")
    for v in dv:
        with st.container(border=True):
            st.markdown(
                f"`{v.get('source', '?')}`　query：`{v.get('query', '')}`　"
                f"样本：{v.get('sample_size', 0)}"
            )
            st.caption(f"假设：{v.get('hypothesis', '—')}")
            finding = v.get("finding", "—")
            is_placeholder = (
                "DEMO" in finding or "占位" in finding or finding in ("", "—")
            )
            if is_placeholder:
                st.warning(f"待验证：{finding}")
            else:
                st.success(f"发现：{finding}")


def render_industry_trends(ind):
    """渲染该行业自己的趋势特点（与顶层跨行业 trends 形成『个性 vs 共性』对照）。"""
    t = ind.get("trends") or {}
    has_any = any(t.get(k) for k in ("tech", "ingredient", "formula"))
    if not has_any:
        st.markdown(
            f"<div style='background:#FAFAFA;border:1px dashed #DDD;border-radius:8px;"
            f"padding:12px 16px;margin:10px 0;color:#999;font-size:12px'>"
            f"<b style='color:#7E57C2'>📈 本行业趋势</b> · 旧数据未含此字段，重跑后会自动补"
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    def _esc(s):
        return (s or "—").replace("<", "&lt;").replace(">", "&gt;")

    def _chip_list(items, bg, fg, border):
        items = items or []
        if not items:
            return f"<span style='color:#BBB;font-size:12px;font-style:italic'>—</span>"
        html = ""
        for it in items:
            html += (
                f"<div style='background:{bg};border-left:3px solid {border};"
                f"padding:7px 12px;border-radius:4px;margin-bottom:6px;"
                f"color:#1A1A1A;font-size:12.5px;line-height:1.55'>"
                f"{_esc(it)}</div>"
            )
        return html

    st.markdown("### 📈 本行业的技术 / 成分 / 配方特点")
    st.caption("聚焦『这个行业自己的趋势细节』。跨行业整体共性趋势在页面顶部 expander 里。")
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.markdown(
            f"<div style='color:#1976D2;font-size:13px;font-weight:700;margin-bottom:6px'>"
            f"⚙️ 技术特点</div>"
            + _chip_list(t.get("tech"), "#E3F2FD", "#1976D2", "#1976D2"),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div style='color:#7B1FA2;font-size:13px;font-weight:700;margin-bottom:6px'>"
            f"🧪 成分特点</div>"
            + _chip_list(t.get("ingredient"), "#F3E5F5", "#7B1FA2", "#7B1FA2"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div style='color:#2E7D32;font-size:13px;font-weight:700;margin-bottom:6px'>"
            f"📐 配方特点</div>"
            + _chip_list(t.get("formula"), "#E8F5E9", "#2E7D32", "#2E7D32"),
            unsafe_allow_html=True,
        )


def render_solution_stack(ind):
    """行业如何解决核心问题——成分/工艺/形态/品质信号/可迁移性。"""
    sol = ind.get("solution_stack") or {}
    has_any = any(sol.get(k) for k in ("signature_ingredients", "key_processes", "delivery_form", "quality_proof", "transferability_note"))
    if not has_any:
        st.markdown(
            f"<div style='background:#FAFAFA;border:1px dashed #DDD;border-radius:8px;"
            f"padding:14px 18px;margin:10px 0;color:#999;font-size:12.5px'>"
            f"<b style='color:#7E57C2'>🧬 解决方案技术栈</b> · 旧数据未含此字段，重跑后会自动补：标志成分 / 关键工艺 / 递送形态 / 品质信号 / 可迁移性"
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    def _esc(s):
        return (s or "—").replace("<", "&lt;").replace(">", "&gt;")

    def _chip_list(items, bg, fg):
        items = items or []
        if not items:
            return f"<span style='color:#BBB;font-size:12px;font-style:italic'>—</span>"
        chips = ""
        for it in items:
            chips += (
                f"<span style='display:inline-block;background:{bg};color:{fg};"
                f"padding:4px 11px;border-radius:12px;font-size:12px;font-weight:500;"
                f"margin:3px 5px 3px 0'>{_esc(it)}</span>"
            )
        return chips

    st.markdown("### 🧬 这个行业是怎么解决核心问题的")
    st.caption("从「成分清单 → 关键工艺 → 递送形态 → 品质信号」拆解，最后一句话告诉你哪些可直接迁移到宠物侧。")

    col_l, col_r = st.columns(2, gap="medium")
    with col_l:
        st.markdown(
            f"<div style='background:#F3E5F5;border-left:3px solid #5E35B1;"
            f"padding:12px 16px;border-radius:6px;margin-bottom:10px;min-height:120px'>"
            f"<div style='color:#5E35B1;font-size:12px;font-weight:600;margin-bottom:8px'>"
            f"🧪 标志性成分</div>"
            f"<div>{_chip_list(sol.get('signature_ingredients'), '#FFFFFF', '#5E35B1')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='background:#E0F7FA;border-left:3px solid #00838F;"
            f"padding:12px 16px;border-radius:6px;margin-bottom:10px;min-height:90px'>"
            f"<div style='color:#00838F;font-size:12px;font-weight:600;margin-bottom:6px'>"
            f"📦 递送形态</div>"
            f"<div style='color:#1A1A1A;font-size:13px;line-height:1.6'>{_esc(sol.get('delivery_form'))}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(
            f"<div style='background:#E8F5E9;border-left:3px solid #2E7D32;"
            f"padding:12px 16px;border-radius:6px;margin-bottom:10px;min-height:120px'>"
            f"<div style='color:#2E7D32;font-size:12px;font-weight:600;margin-bottom:8px'>"
            f"⚙️ 关键工艺</div>"
            f"<div>{_chip_list(sol.get('key_processes'), '#FFFFFF', '#2E7D32')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='background:#FFF8E1;border-left:3px solid #F57C00;"
            f"padding:12px 16px;border-radius:6px;margin-bottom:10px;min-height:90px'>"
            f"<div style='color:#E65100;font-size:12px;font-weight:600;margin-bottom:6px'>"
            f"🏅 品质 / 功效信号</div>"
            f"<div style='color:#1A1A1A;font-size:13px;line-height:1.6'>{_esc(sol.get('quality_proof'))}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # 可迁移性扣回宠物 — 突出橙色 callout
    transfer = sol.get("transferability_note")
    if transfer:
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#FFF3E0 0%,#FFFFFF 100%);"
            f"border:1.5px solid #FFB74D;border-left:4px solid #FF8C42;"
            f"padding:14px 18px;border-radius:8px;margin:8px 0 4px 0'>"
            f"<div style='color:#E65100;font-size:12px;font-weight:700;letter-spacing:0.5px;"
            f"margin-bottom:6px'>🐾 可迁移性 · 扣回宠物</div>"
            f"<div style='color:#1A1A1A;font-size:13.5px;line-height:1.65'>{_esc(transfer)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )


def render_timeline(ind):
    tl = ind.get("timeline", [])
    if not tl:
        st.info("尚未填写 timeline。真跑结果会自动带上演化时间线。")
        return

    # 概览条：flex 横向排列，超出自动换行（容 era 数变化）
    cards = ""
    for era in tl:
        cards += (
            f"<div style='flex:1;min-width:140px;text-align:center;padding:10px 8px;"
            f"border-radius:6px;background:#F0EAFA;border:1px solid #D9CFEE'>"
            f"<div style='font-weight:600;color:#5E35B1;font-size:14px;line-height:1.3'>"
            f"{era.get('era','—')}</div>"
            f"<div style='font-size:11px;color:#666;margin-top:2px'>"
            f"{era.get('year_range','—')}</div>"
            f"</div>"
        )
    st.markdown(
        f"<div style='display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px'>{cards}</div>",
        unsafe_allow_html=True,
    )

    # 详细 era 卡片，按时间顺序
    def _esc(s):
        return (s or "—").replace("<", "&lt;").replace(">", "&gt;")

    def _ctx_callout(label, value, bg, border, label_color):
        return (
            f"<div style='background:{bg};border-left:3px solid {border};"
            f"padding:10px 14px;border-radius:4px;margin:0;height:100%;min-height:90px'>"
            f"<div style='color:{label_color};font-size:12px;font-weight:600;"
            f"letter-spacing:0.3px;margin-bottom:5px'>{label}</div>"
            f"<div style='color:#1A1A1A;font-size:13px;line-height:1.6'>{_esc(value)}</div>"
            f"</div>"
        )

    for era in tl:
        with st.container(border=True):
            # 头部
            head_l, head_r = st.columns([1, 4])
            with head_l:
                st.markdown(f"#### {era.get('era', '—')}")
                st.caption(era.get("year_range", "—"))
            with head_r:
                st.markdown(f"**{era.get('summary', '—')}**")

            # 差异破局点 + 成分/工艺演进（两条突出条）
            bt = (era.get("breakthrough") or "").strip()
            ta = (era.get("tech_advance") or "").strip()
            if bt:
                st.markdown(
                    f"<div style='background:linear-gradient(135deg,#FFF3E0 0%,#FFFFFF 100%);"
                    f"border-left:4px solid #FF8C42;border-radius:6px;"
                    f"padding:10px 16px;margin:10px 0 6px 0'>"
                    f"<span style='color:#E65100;font-size:11.5px;font-weight:700;"
                    f"letter-spacing:0.5px;margin-right:8px'>🚀 差异破局点</span>"
                    f"<span style='color:#1A1A1A;font-size:13.5px;line-height:1.6'>"
                    f"{_esc(bt)}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            if ta:
                st.markdown(
                    f"<div style='background:linear-gradient(135deg,#E8F5E9 0%,#FFFFFF 100%);"
                    f"border-left:4px solid #2E7D32;border-radius:6px;"
                    f"padding:10px 16px;margin:0 0 12px 0'>"
                    f"<span style='color:#1B5E20;font-size:11.5px;font-weight:700;"
                    f"letter-spacing:0.5px;margin-right:8px'>🧪 成分 / 工艺演进</span>"
                    f"<span style='color:#1A1A1A;font-size:13.5px;line-height:1.6'>"
                    f"{_esc(ta)}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # 时代背景三栏：消费者心智 / 时代痛点 / 品牌占位
            mindset = era.get("consumer_mindset")
            pain = era.get("era_pain_point")
            cmap = era.get("competitive_map")
            if any([mindset, pain, cmap]):
                c1, c2, c3 = st.columns(3, gap="small")
                with c1:
                    st.markdown(_ctx_callout("🧠 消费者心智", mindset, "#E3F2FD", "#1976D2", "#1976D2"), unsafe_allow_html=True)
                with c2:
                    st.markdown(_ctx_callout("😣 时代痛点", pain, "#FFEBEE", "#C62828", "#C62828"), unsafe_allow_html=True)
                with c3:
                    st.markdown(_ctx_callout("🗺 赛道格局", cmap, "#F3E5F5", "#7B1FA2", "#7B1FA2"), unsafe_allow_html=True)
                st.markdown("&nbsp;")

            # 品牌破局动作 · 洞察 → 配方/工艺/卖点 → 占位
            actions = era.get("brand_actions", []) or []
            if actions:
                st.markdown("##### 🎯 品牌破局动作 · 洞察心智 → 调配方/工艺/卖点 → 抢占位")
                for act in actions:
                    brand = _esc(act.get("brand", "—"))
                    insight_t = act.get("insight")
                    action_t = act.get("action")
                    pos = act.get("positioning")

                    # 是否新 schema（action 是 dict 含三子项）
                    is_new_schema = isinstance(action_t, dict)
                    has_any_content = bool(insight_t or pos or action_t)

                    if has_any_content and (insight_t or pos or is_new_schema):
                        # 卡片头：品牌名 + 旁边 inline 按钮 (官网 / 资讯)
                        raw_brand_for_inline = act.get("brand", "")
                        inline_links = _brand_inline_links_html(raw_brand_for_inline)
                        card_html = (
                            f"<div style='background:#FFFFFF;border:1px solid #E6DDF5;"
                            f"border-left:4px solid #5E35B1;border-radius:8px;"
                            f"padding:14px 18px;margin-bottom:12px;"
                            f"box-shadow:0 1px 3px rgba(94,53,177,0.06)'>"
                            f"<div style='font-weight:700;color:#5E35B1;font-size:15px;"
                            f"margin-bottom:10px;letter-spacing:0.3px'>"
                            f"🏷 {brand}{inline_links}</div>"
                        )

                        # ① 洞察心智（蓝色 callout，完整一行）
                        if insight_t:
                            card_html += (
                                f"<div style='background:#E3F2FD;border-left:3px solid #1976D2;"
                                f"padding:9px 13px;border-radius:5px;margin-bottom:10px'>"
                                f"<div style='color:#1976D2;font-size:11px;font-weight:700;"
                                f"letter-spacing:0.5px;margin-bottom:4px'>💡 洞察到的消费者心智</div>"
                                f"<div style='color:#1A1A1A;font-size:13px;line-height:1.6'>"
                                f"{_esc(insight_t)}</div>"
                                f"</div>"
                            )

                        # ② 动作 · 配方/工艺/卖点三栏（配方/工艺各拆 3 子项）
                        if is_new_schema:
                            formula = action_t.get("formula")
                            process_v = action_t.get("process")
                            selling = action_t.get("selling_point")
                            card_html += (
                                f"<div style='margin-bottom:10px'>"
                                f"<div style='color:#5E35B1;font-size:11px;font-weight:700;"
                                f"letter-spacing:0.5px;margin-bottom:6px'>🎬 因此做了这些调整</div>"
                                f"<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));"
                                f"gap:8px'>"
                            )

                            def _sub_rows(rows, fg):
                                """rows = [(label, value)]，渲染成 3 行 mini-table。"""
                                html = ""
                                for label, val in rows:
                                    html += (
                                        f"<div style='padding:5px 0;border-top:1px dashed #FFFFFF99'>"
                                        f"<div style='color:{fg};font-size:10.5px;font-weight:600;"
                                        f"margin-bottom:2px'>{label}</div>"
                                        f"<div style='color:#1A1A1A;font-size:12.5px;line-height:1.5'>"
                                        f"{_esc(val)}</div>"
                                        f"</div>"
                                    )
                                return html

                            # 🧪 配方（紫色子卡）
                            if isinstance(formula, dict):
                                formula_html = _sub_rows([
                                    ("· 核心成分", formula.get("core_ingredient")),
                                    ("· 专利/标准", formula.get("patent_or_standard")),
                                    ("· 差异化", formula.get("differentiation")),
                                ], "#7B1FA2")
                            else:
                                formula_html = (
                                    f"<div style='color:#1A1A1A;font-size:12.5px;line-height:1.55'>"
                                    f"{_esc(formula) if formula else '—'}</div>"
                                )
                            card_html += (
                                f"<div style='background:#F3E5F5;border-top:2px solid #9C27B0;"
                                f"padding:8px 11px;border-radius:4px;min-height:140px'>"
                                f"<div style='color:#7B1FA2;font-size:11px;font-weight:700;"
                                f"margin-bottom:5px'>🧪 配方</div>"
                                f"{formula_html}"
                                f"</div>"
                            )

                            # ⚙️ 工艺（绿色子卡）
                            if isinstance(process_v, dict):
                                process_html = _sub_rows([
                                    ("· 工艺名", process_v.get("tech_name")),
                                    ("· 怎么做", process_v.get("how_it_works")),
                                    ("· 优势", process_v.get("advantage")),
                                ], "#2E7D32")
                            else:
                                process_html = (
                                    f"<div style='color:#1A1A1A;font-size:12.5px;line-height:1.55'>"
                                    f"{_esc(process_v) if process_v else '—'}</div>"
                                )
                            card_html += (
                                f"<div style='background:#E8F5E9;border-top:2px solid #43A047;"
                                f"padding:8px 11px;border-radius:4px;min-height:140px'>"
                                f"<div style='color:#2E7D32;font-size:11px;font-weight:700;"
                                f"margin-bottom:5px'>⚙️ 工艺</div>"
                                f"{process_html}"
                                f"</div>"
                            )

                            # 📣 卖点（橙色子卡，仍是字符串）
                            card_html += (
                                f"<div style='background:#FFF3E0;border-top:2px solid #FB8C00;"
                                f"padding:8px 11px;border-radius:4px;min-height:140px'>"
                                f"<div style='color:#E65100;font-size:11px;font-weight:700;"
                                f"margin-bottom:5px'>📣 卖点</div>"
                                f"<div style='color:#1A1A1A;font-size:12.5px;line-height:1.55'>"
                                f"{_esc(selling)}</div>"
                                f"</div>"
                            )
                            card_html += "</div></div>"
                        elif action_t:
                            # 旧 schema action 是字符串
                            card_html += (
                                f"<div style='background:#FAFAFA;border-left:3px solid #999;"
                                f"padding:9px 13px;border-radius:5px;margin-bottom:10px'>"
                                f"<div style='color:#666;font-size:11px;font-weight:700;"
                                f"margin-bottom:4px'>🎬 做了 <span style='color:#BBB;font-weight:400;font-style:italic'>· 旧数据未拆配方/工艺/卖点</span></div>"
                                f"<div style='color:#333;font-size:13px;line-height:1.6'>"
                                f"{_esc(action_t)}</div>"
                                f"</div>"
                            )

                        # ③ 占位（绿色 callout）
                        if pos:
                            card_html += (
                                f"<div style='background:#E8F5E9;border-left:3px solid #2E7D32;"
                                f"padding:9px 13px;border-radius:5px'>"
                                f"<div style='color:#1B5E20;font-size:11px;font-weight:700;"
                                f"letter-spacing:0.5px;margin-bottom:4px'>🏆 占据了什么市场+心智</div>"
                                f"<div style='color:#1A1A1A;font-size:13px;line-height:1.6'>"
                                f"{_esc(pos)}</div>"
                                f"</div>"
                            )

                        # ④ 跳转链接条：搜这个品牌（多平台）
                        raw_brand = act.get("brand", "")
                        card_html += _brand_search_links_html(raw_brand)

                        card_html += "</div>"
                        st.markdown(card_html, unsafe_allow_html=True)
                    else:
                        # 完全旧 schema fallback：只有 brand + action 字符串
                        st.markdown(
                            f"<div style='background:#FAFAFA;border:1px solid #EEE;"
                            f"border-left:3px solid #999;border-radius:6px;"
                            f"padding:10px 14px;margin-bottom:6px'>"
                            f"<b>{brand}</b>　{_esc(action_t if isinstance(action_t, str) else '—')}"
                            f"<div style='color:#999;font-size:11px;margin-top:4px'>"
                            f"_旧数据：未含完整因果链。重跑可补全。_</div>"
                            f"{_brand_search_links_html(act.get('brand', ''))}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

            # 当时浮现的机会点（紧凑列表）
            opps = era.get("opportunities", []) or []
            if opps:
                st.markdown("##### 📈 当时浮现的机会点")
                st.markdown("　·　".join(f"`{o}`" for o in opps))


def render_current_state(ind):
    cs = ind.get("current_state")
    if not cs:
        return
    st.markdown("### 行业现状")
    st.success(cs)


def render_industry_badge(name):
    selected = st.session_state.get("selected_industries", [])
    if name in selected:
        st.success(f"★ 已纳入候选清单（侧栏共 {len(selected)} 个）  ·  机会矩阵 / 产品概念会包含本行业的条目")
    else:
        st.caption(
            f"○ 未纳入候选（侧栏共 {len(selected)} 个）  ·  "
            "下游页面不会包含本行业；在左侧『候选行业』里勾上即可纳入"
        )


def render_industry_opportunities(ind, all_opps):
    """本行业贡献的机会条目，紧凑表格。"""
    name = ind.get("name", "")
    related = [o for o in all_opps if name in o.get("from_industry", "")]
    st.markdown("### 本行业贡献的机会条目")
    if not related:
        st.caption("本行业暂无关联机会条目。")
        return
    rows = []
    for o in related:
        v = o.get("value", 0); f = o.get("feasibility", 0); d = o.get("differentiation", 0)
        rows.append({
            "★": "★" if o.get("title") in insight.get("top_picks", []) else "",
            "机会": o.get("title", ""),
            "底层机制": o.get("mechanism", ""),
            "价值": v, "可行": f, "差异": d, "综合": v * f * d,
            "类型": "红海" if o.get("is_red_ocean") else "蓝海",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("→ 跨行业全景对比与气泡图见『机会矩阵』页（按侧栏候选自动过滤）。")


def _short_name(name: str) -> str:
    """Tab 标签用短名：去掉括号注释、斜线后半段、过长截断。"""
    s = name.split("（")[0].split("(")[0].strip()
    if len(s) > 12:
        s = s[:11] + "…"
    return s


# ── 对标行业选择器（卡片网格） ──────────────────────
all_opps = insight.get("opportunities", [])

if "selected_industry_idx" not in st.session_state:
    st.session_state.selected_industry_idx = 0
# 切 run 时索引可能越界
if st.session_state.selected_industry_idx >= len(industries):
    st.session_state.selected_industry_idx = 0


def _industry_card_html(idx: int, ind_data: dict, is_selected: bool) -> str:
    """选中态：浅紫底 + 3px 紫边 + 阴影；未选中：白底 + 浅灰边。"""
    name = ind_data.get("name", "—")
    emoji, noto = _industry_icon(name)
    short = _short_name(name)
    borrow = (ind_data.get("borrow") or "—").replace("<", "&lt;").replace(">", "&gt;")
    why = (ind_data.get("why_chosen") or "").replace("<", "&lt;").replace(">", "&gt;")
    safe_short = short.replace("<", "&lt;").replace(">", "&gt;")

    if is_selected:
        bg = "linear-gradient(135deg, #F0EAFA 0%, #FFFFFF 100%)"
        border = "3px solid #5E35B1"
        shadow = "0 4px 14px rgba(94,53,177,0.18)"
        ribbon = (
            "<div style='position:absolute;top:10px;right:10px;"
            "background:#5E35B1;color:#FFFFFF;font-size:11px;"
            "font-weight:600;padding:3px 10px;border-radius:10px'>✓ 当前</div>"
        )
    else:
        bg = "#FFFFFF"
        border = "1px solid #E0E0E0"
        shadow = "0 1px 3px rgba(0,0,0,0.04)"
        ribbon = ""

    html = (
        f"<div style='position:relative;background:{bg};border:{border};"
        f"border-radius:12px;padding:16px 18px;min-height:200px;"
        f"box-shadow:{shadow};transition:all 0.2s;margin-bottom:4px'>"
        f"{ribbon}"
        f"<div style='display:flex;align-items:flex-start;gap:14px;margin-bottom:12px'>"
        f"{_icon_img_html(noto, size=44)}"
        f"<div style='flex:1;min-width:0'>"
        f"<div style='font-size:11px;color:#999;font-weight:600;letter-spacing:0.5px;"
        f"text-transform:uppercase'>对标行业 {idx+1:02d}</div>"
        f"<div style='font-size:16px;color:#1A1A1A;font-weight:600;line-height:1.3;"
        f"margin-top:3px'>{emoji} {safe_short}</div>"
        f"</div></div>"
        f"<div style='color:#5E35B1;font-size:12.5px;line-height:1.55;"
        f"display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;"
        f"overflow:hidden;margin-bottom:8px'>"
        f"<span style='opacity:0.7;font-weight:600;margin-right:4px'>借鉴焦点 ·</span>"
        f"{borrow}</div>"
    )
    if why:
        html += (
            f"<div style='border-top:1px dashed #D9CFEE;padding-top:8px;margin-top:6px;"
            f"color:#555;font-size:11.5px;line-height:1.55;"
            f"display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden'>"
            f"<span style='color:#5E35B1;font-weight:600;margin-right:4px'>为什么选 ·</span>"
            f"{why}</div>"
        )
    else:
        html += (
            f"<div style='border-top:1px dashed #EEEEEE;padding-top:8px;margin-top:6px;"
            f"color:#BBB;font-size:11.5px;line-height:1.5;font-style:italic'>"
            f"为什么选 · 旧 run 未含该字段，重跑后会自动补上</div>"
        )
    html += "</div>"
    return html


# ── 跨行业趋势区（顶部 expander） ─────────────────────────
def _render_cross_industry_trends(trends_data):
    """渲染顶部跨行业趋势卡片（tech / ingredient / formula 三类）。"""
    if not trends_data:
        with st.expander("📈 跨行业趋势 · 技术 / 成分 / 配方（旧数据未含 trends，重跑后会自动补）", expanded=False):
            st.caption("⏳ 当前 run 未跑出 trends 数据。重新跑一次该立项即可看到跨行业横切归纳的 5-15 条趋势。")
        return

    def _esc(s):
        return (s or "—").replace("<", "&lt;").replace(">", "&gt;")

    def _trend_section(title, emoji, items, color, bg):
        if not items:
            return f"<div style='color:#BBB;font-size:12px;font-style:italic'>暂无 {title}</div>"
        chips = ""
        for it in items:
            trend = _esc((it.get("trend") if isinstance(it, dict) else it) or "")
            evi = it.get("evidence_industries") or [] if isinstance(it, dict) else []
            evi_html = ""
            for e in evi:
                evi_html += (
                    f"<span style='display:inline-block;background:#FFFFFF;color:{color};"
                    f"padding:1px 8px;border-radius:9px;font-size:10.5px;font-weight:500;"
                    f"margin:2px 4px 2px 0;border:1px solid {color}55'>{_esc(e)}</span>"
                )
            chips += (
                f"<div style='background:{bg};border-left:3px solid {color};"
                f"padding:9px 13px;border-radius:5px;margin-bottom:8px'>"
                f"<div style='color:#1A1A1A;font-size:13px;line-height:1.55;margin-bottom:5px'>"
                f"{trend}</div>"
                f"<div style='font-size:10.5px'>{evi_html}</div>"
                f"</div>"
            )
        return chips

    with st.expander("📈 跨行业趋势 · 技术 / 成分 / 配方（横切归纳）", expanded=True):
        st.caption(
            "把所有对标行业的『成分/工艺/形态』演化横切归纳。每条趋势底下挂证据行业链接，方便回溯。"
        )
        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            st.markdown(
                f"<div style='color:#1976D2;font-size:13px;font-weight:700;margin-bottom:8px'>"
                f"⚙️ 技术趋势</div>"
                + _trend_section("技术趋势", "⚙️", trends_data.get("tech_trends") or [],
                                 "#1976D2", "#E3F2FD"),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"<div style='color:#7B1FA2;font-size:13px;font-weight:700;margin-bottom:8px'>"
                f"🧪 成分趋势</div>"
                + _trend_section("成分趋势", "🧪", trends_data.get("ingredient_trends") or [],
                                 "#7B1FA2", "#F3E5F5"),
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"<div style='color:#2E7D32;font-size:13px;font-weight:700;margin-bottom:8px'>"
                f"📐 配方趋势</div>"
                + _trend_section("配方趋势", "📐", trends_data.get("formula_trends") or [],
                                 "#2E7D32", "#E8F5E9"),
                unsafe_allow_html=True,
            )


_render_cross_industry_trends(insight.get("trends"))
st.markdown("---")

st.markdown("### 🎯 选择对标行业")
st.caption(f"共 {len(industries)} 个 · 点击卡片下方按钮切换 · 候选行业筛选请去左侧栏")

with st.container(border=False):
    CARDS_PER_ROW = 3
    for row_start in range(0, len(industries), CARDS_PER_ROW):
        cols = st.columns(CARDS_PER_ROW, gap="medium")
        for col_i, ind_idx in enumerate(range(row_start, min(row_start + CARDS_PER_ROW, len(industries)))):
            with cols[col_i]:
                ind_data = industries[ind_idx]
                is_sel = (ind_idx == st.session_state.selected_industry_idx)
                st.markdown(_industry_card_html(ind_idx, ind_data, is_sel), unsafe_allow_html=True)
                if st.button(
                    "✓ 当前查看" if is_sel else "查看 →",
                    key=f"ind_pick_{insight.get('_slug','')[:8]}_{ind_idx}",
                    type="primary" if is_sel else "secondary",
                    use_container_width=True,
                    disabled=is_sel,
                ):
                    st.session_state.selected_industry_idx = ind_idx
                    st.rerun()

selected_idx = st.session_state.selected_industry_idx
ind = industries[selected_idx]
st.markdown("---")

# ── 选中行业详情 ──────────────────────────────────────
full_name = ind.get("name", "—")
emoji, noto = _industry_icon(full_name)
borrow = (ind.get("borrow") or "—").replace("<", "&lt;").replace(">", "&gt;")
why_detail = (ind.get("why_chosen") or "").replace("<", "&lt;").replace(">", "&gt;")
safe_name = full_name.replace("<", "&lt;").replace(">", "&gt;")

why_html = (
    f"<div style='font-size:12.5px;color:#444;margin-top:8px;line-height:1.6;"
    f"padding-top:8px;border-top:1px dashed #D9CFEE'>"
    f"<span style='color:#5E35B1;font-weight:600;margin-right:6px'>为什么选 ·</span>{why_detail}"
    f"</div>"
) if why_detail else ""

# 行业名片高亮框（紫色 banner + Iconify 彩色 SVG）
st.markdown(
    f"<div style='background:linear-gradient(135deg, #F0EAFA 0%, #FFFFFF 70%);"
    f"border-left:5px solid #5E35B1;border-radius:8px;"
    f"padding:18px 22px;margin:14px 0 18px 0;"
    f"display:flex;align-items:flex-start;gap:20px'>"
    f"{_icon_img_html(noto, size=56)}"
    f"<div style='flex:1'>"
    f"<div style='font-size:20px;font-weight:600;color:#1A1A1A;line-height:1.3'>"
    f"{safe_name}</div>"
    f"<div style='font-size:13px;color:#5E35B1;margin-top:6px;line-height:1.5'>"
    f"<span style='opacity:0.7;margin-right:6px'>借鉴焦点 ·</span>{borrow}</div>"
    f"{why_html}"
    f"</div></div>",
    unsafe_allow_html=True,
)
render_industry_badge(ind.get("name", ""))
st.markdown("&nbsp;")
render_dimensions(ind)
st.markdown("---")
render_solution_stack(ind)
st.markdown("---")
render_industry_trends(ind)
st.markdown("---")
st.markdown("### 行业发展历程")
st.caption(
    "覆盖完整发展周期（4-5 个 era）。每个 era：差异破局点 → 成分/工艺演进 → 消费者心智/痛点/格局 → 头部品牌动作。"
)
render_timeline(ind)
st.markdown("---")
render_current_state(ind)
st.markdown("---")
render_data_validation(ind)
st.markdown("---")
render_industry_opportunities(ind, all_opps)
st.markdown("---")
render_borrow(ind)
