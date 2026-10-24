# 发布到 GitHub（需你手动执行，本机没有 gh CLI）

截止：**2026-10-25 23:59（北京时间）**，现在 10-24 下午，时间够但别拖。
排行榜 10-26 00:00 定榜。

---

## Step 1 · 申请麦当劳 MCP Token（5 分钟）

1. 打开 https://open.mcd.cn/mcp
2. 手机号登录 → 右上角「控制台」→ 「激活」→ 复制 Token
3. 存到环境变量（**不要**写进任何要提交的文件）：

```bash
export MCD_MCP_TOKEN=你的Token
```

拿到后先验证一下能不能取到真实数据：

```bash
cd mcd-nutrition-academy
python3 scripts/collect.py          # 应输出 source=live
```

若显示 `source=demo` 说明 Token 没生效，检查变量是否设置。

---

## Step 2 · 建仓库并推送（5 分钟）

在 GitHub 新建一个**公开**仓库，名字建议 `mcd-nutrition-academy`，**不要**勾选 README/.gitignore/LICENSE（避免冲突），然后：

```bash
cd mcd-nutrition-academy
git remote add origin https://github.com/你的用户名/mcd-nutrition-academy.git
git push -u origin main
```

推送前最后确认一次（这三条是硬性要求）：

```bash
ls README.md CONTEST_DECLARATION.md MCP_INTEGRATION.md mcp-config.example.json workbuddy.md
```

五个文件都在，缺一个会被判定不合规。

---

## Step 3 · 提交参赛申请（2 分钟）

到活动仓库提交 Issue：https://github.com/M-China/mcd-developer-innovation-challenge/issues

正文格式（照抄官方模板）：

```text
【参赛申请】
项目名称：麦麦营养学徒 · MCD Nutrition Academy
项目地址：https://github.com/你的用户名/mcd-nutrition-academy
项目简介：用麦当劳 MCP 的真实六维营养数据当教材，做成六节可闯关的营养科普课，答对解锁下一课，通关生成六轴雷达图结业证。题目与答案全部从实时营养表自动推导。
```

**别漏这一步**——不提交 Issue 就没有参赛资格，Star 再多也白搭。

---

## Step 4 · 拿去涨星（今天 + 明天）

完整文案和节奏表见 [PROMO.md](PROMO.md)。最短路径：

1. **README 首屏加个 15-30 秒演示 GIF**（转化影响最大，录法见 PROMO.md）
2. 掘金 / 知乎 各发一篇（技术社区，长尾）
3. 朋友圈 / 小红书各发一次（社交扩散，配 `assets/certificate.png`）
4. 明天白天再发一轮 V2EX / 微博

参考话术：

> 把麦当劳的营养成分表做成了六道闯关题，题目自动从真实数据生成。
> 六道题你能全答对吗？GitHub 搜 mcd-nutrition-academy

---

## 提交 Issue 时的自查清单

- [ ] 仓库是**公开**的
- [ ] 五个必交文件都在，文件名一字未改
- [ ] `CONTEST_DECLARATION.md` 与官方原文一致（已校验 sha256）
- [ ] `mcp-config.example.json` 里只有 `${MCD_MCP_TOKEN}` 占位符，无真实 Token
- [ ] 项目**真实使用**了麦当劳 MCP（`MCP_INTEGRATION.md` 有完整调用流程）
- [ ] `workbuddy.md` 已提交（拿 3000 积分的门票，漏了等于白做）
- [ ] README 首屏有图、有三步跑起来的说明
- [ ] 文案没有"垃圾食品""发胖"等评价性表述（见 `references/compliance.md`）
- [ ] 不刷 Star（规则明确禁止，一经发现直接取消资格）
