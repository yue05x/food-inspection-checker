from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# 确保当前目录在 Python 路径中，以便导入 verifier2
sys.path.insert(0, str(Path(__file__).parent))

# 禁用 Intel oneDNN/MKL-DNN ---
# 必须在 paddle 任何 C++ 初始化之前设置
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_use_mkldnn_kernel"] = "0"

from flask import Flask, request, redirect, url_for, flash, jsonify
from flask_cors import CORS

# 框架加载后再通过 Python API 双重禁用 MKLDNN （应对 PaddlePaddle 3.x 的新 oneDNN 机制）
try:
    import paddle
    paddle.set_flags({'FLAGS_use_mkldnn': False})
except Exception:
    pass

from gb_verifier import verify_gb_standards
from package_image_processor import process_package_image
from ragflow_client import get_ragflow_client  # 新增RAGFlow检索客户端
from field_extractor import (
    extract_food_name,
    extract_gb_standards,
    extract_gb_standards_with_title,
    extract_inspection_items,
    extract_production_date,
)
from ocr_engine import get_ocr_engine
from pdf_reader import parse_pdf


BASE_DIR = Path(__file__).resolve().parent.parent  # Go up to PDFInfExtraction directory
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Configure Flask to use templates and static folders from parent directory
app = Flask(__name__, 
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"))
app.secret_key = "change-me-in-production"

# 允许 React 开发服务器（5173端口）跨域访问所有 /api/ 路由
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})


def process_single_file(file_storage, ocr_engine):
    """处理单个上传的PDF文件，返回检测结果和状态"""
    safe_name = Path(file_storage.filename).name
    save_path = UPLOAD_DIR / safe_name
    file_storage.save(save_path)
    print(f"[DEBUG] Started processing file: {safe_name}", flush=True)

    report = parse_pdf(str(save_path), ocr_engine=ocr_engine)
    print(f"[DEBUG] PDF Parsed. Keys: {list(report.keys()) if report else 'None'}", flush=True)

    food_name = extract_food_name(report)
    production_date = extract_production_date(report)
    gb_codes = extract_gb_standards(report)
    gb_detail = extract_gb_standards_with_title(report)
    items = extract_inspection_items(report)
    
    print(f"[DEBUG] Extracted Info:", flush=True)
    print(f"  - Food Name: {food_name}", flush=True)
    print(f"  - Prod Date: {production_date}", flush=True)
    print(f"  - GB Codes : {gb_codes}", flush=True)
    print(f"  - Items Count: {len(items) if items else 0}", flush=True)

    # 简单的问题检测逻辑：检查必填字段是否缺失
    issues = []
    if not food_name:
        issues.append("缺少食品名称")
    if not production_date:
        issues.append("缺少生产日期")
    if not gb_codes:
        issues.append("缺少国标号")
    if not items:
        issues.append("未检测到检验项目表格")

    # 验证国标有效性（如果有生产日期和国标编号）
    gb_validation_results = {}
    ragflow_verification = {}  # 新增 RAGFlow 验证结果

    # 加载配置
    config_path = BASE_DIR / "config.local.json"
    config = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    if production_date and gb_codes:
        try:
            gb_validation_results = verify_gb_standards(
                gb_codes=gb_codes,
                production_date=production_date,
                config_path=str(config_path),
                enable_screenshot=True,  # 自动启用截图
                enable_download=True     # 自动启用下载
            )
            print(f"[DEBUG] GB Validation Results: {json.dumps(gb_validation_results, ensure_ascii=False)[:500]}...", flush=True)
            
            # 检查是否有国标验证失败
            failed_gb_codes = []
            for code, validation in gb_validation_results.items():
                if not validation.get("passed", False):
                    failed_gb_codes.append(code)
            
            if failed_gb_codes:
                issues.append(f"国标验证失败: {', '.join(failed_gb_codes)}")
                
            
            # 2. 提取并验证检测方法中的标准
            if items:
                method_codes = set()
                import re
                gb_regex = re.compile(r"GB(?:/T)?\s*\d+(?:\.\d+)?\s*[—\-‑–－]\s*\d{4}")
                
                for item in items:
                    method_str = item.get("method", "")
                    if method_str:
                         # 提取标准号
                         matches = gb_regex.findall(method_str)
                         for code in matches:
                             # 清理标准号中的换行符和多余空格
                             clean_code = re.sub(r'\s+', ' ', code).strip()
                             method_codes.add(clean_code)
                
                if method_codes:
                    # 过滤掉已经验证过的
                    new_codes = [c for c in method_codes if c not in gb_validation_results]
                    if new_codes:
                        print(f"验证检测方法标准: {new_codes}")
                        method_results = verify_gb_standards(
                            gb_codes=new_codes,
                            production_date=production_date,
                            config_path=str(config_path),
                            enable_screenshot=True,  # 方法标准也自动截图
                            enable_download=True     # 方法标准也自动下载
                        )
                        # 合并结果
                        gb_validation_results.update(method_results)
                        
                        # 检查方法标准是否有效
                        for code, validation in method_results.items():
                            if not validation.get("passed", False):
                                status_text = validation.get("status_text", "未知")
                                issues.append(f"检测方法标准 {code} 无效 ({status_text})")

        except Exception as e:
            # 验证失败不影响基本功能
            print(f"国标验证失败: {e}")
            
            # 新增: RAGFlow 检验项目合规性验证
    if food_name and items:
        try:
            from ragflow_verifier import verify_inspection_compliance
            print(f"正在进行 RAGFlow 合规性验证: {food_name}")
            ragflow_verification = verify_inspection_compliance(
                food_name=food_name,
                report_items=items,
                report_gb_codes=gb_codes,  # 传入提取的标准号列表
                config=config
            )
            print(f"[DEBUG] RAGFlow Verification Status: {ragflow_verification.get('status')}", flush=True)
            if ragflow_verification.get('issues'):
                 print(f"[DEBUG] RAGFlow Issues: {ragflow_verification.get('issues')}", flush=True)
            
            # 将 RAGFlow 发现的问题添加到总 issues 中
            if ragflow_verification.get("status") == "fail":
                 rag_issues = ragflow_verification.get("issues", [])
                 for issue in rag_issues:
                     issues.append(f"[合规性] {issue}")
                     
        except Exception as e:
            print(f"RAGFlow 验证失败: {e}")
            import traceback
            traceback.print_exc()

    
    summary = {
        "type": "summary",
        "file_path": str(save_path),
        "food_name": food_name,
        "production_date": production_date,
        "gb_codes": gb_codes,
        "gb_standards": gb_detail,
        "gb_validation": gb_validation_results,
        "ragflow_verification": ragflow_verification, # 添加到返回结果中
        
        # 计算各模块状态
        "standards_compliance_status": "passed" if ragflow_verification.get("status") == "pass" else ("failed" if ragflow_verification.get("status") == "fail" else "unknown"),
        "regulatory_basis_consistent": all(r.get("passed", False) for r in gb_validation_results.values()) if gb_validation_results else None,
        "method_compliance_status": "failed" if ragflow_verification.get("method_issues") else ("passed" if ragflow_verification.get("matched_items") else "unknown"),
        "standard_indicators_status": "failed" if ragflow_verification.get("indicator_issues") else ("passed" if ragflow_verification.get("evidence") else "unknown"),
        "sample_info_status": "unknown", # 暂无自动逻辑
        "label_info_status": "unknown"   # 暂无自动逻辑
    }


    # ── 调试：打印前端渲染所需的关键字段 ──────────────────────────────
    def _debug_print_summary(s):
        SEP = "=" * 60
        print(f"\n{SEP}", flush=True)
        print("[DEBUG SUMMARY] 前端关键字段分析", flush=True)
        print(SEP, flush=True)

        # 1. gb_codes（标准一致性 reportCodes）
        codes = s.get("gb_codes", [])
        print(f"\n[1] gb_codes（报告检验结论中提取的国标，共 {len(codes)} 个）:", flush=True)
        for c in codes:
            print(f"    {c}", flush=True)
        if not codes:
            print('    ⚠ 为空！标准一致性表格将显示"暂无标准依据数据"', flush=True)

        # 2. ragflow matched_items → required_basis（标准一致性 ruleCodes）
        rag = s.get("ragflow_verification", {})
        matched = rag.get("matched_items", [])
        import re as _re
        gb_pat = _re.compile(r"GB(?:\/T|\/Z)?\s*[\d]+[\d.]*(?:-\d{2,4})?", _re.IGNORECASE)
        rule_codes = []
        for item in matched:
            basis = (item.get("required_basis") or "").strip()
            for m in gb_pat.findall(basis):
                rule_codes.append(m.replace(" ", " ").strip())
        rule_codes = list(dict.fromkeys(rule_codes))
        print(f"\n[2] 细则 required_basis 中提取的国标（共 {len(rule_codes)} 个）:", flush=True)
        for c in rule_codes:
            print(f"    {c}", flush=True)

        # 3. 标准一致性：原来会显示哪些行，过滤后保留哪些
        norm = lambda c: _re.sub(r"-\s*\d{4}$", "", c.strip()).strip()
        code_map = {}
        for c in codes:
            k = norm(c)
            code_map.setdefault(k, {"report": None, "rules": None})
            code_map[k]["report"] = c
        for c in rule_codes:
            k = norm(c)
            code_map.setdefault(k, {"report": None, "rules": None})
            code_map[k]["rules"] = c
        print(f"\n[3] 标准一致性表格行分析（过滤前 {len(code_map)} 行，过滤后只保留 report 不为空的）:", flush=True)
        filtered_count = 0
        for k, v in sorted(code_map.items()):
            keep = v["report"] is not None
            tag = "✓ 保留" if keep else "✗ 过滤（报告未引用）"
            if keep:
                filtered_count += 1
            consistent = v["report"] and v["rules"]
            result = "一致" if consistent else ("细则无要求" if v["report"] and not v["rules"] else "报告未引用")
            print(f"    [{tag}] 基码={k}  报告={v['report']}  细则={v['rules']}  → {result}", flush=True)
        print(f"  过滤后剩余 {filtered_count} 行", flush=True)

        # 4. gb_validation（国标文件有效性）
        gb_val = s.get("gb_validation", {})
        print(f"\n[4] gb_validation（共 {len(gb_val)} 个 key）:", flush=True)
        seen_norm = {}
        for code, v in gb_val.items():
            k = norm(code)
            dup_tag = ""
            if k in seen_norm:
                dup_tag = f"  ⚠ 与 '{seen_norm[k]}' 重复（同一基码，前端将去重）"
            else:
                seen_norm[k] = code
            passed = v.get('passed')
            status = v.get('status_text', '未知')
            publish = v.get('publish_date') or '❌未获取'
            implement = v.get('implement_date') or '❌未获取'
            abolish = v.get('abolish_date') or ('❌未获取' if not passed else '无（现行有效）')
            screenshot = v.get('screenshot_path') or '无'
            flag = '✓' if passed else '✗'
            print(f"  {flag} {code}  [{status}]{dup_tag}", flush=True)
            print(f"      发布={publish}  实施={implement}  废止={abolish}", flush=True)
            print(f"      screenshot={screenshot}", flush=True)

        print(f"\n{SEP}\n", flush=True)

    _debug_print_summary(summary)
    # ────────────────────────────────────────────────────────────────

    pdf_url = url_for("static", filename=f"uploads/{safe_name}")

    return {
        "filename": safe_name,
        "pdf_url": pdf_url,
        "summary": summary,
        "items": items,
        "issues": issues,
        "issue_count": len(issues),
        "status": "error" if issues else "success",
    }


@app.route("/api/upload_package_image", methods=["POST"])
def upload_package_image():
    """
    上传并识别包装图片
    
    返回:
    {
        "success": true,
        "data": {
            "product_type": "纯牛奶",
            "standard_code": "GB 25190",
            "production_date": "2024-01-15",
            "shelf_life": "6个月",
            "image_url": "/static/uploads/xxx.jpg"
        }
    }
    """
    try:
        if 'image' not in request.files:
            return jsonify({"success": False, "error": "未提供图片文件"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"success": False, "error": "文件名为空"}), 400
        
        # 保存文件
        safe_name = Path(file.filename).name
        save_path = UPLOAD_DIR / safe_name
        file.save(save_path)
        
        # 初始化OCR引擎
        ocr_engine = get_ocr_engine()
        
        # 识别图片
        package_info = process_package_image(str(save_path), ocr_engine)
        
        # 生成图片URL
        image_url = url_for("static", filename=f"uploads/{safe_name}")
        
        return jsonify({
            "success": True,
            "data": {
                "product_type": package_info.get("product_type"),
                "standard_code": package_info.get("standard_code"),
                "production_date": package_info.get("production_date"),
                "shelf_life": package_info.get("shelf_life"),
                "raw_text": package_info.get("raw_text"),
                "image_url": image_url
            }
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/upload_protocol", methods=["POST"])
def upload_protocol():
    """
    上传检验检测协议(委托单)
    
    返回:
    {
        "success": true,
        "data": {
            "file_url": "/static/uploads/protocols/xxx.pdf",
            "filename": "委托单_20250122.pdf",
            "file_type": "pdf",
            "upload_time": "2025-01-22 11:30:00"
        }
    }
    """
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "未提供文件"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "文件名为空"}), 400
        
        # 创建协议文件目录
        protocol_dir = UPLOAD_DIR / "protocols"
        protocol_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存文件
        safe_name = Path(file.filename).name
        save_path = protocol_dir / safe_name
        file.save(save_path)
        
        # 生成文件URL
        file_url = url_for("static", filename=f"uploads/protocols/{safe_name}")
        
        # 判断文件类型
        file_ext = Path(safe_name).suffix.lower()
        file_type = "pdf" if file_ext == ".pdf" else "image"
        
        from datetime import datetime
        upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return jsonify({
            "success": True,
            "data": {
                "file_url": file_url,
                "filename": safe_name,
                "file_type": file_type,
                "upload_time": upload_time
            }
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/upload_label_info", methods=["POST"])
def upload_label_info():
    """
    上传标签信息
    
    返回:
    {
        "success": true,
        "data": {
            "file_url": "/static/uploads/labels/xxx.jpg",
            "filename": "标签_20250122.jpg",
            "file_type": "image",
            "upload_time": "2025-01-22 11:30:00"
        }
    }
    """
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "未提供文件"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "文件名为空"}), 400
        
        # 创建标签文件目录
        label_dir = UPLOAD_DIR / "labels"
        label_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存文件
        safe_name = Path(file.filename).name
        save_path = label_dir / safe_name
        file.save(save_path)
        
        # 生成文件URL
        file_url = url_for("static", filename=f"uploads/labels/{safe_name}")
        
        # 判断文件类型
        file_ext = Path(safe_name).suffix.lower()
        file_type = "pdf" if file_ext == ".pdf" else "image"
        
        from datetime import datetime
        upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Perform OCR processing
        package_info = {}
        try:
            print(f"Processing label image for OCR: {save_path}")
            ocr_engine = get_ocr_engine()
            package_info = process_package_image(str(save_path), ocr_engine)
            print(f"OCR Success. Extracted: {package_info.keys()}")
            print(f"Product Type: {package_info.get('product_type')}, Standard: {package_info.get('standard_code')}")
        except Exception as e:
            print(f"Error processing package image: {e}")
            import traceback
            traceback.print_exc()
            package_info = {"raw_text": f"Error: {str(e)}"}
        
        return jsonify({
            "success": True,
            "data": {
                "file_url": file_url,
                "filename": safe_name,
                "file_type": file_type,
                "upload_time": upload_time,
                "product_type": package_info.get("product_type"),
                "standard_code": package_info.get("standard_code"),
                "production_date": package_info.get("production_date"),
                "shelf_life": package_info.get("shelf_life"),
                "raw_text": package_info.get("raw_text")
            }
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/query_standards", methods=["POST"])
def query_standards():
    """
    查询食品检验标准（通过 RAGFlow）
    """
    try:
        data = request.get_json()
        food_name = data.get('food_name')

        if not food_name:
            return jsonify({"success": False, "error": "缺少食品名称"}), 400

        config_path = BASE_DIR / "config.local.json"
        config = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

        ragflow_client = get_ragflow_client(config)
        if not ragflow_client:
            return jsonify({"success": False, "error": "RAGFlow 客户端初始化失败，请检查配置"}), 500

        result = ragflow_client.query_inspection_items(food_name)
        return jsonify({"success": True, "data": {"chunks": result, "count": len(result)}})

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/ragflow/query_inspection_items", methods=["POST"])
def ragflow_query_inspection_items():
    """
    查询检验项目表格（步骤3：匹配对应监管细则）
    
    输入:
    {
        "food_name": "婴儿配方食品"
    }
    
    输出:
    {
        "success": true,
        "data": {
            "chunks": [
                {
                    "chunk_id": "...",
                    "content": "...(包含HTML表格)",
                    "similarity": 0.95,
                    "page_number": 155,
                    "source_file": "2025年食品安全监督抽检实施细则.pdf"
                }
            ],
            "count": 5
        }
    }
    """
    try:
        data = request.get_json()
        food_name = data.get('food_name')
        
        if not food_name:
            return jsonify({
                "success": False,
                "error": "缺少食品名称"
            }), 400
        
        # 加载配置
        config_path = BASE_DIR / "config.local.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}
            print(f"配置文件未找到: {config_path}")

        # 获取RAGFlow客户端
        ragflow_client = get_ragflow_client(config)
        
        if not ragflow_client:
             return jsonify({
                "success": False,
                "error": "RAGFlow客户端初始化失败，请检查配置"
            }), 500

        # 查询检验项目
        result = ragflow_client.query_inspection_items(food_name)
        
        # 返回结果 (直接返回 list, 或者封装一下)
        # RAGFlowClient.query_inspection_items 返回的是 list[dict]
        return jsonify({
            "success": True,
            "data": {
                "chunks": result,
                "count": len(result)
            }
        })
            
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/ragflow/query_test_methods", methods=["POST"])
def ragflow_query_test_methods():
    """
    查询检验方法（步骤5：检验方法合法性核查）
    
    输入:
    {
        "food_name": "婴儿配方食品",
        "test_item": "蛋白质"  // 可选
    }
    
    输出:
    {
        "success": true,
        "data": {
            "chunks": [...],
            "count": 5
        }
    }
    """
    try:
        data = request.get_json()
        food_name = data.get('food_name')
        test_item = data.get('test_item')
        
        if not food_name:
            return jsonify({
                "success": False,
                "error": "缺少食品名称"
            }), 400
        
        # 加载配置
        config_path = BASE_DIR / "config.local.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}
        
        ragflow_client = get_ragflow_client(config)
        
        result = ragflow_client.query_test_methods(food_name, test_item)
        
        if result.get("success"):
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/ragflow/query_gb_standards", methods=["POST"])
def ragflow_query_gb_standards():
    """
    查询国家标准（步骤6、7：法律法规/标准有效性核查、标准引用一致性核查）
    
    输入:
    {
        "food_name": "婴儿配方食品",
        "standard_code": "GB 10765-2021"  // 可选
    }
    
    输出:
    {
        "success": true,
        "data": {
            "chunks": [
                {
                    "content": "...(国标文件内容)",
                    "page_number": 20,
                    "source_file": "GB 10765-2021.pdf"
                }
            ],
            "count": 5
        }
    }
    """
    try:
        data = request.get_json()
        food_name = data.get('food_name')
        standard_code = data.get('standard_code')
        
        if not food_name:
            return jsonify({
                "success": False,
                "error": "缺少食品名称"
            }), 400
        
        # 加载配置
        config_path = BASE_DIR / "config.local.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}
        
        ragflow_client = get_ragflow_client(config)
        
        result = ragflow_client.query_gb_standards(food_name, standard_code)
        
        if result.get("success"):
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/ragflow/query_standard_indicators", methods=["POST"])
def ragflow_query_standard_indicators():
    """
    查询标准指标与计量单位（步骤8：标准指标与计量单位核对）
    
    输入:
    {
        "food_name": "婴儿配方食品",
        "test_item": "蛋白质",
        "standard_code": "GB 10765-2021"  // 可选
    }
    
    输出:
    {
        "success": true,
        "data": {
            "chunks": [
                {
                    "content": "...(标准指标范围和计量单位)",
                    "page_number": 25,
                    "source_file": "GB 10765-2021.pdf"
                }
            ],
            "count": 3
        }
    }
    """
    try:
        data = request.get_json()
        food_name = data.get('food_name')
        test_item = data.get('test_item')
        standard_code = data.get('standard_code')
        
        if not food_name or not test_item:
            return jsonify({
                "success": False,
                "error": "缺少食品名称或检验项目"
            }), 400
        
        # 加载配置
        config_path = BASE_DIR / "config.local.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}
        
        ragflow_client = get_ragflow_client(config)
        
        # 使用特定 KB ID 查询国标指标
        kb_id_gb = config.get("RAGFLOW_KB_ID_GB")
        
        result = ragflow_client.query_standard_indicators(
            food_name, test_item, standard_code, kb_id=kb_id_gb
        )
        
        if result.get("success"):
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    React 前端专用上传接口（返回 JSON）
    """
    print("[DEBUG] Received POST request at /api/upload", flush=True)
    files = request.files.getlist("pdfs")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"success": False, "error": "请至少选择一个 PDF 文件"}), 400

    # 过滤出有效的PDF文件
    valid_files = [
        f for f in files
        if f.filename and Path(f.filename).suffix.lower() == ".pdf"
    ]
    if not valid_files:
        return jsonify({"success": False, "error": "没有有效的 PDF 文件"}), 400

    print("[DEBUG] Initializing OCR engine...", flush=True)
    ocr_engine = get_ocr_engine()

    results = []
    for file in valid_files:
        try:
            result = process_single_file(file, ocr_engine)
            results.append(result)
        except Exception as e:
            results.append({
                "filename": file.filename,
                "pdf_url": "",
                "summary": {},
                "items": [],
                "issues": [f"处理失败: {str(e)}"],
                "issue_count": 1,
                "status": "error",
            })

    return jsonify({"success": True, "results": results})


@app.route("/", methods=["GET"])
def index():
    """纯 REST API 后端，前端由 Vite+React 提供"""
    return jsonify({"message": "InspeX API Server. Please access via the React frontend at http://localhost:5173"}), 200


@app.route("/api/process_pdf", methods=["POST"])
def process_pdf():
    """
    动态处理单个上传的PDF文件
    
    返回单条 PDF 的处理结果 JSON
    """
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "未提供文件"}), 400
        
        file = request.files['file']
        if file.filename == '' or Path(file.filename).suffix.lower() != ".pdf":
            return jsonify({"success": False, "error": "无效的 PDF 文件"}), 400
        
        # 初始化OCR引擎
        ocr_engine = get_ocr_engine()
        
        # 处理文件
        result = process_single_file(file, ocr_engine)
        
        return jsonify({
            "success": True,
            "data": result
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/check_gb_validity", methods=["POST"])
def check_gb_validity():
    """
    检查 GB 标准的有效性状态（真实验证接口）
    
    请求格式：
    {
        "gb_codes": ["GB 2763-2021", "GB 5009.1-2016", ...],
        "production_date": "2025-10-25"  // 可选
    }
    
    返回格式：
    {
        "results": [
            {
                "code": "GB 2763-2021",
                "status": "valid",  // "valid" | "obsolete" | "invalid" | "error" | "unknown"
                "status_text": "现行有效",
                "passed": true,
                "publish_date": "2021-03-15",
                "implement_date": "2021-09-15",
                "abolish_date": null,
                "detail_url": "https://down.foodmate.net/...",
                "reasons": []
            },
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        gb_codes = data.get("gb_codes", [])
        production_date = data.get("production_date", "2025-01-01")  # 默认日期
        enable_screenshot = data.get("enable_screenshot", False)
        enable_download = data.get("enable_download", False)
        
        if not gb_codes:
            return jsonify({"error": "Missing gb_codes"}), 400
        
        # 调用验证逻辑
        validation_results = verify_gb_standards(
            gb_codes=gb_codes,
            production_date=production_date,
            config_path=str(BASE_DIR / "config.local.json"),
            enable_screenshot=enable_screenshot,
            enable_download=enable_download
        )
        
        # 格式化返回结果
        results = []
        for code, result in validation_results.items():
            results.append({
                "code": code,
                "status": result.get("status", "unknown"),
                "status_text": result.get("status_text", "未知"),
                "passed": result.get("passed", False),
                "publish_date": result.get("publish_date"),
                "implement_date": result.get("implement_date"),
                "abolish_date": result.get("abolish_date"),
                "detail_url": result.get("detail_url"),
                "screenshot_path": result.get("screenshot_path"),
                "download_path": result.get("download_path"),
                "reasons": result.get("reasons", []),
            })
        
        return jsonify({"results": results})
    
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/download_gb", methods=["POST"])
def download_gb():
    """
    按需下载国标文件

    请求格式：{ "detail_url": "https://...", "gb_number": "2763-2021" }
    返回格式：{ "success": true, "download_url": "/static/downloads/..." }
             或 { "success": false, "error": "..." }
    """
    try:
        data = request.get_json() or {}
        detail_url = data.get("detail_url", "").strip()
        gb_number = data.get("gb_number", "unknown").strip()

        if not detail_url:
            return jsonify({"success": False, "error": "缺少 detail_url"}), 400

        from gb_verifier.html_extractor import fetch_detail_page_content
        from gb_verifier.download import download_standard_from_html

        try:
            html_content = fetch_detail_page_content(detail_url, timeout=30)
        except Exception as e:
            return jsonify({"success": False, "error": f"获取详情页失败：{e}"}), 500

        download_dir = os.path.join("static", "downloads")
        os.makedirs(download_dir, exist_ok=True)

        success, dl_path, err = download_standard_from_html(
            html=html_content,
            gb_number=gb_number,
            download_dir=download_dir,
            referer=detail_url,
        )
        if success:
            download_url = "/" + dl_path.replace(os.sep, "/")
            return jsonify({"success": True, "download_url": download_url})
        else:
            return jsonify({"success": False, "error": err or "下载失败"}), 500

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e),
                        "traceback": traceback.format_exc()}), 500


@app.route("/api/take_screenshot", methods=["POST"])
def take_screenshot():
    """
    按需截取国标详情页截图

    请求格式：{ "detail_url": "https://...", "gb_number": "2763-2021" }
    返回格式：{ "success": true, "screenshot_url": "/static/screenshots/..." }
             或 { "success": false, "error": "..." }
    """
    try:
        data = request.get_json() or {}
        detail_url = data.get("detail_url", "").strip()
        gb_number = data.get("gb_number", "unknown").strip()

        if not detail_url:
            return jsonify({"success": False, "error": "缺少 detail_url"}), 400

        from gb_verifier.screenshot import screenshot_detail_page, PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            return jsonify({
                "success": False,
                "error": "Playwright 未安装。请在 backend 目录执行：\n"
                         ".venv\\Scripts\\pip install playwright\n"
                         ".venv\\Scripts\\python -m playwright install chromium"
            }), 500

        screenshot_dir = os.path.join("static", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)

        success, path, err = screenshot_detail_page(
            detail_url=detail_url,
            gb_number=gb_number,
            screenshot_dir=screenshot_dir,
        )
        if success:
            screenshot_url = "/" + path.replace(os.sep, "/")
            return jsonify({"success": True, "screenshot_url": screenshot_url})
        else:
            return jsonify({"success": False, "error": err or "截图失败"}), 500

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e),
                        "traceback": traceback.format_exc()}), 500


if __name__ == "__main__":
    # Force port 5002 to avoid conflict
    port = int(os.environ.get("PORT", 5002))
    print(f"[DEBUG] Starting Flask server on port {port}...", flush=True)
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
