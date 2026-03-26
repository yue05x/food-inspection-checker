"""
食品包装图片处理模块

处理食品包装图片，提取产品信息
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


def extract_product_type(ocr_text: str) -> Optional[str]:
    """
    从 OCR 文本中提取产品类型
    支持同行 / 下一行 / 全角冒号等多种格式
    """
    patterns = [
        # 同行: "产品类型：纯牛奶"
        r'产品类型[：:\s]*([^，！。\n\r\uff0c\uff01\uff0e]+)',
        r'类型[：:\s]*([^，\n\r\uff0c]+)',
        r'品类[：:\s]*([^\n\r]+)',
        r'产品类别[：:\s]*([^\n\r]+)',
        r'产品种类[：:\s]*([^\n\r]+)',
        # 下一行: 标题单独占一行
        r'产品类型[：:\s]*\n\s*([^\n\r]+)',
        r'类型[：:\s]*\n\s*([^\n\r]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, ocr_text)
        if match:
            val = match.group(1).strip().lstrip(':：').strip()
            val = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9个分]+$', '', val)
            if val and len(val) >= 2:
                return val
    return None


def extract_standard_code(ocr_text: str) -> Optional[str]:
    """
    从 OCR 文本中提取产品标准号
    支持 GB 25190 / GB/T 19645 / 跨行等格式
    """
    gb_num = r'([Gg][Bb](?:/[Tt])?[\s.]*\d+(?:[.\-]\d+)*)'
    patterns = [
        # 同行
        r'产品标准[号代]*[：:\s]*' + gb_num,
        r'执行标准[：:\s]*' + gb_num,
        r'标准[号代][：:\s]*' + gb_num,
        r'标准编号[：:\s]*' + gb_num,
        # 下一行
        r'产品标准[号代]*[：:\s]*\n\s*' + gb_num,
        r'执行标准[：:\s]*\n\s*' + gb_num,
    ]
    for pattern in patterns:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            code = re.sub(r'[\s.]+', ' ', match.group(1)).strip().upper()
            # "GB25190" -> "GB 25190"
            code = re.sub(r'^(GB(?:/T)?)(\d)', r'\1 \2', code)
            return code
    # 兜底: 全文直接搜索 GB 开头的标准号
    m = re.search(r'\b' + gb_num + r'\b', ocr_text, re.IGNORECASE)
    if m:
        code = re.sub(r'[\s.]+', ' ', m.group(1)).strip().upper()
        code = re.sub(r'^(GB(?:/T)?)(\d)', r'\1 \2', code)
        return code
    return None


def extract_production_date(ocr_text: str) -> Optional[str]:
    """
    从 OCR 文本中提取生产日期
    """
    patterns = [
        r'生产日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})',
        r'生产日期[：:]\s*(\d{8})',
    ]
    for pattern in patterns:
        match = re.search(pattern, ocr_text)
        if match:
            date_str = match.group(1)
            date_str = re.sub(r'[年月]', '-', date_str)
            date_str = re.sub(r'日', '', date_str)
            return date_str
    return None


def extract_shelf_life(ocr_text: str) -> Optional[str]:
    """
    从 OCR 文本中提取保质期
    """
    patterns = [
        r'保质期[：:]\s*([^\n\r]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, ocr_text)
        if match:
            shelf_life = match.group(1).strip()
            simple_match = re.search(r'(\d+\s*[个]?[月天年])', shelf_life)
            if simple_match:
                return simple_match.group(1)
            return shelf_life
    return None


def process_package_image(image_path: str, ocr_engine) -> dict[str, Any]:
    """
    处理食品包装图片，提取产品信息

    参数:
        image_path: 图片文件路径
        ocr_engine: OCR引擎实例（PaddleOCR）

    返回:
        {
            "product_type": "纯牛奶",
            "standard_code": "GB 25190",
            "production_date": "2024-01-15",
            "shelf_life": "6个月",
            "raw_text": "原始OCR文本"
        }
    """
    # 将图片读为 numpy 数组再传入 PaddleOCR：
    # 直接传路径会触发 PaddleOCR 内部特定的 oneDNN fused_conv2d 算子，
    # 在 Windows 上导致 "OneDnnContext does not have the input Filter" 错误。
    # 传 numpy array 走不同的代码路径，可以绕过该 bug。
    img_array = None
    try:
        import cv2
        img_array = cv2.imread(image_path)
        if img_array is not None:
            # BGR → RGB（PaddleOCR 期望 RGB）
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
    except Exception:
        pass

    if img_array is None:
        # fallback: 用 Pillow
        try:
            from PIL import Image
            import numpy as np
            img_array = np.array(Image.open(image_path).convert("RGB"))
        except Exception:
            pass

    ocr_input = img_array if img_array is not None else image_path
    # cls=False 跳过方向分类器（另一个可能触发 oneDNN 的步骤）
    result = ocr_engine.ocr(ocr_input, cls=False)


    # 提取所有识别文本（每行拼接）
    ocr_text = ""
    if result and len(result) > 0:
        for line in result[0]:
            if line and len(line) >= 2:
                text = line[1][0] if isinstance(line[1], tuple) else line[1]
                ocr_text += text + "\n"

    logger.info("OCR 识别: %d 行文本", len(ocr_text.splitlines()))

    product_info = {
        "product_type": extract_product_type(ocr_text),
        "standard_code": extract_standard_code(ocr_text),
        "production_date": extract_production_date(ocr_text),
        "shelf_life": extract_shelf_life(ocr_text),
        "raw_text": ocr_text.strip()
    }

    logger.info("OCR 提取: 类型=%s, 标准=%s", product_info['product_type'], product_info['standard_code'])
    return product_info
