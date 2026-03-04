from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


DATE_KEYWORDS = ["生产日期", "生产/加工日期", "生产/包装日期", "生产检验日期"]
NAME_KEYWORDS = ["样品名称", "食品名称", "产品名称"]
CONCLUSION_KEYWORDS = ["检验结论", "结论", "判定"]

DATE_PATTERNS = [
    re.compile(r"\d{4}[年\-/.]\d{1,2}[月\-/.]\d{1,2}日?"),
    re.compile(r"\d{4}-\d{1,2}-\d{1,2}"),
]

CONCLUSION_REGEX = re.compile(
    r"(合格|不合格|基本符合|符合[^。；;\n]*要求|不符合[^。；;\n]*要求|未检出)"
)

GB_REGEX = re.compile(
    # 匹配 GB 或 GB/T 开头的国家标准号，例如：GB 2763-2021、GB/T 5009.12-2017 等
    r"GB(?:/T)?\s*\d+(?:\.\d+)?\s*[—\-‑–－]\s*\d{4}"
)


def _iter_text_lines(report: Dict[str, Any]) -> Iterable[str]:
    for page in report.get("pages", []):
        for line in page.get("text_lines", []) or []:
            if isinstance(line, str):
                text = line.strip()
                if text:
                    yield text


def _iter_tables(report: Dict[str, Any]) -> Iterable[List[List[Any]]]:
    for page in report.get("pages", []):
        for table in page.get("tables", []) or []:
            if table:
                yield table


def _search_first_pattern(text: str, patterns) -> Optional[str]:
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


def extract_production_date(report: Dict[str, Any]) -> Optional[str]:
    """Extract production date from text lines and tables."""
    # 先在带关键字的行中查找日期
    for line in _iter_text_lines(report):
        if any(k in line for k in DATE_KEYWORDS):
            value = _search_first_pattern(line, DATE_PATTERNS)
            if value:
                return value

    # 再在表格表头中查找对应列
    for table in _iter_tables(report):
        header = [str(c) for c in table[0]]
        target_col = None
        for idx, col_name in enumerate(header):
            if any(k in col_name for k in DATE_KEYWORDS):
                target_col = idx
                break
        if target_col is not None:
            for row in table[1:]:
                if target_col < len(row):
                    cell = str(row[target_col])
                    value = _search_first_pattern(cell, DATE_PATTERNS)
                    if value:
                        return value

    # 最后兜底：在所有文本中找第一个日期
    for line in _iter_text_lines(report):
        value = _search_first_pattern(line, DATE_PATTERNS)
        if value:
            return value

    return None


def extract_food_name(report: Dict[str, Any]) -> Optional[str]:
    """Extract food/sample name from text lines and tables."""
    # 文本行：关键字 + 冒号后的部分
    for line in _iter_text_lines(report):
        for kw in NAME_KEYWORDS:
            if kw in line:
                parts = re.split(r"[：:]", line, maxsplit=1)
                if len(parts) > 1:
                    value = parts[1].strip()
                    if value:
                        return value
                m = re.search(re.escape(kw) + r"\s*([^：:\s]+)", line)
                if m:
                    return m.group(1).strip()

    # 表格：表头列名匹配
    for table in _iter_tables(report):
        header = [str(c) for c in table[0]]
        target_col = None
        for idx, col_name in enumerate(header):
            if any(kw in col_name for kw in NAME_KEYWORDS):
                target_col = idx
                break
        if target_col is not None:
            for row in table[1:]:
                if target_col < len(row):
                    cell = str(row[target_col]).strip()
                    if cell:
                        return cell

    return None


def extract_conclusion(report: Dict[str, Any]) -> Optional[str]:
    """Extract inspection conclusion (合格/不合格/符合...要求等)."""
    # 文本行中优先带关键字的行
    for line in _iter_text_lines(report):
        if any(kw in line for kw in CONCLUSION_KEYWORDS):
            m = CONCLUSION_REGEX.search(line)
            if m:
                return m.group(0)

    # 表格列
    for table in _iter_tables(report):
        header = [str(c) for c in table[0]]
        target_col = None
        for idx, col_name in enumerate(header):
            if any(kw in col_name for kw in CONCLUSION_KEYWORDS):
                target_col = idx
                break
        if target_col is not None:
            values: List[str] = []
            for row in table[1:]:
                if target_col < len(row):
                    cell = str(row[target_col]).strip()
                    if cell:
                        values.append(cell)
            if values:
                return values[0]

    # 兜底：全文中查找常见结论短语
    for line in _iter_text_lines(report):
        m = CONCLUSION_REGEX.search(line)
        if m:
            return m.group(0)

    return None


def extract_gb_standards(report: Dict[str, Any]) -> List[str]:
    """Extract GB standard codes such as "GB 2763-2021" from text and tables.

    返回去重后的 GB 标准号列表，按在文档中出现的顺序排列。
    """

    standards: List[str] = []
    seen = set()

    def _add_from_text(text: str) -> None:
        # 先把多余空白（换行、多个空格）压缩成一个空格，避免 OCR 把标准号拆成多行
        normalized = re.sub(r"\s+", " ", text)
        for match in GB_REGEX.findall(normalized):
            value = match.strip()
            if value and value not in seen:
                seen.add(value)
                standards.append(value)

    # 先遍历所有文本行，只关注和检验结论相关的句子
    for line in _iter_text_lines(report):
        if "GB" in line and (
            any(kw in line for kw in CONCLUSION_KEYWORDS) or "经抽样检验" in line
        ):
            _add_from_text(line)

    # 再遍历所有表格行，只在包含结论关键字的行中查找 GB
    for table in _iter_tables(report):
        for row in table:
            row_text = " ".join(str(cell) for cell in row)
            if "GB" in row_text and (
                any(kw in row_text for kw in CONCLUSION_KEYWORDS) or "经抽样检验" in row_text
            ):
                _add_from_text(row_text)

    return standards


def extract_gb_standards_with_title(report: Dict[str, Any]) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    seen = set()
    used_codes = set()

    def _add_from_text(text: str) -> None:
        normalized = re.sub(r"\s+", " ", text)
        pos = 0
        while True:
            m = GB_REGEX.search(normalized, pos)
            if not m:
                break
            code = m.group(0).strip()
            start = m.end()
            tail = normalized[start:]

            # 优先：GB 号后紧跟的《……》内容，避免把后面的公告等长句一起当成标题
            book_match = re.search(r"《([^》]+)》", tail)
            if book_match and book_match.start() == 0:
                raw_title = book_match.group(1)
                end = start + book_match.end()
            else:
                # 回退：仍然用句号/分号截断
                end_match = re.search(r"[。；;]", tail)
                if end_match:
                    end = start + end_match.start()
                else:
                    end = len(normalized)
                raw_title = normalized[start:end]

            title = raw_title.strip().strip(" ，,《》[]（）()")
            # 去掉结尾的“要求/的要求”等修饰词
            title = re.sub(r"[的]*要求$", "", title).strip()
            key = (code, title)
            if code and key not in seen:
                seen.add(key)
                if code in used_codes:
                    pos = m.end()
                    continue
                used_codes.add(code)
                if title:
                    results.append({"code": code, "title": title})
                else:
                    results.append({"code": code})
            pos = m.end()

    # 与 extract_gb_standards 保持一致：只在“检验结论/经抽样检验”等语境中查 GB，
    # 避免第二个表格“检验依据”之类的 GB 号被误收集。
    for line in _iter_text_lines(report):
        if "GB" in line and (
            any(kw in line for kw in CONCLUSION_KEYWORDS) or "经抽样检验" in line
        ):
            _add_from_text(line)

    for table in _iter_tables(report):
        for row in table:
            row_text = " ".join(str(cell) for cell in row)
            if "GB" in row_text and (
                any(kw in row_text for kw in CONCLUSION_KEYWORDS) or "经抽样检验" in row_text
            ):
                _add_from_text(row_text)

    return results


def extract_inspection_items(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    for table in _iter_tables(report):
        if not table:
            continue
        header = [str(c) for c in table[0]]
        col_map: Dict[str, int] = {}
        for idx, col_name in enumerate(header):
            name = col_name.strip()
            if "序号" in name and "index" not in col_map:
                col_map["index"] = idx
            if any(k in name for k in ["检验项目", "项目名称", "项目"]) and "item" not in col_map:
                col_map["item"] = idx
            if any(k in name for k in ["计量单位", "单位"]) and "unit" not in col_map:
                col_map["unit"] = idx
            if any(k in name for k in ["标准指标", "标准要求", "限量", "标准值"]) and "standard" not in col_map:
                col_map["standard"] = idx
            if any(k in name for k in ["实测值", "检验结果", "测定值", "结果"]) and "value" not in col_map:
                col_map["value"] = idx
            if any(k in name for k in ["单项判定", "判定", "结论"]) and "conclusion" not in col_map:
                col_map["conclusion"] = idx
            if any(k in name for k in ["检验方法", "检测方法", "方法", "检验依据", "依据"]) and "method" not in col_map:
                col_map["method"] = idx

        if "item" not in col_map or "value" not in col_map:
            continue

        def _get_cell(row: List[Any], col_idx: Optional[int]) -> str:
            if col_idx is None or col_idx < 0 or col_idx >= len(row):
                return ""
            value = row[col_idx]
            if value is None:
                return ""
            return str(value).strip()

        for row in table[1:]:
            record: Dict[str, Any] = {
                "type": "item",
                "index": _get_cell(row, col_map.get("index")),
                "item": _get_cell(row, col_map.get("item")),
                "unit": _get_cell(row, col_map.get("unit")),
                "standard": _get_cell(row, col_map.get("standard")),
                "value": _get_cell(row, col_map.get("value")),
                "method": _get_cell(row, col_map.get("method")),
                "conclusion": _get_cell(row, col_map.get("conclusion")),
            }
            if any(record.get(k) for k in ["item", "value", "standard"]):
                items.append(record)

        if items:
            break

    return items
