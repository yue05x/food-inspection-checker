# -*- coding: utf-8 -*-
"""
业务逻辑层 - 数据筛选和处理
从 OCR 提取的原始数据中筛选出符合业务需求的数据
"""
import json
from pathlib import Path
from typing import List, Dict, Any


class DataFilter:
    """数据筛选器 - 负责业务逻辑判断"""
    
    @staticmethod
    def filter_by_keywords(tables: List[Dict], keywords: List[str], column_index: int = 0) -> Dict[str, str]:
        """
        根据关键词筛选数据
        
        Args:
            tables: OCR 提取的原始表格数据
            keywords: 要筛选的关键词列表
            column_index: 要搜索的列索引（默认第一列）
            
        Returns:
            筛选后的数据字典 {名称: 值}
        """
        result = {}
        
        for table in tables:
            rows = table.get('rows', [])
            for row in rows:
                cells = row.get('cells', [])
                if len(cells) > column_index:
                    name = cells[column_index].strip()
                    value = cells[column_index + 1].strip() if len(cells) > column_index + 1 else ""
                    
                    # 检查是否包含关键词
                    if any(keyword in name for keyword in keywords):
                        result[name] = value
        
        return result
    
    @staticmethod
    def filter_by_category(tables: List[Dict], category_name: str, items: List[str]) -> Dict[str, str]:
        """
        根据类别筛选数据
        
        Args:
            tables: OCR 提取的原始表格数据
            category_name: 类别名称（如"水果"）
            items: 要保留的项目列表
            
        Returns:
            筛选后的数据字典
        """
        result = {}
        in_category = False
        
        for table in tables:
            rows = table.get('rows', [])
            for row in rows:
                cells = row.get('cells', [])
                if not cells:
                    continue
                
                name = cells[0].strip()
                value = cells[1].strip() if len(cells) > 1 else ""
                
                # 检测是否进入目标类别
                if name == category_name:
                    in_category = True
                    continue
                
                # 检测是否离开类别
                if in_category and name in ['谷物', '油料和油脂', '蔬菜', '水果', '坚果', '糖料', '饮料类', '食用菌', '调味料', '药用植物']:
                    if name != category_name:
                        in_category = False
                        break
                
                # 在类别中，筛选指定的项目
                if in_category and value:
                    for item in items:
                        if item in name and len(name) <= 10:
                            result[name] = value
                            break
        
        return result


# 使用示例
if __name__ == "__main__":
    print("业务逻辑层示例\n")
    
    # 假设从 OCR 获取了原始数据
    raw_data_file = Path("test_results_deepseek_pure/百草枯表格/百草枯表格_完整原始数据.json")
    
    if raw_data_file.exists():
        with open(raw_data_file, 'r', encoding='utf-8') as f:
            ocr_result = json.load(f)
        
        tables = ocr_result.get('原始表格数据', [])
        
        # 业务逻辑1: 筛选油料和油脂
        filter1 = DataFilter()
        oil_keywords = ['棉籽', '大豆', '葵花籽', '菜籽油', '花生', '油菜籽']
        oil_data = filter1.filter_by_keywords(tables, oil_keywords)
        
        print("筛选结果 - 油料和油脂：")
        for name, value in oil_data.items():
            print(f"  {name}: {value}")
    else:
        print(f"⚠️  请先运行 test_deepseek_ocr_pure.py 生成原始数据")
        print("\n这个脚本展示了如何分离业务逻辑：")
        print("1. OCR 层: 提取原始表格数据")
        print("2. 业务逻辑层: 筛选需要的数据")
