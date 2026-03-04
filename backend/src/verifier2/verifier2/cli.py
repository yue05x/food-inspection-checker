from __future__ import annotations

import argparse
import json
import os
import sys

from .config import DEFAULT_CONFIG_PATH, build_config
from .runner import run_smoke, write_artifacts, fetch_and_update_from_detail_page
from .test_input import parse_line, read_test_lines, read_input_json, extract_gb_number
from .validate import format_user_friendly_report, validate_standard_for_production_date


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Tavily MCP smoke test (Foodmate standard search).")
    p.add_argument("--mcp-url", dest="mcp_url", default=None, help="Full Tavily MCP URL (includes tavilyApiKey).")
    p.add_argument("--config", dest="config_path", default=DEFAULT_CONFIG_PATH, help="Path to local config JSON.")
    p.add_argument("--input-json", dest="input_json", default="input.json", help="Path to input.json file.")
    p.add_argument("--output-txt", dest="output_txt", default="output.txt", help="Path to output.txt file.")
    p.add_argument("--test-txt", dest="test_path", default=None, help="Path to test.txt (deprecated, use --input-json).")
    p.add_argument("--line", dest="line_index", type=int, default=0, help="Which line to use from test.txt (0-based).")
    p.add_argument("--artifacts-dir", dest="artifacts_dir", default="artifacts", help="Where to write output JSON files.")
    return p


def main(argv: list[str] | None = None) -> int:
    # Best-effort: make Chinese output readable on Windows terminals.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = build_arg_parser().parse_args(argv)

    try:
        cfg = build_config(args.mcp_url, args.config_path, args.test_path)
    except ValueError:
        print("Missing Tavily MCP URL.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Provide it in ONE of the following ways:", file=sys.stderr)
        print("  1) PowerShell env var (recommended):", file=sys.stderr)
        print('     $env:TAVILY_MCP_URL = \"https://mcp.tavily.com/mcp/?tavilyApiKey=...\"', file=sys.stderr)
        print("     python mcp_tavily_demo.py", file=sys.stderr)
        print("  2) CLI flag:", file=sys.stderr)
        print('     python mcp_tavily_demo.py --mcp-url \"https://mcp.tavily.com/mcp/?tavilyApiKey=...\"', file=sys.stderr)
        print("  3) Local config file (gitignored):", file=sys.stderr)
        print(f"     Create {DEFAULT_CONFIG_PATH} with:", file=sys.stderr)
        print('       {\"TAVILY_MCP_URL\": \"https://mcp.tavily.com/mcp/?tavilyApiKey=...\"}', file=sys.stderr)
        return 2

    # 读取 input.json
    try:
        input_data = read_input_json(args.input_json)
    except FileNotFoundError:
        print(f"找不到输入文件：{args.input_json}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误：{e}", file=sys.stderr)
        return 2

    # 提取字段
    summary = input_data.get("summary", {})
    food_name = summary.get("food_name", "未知食品")
    production_date = summary.get("production_date")
    gb_codes = summary.get("gb_codes", [])

    if not production_date:
        print("缺少生产日期（production_date）", file=sys.stderr)
        return 2

    if not gb_codes:
        print("缺少国标编号（gb_codes）", file=sys.stderr)
        return 2

    # 输出文件
    output_lines = []
    output_lines.append(f"食品名称：{food_name}")
    output_lines.append(f"生产日期：{production_date}")
    output_lines.append(f"待校验国标数量：{len(gb_codes)}")
    output_lines.append("=" * 80)
    output_lines.append("")

    # 对每个 GB 编号进行检索和校验
    for idx, gb_code in enumerate(gb_codes, start=1):
        gb_number = extract_gb_number(gb_code)
        
        output_lines.append(f"【{idx}/{len(gb_codes)}】校验国标：{gb_code} (GB {gb_number})")
        output_lines.append("-" * 80)
        
        try:
            out, parsed = run_smoke(cfg.mcp_url, gb_number=gb_number)
            out["input_info"] = {
                "food_name": food_name,
                "production_date": production_date,
                "gb_code": gb_code,
                "gb_number": gb_number,
            }

            # 保存 artifacts（每个 GB 编号独立保存）
            out_path, structured_path = write_artifacts(out, parsed, artifacts_dir=args.artifacts_dir, gb_number=gb_number)

            # 从详情页获取并更新标准信息
            html_dir = os.path.join(os.path.dirname(args.artifacts_dir), "html")
            success, error_msg = fetch_and_update_from_detail_page(
                parsed, 
                gb_number, 
                html_dir=html_dir, 
                artifacts_dir=args.artifacts_dir
            )
            
            if not success:
                output_lines.append(f"提示：详情页信息更新失败（{error_msg}），使用初始信息继续校验")
                output_lines.append("")

            # 校验
            result = validate_standard_for_production_date(production_date=production_date, standard_info=parsed)
            report = format_user_friendly_report(standard_info=parsed, result=result)
            
            output_lines.append(report)
            
        except Exception as e:
            output_lines.append(f"处理失败：{e}")
            import traceback
            output_lines.append(traceback.format_exc())
        
        output_lines.append("")
        output_lines.append("")

    # 写入输出文件
    output_content = "\n".join(output_lines)
    with open(args.output_txt, "w", encoding="utf-8") as f:
        f.write(output_content)

    print(f"校验完成！结果已保存到：{args.output_txt}")
    print(f"共校验 {len(gb_codes)} 个国标")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


