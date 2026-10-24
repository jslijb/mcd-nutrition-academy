# MCP_INTEGRATION

本项目实际使用的麦当劳 MCP Server、Tool、调用流程与业务价值。

## Server

| 项 | 值 |
|---|---|
| Server | 麦当劳中国 MCP Server（McDonald's China） |
| Endpoint | `https://mcp.mcd.cn` |
| Transport | Streamable HTTP（`type: streamablehttp`） |
| 协议版本 | `2025-06-18` |
| 鉴权 | `Authorization: Bearer <MCD_MCP_TOKEN>` |
| 限流 | 每个 Token 600 次/分钟，超出返回 HTTP 429 |
| 配置文件 | `mcp-config.example.json`（仅环境变量占位符，不含真实凭证） |

Token 在 https://open.mcd.cn 用手机号登录后于控制台申请「激活」获取。

## 实际调用的 Tool

本项目**只调用只读 Tool**，不产生任何订单、积分消耗或抽奖行为。

| Tool | 类型 | 在本项目中的用途 |
|---|---|---|
| `list-nutrition-foods` | 只读 | **核心数据源**。返回麦当劳常见餐品的营养成分表，含能量（kJ/kcal）、蛋白质、脂肪、碳水化合物、钠、钙六个维度。课程的全部题目、结业证的雷达图与数字都由它推导。 |
| `order-list` | 只读 | 查询用户到店/外送历史订单，用于把课程与用户"常点的餐"关联起来（可选，失败自动降级）。 |
| `query-my-account` | 只读 | 查询会员积分（可选，用于结业证展示，失败自动降级）。 |

### 未调用（写操作，明确回避）

`create-order`、`cancel-order`、`mall-create-order`、`auto-bind-coupons`、
`party-order-create`、`delivery-create-address`、`draw-lottery`、
`mall-create-order` 属于会真实产生副作用的 Tool，本项目**一律不调用**。

## 调用流程

```
用户请求（"来一节麦麦营养课"）
        │
        ▼
scripts/collect.py
        │
        ├─ McpClient.initialize()          # MCP 握手
        ├─ call_tool("list-nutrition-foods")
        │     └─ data 为文本表格，表头：
        │        productName,nutritionDescription,energyKj,energyKcal,
        │        protein,fat,carbohydrate,sodium,calcium
        ├─ call_tool("order-list")          # 可选，失败则跳过
        └─ call_tool("query-my-account")    # 可选，失败则跳过
        │
        ▼
data/nutrition.json  {source: "live"|"demo", foods:[...], orders:[...], points:{...}}
        │
        ▼
scripts/build_course.py
        │
        ├─ nutrition_kb.parse_nutrition_csv()   # 表格 → 结构化记录
        ├─ nutrition_kb.food_profile()           # 每项对全天参考量的占比
        ├─ nutrition_kb.radar_points()           # 六轴雷达顶点
        ├─ nutrition_kb.teach_points()           # 知识点推导
        ├─ build_quiz()                          # 从真实数据自动出题
        ├─ build_lesson_page()                   # -> out/lesson.html
        └─ build_certificate()                   # -> out/certificate.html (+ .png)
```

## 实测返回结构（2026-10-24 于 https://mcp.mcd.cn 验证）

`list-nutrition-foods` 的 `data` 是**文本表格**，非 JSON：

```
productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium
```

解析时按"数值列"匹配，容忍额外的描述列或末尾单位列；表头行与说明行自动跳过。

`order-list` 返回路径为 `data.list[]`：

```
data.list[].orderId / orderType / createTime / storeName / storeCode
data.list[].orderStatus / realTotalAmount
data.list[].orderProductList[]  -> .productCode / .productName / .quantity / .comboItemList
```

`query-my-account` 返回路径为 `data`：

```
availablePoint  accumulativePoint  usedPoint  frozenPoint
expiredPoint  currentMouthExpirePoint  nextMouthExpirePoint  lastMouthExpirePoint
```

（均为字符串类型的数字，代码中已做类型转换。）

字段名以服务端为准。`scripts/collect.py` 采用**候选键匹配 + 递归遍历**提取，不硬绑定单一字段名；若真实返回出现新键名，读 `data/raw/*.json` 后补进对应候选列表即可。

## 业务价值

### 对用户

把一份看不懂的营养成分表，变成**六节能读完的课**。

麦当劳官方营养计算器给出的是六列数字，绝大多数用户看不懂「钠 961 mg」意味着什么。本项目把这六列数据重新组织成"一课一知识点 + 一道从数据里自动生成的题"，让用户通过闯关真正理解每个营养素的含义和量级——而且**题目和答案直接来自 MCP 实时数据**，数据更新，题目自动跟着变，永远不会出现"讲义和数据对不上"的情况。

结业证把这一餐的六维结构画成雷达图并给出关键指标与知识点，让"我学到了什么"变成一张可以分享的图。

### 对麦当劳

- **把官方营养计算器从"查数字"变成"能学"**。数据源没有变，还是 `list-nutrition-foods`，但呈现形态从表格变成课程，触达的是本来不会去查营养成分表的人群。
- **正向的品牌表达**。项目不评价产品好坏、不做道德说教，只解释营养学常识（"钠藏在酱料里"是知识，不是指责），符合"选择麦当劳美食，计算一餐营养信息，更好地搭配你一天的膳食"的官方表述。
- **不产生任何交易副作用**。全程只读，不点单、不消耗积分、不抽奖。

### 可扩展方向

- `campaign-calendar`：把当月营销活动日历作为"营养搭配 + 活动"的时间线，扩展成"节日点餐营养课"。
- `query-meal-detail`：拆解套餐组成，把套餐内的替换选项纳入对比，给出"同样价格下换个单品，六维怎么变"。
- `mall-order-list`：近一年商城订单，用于长期饮食结构趋势。
