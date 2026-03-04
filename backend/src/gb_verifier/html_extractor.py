"""HTML详情页信息提取模块"""

from __future__ import annotations

import re
import urllib.request
from typing import Optional


def fetch_detail_page_content(url: str, timeout: int = 30) -> str:
    """
    获取详情页内容，使用 Playwright 以绕过反爬
    
    Args:
        url: 详情页 URL
        timeout: 超时时间（秒）
        
    Returns:
        页面 HTML 内容（UTF-8 字符串）
        
    Raises:
        Exception: 网络请求失败
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError("Playwright not installed. Please run: pip install playwright && python -m playwright install chromium")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # 使用固定 User-Agent 和 视口，模拟真实浏览器
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            # 设置 header
            page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://down.foodmate.net/standard/'
            })
            
            # 访问页面
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            content = page.content()
            browser.close()
            return content
            
    except Exception as e:
        print(f"Error fetching {url} with Playwright: {e}")
        raise


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
                else:
                    # 尝试从文本中提取状态（针对没有 gif 图片的情况）
                    clean_status = re.sub(r'<[^>]+>', '', status_html).strip()
                    if "现行" in clean_status or "有效" in clean_status:
                        info["status"] = "现行有效"
                    elif "废止" in clean_status or "作废" in clean_status:
                        info["status"] = "已废止"
                    elif "即将实施" in clean_status:
                        info["status"] = "即将实施"
    
    return info


def search_gb_detail_url(gb_number: str) -> Optional[str]:
    """
    使用本地网络搜索 GB 标准的详情页 URL
    
    Args:
        gb_number: GB编号 (e.g. "2763-2021")
        
    Returns:
        详情页 URL 或 None
    """

    
    search_url = f"https://down.foodmate.net/standard/search.php?kw={gb_number}"
    print(f"Searching locally (Playwright): {search_url}")
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            # 访问搜索页
            page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            content = page.content()
            browser.close()
            
        # 查找详情页链接
        m = re.search(r"https?://down\.foodmate\.net/standard/sort/\d+/\d+\.html", content)
        if m:
            return m.group(0)
            
        return None
        
    except Exception as e:
        print(f"Local search failed for {gb_number}: {e}")
        return None
