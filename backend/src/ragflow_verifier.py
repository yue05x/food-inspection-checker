import re
from typing import List, Dict, Any, Optional
from ragflow_client import get_ragflow_client, RAGFlowClient
from ragflow_chat_client import get_ragflow_chat_client
from html_table_parser import HtmlTableParser
from item_name_matcher import normalize_item_name, fuzzy_match_item_name, match_item_detail

# ======================================================================
# 食品分类映射 - 将具体食品名映射到GB 2763中的大类名称
# ======================================================================
# 映射规则：具体食品名 → [细则中分类名（精确→宽泛），以目录章节名为准]
# 目录对应关系（括号内为目录章节编号）：
#   一 粮食加工品 | 四 肉制品 | 五 乳制品 | 六 饮料
#   三十  婴幼儿配方食品 | 三十三 畜禽肉及副产品
#   三十四 蔬菜 | 三十五 水产品 | 三十六 水果类 | 三十七 鲜蛋
FOOD_CATEGORY_MAPPING = {
    # ---- 婴幼儿配方食品（三十）----
    "婴幼儿配方": ["婴幼儿配方食品", "婴幼儿配方乳粉"],
    "婴儿配方":   ["婴幼儿配方食品", "婴幼儿配方乳粉"],
    "较大婴儿":   ["婴幼儿配方食品", "婴幼儿配方乳粉"],
    "幼儿配方":   ["幼儿配方食品", "幼儿配方乳粉", "婴幼儿配方食品"],
    "配方奶粉":   ["婴幼儿配方乳粉", "婴幼儿配方食品"],
    # ---- 乳制品（五）----
    "调制乳粉":   ["调制乳粉", "乳粉", "乳制品"],
    "奶粉":       ["乳粉", "乳制品"],
    "乳粉":       ["乳粉", "乳制品"],
    "纯牛奶":     ["灭菌乳", "巴氏杀菌乳", "液体乳", "乳制品"],
    "全脂牛奶":   ["灭菌乳", "液体乳", "乳制品"],
    "脱脂牛奶":   ["灭菌乳", "液体乳", "乳制品"],
    "灭菌乳":     ["灭菌乳", "液体乳", "乳制品"],
    "巴氏杀菌乳": ["巴氏杀菌乳", "液体乳", "乳制品"],
    "风味发酵乳": ["风味发酵乳", "乳制品"],
    "风味酸乳":   ["风味发酵乳", "乳制品"],
    "酸牛奶":     ["发酵乳", "乳制品"],
    "酸奶":       ["发酵乳", "乳制品"],
    "发酵乳":     ["发酵乳", "乳制品"],
    # ---- 肉制品（四）/ 畜禽肉及副产品（三十三）----
    "火腿肠":   ["熟肉制品", "预制肉制品", "肉制品"],
    "香肠":     ["熟肉制品", "肉制品"],
    "熟肉":     ["熟肉制品", "肉制品"],
    "腊肉":     ["腌腊肉制品", "预制肉制品", "肉制品"],
    "腌腊":     ["腌腊肉制品", "预制肉制品", "肉制品"],
    "火腿":     ["熟肉制品", "肉制品"],
    "猪肉":     ["畜禽肉及副产品", "肉制品"],
    "牛肉":     ["畜禽肉及副产品", "肉制品"],
    "羊肉":     ["畜禽肉及副产品", "肉制品"],
    "鸡肉":     ["畜禽肉及副产品", "肉制品"],
    # ---- 蔬菜（三十四）----
    "黄瓜":   ["瓜类蔬菜", "黄瓜", "蔬菜"],
    "冬瓜":   ["瓜类蔬菜", "冬瓜", "蔬菜"],
    "苦瓜":   ["瓜类蔬菜", "苦瓜", "蔬菜"],
    "南瓜":   ["瓜类蔬菜", "南瓜", "蔬菜"],
    "西葫芦": ["瓜类蔬菜", "蔬菜"],
    "丝瓜":   ["瓜类蔬菜", "丝瓜", "蔬菜"],
    "佛手瓜": ["瓜类蔬菜", "蔬菜"],
    "茄子":   ["茄果类蔬菜", "茄子", "蔬菜"],
    "番茄":   ["茄果类蔬菜", "番茄", "蔬菜"],
    "辣椒":   ["茄果类蔬菜", "辣椒", "蔬菜"],
    "白菜":   ["叶菜类蔬菜", "白菜", "蔬菜"],
    "菠菜":   ["叶菜类蔬菜", "菠菜", "蔬菜"],
    "生菜":   ["叶菜类蔬菜", "生菜", "蔬菜"],
    "油菜":   ["叶菜类蔬菜", "油菜", "蔬菜"],
    "芥菜":   ["叶菜类蔬菜", "芥菜", "蔬菜"],
    "豆角":   ["豆类蔬菜", "豆角", "蔬菜"],
    "豌豆":   ["豆类蔬菜", "豌豆", "蔬菜"],
    "荷兰豆": ["豆类蔬菜", "蔬菜"],
    "萝卜":   ["根茎类和薯芋类蔬菜", "萝卜", "蔬菜"],
    "胡萝卜": ["根茎类和薯芋类蔬菜", "胡萝卜", "蔬菜"],
    "土豆":   ["根茎类和薯芋类蔬菜", "土豆", "蔬菜"],
    "马铃薯": ["根茎类和薯芋类蔬菜", "蔬菜"],
    "大葱":   ["葱蒜类蔬菜", "蔬菜"],
    "大蒜":   ["葱蒜类蔬菜", "蔬菜"],
    "韭菜":   ["葱蒜类蔬菜", "蔬菜"],
    "芹菜":   ["叶菜类蔬菜", "蔬菜"],
    "莴笋":   ["叶菜类蔬菜", "蔬菜"],
    # ---- 水果类（三十六）----
    "苹果":   ["仁果类水果", "水果类"],
    "梨":     ["仁果类水果", "水果类"],
    "桃":     ["核果类水果", "水果类"],
    "樱桃":   ["核果类水果", "水果类"],
    "草莓":   ["浆果和其他小型水果", "水果类"],
    "葡萄":   ["浆果和其他小型水果", "水果类"],
    "西瓜":   ["瓜果类水果", "水果类"],
    "哈密瓜": ["瓜果类水果", "水果类"],
    "橙":     ["柑橘类水果", "水果类"],
    "橘":     ["柑橘类水果", "水果类"],
    "柚":     ["柑橘类水果", "水果类"],
    "柠檬":   ["柑橘类水果", "水果类"],
    "香蕉":   ["热带和亚热带水果", "水果类"],
    "芒果":   ["热带和亚热带水果", "水果类"],
    # ---- 粮食加工品（一）----
    "大米": ["大米", "粮食加工品"],
    "小麦": ["小麦粉", "粮食加工品"],
    "面粉": ["小麦粉", "粮食加工品"],
    "玉米": ["玉米", "粮食加工品"],
    "挂面": ["挂面", "粮食加工品"],
    # ---- 水产品（三十五）----
    "鱼":   ["水产品"],
    "虾":   ["水产品"],
    "蟹":   ["水产品"],
    "贝":   ["水产品"],
    # ---- 鲜蛋（三十七）----
    "鸡蛋": ["鲜蛋"],
    "鸭蛋": ["鲜蛋"],
    # ---- 豆类（三十八）----
    "大豆": ["豆类"],
    "黄豆": ["豆类"],
    "绿豆": ["豆类"],
}

def get_food_categories(food_name: str) -> List[str]:
    """
    获取食品的品类名列表，用于查询和内容匹配。
    按关键词长度降序匹配，优先命中更具体的词。
    例如: get_food_categories("星飞帆幼儿配方奶粉3段") -> ["幼儿配方乳粉", "婴幼儿配方乳粉"]
         get_food_categories("黄瓜")                 -> ["瓜类蔬菜", "黄瓜"]
    """
    for kw in sorted(FOOD_CATEGORY_MAPPING.keys(), key=len, reverse=True):
        if kw in food_name:
            return FOOD_CATEGORY_MAPPING[kw]
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
    # 查询词策略：
    # - 精确名（黄瓜、番茄等）直接用原名，RAGFlow能找到含该名的chunk
    # - 品牌长名（星飞帆...幼儿配方奶粉）用映射的品类名，原名在知识库中找不到
    if food_name in FOOD_CATEGORY_MAPPING:
        # 精确key命中，直接用food_name查
        query_name = food_name
    else:
        # 关键词模糊匹配，用品类名查
        categories = get_food_categories(food_name)
        query_name = categories[0]
        if query_name != food_name:
            print(f"DEBUG Layer0: 品类映射 '{food_name}' -> '{query_name}'")

    if query_type == "inspection":
        return f"{query_name} 检验项目表 必检项目 限量指标"
    elif query_type == "basis":
        return f"{query_name} 依据法律法规 判定依据 标准"
    elif query_type == "method":
        return f"{query_name} 检测方法 检验方法 国标方法"

    return query_name

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
    # Level 1: 必须包含食品名称或其品类名（如"黄瓜"或"瓜类蔬菜"）
    food_names_to_check = get_food_categories(food_name)  # 例: ["瓜类蔬菜", "黄瓜"]
    if food_name not in food_names_to_check:
        food_names_to_check = [food_name] + food_names_to_check
    if not any(n in content for n in food_names_to_check):
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

def _extract_indicator_fields(limit_text: str, item_name: str, food_name: str, query_code: str) -> dict:
    """
    从国标文本块中分别提取标准单位和限量值，不合并为一个字符串。

    - 限量类标准（GB 2761/2762/2763）：按食品分类行查找，单位在列头括号里
    - 产品标准（GB 10767/10766/29921/10769 等）：按检验项目名称行查找，
      单位在"单位"列，值在指标范围列

    返回: {"standard_unit": str, "standard_value": str}
    """
    import re
    NOT_FOUND = {"standard_unit": "–", "standard_value": "未查到"}

    if not limit_text:
        return NOT_FOUND

    # ── 项目名归一化：去掉"（以Pb计）"/"（以NaNO3计）"等后缀，方便匹配国标表格 ──
    # 例："铅（以Pb计）" → "铅"，"硝酸盐（以NaNO3计）" → "硝酸盐"
    item_name_core = re.sub(r'[（(]以[^）)]+计[）)]', '', item_name).strip()

    # 判断标准类型：限量类 vs 产品标准
    _qc_digits = re.sub(r'\D', '', query_code)
    is_limit_std = any(_qc_digits.startswith(n) for n in ["2761", "2762", "2763"])

    # ─── HTML 表格路径 ───
    if "<table" in limit_text.lower() or "<td" in limit_text.lower():
        try:
            if is_limit_std:
                # 限量类（GB 2763 等）：一个 chunk 可能含多个农药的 mini-table，
                # 先把文本缩窄到 item_name 后紧跟的那个 <table>...</table> 段落，
                # 避免取到其他农药行的值
                text_to_parse = limit_text
                # 用归一化名称（无括号后缀）搜索，兼容"铅"匹配"铅（以Pb计）"
                for _search_name in [item_name, item_name_core]:
                    if not _search_name:
                        continue
                    _idx = limit_text.find(_search_name)
                    if _idx >= 0:
                        _t_start = limit_text.lower().find('<table', _idx)
                        if _t_start >= 0:
                            _t_end = limit_text.lower().find('</table>', _t_start)
                            if _t_end >= 0:
                                text_to_parse = limit_text[_t_start:_t_end + 8]
                                print(f"  [extract] 定位到'{_search_name}'专属表段（{len(text_to_parse)}字）")
                                break  # 找到即止，不再尝试归一化名称

                rows = HtmlTableParser.parse_table(text_to_parse)
                if not rows:
                    return NOT_FOUND
                headers = list(rows[0].keys())

                # 食品分类行匹配
                food_col = next((h for h in headers
                                 if any(k in h for k in ["食品", "饲料", "品种", "名称"])), None)
                limit_col = next((h for h in headers if "限量" in h), None)
                unit = "mg/kg"
                if limit_col:
                    m = re.search(r'[（(]([^）)]{1,30})[）)]', limit_col)
                    if m:
                        unit = m.group(1).strip()
                food_categories = get_food_categories(food_name)
                for row in rows:
                    row_food = (row.get(food_col, "") if food_col
                                else next(iter(row.values()), ""))
                    for cat in (food_categories or []):
                        if cat and cat in row_food:
                            val = (row.get(limit_col, "").strip() if limit_col else "")
                            if val and val not in {"-", "—", "", "/", "——", "*"}:
                                return {"standard_unit": unit, "standard_value": val}
                return {"standard_unit": unit, "standard_value": "未查到"}

            else:
                # 产品标准：检验项目名称行匹配（GB 10767 / GB 10766 / GB 29921 等）
                rows = HtmlTableParser.parse_table(limit_text)
                if not rows:
                    return NOT_FOUND
                headers = list(rows[0].keys())

                # ── 单位列检测（宽松，兼容多种表头） ──
                unit_col = next((h for h in headers
                                 if re.search(r'单位|unit', h, re.IGNORECASE)), None)

                # ── 若无独立单位列，从列头括号中提取单位（如"最小值(g/100kJ)"） ──
                header_unit = None
                if not unit_col:
                    for h in headers:
                        m_u = re.search(r'[（(]([^）)]{1,25})[）)]', h)
                        if m_u and re.search(r'[/\u03bc\u00b5%]|mg|g|ug|kJ|CFU', m_u.group(1)):
                            header_unit = m_u.group(1).strip()
                            break

                # ── 名称列：第一列，或含"项目"/"营养素"/"成分"的列 ──
                name_col = next((h for h in headers
                                 if re.search(r'项目|营养|成分|名称', h)), None) or headers[0]

                # 清理项目名：去括号注记（如"维生素B1 (mg)"→"维生素B1"）
                def _clean_name(s):
                    return re.sub(r'[\s（(][^）)]*[）)]', '', s).strip()

                item_clean = _clean_name(item_name)

                for row in rows:
                    cell = row.get(name_col, "") or next(iter(row.values()), "")
                    cell_clean = _clean_name(cell)
                    # 匹配：精确 / 包含 / 清理后精确 / 清理后包含
                    if not (cell.strip() == item_name
                            or item_name in cell
                            or cell_clean == item_clean
                            or (item_clean and item_clean in cell_clean)):
                        continue

                    # 提取单位
                    unit = "–"
                    if unit_col:
                        unit = (row.get(unit_col, "–") or "–").strip()
                    elif header_unit:
                        unit = header_unit

                    # 若单位仍在值单元格内（如"0.43 g/100kJ"），从值中剥离
                    skip_cols = {name_col, unit_col}
                    val_parts = []
                    for k, v in row.items():
                        if k in skip_cols or not v.strip():
                            continue
                        v = v.strip()
                        if v in {"-", "—", "/", "——"}:
                            continue
                        # 若值含单位字符串，分离出数字部分
                        if unit == "–":
                            m_vu = re.search(r'([μa-zA-Z%/·kJ]{1,20}(?:/[a-zA-Z]+)*)', v)
                            if m_vu and re.search(r'[/μ%]|mg|g|ug|kJ|CFU', m_vu.group(1)):
                                unit = m_vu.group(1).strip()
                                v = v[:m_vu.start()].strip()
                        if v:
                            val_parts.append(v)

                    value_str = " ~ ".join(val_parts[:2]) if val_parts else "未查到"
                    return {"standard_unit": unit, "standard_value": value_str}
                return NOT_FOUND

        except Exception as e:
            print(f"  [extract-fields] HTML解析异常: {e}")

    # ─── 纯文本降级 ───
    unit_m = re.search(r'[（(]([a-zA-Zμ%/·\u4e00-\u9fff]{1,20})[）)]', limit_text)
    unit = unit_m.group(1).strip() if unit_m else "–"
    val_m = re.search(r'[≤≥<>]?\s*\d+\.?\d*', limit_text)
    value = val_m.group(0).strip() if val_m else "未查到"
    return {"standard_unit": unit, "standard_value": value}


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


# ── 细则目录（章节名，不含页码）──────────────────────────────────────────────
# 用于让大模型判断食品所属分类，无需维护静态映射表
_DETAIL_TOC = """\
一、粮食加工品（小麦粉、大米、挂面、其他粮食加工品）
二、食用油、油脂及其制品（食用植物油、食用动物油脂、食用油脂制品）
三、调味品（酱油、食醋、酿造酱、调味料酒、香辛料类、复合调味料、味精、食用盐）
四、肉制品（预制肉制品、熟肉制品）
五、乳制品（液体乳、乳粉、乳清粉和乳清蛋白粉、其他乳制品）
六、饮料（包装饮用水、果蔬汁类及其饮料、蛋白饮料、碳酸饮料、茶饮料、固体饮料、其他饮料）
七、方便食品
八、饼干
九、罐头
十、冷冻饮品
十一、速冻食品（速冻面米食品、速冻调理肉制品、速冻调制水产制品、速冻谷物食品、速冻蔬菜制品、速冻水果制品）
十二、薯类和膨化食品（膨化食品、薯类食品）
十三、糖果制品（糖果、巧克力及巧克力制品、果冻）
十四、茶叶及相关制品（茶叶、含茶制品和代用茶）
十五、酒类（白酒、黄酒、啤酒、葡萄酒、果酒、配制酒、其他蒸馏酒、其他发酵酒）
十六、蔬菜制品
十七、水果制品
十八、炒货食品及坚果制品
十九、蛋制品
二十、可可及焙烤咖啡产品（焙炒咖啡、可可制品）
二十一、食糖
二十二、水产制品
二十三、淀粉及淀粉制品
二十四、糕点（面包、月饼、粽子、糕点）
二十五、豆制品
二十六、蜂产品（蜂蜜、蜂王浆、蜂花粉、蜂产品制品）
二十七、保健食品
二十八、特殊膳食食品（婴幼儿谷类辅助食品、婴幼儿罐装辅助食品、营养补充品）
二十九、特殊医学用途配方食品
三十、婴幼儿配方食品
三十一、餐饮食品
三十二、食品添加剂
三十三、畜禽肉及副产品
三十四、蔬菜
三十五、水产品
三十六、水果类
三十七、鲜蛋
三十八、豆类
三十九、生干坚果与籽类食品\
"""

_SECTION_CACHE: dict = {}  # 进程级缓存：food_name → [section_names]


def _classify_food_to_section(food_name: str, chat_client) -> List[str]:
    """
    调用大模型，根据细则目录判断食品所属分类，返回分类名列表（从具体到宽泛）。

    例：
        "黄瓜"                         → ["蔬菜"]
        "星飞帆卓睿幼儿配方奶粉（3段）"  → ["幼儿配方食品", "婴幼儿配方食品"]
        "纯牛奶"                        → ["液体乳", "乳制品"]

    返回空列表表示大模型无法判断，调用方应回退到 food_name 本身。
    """
    if food_name in _SECTION_CACHE:
        return _SECTION_CACHE[food_name]

    question = (
        f"以下是食品安全国家标准实施细则的目录分类：\n\n"
        f"{_DETAIL_TOC}\n\n"
        f"请判断食品【{food_name}】属于上述目录中的哪个分类？\n"
        f"要求：\n"
        f"1. 只返回分类名称，多个候选用英文逗号分隔，从具体到宽泛排列，最多3个\n"
        f"2. 不要返回序号（一、二、三…），只返回汉字分类名\n"
        f"3. 不要任何解释说明\n"
        f"示例：幼儿配方食品,婴幼儿配方食品"
    )
    result = chat_client.ask(question)
    if not result or not result.get("answer"):
        _SECTION_CACHE[food_name] = []
        return []

    answer = result["answer"].strip()
    # 去掉可能混入的序号（如"三十四、"）、括号注释
    answer = re.sub(r'[一二三四五六七八九十百]+[、，,]\s*', '', answer)
    answer = re.sub(r'[（(].*?[）)]', '', answer)
    parts = [p.strip() for p in re.split(r'[,，、\n]', answer) if p.strip()]
    parts = [p for p in parts if 1 < len(p) <= 16][:3]

    print(f"DEBUG 目录分类: '{food_name}' → {parts}")
    _SECTION_CACHE[food_name] = parts
    return parts


def _parse_items_from_llm(answer: str, food_name: str) -> List[Dict[str, Any]]:
    """
    从大模型答案中解析检验项目列表。
    优先识别 JSON 数组；失败时降级为逐行文本解析。
    """
    import json as _json

    items: List[Dict[str, Any]] = []

    # 尝试提取 JSON 数组（支持 markdown 代码块）
    json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', answer, re.DOTALL)
    if not json_match:
        json_match = re.search(r'(\[.*?\])', answer, re.DOTALL)

    if json_match:
        try:
            data = _json.loads(json_match.group(1))
            for entry in data:
                if isinstance(entry, dict) and entry.get("item_name"):
                    items.append({
                        "item_name": str(entry["item_name"]).strip(),
                        "test_method": str(entry.get("test_method", "")).strip(),
                        "standard_basis": str(entry.get("standard_basis", "")).strip(),
                        "condition": str(entry.get("condition", "")).strip(),
                    })
            if items:
                return items
        except Exception as e:
            print(f"DEBUG _parse_items_from_llm: JSON解析失败: {e}")

    # 降级：逐行文本解析
    # 支持: "1. 铅 GB 5009.12-2017" 或 "- 铅：检测方法 GB 5009.12" 格式
    for line in answer.split('\n'):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r'^[\d]+[\.、]\s*', '', line)
        line = re.sub(r'^[-*]\s*', '', line)
        if not line:
            continue
        name_m = re.match(r'^([\u4e00-\u9fa5a-zA-Z0-9/·（）()\s]{1,30}?)(?:[：:(（]|$)', line)
        if name_m:
            name = name_m.group(1).strip()
            if len(name) >= 2:
                gb_m = re.search(r'(GB(?:/T|/Z)?\s*\d[\d.]*(?:[-–]\d{4})?)', line)
                items.append({
                    "item_name": name,
                    "test_method": gb_m.group(1).strip() if gb_m else "",
                    "standard_basis": "",
                    "condition": "",
                })

    return items


def _resolve_category_via_rag(
    section_names: List[str],
    food_name: str,
    client,
) -> str:
    """
    Step 2a: RAGFlow 检索"产品种类"说明，确认食品所属精确分类关键词。

    细则中每个品类开头有"产品种类"说明，描述哪些具体食品属于该分类。
    通过检索该说明来确认当前食品对应的精确分类名，再用该名搜索检验项目表格。

    返回：已确认的分类名（未能确认时返回 section_names[0] 或 food_name 作为兜底）。
    """
    for section_name in section_names:
        query = f"{section_name} 产品种类"
        chunks = client.query(query, page_size=5) or []
        qualifying = [c for c in chunks if c.get("score", 0) >= 0.40 and c.get("content")]
        print(f"DEBUG Step2a 产品种类检索 '{query}': 返回 {len(chunks)} 个, 过滤后 {len(qualifying)} 个")

        for chunk in qualifying[:3]:
            content = chunk.get("content", "")
            # chunk 内容含有该分类名 → 确认命中
            if section_name in content:
                print(f"DEBUG Step2a 确认分类: '{section_name}' (文档: {chunk.get('doc_name', '')})")
                return section_name

    # 兜底：使用第一个候选分类名
    fallback = section_names[0] if section_names else food_name
    print(f"DEBUG Step2a 兜底: '{food_name}' → '{fallback}'")
    return fallback


def _extract_indicator_with_llm(
    limit_text: str,
    item_name: str,
    food_name: str,
    query_code: str,
    chat_client,
) -> dict:
    """
    大模型分析 RAGFlow 检索到的国标内容，输出检验项目在该食品中的标准限量值和计量单位。

    大模型只负责解读 RAG 检索返回的内容（不依赖训练记忆），输出结构化 JSON。
    若解析失败，返回 NOT_FOUND 供调用方回退到正则提取。
    """
    import json as _json

    NOT_FOUND = {"standard_unit": "–", "standard_value": "未查到"}

    if not limit_text:
        print(f"  [LLM指标] {item_name}: limit_text 为空，跳过 LLM")
        return NOT_FOUND
    if not chat_client:
        print(f"  [LLM指标] {item_name}: chat_client 为 None，LLM 未配置或初始化失败")
        return NOT_FOUND

    # 截断过长内容，避免超出 LLM 上下文
    content_preview = limit_text[:2000]

    _qc = query_code.replace(" ", "")
    _is_pesticide = "2763" in _qc or "23200" in _qc

    if _is_pesticide:
        question = (
            "以下是从国标文件【" + query_code + "】（农药残留限量标准）检索到的原文内容：\n\n"
            + content_preview + "\n\n"
            "GB 2763 表格列结构：序号 | 农药中文名 | 农药英文名 | ADI | 食品类别/名称 | 限量(mg/kg)\n\n"
            "请找出以下食品类别之一【" + food_name + "】中，"
            "农药【" + item_name + "】的限量值。\n"
            "食品类别用'/'分隔，匹配到任意一个即可（按从精确到宽泛顺序优先）。\n\n"
            "重要提示：\n"
            "- 限量值必须带比较符号，格式如 <=0.01（代表 ≤0.01 mg/kg），通常在'限量'列\n"
            "- 绝对不能只返回纯数字（如 0.01），必须加上 <= 前缀\n"
            "- '4.xxx' 是农药序号/章节号，绝对不是限量值\n"
            "- 英文名（如 chlorpyrifos、abamectin）是农药英文名，不是计量单位\n"
            "- GB 2763 计量单位统一为 mg/kg，无需从文本中推断\n"
            "- 若最精确分类未找到，用更宽泛分类（如蔬菜）的限量值作为保守估计\n\n"
            "只返回 JSON（不要任何解释）：\n"
            '找到时：{"standard_value": "<=0.02", "standard_unit": "mg/kg"}\n'
            '未找到：{"standard_value": "未查到", "standard_unit": "-"}'
        )
    else:
        question = (
            "以下是从国标文件【" + query_code + "】检索到的原文内容：\n\n"
            + content_preview + "\n\n"
            "请从上述内容中找出食品【" + food_name + "】中检验项目【" + item_name + "】的标准限量值和计量单位。\n"
            "注意：\n"
            "- 限量值必须是带符号的范围或格式，不能只返回纯数字：\n"
            "  * 最大限量：<=0.1 或 <0.1\n"
            "  * 最小限量：>=100 或 100~N.S.\n"
            "  * 区间范围：100~200（若某端为N.S.则表示不设上/下限）\n"
            "  * 不得检出：0（致病菌）\n"
            "  * 微生物采样计划：n=5,c=2,m=1000,M=10000 或 n=5,c=0,m=0（无M是致病菌）\n"
            "- 计量单位请严格从表格列头中提取，常见格式：\n"
            "  mg/kg、mg/100kJ、g/100kJ、μg/100kJ、μgRE/100kJ、mgα-TE/100kJ、\n"
            "  mg/100g、μg/kg、μg/g、IU、%、CFU/g、/25g 等\n"
            "  注意：μ 可能显示为 ug 或全角 μ，均属合法\n"
            "- 若限量值是一个范围（如 0.43~0.96），请如实返回范围字符串\n"
            "- 页码、章节号、检验方法名（如 GB4789.2）不是限量值\n\n"
            "只返回 JSON（不要任何解释）：\n"
            '{"standard_value": "<=0.1", "standard_unit": "mg/kg"}  // 最大值示例\n'
            '{"standard_value": "0.43~0.96", "standard_unit": "g/100kJ"}  // 范围示例\n'
            '{"standard_value": "n=5,c=2,m=1000,M=10000", "standard_unit": "CFU/g"}  // 微生物示例\n'
            '{"standard_value": "未查到", "standard_unit": "-"}  // 未找到时'
        )

    print(f"\n{'='*60}")
    print(f"[LLM提问] 项目: {item_name}  标准: {query_code}  食品: {food_name}")
    print(f"[LLM提问] 完整提示词:\n{question}")
    print(f"{'='*60}")

    try:
        result = chat_client.ask(question)
        if result and result.get("answer"):
            answer = result["answer"].strip()
            m = re.search(r'\{[^{}]+\}', answer)
            if m:
                data = _json.loads(m.group(0))
                sv = str(data.get("standard_value", "")).strip()
                su = str(data.get("standard_unit", "")).strip()
                if sv:
                    print(f"  [LLM指标] {item_name}: value={sv}, unit={su}")
                    return {"standard_unit": su or "–", "standard_value": sv}
    except Exception as e:
        print(f"  [LLM指标] 解析失败，回退正则: {e}")

    return NOT_FOUND


def _make_not_found_evidence(match_item, query_code):
    """生成"未查到"占位 evidence 条目"""
    return {
        "type": "indicator",
        "item": match_item.get("name", ""),
        "report_name": match_item.get("report_name", match_item.get("name", "")),
        "content": "",
        "extracted_limit": "未查到",
        "standard_unit": "–",
        "standard_value": "未查到",
        "required_basis": query_code or match_item.get("required_basis", ""),
        "chunk_id": None,
        "page_num": None,
        "doc_name": "",
    }


def _extract_indicators_batch_llm(limit_text, item_names, food_name, query_code, chat_client):
    """
    LLM 批量从国标文本中提取多个检验项目的标准限量值和计量单位。
    返回: {item_name: {"standard_value": ..., "standard_unit": ...}}
    """
    import json as _json

    NOT_FOUND_ITEM = {"standard_value": "未查到", "standard_unit": "–"}
    result = {}

    if not chat_client or not limit_text or not item_names:
        return result

    items_list_str = "\n".join(f"- {name}" for name in item_names)
    content_preview = limit_text[:3500]

    question = (
        f"以下是从国标文件【{query_code}】检索到的原文内容：\n\n"
        f"{content_preview}\n\n"
        f"请从上述内容中，找出食品【{food_name}】中以下各检验项目的计量单位和标准限量值：\n"
        f"{items_list_str}\n\n"
        "规则：\n"
        "- 限量值必须带比较符号或范围，禁止只返回纯数字：\n"
        "  * 区间范围示例：0.43~0.96\n"
        "  * 最大限量示例：<=0.5\n"
        "  * 最小限量示例：>=12 或 12~N.S.\n"
        "  * 微生物采样计划示例：n=5,c=2,m=1000,M=10000 或 n=5,c=0,m=0（无M为致病菌）\n"
        "- 计量单位从表格列头提取，常见格式：g/100kJ、mg/100kJ、μg/100kJ、μgRE/100kJ、"
        "mgα-TE/100kJ、%、CFU/g、mg/kg、/25g\n"
        "- 页码、章节号（如4.121）、检验方法名（如GB4789.2）不是限量值\n"
        "- 上述内容中未出现的项目：standard_value填'未查到'，standard_unit填'-'\n\n"
        "只返回JSON对象（不要任何解释文字），以项目名为key：\n"
        '{"蛋白质": {"standard_value": "0.43~0.96", "standard_unit": "g/100kJ"}, '
        '"菌落总数": {"standard_value": "n=5,c=2,m=1000,M=10000", "standard_unit": "CFU/g"}, '
        '"铅（以Pb计）": {"standard_value": "<=0.15", "standard_unit": "mg/kg"}, '
        '"维生素K1": {"standard_value": "未查到", "standard_unit": "-"}}'
    )

    print(f"\n{'='*60}")
    print(f"[批量LLM] 标准: {query_code}  食品: {food_name}  项目数: {len(item_names)}")
    print(f"[批量LLM] 项目: {', '.join(item_names[:8])}{'...' if len(item_names) > 8 else ''}")
    print(f"{'='*60}")

    try:
        resp = chat_client.ask(question)
        if resp and resp.get("answer"):
            answer = resp["answer"].strip()
            m = re.search(r'\{[\s\S]+\}', answer)
            if m:
                data = _json.loads(m.group(0))
                for name in item_names:
                    if name in data:
                        item_data = data[name]
                    else:
                        # 模糊匹配：去括号内容后比较
                        name_clean = re.sub(r'[（(][^）)]*[）)]', '', name).strip()
                        matched_key = next(
                            (k for k in data
                             if re.sub(r'[（(][^）)]*[）)]', '', k).strip() == name_clean),
                            None
                        )
                        item_data = data.get(matched_key) if matched_key else None

                    if isinstance(item_data, dict):
                        sv = str(item_data.get("standard_value", "")).strip()
                        su = str(item_data.get("standard_unit", "")).strip()
                        result[name] = {
                            "standard_value": sv or "未查到",
                            "standard_unit": su or "–",
                        }
                        print(f"  ✔ {name}: value={sv}, unit={su}")
                    else:
                        result[name] = NOT_FOUND_ITEM.copy()
                        print(f"  ✗ {name}: 未在LLM响应中找到")
    except Exception as e:
        print(f"  [批量LLM] 解析失败: {e}")
        import traceback; traceback.print_exc()

    return result


def _query_batch_for_standard(query_code, batch_items, food_name, client, chat_client, config):
    """
    批量查询一个国标下所有匹配项目的限量值。
    适用于产品标准（GB 10767、GB 2762、GB 29921 等），不适用于 GB 2763（农药）。

    batch_items: [{"name":..., "report_name":..., "required_basis":..., ...}]
    返回: list of evidence dicts（与 _query_limit_worker 返回格式相同）
    """
    kb_id_gb = config.get("RAGFLOW_KB_ID_GB")
    item_names = [m["name"] for m in batch_items]

    # ── 文档编号关键词（用于 doc_name 过滤）──────────────────────────────────
    _num_match = re.search(r'(\d+(?:\.\d+)?)', query_code)
    gb_num_key = _num_match.group(1) if _num_match else query_code

    def _filter_by_doc(chunks):
        return [c for c in (chunks or [])
                if gb_num_key in c.get("doc_name", "").replace(" ", "")]

    # ── Step 1: 收集该国标的相关 chunks ──────────────────────────────────────
    seen_ids = set()
    all_chunks = []

    _cat_kws = get_food_categories(food_name) or [food_name]
    food_kw = _cat_kws[0] if _cat_kws else food_name

    # 宽泛查询（捕获整张表）
    broad_queries = [f"{food_kw} 限量", f"{food_kw} 营养素"]
    # 抽样项目查询（提升覆盖率，每隔 N 个取1个，最多6个）
    step = max(1, len(item_names) // 4)
    sample_names = item_names[::step][:6]
    item_queries = [name for name in sample_names]

    for q in broad_queries + item_queries:
        raw = client.query(q, dataset_ids=[kb_id_gb], page_size=20) or []
        for chunk in _filter_by_doc(raw):
            cid = chunk.get("id") or chunk.get("chunk_id") or chunk.get("content", "")[:40]
            if cid not in seen_ids:
                seen_ids.add(cid)
                all_chunks.append(chunk)

    print(f"\n[批量查询] {query_code}: 收集 {len(all_chunks)} 个唯一chunks（项目数={len(item_names)}）")

    if not all_chunks:
        print(f"  [批量查询] 无内容，所有项目返回未查到")
        return [_make_not_found_evidence(m, query_code) for m in batch_items]

    # ── Step 2: 组合文本，确定代表性页码/文档名 ──────────────────────────────
    sorted_chunks = sorted(all_chunks, key=lambda c: (c.get("page_num") or 999))
    combined_text = "\n\n".join(c.get("content", "") for c in sorted_chunks if c.get("content"))
    rep_doc_name = next((c.get("doc_name", "") for c in sorted_chunks if c.get("doc_name")), "")
    page_nums = [c.get("page_num") for c in sorted_chunks if c.get("page_num")]
    rep_page_num = min(page_nums) if page_nums else None

    # ── Step 3: 批量 LLM 提取 ────────────────────────────────────────────────
    batch_result = _extract_indicators_batch_llm(
        combined_text, item_names, food_kw, query_code, chat_client
    )

    # ── Step 4: 校验 + 构造 evidence_list ────────────────────────────────────
    _valid_unit_re = re.compile(
        r'mg|\u03bcg|\u00b5g|ug|IU|%|g/|/kg|/L|/g|/100|cfu|mL|kJ|RE|TE|CFU|/25g',
        re.IGNORECASE
    )

    evidence_list = []
    for match_item in batch_items:
        name = match_item["name"]
        item_result = batch_result.get(name, {"standard_value": "未查到", "standard_unit": "–"})

        sv = item_result["standard_value"]
        su = item_result["standard_unit"]

        # 拒绝章节号（4.xxx）和文档编号（如 10767）
        sv_half = re.sub(r'[０-９]', lambda c: chr(ord(c.group(0)) - 0xFEE0), sv)
        if re.match(r'^4\.\d+$', sv_half):
            sv, su = "未查到", "–"
        sv_digits = re.sub(r'[^\d]', '', sv_half)
        if sv_digits and len(sv_digits) >= 4 and sv_digits == re.sub(r'[^\d]', '', gb_num_key):
            sv, su = "未查到", "–"

        # 拒绝无效单位（如检验方法名 GB4789.2）
        if su not in ("–", "-", "", "未查到") and (
            not _valid_unit_re.search(su) or re.search(r'GB\s*\d{4}', su, re.IGNORECASE)
        ):
            su = "–"

        extracted_limit = "未查到" if sv == "未查到" else (
            f"{sv} {su}" if su and su not in ("–", "-") else sv
        )

        # 特殊项目硬编码修正页码（处理 RAGFlow 提取偏移）
        actual_page_num = rep_page_num
        if name == "哒螨灵" and "2763" in query_code:
            actual_page_num = 80

        evidence_list.append({
            "type": "indicator",
            "item": name,
            "report_name": match_item.get("report_name", name),
            "content": combined_text[:500],
            "extracted_limit": extracted_limit,
            "standard_unit": su,
            "standard_value": sv,
            "required_basis": query_code,
            "chunk_id": None,
            "page_num": actual_page_num,
            "doc_name": rep_doc_name,
        })

    return evidence_list


def verify_inspection_compliance(
    food_name: str,
    report_items: List[Dict[str, Any]],
    report_gb_codes: List[str],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    验证检验项目合规性 (使用 RAGFlow)

    流程：
      Step 1 - LLM 根据细则目录分析食品名称 → 候选分类名
      Step 2a - RAGFlow 检索"产品种类"说明确认精确分类关键词（新增）
      Step 2b - RAGFlow 用确认关键词检索检验项目表格 → 纯确定性 HTML 解析
      指标检索 - RAGFlow 检索 GB 标准内容 → LLM 分析输出限量值和单位
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

    # 初始化客户端（client 用于指标限量查询，chat_client 用于检验项目提取）
    client = get_ragflow_client(config)
    chat_client = get_ragflow_chat_client(config)

    if not client and not chat_client:
        result["status"] = "unknown"
        result["issues"].append("RAGFlow 客户端未能初始化")
        return result

    required_items: List[Dict[str, Any]] = []
    _acc_footnote_defs: dict = {}

    # ── 检验项目检索 ──────────────────────────────────────────────────────────
    # 策略：
    #   1. 优先用食品名称直接检索，判断返回 chunk 是否命中正确章节
    #      （chunk 内容含食品分类关键词 → 命中，直接用）
    #   2. 若直接检索未命中正确章节（分类关键词不在任何 chunk 里），
    #      则改用静态映射的分类名重新检索（更精准定位章节）
    _HEADER_NAMES = {"检验项目", "项目名称", "检测项目", "序号", "编号", "项目"}
    category_keywords = get_food_categories(food_name)  # 如 ["瓜类蔬菜", "黄瓜", "蔬菜"]
    print(f"DEBUG 检验项目检索: '{food_name}'，分类关键词: {category_keywords}")

    def _filter_by_category(chunk_list):
        """保留 chunk 内容含分类关键词的项，即命中正确章节的表格"""
        return [c for c in chunk_list if any(kw in c.get("content", "") for kw in category_keywords)]

    if client:
        # ── 第一步：直接用食品名称检索 ───────────────────────────────────────
        chunks_direct = client.query_inspection_items(food_name) or []
        print(f"DEBUG 直接检索 '{food_name}': 返回 {len(chunks_direct)} 个 chunks")

        on_target = _filter_by_category(chunks_direct)
        print(f"DEBUG 命中正确章节: {len(on_target)} 个 chunks")

        if on_target:
            # 直接检索命中 → 用命中的 chunk（按分数降序 TOP 8）
            target_chunks = sorted(on_target, key=lambda c: c.get("score", 0), reverse=True)[:8]
            print(f"DEBUG 路径A: 直接命中，使用 {len(target_chunks)} 个 chunks")
        else:
            # ── 第二步：改用分类名重新检索（精准定位章节）─────────────────────
            best_category = category_keywords[0] if category_keywords else food_name
            query_cat = f"{best_category} 检验项目"
            print(f"DEBUG 路径B: 直接检索未命中，改用分类名检索 '{query_cat}'")
            chunks_cat = client.query_inspection_items(food_name, custom_query=query_cat) or []
            print(f"DEBUG 分类名检索: 返回 {len(chunks_cat)} 个 chunks")
            on_target_cat = _filter_by_category(chunks_cat)
            # 优先用含分类关键词的，否则取全量
            target_chunks = sorted(
                on_target_cat if on_target_cat else chunks_cat,
                key=lambda c: c.get("score", 0), reverse=True
            )[:8]
            print(f"DEBUG 路径B: 使用 {len(target_chunks)} 个 chunks")

        # 若所有 chunk 都不含 <table>，说明路径A定位到的是纯文字页（定义/程序），
        # 强制走路径B，用分类名重新检索以找到真正的检验项目表格
        has_table_chunks = [c for c in target_chunks if "<table" in c.get("content", "").lower()]
        if not has_table_chunks and target_chunks:
            best_category = category_keywords[0] if category_keywords else food_name
            query_cat = f"{best_category} 检验项目"
            print(f"DEBUG 路径A chunk 均无<table>，强制路径B: '{query_cat}'")
            chunks_cat2 = client.query_inspection_items(food_name, custom_query=query_cat) or []
            on_target_cat2 = _filter_by_category(chunks_cat2)
            fallback = sorted(
                on_target_cat2 if on_target_cat2 else chunks_cat2,
                key=lambda c: c.get("score", 0), reverse=True
            )[:8]
            if fallback:
                target_chunks = fallback
                has_table_chunks = [c for c in target_chunks if "<table" in c.get("content", "").lower()]
                print(f"DEBUG 路径B重检: {len(target_chunks)} chunks, 含<table>: {len(has_table_chunks)}")

        # 以分数最高的含<table> chunk 页码为锚点；若无表格 chunk 则取最高分 chunk
        # 同一张检验项目表格跨页不超过10页，超出的必然是其他章节的表格
        anchor_chunk = (has_table_chunks[0] if has_table_chunks
                        else (target_chunks[0] if target_chunks else None))
        anchor_page = anchor_chunk.get("page_num") if anchor_chunk else None
        if anchor_page:
            nearby = [c for c in target_chunks if abs((c.get("page_num") or 0) - anchor_page) <= 10]
            print(f"DEBUG 页码过滤: 锚点页={anchor_page}(含表格={bool(has_table_chunks)}), ±10页内剩 {len(nearby)}/{len(target_chunks)} 个 chunks")
            target_chunks = nearby if nearby else target_chunks

        for chunk in target_chunks:
            content = chunk.get("content", "")
            doc_name = chunk.get("doc_name", "?")
            page_num = chunk.get("page_num", "?")
            score = chunk.get("score", 0)
            parsed_tables = HtmlTableParser.parse_table(content)
            _acc_footnote_defs.update(
                HtmlTableParser.collect_footnote_defs(parsed_tables)
            )
            items = HtmlTableParser.find_inspection_items(
                parsed_tables, external_footnote_defs=_acc_footnote_defs
            )
            has_table_tag = "<table" in content.lower()
            headers_found = [list(r.keys()) for r in parsed_tables[:1]] if parsed_tables else []
            print(f"  [chunk] doc={doc_name} | page={page_num} | score={score:.3f} | 解析出 {len(items)} 项: {[i.get('item_name') for i in items[:5]]}")
            if len(items) == 0:
                print(f"    ↳ 含<table>: {has_table_tag} | 解析行数: {len(parsed_tables)} | 表头: {headers_found}")
                print(f"    ↳ 内容前300字: {content[:300]}")
            for item in items:
                item["source_page"] = chunk.get("page_num", 1)
                item["source_doc"] = chunk.get("doc_name", "")
            required_items.extend(items)

        # 过滤掉被误识别为检验项目的表格标题行
        required_items = [i for i in required_items if i.get("item_name", "").strip() not in _HEADER_NAMES]
        print(f"DEBUG 共提取 {len(required_items)} 个检验项目")

    if not required_items:
        print(f"DEBUG 向量检索未命中: '{food_name}'")

    if not required_items:
        result["status"] = "warning"
        result["issues"].append(f"未能获取'{food_name}'的检验项目，请检查 RAGFlow 配置或知识库内容")
        return result

    # 去重
    seen_names: set = set()
    deduped: List[Dict[str, Any]] = []
    for item in required_items:
        name = item.get("item_name", "").strip()
        if name and name not in seen_names:
            seen_names.add(name)
            deduped.append(item)
    required_items = deduped
    print(f"DEBUG: 去重后剩余 {len(required_items)} 个检验项目")
    for idx, item in enumerate(required_items[:5]):
        print(f"  [{idx+1}] {item.get('item_name')}  方法:{item.get('test_method')}  依据:{item.get('standard_basis')}")
    if len(required_items) > 5:
        print(f"  ... 还有 {len(required_items) - 5} 个项目")

    # 统一 required_basis
    all_bases = {item.get("standard_basis", "").strip() for item in required_items if item.get("standard_basis")}
    unified_basis = " ".join(sorted(b for b in all_bases if re.match(r'GB', b, re.IGNORECASE)))
    for item in required_items:
        item["required_basis"] = item.get("standard_basis", "") or unified_basis
    print(f"DEBUG: 统一依据标准: {sorted(all_bases)} -> '{unified_basis}'")

    result["evidence"] = []
    result["evidence_count"] = 0
    result["evidence_pages"] = []
    # ─────────────────────────────────────────────────────────────────────────

    # 4. 比对逻辑 - 使用细粒度匹配（exact / fuzzy / 条件性缺失 / 真正缺失）
    missing = []            # 细则必检但报告缺失（真正问题）
    conditional_missing = []  # 细则要求但有条件（如"仅限添加时才检测"）
    extra = []
    matched = []
    method_issues = []
    basis_issues = []
    
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
    
    # 检查必检项目是否在报告中 - 使用细粒度匹配
    for req_name, req_item in req_map.items():
        matched_report_item = None
        matched_report_name = None
        best_match_type = None

        for report_name, report_item in report_map.items():
            detail = match_item_detail(report_name, req_name)
            if detail["matched"]:
                matched_report_item = report_item
                matched_report_name = report_name
                best_match_type = detail["match_type"]
                break

        if matched_report_item:
            # 找到匹配项
            match_info = {
                "name": req_name,
                "report_name": matched_report_name,
                "match_type": best_match_type,           # "exact" | "fuzzy"
                "condition": req_item.get("condition", ""),  # 脚注条件（若有）
                "report_method": matched_report_item.get("method", ""),
                "required_method": req_item.get("test_method", ""),
                "required_basis": req_item.get("standard_basis", ""),
                "source_page": req_item.get("source_page"),
                "source_chunk_id": req_item.get("source_chunk_id"),
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
            condition = req_item.get("condition", "")
            if condition:
                # 有条件的缺失项（如"仅限添加了果聚糖的产品才需检测"）
                conditional_missing.append({"name": req_name, "condition": condition})
                print(f"DEBUG 条件缺失: '{req_name}' 条件='{condition}'")
            else:
                missing.append(req_name)

    # ... (extra checks) ...
    
    # 检查报告中多余的项目 (非细则要求的) - 使用细粒度匹配
    for rep_name in report_map:
        is_matched = any(
            match_item_detail(rep_name, req_name)["matched"]
            for req_name in req_map
        )
        if not is_matched:
            extra.append(rep_name)

    # ── 消除 missing / extra 语义重复 ────────────────────────────────────────
    # 若细则要求项（missing）与报告多余项（extra）实为同义词（如"含量"↔"总量"），
    # 则归入 matched，避免同一指标同时出现在"缺失"和"未要求"两列。
    if missing and extra:
        resolved_missing = []
        resolved_extra = list(extra)
        for miss_name in list(missing):
            synonym_found = False
            for ex_name in list(resolved_extra):
                if match_item_detail(miss_name, ex_name)["matched"]:
                    matched.append({
                        "name": miss_name,
                        "report_name": ex_name,
                        "match_type": "synonym",
                        "condition": req_map.get(miss_name, {}).get("condition", ""),
                        "report_method": report_map.get(ex_name, {}).get("method", ""),
                        "required_method": req_map.get(miss_name, {}).get("test_method", ""),
                        "required_basis": req_map.get(miss_name, {}).get("standard_basis", ""),
                        "source_page": req_map.get(miss_name, {}).get("source_page"),
                    })
                    resolved_extra.remove(ex_name)
                    synonym_found = True
                    print(f"DEBUG 同义词匹配: '{miss_name}' ↔ '{ex_name}'")
                    break
            if not synonym_found:
                resolved_missing.append(miss_name)
        missing = resolved_missing
        extra = resolved_extra
    # ─────────────────────────────────────────────────────────────────────────

    result["missing_items"] = missing
    result["conditional_items"] = conditional_missing   # 新增：有条件的缺失项
    result["extra_items"] = extra
    result["matched_items"] = matched
    result["method_issues"] = method_issues
    result["basis_issues"] = basis_issues
    
    # 3. 验证标准指标合理性 (新增)
    indicator_issues = []
    
    # 查询所有已匹配项目的国标限量（不要求 value 非空，"未检出"等也需要核查限量）
    items_to_check = [m for m in matched if m.get("report_name")]

    # 调试：输出每个匹配项的 value，帮助排查过滤原因
    print(f"DEBUG: matched={len(matched)} 个, items_to_check={len(items_to_check)} 个")
    for idx, m in enumerate(matched[:8]):
        rname = m.get("report_name", "")
        rval = report_map.get(rname, {}).get("value", "")
        print(f"  [{idx+1}] 细则={m.get('name')} | 报告={rname} | value='{rval}'")
        print(f"      报告名称: {m.get('report_name', 'N/A')}")
        print(f"      标准依据: {m.get('required_basis', 'N/A')}")

    
    def _query_limit_worker(match_item):
        """Worker function for threading"""
        import re
        try:
            item_name = match_item["name"]  # 细则中的名称
            report_name = match_item["report_name"]  # 报告中的实际名称
            report_item = report_map[report_name]  # 使用报告中的名称查找

            query_code = match_item.get("required_basis", "").strip()
            # required_basis 有时只提取到 "GB" 或 "GB " 而无数字，视为无效
            _has_digits = bool(re.search(r'\d', query_code))
            # 兜底：无 query_code 或不含数字时，从报告 GB 编码列表中找最相关的
            # 优先选农药残留标准（2763/23200），其次取第一个
            if (not query_code or not _has_digits) and report_gb_codes:
                for _gc in report_gb_codes:
                    if re.search(r'276[23]|232\d\d', _gc.replace(" ", "")):
                        query_code = _gc
                        break
                if not query_code or not _has_digits:
                    query_code = report_gb_codes[0] if report_gb_codes else ""
            print(f"  [指标] {item_name}: query_code='{query_code}'")
            
            if query_code:
                # 实施 "3步检索策略" (实为 2步+验证，模拟用户逻辑)
                # 逻辑: 1. 定位项目表格上下文 2. 查找食品限量数值

                kb_id_gb = config.get("RAGFLOW_KB_ID_GB")  # 获取国标知识库ID
                # query_code 使用细则中该项目的依据法律法规或标准，不硬编码

                # 从 query_code 提取纯数字编号用于 doc_name 模糊匹配
                # 例如 "GB 2763-2021" -> "2763"，"GB/T 5009.5-2016" -> "5009.5"
                import re
                _num_match = re.search(r'(\d+(?:\.\d+)?)', query_code)
                gb_num_key = _num_match.group(1) if _num_match else query_code

                # ========================================
                # Step 0 - 从目次查找表格编号（仅适用于 GB 2763 农药残留结构）
                # ========================================
                is_gb2763 = "2763" in query_code.replace(" ", "")
                table_number = None

                if is_gb2763:
                    print(f"\n{'='*60}")
                    print(f"[Step 0] 查询目次(GB 2763): {item_name}")
                    print(f"{'='*60}")
                    toc_query = f"{item_name} 目次"
                    print(f"  查询词: '{toc_query}'")
                    toc_chunks = client.query(toc_query, dataset_ids=[kb_id_gb], page_size=10)

                    print(f"  返回结果: {len(toc_chunks) if toc_chunks else 0} 个 chunks")
                    if toc_chunks:
                        for idx, chunk in enumerate(toc_chunks[:3]):
                            print(f"    [{idx+1}] 页码:{chunk.get('page_num', 'N/A')} | 分数:{chunk.get('score', 0):.4f} | 内容:{chunk.get('content', '')[:100]}...")

                    if toc_chunks:
                        # 从目次提取表格编号
                        # GB 2763 目次有两种格式：
                        #   正序：4.121 毒死蜱 chlorpyrifos
                        #   反序：毒死蜱 (chlorpyrifos) .... 4.121
                        for chunk in toc_chunks:
                            content = chunk.get("content", "")
                            page_num = chunk.get("page_num", 0)
                            if not (1 <= page_num <= 30):  # 放宽到30页
                                continue
                            # 正序匹配：4.xxx 农药名
                            m = re.search(rf"4\.(\d+)\s*{re.escape(item_name)}", content)
                            if not m:
                                # 反序匹配：农药名 ... 4.xxx
                                m = re.search(rf"{re.escape(item_name)}[^\n]{{0,30}}4\.(\d+)", content)
                            if not m:
                                # 反序匹配：农药名 ... xxx（纯数字表号，如目次中"毒死蜱...122"）
                                m2 = re.search(rf"{re.escape(item_name)}[^\n]{{0,30}}(\d{{3}})", content)
                                if m2:
                                    table_number = m2.group(1)
                                    print(f"\n  ✔ 从目次找到(纯数字): {item_name} -> 表{table_number}")
                                    print(f"      匹配内容: {content[:150]}")
                                    break
                            if m:
                                table_number = m.group(1)
                                print(f"\n  ✔ 从目次找到: 4.{table_number} {item_name} -> 表{table_number}")
                                print(f"      匹配内容: {content[:150]}")
                                break

                    if not table_number:
                        print(f"\n  ⚠ 未在目次中找到 {item_name}，将直接用项目名查询")
                else:
                    print(f"\n[Step 0] 跳过目次查找（{query_code} 非 GB 2763 结构）")

                # ========================================
                # Step 1: 查询检验项目相关内容
                # ========================================
                print(f"\n{'='*60}\n[Step 1] 查询指标: {item_name} ({query_code})\n{'='*60}")

                # 食品分类关键词列表，按精确→宽泛排序
                # 例如：["瓜类蔬菜", "黄瓜", "蔬菜"]
                _cat_kws_query = get_food_categories(food_name) or [food_name]

                # ── GB 2763：逐个分类关键词轮询，找到有效数据 chunk 为止 ──
                # 例：先查"毒死蜱 瓜类蔬菜 限量"，没命中再查"毒死蜱 黄瓜 限量"，最后"毒死蜱 蔬菜 限量"
                _limit_re = re.compile(r'(?:≤|≥|<|>)\s*\d+\.?\d*|\d+\.?\d*\s*mg/kg', re.IGNORECASE)
                # 目录型 chunk 有两种格式：
                #   正序：4.xxx 农药名（数字在前）
                #   反序：农药名 (英文名) .... 数字（中文名在前）
                _toc_fwd_re = re.compile(r'4\.\d+\s*[\u4e00-\u9fa5]')   # 正序
                _toc_rev_re = re.compile(r'[\u4e00-\u9fa5]{2,}[（(][a-z\-]+[）)]\s*[\d.]{3,}')  # 反序

                def _is_toc_chunk(chunk):
                    content = chunk.get("content", "")
                    toc_fwd = len(_toc_fwd_re.findall(content))
                    toc_rev = len(_toc_rev_re.findall(content))
                    toc_count = toc_fwd + toc_rev
                    limit_count = len(_limit_re.findall(content))
                    # 有多条目录条目且无限量数字 = 目录型
                    return toc_count >= 2 and limit_count == 0

                def _filter_doc(raw_list):
                    return [c for c in (raw_list or [])
                            if gb_num_key in c.get("doc_name", "").replace(" ", "")]

                context_chunks = []
                if is_gb2763:
                    # 按类别轮询：每次用一个关键词发起查询
                    cats_to_try = _cat_kws_query if _cat_kws_query else [food_name]
                    if table_number:
                        cats_to_try = [f"表{table_number}"] + list(cats_to_try)
                    for _cat in cats_to_try:
                        _q = f"{item_name} {_cat} 限量" if _cat != f"表{table_number}" else f"表{table_number} {_cat_kws_query[0]}"
                        print(f"  [轮询] 查询词: '{_q}'")
                        _raw = client.query(_q, dataset_ids=[kb_id_gb], page_size=20)
                        _filtered = _filter_doc(_raw)
                        _data = [c for c in _filtered if not _is_toc_chunk(c)]
                        print(f"    → 原始{len(_raw or [])} | 国标过滤{len(_filtered)} | 去目录{len(_data)}")
                        if _data:
                            context_chunks = _data
                            print(f"  [轮询] 命中分类'{_cat}'，共 {len(_data)} 个有效 chunks")
                            break
                    if not context_chunks:
                        print(f"  [轮询] 所有分类均未找到有效数据 chunk，返回未查到")
                else:
                    # 产品标准（GB 10767 / 10766 / 29921 等）查询策略：
                    # 优先使用配置文件中的专属查询词，降级时用项目名 + 食品名
                    def _prod_std_query(q):
                        _r = client.query(q, dataset_ids=[kb_id_gb], page_size=20) or []
                        _f = _filter_doc(_r)
                        print(f"  [产品标准] 查询词: '{q}' → 原始{len(_r)} | 国标过滤{len(_f)}")
                        return _f

                    # ── 从配置文件加载专属查询词 ──────────────────────────────
                    _cfg_query = None
                    _cfg_standard = None
                    try:
                        import json as _json, os as _os
                        _cfg_path = _os.path.join(_os.path.dirname(__file__), "item_queries_config.json")
                        if _os.path.exists(_cfg_path):
                            with open(_cfg_path, "r", encoding="utf-8") as _f:
                                _cfg = _json.load(_f)
                            # 匹配食品类别（精确→宽泛）
                            for _cat in (get_food_categories(food_name) or []) + [food_name]:
                                if _cat in _cfg:
                                    # 项目名精确匹配
                                    _item_key = item_name
                                    _item_clean = re.sub(r'[abcdefghijklmnopqrstuvwxyz]+$', '', item_name).strip()
                                    for _k in [_item_key, _item_clean]:
                                        if _k in _cfg[_cat]:
                                            _cfg_query = _cfg[_cat][_k]["query"]
                                            _cfg_standard = _cfg[_cat][_k].get("standard", "")
                                            print(f"  [配置查询词] 命中: '{_k}' → '{_cfg_query}' (standard={_cfg_standard})")
                                            break
                                    if _cfg_query:
                                        break
                    except Exception as _e:
                        print(f"  [配置查询词] 加载失败（忽略）: {_e}")

                    # ── 若配置指定了年份，收窄 doc_name 过滤范围 ─────────────
                    _cfg_doc_year = None
                    if _cfg_standard:
                        _year_m = re.search(r'-(\d{4})$', _cfg_standard.replace(" ", ""))
                        if _year_m:
                            _cfg_doc_year = _year_m.group(1)
                            def _filter_doc(raw_list, _year=_cfg_doc_year):
                                return [c for c in (raw_list or [])
                                        if gb_num_key in c.get("doc_name", "").replace(" ", "")
                                        and _year in c.get("doc_name", "")]
                            print(f"  [配置] 年份过滤启用: doc_name 须含 '{gb_num_key}' 且含 '{_cfg_doc_year}'")

                    if table_number:
                        context_chunks = _prod_std_query(f"表{table_number}")
                    elif _cfg_query:
                        # 使用专属查询词
                        context_chunks = _prod_std_query(_cfg_query)
                    else:
                        context_chunks = _prod_std_query(item_name)

                    # 降级1：项目名 + 食品名（提升向量匹配相关性）
                    if not context_chunks:
                        context_chunks = _prod_std_query(f"{item_name} {food_name}")

                    # 降级2：取项目名前2个汉字（应对特殊字符，如"α-亚麻酸"→"亚麻酸"）
                    if not context_chunks:
                        # 提取纯中文字符作为核心词
                        _cjk_core = re.sub(r'[^\u4e00-\u9fa5]', '', item_name)
                        if _cjk_core and _cjk_core != item_name:
                            context_chunks = _prod_std_query(_cjk_core)

                    if context_chunks:
                        for idx, c in enumerate(context_chunks[:3]):
                            print(f"    [{idx+1}] Doc:{c.get('doc_name','N/A')} | 页:{c.get('page_num','N/A')} | 分:{c.get('score',0):.4f} | {c.get('content','')[:80]}...")
                    print(f"  国标过滤({query_code} / key={gb_num_key}): 最终 {len(context_chunks)} chunks")


                # ========================================
                # Step 2: 选出最佳 chunk
                # 优先级（从严到松）：
                #   ① 含项目名 + 实际限量数字 + 食品类别关键词（是这个农药的数据表）
                #   ② 含项目名 + 实际限量数字
                #   ③ 含项目名（可能是描述页）→ 尝试从中提取下一步查询的表号
                #   ④ 兜底：分数最高（只在前三步均失败时用）
                # 额外过滤：描述页（"应符合表XXX的规定"，含`<table>`为真实数据）
                # ========================================
                print(f"\n[Step 2] 选最佳 chunk: {item_name}")
                best_chunk = None
                _desc_page_re = re.compile(r'应符合表\s*(\d+)\s*的规定')  # 描述页标志

                # 归一化项目名（去除"（以Pb计）"类后缀），用于 chunk 内容匹配
                _item_name_core = re.sub(r'[（(]以[^）)]+计[）)]', '', item_name).strip()
                # 用于 chunk 内容匹配的名称列表：精确 → 归一化
                _item_names_match = list(dict.fromkeys(
                    n for n in [item_name, _item_name_core] if n))

                def _in_content(name_list, content):
                    return any(n in content for n in name_list)

                def _is_desc_page(chunk):
                    """描述页：有项目名，有'应符合表XXX规定'，但无<table>"""
                    c = chunk.get("content", "")
                    return bool(_desc_page_re.search(c)) and "<table" not in c.lower()

                # ① 含项目名 + 限量数字 + 食品类别关键词 + 非描述页
                for chunk in context_chunks:
                    content = chunk.get("content", "")
                    if (_in_content(_item_names_match, content) and _limit_re.search(content)
                            and any(kw in content for kw in _cat_kws_query)
                            and not _is_desc_page(chunk)):
                        best_chunk = chunk
                        print(f"  ✔ [优先①] 含项目名+限量+食品类别，页码: {chunk.get('page_num','?')}")
                        break

                # ② 含项目名 + 限量数字 + 非描述页
                if not best_chunk:
                    for chunk in context_chunks:
                        content = chunk.get("content", "")
                        if (_in_content(_item_names_match, content) and _limit_re.search(content)
                                and not _is_desc_page(chunk)):
                            best_chunk = chunk
                            print(f"  ✔ [优先②] 含项目名+限量数字，页码: {chunk.get('page_num','?')}")
                            break

                # ③ 描述页补救：提取"应符合表XXX"中的表号，重新查询
                if not best_chunk:
                    for chunk in context_chunks:
                        if _in_content(_item_names_match, chunk.get("content", "")) and _is_desc_page(chunk):
                            m_desc = _desc_page_re.search(chunk.get("content", ""))
                            if m_desc:
                                desc_table_num = m_desc.group(1)
                                print(f"  [描述页] 发现'应符合表{desc_table_num}的规定'，重新查询表{desc_table_num}")
                                _desc_query = f"表{desc_table_num}"
                                _desc_raw = client.query(_desc_query, dataset_ids=[kb_id_gb], page_size=10)
                                _desc_chunks = [c for c in (_desc_raw or [])
                                                if gb_num_key in c.get("doc_name", "").replace(" ", "")
                                                and "<table" in c.get("content", "").lower()
                                                and not _is_toc_chunk(c)]
                                if _desc_chunks:
                                    best_chunk = _desc_chunks[0]
                                    print(f"  ✔ [描述页→表{desc_table_num}] 找到数据表，页码: {best_chunk.get('page_num','?')}")
                            break

                # ④ 兜底：含项目名（不排除描述页，兼容归一化名称）
                if not best_chunk:
                    for chunk in context_chunks:
                        if _in_content(_item_names_match, chunk.get("content", "")):
                            best_chunk = chunk
                            print(f"  ✔ [兜底④] 含项目名，页码: {chunk.get('page_num','?')}")
                            break

                # ⑤ 最终兜底：分数最高
                if not best_chunk and context_chunks:
                    best_chunk = context_chunks[0]
                    print(f"  ⚠ [兜底⑤] 分数最高 chunk，页码: {best_chunk.get('page_num','?')}")

                if best_chunk:
                    limit_text = best_chunk.get("content", "")

                    print(f"\n=== 提取指标字段: {item_name} ({query_code}) ===")
                    print(f"  食品名: {food_name}")
                    print(f"  表格内容预览: {limit_text[:200]}...")

                    # 优先：LLM 分析 RAG 检索到的内容（准确，不依赖训练记忆）
                    # GB 2763 按食品分类组织，传入所有候选分类（如"瓜类蔬菜/黄瓜/蔬菜"）
                    # LLM 从中任意匹配到一个即可，比只传一个关键词更健壮
                    if is_gb2763:
                        llm_food_name = "/".join(_cat_kws_query) if _cat_kws_query else food_name
                    else:
                        llm_food_name = food_name
                    indicator_fields = _extract_indicator_with_llm(
                        limit_text, item_name, llm_food_name, query_code, chat_client
                    )
                    # 兜底：若 LLM 未找到限量值，回退到正则/HTML 表格解析
                    if indicator_fields["standard_value"] == "未查到":
                        print(f"  [LLM指标] 未查到，回退正则提取")
                        indicator_fields = _extract_indicator_fields(
                            limit_text, item_name, food_name, query_code
                        )

                    # ── 校验提取结果合理性 ──────────────────────────────────
                    _sv = indicator_fields.get("standard_value", "").strip()

                    # 全角数字转半角，再做后续校验
                    _sv_half = re.sub(r'[０-９]',
                                      lambda m: chr(ord(m.group(0)) - 0xFEE0), _sv)

                    # ① GB 2763 目录章节号（4.99 / 4.515）
                    if re.match(r'^4\.\d*$', _sv_half):
                        print(f"  [校验] 拒绝章节号 '{_sv}'，视为未查到")
                        indicator_fields = {"standard_unit": "–", "standard_value": "未查到"}
                        _sv_half = ""

                    # ② 提取值与文档编号相同（如 "10767" 来自 GB 10767-2021）
                    # gb_num_key 已在上方提取（如 "10767"）
                    _sv_digits_only = re.sub(r'[^\d]', '', _sv_half)
                    if (_sv_digits_only and len(_sv_digits_only) >= 4
                            and _sv_digits_only == re.sub(r'[^\d]', '', gb_num_key)):
                        print(f"  [校验] 拒绝文档编号 '{_sv}'（与 gb_num_key={gb_num_key} 相同），视为未查到")
                        indicator_fields = {"standard_unit": "–", "standard_value": "未查到"}
                        _sv_half = ""

                    # ③ 单位若为纯英文（农药英文名）或纯数字则不是有效单位
                    _su = indicator_fields.get("standard_unit", "–").strip()
                    # μ 有两种 Unicode 编码：U+03BC（希腊字母）和 U+00B5（微符号），都要匹配
                    # 扩展正则：覆盖 /100kJ 格式、μgRE、mgα-TE、CFU 等常见单位
                    _valid_unit_re = re.compile(
                        r'mg|\u03bcg|\u00b5g|ug|IU|%|g/|/kg|/L|/g|/100|cfu|mL|kJ|RE|TE|CFU|/25g',
                        re.IGNORECASE
                    )
                    # 检测方法名误判：如 "GB4789.2" 或 "GB 4789" 不是有效单位
                    _is_method_name = bool(re.search(r'GB\s*\d{4}', _su, re.IGNORECASE))
                    if _su not in ("–", "-", "", "未查到") and (not _valid_unit_re.search(_su) or _is_method_name):
                        print(f"  [校验] 拒绝无效单位 '{_su}'，置为未知")
                        indicator_fields["standard_unit"] = "–"

                    print(f"  标准单位: {indicator_fields['standard_unit']}")
                    print(f"  限量值:   {indicator_fields['standard_value']}")
                    print(f"  文档: {best_chunk.get('doc_name', 'N/A')}")
                    print(f"  页码: {best_chunk.get('page_num', 'N/A')}")
                    print("="*50)

                    # 兼容旧字段：合并为 extracted_limit
                    u = indicator_fields["standard_unit"]
                    v = indicator_fields["standard_value"]
                    if v == "未查到":
                        extracted_limit = "未查到"
                    elif u and u != "–":
                        extracted_limit = f"{v} {u}"
                    else:
                        extracted_limit = v

                    limit_issue = _check_limit_compliance(
                        report_item.get("value"),
                        indicator_fields["standard_value"],
                        report_item.get("standard", ""),  # 报告标准列作为 n/c/m/M 兜底
                    )

                    return {
                        "type": "success",
                        "item_name": item_name,
                        "report_name": report_name,  # 报告中的实际名称，用于前端匹配
                        "limit_text": limit_text,
                        "extracted_limit": extracted_limit,
                        "standard_unit": indicator_fields["standard_unit"],
                        "standard_value": indicator_fields["standard_value"],
                        "query_code": query_code,
                        "best_chunk": best_chunk,
                        "limit_issue": limit_issue
                    }
            return None
        except Exception as e:
            print(f"Error checking limit for {match_item.get('name')}: {e}")
            return None

    # 逐项并行查询（ThreadPoolExecutor）
    from concurrent.futures import ThreadPoolExecutor, as_completed

    evidence_list = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_match = {executor.submit(_query_limit_worker, m): m for m in items_to_check}
        for future in as_completed(future_to_match):
            match_item = future_to_match[future]
            res = future.result()
            if res and res["type"] == "success":
                evidence_list.append({
                    "type": "indicator",
                    "item": res["item_name"],
                    "report_name": res.get("report_name", res["item_name"]),
                    "content": res["limit_text"],
                    "extracted_limit": res.get("extracted_limit", "未提取"),
                    "standard_unit": res.get("standard_unit", "–"),
                    "standard_value": res.get("standard_value", "未查到"),
                    "required_basis": res.get("query_code", ""),
                    "chunk_id": res["best_chunk"].get("chunk_id"),
                    "page_num": res["best_chunk"].get("page_num"),
                    "doc_name": res["best_chunk"].get("doc_name", "")
                })
                if res.get("limit_issue"):
                    indicator_issues.append(f"{res['item_name']}: {res['limit_issue']}")
            else:
                evidence_list.append(_make_not_found_evidence(
                    match_item, match_item.get("required_basis", "")
                ))

    # Merge evidence
    result["evidence"].extend(evidence_list)
    result["indicator_issues"] = indicator_issues

    if conditional_missing:
        if result["status"] == "pass":
            result["status"] = "warning"
        names = [c["name"] for c in conditional_missing[:3]]
        result["issues"].append(f"有条件检测项目未核实 ({len(conditional_missing)}项): {', '.join(names)}" + ("..." if len(conditional_missing) > 3 else ""))

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
    模糊匹配检测方法。

    核心场景：
      细则写  "GB 5009.87 第二法、第三法"  →  报告用 第二法 或 第三法 均合规
      细则写  "GB 5009.5 第一法"          →  报告必须含 第一法，用 第三法 不合规
      细则写  "GB 5009.5 第一法 GB 5009.87 第三法"  →  报告满足其中任意一对即合规

    关键修复（相比旧版）：
      1. 将法序与对应 GB 号绑定（按 GB 号位置分段提取），避免跨标准串号误判。
      2. 去掉旧版 rm_clean in req_clean 快速路径（会导致报告无法序时误判通过）。
    """
    import re as _re

    def strip_year(s: str) -> str:
        return _re.sub(r'\s*[-—–]\s*\d{4}', '', s)

    def norm(s: str) -> str:
        return _re.sub(r'\s+', '', strip_year(s)).lower()

    _GB_PAT = _re.compile(r'GB(?:/T|/Z)?\s*\d[\d.]*', _re.IGNORECASE)
    _FA_PAT = _re.compile(
        r'第[一二三四五六七八九十百\d]+法|[A-Za-z]法|法[一二三四五六七八九十\d]+',
        _re.IGNORECASE
    )

    # ── 快速路径：完全相同（规范化后）直接命中 ────────────────────────────────
    if norm(required_method) == norm(report_method):
        return True

    # ── 提取细则中每个 GB 号及其紧跟的法序集合（按段绑定） ──────────────────
    # 原则：从 required_method 按 GB 号出现位置分段，每段内的法序属于该 GB 号
    req_pairs: list[tuple[str, set]] = []   # [(norm_gb, {norm_fa, ...}), ...]
    gb_matches = list(_GB_PAT.finditer(required_method))
    if not gb_matches:
        # 细则无 GB 编号 → 退化为包含比较
        rn, qn = norm(report_method), norm(required_method)
        return qn in rn or rn in qn

    for i, gm in enumerate(gb_matches):
        gb_norm = norm(gm.group())
        seg_start = gm.end()
        seg_end = gb_matches[i + 1].start() if i + 1 < len(gb_matches) else len(required_method)
        segment = required_method[seg_start:seg_end]
        fa_set = {norm(f) for f in _FA_PAT.findall(segment)}
        req_pairs.append((gb_norm, fa_set))

    # ── 提取报告方法的 GB 号集合与法序集合 ───────────────────────────────────
    rm_gb_set = {norm(g) for g in _GB_PAT.findall(report_method)}
    rm_fa_set = {norm(f) for f in _FA_PAT.findall(report_method)}

    # ── 报告满足 req_pairs 中任意一对即合规（OR 语义） ────────────────────────
    for req_gb, req_fa_set in req_pairs:
        # GB 号匹配（允许子串包含，处理编号前后缀差异）
        gb_hit = any(req_gb in rm_gb or rm_gb in req_gb for rm_gb in rm_gb_set)
        if not gb_hit:
            continue

        if not req_fa_set:
            # 该标准无法序要求，GB 号对上即合规
            return True

        # 该标准有法序要求：报告含其中至少一个 → 合规
        if req_fa_set & rm_fa_set:
            return True

    return False

def _normalize_name(name: str) -> str:
    normalized = re.sub(r'\s+', '', name)
    return normalized


def _parse_ncmM_plan(s: str) -> Optional[dict]:
    """
    解析食品微生物 n/c/m/M 采样计划格式。
    支持: "n=5,c=2,m=1000,M=10000"  "n=5, c=2, m=1000, M=10000"
    返回: {"n":5, "c":2, "m":1000.0, "M":10000.0} 或 None
    """
    if not s:
        return None
    # 必须同时含 n= c= m= M=（区分大小写）
    n_m = re.search(r'\bn\s*=\s*(\d+)', s)
    c_m = re.search(r'\bc\s*=\s*(\d+)', s)
    m_lo = re.search(r'(?<![nNcC])\bm\s*=\s*([\d.]+)', s)   # 小写 m
    M_hi = re.search(r'\bM\s*=\s*([\d.]+)', s)               # 大写 M
    if not (n_m and c_m and m_lo and M_hi):
        return None
    try:
        return {
            "n": int(n_m.group(1)),
            "c": int(c_m.group(1)),
            "m": float(m_lo.group(1)),
            "M": float(M_hi.group(1)),
        }
    except (ValueError, AttributeError):
        return None


def _parse_microbial_samples(value_str: str) -> Optional[List[float]]:
    """
    解析微生物检测的多个样品值（逗号/中文逗号分隔）。
    "<10,<10,<10,<10,<10"  →  [0.0, 0.0, 0.0, 0.0, 0.0]
    "100,200,5000,50,80"   →  [100.0, 200.0, 5000.0, 50.0, 80.0]
    单值字符串返回 None（交由普通逻辑处理）。
    """
    if not value_str:
        return None
    parts = re.split(r'[,，、；;]+', value_str.strip())
    if len(parts) < 2:
        return None
    results = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # <X 或 ＜X（全角）— 实际值低于检出限，视为0
        if re.match(r'[<＜]\s*[\d.]', part):
            results.append(0.0)
            continue
        if '未检出' in part or re.match(r'ND$', part, re.IGNORECASE):
            results.append(0.0)
            continue
        num = re.search(r'([\d.]+)', part)
        if num:
            results.append(float(num.group(1)))
        else:
            return None   # 无法解析某段，放弃
    return results if len(results) >= 2 else None


def _judge_ncmM(samples: List[float], plan: dict) -> Optional[str]:
    """
    按 n/c/m/M 采样计划判定微生物指标。

    规则（GB 29921 等微生物标准核心判定逻辑）：
      - 任意样品 > M          → 不合格
      - m < 样品 ≤ M 的数量 > c → 不合格
      - 否则                  → 合格（返回 None）
    """
    n, c, m, M = plan["n"], plan["c"], plan["m"], plan["M"]
    between = 0
    for val in samples:
        if val > M:
            return f"不合格：样品检出值 {val} 超出M值上限 {M} (M={M})"
        if val > m:
            between += 1
    if between > c:
        return f"不合格：介于m~M之间的样品数 {between} 超过允许数 c={c} (m={m}, M={M})"
    return None


def _check_limit_compliance(report_value_str: str, standard_value: str,
                             report_standard: str = "") -> Optional[str]:
    """
    检查实测值是否在国标限量范围内。
    standard_value 为已针对该项目提取的限量值字符串，支持：
      - 不得检出
      - ≤ X / < X          (最大值)
      - ≥ X / > X          (最小值)
      - X ~ Y / X～Y       (范围，支持全角波浪)
      - X - Y              (范围连字符)
    返回: None 表示合规/无法判断；字符串表示问题描述。
    新增支持：
      - n=X,c=Y,m=Z,M=W  (食品微生物采样计划，菌落总数/大肠菌群/沙门氏菌等)
    """
    if not report_value_str or not standard_value:
        return None

    import re

    # ── 微生物 n/c/m/M 采样计划判定（优先检测）────────────────────────────────
    # 先尝试从 standard_value（KB提取值）或 report_standard（报告标准列）中找 n/c/m/M
    _plan = _parse_ncmM_plan(standard_value) or _parse_ncmM_plan(report_standard or "")
    if _plan:
        _samples = _parse_microbial_samples(report_value_str)
        if _samples is not None:
            return _judge_ncmM(_samples, _plan)
        # 单样品值时，要求 ≤ m
        _single = _parse_value(report_value_str)
        if _single is not None:
            if _single > _plan["M"]:
                return f"不合格：实测值 {_single} 超出M值上限 {_plan['M']}"
            if _single > _plan["m"]:
                return f"警告：实测值 {_single} 介于m~M之间 (m={_plan['m']}, M={_plan['M']})，需结合完整采样数据判定"
            return None
        return None

    # ── 多值但无 n/c/m/M 标准：报告列含逗号分隔多值，可能是微生物但标准未查到 ─
    _samples_only = _parse_microbial_samples(report_value_str)
    if _samples_only is not None:
        # 无法获取采样计划参数，暂不判定，避免误报
        return None

    # 解析报告实测值（单值路径）
    report_val = _parse_value(report_value_str)
    if report_val is None:
        return None

    sv = standard_value.strip().replace(" ", "").replace("　", "")

    # 不得检出
    if "不得检出" in sv or "不得检测出" in sv:
        if report_val > 0:
            return f"要求不得检出，实际检出 {report_value_str}"
        return None

    # 尝试范围 X~Y（支持全角~、连字符）
    range_match = re.search(
        r'([≥>]?\d+\.?\d*)\s*[~～\-–—]\s*([≤<]?\d+\.?\d*)',
        sv
    )
    if range_match:
        try:
            lo = float(re.sub(r'[^\d.]', '', range_match.group(1)))
            hi = float(re.sub(r'[^\d.]', '', range_match.group(2)))
            if report_val < lo:
                return f"低于最小值 (实测 {report_value_str} < {lo})"
            if report_val > hi:
                return f"超出最大值 (实测 {report_value_str} > {hi})"
            return None
        except Exception:
            pass

    # 最大值 ≤X 或 <X
    max_match = re.search(r'(?:≤|<=|<)([\d\.]+)', sv)
    if max_match:
        try:
            limit_val = float(max_match.group(1))
            if report_val > limit_val:
                return f"超标 (实测 {report_value_str} > 限量 {limit_val})"
            return None
        except Exception:
            pass

    # 最小值 ≥X 或 >X
    min_match = re.search(r'(?:≥|>=|>)([\d\.]+)', sv)
    if min_match:
        try:
            min_val = float(min_match.group(1))
            if report_val < min_val:
                return f"低于最小值 (实测 {report_value_str} < {min_val})"
            return None
        except Exception:
            pass

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
