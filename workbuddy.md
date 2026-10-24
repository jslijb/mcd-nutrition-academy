# workbuddy.md

> 本文件记录本项目在腾讯 WorkBuddy 智能体中的真实开发对话上下文，用于证明项目确实由 WorkBuddy 参与开发。

---

## 一、开发背景与目标

用户在 2026-10-24 提出需求：参加 WorkBuddy × 麦当劳「1024 造物挑战」程序员创意开发大赛，做一个**教育方向**的工具。

初始设想是"年度营养账单"式的分享卡片。在调研当前赛道（活动仓库 RANKING.md，104 个在榜项目）后发现，年度总结、人格测试、卡路里计算三类均已有高分作品，其中 `mcd-wrapped`（年度总结）516 星、`mcd-receipt-persona`（小票人格）97 星、`mcd-calorie-butler`（卡路里管家）149 星——**继续做"年度营养账单"会与在榜项目高度同质**。

于是把方向调整为：**保留教育内核与可分享卡片，但把产品形态从"一张账单"变成"六节可闯关的课"**。理由是——

1. 教育赛道在榜项目仅 `mcd-chinese-class`（64 星）一家，无人深耕；
2. 六维营养数据（能量/蛋白质/脂肪/碳水/钠/钙）榜单上无人用雷达图呈现；
3. "课"这个形态自带闯关感和完成感，比"报告"更适合做社交分享。

## 二、调研过程

### 活动规则核实

- 活动页 https://www.workbuddy.link/p/8QYARuAmZ9RgQty3FSzNUs 为 JS 渲染 SPA，抓不到正文
- 改从官方 GitHub 仓库取一手规则：
  - `M-China/mcd-developer-innovation-challenge`（活动规则与排行榜）
  - `M-China/mcd-mcp-server`（MCP Server 使用指南）
- 用 GitHub API base64 解码取得 `CONTEST_DECLARATION.md` 官方原文，校验 sha256 与官方一致后原样入库
- 确认关键约束：报名与排名截止 **2026-10-25 23:59**，排行榜数据截止 10-26 00:00；必交 5 个文件且文件名不可改动；排名按 GitHub 公开 Star；前 100 名进榜

### MCP 能力核实

从 `mcd-mcp-server` README 解析出全部 39 个 Tool 的真实名称与描述，确认本项目要用的是：

- `list-nutrition-foods` —— 餐品营养信息列表，含能量/蛋白质/脂肪/碳水化合物/钠/钙
- `order-list` —— 查询历史订单
- `query-my-account` —— 我的积分

同时从头部项目 `lvzuojing/mcd-wrapped` 的 `references/mcp_tools.md` 获取了 `list-nutrition-foods` 的**真实返回结构**（文本表格，表头 `productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium`），据此设计容错解析，而不是猜字段名。

### 营养数据核实

用 WebFetch 访问麦当劳中国官网产品页（`mcdonalds.com.cn/product/...`），取得巨无霸、麦辣鸡腿汉堡、麦香鱼、薯条、可口可乐的官方六维营养数值，用作无 Token 演示模式的离线数据。官网明确标注该数据更新时间为 2025 年 4 月，六项即能量、蛋白质、脂肪、碳水化合物、钠、钙。

## 三、开发过程中的关键决策

### 决策 1：MCP 客户端自己写，不引第三方 SDK

`scripts/mcp_client.py` 用标准库 `urllib` 手写 Streamable HTTP 传输。理由：项目要求"零依赖即可运行"，评审 clone 下来不需要 pip install。

### 决策 2：题目从真实数据自动生成，而不是预写文案

`build_quiz()` 从营养表里排序取最高项作答案、按区间取干扰项。这样数据一旦更新，题目自动跟着变，不会出现"讲义和数据对不上"。

### 决策 3：百分比口径修正（教育准确性问题）

初版用"一餐参考量"（全天 ÷ 3）作分母，巨无霸钠算出 192%。这个数字会被读成"超标近两倍"，既夸张又误导。改为统一用**全天参考摄入量**作分母：巨无霸钠 = 64%，麦辣鸡腿堡 = 80%，既准确又符合营养标签常识。

代码里两个口径都保留：`pct_of_day` 对外展示，`pct_of_meal` 仅供内部判断某项是否值得讲。

### 决策 4：教学点必须"有信号"才讲

初版逻辑取每个维度的最大值，导致薯条钠 12% 也被标成"要留意"、可乐钠 0% 也被标"要留意"。加入阈值后，低于 40%（按一餐口径折算）的维度不再生成教学点，改为"六项都在参考范围内"的中性表述。

### 决策 5：只调用只读 Tool

`create-order`、`cancel-order`、`mall-create-order`、`auto-bind-coupons`、`draw-lottery` 等写操作一律不调用。这既是活动规则要求（真实使用但不得刷数据），也让项目在合规上无可指摘。

### 决策 6：HTML 模板用 replace 而非 % 格式化

HTML/CSS 里大量 `%` 符号（`width:40%`）与 Python `%` 格式化冲突，初版直接抛 `ValueError: unsupported format character`。改为占位符 + `.replace()`，模板里可以自由写百分号。

## 四、实际运行记录

### 演示模式（无 Token）

```bash
python3 scripts/collect.py --demo
# wrote data/nutrition.json (source=demo, foods=12)

python3 scripts/build_course.py
# wrote out/certificate.png
# wrote out/lesson.html and out/certificate.html
```

渲染结果经人工核对：结业证六轴雷达图、六条维度条、四项 KPI、课程徽章、知识点提示、底部免责声明均正确呈现；课程页六节课的锁课状态与题目选项正常。

### MCP 端点连通性验证

```bash
curl -X POST https://mcp.mcd.cn -H "Authorization: Bearer <无效token>" ...
# 返回：当前鉴权码不存在或已失效!
```

说明服务端正常响应，只差有效 Token；无 Token 时 `collect.py` 自动降级到演示数据并打印告警，流水线不中断。

## 五、产出

| 文件 | 作用 |
|---|---|
| `SKILL.md` | WorkBuddy Skill 定义 |
| `scripts/mcp_client.py` | MCP 客户端（标准库实现） |
| `scripts/collect.py` | 采集 + 归一化 + 降级 |
| `scripts/nutrition_kb.py` | 营养知识库、参考量、雷达计算、知识点推导 |
| `scripts/build_course.py` | 课程页与结业证渲染 |
| `scripts/render_png.js` | Playwright 截图（可选） |
| `data/nutrition_demo.json` | 官方离线数据（12 项） |
| `references/mcp_tools.md` | Tool 清单与实测返回结构 |
| `references/compliance.md` | 合规红线与措辞规范 |
| `CONTEST_DECLARATION.md` | 官方声明原文（sha256 校验一致） |

## 六、开发者声明

本项目全部代码、文档与设计由参赛者使用腾讯 WorkBuddy 智能体独立开发完成。项目中未包含任何真实 Token、密钥、账号凭证或他人个人信息；`mcp-config.example.json` 仅使用环境变量占位符 `${MCD_MCP_TOKEN}`。
