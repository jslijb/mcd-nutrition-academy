#!/usr/bin/env python3
"""Minimal MCP client for the McDonald's China MCP server (Streamable HTTP).

Protocol: MCP Streamable HTTP transport.
    POST https://mcp.mcd.cn
    Authorization: Bearer <token>

Rate limit: 600 requests/minute per token (HTTP 429 on exceed).

Usage:
    export MDN_MCP_KEY=xxx      # or MCD_MCP_TOKEN=xxx
    python3 mcp_client.py tools                      # list all tools
    python3 mcp_client.py call list-nutrition-foods '{}'
"""

import json
import os
import sys
import urllib.error
import urllib.request

MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")
PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "mcd-nutrition-academy", "version": "1.0.0"}

# Token lookup order: explicit argument > MDN_MCP_KEY > MCD_MCP_TOKEN.
# MDN_MCP_KEY is the name used by the official MCP console; MCD_MCP_TOKEN is
# kept as an alias so either one works.
TOKEN_ENV_NAMES = ("MDN_MCP_KEY", "MCD_MCP_TOKEN")


def resolve_token(explicit=None):
    """Return the MCP token from the argument or the environment."""
    if explicit:
        return explicit.strip()
    for name in TOKEN_ENV_NAMES:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


class McpError(RuntimeError):
    pass


class McpClient:
    """Minimal MCP Streamable HTTP client. No third-party dependency."""

    def __init__(self, token=None, url=None, timeout=30):
        self.token = resolve_token(token)
        if not self.token:
            raise McpError(
                "missing MCP token: set %s env var or pass token="
                % " or ".join(TOKEN_ENV_NAMES)
            )
        self.url = url or MCP_URL
        self.timeout = timeout
        self.session_id = None
        self._seq = 0
        self._initialized = False

    def _next_id(self):
        self._seq += 1
        return self._seq

    def _post(self, payload, notify=False):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": "Bearer %s" % self.token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(
            self.url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get(
                    "mcp-session-id"
                )
                if sid:
                    self.session_id = sid
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
            if e.code == 401:
                raise McpError("HTTP 401: MCP token invalid, expired or missing")
            if e.code == 429:
                raise McpError("HTTP 429: rate limit exceeded (600 req/min)")
            raise McpError("HTTP %s: %s" % (e.code, detail))
        except urllib.error.URLError as e:
            raise McpError("network error: %s" % e.reason)
        if notify or not raw.strip():
            return None
        return self._parse(raw)

    @staticmethod
    def _parse(raw):
        """Accept both plain JSON and SSE-framed responses."""
        text = raw.lstrip()
        if text.startswith("{"):
            try:
                return json.loads(raw)
            except ValueError:
                pass
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    return json.loads(chunk)
                except ValueError:
                    continue
        raise McpError("unparsable MCP response: %s" % raw[:300])

    def _rpc(self, method, params=None, notify=False):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        if not notify:
            payload["id"] = self._next_id()
        return self._post(payload, notify=notify)

    def initialize(self):
        """Perform the MCP initialize handshake. Idempotent."""
        if self._initialized:
            return True
        resp = self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )
        self._initialized = True
        self._rpc("notifications/initialized", notify=True)
        return resp

    def list_tools(self):
        self.initialize()
        resp = self._rpc("tools/list")
        return (resp or {}).get("result", {}).get("tools", [])

    def call_tool(self, name, args=None):
        """Call a tool and return its parsed result payload."""
        self.initialize()
        resp = self._rpc("tools/call", {"name": name, "arguments": args or {}})
        if resp is None:
            return None
        if "error" in resp:
            raise McpError("tool error on %s: %s" % (name, resp["error"]))
        result = resp.get("result", {})
        content = result.get("content") or []
        for item in content:
            if item.get("type") == "text":
                text = item.get("text", "")
                try:
                    return json.loads(text)
                except ValueError:
                    return text
        return result.get("structuredContent") or result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    try:
        c = McpClient()
        if sys.argv[1] == "tools":
            for t in c.list_tools():
                print("-", t.get("name"), "|", (t.get("description") or "")[:80])
        elif sys.argv[1] == "call":
            args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
            print(json.dumps(c.call_tool(sys.argv[2], args), ensure_ascii=False, indent=2))
        else:
            print("usage: mcp_client.py tools | call <tool> [json_args]")
    except McpError as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
