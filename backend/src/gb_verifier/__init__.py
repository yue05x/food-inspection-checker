"""
GB 标准验证包装模块

提供简化的接口来验证国标有效性
"""
from __future__ import annotations

import json
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

# Updated imports to use the local gb_verifier package (relative imports)
from .config import load_mcp_url
from .runner import run_smoke, fetch_and_update_from_detail_page
from .test_input import extract_gb_number
from .validate import validate_standard_for_production_date
from .screenshot import screenshot_detail_page
from .download import download_standard_from_html


CACHE_DIR = Path("static/cache")
CACHE_FILE = CACHE_DIR / "gb_verification.json"

def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_cache(cache: dict):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save cache: {e}")

def _get_cache_key(gb_code: str, production_date: str) -> str:
    return f"{gb_code}_{production_date}"

def _verify_single_code_logic(
    gb_code: str,
    production_date: str,
    mcp_url: str,
    enable_screenshot: bool,
    enable_download: bool
) -> dict:
    """内部函数：执行单个 GB 标准的验证逻辑（无缓存读取，但包含结果生成）"""
    try:
        # 提取 GB 编号
        gb_number = extract_gb_number(gb_code)
        
        # 调用验证逻辑 (Tavily Search)
        out, parsed = run_smoke(mcp_url, gb_number=gb_number)
        
        # 如果 Tavily 没找到详情页 URL，尝试本地搜索
        if not parsed.get("foodmate_detail_page_url"):
            from .html_extractor import search_gb_detail_url
            local_url = search_gb_detail_url(gb_number)
            if local_url:
                parsed["foodmate_detail_page_url"] = local_url
                print(f"Local fallback found URL for {gb_number}: {local_url}")
        
        detail_url = parsed.get("foodmate_detail_page_url")
        screenshot_path = None
        download_path = None
        
        # 从详情页获取更准确的状态信息
        try:
            import tempfile
            
            with tempfile.TemporaryDirectory() as temp_dir:
                html_dir = os.path.join(temp_dir, "html")
                artifacts_dir = os.path.join(temp_dir, "artifacts")
                
                success, error_msg, html_content = fetch_and_update_from_detail_page(
                    parsed=parsed,
                    gb_number=gb_number,
                    html_dir=html_dir,
                    artifacts_dir=artifacts_dir
                )
                
                if success:
                     # 截图功能
                    if enable_screenshot and detail_url:
                        # 确保截图目录存在
                        screenshot_dir = os.path.join("static", "screenshots")
                        os.makedirs(screenshot_dir, exist_ok=True)
                        
                        ss_success, ss_path, ss_err = screenshot_detail_page(
                            detail_url=detail_url,
                            gb_number=gb_number,
                            screenshot_dir=screenshot_dir
                        )
                        if ss_success:
                            # 转换为相对于 static 的路径，供前端访问 (必须以 / 开头)
                            screenshot_path = "/" + ss_path.replace(os.sep, "/")
                        else:
                            print(f"详情页截图失败: {ss_err}")

                    # 下载功能
                    if enable_download and html_content:
                        # 确保下载目录存在
                        download_dir = os.path.join("static", "downloads")
                        os.makedirs(download_dir, exist_ok=True)
                        
                        dl_success, dl_path, dl_err = download_standard_from_html(
                            html=html_content,
                            gb_number=gb_number,
                            download_dir=download_dir,
                            referer=detail_url
                        )
                        if dl_success:
                            # 转换为相对于 static 的路径
                            download_path = "/" + dl_path.replace(os.sep, "/")
                        else:
                            print(f"标准下载失败: {dl_err}")

                elif error_msg:
                    print(f"Warning: Failed to fetch detail page for {gb_code}: {error_msg}")
                    
        except Exception as e:
            print(f"Warning: Error fetching detail page for {gb_code}: {str(e)}")
            traceback.print_exc()
        
        # 执行校验
        validation_result = validate_standard_for_production_date(
            production_date=production_date,
            standard_info=parsed
        )
        
        # 格式化结果
        return {
            "passed": validation_result.passed,
            "status": "valid" if validation_result.passed else (
                "obsolete" if parsed.get("status") and "废止" in parsed.get("status", "") else "invalid"
            ),
            "status_text": parsed.get("status") or "未知",
            "publish_date": parsed.get("publish_date"),
            "implement_date": parsed.get("implement_date"),
            "abolish_date": parsed.get("abolish_date"),
            "detail_url": parsed.get("foodmate_detail_page_url"),
            "screenshot_path": screenshot_path,
            "download_path": download_path,
            "reasons": validation_result.reasons,
            "error": None,
            "timestamp": time.time() # 记录缓存时间
        }
        
    except Exception as e:
        return {
            "passed": False,
            "status": "error",
            "status_text": "验证失败",
            "reasons": [f"验证过程出错: {str(e)}"],
            "error": traceback.format_exc(),
            "timestamp": time.time()
        }

def verify_gb_standards(
    gb_codes: list[str],
    production_date: str,
    mcp_url: Optional[str] = None,
    config_path: str = "config.local.json",
    enable_screenshot: bool = False,
    enable_download: bool = False
) -> dict[str, dict[str, Any]]:
    """
    批量验证国标有效性 (并行 + 缓存)
    """
    # 加载 MCP URL
    if not mcp_url:
        mcp_url = load_mcp_url(None, config_path)
    
    if not mcp_url:
        return {
            code: {
                "passed": False,
                "status": "unknown",
                "status_text": "未配置验证服务",
                "reasons": ["未配置 Tavily MCP URL"],
                "error": "Missing MCP configuration"
            }
            for code in gb_codes
        }
    
    results = {}
    codes_to_fetch = []
    
    print(f"DEBUG: verify_gb_standards called with {len(gb_codes)} codes")
    
    # 1. 检查缓存
    cache = _load_cache()
    current_time = time.time()
    CACHE_TTL = 86400  # 24小时过期
    
    for code in set(gb_codes): # 去重
        key = _get_cache_key(code, production_date)
        cached_result = cache.get(key)
        
        if cached_result and (current_time - cached_result.get("timestamp", 0) < CACHE_TTL):
            print(f"DEBUG: Cache hit for {code}")
            results[code] = cached_result
            # 如果缓存里没有 screenshot_path 但现在要求截图，可能需要重新跑？
            # 简化起见，如果缓存有效直接用。如果用户强行要新截图，怎么处理？
            # 暂时认为缓存优先。
        else:
            print(f"DEBUG: Cache miss for {code}, scheduling fetch")
            codes_to_fetch.append(code)
            
    # 2. 并行处理未缓存的项目
    if codes_to_fetch:
        print(f"Verifying {len(codes_to_fetch)} standards (parallel)...")
        # log to file
        with open("gb_verify.log", "a") as logf:
            logf.write(f"[{time.ctime()}] Verifying: {codes_to_fetch}\n")
            
        new_results = {}
        
        # 降低并发数以避免 403 (Foodmate 可能限制并发)
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_code = {
                executor.submit(
                    _verify_single_code_logic, 
                    code, 
                    production_date, 
                    mcp_url, 
                    enable_screenshot, 
                    enable_download
                ): code 
                for code in codes_to_fetch
            }
            
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    res = future.result()
                    new_results[code] = res
                    results[code] = res
                    print(f"DEBUG: Finished verifying {code}, result: {res.get('status')}")
                    with open("gb_verify.log", "a") as logf:
                        logf.write(f"[{time.ctime()}] Finished {code}: {res.get('status')}\n")
                except Exception as e:
                    print(f"Error verifying {code}: {e}")
                    traceback.print_exc()
                    with open("gb_verify.log", "a") as logf:
                        logf.write(f"[{time.ctime()}] Error {code}: {e}\n{traceback.format_exc()}\n")
                    results[code] = {
                        "passed": False,
                        "status": "error",
                        "status_text": "未处理异常",
                        "reasons": [str(e)],
                        "error": traceback.format_exc()
                    }
        
        # 3. 更新缓存
        if new_results:
            for code, res in new_results.items():
                key = _get_cache_key(code, production_date)
                cache[key] = res
            _save_cache(cache)
            
    return results


def verify_single_gb(
    gb_code: str,
    production_date: str,
    mcp_url: Optional[str] = None,
    config_path: str = "config.local.json",
    enable_screenshot: bool = False,
    enable_download: bool = False
) -> dict[str, Any]:
    """
    验证单个国标
    """
    results = verify_gb_standards(
        [gb_code], 
        production_date, 
        mcp_url, 
        config_path,
        enable_screenshot=enable_screenshot,
        enable_download=enable_download
    )
    return results.get(gb_code, {
        "passed": False,
        "status": "error",
        "status_text": "验证失败",
        "reasons": ["未知错误"],
        "error": "No result returned"
    })
