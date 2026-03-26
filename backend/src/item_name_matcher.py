# -*- coding: utf-8 -*-
"""
检验项目名称匹配辅助函数
处理括号说明、多物质合并、比值/占比复合指标等复杂情况
"""
import re

# ──────────────────────────────────────────────────────────────
# 复合指标模式：比值 / 占比 / 之和 / 总量
# 匹配到这些模式的指标名不能用子串包含来与简单指标互相匹配
# ──────────────────────────────────────────────────────────────
COMPOSITE_PATTERNS = [
    r'与.+比值',        # 亚油酸与α-亚麻酸比值
    r'和.+比值',        # A和B比值
    r'/.+比',           # A/B比
    r'比值$',           # 钙磷比值
    r'比例$',           # 钙磷比例
    r'占.+含量',        # 乳糖占碳水化合物含量
    r'占.+百分比',
    r'占比$',
    r'之和$',           # 亚硝酸盐之和
    r'总量$',           # 总汞总量
    r'总和$',
]


def is_composite_indicator(name: str) -> bool:
    """判断是否为复合/比值/占比类指标，这类指标不允许与组成成分互相模糊匹配"""
    return any(re.search(p, name) for p in COMPOSITE_PATTERNS)


# ──────────────────────────────────────────────────────────────
# 复合指标同义词归一化：将语义等价的表达统一，使
#   "乳糖占碳水化合物含量" ↔ "乳糖占碳水化合物总量"
#   "亚油酸与α亚麻酸比例"  ↔ "亚油酸与α亚麻酸比值"
# 等同义复合指标可以互相匹配。
# ──────────────────────────────────────────────────────────────
_COMPOSITE_SYNONYM_RULES = [
    (re.compile(r'占(.+?)含量$'), r'占\1总量'),   # 含量 → 总量（占比类）
    (re.compile(r'比例$'),         '比值'),        # 比例 → 比值
    (re.compile(r'占(.+?)比例$'),  r'占\1比值'),   # 占X比例 → 占X比值
]


def _normalize_composite_synonyms(name: str) -> str:
    """将复合指标中的常见同义词统一，便于语义等价比较。"""
    result = name
    for pattern, repl in _COMPOSITE_SYNONYM_RULES:
        result = pattern.sub(repl, result)
    return result


def _has_digit_letter_extension(shorter: str, longer: str) -> bool:
    """
    判断 shorter 在 longer 中的出现位置之后是否紧跟数字或ASCII字母。
    True 表示 longer 是 shorter 的"更具体版本"（如 维生素B12 vs 维生素B1），不应匹配。
    """
    idx = longer.find(shorter)
    if idx == -1:
        return False
    after_idx = idx + len(shorter)
    if after_idx >= len(longer):
        return False
    next_char = longer[after_idx]
    return next_char.isdigit() or (next_char.isascii() and next_char.isalpha())


def _safe_substring_match(a: str, b: str, min_len: int = 3) -> bool:
    """
    带保护的子串包含匹配：
    - 两边最短的一方长度 >= min_len
    - 不允许数字/字母延伸误匹配（如 B1 vs B12）
    """
    if len(a) == 0 or len(b) == 0:
        return False
    shorter = a if len(a) <= len(b) else b
    longer  = b if len(a) <= len(b) else a
    if len(shorter) < min_len:
        return False
    if shorter not in longer:
        return False
    return not _has_digit_letter_extension(shorter, longer)


def normalize_item_name(name: str) -> str:
    """
    智能标准化检验项目名称

    处理:
    1. 括号说明: 甲拌磷（甲拌磷及其氧类似物...） -> 甲拌磷
    2. 空格和特殊字符

    示例:
    - "甲拌磷（甲拌磷及其氧类似物（亚砜、砜）之和，以甲拌磷表示）" -> "甲拌磷"
    - "克百威(克百威及3-羟基克百威之和，以克百威表示)" -> "克百威"
    """
    if not name:
        return ""

    # 提取括号前的主要名称
    main_name = name
    if '(' in name or '（' in name:
        paren_pos = min(
            name.find('(') if '(' in name else len(name),
            name.find('（') if '（' in name else len(name)
        )
        main_name = name[:paren_pos]

    # 去除空格和特殊字符
    normalized = re.sub(r'\s+', '', main_name)
    return normalized.strip()


def extract_item_names(text: str) -> list:
    """
    从文本中提取可能的检验项目名称
    处理表格解析错误导致的多物质合并问题

    示例:
    - "阿维菌素哒螨灵" -> ["阿维菌素", "哒螨灵"]
    - "甲拌磷和克百威" -> ["甲拌磷", "克百威"]
    """
    if not text:
        return []

    # 先标准化
    text = normalize_item_name(text)

    # 如果文本很短,可能是单个物质
    if len(text) <= 6:
        return [text]

    # 复合指标（比值/占比/之和）不允许按分隔符拆分
    if is_composite_indicator(text):
        return [text]

    # 常见分隔符
    separators = ['和', '、', '/', '，', ',', ' ']

    for sep in separators:
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) > 1:
                # 拆出的子片段若单独构成复合指标，说明拆错了，整体保留
                if any(is_composite_indicator(p) for p in parts):
                    return [text]
                return parts

    # 尝试识别常见农药名称模式
    # 如果包含多个常见后缀,可能是多个物质
    common_suffixes = ['菌素', '灵', '磷', '威', '酯', '醇', '胺', '酮']

    suffix_count = sum(1 for suffix in common_suffixes if suffix in text)
    if suffix_count >= 2:
        # 可能是多个物质合并,尝试按后缀分割
        for suffix in common_suffixes:
            if text.count(suffix) >= 2:
                # 找到所有后缀位置
                parts = []
                last_pos = 0
                while True:
                    pos = text.find(suffix, last_pos)
                    if pos == -1:
                        break
                    parts.append(text[last_pos:pos + len(suffix)])
                    last_pos = pos + len(suffix)

                if len(parts) > 1:
                    return [p.strip() for p in parts if p.strip()]

    # 默认返回原文本
    return [text]


def fuzzy_match_item_name(report_name: str, required_name: str) -> bool:
    """
    模糊匹配检验项目名称（返回 bool，向后兼容）

    内部调用 match_item_detail，只返回 matched 字段。
    """
    return match_item_detail(report_name, required_name)["matched"]


def match_item_detail(report_name: str, required_name: str) -> dict:
    """
    带类型信息的检验项目名称匹配。

    返回:
        {
            "matched": bool,
            "match_type": "exact" | "fuzzy" | None
        }

    匹配规则:
    1. 标准化后完全匹配 → exact
    2. 复合指标（比值/占比/之和）必须完全匹配，不允许与组成成分互匹配
    3. 带数字/字母延伸保护的子串包含 → fuzzy
       - "维生素B1" 不匹配 "维生素B12"（B1后跟数字2）
    4. 提取多名称后任一精确/子串匹配 → fuzzy（同样受延伸保护）
    """
    norm_report   = normalize_item_name(report_name)
    norm_required = normalize_item_name(required_name)

    # 1. 完全匹配
    if norm_report == norm_required:
        return {"matched": True, "match_type": "exact"}

    # 2. 复合指标处理：先尝试同义词归一化后精确比较，失败才阻断模糊匹配
    if is_composite_indicator(norm_report) or is_composite_indicator(norm_required):
        syn_report   = _normalize_composite_synonyms(norm_report)
        syn_required = _normalize_composite_synonyms(norm_required)
        if syn_report == syn_required:
            return {"matched": True, "match_type": "fuzzy"}
        return {"matched": False, "match_type": None}

    # 3. 带保护的子串包含
    if _safe_substring_match(norm_report, norm_required):
        return {"matched": True, "match_type": "fuzzy"}

    # 4. 提取多个名称后匹配（仅精确 + 带保护子串）
    report_names   = extract_item_names(norm_report)
    required_names = extract_item_names(norm_required)

    for rn in report_names:
        for req_n in required_names:
            rn_norm  = normalize_item_name(rn)
            req_norm = normalize_item_name(req_n)

            if rn_norm == req_norm:
                return {"matched": True, "match_type": "fuzzy"}

            if _safe_substring_match(rn_norm, req_norm):
                return {"matched": True, "match_type": "fuzzy"}

    return {"matched": False, "match_type": None}
