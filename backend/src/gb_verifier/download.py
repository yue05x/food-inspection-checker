"""标准文件下载模块"""

from __future__ import annotations

import os
import re
import urllib.request
from pathlib import Path
from typing import Optional


def extract_download_url_from_html(html: str) -> Optional[str]:
    """
    从HTML中提取下载链接
    
    Args:
        html: HTML内容
        
    Returns:
        下载链接，如果未找到则返回None
    """
    # 匹配 <a class="telecom" href="...down.php?auth=...">
    match = re.search(r'href="(https?://down\.foodmate\.net/standard/down\.php\?auth=\d+)"', html)
    if match:
        return match.group(1)
    return None


    return None


def download_standard_file(
    download_url: str,
    gb_number: str,
    download_dir: str = "report",
    referer: Optional[str] = None,
    timeout: int = 300
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    下载标准文件 (使用 Playwright)
    
    Args:
        download_url: 下载URL
        gb_number: GB编号（用于文件命名）
        download_dir: 下载目录
        referer: Referer头（详情页URL）
        timeout: 超时时间（秒）
        
    Returns:
        (success, file_path, error_msg)
    """
    if not download_url:
        return False, None, "缺少下载URL"
    
    # 创建下载目录
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True
            )
            page = context.new_page()
            
            if referer:
                page.set_extra_http_headers({'Referer': referer})
            
            # 访问下载链接
            # 注意: Foodmate 下载通常会重定向或弹窗。Playwright 需要 handle download event.
            with page.expect_download(timeout=timeout * 1000) as download_info:
                # 有些下载是点击触发，有些是直接访问 URL
                # 直接访问 URL
                try:
                    page.goto(download_url, timeout=timeout * 1000)
                except Exception:
                    pass # 忽略页面加载错误，只要触发下载即可
            
            download = download_info.value
            
            # 生成文件名
            suggested_filename = download.suggested_filename
            if not suggested_filename or "unknown" in suggested_filename.lower():
                 safe_gb = gb_number.replace("/", "-").replace("\\", "-")
                 suggested_filename = f"GB_{safe_gb}.pdf" # 默认 pdf
            
            file_path = os.path.join(download_dir, suggested_filename)
            download.save_as(file_path)
            browser.close()
            
            return True, file_path, None
            
    except Exception as e:
        return False, None, f"下载失败 (Playwright): {str(e)}"


def download_standard_from_html(
    html: str,
    gb_number: str,
    download_dir: str = "report",
    referer: Optional[str] = None
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    从HTML中提取下载链接并下载文件
    """
    download_url = extract_download_url_from_html(html)
    
    if not download_url:
        return False, None, "未找到下载链接"
    
    return download_standard_file(download_url, gb_number, download_dir, referer)
