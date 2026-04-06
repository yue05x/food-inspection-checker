from __future__ import annotations

import json
import os
import re
import sys
import mimetypes
from pathlib import Path

# 修复 Windows 下 Python mimetypes 可能把 PDF 识别为下载流，导致 iframe 无法内嵌直接变下载的问题
mimetypes.add_type('application/pdf', '.pdf')

# 确保当前目录在 Python 路径中，以便导入 verifier2
sys.path.insert(0, str(Path(__file__).parent))

# 禁用 Intel oneDNN/MKL-DNN ---
# 必须在 paddle 任何 C++ 初始化之前设置
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_use_mkldnn_kernel"] = "0"

import logging

# 直接操作 root logger，避免被 paddleocr/werkzeug 的 basicConfig 调用覆盖
_root = logging.getLogger()
_root.setLevel(logging.INFO)
_root.handlers.clear()  # 清除任何已存在的 handler
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)-5s] %(name)s: %(message)s', datefmt='%H:%M:%S'
))
_root.addHandler(_handler)

# 压制噪音库（同时清掉它们自己的 handler，彻底静音）
for _lib in ('urllib3', 'requests', 'werkzeug', 'paddleocr', 'ppocr', 'PIL', 'matplotlib'):
    _lg = logging.getLogger(_lib)
    _lg.setLevel(logging.WARNING)
    _lg.handlers.clear()
    _lg.propagate = True  # 只让 WARNING+ 通过 root handler 输出

logger = logging.getLogger(__name__)

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

# ppocr 的 import 会把 root logger level 抬高到 WARNING，在这里重新断言
logging.getLogger().setLevel(logging.INFO)

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

logger.info("=" * 50)
logger.info("后端已启动，上传目录: %s", UPLOAD_DIR)
logger.info("=" * 50)


def process_single_file(file_storage, ocr_engine):
    """处理单个上传的PDF文件，返回检测结果和状态"""
    safe_name = Path(file_storage.filename).name
    save_path = UPLOAD_DIR / safe_name
    file_storage.save(save_path)
    logger.info("开始处理文件: %s", safe_name)

    report = parse_pdf(str(save_path), ocr_engine=ocr_engine)

    food_name = extract_food_name(report)
    production_date = extract_production_date(report)
    gb_codes = extract_gb_standards(report)
    gb_detail = extract_gb_standards_with_title(report)
    items = extract_inspection_items(report)

    logger.info("提取完成: 食品=%s | 日期=%s | 国标=%d个 | 检验项=%d行",
                food_name or '未识别', production_date or '未识别',
                len(gb_codes or []), len(items or []))

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

    from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _as_completed
    import re as _re

    def _run_gb_validation():
        if not (production_date and gb_codes):
            return {}
        try:
            all_codes = list(gb_codes)
            if items:
                gb_regex = _re.compile(r"GB(?:/T)?\s*\d+(?:\.\d+)?\s*[—\-‑–－]\s*\d{4}")
                method_codes = set()
                for item in items:
                    for code in gb_regex.findall(item.get("method", "")):
                        method_codes.add(_re.sub(r'\s+', ' ', code).strip())
                new_codes = [c for c in method_codes if c not in all_codes]
                if new_codes:
                    logger.info("验证检测方法标准: %s", new_codes)
                    all_codes.extend(new_codes)
            return verify_gb_standards(
                gb_codes=all_codes,
                production_date=production_date,
                config_path=str(config_path),
                enable_screenshot=True,
                enable_download=True
            )
        except Exception as e:
            logger.error("国标验证失败: %s", e)
            return {}

    def _run_ragflow_verification():
        if not (food_name and items):
            return {}
        try:
            from ragflow_verifier import verify_inspection_compliance
            logger.info("RAGFlow 合规验证: %s", food_name)
            return verify_inspection_compliance(
                food_name=food_name,
                report_items=items,
                report_gb_codes=gb_codes,
                config=config
            )
        except Exception as e:
            logger.exception("RAGFlow 验证异常: %s", e)
            return {}

    # 国标验证 与 RAGFlow验证 并行执行
    logger.info("RAGFlow 条件检查: food_name=%r  items=%d条", food_name, len(items or []))
    with _TPE(max_workers=2) as _pool:
        _fut_gb = _pool.submit(_run_gb_validation)
        _fut_rf = _pool.submit(_run_ragflow_verification)
        gb_validation_results = _fut_gb.result()
        ragflow_verification   = _fut_rf.result()

    # 处理国标验证结果
    for code, validation in gb_validation_results.items():
        if not validation.get("passed", False):
            status_text = validation.get("status_text", "未知")
            if code in (gb_codes or []):
                issues.append(f"国标验证失败: {code}")
            else:
                issues.append(f"检测方法标准 {code} 无效 ({status_text})")

    # 处理RAGFlow验证结果
    logger.info("RAGFlow 验证完成: status=%s, issues=%d个",
                ragflow_verification.get('status'),
                len(ragflow_verification.get('issues', [])))
    if ragflow_verification.get("status") == "fail":
        for issue in ragflow_verification.get("issues", []):
            issues.append(f"[合规性] {issue}")

    
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


    logger.info("处理完成: food=%s | gb=%d | matched=%d | issues=%d",
                summary.get('food_name', '?'),
                len(summary.get('gb_codes', [])),
                len(summary.get('ragflow_verification', {}).get('matched_items', [])),
                len(issues))

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
            logger.info("标签图片 OCR: %s", save_path)
            ocr_engine = get_ocr_engine()
            package_info = process_package_image(str(save_path), ocr_engine)
            logger.info("OCR 完成: 类型=%s, 标准=%s",
                        package_info.get('product_type'), package_info.get('standard_code'))
        except Exception as e:
            logger.exception("标签图片处理失败: %s", e)
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
            logger.warning("配置文件未找到: %s", config_path)

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
    logger.info("POST /api/upload")
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

    logger.info("初始化 OCR 引擎...")
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


@app.route("/api/admin/kb_files", methods=["GET"])
def admin_kb_files():
    """
    列出知识库各分类下的真实文件。
    ?tab=rules | standards | reports | labels
    """
    import datetime
    TAB_DIRS = {
        "rules":     os.path.join("static", "files"),
        "standards": os.path.join("static", "downloads"),
        "reports":   os.path.join("static", "uploads"),
        "labels":    os.path.join("static", "uploads", "labels"),
    }
    # reports 只显示 PDF，labels 只显示图片
    TAB_EXTS = {
        "reports": {".pdf"},
        "labels":  {".jpg", ".jpeg", ".png", ".webp", ".bmp"},
    }
    tab = request.args.get("tab", "rules")
    directory = TAB_DIRS.get(tab)
    if not directory:
        return jsonify({"success": False, "error": "未知分类"}), 400

    allowed_exts = TAB_EXTS.get(tab)  # None 表示不过滤

    try:
        os.makedirs(directory, exist_ok=True)
        files = []
        for fname in sorted(os.listdir(directory)):
            fpath = os.path.join(directory, fname)
            if not os.path.isfile(fpath):
                continue
            if allowed_exts:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in allowed_exts:
                    continue
            stat = os.stat(fpath)
            size_kb = stat.st_size / 1024
            size_str = f"{size_kb/1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
            files.append({"name": fname, "size": size_str, "date": mtime})
        return jsonify({"success": True, "files": files, "count": len(files)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/upload_kb_file", methods=["POST"])
def admin_upload_kb_file():
    """
    上传文件到指定知识库分类目录。
    表单字段: file (文件), tab (rules | standards | reports | labels)
    """
    TAB_DIRS = {
        "rules":     os.path.join("static", "files"),
        "standards": os.path.join("static", "downloads"),
        "reports":   os.path.join("static", "uploads"),
        "labels":    os.path.join("static", "uploads", "labels"),
    }
    tab = request.form.get("tab", "rules")
    directory = TAB_DIRS.get(tab)
    if not directory:
        return jsonify({"success": False, "error": "未知分类"}), 400

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"success": False, "error": "未选择文件"}), 400

    try:
        os.makedirs(directory, exist_ok=True)
        save_path = os.path.join(directory, file.filename)
        file.save(save_path)
        return jsonify({"success": True, "filename": file.filename})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    # Force port 5002 to avoid conflict
    port = int(os.environ.get("PORT", 5002))
    logger.info("Flask 启动，端口 %d", port)
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
