#!/usr/bin/env python3
"""Nutrition knowledge base + radar scoring for the McDonald's nutrition academy.

Two data sources, same schema:
  1. Live  : `list-nutrition-foods` MCP tool -> CSV-ish text table
  2. Offline: data/nutrition_demo.json (McDonald's China official site, 2025-04)

Schema (per food):
  name, energy_kj, energy_kcal, protein_g, fat_g, carb_g, sodium_mg, calcium_mg

Six dimensions come straight from McDonald's China nutrition calculator:
  energy / protein / fat / carbohydrate / sodium / calcium
"""

import csv
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------- reference values
# Chinese Dietary Reference Intakes (中国居民膳食营养素参考摄入量 2023 版) -- adult
# male 18-49y light activity, used as the "one meal benchmark" for teaching.
# These are reference values for education, NOT medical advice.
REFERENCE_INTAKE = {
    "energy_kcal": {"value": 2250, "unit": "kcal", "label": "每日能量"},
    "protein_g": {"value": 65, "unit": "g", "label": "每日蛋白质"},
    "fat_g": {"value": 60, "unit": "g", "label": "每日脂肪"},
    "carb_g": {"value": 275, "unit": "g", "label": "每日碳水"},
    "sodium_mg": {"value": 1500, "unit": "mg", "label": "每日钠"},
    "calcium_mg": {"value": 800, "unit": "mg", "label": "每日钙"},
}

# Per-meal share: assume 3 meals a day -> each meal is ~1/3 of daily intake.
MEAL_SHARE = 1.0 / 3.0

# A dimension is only worth teaching about when it is a real signal:
# >= 40% of the per-meal reference counts as "worth pointing out".
WATCH_MIN = 40.0

DIMENSIONS = [
    {"key": "energy_kcal", "label": "能量", "unit": "kcal", "axis": "能量"},
    {"key": "protein_g", "label": "蛋白质", "unit": "g", "axis": "蛋白质"},
    {"key": "fat_g", "label": "脂肪", "unit": "g", "axis": "脂肪"},
    {"key": "carb_g", "label": "碳水", "unit": "g", "axis": "碳水"},
    {"key": "sodium_mg", "label": "钠", "unit": "mg", "axis": "钠"},
    {"key": "calcium_mg", "label": "钙", "unit": "mg", "axis": "钙"},
]

# How each dimension is framed in lessons. "balance" axes want a middle range;
# "limit" axes want to stay under a ceiling. Purely educational framing.
LESSON_NOTES = {
    "energy_kcal": {
        "role": "balance",
        "tip": "能量是身体一整天的'电费'，吃进去要花得掉。",
    },
    "protein_g": {
        "role": "need",
        "tip": "蛋白质是长身体、修身体的建材，量要够。",
    },
    "fat_g": {
        "role": "balance",
        "tip": "脂肪是能量储备，也是口感来源，适量最好。",
    },
    "carb_g": {
        "role": "balance",
        "tip": "碳水是最直接的燃料，主食靠它。",
    },
    "sodium_mg": {
        "role": "limit",
        "tip": "钠藏在酱料和腌渍里，是'看不见'的那一项。",
    },
    "calcium_mg": {
        "role": "need",
        "tip": "钙是骨头和牙齿的原料，牛奶和奶昔是补充大户。",
    },
}

# Food -> teaching tags. Each food gets a "spotlight" so the lesson can point at
# something genuinely interesting instead of just listing numbers.
FOOD_TAGS = {
    "巨无霸": {"tag": "双层肉饼", "note": "蛋白质在麦当劳里算高的，但钠也不低。"},
    "麦辣鸡腿汉堡": {"tag": "中国胃", "note": "麦当劳专门为中式口味研发的当家款。"},
    "麦香鱼": {"tag": "鱼排", "note": "不是炸鱼块，是正经的鳕鱼饼。"},
    "薯条": {"tag": "经典小食", "note": "中份薯条的盐分比很多人以为的多。"},
    "可口可乐": {"tag": "纯糖饮料", "note": "碳水几乎全是糖，零脂肪零蛋白。"},
    "麦乐鸡": {"tag": "共享装", "note": "按份算很容易超量，按'几块'更容易控制。"},
    "板烧鸡腿堡": {"tag": "烤制鸡肉", "note": "烤鸡腿堡脂肪比炸鸡腿堡低不少。"},
}


def _to_float(raw):
    if raw is None:
        return 0.0
    s = str(raw).strip()
    if not s or s in {"-", "—", "NA", "null", "None"}:
        return 0.0
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group()) if m else 0.0


def parse_nutrition_csv(text):
    """Parse the `list-nutrition-foods` text table into records.

    Real header observed on 2026-10:
      productName,nutritionDescription,energyKj,energyKcal,protein,fat,
      carbohydrate,sodium,calcium
    """
    rows = []
    reader = csv.reader(io.StringIO(text))
    for raw in reader:
        if not raw or len(raw) < 3:
            continue
        name = (raw[0] or "").strip()
        if not name or name.lower().startswith("productname"):
            continue
        if name.startswith("数据") or name.startswith("营养") and len(raw) < 5:
            continue
        # find the numeric columns by position, tolerant to an extra description
        # column or a trailing unit column
        nums = []
        for cell in raw[1:]:
            s = (cell or "").strip()
            if re.fullmatch(r"-?\d+(\.\d+)?", s):
                nums.append(float(s))
        if len(nums) < 6:
            continue
        energy_kj, energy_kcal, protein, fat, carb, sodium = nums[0:6]
        calcium = nums[6] if len(nums) > 6 else 0.0
        rows.append(
            {
                "name": name,
                "energy_kj": energy_kj,
                "energy_kcal": energy_kcal or (energy_kj / 4.184),
                "protein_g": protein,
                "fat_g": fat,
                "carb_g": carb,
                "sodium_mg": sodium,
                "calcium_mg": calcium,
            }
        )
    return rows


def load_demo_foods():
    path = os.path.join(ROOT, "data", "nutrition_demo.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["foods"]


def merge_foods(live, demo):
    """Live MCP data wins; demo rows fill in gaps for teaching coverage."""
    seen = {f["name"] for f in live}
    merged = list(live)
    for d in demo:
        if d["name"] not in seen:
            merged.append(d)
    return merged


def food_profile(food):
    """Per-meal % of daily reference for each of the six dimensions.

    Two ratios are reported, and they answer different questions:
      pct_of_day     -> share of the WHOLE day's reference intake (what a label
                        would show; easy to compare across a day)
      pct_of_meal    -> share of one meal's budget (1/3 of the day), used for
                        "is this single meal heavy in X?"
    """
    profile = {}
    for dim in DIMENSIONS:
        ref = REFERENCE_INTAKE[dim["key"]]
        day_ref = ref["value"]
        meal_ref = day_ref * MEAL_SHARE
        value = food.get(dim["key"], 0) or 0
        profile[dim["key"]] = {
            "value": round(value, 1),
            "unit": dim["unit"],
            "label": dim["label"],
            "pct_of_day": round((value / day_ref * 100) if day_ref else 0, 1),
            "pct_of_meal": round((value / meal_ref * 100) if meal_ref else 0, 1),
            "day_ref": round(day_ref, 1),
            "meal_ref": round(meal_ref, 1),
        }
    return profile


def teach_points(food):
    """Pick the most teachable observations for one food.

    Rules (deterministic, no randomness):
      - a "need" dimension only counts as a highlight if it reaches WATCH_MIN
      - a "limit" dimension only counts as a warning if it exceeds WATCH_MIN
      - pick the strongest one of each kind, in that priority order

    All percentages are quoted against the WHOLE day's reference intake, which
    is the unit people meet on a nutrition label. Quoting against "one meal"
    alone reads like "192% of a limit" and gets misread as a 2x overdose.
    """
    prof = food_profile(food)
    notes = []

    need = [
        (k, v)
        for k, v in prof.items()
        if LESSON_NOTES[k]["role"] == "need"
        and v["pct_of_day"] * 3 >= WATCH_MIN
    ]
    limit = [
        (k, v)
        for k, v in prof.items()
        if LESSON_NOTES[k]["role"] == "limit"
        and v["pct_of_day"] * 3 >= WATCH_MIN
    ]

    if need:
        k, v = max(need, key=lambda kv: kv[1]["pct_of_day"])
        notes.append(
            {
                "kind": "plus",
                "dimension": v["label"],
                "text": "%s 是它的亮点：这一份就占了全天参考量的 %.0f%%，%s"
                % (v["label"], v["pct_of_day"], LESSON_NOTES[k]["tip"]),
            }
        )
    if limit:
        k, v = max(limit, key=lambda kv: kv[1]["pct_of_day"])
        notes.append(
            {
                "kind": "watch",
                "dimension": v["label"],
                "text": "要留意 %s：这一份就占了全天参考量的 %.0f%%，%s"
                % (v["label"], v["pct_of_day"], LESSON_NOTES[k]["tip"]),
            }
        )
    if not notes:
        notes.append(
            {
                "kind": "plain",
                "dimension": "均衡",
                "text": "这一份的六项都在参考范围内，属于'轻负担'的一餐。",
            }
        )
    return notes


def radar_points(foods):
    """Radar chart vertices: average % of DAILY reference across the given foods.

    Values are capped at 150% so one outlier does not flatten the whole chart.
    """
    if not foods:
        return {d["key"]: 0.0 for d in DIMENSIONS}
    acc = {d["key"]: 0.0 for d in DIMENSIONS}
    for f in foods:
        prof = food_profile(f)
        for dim in DIMENSIONS:
            acc[dim["key"]] += prof[dim["key"]]["pct_of_day"]
    n = len(foods)
    return {
        k: round(min(v / n, 150.0), 1) for k, v in acc.items()
    }


def food_index(foods):
    """Case-insensitive lookup that also tolerates size suffixes (中/小/大)."""
    idx = {}
    for f in foods:
        idx[f["name"]] = f
    return idx


def find_food(foods, query):
    if not query:
        return None
    q = query.strip()
    for f in foods:
        if f["name"] == q:
            return f
    for f in foods:
        if q in f["name"] or f["name"] in q:
            return f
    return None


if __name__ == "__main__":
    demo = load_demo_foods()
    print("demo foods:", len(demo))
    for f in demo:
        prof = food_profile(f)
        print(
            "- %-12s kcal=%-6.0f prot=%-5.1f fat=%-5.1f carb=%-5.1f na=%-6.0f ca=%-5.0f"
            % (
                f["name"],
                f["energy_kcal"],
                f["protein_g"],
                f["fat_g"],
                f["carb_g"],
                f["sodium_mg"],
                f["calcium_mg"],
            )
        )
        for n in teach_points(f):
            print("    [%s] %s" % (n["kind"], n["text"]))
