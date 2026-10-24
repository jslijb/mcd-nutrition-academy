#!/usr/bin/env python3
"""Collect McDonald's nutrition data via MCP and normalise it.

Tools used (read-only):
  list-nutrition-foods  -> the full six-dimension nutrition table
  order-list            -> the user's own order history (for "your own" mode)
  query-my-account      -> loyalty points (shown on the card)

Writes:
  data/nutrition.json  -> {"source": "live|demo", "foods": [...]}

Usage:
  export MDN_MCP_KEY=xxx      # or MCD_MCP_TOKEN=xxx
  python3 collect.py
  python3 collect.py --demo
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import nutrition_kb as kb  # noqa: E402
from mcp_client import McpClient, McpError  # noqa: E402

OUT = os.path.join(ROOT, "data", "nutrition.json")


def _text_of(payload):
    """MCP tool results may be a dict, a JSON string, or plain text."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, str):
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("list"), list):
                    return item["list"]
        if isinstance(data, list):
            return data
        return payload.get("content") or json.dumps(payload, ensure_ascii=False)
    return json.dumps(payload, ensure_ascii=False)


def collect_nutrition(client):
    payload = client.call_tool("list-nutrition-foods", {})
    text = _text_of(payload)
    if not isinstance(text, str):
        rows = []
        for item in text:
            if isinstance(item, dict):
                name = item.get("productName") or item.get("name")
                if name:
                    rows.append({"name": name, **item})
        return rows
    return kb.parse_nutrition_csv(text)


def collect_orders(client):
    """Best-effort: user order history. Never fatal."""
    try:
        payload = client.call_tool("order-list", {})
    except McpError as e:
        print("warn: order-list failed: %s" % e, file=sys.stderr)
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return []
    items = data.get("list")
    return items if isinstance(items, list) else []


def collect_points(client):
    try:
        payload = client.call_tool("query-my-account", {})
    except McpError as e:
        print("warn: query-my-account failed: %s" % e, file=sys.stderr)
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, dict) else None


def main():
    demo_mode = "--demo" in sys.argv
    out = {"source": "demo", "foods": kb.load_demo_foods(), "orders": [], "points": None}

    if not demo_mode:
        try:
            client = McpClient()
            live = collect_nutrition(client)
            if live:
                out["foods"] = kb.merge_foods(live, kb.load_demo_foods())
                out["source"] = "live"
                print("live: %d foods from list-nutrition-foods" % len(live))
            else:
                print("warn: live table parsed empty, falling back to demo", file=sys.stderr)
            out["orders"] = collect_orders(client)
            out["points"] = collect_points(client)
        except McpError as e:
            print("MCP error: %s" % e, file=sys.stderr)
            print("falling back to demo data", file=sys.stderr)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("wrote %s (source=%s, foods=%d)" % (OUT, out["source"], len(out["foods"])))


if __name__ == "__main__":
    main()
