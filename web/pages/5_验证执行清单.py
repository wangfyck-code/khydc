import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from loader import pick_run

st.set_page_config(page_title="验证执行清单", layout="wide")
insight = pick_run()
if insight is None:
    st.stop()

st.title("验证执行清单")
st.caption("上市前要验证的假设与禁区。按行业 data_validation 汇总，附各机会的 taboo 警示。")

st.subheader("行业级数据假设")
st.caption("默认只展开第一条，其余点击行业名称展开。")
industries = insight.get("industries", [])
any_dv = False
shown_first = False
for ind in industries:
    dv = ind.get("data_validation", [])
    if not dv:
        continue
    any_dv = True
    expand = not shown_first
    shown_first = True
    with st.expander(f"{ind.get('name', '—')}  ·  {len(dv)} 条", expanded=expand):
        for v in dv:
            with st.container(border=True):
                st.markdown(f"**假设**：{v.get('hypothesis', '—')}")
                st.caption(
                    f"来源：`{v.get('source', '—')}`　·　"
                    f"query：`{v.get('query', '—')}`　·　"
                    f"样本：{v.get('sample_size', 0)}"
                )
                finding = v.get("finding", "—")
                is_placeholder = (
                    "DEMO" in finding
                    or "占位" in finding
                    or finding in ("", "—")
                )
                if is_placeholder:
                    st.warning(f"未验证 / 占位：{finding}")
                else:
                    st.success(f"已验证：{finding}")
if not any_dv:
    st.info("无 data_validation 条目。")

st.markdown("---")
st.subheader("机会级禁区 / 风险")
opps = insight.get("opportunities", [])
shown = False
for o in opps:
    if o.get("taboo"):
        shown = True
        with st.container(border=True):
            st.markdown(f"**{o.get('title', '—')}**")
            st.error(o["taboo"])
if not shown:
    st.info("无 taboo 条目。")
