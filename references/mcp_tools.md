# MCP Tool 清单与实测记录

数据来源：https://github.com/M-China/mcd-mcp-server （麦当劳 MCP Server 官方使用指南）
实测时间：2026-10-24

## 本项目使用的 Tool

| Tool | 类型 | 用途 | 失败是否致命 |
|---|---|---|---|
| `list-nutrition-foods` | 只读 | 全量餐品六维营养成分表 | 否（降级到演示数据） |
| `order-list` | 只读 | 历史订单（到店/外送） | 否 |
| `query-my-account` | 只读 | 会员积分 | 否 |

## 明确不调用的 Tool（写操作）

`create-order`、`cancel-order`、`mall-create-order`、`auto-bind-coupons`、
`party-order-create`、`delivery-create-address`、`draw-lottery` —— 会真实产生
副作用（下单、扣积分、领券、抽奖），本项目一律不调用。

## 实测返回结构

### list-nutrition-foods

`data` 是**文本表格**（不是 JSON），表头：

```
productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium
```

解析策略（`scripts/nutrition_kb.py::parse_nutrition_csv`）：

- 逐行按 CSV 切分，跳过表头行与说明行
- 对第 2 列之后的每个 cell 做"是否为纯数字"判定，收集为数值列
- 前 6 个数值依次为 energy_kj / energy_kcal / protein / fat / carb / sodium，第 7 个为 calcium
- 这样可以容忍额外的描述列或末尾多出的单位列，容错性比按列号硬取强

注意：`energy_kcal` 若缺失，用 `energy_kj / 4.184` 补算。

### order-list

入参为空对象。返回路径 `data.list[]`：

```
data.list[].orderId          订单编码
data.list[].orderType        订单类型
data.list[].createTime       下单时间
data.list[].storeName        门店名称
data.list[].storeCode / beCode / beType
data.list[].orderStatus      订单状态
data.list[].realTotalAmount  实付总金额
data.list[].orderProductList[]  商品
    .productCode / .productName / .quantity / .comboItemList
```

### query-my-account

返回路径 `data`，字段（均为字符串型数字）：

```
availablePoint  accumulativePoint  usedPoint  frozenPoint
expiredPoint  currentMouthExpirePoint  nextMouthExpirePoint  lastMouthExpirePoint
```

## 候选键匹配

字段名以服务端为准。`scripts/collect.py` 采用候选键 + 递归遍历提取，不硬绑定：

| 语义 | 候选键 |
|---|---|
| 时间 | `orderTime` `createTime` `createdAt` `payTime` `gmtCreate` `time` `date` `orderDate` `createAt` |
| 名称 | `mealName` `productName` `itemName` `goodsName` `name` `title` |
| 金额 | `price` `amount` `payAmount` `totalAmount` `realAmount` `sellPrice` |
| 数量 | `quantity` `qty` `num` `count` |
| 门店 | `storeName` `shopName` `store` `shop` `restaurantName` |
| 渠道 | `channel` `orderType` `scene` `deliveryType` `dineType` |

若真实返回出现新键名，读 `data/raw/*.json` 后把新键名补进对应列表即可。

## 可扩展（当前未用）

- `query-meal-detail`：拆解套餐组成，把替换选项纳入六维对比
- `campaign-calendar`：把营销活动日历叠加成"节日点餐营养课"时间线
- `mall-order-list`：近一年商城订单，做长期饮食结构趋势
- `query-nearby-stores` / `delivery-query-stores`：门店维度
