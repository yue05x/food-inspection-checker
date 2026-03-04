import re
from typing import List, Dict, Any, Optional
from ragflow_client import get_ragflow_client, RAGFlowClient
from html_table_parser import HtmlTableParser
from item_name_matcher import normalize_item_name, fuzzy_match_item_name

# ======================================================================
# 食品分类映射 - 将具体食品名映射到GB 2763中的大类名称
# ======================================================================
FOOD_CATEGORY_MAPPING = {
    # 瓜类蔬菜
    "黄瓜": ["瓜类蔬菜", "黄瓜"],
    "冬瓜": ["瓜类蔬菜", "冬瓜"],
    "苦瓜": ["瓜类蔬菜", "苦瓜"],
    "南瓜": ["瓜类蔬菜", "南瓜"],
    "西葡芦": ["瓜类蔬菜", "西葡芦"],
    "丝瓜": ["瓜类蔬菜", "丝瓜"],
    "佛手瓜": ["瓜类蔬菜", "佛手瓜"],
    
    # 茄果类蔬菜
    "茄子": ["茄果类蔬菜", "茄子"],
    "番茄": ["茄果类蔬菜", "番茄"],
    "辣椒": ["茄果类蔬菜", "辣椒"],
    
    # 叶菜类
    "白菜": ["叶菜类蔬菜", "白菜"],
    "菠菜": ["叶菜类蔬菜", "菠菜"],
    "生菜": ["叶菜类蔬菜", "生菜"],
    "油菜": ["叶菜类蔬菜", "油菜"],
    "芥菜": ["叶菜类蔬菜", "芥菜"],
    
    # 豆类蔬菜
    "豆角": ["豆类蔬菜", "豆角"],
    "豌豆": ["豆类蔬菜", "豌豆"],
    "荱豆": ["豆类蔬菜", "荱豆"],
    
    # 根茎类
    "萝卜": ["根茎类和薯苋类蔬菜", "萝卜"],
    "胡萝卜": ["根茎类和薯苋类蔬菜", "胡萝卜"],
    "土豆": ["根茎类和薯苋类蔬菜", "土豆"],
}

def get_food_categories(food_name: str) -> List[str]:
    """
    获取食品的所有可能名称(包括大类)
    返回顺序: [具体名称, 大类名称]
    
    例如: get_food_categories("黄瓜") -> ["黄瓜", "瓜类蔬菜"]
    """
    if food_name in FOOD_CATEGORY_MAPPING:
        # 返回大类和具体名称，大类在前
        return [FOOD_CATEGORY_MAPPING[food_name][0], food_name]
    # 如果没有映射,返回原名称
    return [food_name]

# ======================================================================

# ==================== Five-Layer Filtering Helpers ====================

def build_optimized_query(food_name: str, query_type: str = "inspection") -> str:
    """
    Layer 0: Query 约束 - 构建优化的查询语句
    
    Args:
        food_name: 食品名称
        query_type: 查询类型 (inspection/basis/method)
    
    Returns:
        优化的查询语句
    """
    if query_type == "inspection":
        # 使用结构化查询,明确指定要查找的内容
        return f"{food_name} 检验项目表 必检项目 限量指标"
    elif query_type == "basis":
        return f"{food_name} 依据法律法规 判定依据 标准"
    elif query_type == "method":
        return f"{food_name} 检测方法 检验方法 国标方法"
    
    return food_name

def check_structural_validity(content: str, food_name: str, require_strict: bool = False) -> bool:
    """
    Layer 2: 关键词/结构存在性过滤
    
    Args:
        content: 内容
        food_name: 食品名称
        require_strict: 是否需要严格检查
    
    Returns:
        是否通过结构验证
    """
    # Level 1: 必须包含食品名称
    if food_name not in content:
        return False
    
    # Level 2: 必须包含项目相关关键词
    project_keywords = ["检验项目", "检测项目", "项目名称", "必检项"]
    has_project_keyword = any(kw in content for kw in project_keywords)
    
    if not has_project_keyword:
        if require_strict:
            return False
    
    # Level 3: 应该包含表格标识
    table_indicators = ["<table", "<td", "表格"]
    has_table = any(kw in content for kw in table_indicators)
    
    # 如果需要严格检查,必须有表格
    if require_strict and not has_table:
        return False
    
    return True

def _extract_limit_value(limit_text: str, food_name: str, item_name: str) -> str:
    """
    从限量表格文本中提取具体食品的限量值
    GB 2763 表格典型结构:
      列1: "食品和饲料品种" / "食品名称"  -> 可能写大类（如"瓜类蔬菜"）
      列2: "最大残留限量（mg/kg）"       -> 单位在括号里，数值在数据行
    路径A: HTML 表格（RAGFlow 通常返回此格式）
    路径B: 纯文本（降级）
    """
    import re

    if not limit_text or not food_name:
        return "未找到限量值"

    food_categories = get_food_categories(food_name)
    print(f"  [extract] 食品分类: {food_categories}")
    print(f"  [extract] 内容前300字: {repr(limit_text[:300])}")

    # ─── 路径 A: HTML 表格解析 ───
    if "<table" in limit_text.lower() or "<td" in limit_text.lower():
        try:
            rows = HtmlTableParser.parse_table(limit_text)   # List[Dict[str, str]]
            print(f"  [extract-HTML] {len(rows)} 行, 表头: {list(rows[0].keys()) if rows else '无'}")

            if rows:
                headers = list(rows[0].keys())
                food_col = None
                limit_col = None
                unit = "mg/kg"

                for h in headers:
                    h_s = h.strip()
                    if any(k in h_s for k in ["食品", "饲料", "品种", "作物", "名称"]):
                        if food_col is None:
                            food_col = h
                    if any(k in h_s for k in ["最大残留限量", "最大限量", "限量"]):
                        limit_col = h
                        m = re.search(r'[（(]([^）)]+)[）)]', h_s)
                        if m:
                            unit = m.group(1).strip()

                print(f"  [extract-HTML] 食品列='{food_col}', 限量列='{limit_col}', 单位='{unit}'")

                for row in rows:
                    food_val = (row.get(food_col, "") if food_col
                                else next(iter(row.values()), ""))
                    for cat in food_categories:
                        if cat and cat in food_val:
                            limit_val = (row.get(limit_col, "").strip() if limit_col else "")
                            if limit_val and limit_val not in {"-", "—", "", "/", "——", "*"}:
                                print(f"  [extract-HTML] 匹配: '{cat}' in '{food_val}' -> {limit_val} {unit}")
                                return f"{limit_val} {unit}"

                # 全行文本回退
                print("  [extract-HTML] 列匹配失败，全行搜索")
                for row in rows:
                    row_text = " ".join(str(v) for v in row.values())
                    for cat in food_categories:
                        if cat and cat in row_text:
                            nums = re.findall(r'(\d+\.?\d*)', row_text)
                            if nums:
                                print(f"  [extract-HTML] 全行: '{cat}' -> {nums[0]} {unit}")
                                return f"{nums[0]} {unit}"
        except Exception as e:
            print(f"  [extract-HTML] 异常: {e}")

    # ─── 路径 B: 纯文本解析（降级）───
    print("  [extract-TEXT] 纯文本解析")
    lines = limit_text.split('\n')
    unit = "mg/kg"
    for line in lines:
        if "最大残留限量" in line or "最大限量" in line:
            m = re.search(r'[（(]([^）)]+)[）)]', line)
            if m:
                unit = m.group(1).strip()
                break

    food_line = None
    for cat in food_categories:
        for line in lines:
            if cat and cat in line:
                food_line = line
                break
        if food_line:
            break

    if not food_line:
        numbers = re.findall(r'(\d+\.?\d*)\s*(mg/kg|ppm|%|μg/kg)', limit_text)
        if numbers:
            return f"{numbers[0][0]} {numbers[0][1]}"
        return "未找到限量值"

    pattern = r'([\u2264<]?\s*\d+\.?\d*)\s*(mg/kg|ppm|%|μg/kg|mg/L)?'
    matches = re.findall(pattern, food_line)
    if matches:
        value, found_unit = matches[0]
        value = value.strip()
        if found_unit:
            unit = found_unit.strip()
        if value.startswith(('\u2264', '<')):
            value = value.lstrip('\u2264<').strip()
            return f"\u2264{value} {unit}"
        return f"{value} {unit}"

# ======================================================================


def verify_inspection_compliance(
    food_name: str, 
    report_items: List[Dict[str, Any]], 
    report_gb_codes: List[str], # 新增：报告中提取的标准号
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    验证检验项目合规性 (使用 RAGFlow)
    
    1. 通过 RAGFlow 查询细则中该食品的检验项目
    2. 解析返回的 HTML 表格
    3. 与报告中的检验项目进行比对
    """
    
    # 1. 初始化结果
    result = {
        "status": "pass",  # pass, fail, warning, unknown
        "issues": [],
        "evidence": [],    # RAGFlow 返回的佐证 (原文片段, 页码)
        "missing_items": [], # 细则有但报告没有
        "extra_items": [],   # 报告有但细则没有
        "matched_items": []  # 匹配的项目
    }
    
    if not food_name:
        result["status"] = "unknown"
        result["issues"].append("缺少食品名称，无法查询细则")
        return result
        
    client = get_ragflow_client(config)
    if not client:
        result["status"] = "unknown"
        result["issues"].append("RAGFlow 客户端未能初始化")
        return result

    # 2. 查询 RAGFlow
    # Layer 0: Query 约束 - 使用优化的查询语句
    optimized_query = build_optimized_query(food_name, "inspection")
    print(f"DEBUG Layer0: 优化查询 = '{optimized_query}'")
    
    query_result = client.query_inspection_items(food_name, custom_query=optimized_query)
    if not query_result:
        result["status"] = "warning"
        result["issues"].append(f"未在细则中找到关于'{food_name}'的检验要求")
        return result
    
    print(f"DEBUG Layer0: RAGFlow 返回 {len(query_result)} 个 chunks")
        
    # 3. 筛选和解析 RAGFlow 结果
    required_items = []
    filtered_chunks = []  # 存储筛选后的 chunks
    
    # Layer 1: 向量相似度硬门槛
    SIMILARITY_THRESHOLD_HARD = 0.4  # 硬门槛,低于此值直接丢弃
    SIMILARITY_THRESHOLD_SOFT = 0.25  # 软门槛,需要通过后续检查
    
    layer1_passed = []
    for chunk in query_result:
        content = chunk.get("content", "")
        score = chunk.get("score", 0)
        
        if not content:
            continue
        
        # 硬门槛检查
        if score >= SIMILARITY_THRESHOLD_HARD:
            chunk["require_strict"] = False
            layer1_passed.append(chunk)
        elif score >= SIMILARITY_THRESHOLD_SOFT:
            # 软门槛:需要通过严格的 Layer 2 检查
            chunk["require_strict"] = True
            layer1_passed.append(chunk)
        else:
            # 低于软门槛,直接丢弃
            print(f"DEBUG Layer1: 过滤低分 chunk (score={score:.3f})")
            continue
    
    print(f"DEBUG Layer1: {len(query_result)} -> {len(layer1_passed)} chunks")
    
    # Layer 2: 结构存在性过滤
    layer2_passed = []
    for chunk in layer1_passed:
        content = chunk.get("content", "")
        score = chunk.get("score", 0)
        require_strict = chunk.get("require_strict", False)
        
        # 结构有效性检查
        if check_structural_validity(content, food_name, require_strict):
            layer2_passed.append(chunk)
        else:
            print(f"DEBUG Layer2: 过滤结构无效 chunk (score={score:.3f}, strict={require_strict})")
            continue
    
    print(f"DEBUG Layer2: {len(layer1_passed)} -> {len(layer2_passed)} chunks")
    
    # 收集证据和解析表格
    for chunk in layer2_passed:
        content = chunk.get("content", "")
        page_num = chunk.get("page_num", 1)
        score = chunk.get("score", 0)
        
        # 收集证据
        filtered_chunks.append({
            "content": content,
            "chunk_id": chunk.get("chunk_id"),
            "score": score,
            "page_num": page_num,
            "doc_name": chunk.get("doc_name", "")
        })
        
        # 解析表格
        parsed_tables = HtmlTableParser.parse_table(content)
        items = HtmlTableParser.find_inspection_items(parsed_tables)
        
        # 为每个提取的项目添加来源信息
        for item in items:
            item["source_page"] = page_num
            item["source_chunk_id"] = chunk.get("chunk_id")
            item["source_score"] = score
            
        required_items.extend(items)
    
    # 调试输出:显示解析出的检测项目
    print(f"DEBUG: 从 RAGFlow 解析出 {len(required_items)} 个检测项目(去重前)")
    
    # 后处理:去重和筛选
    seen_names = set()
    filtered_items = []
    for item in required_items:
        name = item.get("item_name", "")
        if not name:
            continue
        
        # 完全重复去重
        if name in seen_names:
            print(f"DEBUG 去重: 过滤掉重复项目: {name}")
            continue
        seen_names.add(name)
        
        # 最后一次验证:过滤明显无效的项目
        if len(name) > 50 or len(name) < 2:
            print(f"DEBUG 去重: 过滤掉长度异常的项目: {name}")
            continue
        
        filtered_items.append(item)
    
    required_items = filtered_items
    print(f"DEBUG: 去重和筛选后剩余 {len(required_items)} 个检测项目")
    
    for idx, item in enumerate(required_items[:5]):  # 只显示前5个
        print(f"  [{idx+1}] 项目名称: {item.get('item_name', 'N/A')}")
        print(f"      标准依据: {item.get('standard_basis', 'N/A')}")
        print(f"      检测方法: {item.get('test_method', 'N/A')}")
    if len(required_items) > 5:
        print(f"  ... 还有 {len(required_items) - 5} 个项目")
    
    # 统一依据标准: 收集所有不同的依据，移除不完整的片段
    all_bases = set()
    for item in required_items:
        basis = item.get("standard_basis", "").strip()
        if basis:
            all_bases.add(basis)
    
    # 智能过滤: 移除是其他basis子串的basis
    # 例如: {"GB", "2763", "GB 2763"} -> {"GB 2763"}
    import re
    filtered_bases = []
    for basis in all_bases:
        # 检查是否是完整的标准号 (GB + 数字)
        if re.match(r'GB\s*\d+', basis, re.IGNORECASE):
            # 是完整标准号，保留
            filtered_bases.append(basis)
        else:
            # 不完整，检查是否是其他basis的子串
            is_substring = False
            for other in all_bases:
                if other != basis and basis in other:
                    is_substring = True
                    print(f"DEBUG 依据过滤: 移除子串 '{basis}' (存在完整版本 '{other}')")
                    break
            if not is_substring:
                # 不是子串但也不是完整标准号，警告但保留
                print(f"WARNING: 不完整的依据标准: '{basis}'")
                filtered_bases.append(basis)
    
    # 统一所有项目的 required_basis
    unified_basis = " ".join(sorted(filtered_bases)) if filtered_bases else ""
    print(f"DEBUG: 统一依据标准: {list(all_bases)} -> '{unified_basis}'")
    
    for item in required_items:
        item["required_basis"] = unified_basis

    
    # 将筛选后的 chunks 添加到证据中
    result["evidence"] = filtered_chunks
    result["evidence_count"] = len(filtered_chunks)
    result["evidence_pages"] = list(set(chunk["page_num"] for chunk in filtered_chunks))  # 去重的页码列表

    if not required_items:
        result["status"] = "warning"
        result["issues"].append(f"找到 {len(query_result)} 个相关文档,但筛选后未能提取到有效检验项目")
        result["issues"].append(f"筛选条件: 相似度>{SIMILARITY_THRESHOLD}, 包含'{food_name}', 包含'检验项目'")
        return result

    # 4. 比对逻辑 - 使用模糊匹配
    # 不再使用简单的集合比对,而是逐项进行模糊匹配
    missing = []
    extra = []
    matched = []
    method_issues = []  # 方法不匹配的问题
    basis_issues = []   # 判定依据不匹配的问题
    
    # 构建映射方便查找
    report_map = {}
    for item in report_items:
        name = item.get("item", "") or item.get("name", "") or item.get("item_name", "")
        if name:
            report_map[name] = item
    
    req_map = {}
    for item in required_items:
        name = item.get("item_name", "")
        if name:
            req_map[name] = item
    
    # 检查必检项目是否在报告中 - 使用模糊匹配
    for req_name, req_item in req_map.items():
        # 尝试在报告中找到匹配项 (使用模糊匹配)
        matched_report_item = None
        matched_report_name = None
        
        for report_name, report_item in report_map.items():
            if fuzzy_match_item_name(report_name, req_name):
                matched_report_item = report_item
                matched_report_name = report_name
                break
        
        if matched_report_item:
            # 找到匹配项
            match_info = {
                "name": req_name,
                "report_name": matched_report_name,  # 添加报告中的实际名称
                "report_method": matched_report_item.get("method", ""),
                "required_method": req_item.get("test_method", ""),
                "required_basis": req_item.get("standard_basis", ""),
                "source_page": req_item.get("source_page"),       # 细则来源页码
                "source_chunk_id": req_item.get("source_chunk_id"),  # 细则来源 chunk
            }
            matched.append(match_info)
            
            # 1. 验证检测方法
            rep_method = _normalize_name(match_info["report_method"])
            req_method_raw = match_info["required_method"] or ""
            
            if req_method_raw and rep_method:
                 if not _fuzzy_match_method(rep_method, req_method_raw):
                     method_issues.append({
                         "item": req_name,
                         "expected": req_method_raw,
                         "actual": matched_report_item.get("method", ""),
                         "issue": "检测方法不一致"
                     })
                     
            # 2. 验证判定依据 (细则要求的标准 vs 报告引用的标准)
            # 用户要求: "细则中检验项目表格中依据法律法规或标准一列中的国标文件...以及上传的食品报告中的检验结论中的国标文件是否是...一列中的国标文件"
            # 我们检查 match_info["required_basis"] 是否包含在 report_gb_codes 中
            # 或者，检查 report_item 所在的上下文是否引用了该标准 (OCR 提取的 item 通常不带 basis，但是整个报告有 standards)
            
            req_basis_raw = match_info["required_basis"] or ""
            if req_basis_raw:
                # 检查报告的全局标准列表中是否包含此依据
                # 简化逻辑: 只要 report_gb_codes 中有一个出现在 req_basis_raw 中，或者 req_basis_raw 出现在某个 report_gb_code 中
                found_basis = False
                for gb in report_gb_codes:
                    if _fuzzy_match_method(gb, req_basis_raw): # 复用模糊匹配逻辑 (都是 GB 号比较)
                         found_basis = True
                         break
                
                if not found_basis:
                    # 再试一下反向：细则要求 GB 2760，报告里有 GB 2760-2014
                    pass
                
                # 如果没找到，记录问题 (注意: 有些细则写的是 "产品明示标准"，这种比较难校验，先跳过)
                if not found_basis and "明示" not in req_basis_raw and "企业标准" not in req_basis_raw:
                     print(f"DEBUG 判定依据: 项目'{req_name}' 依据不匹配 - 细则要求:{req_basis_raw}, 报告引用:{report_gb_codes}")
                     basis_issues.append({
                         "item": req_name,
                         "expected": req_basis_raw,
                         "actual": str(report_gb_codes),
                         "issue": "判定依据未在报告中引用"
                     })
                else:
                    if found_basis:
                        print(f"DEBUG 判定依据: 项目'{req_name}' 依据匹配成功 - 细则要求:{req_basis_raw}, 报告引用:{report_gb_codes}")
            
        else:
            missing.append(req_name)
    
    # ... (extra checks) ...
    
    # 检查报告中多余的项目 (非细则要求的) - 使用模糊匹配
    for rep_name in report_map:
        # 检查是否有任何细则项目与此报告项目匹配
        is_matched = False
        for req_name in req_map:
            if fuzzy_match_item_name(rep_name, req_name):
                is_matched = True
                break
        
        if not is_matched:
            extra.append(rep_name)
    
    result["missing_items"] = missing
    result["extra_items"] = extra
    result["matched_items"] = matched
    result["method_issues"] = method_issues
    result["basis_issues"] = basis_issues
    
    # 3. 验证标准指标合理性 (新增)
    indicator_issues = []
    
    # 查询所有有检验结果的项目（不再限制为前3个）
    # 使用 report_name 而不是 name 来查找 report_map
    items_to_check = [m for m in matched if m.get("report_name") and report_map.get(m["report_name"], {}).get("value")]
    
    # 调试输出：显示要查询的匹配项目
    print(f"DEBUG: 准备查询 {len(items_to_check)} 个匹配项目的标准限量 (并行)")
    for idx, m in enumerate(items_to_check[:5]):  # 调试输出只显示前5个
        print(f"  [{idx+1}] 细则名称: {m.get('name', 'N/A')}")
        print(f"      报告名称: {m.get('report_name', 'N/A')}")
        print(f"      标准依据: {m.get('required_basis', 'N/A')}")

    
    def _query_limit_worker(match_item):
        """Worker function for threading"""
        try:
            item_name = match_item["name"]  # 细则中的名称
            report_name = match_item["report_name"]  # 报告中的实际名称
            report_item = report_map[report_name]  # 使用报告中的名称查找
            
            # Restore missing definition
            query_code = match_item["required_basis"]
            if not query_code and report_gb_codes:
                query_code = report_gb_codes[0]
            
            if query_code:
                # 实施 "3步检索策略" (实为 2步+验证，模拟用户逻辑)
                # 逻辑: 1. 定位项目表格上下文 2. 查找食品限量数值
                
                kb_id_gb = config.get("RAGFLOW_KB_ID_GB")  # 获取国标知识库ID
                query_code = "GB 2763"
                
                # ========================================
                # 新增: Step 0 - 从目次查找表格编号 (Table Number from TOC)
                # ========================================
                print(f"\n{'='*60}")
                print(f"[Step 0] 查询目次: {item_name}")
                print(f"{'='*60}")
                toc_query = f"{item_name} 目次"  # 查询目次
                print(f"  查询词: '{toc_query}'")
                toc_chunks = client.query(toc_query, dataset_ids=[kb_id_gb], page_size=10)
                
                print(f"  返回结果: {len(toc_chunks) if toc_chunks else 0} 个 chunks")
                if toc_chunks:
                    for idx, chunk in enumerate(toc_chunks[:3]):  # 只显示前3个
                        print(f"    [{idx+1}] 页码:{chunk.get('page_num', 'N/A')} | 分数:{chunk.get('score', 0):.4f} | 内容:{chunk.get('content', '')[:100]}...")
                
                table_number = None
                if toc_chunks:
                    # 从目次提取表格编号: "4.121 毒死蜱" -> 表121
                    # 注意：目次行末的页码是"目次本身的页码"，不是表格所在页，不可用
                    import re
                    for chunk in toc_chunks:
                        content = chunk.get("content", "")
                        page_num = chunk.get("page_num", 0)
                        
                        # 只处理目次页（放宽到前20页）
                        if not (1 <= page_num <= 20):
                            continue
                        
                        # 匹配 "4.X pesticide_name"，提取 X 作为表格编号
                        pattern = rf"4\.(\d+)\s+{re.escape(item_name)}"
                        match = re.search(pattern, content)
                        if not match:
                            # 允许名称前不强制空格
                            pattern2 = rf"4\.(\d+)\s*{re.escape(item_name)}"
                            match = re.search(pattern2, content)
                        if match:
                            table_number = match.group(1)
                            print(f"\n  ✔ 从目次找到: 4.{table_number} {item_name} -> 表{table_number} (目次位于第{page_num}页,非表格页)")
                            print(f"      匹配内容: {content[:150]}")
                            break
                
                if not table_number:
                    print(f"\n  ⚠ 未在目次中找到 {item_name}，将直接用农药名查询")
                
                # ========================================
                # Step 1: 搜索「表X」定位最大残留限量表格
                # ========================================
                print(f"\n{'='*60}\n[Step 1] 查询表格: {item_name}\n{'='*60}")
                
                if table_number:
                    context_query = f"表{table_number}"
                    print(f"  查询词: '{context_query}'")
                else:
                    context_query = f"{item_name} 最大残留限量"
                    print(f"  查询词: '{context_query}'（未找到表号，用农药名）")
                
                context_chunks_raw = client.query(context_query, dataset_ids=[kb_id_gb], page_size=20)
                print(f"  原始返回: {len(context_chunks_raw) if context_chunks_raw else 0} 个 chunks")
                if context_chunks_raw:
                    for idx, c in enumerate(context_chunks_raw[:5]):
                        print(f"    [{idx+1}] Doc:{c.get('doc_name','N/A')} | 页:{c.get('page_num','N/A')} | 分:{c.get('score',0):.4f} | {c.get('content','')[:80]}...")
                
                # 只保留 GB 2763 文件的 chunk
                context_chunks = [
                    c for c in (context_chunks_raw or [])
                    if "GB 2763" in c.get("doc_name", "") or "GB2763" in c.get("doc_name", "")
                ]
                print(f"  国标过滤: {len(context_chunks_raw or [])} -> {len(context_chunks)} chunks")
                
                # ========================================
                # Step 2: 选出最佳 chunk
                # 优先：包含农药名 → 兜底第一个
                # chunk 的 page_num 就是表格所在真实页
                # ========================================
                print(f"\n[Step 2] 选最佳 chunk: {item_name}")
                best_chunk = None
                
                # ① 包含农药名的 chunk
                for chunk in context_chunks:
                    if item_name in chunk.get("content", ""):
                        best_chunk = chunk
                        print(f"  ✔ 找到含农药名的 chunk，页码: {chunk.get('page_num','?')}")
                        break
                
                # ② 兜底：分数最高（第一个）
                if not best_chunk and context_chunks:
                    best_chunk = context_chunks[0]
                    print(f"  ⚠ 兜底第一个 chunk，页码: {best_chunk.get('page_num','?')}")

                if best_chunk:
                    limit_text = best_chunk.get("content", "")
                    
                    # 提取具体的限量值
                    print(f"\n=== 提取限量值: {item_name} ===")
                    print(f"  食品名: {food_name}")
                    print(f"  食品分类: {get_food_categories(food_name)}")
                    print(f"  表格内容预览: {limit_text[:200]}...")  # 只打印前200字符
                    
                    extracted_limit = _extract_limit_value(limit_text, food_name, item_name)
                    print(f"  提取结果: {extracted_limit}")
                    print(f"  文档: {best_chunk.get('doc_name', 'N/A')}")
                    print(f"  页码: {best_chunk.get('page_num', 'N/A')}")
                    print("="*50)
                    
                    # 提取 limit_text 中的数值进行比对
                    limit_issue = _check_limit_compliance(report_item.get("value"), limit_text)
                    
                    return {
                        "type": "success",
                        "item_name": item_name,
                        "limit_text": limit_text,  # 完整文本供调试
                        "extracted_limit": extracted_limit,  # 提取的限量值
                        "best_chunk": best_chunk,
                        "limit_issue": limit_issue
                    }
            return None
        except Exception as e:
            print(f"Error checking limit for {match_item.get('name')}: {e}")
            return None

    # Use ThreadPoolExecutor for parallel queries
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    evidence_list = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_match = {executor.submit(_query_limit_worker, m): m for m in items_to_check}
        for future in as_completed(future_to_match):
            res = future.result()
            if res and res["type"] == "success":
                # 添加证据到列表 - 设置 type='indicator'
                evidence_list.append({
                    "type": "indicator",  # 添加证据类型标记
                    "item": res["item_name"],
                    "content": res["limit_text"],  # 完整表格文本
                    "extracted_limit": res.get("extracted_limit", "未提取"),  # 提取的限量值
                    "chunk_id": res["best_chunk"].get("chunk_id"),
                    "page_num": res["best_chunk"].get("page_num"),
                    "doc_name": res["best_chunk"].get("doc_name", "")
                })
                # 如果有问题，添加到问题列表
                if res.get("limit_issue"):
                    indicator_issues.append(f"{res['item_name']}: {res['limit_issue']}")

    # Merge evidence
    result["evidence"].extend(evidence_list)
    result["indicator_issues"] = indicator_issues

    if missing:
        result["status"] = "fail"
        result["issues"].append(f"缺少必检项目: {', '.join(missing[:5])}" + ("..." if len(missing)>5 else ""))
        
    if method_issues:
        if result["status"] == "pass": result["status"] = "warning"
        result["issues"].append(f"存在检测方法不一致 ({len(method_issues)}项)")

    if basis_issues:
         if result["status"] == "pass": result["status"] = "warning"
         result["issues"].append(f"存在判定依据不一致 ({len(basis_issues)}项)")
         
    if indicator_issues:
         if result["status"] == "pass": result["status"] = "warning"
         result["issues"].append(f"存在指标不合格或无法验证 ({len(indicator_issues)}项)")

    return result

def _fuzzy_match_method(report_method: str, required_method: str) -> bool:
    """
    模糊匹配检测方法
    """
    # 移除年份，例如 GB 5009.5-2016 -> GB 5009.5
    # 移除空格
    def clean(s):
        import re
        s = re.sub(r'-\d{4}', '', s) # 去掉年份
        s = re.sub(r'\s+', '', s)
        return s.lower()
        
    rm = clean(report_method)
    qm = clean(required_method)
    
    # 只要由一方包含另一方的主体 GB 号
    if qm in rm or rm in qm:
        return True
    
    # 特殊处理：有些写 "第一法"，有些写 "法一"
    return False

def _normalize_name(name: str) -> str:
    normalized = re.sub(r'\s+', '', name)
    return normalized

def _check_limit_compliance(report_value_str: str, limit_text: str) -> Optional[str]:
    """
    检查指标是否合规
    返回: None (无法判断/合规), 或 错误描述字符串
    """
    if not report_value_str or not limit_text:
        return None
        
    # 1. 解析报告值
    report_val = _parse_value(report_value_str)
    if report_val is None:
        return None # 无法解析报告值，跳过
        
    # 2. 解析限值
    # 限值文本可能是一大段话，我们需要提取出与该项目相关的数值
    # 简单策略：查找 "≤", "<", "不得检出" 等关键词附近的数字
    # TODO: 这是一个难点，目前仅处理最简单的 "≤ X" 格式
    
    limit_val = None
    limit_type = None # 'max', 'min', 'range', 'nd' (not detected)
    
    import re
    
    # 预处理 limit_text
    limit_text = limit_text.replace(" ", "")
    
    if "不得检出" in limit_text or "不得检测出" in limit_text:
        limit_type = 'nd'
    else:
        # 匹配 ≤ 3.0 或 < 3.0
        match = re.search(r'(?:≤|<=|<)([\d\.]+)', limit_text)
        if match:
            try:
                limit_val = float(match.group(1))
                limit_type = 'max'
            except:
                pass
                
    # 3. 比对
    if limit_type == 'nd':
        # 要求不得检出
        # 如果报告值是数值且 > 0，或者报告值是 "检出"
        if isinstance(report_val, float) and report_val > 0:
            return f"要求不得检出，实际检出 {report_value_str}"
        # 如果报告值包含 "<" (e.g. <0.01) 通常认为是未检出，合规
        
    elif limit_type == 'max':
        # 上限控制
        if isinstance(report_val, float):
             if report_val > limit_val:
                 return f"超标 (实测 {report_value_str} > 限量 {limit_val})"
    
    return None

def _parse_value(val_str: str) -> Optional[float]:
    """
    解析检测值
    "0.052" -> 0.052
    "<0.01" -> 0.0 (视为未检出/合规边界)
    "未检出" -> 0.0
    "ND" -> 0.0
    """
    if not val_str:
        return None
        
    val_str = val_str.strip()
    
    if "未检出" in val_str or "ND" in val_str.upper():
        return 0.0
        
    # 处理 < 符号
    if val_str.startswith("<"):
        # <0.01 视为 0 (或者视为小于限量的极小值)
        # 这里的逻辑是：如果是 <DL，通常说明合规（除非DL > Limit，那在另外的逻辑处理）
        return 0.0 
        
    try:
        import re
        # 提取第一个浮点数
        match = re.search(r'([\d\.]+)', val_str)
        if match:
            return float(match.group(1))
    except:
        pass
        
    return None
