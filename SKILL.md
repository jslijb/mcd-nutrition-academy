---
name: mcd-nutrition-academy
description: 麦麦营养学徒：用麦当劳 MCP 的真实六维营养数据（能量/蛋白质/脂肪/碳水/钠/钙）当教材，生成六节可闯关的营养科普课，并输出一张带六轴雷达图的可分享结业证。当用户说"麦麦营养课""麦当劳营养学徒""营养雷达图""看懂营养标签""这顿吃了多少""麦当劳营养结业证""mcd nutrition academy"时使用本技能。
agent_created: true
---

# 麦麦营养学徒 · MCD Nutrition Academy

用麦当劳真实菜单的六维营养数据当教材，做成六节可闯关的营养课，最后产出一张可分享的结业证。

## 何时使用

- 想把麦当劳的菜单当成营养科普素材，学懂能量/蛋白质/脂肪/碳水/钠/钙
- 想知道某一餐的六维营养结构长什么样
- 想要一张能发朋友圈的营养结业证 / 雷达图
- 想了解麦当劳 MCP 的营养相关能力

## 前置条件

- 麦当劳 MCP Token：在 open.mcd.cn 用手机号激活后复制
- 无 Token 时也能跑演示模式（使用麦当劳中国官方营养成分表作为离线数据）

## 工作流程

### 一、采集营养数据

```bash
export MDN_MCP_KEY=<用户的token>
python3 scripts/collect.py           # -> data/nutrition.json
```

`collect.py` 调用三个只读 tool：

| Tool | 用途 |
|---|---|
| `list-nutrition-foods` | 全量餐品六维营养成分表（核心数据源） |
| `order-list` | 用户历史订单（可选，用于"我常点的那几样"） |
| `query-my-account` | 会员积分（可选） |

任一 tool 失败都会降级，不会中断整条流水线。演示模式：

```bash
python3 scripts/collect.py --demo
```

### 二、生成课程与结业证

```bash
python3 scripts/build_course.py       # -> out/lesson.html, out/certificate.html
```

`build_course.py` 会：

1. 从真实营养表里**自动出题**：每课一题，选项和正确答案都从数据里推导，题面永远和数据一致
2. 渲染六节课页面（单文件，无外部依赖）：概念讲解 + 真实数据卡 + 闯关题
3. 渲染结业证：六轴雷达图（纯 SVG 手绘，不引图表库）+ 关键指标 + 知识点

可选渲染 PNG（需要 Node + Playwright）：

```bash
node scripts/render_png.js out/certificate.html out/certificate.png 1080 1350
```

## 课程设计

六节课，一课一个营养素，每课都由"概念 + 真实数据 + 一道题"构成：

| 课 | 主题 | 教学落点 |
|---|---|---|
| 1 | 能量 | 一天的"电费"账单，一餐占全天多少 |
| 2 | 蛋白质 | 身体的建材，看占总能量比例 |
| 3 | 脂肪 | 能量储备与口感，脂肪供能占比 |
| 4 | 碳水 | 最直接的燃料，甜饮里的隐形糖 |
| 5 | 钠 | 藏在酱料和腌渍里的那一项 |
| 6 | 钙 | 骨头和牙齿的原料，常见餐品里最缺位 |

答对一题解锁下一课，全部通关后生成结业证。

## 输出口径（重要）

- 所有百分比一律以**全天参考摄入量**为分母，不以"一餐"为分母，避免"192% 这类数字被误读为超标两倍。
- 参考量采用《中国居民膳食营养素参考摄入量》成人 18-49 岁轻体力活动水平。
- **只陈述数据与营养学常识，不做价值判断。** 禁止出现"垃圾食品""不健康""罪恶""发胖""必须戒"等表述；能量等数字标注为估算参考值。
- 明确声明：仅供营养科普参考，**不构成医疗、营养或其他专业建议**；餐品信息、价格与供应状态以麦当劳官方渠道实时结果为准。
- 不对用户下单、不创建订单、不兑换积分、不抽奖（写操作一律不调用）。

## 资源

- `scripts/mcp_client.py` — MCP Streamable HTTP 客户端，零第三方依赖
- `scripts/collect.py` — 采集与归一化
- `scripts/nutrition_kb.py` — 营养知识库、参考量、雷达计算、知识点推导
- `scripts/build_course.py` — 课程与结业证渲染
- `scripts/render_png.js` — Playwright 截图（可选）
- `data/nutrition_demo.json` — 离线演示数据（麦当劳中国官方营养成分表）
- `references/mcp_tools.md` — MCP tool 清单与实测返回结构
- `references/compliance.md` — 合规红线与措辞规范
