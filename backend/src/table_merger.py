"""
跨页表格合并工具模块

用于检测和合并PDF中的跨页表格
"""
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher


class TableMerger:
    """跨页表格合并器"""
    
    def __init__(self, similarity_threshold: float = 0.7):
        """
        初始化表格合并器
        
        Args:
            similarity_threshold: 表头相似度阈值（0-1）
        """
        self.similarity_threshold = similarity_threshold
    
    def detect_cross_page_tables(
        self,
        tables_by_page: Dict[int, List[Dict]]
    ) -> List[List[Dict]]:
        """
        检测跨页表格
        
        Args:
            tables_by_page: 按页码组织的表格字典 {page_num: [table1, table2, ...]}
            
        Returns:
            跨页表格组列表，每组包含需要合并的表格
        """
        cross_page_groups = []
        pages = sorted(tables_by_page.keys())
        
        for i in range(len(pages) - 1):
            current_page = pages[i]
            next_page = pages[i + 1]
            
            # 检查页码是否连续
            if next_page != current_page + 1:
                continue
            
            current_tables = tables_by_page[current_page]
            next_tables = tables_by_page[next_page]
            
            # 检查每个表格对
            for curr_table in current_tables:
                for next_table in next_tables:
                    if self._should_merge(curr_table, next_table):
                        cross_page_groups.append([curr_table, next_table])
        
        return cross_page_groups
    
    def _should_merge(self, table1: Dict, table2: Dict) -> bool:
        """
        判断两个表格是否应该合并
        
        Args:
            table1: 第一个表格
            table2: 第二个表格
            
        Returns:
            是否应该合并
        """
        # 检查列数是否相同
        cols1 = self._get_column_count(table1)
        cols2 = self._get_column_count(table2)
        
        if cols1 != cols2 or cols1 == 0:
            return False
        
        # 检查表头相似度
        header1 = self._get_table_header(table1)
        header2 = self._get_table_header(table2)
        
        if header1 and header2:
            similarity = self._calculate_similarity(header1, header2)
            return similarity >= self.similarity_threshold
        
        return False
    
    def _get_column_count(self, table: Dict) -> int:
        """获取表格列数"""
        if 'html' in table:
            # 从HTML中提取列数
            html = table['html']
            # 简化：计算第一行的<td>或<th>标签数
            import re
            matches = re.findall(r'<t[dh]', html.split('</tr>')[0] if '</tr>' in html else html)
            return len(matches)
        elif 'rows' in table and table['rows']:
            return len(table['rows'][0])
        return 0
    
    def _get_table_header(self, table: Dict) -> Optional[List[str]]:
        """获取表格表头"""
        if 'rows' in table and table['rows']:
            return table['rows'][0]
        elif 'html' in table:
            # 从HTML中提取表头
            import re
            html = table['html']
            # 提取第一行
            first_row_match = re.search(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
            if first_row_match:
                cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', first_row_match.group(1))
                return [self._clean_html(cell) for cell in cells]
        return None
    
    def _clean_html(self, html_text: str) -> str:
        """清理HTML标签"""
        import re
        return re.sub(r'<[^>]+>', '', html_text).strip()
    
    def _calculate_similarity(self, list1: List[str], list2: List[str]) -> float:
        """
        计算两个列表的相似度
        
        Args:
            list1: 第一个列表
            list2: 第二个列表
            
        Returns:
            相似度（0-1）
        """
        if len(list1) != len(list2):
            return 0.0
        
        similarities = []
        for item1, item2 in zip(list1, list2):
            sim = SequenceMatcher(None, str(item1), str(item2)).ratio()
            similarities.append(sim)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def merge_tables(
        self,
        tables: List[Dict],
        remove_duplicate_header: bool = True
    ) -> Dict:
        """
        合并多个表格
        
        Args:
            tables: 要合并的表格列表
            remove_duplicate_header: 是否移除重复的表头
            
        Returns:
            合并后的表格
        """
        if not tables:
            return {}
        
        if len(tables) == 1:
            return tables[0]
        
        # 初始化合并后的表格
        merged = {
            'rows': [],
            'source_pages': [],
            'is_cross_page': True
        }
        
        for idx, table in enumerate(tables):
            # 记录来源页
            if 'page' in table:
                merged['source_pages'].append(table['page'])
            
            # 提取行数据
            rows = table.get('rows', [])
            
            if idx == 0:
                # 第一个表格，添加所有行
                merged['rows'].extend(rows)
            else:
                # 后续表格，可能需要跳过表头
                start_idx = 1 if remove_duplicate_header and rows else 0
                merged['rows'].extend(rows[start_idx:])
        
        # 复制其他元数据
        if 'html' in tables[0]:
            merged['html'] = self._merge_html_tables(tables)
        
        return merged
    
    def _merge_html_tables(self, tables: List[Dict]) -> str:
        """合并HTML格式的表格"""
        import re
        
        merged_html = "<table>"
        
        for idx, table in enumerate(tables):
            html = table.get('html', '')
            
            # 提取所有行
            rows = re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL)
            
            if idx == 0:
                # 第一个表格，添加所有行
                merged_html += ''.join(rows)
            else:
                # 后续表格，跳过表头
                merged_html += ''.join(rows[1:]) if len(rows) > 1 else ''
        
        merged_html += "</table>"
        return merged_html
    
    def validate_merge(self, merged_table: Dict) -> Dict[str, Any]:
        """
        验证合并结果
        
        Args:
            merged_table: 合并后的表格
            
        Returns:
            验证结果
        """
        validation = {
            'is_valid': True,
            'warnings': [],
            'stats': {}
        }
        
        # 检查行数
        row_count = len(merged_table.get('rows', []))
        validation['stats']['total_rows'] = row_count
        
        if row_count == 0:
            validation['is_valid'] = False
            validation['warnings'].append('合并后的表格没有数据行')
        
        # 检查列数一致性
        rows = merged_table.get('rows', [])
        if rows:
            col_counts = [len(row) for row in rows]
            if len(set(col_counts)) > 1:
                validation['warnings'].append(f'列数不一致: {set(col_counts)}')
            validation['stats']['column_count'] = col_counts[0] if col_counts else 0
        
        # 检查来源页
        source_pages = merged_table.get('source_pages', [])
        validation['stats']['source_pages'] = source_pages
        validation['stats']['page_count'] = len(source_pages)
        
        return validation
