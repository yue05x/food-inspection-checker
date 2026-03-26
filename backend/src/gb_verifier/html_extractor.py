"""HTML详情页信息提取模块"""

from __future__ import annotations

import logging
import re
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

STATUS_BY_GIF = {
    "jjss.gif": "即将实施",
    "xxyx.gif": "现行有效",
    "bfyx.gif": "部分有效",
    "jjfz.gif": "即将废止",
    "yjfz.gif": "已经废止",
}


def fetch_detail_page_content(url: str, timeout: int = 30) -> str:
    """
    获取详情页内容，使用 urllib 直接请求以保留原始 HTML 结构。
    使用 Playwright 渲染会标准化 HTML 属性（如 bgcolor="#FFFFFF" → "#ffffff"），
    导致 extract_standard_info_from_html 的字符串匹配失败，无法提取日期字段。

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
        raw_bytes = resp.read()

        try:
            return raw_bytes.decode('gb2312')
        except UnicodeDecodeError:
            try:
                return raw_bytes.decode('gbk')
            except UnicodeDecodeError:
                return raw_bytes.decode('utf-8', errors='replace')


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


def _find_date_after_label(html: str, label: str) -> Optional[str]:
    """
    用正则从 HTML 中提取 <th>label</th><td>VALUE</td> 格式的日期，
    兼容大小写差异、多余属性、内嵌标签等。
    """
    # 匹配 <th ...>label</th> 后紧跟 <td ...>内容</td>
    pattern = rf'<th[^>]*>\s*{re.escape(label)}\s*</th>\s*<td[^>]*>(.*?)</td>'
    m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    if m:
        raw = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if raw and raw not in ('暂无', '', '/'):
            return raw
    return None


def extract_standard_info_from_html(html: str, detail_url: str) -> dict:
    """
    从HTML详情页中提取标准信息（使用宽松 regex，兼容大小写/属性顺序变化）

    Returns:
        包含 gb_number / publish_date / implement_date / abolish_date / status
    """
    info = {
        "gb_number": None,
        "publish_date": None,
        "implement_date": None,
        "abolish_date": None,
        "status": None,
    }

    # GB 编号
    title_match = re.search(r'<span>(GB\s+[\d\.\-/]+)', html)
    if title_match:
        info["gb_number"] = title_match.group(1)

    # 日期字段
    info["publish_date"]   = _find_date_after_label(html, "发布日期")
    info["implement_date"] = _find_date_after_label(html, "实施日期")
    raw_abolish            = _find_date_after_label(html, "废止日期")
    info["abolish_date"]   = raw_abolish if raw_abolish and raw_abolish != "暂无" else None

    # 标准状态：优先 GIF 图片名，降级文本关键词
    for gif, status in STATUS_BY_GIF.items():
        if gif in html:
            info["status"] = status
            break
    if not info["status"]:
        # 在 <th>标准状态</th> 附近检索
        m_st = re.search(r'<th[^>]*>\s*标准状态\s*</th>(.*?)</td>', html, re.IGNORECASE | re.DOTALL)
        block = m_st.group(1) if m_st else html
        if "现行有效" in block:
            info["status"] = "现行有效"
        elif "已废止" in block or "yjfz" in block or "作废" in block:
            info["status"] = "已废止"
        elif "即将实施" in block:
            info["status"] = "即将实施"

    logger.info("HTML提取结果: publish=%s implement=%s abolish=%s status=%s",
                info["publish_date"], info["implement_date"], info["abolish_date"], info["status"])
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
    logger.info("本地搜索: %s", search_url)
    
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
        logger.warning("本地搜索失败 %s: %s", gb_number, e)
        return None
