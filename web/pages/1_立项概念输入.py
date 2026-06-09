import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from datetime import datetime
from loader import pick_run, make_slug, save_input, write_prompt, run_dir
from ai_worker import generate_insight, save_insight, DEFAULT_MODEL

st.set_page_config(page_title="立项概念输入 · PM 录入", layout="wide")
insight = pick_run()

st.title("立项概念输入 · 升级需求")
st.caption(
    "填升级概念 + 现款 baseline → 点⚡一键生成洞察 → 1-2 分钟出 insight.json → 自动进入机会与概念。"
)

# ── 顶部 banner：当前 run 状态提示 ──
if insight is not None:
    slug_cur = insight.get("_slug", "")
    status = insight.get("_status", "ready")
    if status == "pending":
        prompt_file = run_dir(slug_cur) / "_prompt.md"
        st.info(
            f"💡 当前侧栏选中的 run `{slug_cur}` 是 **待生成** 状态——已有 input.json，没 insight.json。"
        )
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button(f"⚡ 给这个 run 跑洞察", type="primary", use_container_width=True):
                from loader import load_input
                input_data = load_input(slug_cur)
                if input_data:
                    st.session_state["_pending_run"] = {"slug": slug_cur, "data": input_data}
                    st.rerun()
        with cc2:
            if prompt_file.exists():
                with st.popover("📋 或：拷贝提示词到 Claude Code", use_container_width=True):
                    st.code(prompt_file.read_text(encoding="utf-8"), language="markdown")
        st.markdown("---")
    elif status == "ready":
        st.success(f"✅ 当前 run `{slug_cur}` 已 ready。要做新升级请在下方录入。")
        st.markdown("---")

# ── 表单 ──
st.markdown("### 升级需求")
st.caption("所有字段都会被 skill 当 baseline 用；写得越具体，产物越能扣回现款。")

with st.form("new_run_form", clear_on_submit=False):
    concept = st.text_input(
        "概念 *（必填）",
        placeholder="例：体态管理狗粮",
        help="一句话写要做的升级方向；slug 会从这里生成",
    )
    current_product = st.text_area(
        "现款产品 *",
        placeholder="例：麦富迪体重管理粮（成犬款），低脂高纤配方，价格 ¥X/kg，主销渠道天猫旗舰",
        height=80,
        help="要升级的那款在售产品；具体到 SKU / 价格 / 卖点",
    )
    current_weakness = st.text_area(
        "现款短板 / 升级诉求 *",
        placeholder="例:复购偏低;概念偏旧(『低脂』说了十年);缺方法论 + 用户陪伴",
        height=80,
        help="现款最让 PM 不爽的那一点;这是 skill 找『增量』的靶心",
    )
    decision_maker = st.text_area(
        "决策人画像 *(谁掏钱)",
        placeholder="例:一二线城市 25-40 岁主人,养绝育后犬,对体重焦虑但缺方法",
        height=70,
    )
    user_ = st.text_input(
        "使用者(猫/狗) *",
        placeholder="例:绝育后易胖犬(成犬,5-10kg)",
    )
    objective = st.text_input(
        "长期目标(可选)",
        placeholder="例:长期体重管理 + 复购粘性",
    )
    mother_needs_raw = st.text_input(
        "母需求(可选,留空让 skill 自己推)",
        placeholder="例:哺乳动物的体重/体脂管理(多个用 / 分隔)",
        help="不填的话 skill 会在阶段 1 自己抽象",
    )

    submitted = st.form_submit_button(
        f"⚡ 一键生成洞察（{DEFAULT_MODEL.split('/')[-1]} · 约 1-2 分钟）",
        type="primary",
        use_container_width=True,
    )

# ── 表单提交：写盘 + 排队等 LLM ──
if submitted:
    required = {"概念": concept, "现款产品": current_product, "现款短板": current_weakness,
                "决策人": decision_maker, "使用者": user_}
    missing = [k for k, v in required.items() if not v.strip()]
    if missing:
        st.error(f"以下字段必填：{ '、'.join(missing) }")
    else:
        slug = make_slug(concept)
        mother_needs = [m.strip() for m in mother_needs_raw.split("/") if m.strip()]
        data = {
            "concept": concept.strip(),
            "current_product": current_product.strip(),
            "current_weakness": current_weakness.strip(),
            "decision_maker": decision_maker.strip(),
            "user": user_.strip(),
            "objective": objective.strip(),
            "mother_needs": mother_needs,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "created_by": "pm-web",
        }
        save_input(slug, data)
        write_prompt(slug, data)
        st.session_state["_pending_run"] = {"slug": slug, "data": data}
        st.rerun()

# ── LLM 调用区（form 外，能显示 spinner） ──
if "_pending_run" in st.session_state:
    p = st.session_state["_pending_run"]
    slug = p["slug"]
    data = p["data"]

    with st.status(f"⚡ 正在为 `{slug}` 生成洞察…", expanded=True) as status:
        try:
            st.write(f"📡 调用 OpenRouter / {DEFAULT_MODEL}")
            raw_dump = run_dir(slug) / "_llm_raw.txt"
            insight_out = generate_insight(data, raw_dump_path=raw_dump)
            st.write(
                f"✓ 行业 {len(insight_out['industries'])} · "
                f"机会 {len(insight_out['opportunities'])} · "
                f"Top {len(insight_out['top_picks'])}"
            )
            out_path = save_insight(slug, insight_out)
            st.write(f"💾 落盘 → {out_path}")
            st.session_state.run_slug = slug
            st.session_state.decisions = {}
            st.session_state.decisions_slug = slug
            status.update(label=f"✅ 洞察生成完毕!run `{slug}` 已 ready", state="complete")

            # 跑完清排队 + 给明显 CTA
            del st.session_state["_pending_run"]

            st.markdown("### 下一步")
            n1, n2, n3 = st.columns(3)
            with n1:
                st.page_link("pages/3_机会矩阵与产品概念.py", label="🎯 去机会矩阵与产品概念", icon="➡️", use_container_width=True)
            with n2:
                st.page_link("pages/2_跨行业洞察地图.py", label="🗺 看对标行业全景", icon="➡️", use_container_width=True)
            with n3:
                st.page_link("pages/4_立项候选篮.py", label="🧺 立项候选篮 / 导 onepager", icon="➡️", use_container_width=True)

        except Exception as e:
            status.update(label="❌ LLM 调用失败", state="error")
            st.error(f"错误：{e}")
            st.caption("可改走兜底路径——把下面的提示词拷到 Claude Code 跑：")
            prompt_file = run_dir(slug) / "_prompt.md"
            if prompt_file.exists():
                with st.popover("📋 查看提示词", use_container_width=True):
                    st.code(prompt_file.read_text(encoding="utf-8"), language="markdown")
            if st.button("重试一次"):
                st.rerun()
            if st.button("放弃此 run"):
                del st.session_state["_pending_run"]
                st.rerun()
