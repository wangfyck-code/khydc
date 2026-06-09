"""Cloud entrypoint for Streamlit Community Cloud."""
import streamlit as st
from loader import pick_run

st.set_page_config(page_title="跨行业洞察 · PM 立项 App", layout="wide")

insight = pick_run()

st.title("跨行业洞察 · PM 立项 App")
st.caption(
    "输入升级概念 → skill 跑洞察 → PM 标注决策 → 一键出立项一页纸。"
    "底层方法论：母需求 → 对标行业 → 借机制 → 反向迁移。"
)

if insight is None:
    st.info(
        "**还没有 run。** 请到左侧『立项概念输入』新建一个升级立项："
        "录入概念 + 现款 baseline → 生成洞察。"
    )
    st.stop()

status = insight.get("_status", "ready")
slug = insight.get("_slug", "")

if status == "pending":
    st.warning(
        f"当前 run `{slug}` 是『**待生成**』状态——已录入 input.json，还没生成 insight.json。"
        "请到『立项概念输入』继续生成。"
    )
    st.markdown("### 已录入的 baseline")
    b = insight.get("baseline", {})
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**概念**：{insight.get('concept','-')}")
        st.markdown(f"**现款**：{b.get('current_product','-')}")
        st.markdown(f"**决策人**：{b.get('decision_maker','-')}")
    with c2:
        st.markdown(f"**短板 / 诉求**：{b.get('current_weakness','-')}")
        st.markdown(f"**使用者**：{b.get('user','-')}")
    st.stop()

if insight.get("_is_demo"):
    st.warning(
        "当前展示的是 DEMO 占位数据（schema 已跑通，便于先看 UI 形态）。"
        "录入真实概念后，跑出的新 run 会落入 `runs/` 自动出现在侧栏。"
    )

c1, c2, c3, c4 = st.columns(4)
c1.metric("对标行业", len(insight.get("industries", [])))
c2.metric("机会总数", len(insight.get("opportunities", [])))
c3.metric("分析师 Top", len(insight.get("top_picks", [])))
decs = st.session_state.get("decisions", {})
basket_n = sum(1 for v in decs.values() if v.get("in_basket"))
c4.metric("立项候选篮", basket_n, help="PM 已勾选进立项候选篮的机会数")

st.markdown("### 母需求（抽象层）")
for mn in insight.get("mother_needs", []):
    st.markdown(f"- {mn}")

st.markdown("---")
st.markdown("### PM 工作流（闭环）")
st.markdown(
    """
| 步骤 | 页面 | 你做什么 |
|---|---|---|
| **1** | **立项概念输入** | 录入升级概念 + 现款 baseline → 生成洞察 |
| **2** | **跨行业洞察地图** | 看对标行业全景：十维 / 演化时间线 / 可参考借鉴 |
| **3** | **机会矩阵与产品概念** | 看气泡图 + 卡片 → 给每条机会打 PM 判断 / 备注 / 覆盖打分 / 加入篮 |
| **4** | **立项候选篮** | 一键导出立项一页纸 `onepager_pm.md` |
| **5** | **验证执行清单** | 上市前要验证的假设清单（按行业组织） |
"""
)
st.caption(
    "PM 标注会写入当前运行环境的 `runs/<slug>/decisions.json`。"
    "Streamlit Community Cloud 的文件系统可能随重启丢失，正式协作建议接数据库或下载导出物。"
)
