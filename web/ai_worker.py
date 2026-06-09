"""一键洞察 worker — 跑 cross-industry-insight skill。

主路：llm-api.net 的 Anthropic 兼容代理 + claude-opus-4-8
备路：OpenRouter + deepseek-v3.2（当 model 名以 deepseek/ 开头时走 OpenRouter）
"""
import json
import os
import signal
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class LLMHardTimeout(Exception):
    """SDK 的 read timeout 在 proxy 断流时不可靠时的兜底硬超时。"""

# 加载 OpenRouter key
_ENV_PATH = Path("~/AI/openrouter-demo/.env").expanduser()
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

DEFAULT_MODEL = "claude-opus-4-8"  # 单步跑或 Step 2（brand_actions 深度升级）
DEFAULT_SKELETON_MODEL = "deepseek/deepseek-v3.2"  # Step 1 骨架 — 单价低、能装更多输出
DEFAULT_MAX_TOKENS = 16000  # llm-api.net 代理实测输出上限 ~7K，OpenRouter deepseek 上限大

SYSTEM_PROMPT = """你是为宠物食品产品经理（乖宝 / 麦富迪 体系）服务的「跨行业洞察分析师」。

🚨🚨🚨【最高优先级硬约束】industries 数组必须有 **5 或 6 个** 对标行业，少于 5 个 = 整个 JSON 不合格被打回。
不要因为"觉得相关性不够"就偷懒只给 3 个——你的任务是穷举可借鉴行业（即使部分相关性弱也要列），PM 来筛。
准备 5-6 个角度互补的行业：直接对标（同一母需求）+ 间接借鉴（叙事/渠道/工艺/形态）。


你的方法论（严格遵循）：
1. 把 PM 输入的产品概念抽象到「母需求」层（去掉物种/品类限定词，保留本质诉求）
2. 列 5-6 个对标行业 —— 在该母需求上更成熟、有可迁移的成分/形态/模式/话术
3. 每个行业按【十维度 + 演化时间线 + 行业现状 + 借鉴焦点 + 扣回宠物痛点】完整拆解
4. 提取 5-8 个跨行业可迁移机会，按 v/f/d (1-5) 打分，标红海与禁区
5. 给 Top 3 推荐（综合 = v × f × d 最高的 3 条）

宠物专业约束：
- 成分禁区：木糖醇、葡萄/葡萄干、洋葱、大蒜、可可/咖啡因、夏威夷果、酒精——对犬有毒
- 不得宣称疾病治疗功效（"体重管理"OK，"治疗肥胖"违规）
- 决策人 ≠ 使用者：主人买单（焦虑/愧疚/省心/面子是支点），狗/猫使用
- 所有行业数据若不能确证就在 evidence/data_validation 里标"待核实"，不要瞎编精确数字

输出严格 JSON（用下面这个 schema，**不要任何解释、不要 markdown 包裹、直接 JSON**）：

{
  "concept": "（PM 输入的概念原文）",
  "generated_at": "YYYY-MM-DD",
  "baseline": {
    "current_product": "...", "current_weakness": "...",
    "decision_maker": "...", "user": "..."
  },
  "mother_needs": ["...", "..."],
  "industries": [
    {
      "name": "对标行业名",
      "borrow": "一句话写借鉴焦点（要迁移的核心维度，避免口语化）",
      "why_chosen": "**为什么选这个行业作为对标**（30-60 字，一句话讲清逻辑）。要扣回母需求 / baseline，说明这个行业凭什么是值得借鉴的（例：『这个行业是减脂赛道的『心智旗手』，建立了用户对科学减重的认知，宠物体重管理无法绕过；其 GLP-1 时代的渠道与话术对宠粮高端化有直接参考价值』）",
      "pet_pain_link": "2-3 句话：这个借鉴焦点扣回宠物现款的哪个具体痛点（baseline.current_weakness）",
      "dimensions": {
        "pain_point": "...", "target_user": "...", "ingredient_tech": "...",
        "product_form": "...", "narrative": "...", "price_band": "...",
        "business_model": "...", "competitors": "...", "regulation": "...",
        "evidence": "..."
      },
      "data_validation": [
        {"source": "taboo/pubmed/web 等占位", "query": "...", "hypothesis": "需要验证的假设", "finding": "DEMO 推断 · 待真跑验证", "sample_size": 0}
      ],
      "solution_stack": {
        "signature_ingredients": ["该行业用来解决核心问题的 3-5 个标志性成分（具体到分子/原料名，避免泛词）", "..."],
        "key_processes": ["2-4 个关键工艺 / 技术（如低温分子蒸馏、微胶囊包埋、冷压萃取、菌株活性保护）", "..."],
        "delivery_form": "递送形态与剂型创新（如软胶囊 / 微囊缓释 / 滴剂 / 喷雾 / 即食条），一句话",
        "quality_proof": "品质 / 功效信号（如 GOED 认证 / IFOS 五星 / 第三方 GC-MS 检测 / 临床 RCT 报告），一句话",
        "transferability_note": "**一句话扣回宠物**：这个技术栈里哪些可直接迁移、哪些要改造（涉及宠物禁区/适口性/法规）"
      },
      "trends": {
        "tech": ["**本行业的技术趋势 / 新兴技术方向**，每条 25-40 字，3-4 条。例：『后生元/灭活菌+代谢物取代活菌（活性可标定，免冷链）』", "..."],
        "ingredient": ["**本行业的成分趋势 / 新原料热点**，每条 25-40 字，3-4 条。例：『单菌株高剂量+临床数据（LGG/BB-12）取代复合堆料』", "..."],
        "formula": ["**本行业的配方架构趋势 / 剂型创新**，每条 25-40 字，3-4 条。例：『基础益生菌+场景适配双层架构（晨夜分剂、按月龄分段）』", "..."]
      },
      "timeline": [
        {
          "era": "阶段名（如 萌芽期 / 成长期 / 爆发期 / 成熟期 / 转型退潮期）",
          "year_range": "例 2015-2018",
          "summary": "这阶段在干什么（一句话）",
          "breakthrough": "**该 era 的差异破局点**（30-60 字）—— 跟前一个 era 相比，谁/什么把行业推到了新阶段？是新成分、新人群、新场景、新渠道、还是新政策？要点名是哪类 player 怎么破的。例：『药房派失守、新消费派靠功能性零食化（小蓝瓶/每日的菌）把益生菌从『保健品柜』搬进『年轻女性零食袋』，价位带从 200+ 拉到 30 元单包』",
          "tech_advance": "**该 era 在成分/工艺/形态上的关键演进**（30-60 字）—— 出现了什么新成分、新工艺、新形态？解决了什么旧痛点？例：『EE 型 Omega-3 取代 TG 型，吸收率从 30% 升到 70%；同期软胶囊+氮气填充工艺解决鱼油氧化腥味问题』",
          "consumer_mindset": "那时候消费者对这个品类的主流认知（**至少 80-120 字，必须包含 4 个维度**）：① 认知层（怎么理解这个品类、信什么）② 情绪层（焦虑/向往/抵触/好奇 等情绪状态）③ 行为层（怎么买、怎么用、问谁意见）④ 圈层差异（哪些人先用 vs 大众怎么看）。要写出时代画面感，避免抽象套话。例：『2005-2010 益生菌在中国还是新概念。**认知上**多数人把它等同『有助消化的酸奶』，分不清菌株差别，对『活菌数』『定植率』概念陌生；**情绪上**白领开始有『亚健康焦虑』，但保健品市场被脑白金式营销污染，对功效宣称半信半疑；**行为上**靠药店导购 / 妈妈群口碑做决策，电商渗透低，价格敏感；**圈层上**高知白领+一线妈妈先尝鲜（看美国 Reddit / 海淘 BB 益生菌），三四线还在喝普通酸奶』",
          "era_pain_point": "当时消费者未被充分满足的核心痛点（**至少 80-120 字，必须包含 3 个层次**）：① 表层痛（消费者自己能说出来的不满，如效果慢/价格贵）② 隐性痛（消费者自己没说但实际存在的痛，如选择困难/不会用）③ 心智空白（被这个品类教育但没被满足的期待）。每一层都要具体，最好带场景。例：『**表层痛**：益生菌动辄几百元一瓶，吃了一两周『没明显感觉』就弃用，复购率低；**隐性痛**：菌株名（动双 BB-12 / 鼠李糖 LGG）全是英文缩写，消费者根本不知道选哪个，只能靠品牌信任度盲选；**心智空白**：被『调节肠道菌群』概念种草后，期待有可量化的反馈（什么时候见效、怎么知道起作用了），但没有任何品牌能给』",
          "competitive_map": "该时代下行业的赛道地图与品牌占位（**至少 120-180 字**）。要：① 划出 3-4 个明确的竞争阵营 / 流派；② 每个阵营点名 1-2 个代表品牌；③ 说清每个阵营的差异化打法（产品 / 渠道 / 人群 / 价位）；④ 阵营之间是怎么互相区隔 vs 互相抢用户的。例：『分四派——**高端临床派**（Life Space 澳洲 / 合生元法国）走母婴渠道+专利菌株+几百元价位，吃用户对『海外+科研』的信任；**大众保健派**（汤臣倍健益生菌粉 / 善存）走药店+商超+电视广告，主打『性价比+全家适用』，单价百元内；**年轻女性派**（WonderLab 小蓝瓶 / 每日的菌）走天猫+小红书+联名包装，把益生菌『零食化饮品化』，主打瘦身/美肤场景；**功能细分派**（Culturelle康萃乐 / 修益升）切免疫力 / 过敏等垂直细分，靠儿科医生背书。前两派抢主流人群，后两派抢年轻心智』",
          "opportunities": ["该阶段浮现的机会点 1", "..."],
          "brand_actions": [
            {
              "brand": "阵营1的代表品牌（如高端进口派的 Life Space）",
              "insight": "**消费者心智洞察**（60-100 字，要写出该时代具体的心智误解/期待/未满足动机+消费场景）。例：『一二线高知妈妈被国外母婴论坛种草，相信『海外专利菌株』比国产可靠，但又怕跨境购买没保障；母婴店导购的话术决策权高，妈妈在 0-3 岁阶段焦虑值最高、对价格不敏感』",
              "action": {
                "formula": {
                  "core_ingredient": "**核心成分**（20-40 字，要具体到学名/菌株代号/分子缩写）。例：『BB-12® 动物双歧杆菌 + LGG® 鼠李糖乳杆菌，100 亿 CFU/条』",
                  "patent_or_standard": "**专利 / 标准 / 规格**（20-40 字，要带具体专利号/认证名）。例：『科汉森 BB-12 + Valio LGG 专利菌株；IFOS 五星；FDA GRAS』",
                  "differentiation": "**vs 同类的差异化**（20-40 字，点名比谁强）。例：『vs 复合多菌株主张『单一明星菌株+高剂量+临床全』』"
                },
                "process": {
                  "tech_name": "**工艺/技术名**（10-30 字，行业标准术语）。例：『冷冻干燥+微胶囊包埋（FloraActiv™）+ 铝箔条装』",
                  "how_it_works": "**工艺怎么做的**（25-50 字，关键步骤+参数）。例：『-40℃ 冷冻干燥锁活；HPMC 微胶囊抗胃酸；氮气填充阻氧；TGA GMP 工厂全程冷链』",
                  "advantage": "**带来的优势**（20-40 字，最好量化）。例：『胃酸存活率从 5% 提到 80%；24 个月常温不掉活』"
                },
                "selling_point": "**卖点/叙事调整**（30-60 字）：传播话术 hook、视觉锤、人群话术。例：『澳洲专利菌株 + 母婴医院同款，绑定『1000 天免疫黄金期』』"
              },
              "positioning": "**市场+心智双视角占位**（60-100 字）：① 市场位置（vs 谁、价位段、渠道、份额）② 心智位置（用户记得它什么、跟竞品的差异化标签）。例：『市场位置：母婴渠道高端进口益生菌 Top3，¥350-450/盒，主攻一二线高知妈妈；心智位置：用户提起『婴幼儿专用益生菌』脑中冒出 Life Space，把『海外母婴专研』标签从泛保健品里独立出来』"
            },
            {
              "brand": "阵营2的代表品牌（如大众保健派的 汤臣倍健）",
              "insight": "...",
              "action": {"formula": "...", "process": "...", "selling_point": "..."},
              "positioning": "..."
            },
            {
              "brand": "阵营3的代表品牌（如年轻女性派的 WonderLab）",
              "insight": "...",
              "action": {"formula": "...", "process": "...", "selling_point": "..."},
              "positioning": "..."
            },
            {
              "brand": "阵营4的代表品牌（如功能细分派的 Culturelle康萃乐）",
              "insight": "...",
              "action": {"formula": "...", "process": "...", "selling_point": "..."},
              "positioning": "..."
            }
          ]
        }
      ],
      "current_state": "一段话：行业当前局面（红海/蓝海/退潮/稳态），头部格局，主要矛盾"
    }
  ],
  "opportunities": [
    {
      "title": "机会一句话标题",
      "from_industry": "来源行业（与 industries[].name 之一对应）",
      "mechanism": "借的底层机制（如 即时反馈/进度可视化/订阅复购/专业背书/分阶段目标）",
      "value": 4, "feasibility": 3, "differentiation": 4,
      "transfer_note": "怎么迁移到宠物侧的具体落地要点",
      "taboo": "禁区/风险（如有）",
      "is_red_ocean": false,
      "concept_detail": {
        "ingredients": "具体成分建议（注意宠物禁区）",
        "tech": "技术/工艺建议",
        "product_form": "产品形态/包装",
        "trust_backing": "信任背书方式（兽医协会/临床/案例等）"
      }
    }
  ],
  "top_picks": ["机会标题1", "机会标题2", "机会标题3"],
  "trends": {
    "tech_trends": [
      {
        "trend": "**跨行业整体技术趋势**（30-60 字，从 industries.trends.tech 横切归纳出的共性方向）。例：『2020 起冷冻干燥取代喷雾干燥成为活菌保护新标准，活菌存活率从 30% 提到 80%』",
        "evidence_industries": ["该趋势在哪些行业出现过（取 industries[].name，2-4 个）"]
      }
    ],
    "ingredient_trends": [
      {
        "trend": "**跨行业整体成分趋势**（30-60 字）。例：『单一明星成分+高剂量+临床数据，取代复合配方成为高端定位新标配（LGG/HMO/5%鱼油/神经酰胺）』",
        "evidence_industries": ["..."]
      }
    ],
    "formula_trends": [
      {
        "trend": "**跨行业整体配方架构趋势**（30-60 字）。例：『从单一功效配方转向『基础功效 + 场景适配』双层架构』",
        "evidence_industries": ["..."]
      }
    ]
  }
}

📌 注：
- 顶层 `trends` 是**跨行业整体总结**（横切归纳出的共性方向，3-5 条/类）
- 每个 `industry.trends` 是**该行业的特点**（细节，3-4 条/类）
- UI 会同时呈现两者：PM 既看个性也看共性

字段量约束（⚠️ 优先级从高到低，token 紧张时按此优先级保留）：

【P0 - 绝对不可省，少了 = 整个 JSON 不合格】
- industries: 5-6 个
- 每个 industry 必填 **why_chosen**（30-60 字）
- 每个 industry 必填 **solution_stack**（行业是怎么解决核心问题的——成分/工艺/形态/品质信号/可迁移性，5 个子字段都要填，每个 20-40 字）
- 每个 industry 的 **timeline: 3 个 era**（覆盖萌芽/成长 → 爆发/成熟 → 转型/退潮 三阶段；不要 4-5，token 紧张）
- **每个 era 必填 breakthrough**（20-40 字，该 era 的差异破局点）
- **每个 era 必填 tech_advance**（20-40 字，成分/工艺/形态层面的演进）
- **每个 era 的 brand_actions 必须 ≥ 3 条**，每条**完整四字段**：
  - `brand`：品牌名
  - `insight`：消费者心智洞察（60-100 字，要有时代具体性 + 场景）
  - `action`：**必须是 object**，含 `{formula: object, process: object, selling_point: string}`：
    - `formula` 是 object，含 `{core_ingredient, patent_or_standard, differentiation}` 三子项（各 30-60 字，**必须有具体菌株/分子/专利号/标准号**，不能空话）
    - `process` 是 object，含 `{tech_name, how_it_works, advantage}` 三子项（**必须有具体工艺名 + 关键参数 + 最好量化的优势**）
    - `selling_point` 是 string（40-80 字）
  - `positioning`：市场+心智双视角占位（60-100 字）
  ⚠️ **formula 和 process 必须拆成子 object**，少任何一个子字段 = 不合格
- top_picks: 必须 3 个
- **trends**：必填，含 tech_trends / ingredient_trends / formula_trends 三类，每类 4-6 条，每条含 trend (30-60 字) + evidence_industries（2-4 个行业名，必须从 industries[].name 里挑）。这是把 industries 横切归纳的"跨行业共性趋势"，比单个行业的 tech_advance 高一层视角

【P1 - 重要但可压缩】
- 每个 era 的 consumer_mindset / era_pain_point / competitive_map：**目标字数 40-70 字**（简短要点齐）
- opportunities: 5-7 条，其中 1-2 条标 is_red_ocean=true（控制条数）
- dimensions 十维：每维 15-25 字（简短）
- data_validation: 每行业 1-2 条占位即可

【总长度硬约束】
🚨 **整体 JSON 输出严格控制在 12000 字以内**（约 6000 token）—— 代理实测稳定上限 ~7K token 输出。
- 估算：5 行业 × 3 era × 3 brand_actions（只填 brand 名）= 45 brand_actions × 15 字 ≈ 700 字
- + 5 行业 × 3 era × 200 字（mindset+pain+cmap+breakthrough+tech_advance+summary） ≈ 3000 字
- + 5 行业 × solution_stack 250 字 + dimensions 200 字 + current_state 80 字 + why_chosen 50 字 ≈ 2900 字
- + opportunities 5 条 × 200 字 ≈ 1000 字 + trends 12 条 × 50 字 ≈ 600 字
- 合计 ≈ 8200 字 = 4K token，安全
- **绝不省 P0 字段数量**（行业 5 个、era 3 个、brand_actions ≥3 个、trends ≥3 条/类）；只能压字数
"""


def build_user_prompt(input_data: dict) -> str:
    concept = input_data.get("concept", "—")
    weakness = input_data.get("current_weakness", "—")
    product = input_data.get("current_product", "—")
    decision_maker = input_data.get("decision_maker", "—")
    user_ = input_data.get("user", "—")
    objective = input_data.get("objective", "") or "（未填）"
    mother_hints = input_data.get("mother_needs") or []
    mother_line = "（PM 未预设，请你抽象）" if not mother_hints else f"（PM 预设：{ ' / '.join(mother_hints) }，可参考也可调整）"

    return f"""请按已给定的 schema 产出完整 insight.json。

【升级概念】{concept}
【现款产品】{product}
【现款短板 / 升级诉求】{weakness}
【决策人画像】{decision_maker}
【使用者（猫/狗）】{user_}
【长期目标】{objective}
【母需求提示】{mother_line}

⚠️ 严格遵守（assistant 已经预填了 `{{`，你只需续写后续内容）：
- 我已经替你打好 JSON 起始 `{{`，**你的响应应该直接续写**：第一个字符是字段名引号 `"`（如 `"concept": "..."`）
- 不要再写一个 `{{`（会变成 `{{{{`），不要写 ```json，不要写任何英文前言/规划文字
- 不要使用工具/函数调用，直接续写 JSON 文本
- baseline 4 个字段原样填回（current_product/current_weakness/decision_maker/user）
- concept 用上面的「升级概念」原文
- generated_at = {datetime.now().strftime("%Y-%m-%d")}
4. mother_needs、industries（5-6 个，每个含完整十维 + 时间线 + 当下 + 借鉴 + 痛点扣回）、opportunities（5-8 条，含 concept_detail）、top_picks（3 条）

直接输出 JSON，不要 markdown 围栏，不要任何解释文字。"""


def _is_anthropic_model(model: str) -> bool:
    """claude-* 走 Anthropic；deepseek/* 等走 OpenRouter。"""
    return model.startswith("claude") or model.startswith("anthropic/")


def _strip_md_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("\n", 1)[0]
        s = s.strip()
    return s


def _call_llm(client, model: str, messages: list, hard_timeout: int = 600) -> str:
    """统一调 LLM，按 model 名分发到 Anthropic 或 OpenRouter。

    都加 signal.alarm 硬超时（SDK 的 read timeout 在长输出断流时不可靠）。
    """
    def _on_alarm(signum, frame):
        raise LLMHardTimeout(f"LLM 调用超过 {hard_timeout}s 硬超时")

    old_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(hard_timeout)
    try:
        if _is_anthropic_model(model):
            # Anthropic 协议：system 单独传，messages 只含 user/assistant
            system_msg = ""
            user_msgs = []
            for m in messages:
                if m["role"] == "system":
                    system_msg += (m["content"] + "\n")
                else:
                    user_msgs.append(m)
            # prefill assistant=`{` 强制以 JSON 开头（避免 Opus 4.8 输出英文前言/规划文字）
            prefilled_messages = list(user_msgs) + [{"role": "assistant", "content": "{"}]
            resp = client.messages.create(
                model=model,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=system_msg.strip(),
                messages=prefilled_messages,
            )
            if not resp.content:
                raise ValueError("Anthropic resp.content 为空")
            body = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            if not body:
                raise ValueError("Anthropic resp 无 text block")
            # 把 prefilled 的 { 补回来，得到完整 JSON
            # 但若 LLM 自己也加了 {（因 user prompt 要求"第一字符必须是 {"），避免双 {
            body_lstrip = body.lstrip()
            if body_lstrip.startswith("{"):
                raw = body  # LLM 已自带 {，prefill 的不补
            else:
                raw = "{" + body
        else:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                extra_headers={
                    "HTTP-Referer": "http://localhost:8504",
                    "X-Title": "cross-industry-insight-web",
                },
            )
            if resp.choices is None or not resp.choices:
                raise ValueError("OpenRouter resp.choices 为空")
            raw = resp.choices[0].message.content or ""
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    return _strip_md_fence(raw)


def generate_insight(input_data: dict, model: str = DEFAULT_MODEL, timeout: int = 600,
                     max_retries: int = 2, raw_dump_path: Path = None) -> dict:
    """调 LLM 生成 insight.json。失败时重试 max_retries 次。

    model 名以 claude- 开头走 llm-api.net 的 Anthropic 代理；其余走 OpenRouter。
    """
    if _is_anthropic_model(model):
        if Anthropic is None:
            raise RuntimeError("未安装 anthropic SDK：pip install anthropic")
        key = os.environ.get("LLMAPI_NET_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        base = os.environ.get("LLMAPI_NET_BASE", "https://llm-api.net")
        if not key:
            raise RuntimeError(
                "未找到 LLMAPI_NET_KEY；请检查 ~/AI/openrouter-demo/.env 是否包含该变量。"
            )
        client = Anthropic(api_key=key, base_url=base, timeout=timeout)
    else:
        if OpenAI is None:
            raise RuntimeError("未安装 openai SDK：pip install openai")
        if "OPENROUTER_API_KEY" not in os.environ:
            raise RuntimeError(
                "未找到 OPENROUTER_API_KEY；请检查 ~/AI/openrouter-demo/.env。"
            )
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            timeout=timeout,
        )

    base_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(input_data)},
    ]

    last_err = None
    last_raw = ""
    last_violations = []  # 上一轮 brand_actions/why_chosen 不达标的明细
    data = None
    for attempt in range(max_retries + 1):
        msgs = list(base_messages)
        if attempt > 0:
            hints = []
            if isinstance(last_err, LLMHardTimeout) or (
                isinstance(last_err, json.JSONDecodeError) and "Unterminated string" in str(last_err)
            ):
                # 输出过长被断流 → 让 LLM 主动控制字数
                hints.append(
                    "⚠️ 上次输出过长导致超时/断流。本次请严格控制总体输出在 25000 字以内：\n"
                    "- consumer_mindset / era_pain_point 各控制在 80-100 字（不要 150+）\n"
                    "- competitive_map 控制在 100-130 字\n"
                    "- 每个 industry 的 timeline 给 2 个 era 即可（不是 3-4）\n"
                    "- 但 **why_chosen 字段（30-60 字）和 brand_actions ≥3 条/era 仍是硬约束**，必须保\n"
                )
            elif isinstance(last_err, (json.JSONDecodeError, ValueError)) and "JSON" in str(last_err):
                hints.append(
                    "1. 字符串内禁止未转义的 ASCII 双引号 \"，如需引号请用中文「」或单引号 '\n"
                    "2. 禁止用换行符直接放在字符串中间（用 \\n 转义）\n"
                    "3. 不要 markdown 围栏，直接 { 开头"
                )
            if last_violations:
                viol_text = "\n".join(f"  - {v}" for v in last_violations[:20])
                hints.append(
                    "⚠️ 上次输出在以下位置不达标，本次必须修正：\n" + viol_text
                    + "\n\n请重新输出完整 JSON，特别注意（按优先级）：\n"
                    + "(a) 每个 industry 必填 why_chosen（30-60 字）\n"
                    + "(b) 每个 industry 必填 solution_stack（含 signature_ingredients 列表 + key_processes 列表 + delivery_form + quality_proof + transferability_note）\n"
                    + "(c) 每个 industry 的 timeline 必须有 ≥ 4 个 era（覆盖完整发展周期：萌芽 → 成长 → 爆发 → 成熟 → 转型/退潮）\n"
                    + "(d) 每个 era 必填 breakthrough（差异破局点）+ tech_advance（成分/工艺演进）+ brand_actions ≥ 3 条\n"
                    + "(e) 如果 token 不够，请压缩 consumer_mindset/era_pain_point/competitive_map 的字数到 40-80 字，绝不省 P0 字段数量"
                )
            if hints:
                msgs.append({"role": "user", "content": "\n\n".join(hints)})
        try:
            s = _call_llm(client, model, msgs)
            last_raw = s
            data = json.loads(s)

            # 字段量校验（包 try/except 防止结构异常炸到 raise）
            violations = []
            try:
                # trends 三类校验
                trends = data.get("trends")
                if not isinstance(trends, dict):
                    if trends is None:
                        violations.append("[trends] 缺顶层 trends 字段（要 tech_trends/ingredient_trends/formula_trends 三类）")
                    else:
                        violations.append(f"[trends] 应为 object，当前是 {type(trends).__name__}")
                    trends = {}
                for tkey in ("tech_trends", "ingredient_trends", "formula_trends"):
                    items = trends.get(tkey) or []
                    if not isinstance(items, list):
                        violations.append(f"[trends.{tkey}] 应为 array，当前是 {type(items).__name__}")
                        items = []
                    if len(items) < 3:
                        violations.append(
                            f"[trends.{tkey}] 只有 {len(items)} 条（要 ≥3，建议 4-6 条横切归纳）"
                        )
                    for ti, item in enumerate(items):
                        if not isinstance(item, dict):
                            violations.append(f"[trends.{tkey}[{ti}]] 应为 object，当前是 {type(item).__name__}")
                            continue
                        if not (item.get("trend") or "").strip():
                            violations.append(f"[trends.{tkey}[{ti}]] 缺 trend 字段")
                        if not item.get("evidence_industries"):
                            violations.append(f"[trends.{tkey}[{ti}]] 缺 evidence_industries（要列 2-4 个行业名）")
            except Exception as _ve:
                violations.append(f"⚠️ trends 校验崩溃: {type(_ve).__name__}: {_ve}")

            for idx, ind in enumerate(data.get("industries", [])):
                if not isinstance(ind, dict):
                    violations.append(f"[industry[{idx}]] 应为 object，当前是 {type(ind).__name__}")
                    continue
                iname = ind.get("name", f"industry[{idx}]")
                why = (ind.get("why_chosen") or "").strip()
                if not why:
                    violations.append(f"[{iname}] 缺 why_chosen 字段")
                sol = ind.get("solution_stack") or {}
                if not isinstance(sol, dict) or not sol.get("signature_ingredients") or not sol.get("key_processes"):
                    violations.append(
                        f"[{iname}] solution_stack 缺 signature_ingredients/key_processes（需含成分+工艺清单）"
                    )
                # industry.trends 校验
                ind_trends = ind.get("trends") or {}
                if not isinstance(ind_trends, dict):
                    violations.append(f"[{iname}] trends 应为 object（含 tech/ingredient/formula 三类）")
                else:
                    for tkey in ("tech", "ingredient", "formula"):
                        items = ind_trends.get(tkey) or []
                        if not isinstance(items, list) or len(items) < 2:
                            violations.append(
                                f"[{iname}] trends.{tkey} 只有 {len(items) if isinstance(items, list) else 0} 条（要 ≥2，建议 3-4 条）"
                            )
                eras = ind.get("timeline", []) or []
                if len(eras) < 3:
                    violations.append(
                        f"[{iname}] timeline 只有 {len(eras)} 个 era（要 ≥3，覆盖萌芽/爆发/成熟三阶段）"
                    )
                for eidx, era in enumerate(eras):
                    if not isinstance(era, dict):
                        violations.append(f"[{iname} → era[{eidx}]] 应为 object，当前是 {type(era).__name__}")
                        continue
                    ename = era.get("era", f"era[{eidx}]")
                    if not (era.get("breakthrough") or "").strip():
                        violations.append(f"[{iname} → {ename}] 缺 breakthrough（差异破局点）")
                    if not (era.get("tech_advance") or "").strip():
                        violations.append(f"[{iname} → {ename}] 缺 tech_advance（成分/工艺演进）")
                    bas = era.get("brand_actions") or []
                    if len(bas) < 3:
                        violations.append(
                            f"[{iname} → {ename}] brand_actions 只有 {len(bas)} 条（要 ≥3）"
                        )
                    # action 必须是 dict；formula/process 必须是子 object 含三子项
                    for bidx, ba in enumerate(bas):
                        if not isinstance(ba, dict):
                            violations.append(f"[{iname} → {ename} → brand_action[{bidx}]] 应为 object，当前是 {type(ba).__name__}")
                            continue
                        bname = ba.get("brand", f"brand[{bidx}]")
                        act = ba.get("action")
                        if not isinstance(act, dict):
                            violations.append(
                                f"[{iname} → {ename} → {bname}] action 应为 object（含 formula/process/selling_point），当前为 {type(act).__name__}"
                            )
                            continue
                        # formula 校验
                        formula = act.get("formula")
                        if not isinstance(formula, dict):
                            violations.append(
                                f"[{iname} → {ename} → {bname}] action.formula 应为 object（含 core_ingredient/patent_or_standard/differentiation），当前为 {type(formula).__name__}"
                            )
                        else:
                            for k in ("core_ingredient", "patent_or_standard", "differentiation"):
                                if not (formula.get(k) or "").strip():
                                    violations.append(
                                        f"[{iname} → {ename} → {bname}] action.formula.{k} 为空"
                                    )
                        # process 校验
                        process_v = act.get("process")
                        if not isinstance(process_v, dict):
                            violations.append(
                                f"[{iname} → {ename} → {bname}] action.process 应为 object（含 tech_name/how_it_works/advantage），当前为 {type(process_v).__name__}"
                            )
                        else:
                            for k in ("tech_name", "how_it_works", "advantage"):
                                if not (process_v.get(k) or "").strip():
                                    violations.append(
                                        f"[{iname} → {ename} → {bname}] action.process.{k} 为空"
                                    )
                        # selling_point 仍是字符串
                        if not (act.get("selling_point") or "").strip():
                            violations.append(
                                f"[{iname} → {ename} → {bname}] action.selling_point 为空"
                            )
            if violations:
                last_violations = violations
                raise ValueError(
                    f"字段量不达标：{len(violations)} 处违规（前 3 处：{violations[:3]}）"
                )
            break
        except (json.JSONDecodeError, ValueError, LLMHardTimeout) as e:
            last_err = e
            if attempt == max_retries:
                if raw_dump_path:
                    raw_dump_path.write_text(last_raw, encoding="utf-8")
                # 字段量不达标时——降级：仍返回 data 但加 _violations 标记
                if "字段量不达标" in str(e) and "data" in dir():
                    data["_violations"] = last_violations
                    data["_validation_failed_after_retries"] = max_retries + 1
                    print(f"⚠️ 字段量在 {max_retries + 1} 次尝试后仍不达标，降级接受：{len(last_violations)} 处")
                    break
                raise ValueError(
                    f"LLM 输出在 {max_retries + 1} 次尝试后失败：{e}"
                    + (f"\nraw 已落盘：{raw_dump_path}" if raw_dump_path else f"\n前 500 字：{last_raw[:500]}")
                )

    # 最基础 schema 校验
    required_keys = ["concept", "baseline", "mother_needs", "industries", "opportunities", "top_picks"]
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ValueError(f"LLM 输出缺字段：{missing}")
    if not data["industries"]:
        raise ValueError("LLM 输出 industries 为空")
    if not data["opportunities"]:
        raise ValueError("LLM 输出 opportunities 为空")

    # 自动加生成日期（若 LLM 没填）
    data.setdefault("generated_at", datetime.now().strftime("%Y-%m-%d"))
    data["_ai_generated"] = True
    data["_ai_model"] = model
    return data


# ───────────────────────────────────────────────────────────
#  两步跑（骨架 + brand_actions 升级）—— 绕开 llm-api.net 16K token 限制
# ───────────────────────────────────────────────────────────

_SKELETON_HINT = """

🚨🚨🚨 重要：本次是「两步跑」的第一步！请遵守：

- **brand_actions 数组里每个 era 给 ≥3 个品牌**，但**每个品牌只填 `brand` 字段（品牌名）**
- 其他字段全部留空字符串 ""：`insight: ""`, `action: ""`, `positioning: ""`
- **不要写 action 的 formula/process/selling_point 子项**，action 直接是空字符串就行
- 这样能省 token，第二步会专门把 brand_actions 升级为深度因果链版

示例（每个 era 的 brand_actions 写法）：
```
"brand_actions": [
  {"brand": "Life Space", "insight": "", "action": "", "positioning": ""},
  {"brand": "汤臣倍健", "insight": "", "action": "", "positioning": ""},
  {"brand": "WonderLab", "insight": "", "action": "", "positioning": ""}
]
```

**其他字段（why_chosen, solution_stack, timeline 的 breakthrough/tech_advance/consumer_mindset/era_pain_point/competitive_map/opportunities, current_state, opportunities, trends, top_picks）全部正常填全**。
"""


_BA_UPGRADE_SYSTEM = """你是一个产品策略分析师。你的任务：把给定的"品牌列表"升级为"深度因果链 brand_actions"。

每个 brand_action 必须有四字段（严格结构）：
{
  "brand": "品牌名（原样）",
  "insight": "**消费者心智洞察**（60-100 字）：那时代消费者对该品类的心智误解/期待/未满足动机+消费场景。要具体不要空话",
  "action": {
    "formula": {
      "core_ingredient": "**核心成分**（20-40 字，要具体到学名/菌株代号/分子缩写/原料名）",
      "patent_or_standard": "**专利 / 标准 / 含量规格**（20-40 字，要带具体专利号/认证名）",
      "differentiation": "**vs 同类的差异化**（20-40 字，点名比谁强）"
    },
    "process": {
      "tech_name": "**工艺/技术名**（10-30 字，行业标准术语）",
      "how_it_works": "**工艺怎么做的**（25-50 字，关键步骤+参数）",
      "advantage": "**带来的优势**（20-40 字，最好量化）"
    },
    "selling_point": "**卖点/叙事调整**（30-60 字）"
  },
  "positioning": "**市场+心智双视角占位**（60-100 字）"
}

🚨 严格 JSON 输出，response_format 是 object：
{ "<era 名>": [<brand_action 对象数组>], ... }

assistant 已经预填了 `{` —— 你直接续写第一个字段名（era 名）的引号 `"` 开始
不要再写一个 `{`，不要 markdown 围栏，不要前言。
"""


def _generate_skeleton(input_data: dict, model: str = DEFAULT_SKELETON_MODEL,
                       timeout: int = 600, max_retries: int = 1,
                       raw_dump_path: Path = None) -> dict:
    """Step 1：跑骨架，brand_actions 只列 brand 名。

    默认 deepseek-v3.2（单价低、能产更多 token，骨架填结构化字段足够）。
    """
    # 临时把 input_data 包一层，让 build_user_prompt 末尾追加 skeleton hint
    orig_user_prompt = build_user_prompt(input_data)
    skeleton_user_prompt = orig_user_prompt + _SKELETON_HINT

    # 复刻 generate_insight 的内部 client 创建 + retry，但用 skeleton_user_prompt
    if _is_anthropic_model(model):
        client = Anthropic(
            api_key=os.environ.get("LLMAPI_NET_KEY") or os.environ.get("ANTHROPIC_API_KEY"),
            base_url=os.environ.get("LLMAPI_NET_BASE", "https://llm-api.net"),
            timeout=timeout,
        )
    else:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            timeout=timeout,
        )

    base_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": skeleton_user_prompt},
    ]

    last_err = None
    last_raw = ""
    for attempt in range(max_retries + 1):
        try:
            msgs = list(base_messages)
            if attempt > 0 and isinstance(last_err, ValueError) and "industries" in str(last_err):
                msgs.append({
                    "role": "user",
                    "content": (
                        f"⚠️ 上次只产了 {last_err} —— industries 必须 ≥5 个！\n"
                        "请重新输出完整骨架 JSON，industries 数组**严格 5 或 6 个**对标行业，"
                        "不要偷懒。如果直接对标行业不够 5 个，就补充间接借鉴行业（叙事/渠道/工艺/形态相似的）凑够 5 个。"
                    ),
                })
            s = _call_llm(client, model, msgs)
            last_raw = s
            data = json.loads(s)
            # 行业数量校验
            inds = data.get("industries") or []
            if len(inds) < 5:
                raise ValueError(f"骨架只有 {len(inds)} 个行业（要 ≥5）")
            break
        except (json.JSONDecodeError, ValueError, LLMHardTimeout) as e:
            last_err = e
            if attempt == max_retries:
                if raw_dump_path:
                    raw_dump_path.write_text(last_raw, encoding="utf-8")
                raise ValueError(f"Step 1 骨架在 {max_retries+1} 次尝试后失败：{e}")

    data.setdefault("generated_at", datetime.now().strftime("%Y-%m-%d"))
    data["_ai_generated"] = True
    data["_ai_model"] = model
    data["_two_step"] = True
    return data


def _upgrade_industry_brand_actions(industry: dict, concept: str,
                                    model: str = DEFAULT_MODEL,
                                    timeout: int = 600, max_retries: int = 1) -> dict:
    """Step 2：升级某个 industry 的所有 era 的 brand_actions。默认 Opus 4.8（推理深度强）。"""
    if _is_anthropic_model(model):
        client = Anthropic(
            api_key=os.environ.get("LLMAPI_NET_KEY") or os.environ.get("ANTHROPIC_API_KEY"),
            base_url=os.environ.get("LLMAPI_NET_BASE", "https://llm-api.net"),
            timeout=timeout,
        )
    else:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            timeout=timeout,
        )

    iname = industry.get("name", "?")
    # 构造每个 era 的品牌清单 + 时代背景作为 context
    era_briefs = []
    for era in industry.get("timeline", []) or []:
        brands = [ba.get("brand", "") for ba in (era.get("brand_actions") or []) if isinstance(ba, dict)]
        era_briefs.append({
            "era": era.get("era", ""),
            "year_range": era.get("year_range", ""),
            "summary": era.get("summary", ""),
            "consumer_mindset": (era.get("consumer_mindset") or "")[:200],
            "competitive_map": (era.get("competitive_map") or "")[:200],
            "brands": brands,
        })

    user_prompt = (
        f"母概念：{concept}\n"
        f"对标行业：{iname}\n"
        f"行业当下：{industry.get('current_state', '')[:200]}\n\n"
        f"以下是各 era 的品牌列表 + 时代背景。请把每个 era 的每个品牌升级为深度因果链 brand_action：\n\n"
        + json.dumps(era_briefs, ensure_ascii=False, indent=2)
        + "\n\n输出 JSON 格式：{ \"<era 名 1>\": [{brand, insight, action(含 formula/process/selling_point), positioning}, ...], \"<era 名 2>\": [...], ... }"
        + "\n\n🚨 assistant 已预填 `{`，你直接续写第一个 era 名的引号。不要再写 `{`，不要 markdown 围栏。"
    )

    last_err = None
    last_raw = ""
    for attempt in range(max_retries + 1):
        try:
            s = _call_llm(client, model, [
                {"role": "system", "content": _BA_UPGRADE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ])
            last_raw = s
            return json.loads(s)
        except (json.JSONDecodeError, ValueError, LLMHardTimeout) as e:
            last_err = e
            if attempt == max_retries:
                # 失败时返回 {} 让上层继续 — 该行业的 brand_actions 仍是骨架
                print(f"  ⚠️ [{iname}] brand_actions 升级失败：{e}")
                return {}


def generate_insight_two_step(input_data: dict,
                              skeleton_model: str = DEFAULT_SKELETON_MODEL,
                              ba_model: str = DEFAULT_MODEL,
                              timeout: int = 600, max_retries: int = 1,
                              raw_dump_path: Path = None,
                              progress_cb=None) -> dict:
    """两步跑：骨架默认 deepseek（省钱），brand_actions 升级默认 Opus（保深度）。"""
    print(f"[Step 1] 跑骨架（{skeleton_model}）含 timeline/solution_stack/trends/brand 名清单…")
    data = _generate_skeleton(input_data, skeleton_model, timeout, max_retries, raw_dump_path)
    inds = data.get("industries", []) or []
    print(f"  骨架 OK: {len(inds)} 行业")
    if progress_cb:
        progress_cb("skeleton_done", {"industries": len(inds)})

    print(f"[Step 2] 按 {len(inds)} 行业循环升级 brand_actions（{ba_model}）…")
    for i, ind in enumerate(inds, 1):
        iname = ind.get("name", f"industry[{i}]")
        print(f"  [{i}/{len(inds)}] 升级 {iname} …")
        if progress_cb:
            progress_cb("upgrading", {"i": i, "n": len(inds), "name": iname})
        upgraded = _upgrade_industry_brand_actions(
            ind, data.get("concept", ""), ba_model, timeout, max_retries=1
        )
        if not upgraded:
            print(f"    ⚠️ 升级失败，保留骨架版（仅 brand 名）")
            continue
        # merge：每个 era 的 brand_actions 用升级版替换
        for era in ind.get("timeline", []) or []:
            ename = era.get("era", "")
            new_bas = upgraded.get(ename)
            if isinstance(new_bas, list) and new_bas:
                era["brand_actions"] = new_bas
                print(f"    · {ename}: {len(new_bas)} 个 brand_actions 升级 OK")
    return data


def save_insight(slug: str, data: dict) -> Path:
    """落 insight.json 到 runs/<slug>/。"""
    out_dir = Path("~/AI/cross-industry-insight/runs").expanduser() / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "insight.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    # 自检
    sample = {
        "concept": "体态管理狗粮",
        "current_product": "麦富迪体重管理粮（成犬），低脂高纤配方，¥80-120/kg",
        "current_weakness": "复购偏低；概念偏旧；主人难感知效果",
        "decision_maker": "一二线城市绝育后犬主人，对体重焦虑但缺方法",
        "user": "绝育后易胖犬，5-10kg 中型犬",
        "objective": "长期体重管理 + 复购粘性",
        "mother_needs": ["哺乳动物的体重/体脂管理"],
    }
    print("调用 LLM 生成 insight…")
    d = generate_insight(sample)
    print(f"OK: industries={len(d['industries'])}  opportunities={len(d['opportunities'])}  top_picks={len(d['top_picks'])}")
    print("第一条机会：", d["opportunities"][0]["title"])
