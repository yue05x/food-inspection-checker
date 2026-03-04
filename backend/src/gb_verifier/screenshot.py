"""详情页截图模块"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeoutError = Exception


def clamp(v: float, lo: float = 0) -> float:
    """确保值不小于下限"""
    return max(lo, v)


def screenshot_detail_page(
    detail_url: str,
    gb_number: str,
    screenshot_dir: str = "screenshot",
    timeout: int = 120000,
    viewport_width: int = 1400,
    viewport_height: int = 900,
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    截取详情页中标题到日期表的区域
    
    Args:
        detail_url: 详情页 URL
        gb_number: GB 编号（用于文件命名）
        screenshot_dir: 截图保存目录
        timeout: 页面加载超时时间（毫秒）
        viewport_width: 视口宽度
        viewport_height: 视口高度
        
    Returns:
        (success, screenshot_path, error_msg)
        - success: 是否成功
        - screenshot_path: 截图文件路径（相对路径）
        - error_msg: 错误信息（如果失败）
    """
    if not PLAYWRIGHT_AVAILABLE:
        return False, None, "Playwright 未安装，请运行: pip install playwright && python -m playwright install chromium"
    
    if not detail_url:
        return False, None, "缺少详情页 URL"
    
    # 创建截图目录
    Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    safe_gb = gb_number.replace("/", "-").replace("\\", "-")
    filename = f"gb_{safe_gb}_detail.png"
    screenshot_path = os.path.join(screenshot_dir, filename)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height},
                device_scale_factor=1,  # 固定像素比例，避免 Windows 缩放影响
            )
            
            # 加载页面（使用 domcontentloaded 避免等待外部脚本）
            page.goto(detail_url, wait_until="domcontentloaded", timeout=timeout)
            page.evaluate("window.scrollTo(0, 0)")
            
            # 定位目标元素
            fl_rb = page.locator("div.fl_rb").first
            title = page.locator("div.fl_rb div.title2").first
            table = page.locator("div.fl_rb table.xztable").first
            
            # 等待元素可见
            title.wait_for(state="visible", timeout=30000)
            table.wait_for(state="visible", timeout=30000)
            
            # 获取边界框
            b_fl = fl_rb.bounding_box()
            b_t = title.bounding_box()
            b_tb = table.bounding_box()
            
            if not b_fl or not b_t or not b_tb:
                browser.close()
                return False, None, "无法获取元素边界框"
            
            # 计算裁剪区域（从标题顶部到日期表底部，左右取 fl_rb 的宽度）
            pad = 8  # 边距
            left = clamp(b_fl["x"] - pad)
            top = clamp(b_t["y"] - pad)
            right = b_fl["x"] + b_fl["width"] + pad
            bottom = b_tb["y"] + b_tb["height"] + pad
            
            clip = {
                "x": left,
                "y": top,
                "width": right - left,
                "height": bottom - top
            }
            
            # 截图
            page.screenshot(path=screenshot_path, clip=clip)
            browser.close()
            
        return True, screenshot_path, None
        
    except PlaywrightTimeoutError as e:
        return False, None, f"页面加载超时：{str(e)}"
    except Exception as e:
        return False, None, f"截图失败：{str(e)}"
