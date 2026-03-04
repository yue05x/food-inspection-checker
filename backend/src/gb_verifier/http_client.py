from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Iterable, Optional


def http_json(
    url: str,
    payload: dict[str, Any],
    headers: Optional[dict[str, str]] = None,
    timeout_s: int = 60,
) -> tuple[int, dict[str, Any]]:
    """
    POST JSON and parse JSON body; if body isn't JSON, return a dict with _raw/_content_type.

    Tavily MCP requires Accept: application/json, text/event-stream
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Accept", "application/json, text/event-stream")
    # Add User-Agent to avoid 403 and mimic browser
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            content_type = resp.headers.get("Content-Type", "")
            try:
                return resp.getcode(), json.loads(raw)
            except Exception as e:
                return resp.getcode(), {
                    "_raw": raw,
                    "_content_type": content_type,
                    "_json_parse_error": str(e),
                }
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw, "_content_type": e.headers.get("Content-Type", "")}


def http_stream_lines(url: str, timeout_s: int = 60, headers: Optional[dict[str, str]] = None) -> Iterable[str]:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "text/event-stream")
    # Add User-Agent to avoid 403
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        while True:
            line = resp.readline()
            if not line:
                break
            yield line.decode("utf-8", errors="replace").rstrip("\n")
