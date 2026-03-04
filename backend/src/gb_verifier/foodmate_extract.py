from __future__ import annotations

import json
import re
from typing import Any, Optional


YMD_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _first_match(pattern: re.Pattern[str], text: str) -> Optional[str]:
    m = pattern.search(text)
    return m.group(1) if m else None


def extract_dates_from_search_page(raw_text: str) -> dict[str, Optional[str]]:
    publish_date = None
    implement_date = None

    idx_pub = raw_text.find("发布日期")
    if idx_pub != -1:
        publish_date = _first_match(YMD_PATTERN, raw_text[idx_pub : idx_pub + 500])
    idx_impl = raw_text.find("实施日期")
    if idx_impl != -1:
        implement_date = _first_match(YMD_PATTERN, raw_text[idx_impl : idx_impl + 500])

    if not publish_date or not implement_date:
        m = re.search(r"\bGB\s*\d+-\d{4}\b", raw_text)
        if m:
            window = raw_text[m.start() : m.start() + 1200]
            dates = YMD_PATTERN.findall(window)
            if dates:
                publish_date = publish_date or dates[0]
                if len(dates) > 1:
                    implement_date = implement_date or dates[1]

    return {"publish_date": publish_date, "implement_date": implement_date}


def extract_detail_url_from_search_page(raw_text: str) -> Optional[str]:
    m = re.search(r"https?://down\.foodmate\.net/standard/sort/\d+/\d+\.html", raw_text)
    return m.group(0) if m else None


def extract_status_for_gb(raw_text: str, gb_number: str) -> Optional[str]:
    anchors = [f"GB {gb_number}", gb_number]
    idx = -1
    for a in anchors:
        idx = raw_text.find(a)
        if idx != -1:
            break
    if idx == -1:
        return None
    window = raw_text[max(0, idx - 400) : idx + 400]
    if "yjfz.gif" in window:
        return "已废止"
    if "xxyx.gif" in window:
        return "现行有效"
        
    # 增加文本关键字提取 fallback
    # 搜索结果通常包含: "状态：现行有效" 或 "状态：废止"
    if "状态：现行" in window or "状态:现行" in window or "现行有效" in window:
        return "现行有效"
    if "状态：废止" in window or "状态:废止" in window or "已废止" in window:
        return "已废止"
    if "状态：作废" in window or "状态:作废" in window:
        return "已废止"
    if "即将实施" in window:
        return "即将实施"
        
    return None


def extract_status_from_any(obj: Any) -> Optional[str]:
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    if "xxyx.gif" in s:
        return "现行有效"
    if "yjfz.gif" in s:
        return "已废止"
    return None


def extract_abolish_date_from_detail_page(raw_text: str) -> Optional[str]:
    idx = raw_text.find("废止日期")
    if idx != -1:
        return _first_match(YMD_PATTERN, raw_text[idx : idx + 300])
    for alt in ("作废日期", "停止实施日期", "废止时间"):
        idx2 = raw_text.find(alt)
        if idx2 != -1:
            return _first_match(YMD_PATTERN, raw_text[idx2 : idx2 + 300])
    return None
