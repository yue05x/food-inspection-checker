"""
单元格内容解析模块

用于解析表格单元格中的多行内容
"""
from typing import List, Dict, Any, Tuple
import re


class CellParser:
    """单元格内容解析器"""
    
    def __init__(self):
        """初始化解析器"""
        pass
    
    def extract_multiline_content(
        self,
        cell_text: str,
        preserve_structure: bool = True
    ) -> List[str]:
        """
        提取单元格中的多行内容
        
        Args:
            cell_text: 单元格文本
            preserve_structure: 是否保持结构（换行符）
            
        Returns:
            文本行列表
        """
        if not cell_text:
            return []
        
        # 按换行符分割
        lines = cell_text.split('\n')
        
        # 清理每行
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:  # 跳过空行
                cleaned_lines.append(line)
        
        return cleaned_lines
    
    def parse_cell_structure(
        self,
        cell_bbox: Tuple[float, float, float, float],
        ocr_results: List[Dict]
    ) -> Dict[str, Any]:
        """
        解析单元格结构
        
        Args:
            cell_bbox: 单元格边界框 (x1, y1, x2, y2)
            ocr_results: OCR识别结果列表
            
        Returns:
            单元格结构信息
        """
        x1, y1, x2, y2 = cell_bbox
        
        cell_structure = {
            'bbox': cell_bbox,
            'text_lines': [],
            'line_count': 0
        }
        
        # 找出在单元格内的所有文本行
        for ocr_result in ocr_results:
            if self._is_inside_cell(ocr_result, cell_bbox):
                text = ocr_result.get('text', '')
                if text.strip():
                    cell_structure['text_lines'].append({
                        'text': text.strip(),
                        'bbox': ocr_result.get('bbox', []),
                        'confidence': ocr_result.get('confidence', 0)
                    })
        
        # 按Y坐标排序（从上到下）
        cell_structure['text_lines'].sort(
            key=lambda x: x['bbox'][1] if x['bbox'] else 0
        )
        
        cell_structure['line_count'] = len(cell_structure['text_lines'])
        
        return cell_structure
    
    def _is_inside_cell(
        self,
        ocr_result: Dict,
        cell_bbox: Tuple[float, float, float, float]
    ) -> bool:
        """
        判断OCR结果是否在单元格内
        
        Args:
            ocr_result: OCR识别结果
            cell_bbox: 单元格边界框
            
        Returns:
            是否在单元格内
        """
        if 'bbox' not in ocr_result:
            return False
        
        text_bbox = ocr_result['bbox']
        if len(text_bbox) < 4:
            return False
        
        # 文本框的中心点
        text_center_x = (text_bbox[0] + text_bbox[2]) / 2
        text_center_y = (text_bbox[1] + text_bbox[3]) / 2
        
        # 检查中心点是否在单元格内
        cx1, cy1, cx2, cy2 = cell_bbox
        return (cx1 <= text_center_x <= cx2 and 
                cy1 <= text_center_y <= cy2)
    
    def preserve_text_order(
        self,
        text_lines: List[Dict]
    ) -> str:
        """
        保持文本顺序，合并为单个字符串
        
        Args:
            text_lines: 文本行列表
            
        Returns:
            合并后的文本
        """
        return '\n'.join([line['text'] for line in text_lines])
    
    def parse_hierarchical_content(
        self,
        cell_text: str
    ) -> Dict[str, Any]:
        """
        解析层次化内容（如类别-子类-具体项）
        
        Args:
            cell_text: 单元格文本
            
        Returns:
            层次结构
        """
        lines = self.extract_multiline_content(cell_text)
        
        structure = {
            'type': 'hierarchical',
            'levels': []
        }
        
        for line in lines:
            # 检测缩进级别（简化版）
            indent_level = len(line) - len(line.lstrip())
            
            structure['levels'].append({
                'text': line.strip(),
                'indent': indent_level,
                'level': indent_level // 2  # 假设每级缩进2个空格
            })
        
        return structure
    
    def extract_food_items(
        self,
        cell_text: str
    ) -> List[str]:
        """
        从单元格中提取食品名称列表
        
        Args:
            cell_text: 单元格文本
            
        Returns:
            食品名称列表
        """
        lines = self.extract_multiline_content(cell_text)
        
        food_items = []
        for line in lines:
            # 移除可能的编号、符号等
            cleaned = re.sub(r'^[\d\.\-\*\s]+', '', line)
            if cleaned:
                food_items.append(cleaned)
        
        return food_items
    
    def merge_cell_content(
        self,
        cells: List[str],
        separator: str = ' '
    ) -> str:
        """
        合并多个单元格的内容
        
        Args:
            cells: 单元格文本列表
            separator: 分隔符
            
        Returns:
            合并后的文本
        """
        cleaned_cells = [cell.strip() for cell in cells if cell and cell.strip()]
        return separator.join(cleaned_cells)
