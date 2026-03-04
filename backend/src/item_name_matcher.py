# -*- coding: utf-8 -*-
"""
检验项目名称匹配辅助函数
处理括号说明、多物质合并等复杂情况
"""
import re

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
    
    # 常见分隔符
    separators = ['和', '、', '/', '，', ',', ' ']
    
    for sep in separators:
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) > 1:
                return parts
    
    # 尝试识别常见农药名称模式
    # 如果包含多个常见后缀,可能是多个物质
    common_suffixes = ['菌素', '灵', '磷', '威', '酯', '醇', '胺', '酮']
    
    suffix_count = sum(1 for suffix in common_suffixes if suffix in text)
    if suffix_count >= 2:
        # 可能是多个物质合并,尝试按后缀分割
        # 这是一个简化的启发式方法
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
    模糊匹配检验项目名称
    
    匹配规则:
    1. 标准化后完全匹配
    2. 包含关系 (处理详细表述 vs 简化表述)
    3. 提取多个名称后任一匹配 (处理表格解析错误)
    
    示例:
    - "甲拌磷（...）" 匹配 "甲拌磷" ✓
    - "阿维菌素哒螨灵" 匹配 "阿维菌素" ✓
    - "阿维菌素哒螨灵" 匹配 "哒螨灵" ✓
    """
    # 标准化
    norm_report = normalize_item_name(report_name)
    norm_required = normalize_item_name(required_name)
    
    # 1. 完全匹配
    if norm_report == norm_required:
        return True
    
    # 2. 包含关系
    if norm_required in norm_report or norm_report in norm_required:
        return True
    
    # 3. 提取多个名称后匹配
    report_names = extract_item_names(norm_report)
    required_names = extract_item_names(norm_required)
    
    for rn in report_names:
        for req_n in required_names:
            # 标准化后再比较
            rn_norm = normalize_item_name(rn)
            req_norm = normalize_item_name(req_n)
            
            if rn_norm == req_norm or rn_norm in req_norm or req_norm in rn_norm:
                return True
    
    return False
