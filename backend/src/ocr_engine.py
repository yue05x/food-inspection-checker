# 必须在所有 paddle/paddleocr import 之前设置，否则 C++ 后端已完成 oneDNN 初始化
import os
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_use_mkldnn_kernel'] = '0'
os.environ['FLAGS_call_stack_level'] = '2'

from functools import lru_cache
from paddleocr import PaddleOCR


@lru_cache(maxsize=1)
def get_ocr_engine() -> PaddleOCR:
    """Create and cache a global PaddleOCR engine instance.

    使用中文模型+方向分类器。
    enable_mkldnn=False 配合顶部环境变量，双重禁用 Intel oneDNN，
    规避 Windows 上 'OneDnnContext does not have the input Filter' RuntimeError。
    """
    return PaddleOCR(use_angle_cls=True, lang="ch", enable_mkldnn=False, cpu_threads=4)
