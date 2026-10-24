#!/usr/bin/env python3
"""Build the nutrition lesson + shareable certificate.

Design intent (why this is not another "calorie counter"):
  The differentiator is the LESSON. Each lesson teaches one nutrition concept
  using McDonald's real six-dimension data as the teaching material, and ends
  with a short quiz the user must pass to unlock the next lesson. The
  certificate is the social artefact: a six-axis radar of the user's own
  chosen meal set plus the lessons they unlocked.

Outputs:
  out/lesson.html      -> the interactive course page (single file, no deps)
  out/certificate.html -> the shareable card (single file, no deps)
  out/certificate.png  -> rendered card via Playwright (optional)
"""

import html
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import nutrition_kb as kb  # noqa: E402

DATA = os.path.join(ROOT, "data", "nutrition.json")
OUT = os.path.join(ROOT, "out")

# ------------------------------------------------------------------ curriculum
# Six lessons, one per dimension. Each lesson has a plain-language intro, a
# "look at the data" example, and a quiz whose answer is derived from the real
# nutrition table -- never hardcoded, so the data stays truthful.
CURRICULUM = [
    {
        "id": "energy",
        "dimension": "energy_kcal",
        "title": "第一课 · 能量：一份套餐能装下多少电费",
        "concept": "能量不是好坏，是花多少的问题。同一份食物，份量不同，能量能差出一整顿正餐。"
        "把千卡放在'一天 2250 千卡'这个分母上看，才有意义。",
        "teach": "本课用真实菜单里的两组对照做实验：只改份量，其他不变，看能量怎么变。",
    },
    {
        "id": "protein",
        "dimension": "protein_g",
        "title": "第二课 · 蛋白质：身体的建材",
        "concept": "蛋白质是长身体、修身体的原材料。多一层肉饼，多的不只是口感，"
        "更是实实在在的蛋白质——这一点在真实数据里非常明显。",
        "teach": "看蛋白质别只看绝对克数，同时看它占总能量的比例：占比高的那份更抗饿。",
    },
    {
        "id": "fat",
        "dimension": "fat_g",
        "title": "第三课 · 脂肪：能量密度与口感",
        "concept": "脂肪的能量密度是蛋白和碳水的一倍多。同样体积，脂肪多的那份热量更高。"
        "但脂肪也决定口感，所以'减脂'从来不等于'零脂肪'。",
        "teach": "算脂肪占比：脂肪克数 × 9 千焦，除以总能量，看它在能量结构里占几成。",
    },
    {
        "id": "carb",
        "dimension": "carb_g",
        "title": "第四课 · 碳水：最直接的燃料",
        "concept": "碳水是身体最省事的燃料。甜饮的碳水几乎全是糖，"
        "而且喝的时候完全尝不出——这是最'隐形'的一类碳水。",
        "teach": "把碳水和你一天需要的 275 克放在一起看，比单看'克'直观得多。",
    },
    {
        "id": "sodium",
        "dimension": "sodium_mg",
        "title": "第五课 · 钠：藏在酱料里的那一项",
        "concept": "钠是麦当劳餐品里最容易超标的营养素。它主要来自酱汁、腌渍和面包，"
        "吃的时候常常完全尝不出来。多一层肉，酱也更多，钠也跟着涨。",
        "teach": "钠是'限'的维度：一餐超过全天参考量的三分之一就该留意了。",
    },
    {
        "id": "calcium",
        "dimension": "calcium_mg",
        "title": "第六课 · 钙：骨头和牙齿的原料",
        "concept": "钙是少数'越多越好'的营养素，在常见餐品里却常常缺位。"
        "有意思的是：奶类饮品、甜筒的钙含量，反而比多数汉堡高得多。",
        "teach": "钙是'需'的维度：看一餐能贡献多少，而不是看它有没有超标。",
    },
]


def load_foods():
    if not os.path.exists(DATA):
        return kb.load_demo_foods()
    with open(DATA, "r", encoding="utf-8") as f:
        return json.load(f)["foods"]


def build_quiz(foods, dim_key, avoid_keys=None):
    """Build a data-derived quiz for one dimension.

    Two question shapes, both derived from the live table:

    1. "same product, different size" -- the most convincing form, because it
       isolates one variable. Uses two real items from the menu.
    2. "which one has the most X" -- the fallback when no comparable pair
       exists for that dimension.

    `avoid_keys` holds product groups already used by earlier lessons, so
    consecutive lessons do not all show the same comparison.

    Correct answer and options always come from real rows, so the quiz can
    never drift away from the data it teaches.
    """
    avoid_keys = avoid_keys or set()

    # --- shape 1: a real A/B comparison ---------------------------------
    pairs = kb.find_comparisons(foods, dim_key, min_gap_pct=6.0)
    if pairs:
        p = next((x for x in pairs if x["key"] not in avoid_keys), pairs[0])
        low, high = p["low"], p["high"]
        dim = kb.REFERENCE_INTAKE[dim_key]
        question = "%s 和 %s 只差一个变量，%s差多少？" % (
            low["name"],
            high["name"],
            dim.get("short", dim["label"]),
        )
        options = [
            "%s（%s）" % (high["name"], _fmt(p["high_value"], dim["unit"])),
            "%s（%s）" % (low["name"], _fmt(p["low_value"], dim["unit"])),
            "两者相同",
            "无法判断",
        ]
        return {
            "question": question,
            "options": options,
            "answer": options[0],
            "explain": "%s 的%s比 %s 多 %s，占成年人一天参考量的 %.1f%%。"
            "同一个名字，份量不同，%s 就差这么多。"
            % (
                high["name"],
                dim["label"],
                low["name"],
                _fmt(p["diff"], dim["unit"]),
                p["gap_pct_of_day"],
                dim["label"],
            ),
            "compare": {
                "low_name": low["name"],
                "low_value": _fmt(p["low_value"], dim["unit"]),
                "high_name": high["name"],
                "high_value": _fmt(p["high_value"], dim["unit"]),
                "diff": _fmt(p["diff"], dim["unit"]),
                "label": dim.get("short", dim["label"]),
                "gap_pct": round(p["gap_pct_of_day"], 1),
                "group_key": p["key"],
            },
        }

    # --- shape 2: pick the extreme --------------------------------------
    pool = [f for f in foods if (f.get(dim_key) or 0) > 0]
    if len(pool) < 4:
        return None
    ranked = sorted(pool, key=lambda f: f[dim_key], reverse=True)
    top = ranked[0]
    step = max(1, len(ranked) // 4)
    distractors = [ranked[i] for i in range(step, len(ranked), step)][:3]
    if len(distractors) < 3:
        return None
    options = [top] + distractors
    return {
        "question": "下面哪一份的%s含量最高？" % kb.REFERENCE_INTAKE[dim_key]["label"],
        "options": [f["name"] for f in options],
        "answer": top["name"],
        "explain": "%s 的%s是 %s，成人一天参考量是 %s，所以这一份就占了全天的 %.0f%%。"
        % (
            top["name"],
            kb.REFERENCE_INTAKE[dim_key]["label"],
            _fmt(top[dim_key], kb.REFERENCE_INTAKE[dim_key]["unit"]),
            _fmt(
                kb.REFERENCE_INTAKE[dim_key]["value"],
                kb.REFERENCE_INTAKE[dim_key]["unit"],
            ),
            top[dim_key] / kb.REFERENCE_INTAKE[dim_key]["value"] * 100,
        ),
    }


def _fmt(v, unit):
    v = float(v)
    if unit == "mg":
        return "%.0f mg" % v
    if unit == "kcal":
        return "%.0f kcal" % v
    return "%.1f g" % v


# ------------------------------------------------------------------ rendering
def radar_svg(points, size=360):
    """Six-axis radar chart, pure SVG (no chart library)."""
    cx = cy = size / 2.0
    radius = size / 2.0 - 46
    axes = kb.DIMENSIONS
    n = len(axes)

    def xy(idx, pct):
        import math

        ang = -math.pi / 2 + 2 * math.pi * idx / n
        r = radius * min(pct, 100.0) / 100.0
        return cx + r * math.cos(ang), cy + r * math.sin(ang)

    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" class="radar">' % (size, size, size, size)]
    # grid rings
    for ring in (25, 50, 75, 100):
        pts = " ".join("%.1f,%.1f" % xy(i, ring) for i in range(n))
        parts.append(
            '<polygon points="%s" fill="none" stroke="rgba(255,255,255,.16)" stroke-width="1"/>' % pts
        )
    # spokes + labels
    for i, dim in enumerate(axes):
        x, y = xy(i, 100)
        parts.append(
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="rgba(255,255,255,.22)" stroke-width="1"/>'
            % (cx, cy, x, y)
        )
        lx, ly = xy(i, 124)
        parts.append(
            '<text x="%.1f" y="%.1f" fill="rgba(255,255,255,.72)" font-size="13" '
            'text-anchor="middle" dominant-baseline="middle">%s</text>'
            % (lx, ly, html.escape(dim["label"]))
        )
    # data polygon
    pts = " ".join("%.1f,%.1f" % xy(i, points.get(d["key"], 0)) for i, d in enumerate(axes))
    parts.append('<polygon points="%s" fill="rgba(255,182,77,.28)" stroke="#FFB64D" stroke-width="2.5"/>' % pts)
    # dots
    for i, d in enumerate(axes):
        x, y = xy(i, points.get(d["key"], 0))
        parts.append('<circle cx="%.1f" cy="%.1f" r="4" fill="#FFB64D"/>' % (x, y))
    parts.append("</svg>")
    return "".join(parts)


def build_certificate(foods, chosen, points, lessons_done, source):
    """The shareable card. Social artefact first, numbers second."""
    total_kcal = sum(f.get("energy_kcal", 0) for f in chosen)
    total_sodium = sum(f.get("sodium_mg", 0) for f in chosen)
    total_protein = sum(f.get("protein_g", 0) for f in chosen)
    titles = [f["name"] for f in chosen]

    radar = radar_svg(points)

    rows = []
    for dim in kb.DIMENSIONS:
        prof_pct = points.get(dim["key"], 0)
        bar = min(prof_pct, 150.0) / 150.0 * 100
        color = "#FFB64D" if prof_pct < 100 else "#FF8A5B"
        rows.append(
            '<div class="bar-row"><span class="bar-label">%s</span>'
            '<span class="bar-track"><span class="bar-fill" style="width:%.1f%%;background:%s"></span></span>'
            '<span class="bar-val">%.0f%%</span></div>'
            % (html.escape(dim["label"]), bar, color, prof_pct)
        )

    lesson_badges = "".join(
        '<span class="badge %s">%s</span>'
        % (
            "" if c["id"] in lessons_done else "locked",
            html.escape(c["title"].split("·")[0].strip()),
        )
        for c in CURRICULUM
    )

    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>麦麦营养学徒 · 结业证</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1590px;font-family:"Microsoft YaHei","PingFang SC",-apple-system,sans-serif;
 background:linear-gradient(160deg,#12100E 0%,#1E1814 45%,#2A1F16 100%);color:#fff;overflow:hidden;position:relative}
.card{position:relative;z-index:2;padding:60px 60px 52px;height:100%;display:flex;flex-direction:column;gap:0}
.ribbon{position:absolute;top:0;left:0;right:0;height:8px;background:linear-gradient(90deg,#FFB64D,#FF7A29,#E4392B)}
.kicker{font-size:21px;letter-spacing:6px;color:#FFB64D;margin-top:16px;font-weight:700}
h1{font-size:60px;line-height:1.12;margin-top:14px;font-weight:800;letter-spacing:1px}
.sub{font-size:24px;color:rgba(255,255,255,.62);margin-top:14px;line-height:1.6}
.grid{display:flex;gap:26px;margin-top:30px;align-items:center}
.radarbox{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.11);border-radius:24px;padding:14px;flex:0 0 auto}
.stats{flex:1;display:flex;flex-direction:column;gap:17px;max-width:560px}
.bar-row{display:flex;align-items:center;gap:13px}
.bar-label{width:60px;font-size:19px;color:rgba(255,255,255,.75);flex:0 0 auto}
.bar-track{flex:1;height:12px;background:rgba(255,255,255,.09);border-radius:6px;overflow:hidden}
.bar-fill{display:block;height:100%;border-radius:6px}
.bar-val{width:56px;text-align:right;font-size:18px;color:rgba(255,255,255,.7);font-variant-numeric:tabular-nums}
.kpis{display:flex;gap:16px;margin-top:30px}
.kpi{flex:1;background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.1);border-radius:18px;padding:20px 20px}
.kpi .n{font-size:36px;font-weight:800;color:#FFB64D;font-variant-numeric:tabular-nums;line-height:1.1}
.kpi .n small{font-size:17px;font-weight:600;margin-left:3px;color:rgba(255,255,255,.55)}
.kpi .l{font-size:16px;color:rgba(255,255,255,.55);margin-top:7px}
.lesson-title{margin-top:32px;font-size:20px;color:rgba(255,255,255,.5);letter-spacing:3px;font-weight:700}
.badges{display:flex;flex-wrap:wrap;gap:11px;margin-top:15px}
.badge{font-size:17px;padding:8px 17px;border-radius:999px;background:rgba(255,182,77,.14);
 border:1px solid rgba(255,182,77,.42);color:#FFCE8A}
.badge.locked{background:rgba(255,255,255,.04);border-color:rgba(255,255,255,.12);color:rgba(255,255,255,.32)}
.meals{margin-top:30px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);border-radius:18px;padding:20px 24px}
.meals .h{font-size:16px;color:rgba(255,255,255,.45);letter-spacing:2px;margin-bottom:10px}
.meals .t{font-size:23px;line-height:1.5;color:rgba(255,255,255,.88)}
.tip{margin-top:22px;font-size:18px;line-height:1.65;color:rgba(242,237,231,.72);
 background:rgba(255,182,77,.09);border-left:3px solid #FFB64D;padding:15px 19px;border-radius:0 12px 12px 0}
.recap{margin-top:22px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);
 border-radius:18px;padding:18px 22px}
.recap .rh{font-size:16px;color:rgba(255,255,255,.45);letter-spacing:2px;margin-bottom:12px;font-weight:700}
.ri{font-size:17px;color:rgba(242,237,231,.8);line-height:1.9;display:flex;gap:12px;align-items:baseline}
.rn{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:14px;color:#FFB64D;
 min-width:22px;flex:0 0 auto}
.foot{margin-top:auto;padding-top:22px;display:flex;justify-content:space-between;align-items:flex-end;
 border-top:1px solid rgba(255,255,255,.1);font-size:15px;color:rgba(255,255,255,.42);gap:30px;line-height:1.7}
.foot .id{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:14px;letter-spacing:1px;white-space:nowrap}
.glow{position:absolute;width:620px;height:620px;border-radius:50%;background:radial-gradient(circle,rgba(255,138,43,.2),transparent 70%);
 top:-220px;right:-190px;z-index:1}
</style></head><body>
<div class="glow"></div><div class="ribbon"></div>
<div class="card">
  <div class="kicker">MCD NUTRITION ACADEMY</div>
  <h1>麦麦营养学徒</h1>
  <div class="sub">用麦当劳真实菜单的六维营养数据当教材<br>这不是体检报告，是一节看得懂的营养课</div>
  <div class="grid">
    <div class="radarbox">__RADAR__</div>
    <div class="stats">__BARS__</div>
  </div>
  <div class="kpis">
    <div class="kpi"><div class="n">__KCAL__<small>kcal</small></div><div class="l">这一餐总能量</div></div>
    <div class="kpi"><div class="n">__SODIUM__<small>mg</small></div><div class="l">这一餐总钠</div></div>
    <div class="kpi"><div class="n">__PROTEIN__<small>g</small></div><div class="l">这一餐总蛋白质</div></div>
    <div class="kpi"><div class="n">__LESSONS__<small>课</small></div><div class="l">已解锁课程</div></div>
  </div>
  <div class="lesson-title">已解锁的课</div>
  <div class="badges">__BADGES__</div>
  <div class="meals"><div class="h">这一餐吃了什么</div><div class="t">__MEALS__</div></div>
  <div class="tip">__TIP__</div>
  <div class="recap">
    <div class="rh">这一趟你学到的六件事</div>
    <div class="ri"><span class="rn">01</span>能量是花多少的问题，份量一变就差一大截</div>
    <div class="ri"><span class="rn">02</span>多一层肉，蛋白质和钠一起涨，不只是口感</div>
    <div class="ri"><span class="rn">03</span>脂肪的能量密度是糖的两倍多，但它决定口感</div>
    <div class="ri"><span class="rn">04</span>甜饮的碳水几乎全是糖，而且完全尝不出来</div>
    <div class="ri"><span class="rn">05</span>钠藏在酱汁和面包里，是最容易超的那一项</div>
    <div class="ri"><span class="rn">06</span>奶类饮品的钙比多数汉堡高得多，别忽略它</div>
  </div>
  <div class="foot">
    <div>数据来源：__SOURCE__<br>营养素参考量采用中国居民膳食营养素参考摄入量，仅供科普参考，不构成医疗或营养建议</div>
    <div class="id">__CERTID__</div>
  </div>
</div></body></html>"""
    for key, val in (
        ("__RADAR__", radar),
        ("__BARS__", "".join(rows)),
        ("__KCAL__", str(round(total_kcal))),
        ("__SODIUM__", str(round(total_sodium))),
        ("__PROTEIN__", str(round(total_protein))),
        ("__LESSONS__", str(len(lessons_done))),
        ("__BADGES__", lesson_badges or '<span class="badge">尚未开始</span>'),
        ("__MEALS__", html.escape(" + ".join(titles))),
        ("__TIP__", _card_tip(chosen, points)),
        (
            "__SOURCE__",
            "麦当劳 MCP list-nutrition-foods 实时数据"
            if source == "live"
            else "麦当劳中国官方营养成分表（演示数据）",
        ),
        ("__CERTID__", _cert_id(foods)),
    ):
        doc = doc.replace(key, val)
    return doc


def _card_tip(chosen, points):
    """One concrete takeaway line, derived from the data rather than hardcoded."""
    if not chosen:
        return ""
    notes = []
    for f in chosen:
        for n in kb.teach_points(f):
            if n["kind"] == "watch":
                notes.append((f["name"], n["text"]))
    if notes:
        name, text = max(notes, key=lambda x: len(x[1]))
        return "这餐里最值得留意的一点：%s —— %s" % (name, text)
    return "这餐的六项都在参考范围内，是'轻负担'的一餐。"


def _cert_id(foods):
    """Stable pseudo-id so the same meal set yields the same certificate code."""
    import hashlib

    h = hashlib.sha1(("|".join(sorted(f["name"] for f in foods))).encode("utf-8"))
    return "MCD-%s" % h.hexdigest()[:8].upper()


def build_lesson_page(foods, source):
    """Interactive course page: 6 lessons, each with a data-derived quiz."""
    lessons = []
    used_groups = set()
    for c in CURRICULUM:
        quiz = build_quiz(foods, c["dimension"], avoid_keys=used_groups)
        if not quiz:
            continue
        cmp_ = quiz.get("compare")
        if cmp_ and cmp_.get("group_key"):
            used_groups.add(cmp_["group_key"])

        # Teaching material: a real A/B pair from the live menu. Showing two
        # comparable items side by side teaches far more than a bare ranking,
        # because only one variable changed.
        cards = []
        compare = quiz.get("compare")
        if compare:
            cards.append(
                '<div class="mini side"><div class="mn">%s</div><div class="mv">%s</div>'
                '<div class="mp">%s · 小份</div></div>'
                % (
                    html.escape(compare["low_name"]),
                    html.escape(compare["low_value"]),
                    html.escape(compare["label"]),
                )
            )
            cards.append(
                '<div class="mini side hi"><div class="mn">%s</div><div class="mv">%s</div>'
                '<div class="mp">%s · 大份</div></div>'
                % (
                    html.escape(compare["high_name"]),
                    html.escape(compare["high_value"]),
                    html.escape(compare["label"]),
                )
            )
            cards.append(
                '<div class="mini diff"><div class="mn">差值</div><div class="mv">%s</div>'
                '<div class="mp">相当于全天参考量的 %.1f%%</div></div>'
                % (html.escape(compare["diff"]), quiz.get("gap_pct", 0.0))
            )
        else:
            example = sorted(
                [f for f in foods if (f.get(c["dimension"]) or 0) > 0],
                key=lambda f: f[c["dimension"]],
                reverse=True,
            )[:3]
            for f in example:
                prof = kb.food_profile(f)
                v = prof[c["dimension"]]
                cards.append(
                    '<div class="mini"><div class="mn">%s</div><div class="mv">%s</div>'
                    '<div class="mp">占全天参考量 %.0f%%</div></div>'
                    % (html.escape(f["name"]), _fmt(v["value"], v["unit"]), v["pct_of_day"])
                )

        lessons.append(
            {
                "id": c["id"],
                "title": c["title"],
                "concept": c["concept"],
                "teach": c["teach"],
                "cards": cards,
                "quiz": quiz,
            }
        )

    lesson_json = json.dumps(lessons, ensure_ascii=False)
    source_label = (
        "麦当劳 MCP list-nutrition-foods 实时数据"
        if source == "live"
        else "麦当劳中国官方营养成分表（演示数据）"
    )
    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>麦麦营养学徒 · 六节课</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Microsoft YaHei","PingFang SC",-apple-system,sans-serif;background:#141110;color:#F2EDE7;line-height:1.7}
.wrap{max-width:860px;margin:0 auto;padding:40px 22px 80px}
.hero{background:linear-gradient(140deg,#241C15,#2E2318);border:1px solid rgba(255,182,77,.22);
 border-radius:22px;padding:32px 30px;margin-bottom:28px}
.kick{font-size:14px;letter-spacing:5px;color:#FFB64D;font-weight:700}
h1{font-size:38px;margin:12px 0 10px;font-weight:800}
.hero p{color:rgba(242,237,231,.66);font-size:16px}
.prog{height:8px;background:rgba(255,255,255,.08);border-radius:5px;margin-top:20px;overflow:hidden}
.prog i{display:block;height:100%;background:linear-gradient(90deg,#FFB64D,#FF7A29);width:0;transition:width .35s}
.ptxt{font-size:14px;color:rgba(242,237,231,.55);margin-top:9px}
.lesson{background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.09);border-radius:18px;padding:26px 26px 24px;margin-bottom:20px}
.lesson.locked{opacity:.42}
.lh{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.num{width:32px;height:32px;border-radius:50%;background:#FFB64D;color:#241C15;font-weight:800;
 display:flex;align-items:center;justify-content:center;font-size:15px;flex:0 0 auto}
.lh h2{font-size:22px;font-weight:700}
.lk{font-size:13px;padding:4px 11px;border-radius:999px;margin-left:auto;
 background:rgba(255,255,255,.1);color:rgba(242,237,231,.7)}
.lk.ok{background:rgba(120,200,120,.18);color:#9BD89B}
.lk.no{background:rgba(255,138,91,.16);color:#FFB08A}
.concept{background:rgba(255,182,77,.08);border-left:3px solid #FFB64D;padding:13px 16px;
 border-radius:0 10px 10px 0;font-size:15px;color:rgba(242,237,231,.85);margin-bottom:14px}
.teach{font-size:15px;color:rgba(242,237,231,.62);margin-bottom:16px}
.minis{display:flex;gap:12px;margin-bottom:18px;flex-wrap:wrap}
.mini{flex:1;min-width:150px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);
 border-radius:12px;padding:13px 15px}
.mini.side{min-width:190px}
.mini.hi{background:rgba(255,182,77,.1);border-color:rgba(255,182,77,.4)}
.mini.diff{background:rgba(255,138,91,.08);border-color:rgba(255,138,91,.3);min-width:150px}
.mini.diff .mv{color:#FF8A5B}
.mn{font-size:16px;font-weight:700}
.mv{font-size:20px;color:#FFB64D;font-weight:800;margin-top:5px;font-variant-numeric:tabular-nums}
.mp{font-size:13px;color:rgba(242,237,231,.5);margin-top:3px}
.q{background:rgba(0,0,0,.22);border-radius:13px;padding:18px}
.qt{font-size:17px;font-weight:700;margin-bottom:13px}
.opts{display:flex;flex-direction:column;gap:9px}
.opt{text-align:left;background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.12);
 color:#F2EDE7;padding:12px 16px;border-radius:10px;font-size:15px;cursor:pointer;
 font-family:inherit;transition:.16s}
.opt:hover:not(:disabled){background:rgba(255,182,77,.13);border-color:rgba(255,182,77,.45)}
.opt:disabled{cursor:default}
.opt.right{background:rgba(120,200,120,.2);border-color:#7CC87C;color:#B6E8B6}
.opt.wrong{background:rgba(255,90,70,.16);border-color:#E4634A;color:#FFB4A0}
.expl{margin-top:13px;font-size:14px;color:rgba(242,237,231,.72);padding:12px 15px;
 background:rgba(255,255,255,.045);border-radius:10px;display:none}
.expl.show{display:block}
.next{margin-top:16px;width:100%;padding:13px;background:linear-gradient(90deg,#FFB64D,#FF7A29);
 color:#241C15;border:none;border-radius:11px;font-size:16px;font-weight:800;cursor:pointer;font-family:inherit;display:none}
.next.show{display:block}
footer{margin-top:40px;padding-top:22px;border-top:1px solid rgba(255,255,255,.1);
 font-size:13px;color:rgba(242,237,231,.4);line-height:1.8}
</style></head><body><div class="wrap">
<div class="hero">
  <div class="kick">MCD NUTRITION ACADEMY</div>
  <h1>麦麦营养学徒 · 六节课</h1>
  <p>用麦当劳真实菜单的六维营养数据当教材。每课一个知识点，答对一题解锁下一课，
     全部答完生成一张可分享的结业证。</p>
  <div class="prog"><i id="pb"></i></div>
  <div class="ptxt" id="pt">已完成 0 / 6 课</div>
</div>
<div id="lessons"></div>
<footer>
  数据来源：__SOURCE__。<br>
  营养素参考量采用《中国居民膳食营养素参考摄入量》，仅供营养科普参考，不构成医疗、营养或其他专业建议。<br>
  餐品信息以麦当劳官方渠道实时结果为准。
</footer>
</div>
<script>
const LESSONS = __LESSONS__;
const done = new Set();
const box = document.getElementById('lessons');
LESSONS.forEach((L,i)=>{
  const el = document.createElement('div');
  el.className = 'lesson' + (i>0?' locked':'');
  const opts = L.quiz.options.map(o=>`<button class="opt" data-n="${o}">${o}</button>`).join('');
  el.innerHTML = `
    <div class="lh"><div class="num">${i+1}</div><h2>${L.title}</h2>
      <span class="lk ${i===0?'ok':'no'}">${i===0?'已解锁':'待解锁'}</span></div>
    <div class="concept">${L.concept}</div>
    <div class="teach">${L.teach}</div>
    <div class="minis">${L.cards.join('')}</div>
    <div class="q"><div class="qt">${L.quiz.question}</div>
      <div class="opts">${opts}</div>
      <div class="expl" id="e${i}"></div></div>
    <button class="next" id="n${i}">解锁下一课</button>`;
  box.appendChild(el);

  el.querySelectorAll('.opt').forEach(b=>b.addEventListener('click',()=>{
    if(done.has(L.id)) return;
    const ok = b.dataset.n === L.quiz.answer;
    el.querySelectorAll('.opt').forEach(x=>{
      x.disabled=true;
      if(x.dataset.n===L.quiz.answer) x.classList.add('right');
    });
    if(!ok){ b.classList.add('wrong');
      el.querySelector('#e'+i).innerHTML = '再想想～ 正确答案已标绿。'+L.quiz.explain; }
    else { el.querySelector('#e'+i).innerHTML = '答对了！'+L.quiz.explain; }
    el.querySelector('#e'+i).classList.add('show');
    if(ok){
      done.add(L.id);
      el.querySelector('.lk').className='lk ok';
      el.querySelector('.lk').textContent='已通关';
      const nxt=el.querySelector('#n'+i); nxt.classList.add('show');
      nxt.addEventListener('click',()=>{
        if(nxt.dataset.go) return;
        const all=el.parentElement.querySelectorAll('.lesson');
        const me=Array.from(all).indexOf(el);
        if(me+1<all.length){ all[me+1].classList.remove('locked');
          all[me+1].querySelector('.lk').className='lk ok';
          all[me+1].querySelector('.lk').textContent='已解锁';
          all[me+1].scrollIntoView({behavior:'smooth',block:'center'}); }
        nxt.dataset.go='1'; nxt.textContent='已解锁下一课 →';
        update();
      });
    }
    update();
  }));
});
function update(){
  const pct = Math.round(done.size/LESSONS.length*100);
  document.getElementById('pb').style.width = pct+'%';
  document.getElementById('pt').textContent = `已完成 ${done.size} / ${LESSONS.length} 课`+
    (done.size===LESSONS.length ? ' · 可以生成结业证了 🎉' : '');
}
update();
</script></body></html>"""
    doc = doc.replace("__SOURCE__", source_label).replace("__LESSONS__", lesson_json)
    return doc


def render_png(html_path, png_path, width=1080, height=1350):
    """Render the certificate HTML to PNG with Playwright (optional)."""
    node = os.environ.get("NODE_BIN") or "node"
    renderer = os.path.join(HERE, "render_png.js")
    env = dict(os.environ)
    try:
        subprocess.run(
            [node, renderer, os.path.abspath(html_path), os.path.abspath(png_path),
             str(width), str(height)],
            check=True,
            env=env,
            timeout=180,
        )
        return True
    except Exception as e:
        print("warn: PNG render failed (%s); HTML is still usable" % e, file=sys.stderr)
        return False


def main():
    foods = load_foods()
    source = "demo"
    if os.path.exists(DATA):
        with open(DATA, "r", encoding="utf-8") as f:
            source = json.load(f).get("source", "demo")

    os.makedirs(OUT, exist_ok=True)

    # default meal set: one realistic McDonald's order
    default_names = ["巨无霸", "薯条", "可口可乐"]
    chosen = [f for name in default_names for f in foods if f["name"] == name]
    if not chosen:
        chosen = foods[:4]

    points = kb.radar_points(chosen)
    lessons_done = ["energy", "protein", "fat", "carb", "sodium", "calcium"]

    with open(os.path.join(OUT, "lesson.html"), "w", encoding="utf-8") as f:
        f.write(build_lesson_page(foods, source))
    with open(os.path.join(OUT, "certificate.html"), "w", encoding="utf-8") as f:
        f.write(build_certificate(foods, chosen, points, lessons_done, source))
    print("wrote out/lesson.html and out/certificate.html")

    render_png(
        os.path.abspath(os.path.join(OUT, "certificate.html")),
        os.path.abspath(os.path.join(OUT, "certificate.png")),
    )


if __name__ == "__main__":
    main()
