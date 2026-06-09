# Skill 调用提示词

复制下面整段到 Claude Code（确保已在新会话里）：

```
请用 cross-industry-insight skill 处理这个升级立项，run slug 必须用 `肠道管理狗粮-20260601`（覆盖默认日期 slug）：

ARGUMENTS: 肠道管理狗粮 | 想要针对行业下的肠道累主粮做差异化升级 | 全阶段犬 | 能够修护倡导

baseline 已由 PM 在 web 端确定：
- 现款产品：现在没有产品
- 现款短板 / 升级诉求：想要针对行业下的肠道累主粮做差异化升级
- 决策人：Z世代，新锐白领等
- 使用者：全阶段犬
- 长期目标：能够修护倡导

请把最终 insight.json 写到 ~/AI/cross-industry-insight/runs/肠道管理狗粮-20260601/insight.json。
跑完告诉我，我去 web 端 8504 看产物 + 在『立项篮』导出 onepager。
```

完成条件：`runs/肠道管理狗粮-20260601/insight.json` 落盘。Dashboard 会自动检测到。
