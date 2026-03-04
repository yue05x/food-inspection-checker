from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import re

class HtmlTableParser:
    """
    负责解析 RAGFlow 返回的 HTML 表格数据
    """
    
    @staticmethod
    def parse_table(html_content: str) -> List[Dict[str, str]]:
        """
        解析 HTML 表格，返回结构化的数据列表
        每一行转换为一个字典，键为表头
        """
        if not html_content:
            return []

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return []
                
            # 提取表头
            headers = []
            header_row = table.find('tr')
            if header_row:
                # 尝试查找 th
                th_cells = header_row.find_all('th')
                if not th_cells:
                    # 如果没有 th，尝试用第一行 td 作为表头
                    th_cells = header_row.find_all('td')
                
                headers = [HtmlTableParser._clean_text(th.get_text()) for th in th_cells]
            
            # 如果没找到表头，或者是无效表格
            if not headers:
                return []

            results = []
            # 遍历数据行 (跳过第一行如果它是表头)
            rows = table.find_all('tr')
            start_idx = 1 if rows and rows[0] == header_row else 0
            
            for row in rows[start_idx:]:
                cells = row.find_all('td')
                if not cells:
                    continue
                    
                # 处理合并单元格（简单版本：暂不处理复杂的 rowspan/colspan 逻辑，这就需要更复杂的算法）
                # RAGFlow 返回的表格通常已经展平或者比较简单
                # 这里我们假设简单的对应关系
                
                row_data = {}
                for i, cell in enumerate(cells):
                    if i < len(headers):
                        key = headers[i]
                        value = HtmlTableParser._clean_text(cell.get_text())
                        row_data[key] = value
                
                # 只有当行内有实质内容时才添加
                if any(row_data.values()):
                    results.append(row_data)
                    
            return results

        except Exception as e:
            print(f"HTML 表格解析错误: {e}")
            return []

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        清理文本：去除多余空白、换行符
        """
        if not text:
            return ""
        # 替换换行符为空格
        text = text.replace('\n', ' ').replace('\r', ' ')
        # 去除首尾空白
        text = text.strip()
        # 将多个空格合并为一个
        text = re.sub(r'\s+', ' ', text)
        return text

    @staticmethod
    def find_inspection_items(parsed_table: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        从解析后的表格中提取检验项目信息
        需要识别特定的列名，如 "检验项目", "依据法律法规", "检测方法" 等
        """
        items = []
        
        # 定义可能的列名映射
        col_map = {
            "name": ["检验项目", "项目名称", "项目"],
            "basis": ["依据法律法规", "依据法律法规或标准", "检验依据"],
            "method": ["检测方法", "检验方法"]
        }
        
        # 定义需要排除的无效行关键字 (防止将表头说明、备注等误认为项目)
        invalid_keywords = ["注", "备注", "说明", "▲", "★", "类别", "分类", "序号"]
        
        for row in parsed_table:
            item = {}
            found_name = False
            
            # 查找检验项目名称
            item_name_key = None
            for key in row.keys():
                for target in col_map["name"]:
                    if target in key:
                        item_name_key = key
                        break
                if item_name_key:
                    break
            
            if item_name_key:
                raw_name = row[item_name_key]
                raw_name_stripped = raw_name.strip()
                
                # 过滤逻辑 1: 名称太短或太长
                if not raw_name or len(raw_name_stripped) < 2:
                    continue
                if len(raw_name_stripped) > 50:  # 新增:过滤掉长句子和说明文字
                    print(f"DEBUG 筛选: 过滤掉过长项目名称({len(raw_name_stripped)}字符): {raw_name_stripped[:30]}...")
                    continue
                    
                # 过滤逻辑 2: 包含无效关键字 (说明行, 占位符, 目录等)
                # 扩展黑名单 - 添加"补充"相关词汇
                invalid_keywords = [
                    "注", "备注", "说明", "▲", "★", "类别", "分类", "序号", "检测项目",
                    "无", "见下表", "如", "同", "及", "等",  # 单字或连接词
                    "目录", "页码", "页", "表", "附录", "参考", "依据", "标准", "方法", "单位", "限量", "指标",  # 新增
                    "共", "第", "见", "参见", "详见", "参照",  # 新增:引用词
                    "补充", "额外", "蔬菜",  # 新增:过滤"额外补充"、"蔬菜/补充"等
                ]
                
                if any(kw in raw_name for kw in invalid_keywords):
                    print(f"DEBUG 筛选: 过滤掉包含无效关键字的项目: {raw_name_stripped}")
                    continue
                
                # 过滤逻辑 3: 排除纯数字
                if raw_name_stripped.isdigit():
                    continue
                
                # 过滤逻辑 4: 排除纯英文字母序号(如 "a", "b", "c")
                if re.match(r'^[a-zA-Z]$', raw_name_stripped):
                    print(f"DEBUG 筛选: 过滤掉单字母序号: {raw_name_stripped}")
                    continue
                
                # 过滤逻辑 5: 以标准前缀开头的通常是标准依据,不是项目名称
                # 很多时候表格解析错误,把第三列放到了第一列
                std_prefixes = ("GB", "NY", "SN", "DB", "GH", "QB", "SB", "SC", "HG", "LY", "WB", "WM", "T/", "Q/", "JJG", "ISO")
                if raw_name_stripped.upper().startswith(std_prefixes):
                     print(f"DEBUG: Filtered out standard-like item name: {raw_name_stripped}")
                     continue

                # 排除类似 "4.1" 或 "1)" 这样的序号
                if re.match(r'^[\d\.\)\、]+$', raw_name_stripped):
                    continue

                # 排除仅包含特殊符号的
                if not re.search(r'[\u4e00-\u9fa5A-Za-z0-9]', raw_name):
                     continue
                
                # 过滤逻辑 6: 必须包含至少2个中文字符(有效的检验项目名称通常是中文)
                chinese_chars = re.findall(r'[\u4e00-\u9fa5]', raw_name_stripped)
                if len(chinese_chars) < 2:
                    # 例外:允许化学物质英文名称(如 "DDT", "BHC")
                    # 但必须是大写字母且长度在2-10之间
                    if not (raw_name_stripped.isupper() and 2 <= len(raw_name_stripped) <= 10):
                        print(f"DEBUG 筛选: 过滤掉中文字符不足的项目: {raw_name_stripped}")
                        continue

                item["item_name"] = raw_name
                found_name = True
            
            if not found_name:
                continue
                
            # 查找依据
            for key in row.keys():
                for target in col_map["basis"]:
                    if target in key:
                        raw_basis = row[key]
                        # 清理重复的标准号 - 使用简化方法
                        if raw_basis:
                            # split()会自动处理多个空格,返回非空元素列表
                            parts = raw_basis.split()
                            # 去重
                            unique_parts = []
                            seen = set()
                            for part in parts:
                                if part not in seen:
                                    unique_parts.append(part)
                                    seen.add(part)
                            item["standard_basis"] = " ".join(unique_parts)
                        else:
                            item["standard_basis"] = ""
                        break
            
            # 查找方法
            for key in row.keys():
                for target in col_map["method"]:
                    if target in key:
                        item["test_method"] = row[key]
                        break
            
            # 补充默认值
            item.setdefault("standard_basis", "")
            item.setdefault("test_method", "")
            
            items.append(item)
        
        # 后处理：拆分包含多个项目名称的单元格
        # 例如："阿维菌素 哒螨灵" 应该拆分为两个独立项目
        expanded_items = []
        for item in items:
            item_name = item.get("item_name", "")
            
            # 检测是否包含多个项目名称（通过空格分隔，且每个部分长度>=2）
            parts = item_name.split()
            
            # 如果只有一个部分，直接保留
            if len(parts) <= 1:
                expanded_items.append(item)
                continue
            
            # 检查是否所有部分都是有效的项目名称(长度>=2且不是纯数字)
            # 增强过滤:排除括号片段、备注等
            valid_parts = []
            for p in parts:
                # 基本长度检查
                if len(p) < 2 or p.isdigit():
                    continue
                
                # 过滤括号片段(如 "计)"、"量)"、"红）c")
                if p.endswith(')') or p.endswith('）'):
                    # 如果是完整的括号表达式(如 "（以Pb计）")则保留
                    if not (p.startswith('(') or p.startswith('（')):
                        continue
                
                # 过滤以括号开头但不完整的片段(如 "（以Pb")
                if (p.startswith('(') or p.startswith('（')) and not (p.endswith(')') or p.endswith('）')):
                    continue
                
                # 过滤纯符号或单字符
                if len(p.strip('()（）')) < 2:
                    continue
                
                # 过滤备注性文字
                invalid_patterns = [
                    '不检测', '不适用', '视产品', '而定', '以.*为主要原料',
                    '^[a-z]\.$',  # 单字母加点(如 "b.", "c.")
                    '^[a-z]、$',  # 单字母加顿号
                ]
                is_invalid = False
                for pattern in invalid_patterns:
                    if re.search(pattern, p):
                        is_invalid = True
                        break
                if is_invalid:
                    continue
                
                # 通过所有检查,添加到有效列表
                valid_parts.append(p)
            
            if len(valid_parts) <= 1:
                # 只有一个有效部分，保留原项目
                expanded_items.append(item)
            else:
                # 有多个有效部分，拆分为独立项目
                print(f"DEBUG 拆分: 检测到多个项目名称，开始拆分: {valid_parts}")
                
                # 同时尝试拆分标准依据和检测方法
                standard_basis = item.get("standard_basis", "")
                test_method = item.get("test_method", "")
                
                basis_parts = standard_basis.split() if standard_basis else []
                
                # 智能拆分检测方法
                # 检测方法通常包含多个 GB 标准，用空格分隔
                # 例如: "GB 23200.19 GB 23200.20 GB 23200.121"
                method_parts = []
                if test_method:
                    # 按空格分隔,但保留 GB 标准的完整性
                    # 例如: "GB 23200.19" 应该作为一个整体
                    # 匹配 GB/NY/SN 等标准号(可能包含年份)
                    gb_pattern = r'(?:GB|NY|SN|GH)(?:/T)?\s*\d+(?:\.\d+)*(?:-\d{4})?'
                    method_parts = re.findall(gb_pattern, test_method)
                    
                    # 调试输出
                    print(f"DEBUG 拆分: 原始方法='{test_method}'")
                    print(f"DEBUG 拆分: 提取到 {len(method_parts)} 个方法: {method_parts}")
                    print(f"DEBUG 拆分: 项目数量={len(valid_parts)}, 方法数量={len(method_parts)}")
                
                # 如果标准依据的数量与项目名称数量匹配，则一一对应
                # 否则，所有拆分项目共享相同的标准依据
                for i, part in enumerate(valid_parts):
                    # 分配标准依据
                    if len(basis_parts) == len(valid_parts):
                        item_basis = basis_parts[i]
                    else:
                        item_basis = standard_basis
                    
                    # 分配检测方法
                    # 策略1: 如果方法数量 >= 项目数量，尝试分配
                    # 策略2: 否则，共享所有方法
                    if len(method_parts) >= len(valid_parts):
                        # 尝试为每个项目分配对应的方法
                        # 简单策略：平均分配
                        methods_per_item = len(method_parts) // len(valid_parts)
                        start_idx = i * methods_per_item
                        end_idx = start_idx + methods_per_item
                        if i == len(valid_parts) - 1:  # 最后一个项目获取剩余所有方法
                            end_idx = len(method_parts)
                        item_method = " ".join(method_parts[start_idx:end_idx])
                        print(f"DEBUG 拆分: 项目 '{part}' 分配方法: {item_method}")
                    else:
                        # 共享所有方法
                        item_method = test_method
                        print(f"DEBUG 拆分: 项目 '{part}' 共享所有方法（方法数量不足）")
                    
                    new_item = {
                        "item_name": part,
                        "standard_basis": item_basis,
                        "test_method": item_method,
                        # 保留其他字段（如来源信息）
                        **{k: v for k, v in item.items() if k not in ["item_name", "standard_basis", "test_method"]}
                    }
                    expanded_items.append(new_item)

            
        return expanded_items
