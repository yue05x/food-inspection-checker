from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional

from .http_client import http_json, http_stream_lines


@dataclass
class McpConnection:
    post_url: str
    headers: dict[str, str]


def parse_sse_message_json(raw: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if not data:
            continue
        try:
            obj = json.loads(data)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


def try_direct_jsonrpc(mcp_url: str) -> Optional[McpConnection]:
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "verifier2-mcp", "version": "0.1.0"},
            "capabilities": {},
        },
    }
    status, body = http_json(mcp_url, init_req, timeout_s=60)
    if status == 200 and isinstance(body, dict) and "result" in body:
        return McpConnection(post_url=mcp_url, headers={})
    if status == 200 and isinstance(body, dict) and isinstance(body.get("_raw"), str):
        msgs = parse_sse_message_json(body["_raw"])
        if any(isinstance(m, dict) and m.get("result") is not None for m in msgs):
            return McpConnection(post_url=mcp_url, headers={})
    return None


def connect_via_sse(mcp_url: str, max_wait_s: int = 20) -> McpConnection:
    deadline = time.time() + max_wait_s
    post_url: Optional[str] = None
    buf: list[str] = []

    for line in http_stream_lines(mcp_url, timeout_s=max_wait_s):
        if line.startswith("data:"):
            buf.append(line[len("data:") :].strip())
        joined = "\n".join(buf).strip()
        if joined:
            try:
                obj = json.loads(joined)
                for key in ("endpoint", "postUrl", "mcpEndpoint", "messages", "messageEndpoint"):
                    if isinstance(obj, dict) and isinstance(obj.get(key), str):
                        post_url = obj[key]
                        break
            except Exception:
                pass
        if post_url:
            break
        if time.time() > deadline:
            break

    if not post_url:
        post_url = mcp_url
    return McpConnection(post_url=post_url, headers={})


def connect(mcp_url: str) -> McpConnection:
    return try_direct_jsonrpc(mcp_url) or connect_via_sse(mcp_url)


def jsonrpc(conn: McpConnection, req_id: int, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    status, body = http_json(conn.post_url, payload, headers=conn.headers, timeout_s=120)

    if isinstance(body, dict) and isinstance(body.get("_raw"), str):
        msgs = parse_sse_message_json(body["_raw"])
        for m in msgs:
            if m.get("id") == req_id:
                return {"http_status": status, "body": m, "_transport": "sse", "_raw": body.get("_raw")}
        if msgs:
            return {"http_status": status, "body": msgs[0], "_transport": "sse", "_raw": body.get("_raw")}
    return {"http_status": status, "body": body, "_transport": "json"}


def find_tool(tools: list[dict[str, Any]], name: str) -> Optional[dict[str, Any]]:
    for t in tools:
        if t.get("name") == name:
            return t
    return None


def pick_search_tool(tools: list[dict[str, Any]]) -> Optional[str]:
    candidates = []
    for t in tools:
        name = (t.get("name") or "").lower()
        desc = (t.get("description") or "").lower()
        if "search" in name or "search" in desc:
            candidates.append(t.get("name"))
    for preferred in ("tavily_search", "search", "web_search", "tavily.search"):
        for c in candidates:
            if c and c.lower() == preferred:
                return c
    return candidates[0] if candidates else None


def build_tool_args(tool: dict[str, Any], query: str) -> dict[str, Any]:
    schema = tool.get("inputSchema") or {}
    props = (schema.get("properties") or {}) if isinstance(schema, dict) else {}
    required = schema.get("required") if isinstance(schema, dict) else None

    query_keys = ["query", "q", "text", "input"]
    key = None
    for k in query_keys:
        if k in props:
            key = k
            break
    if key is None:
        key = "query"

    args: dict[str, Any] = {key: query}

    if "max_results" in props:
        args["max_results"] = 10
    if "search_depth" in props:
        args["search_depth"] = "advanced"
    if "include_domains" in props:
        args["include_domains"] = ["down.foodmate.net"]
    if "include_raw_content" in props:
        args["include_raw_content"] = True

    if isinstance(required, list):
        for r in required:
            if r not in args and r in props:
                t = (props[r] or {}).get("type")
                if t == "string":
                    args[r] = ""
                elif t in ("number", "integer"):
                    args[r] = 0
                elif t == "boolean":
                    args[r] = False
                elif t == "array":
                    args[r] = []
                elif t == "object":
                    args[r] = {}

    return args


