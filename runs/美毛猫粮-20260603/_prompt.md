# Skill 调用提示词

复制下面整段到 Claude Code（确保已在新会话里）：

```
请用 cross-industry-insight skill 处理这个升级立项，run slug 必须用 `美毛猫粮-20260603`（覆盖默认日期 slug）：

ARGUMENTS: 美毛猫粮 | 复购偏低，且为美毛产品下解决方案同质化 | 全期猫 | 美毛

baseline 已由 PM 在 web 端确定：
- 现款产品：麦富迪舒然猫粮，20/kg
- 现款短板 / 升级诉求：复购偏低，且为美毛产品下解决方案同质化
- 决策人：一线城市20-35，新锐白领，小镇青年
- 使用者：全期猫
- 长期目标：美毛

请把最终 insight.json 写到 ~/AI/cross-industry-insight/runs/美毛猫粮-20260603/insight.json。
跑完告诉我，我去 web 端 8504 看产物 + 在『立项篮』导出 onepager。
```

完成条件：`runs/美毛猫粮-20260603/insight.json` 落盘。Dashboard 会自动检测到。
