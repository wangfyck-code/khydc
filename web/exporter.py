"""PM 立项 onepager 生成器。"""
from datetime import datetime


VERDICT_LABEL = {
    "agree": "✅ 赞同推进",
    "doubt": "❓ 有质疑 / 待验证",
    "pass":  "❌ 暂不推进",
    "":      "未表态",
    None:    "未表态",
}


def _effective_score(o, dec):
    """优先用 PM 覆盖分；否则用分析师分。返回 (v, f, d, source)。"""
    ov = (dec or {}).get("override_score")
    if ov:
        return ov.get("value", 0), ov.get("feasibility", 0), ov.get("differentiation", 0), "PM 覆盖"
    return o.get("value", 0), o.get("feasibility", 0), o.get("differentiation", 0), "分析师"


def build_onepager(insight: dict, decisions: dict) -> str:
    """结合 insight + PM 决策，输出立项一页纸 markdown。

    只纳入 in_basket=True 的机会。按 effective score 综合分降序。
    """
    concept = insight.get("concept", "未命名概念")
    date = datetime.now().strftime("%Y-%m-%d")
    slug = insight.get("_slug", "")
    is_demo = insight.get("_is_demo", False)
    baseline = insight.get("baseline", {})

    opps_by_title = {o["title"]: o for o in insight.get("opportunities", [])}
    basket_titles = [t for t, d in decisions.items() if d.get("in_basket") and t in opps_by_title]
    basket = [opps_by_title[t] for t in basket_titles]
    basket.sort(
        key=lambda o: -(
            _effective_score(o, decisions.get(o["title"]))[0]
            * _effective_score(o, decisions.get(o["title"]))[1]
            * _effective_score(o, decisions.get(o["title"]))[2]
        )
    )

    industries_by_name = {i["name"]: i for i in insight.get("industries", [])}

    lines = [f"# {concept} · PM 立项一页纸", ""]
    suffix = " [DEMO 数据]" if is_demo else ""
    lines.append(f"> 生成：{date}　·　run：`{slug}`{suffix}　·　PM 已选 {len(basket)} 条机会")
    lines.append("")

    # ── 现款痛点 ──
    lines += [
        "## 1. 现款痛点（升级起点）",
        f"- **现款产品**：{baseline.get('current_product','—')}",
        f"- **现款短板 / 升级诉求**：{baseline.get('current_weakness','—')}",
        f"- **决策人**：{baseline.get('decision_maker','—')}　·　**使用者**：{baseline.get('user','—')}",
        "",
    ]

    # ── 升级方向 ──
    if not basket:
        lines += [
            "## 2. 升级方向",
            "",
            "> _立项候选篮为空。请到『机会矩阵与产品概念』页勾选机会加入篮子。_",
            "",
        ]
    else:
        lines.append("## 2. 升级方向（PM 选定）")
        lines.append("")
        for i, o in enumerate(basket, 1):
            dec = decisions.get(o["title"], {})
            v, f, d, src = _effective_score(o, dec)
            verdict = VERDICT_LABEL.get(dec.get("verdict") or "")
            red = "　【红海，慎抄】" if o.get("is_red_ocean") else ""
            lines.append(f"### {i}. {o.get('title','—')}{red}")
            lines.append(f"- **PM 判断**：{verdict}")
            if dec.get("note"):
                lines.append(f"- **PM 备注**：{dec['note']}")
            lines.append(
                f"- **打分（{src}）**：增量价值 **{v}** / 可行性 **{f}** / 差异化 **{d}**　·　综合 **{v*f*d}**"
            )
            lines.append(f"- **来源行业**：{o.get('from_industry','—')}　·　**底层机制**：{o.get('mechanism','—')}")
            lines.append(f"- **迁移要点**：{o.get('transfer_note','—')}")
            cd = o.get("concept_detail") or {}
            if cd:
                lines.append("- **产品概念方向**：")
                lines.append(f"  - 成分：{cd.get('ingredients','—')}")
                lines.append(f"  - 技术 / 工艺：{cd.get('tech','—')}")
                lines.append(f"  - 产品形态：{cd.get('product_form','—')}")
                lines.append(f"  - 信任背书：{cd.get('trust_backing','—')}")
            if o.get("taboo"):
                lines.append(f"- **禁区 / 风险**：{o['taboo']}")
            lines.append("")

    # ── 借鉴来源（仅篮中机会涉及的行业） ──
    src_inds = []
    if basket:
        seen = set()
        for o in basket:
            ind_name = o.get("from_industry", "") or ""
            for n in industries_by_name:
                if n and n in ind_name and n not in seen:
                    src_inds.append(industries_by_name[n])
                    seen.add(n)
        if src_inds:
            lines.append("## 3. 借鉴来源")
            lines.append("")
            for ind in src_inds:
                lines.append(f"- **{ind.get('name','—')}**：{ind.get('borrow','—')}")
                pl = ind.get("pet_pain_link")
                if pl:
                    lines.append(f"  > 扣回宠物痛点：{pl}")
            lines.append("")

    # ── 预期提升汇总 ──
    if basket:
        lines.append("## 4. 预期提升（相对现款）")
        lines.append("")
        agree = [o for o in basket if (decisions.get(o["title"], {}).get("verdict") == "agree")]
        if agree:
            lines.append(f"PM 明确推进 {len(agree)} 条：")
            for o in agree:
                lines.append(f"- {o.get('title','—')}")
        else:
            lines.append("_PM 尚未在篮中标记『赞同推进』；列入的均处于待验证状态。_")
        lines.append("")

    # ── 验证清单（来自篮中机会涉及行业的 data_validation + opp.taboo） ──
    if basket:
        val_hyps = []
        for ind in src_inds:
            for v in ind.get("data_validation", []) or []:
                val_hyps.append((ind.get("name", "—"), v.get("hypothesis", "—"), v.get("source", "?")))
        taboos = [(o.get("title", "—"), o["taboo"]) for o in basket if o.get("taboo")]
        if val_hyps or taboos:
            lines.append("## 5. 验证清单 / 风险")
            lines.append("")
            if val_hyps:
                lines.append("**上市前要验证的假设**")
                for ind_name, hyp, src in val_hyps:
                    lines.append(f"- [{ind_name} · {src}] {hyp}")
                lines.append("")
            if taboos:
                lines.append("**禁区 / 已知风险**")
                for title, t in taboos:
                    lines.append(f"- [{title}] {t}")
                lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_本一页纸由跨行业洞察 dashboard 自动生成。底层方法论：母需求 → 对标行业 → 借机制 → 反向迁移。_")
    return "\n".join(lines)
