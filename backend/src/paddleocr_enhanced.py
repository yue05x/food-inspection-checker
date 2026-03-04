# -*- coding: utf-8 -*-
"""
PaddleOCR 增强版表格提取
集成了三大核心优化：
1. 高分辨率 PDF 转图（3.0x 缩放）
2. 跨页表格合并
3. 符号保留策略
"""
import os
import sys
from pathlib import Path
import fitz  # PyMuPDF
import cv2
import numpy as np
from paddleocr import PaddleOCR

# 添加项目根目录到路径
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from src.table_merger import TableMerger
from src.cell_parser import CellParser


class PaddleOCREnhanced:
    """PaddleOCR 增强版"""
    
    def __init__(self, lang='ch'):
        """初始化 PaddleOCR 引擎"""
        print("Initializing PaddleOCR Enhanced...")
        try:
            # 使用与原代码相同的参数
            self.ocr = PaddleOCR(use_angle_cls=True, lang=lang)
            print("[OK] PaddleOCR initialized")
        except Exception as e:
            print(f"[ERROR] Failed to initialize PaddleOCR: {e}")
            raise
        
        # 初始化辅助模块
        self.merger = TableMerger(similarity_threshold=0.6)
        self.parser = CellParser()
        print("[OK] Helper modules initialized")
    
    def pdf_to_high_res_images(self, pdf_path, zoom=3.0, output_dir=None):
        """
        将 PDF 转换为高分辨率图片
        
        Args:
            pdf_path: PDF 文件路径
            zoom: 缩放倍数，默认 3.0（约 216 DPI）
            output_dir: 输出目录，默认为 None（临时目录）
        
        Returns:
            list: 图片信息列表
        """
        print(f"\nConverting PDF to high-resolution images (zoom: {zoom}x)...")
        
        if output_dir is None:
            output_dir = Path("temp_images")
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        doc = fitz.open(pdf_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # 关键改进：使用高倍缩放矩阵
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # 保存图片
            img_path = output_dir / f"page_{page_num + 1}.png"
            pix.save(str(img_path))
            
            # 转换为 numpy 数组（供 OpenCV 使用）
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            if pix.n == 4:  # RGBA -> BGR
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
            else:  # RGB -> BGR
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            images.append({
                'page_num': page_num + 1,
                'path': str(img_path),
                'array': img_array,
                'width': pix.width,
                'height': pix.height,
                'size_mb': img_path.stat().st_size / 1024 / 1024
            })
            
            print(f"  Page {page_num + 1}: {pix.width}x{pix.height}, "
                  f"{images[-1]['size_mb']:.2f} MB")
        
        print(f"Converted {len(images)} pages")
        return images
    
    def ocr_extract_tables(self, images):
        """
        使用 PaddleOCR 提取表格
        
        Args:
            images: 图片信息列表
        
        Returns:
            dict: 按页码组织的表格数据
        """
        print("\nExtracting tables with PaddleOCR...")
        tables_by_page = {}
        
        for img_data in images:
            page_num = img_data['page_num']
            print(f"\nProcessing page {page_num}...")
            
            # PaddleOCR 识别（3.x 不支持 cls 参数）
            result = self.ocr.ocr(img_data['path'])
            
            if not result or not result[0]:
                print(f"  No text found on page {page_num}")
                tables_by_page[page_num] = []
                continue
            
            # 将 OCR 结果按行聚类
            lines = result[0]
            lines.sort(key=lambda x: (x[0][0][1] + x[0][3][1]) / 2)  # 按 Y 坐标排序
            
            # 行聚类（根据 Y 坐标相近程度）
            rows = []
            if lines:
                current_row = [lines[0]]
                threshold = 25  # 行间距阈值（像素）
                
                for i in range(1, len(lines)):
                    prev_y = (lines[i-1][0][0][1] + lines[i-1][0][3][1]) / 2
                    curr_y = (lines[i][0][0][1] + lines[i][0][3][1]) / 2
                    
                    if abs(curr_y - prev_y) < threshold:
                        current_row.append(lines[i])
                    else:
                        rows.append(current_row)
                        current_row = [lines[i]]
                rows.append(current_row)
            
            # 构建表格 HTML
            table_html = "<table>"
            for row in rows:
                row.sort(key=lambda x: x[0][0][0])  # 行内按 X 坐标排序
                table_html += "<tr>"
                for cell in row:
                    text = cell[1][0]
                    table_html += f"<td>{text}</td>"
                table_html += "</tr>"
            table_html += "</table>"
            
            # 构造表格对象
            table = {
                'page': page_num,
                'html': table_html,
                'bbox': [0, 0, img_data['width'], img_data['height']],
                'rows': self._parse_html_to_rows(table_html)
            }
            
            tables_by_page[page_num] = [table]
            print(f"  Extracted {len(rows)} rows")
        
        return tables_by_page
    
    def merge_cross_page_tables(self, tables_by_page):
        """
        合并跨页表格
        
        Args:
            tables_by_page: 按页码组织的表格数据
        
        Returns:
            list: 合并后的表格列表
        """
        print("\nDetecting cross-page tables...")
        cross_page_groups = self.merger.detect_cross_page_tables(tables_by_page)
        
        final_tables = []
        
        if cross_page_groups:
            print(f"Found {len(cross_page_groups)} cross-page table group(s)")
            for group in cross_page_groups:
                merged = self.merger.merge_tables(group)
                merged['type'] = 'cross_page'
                final_tables.append(merged)
        else:
            print("No cross-page tables detected, using single-page tables")
            for page_num, page_tables in tables_by_page.items():
                for table in page_tables:
                    table['type'] = 'single_page'
                    final_tables.append(table)
        
        return final_tables
    
    def apply_symbol_preservation(self, tables):
        """
        应用符号保留策略
        
        Args:
            tables: 表格列表
        
        Returns:
            list: 处理后的表格列表
        """
        print("\nApplying symbol preservation...")
        
        for table in tables:
            for row in table.get('rows', []):
                # 处理限量值列（保留星号）
                if 'limit' in row:
                    original = row['limit']
                    cleaned = self.parser.parse_limit_value(original)
                    if original != cleaned:
                        print(f"  Cleaned: '{original}' -> '{cleaned}'")
                    row['limit'] = cleaned
        
        return tables
    
    def extract_from_pdf(self, pdf_path, zoom=3.0, output_dir=None):
        """
        完整的表格提取流程
        
        Args:
            pdf_path: PDF 文件路径
            zoom: 缩放倍数
            output_dir: 输出目录
        
        Returns:
            list: 提取的表格列表
        """
        print(f"\n{'='*60}")
        print(f"PaddleOCR Enhanced - Table Extraction")
        print(f"{'='*60}")
        print(f"PDF: {pdf_path}")
        print(f"Zoom: {zoom}x")
        
        # 步骤1：高分辨率转图
        images = self.pdf_to_high_res_images(pdf_path, zoom, output_dir)
        
        # 步骤2：OCR 提取
        tables_by_page = self.ocr_extract_tables(images)
        
        # 步骤3：跨页合并
        final_tables = self.merge_cross_page_tables(tables_by_page)
        
        # 步骤4：符号保留
        final_tables = self.apply_symbol_preservation(final_tables)
        
        print(f"\n{'='*60}")
        print(f"Extraction completed: {len(final_tables)} table(s)")
        print(f"{'='*60}\n")
        
        return final_tables
    
    def _parse_html_to_rows(self, html):
        """将 HTML 表格解析为行列表（简化版）"""
        import re
        rows = []
        tr_pattern = r'<tr>(.*?)</tr>'
        td_pattern = r'<td>(.*?)</td>'
        
        for tr_match in re.finditer(tr_pattern, html, re.DOTALL):
            row_html = tr_match.group(1)
            cells = re.findall(td_pattern, row_html)
            if cells:
                rows.append({'cells': cells})
        
        return rows


def main():
    """示例用法"""
    # 配置
    PDF_PATH = "path/to/your/pdf.pdf"  # 修改为您的 PDF 路径
    OUTPUT_DIR = "output"
    
    # 初始化
    extractor = PaddleOCREnhanced(lang='ch', use_gpu=False)
    
    # 提取表格
    tables = extractor.extract_from_pdf(
        pdf_path=PDF_PATH,
        zoom=3.0,
        output_dir=OUTPUT_DIR
    )
    
    # 打印结果
    for i, table in enumerate(tables, 1):
        print(f"\nTable {i}:")
        print(f"  Type: {table.get('type')}")
        print(f"  Pages: {table.get('source_pages', [table.get('page')])}")
        print(f"  Rows: {len(table.get('rows', []))}")


if __name__ == "__main__":
    main()
