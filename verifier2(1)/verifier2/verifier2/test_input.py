from __future__ import annotations

import json
import re
from typing import Any


GB_PATTERN = re.compile(r"国标编号：\s*GB\s*(\d+-\d{4})")
DATE_PATTERN = re.compile(r"生产日期：\s*(\d{4}-\d{1,2}-\d{1,2})")


def read_test_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def parse_line(line: str) -> dict[str, str]:
    m_gb = GB_PATTERN.search(line)
    m_dt = DATE_PATTERN.search(line)
    if not m_gb or not m_dt:
        raise ValueError(f"Unrecognized line format: {line}")
    return {"production_date": m_dt.group(1), "gb_number": m_gb.group(1), "gb_full": f"GB {m_gb.group(1)}"}


def read_input_json(path: str) -> dict[str, Any]:
    """读取 input.json 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_gb_number(gb_code: str) -> str:
    """从 GB 编号中提取数字部分，例如 'GB 2763-2016' -> '2763-2016'"""
    m = re.search(r"(\d+-\d{4})", gb_code)
    if m:
        return m.group(1)
    return gb_code.replace("GB", "").replace("gb", "").strip()


