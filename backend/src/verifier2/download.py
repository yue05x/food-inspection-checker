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


def download_standard_file(
    download_url: str,
    gb_number: str,
    download_dir: str = "report",
    referer: Optional[str] = None,
    timeout: int = 300
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    下载标准文件

    Args:
        download_url: 下载URL
        gb_number: GB编号（用于文件命名）
        download_dir: 下载目录
        referer: Referer头（详情页URL）
        timeout: 超时时间（秒）

    Returns:
        (success, file_path, error_msg)
        - success: 是否成功
        - file_path: 文件路径（相对路径）
        - error_msg: 错误信息（如果失败）
    """
    if not download_url:
        return False, None, "缺少下载URL"

    # 创建下载目录
    Path(download_dir).mkdir(parents=True, exist_ok=True)

    try:
        # 构建请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "*/*",
        }
        if referer:
            headers["Referer"] = referer

        # 发起请求
        req = urllib.request.Request(download_url, headers=headers)

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # 尝试从Content-Disposition获取文件名
            content_disposition = resp.headers.get("Content-Disposition")
            filename = None

            if content_disposition:
                # 尝试解析filename
                match = re.search(r'filename="?([^";\r\n]+)"?', content_disposition)
                if match:
                    filename = match.group(1)

            # 如果没有获取到文件名，根据Content-Type推断
            if not filename:
                content_type = resp.headers.get("Content-Type", "").lower()
                if "pdf" in content_type:
                    ext = ".pdf"
                elif "zip" in content_type:
                    ext = ".zip"
                elif "doc" in content_type:
                    ext = ".doc"
                else:
                    ext = ".pdf"  # 默认为PDF

                safe_gb = gb_number.replace("/", "-").replace("\\", "-")
                filename = f"GB_{safe_gb}{ext}"

            # 保存文件
            file_path = os.path.join(download_dir, filename)
            data = resp.read()

            with open(file_path, "wb") as f:
                f.write(data)

            return True, file_path, None

    except urllib.error.HTTPError as e:
        return False, None, f"HTTP错误 {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, None, f"网络错误: {e.reason}"
    except Exception as e:
        return False, None, f"下载失败: {str(e)}"


def download_standard_from_html(
    html: str,
    gb_number: str,
    download_dir: str = "report",
    referer: Optional[str] = None
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    从HTML中提取下载链接并下载文件

    Args:
        html: HTML内容
        gb_number: GB编号
        download_dir: 下载目录
        referer: Referer头（详情页URL）

    Returns:
        (success, file_path, error_msg)
    """
    download_url = extract_download_url_from_html(html)

    if not download_url:
        return False, None, "未找到下载链接"

    return download_standard_file(download_url, gb_number, download_dir, referer)
