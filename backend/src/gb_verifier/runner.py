from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from .foodmate_extract import (
    extract_abolish_date_from_detail_page,
    extract_dates_from_search_page,
    extract_detail_url_from_search_page,
    extract_status_for_gb,
    extract_status_from_any,
)
from .html_extractor import extract_standard_info_from_html, fetch_detail_page_content
from .mcp_client import build_tool_args, connect, find_tool, jsonrpc, pick_search_tool


def _safe_get_raw_content(resp: Optional[dict[str, Any]]) -> Optional[str]:
    if not isinstance(resp, dict):
        return None
    try:
        return (
            (((resp.get("body") or {}).get("result") or {}).get("structuredContent") or {}).get("results", [{}])[0].get("raw_content")
        )
    except Exception:
        return None


def _safe_get_url(resp: Optional[dict[str, Any]]) -> Optional[str]:
    if not isinstance(resp, dict):
        return None
    try:
        return (((resp.get("body") or {}).get("result") or {}).get("structuredContent") or {}).get("results", [{}])[0].get("url")
    except Exception:
        return None


def run_smoke(mcp_url: str, gb_number: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Returns:
      - out: full trace (MCP raw responses + parsed_standard_info)
      - parsed: compact user-friendly structure
    """
    query = (
        f"GB {gb_number} 食品安全国家标准 食品中农药最大残留限量 "
        f"标准状态 发布日期 实施日期 "
        f"site:down.foodmate.net/standard/sort"
    )

    conn = connect(mcp_url)

    init_resp = jsonrpc(
        conn,
        req_id=1,
        method="initialize",
        params={
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "verifier2-mcp", "version": "0.1.0"},
            "capabilities": {},
        },
    )

    tools_resp = jsonrpc(conn, req_id=2, method="tools/list", params={})
    tools = (((tools_resp.get("body") or {}).get("result") or {}).get("tools")) if isinstance(tools_resp.get("body"), dict) else None
    if not isinstance(tools, list):
        tools = []

    tool_name = pick_search_tool(tools)
    chosen_tool = find_tool(tools, tool_name) if tool_name else None

    search_resp = None
    extract_resp = None
    extract_resp_alt = None
    extract_resp_text = None
    extract_detail_resp = None
    extract_detail_text = None
    fallback_search_resp = None

    if tool_name and chosen_tool:
        tool_args = build_tool_args(chosen_tool, query=query)
        search_resp = jsonrpc(conn, req_id=3, method="tools/call", params={"name": tool_name, "arguments": tool_args})

        # Deterministic search page URL
        search_page_url = f"https://down.foodmate.net/standard/search.php?kw={gb_number}"

        extract_tool = find_tool(tools, "tavily_extract")
        if extract_tool:
            extract_args = {"urls": [search_page_url], "format": "markdown", "extract_depth": "advanced", "include_images": True}
            extract_resp = jsonrpc(conn, req_id=4, method="tools/call", params={"name": "tavily_extract", "arguments": extract_args})

            extract_args_alt = {"urls": [search_page_url], "format": "markdown", "extract_depth": "basic"}
            extract_resp_alt = jsonrpc(conn, req_id=7, method="tools/call", params={"name": "tavily_extract", "arguments": extract_args_alt})

            extract_args_text = {"urls": [search_page_url], "format": "text", "extract_depth": "basic"}
            extract_resp_text = jsonrpc(conn, req_id=8, method="tools/call", params={"name": "tavily_extract", "arguments": extract_args_text})

            # Find detail URL from extracted pages (prefer markdown advanced -> alt -> text)
            detail_url = None
            for candidate in (extract_resp, extract_resp_alt, extract_resp_text):
                raw = _safe_get_raw_content(candidate)
                if isinstance(raw, str):
                    m = re.search(r"https?://down\.foodmate\.net/standard/sort/\d+/\d+\.html", raw)
                    if m:
                        detail_url = m.group(0)
                        break

            if not detail_url:
                fb_tool = find_tool(tools, "tavily_search")
                if fb_tool:
                    fb_query = f"GB {gb_number} site:down.foodmate.net/standard/sort"
                    fb_args = build_tool_args(fb_tool, query=fb_query)
                    fallback_search_resp = jsonrpc(conn, req_id=5, method="tools/call", params={"name": "tavily_search", "arguments": fb_args})
                    try:
                        fb_results = (
                            (((fallback_search_resp.get("body") or {}).get("result") or {}).get("structuredContent") or {}).get("results")
                        )
                    except Exception:
                        fb_results = None
                    if isinstance(fb_results, list):
                        for r in fb_results:
                            u = (r or {}).get("url")
                            if isinstance(u, str) and re.search(r"/standard/sort/\d+/\d+\.html$", u):
                                detail_url = u
                                break

            if detail_url:
                extract_detail_args = {"urls": [detail_url], "format": "markdown", "extract_depth": "advanced", "include_images": True}
                extract_detail_resp = jsonrpc(
                    conn, req_id=6, method="tools/call", params={"name": "tavily_extract", "arguments": extract_detail_args}
                )
                extract_detail_text_args = {"urls": [detail_url], "format": "text", "extract_depth": "basic"}
                extract_detail_text = jsonrpc(
                    conn, req_id=9, method="tools/call", params={"name": "tavily_extract", "arguments": extract_detail_text_args}
                )

    # -------- parsed output --------
    parsed: dict[str, Any] = {
        "gb_number": gb_number,
        "foodmate_search_page_url": f"https://down.foodmate.net/standard/search.php?kw={gb_number}",
        "publish_date": None,
        "implement_date": None,
        "abolish_date": None,
        "status": None,
        "foodmate_detail_page_url": None,
    }

    # Search page raw_content candidates
    for r in (_safe_get_raw_content(extract_resp), _safe_get_raw_content(extract_resp_alt), _safe_get_raw_content(extract_resp_text)):
        if isinstance(r, str) and (parsed["publish_date"] is None or parsed["implement_date"] is None):
            parsed.update(extract_dates_from_search_page(r))
        if isinstance(r, str) and parsed["foodmate_detail_page_url"] is None:
            parsed["foodmate_detail_page_url"] = extract_detail_url_from_search_page(r)
        if isinstance(r, str) and parsed["status"] is None:
            parsed["status"] = extract_status_for_gb(r, gb_number)

    # Prefer extracted detail url if present
    extracted_detail_url = _safe_get_url(extract_detail_resp) or _safe_get_url(extract_detail_text)
    if isinstance(extracted_detail_url, str) and extracted_detail_url:
        parsed["foodmate_detail_page_url"] = extracted_detail_url

    # Abolish date (detail page text first, then markdown)
    for dr in (_safe_get_raw_content(extract_detail_text), _safe_get_raw_content(extract_detail_resp)):
        if isinstance(dr, str) and parsed["abolish_date"] is None:
            parsed["abolish_date"] = extract_abolish_date_from_detail_page(dr)

    # Final status fallback (rare)
    if not parsed["status"]:
        parsed["status"] = extract_status_from_any(extract_resp_text) or extract_status_from_any(search_resp)

    # Extract structuredContent from search_response
    search_structured_content = None
    if search_resp and isinstance(search_resp, dict):
        try:
            search_structured_content = (
                (search_resp.get("body", {}).get("result", {})).get("structuredContent")
            )
        except Exception:
            pass

    # Build compact output with only essential fields
    out = {
        "search_structured_content": search_structured_content,
        "parsed_standard_info": parsed,
    }

    return out, parsed


def write_artifacts(
    out: dict[str, Any], 
    parsed: dict[str, Any], 
    artifacts_dir: str = "artifacts",
    gb_number: Optional[str] = None
) -> tuple[str, str]:
    os.makedirs(artifacts_dir, exist_ok=True)
    
    # 如果提供了 gb_number，使用它作为文件名的一部分
    if gb_number:
        safe_gb = gb_number.replace("/", "-").replace("\\", "-")
        out_path = os.path.join(artifacts_dir, f"tavily_mcp_smoke_{safe_gb}.json")
        structured_path = os.path.join(artifacts_dir, f"standard_info_{safe_gb}.json")
    else:
        out_path = os.path.join(artifacts_dir, "tavily_mcp_smoke.json")
        structured_path = os.path.join(artifacts_dir, "standard_info.json")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(structured_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    return out_path, structured_path


def fetch_and_update_from_detail_page(
    parsed: dict[str, Any],
    gb_number: str,
    html_dir: str = "html",
    artifacts_dir: str = "artifacts"
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    从详情页获取HTML并更新标准信息
    
    Args:
        parsed: 初始的标准信息字典
        gb_number: GB编号
        html_dir: HTML文件保存目录
        artifacts_dir: JSON文件保存目录
        
    Returns:
        (success, message, html_content): 是否成功、说明信息、HTML内容
    """
    detail_url = parsed.get('foodmate_detail_page_url')
    
    if not detail_url:
        return False, "未找到详情页URL", None
    
    try:
        # 获取详情页HTML
        html_content = fetch_detail_page_content(detail_url, timeout=30)
        
        # 保存HTML文件
        os.makedirs(html_dir, exist_ok=True)
        safe_gb = gb_number.replace("/", "-").replace("\\", "-")
        html_path = os.path.join(html_dir, f"gb_{safe_gb}_detail.html")
        
        # 提取 <div class="fl_rb"> 到 </div> 的部分
        start_marker = '<div class="fl_rb">'
        end_marker = '<div class="biaoqian">'
        start_idx = html_content.find(start_marker)
        
        if start_idx != -1:
            end_idx = html_content.find(end_marker, start_idx)
            if end_idx != -1:
                content_to_save = html_content[start_idx:end_idx]
            else:
                content_to_save = html_content[start_idx:]
        else:
            content_to_save = html_content
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content_to_save)
        
        # 从HTML中提取信息
        extracted_info = extract_standard_info_from_html(html_content, detail_url)
        
        # 保留原有的URL字段，只更新其他字段
        preserved_urls = {
            'foodmate_search_page_url': parsed.get('foodmate_search_page_url'),
            'foodmate_detail_page_url': parsed.get('foodmate_detail_page_url'),
        }
        
        # 更新字段（只更新非None的值）
        for key in ['gb_number', 'publish_date', 'implement_date', 'abolish_date', 'status']:
            if extracted_info.get(key) is not None:
                parsed[key] = extracted_info[key]
        
        # 确保URL字段不被覆盖
        parsed.update(preserved_urls)
        
        # 重新写入JSON文件
        os.makedirs(artifacts_dir, exist_ok=True)
        safe_gb = gb_number.replace("/", "-").replace("\\", "-")
        structured_path = os.path.join(artifacts_dir, f"standard_info_{safe_gb}.json")
        with open(structured_path, 'w', encoding='utf-8') as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        
        return True, None, html_content
        
    except Exception as e:
        return False, str(e), None
