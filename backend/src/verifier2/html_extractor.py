"""HTML详情页信息提取模块"""

from __future__ import annotations

import re
import urllib.request
from typing import Optional


def fetch_detail_page_content(url: str, timeout: int = 30) -> str:
    """
    获取详情页内容，正确处理 gb2312 编码
    
    Args:
        url: 详情页 URL
        timeout: 超时时间（秒）
        
    Returns:
        页面 HTML 内容（UTF-8 字符串）
        
    Raises:
        Exception: 网络请求失败或解码失败
    """
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        # 读取原始字节
        raw_bytes = resp.read()
        
        # 尝试使用 gb2312 解码
        try:
            content = raw_bytes.decode('gb2312')
        except UnicodeDecodeError:
            # 如果 gb2312 失败，尝试 gbk（gb2312 的超集）
            try:
                content = raw_bytes.decode('gbk')
            except UnicodeDecodeError:
                # 最后尝试 utf-8
                content = raw_bytes.decode('utf-8', errors='replace')
        
        return content


def extract_text_between(html: str, start: str, end: str) -> Optional[str]:
    """
    提取两个标记之间的文本内容，去除HTML标签
    
    Args:
        html: HTML 内容
        start: 起始标记
        end: 结束标记
        
    Returns:
        提取的文本内容，如果未找到则返回 None
    """
    start_idx = html.find(start)
    if start_idx == -1:
        return None
    
    start_idx += len(start)
    end_idx = html.find(end, start_idx)
    if end_idx == -1:
        return None
    
    content = html[start_idx:end_idx]
    # 移除HTML标签
    content = re.sub(r'<[^>]+>', '', content)
    # 清理空白字符
    content = content.strip()
    return content if content else None


def extract_standard_info_from_html(html: str, detail_url: str) -> dict:
    """
    从HTML详情页中提取标准信息
    
    Args:
        html: HTML 内容
        detail_url: 详情页 URL
        
    Returns:
        包含标准信息的字典，包括以下字段：
        - gb_number: GB编号（如 "GB 2763-2021"）
        - publish_date: 发布日期
        - implement_date: 实施日期
        - abolish_date: 废止日期（可能为 None）
        - status: 标准状态（"现行有效" 或 "已废止"）
    """
    info = {
        "gb_number": None,
        "publish_date": None,
        "implement_date": None,
        "abolish_date": None,
        "status": None,
    }
    
    # 提取GB编号（从标题中）
    title_match = re.search(r'<span>(GB\s+[\d\.-]+)', html)
    if title_match:
        info["gb_number"] = title_match.group(1)
    
    # 提取发布日期
    publish_date = extract_text_between(html, '<th bgcolor="#FFFFFF">发布日期</th>', '</td>')
    if publish_date:
        # 提取最后一个>之后的内容
        if '>' in publish_date:
            publish_date = publish_date.split('>')[-1].strip()
        info["publish_date"] = publish_date
    
    # 提取实施日期
    implement_date = extract_text_between(html, '<th bgcolor="#FFFFFF">实施日期</th>', '</td>')
    if implement_date:
        # 提取最后一个>之后的内容
        if '>' in implement_date:
            implement_date = implement_date.split('>')[-1].strip()
        info["implement_date"] = implement_date
    
    # 提取废止日期
    abolish_date = extract_text_between(html, '<th bgcolor="#FFFFFF">废止日期</th>', '</td>')
    if abolish_date:
        # 提取最后一个>之后的内容
        if '>' in abolish_date:
            abolish_date = abolish_date.split('>')[-1].strip()
        # 如果是"暂无"，则设置为 None
        if abolish_date == "暂无":
            info["abolish_date"] = None
        else:
            info["abolish_date"] = abolish_date
    
    # 提取标准状态（通过图片判断）
    status_section = extract_text_between(html, '<th bgcolor="#FFFFFF">标准状态</th>', '<th bgcolor="#FFFFFF">实施日期</th>')
    if status_section is not None:
        # 在原始HTML中查找状态部分
        status_start = html.find('<th bgcolor="#FFFFFF">标准状态</th>')
        if status_start != -1:
            status_end = html.find('<th bgcolor="#FFFFFF">实施日期</th>', status_start)
            if status_end != -1:
                status_html = html[status_start:status_end]
                if 'yjfz.gif' in status_html:
                    info["status"] = "已废止"
                elif 'xxyx.gif' in status_html:
                    info["status"] = "现行有效"
    
    return info

