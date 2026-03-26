import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import re
from item_name_matcher import is_composite_indicator

logger = logging.getLogger(__name__)

class HtmlTableParser:
    """
    负责解析 RAGFlow 返回的 HTML 表格数据
    """
    
    @staticmethod
    def parse_table(html_content: str) -> List[Dict[str, str]]:
        """
        解析 HTML 表格，返回结构化的数据列表（支持 chunk 内多张表格）。
        每一行转换为一个字典，键为表头。
        """
        if not html_content:
            return []

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            tables = soup.find_all('table')

            if not tables:
                return []

            all_results = []
            for table in tables:
                all_results.extend(HtmlTableParser._parse_single_table(table))
            return all_results

        except Exception as e:
            logger.warning("HTML 表格解析错误: %s", e)
            return []

    @staticmethod
    def _parse_single_table(table) -> List[Dict[str, str]]:
        """解析单个 <table> 元素，返回行数据列表。"""
        try:
            # 提取表头：优先找含 <th> 的行，其次找内容最丰富的首行
            headers = []
            header_row = None
            all_rows = table.find_all('tr')

            # 优先：找第一个含 <th> 元素的行
            for row in all_rows:
                if row.find_all('th'):
                    header_row = row
                    th_cells = row.find_all('th')
                    headers = [HtmlTableParser._clean_text(th.get_text()) for th in th_cells]
                    break

            # 降级：用第一行 <td> 作为表头
            if not headers and all_rows:
                header_row = all_rows[0]
                td_cells = header_row.find_all('td')
                candidate = [HtmlTableParser._clean_text(td.get_text()) for td in td_cells]
                if any(h for h in candidate):
                    headers = candidate

            if not headers:
                return []

            results = []
            rows = all_rows
            start_idx = (rows.index(header_row) + 1) if header_row in rows else 0

            for row in rows[start_idx:]:
                cells = row.find_all('td')
                if not cells:
                    continue

                row_data = {}
                for i, cell in enumerate(cells):
                    if i < len(headers):
                        key = headers[i]
                        value = HtmlTableParser._clean_text(cell.get_text())
                        row_data[key] = value

                if any(row_data.values()):
                    results.append(row_data)

            return results
        except Exception as e:
            logger.warning("_parse_single_table 错误: %s", e)
            return []

    @staticmethod
    def _split_cell_items(raw_text: str) -> List[str]:
        """
        检测并拆分合并了多个项目的单元格内容。
        细则 HTML 表格中，某些 <td> 包含多行项目（换行后被合并成空格）。

        边界识别：[中文/括号/数字] + [脚注小写字母串] + 空格 + [中文字符开头的新项目]
        例: "亚硝酸盐（以NaNO2计）e 黄曲霉毒素M1 或黄曲霉 51 毒素B1"
           → ["亚硝酸盐（以NaNO2计）", "黄曲霉毒素M1 或黄曲霉 毒素B1"]
        """
        if not raw_text:
            return [raw_text]

        parts = re.split(
            r'(?<=[\u4e00-\u9fa5）)）\d])[a-z]+\s+(?=[\u4e00-\u9fa5])',
            raw_text
        )
        if len(parts) == 1:
            return [raw_text]

        result = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # 去掉开头残余的序号（如 "51 毒素B1" → "毒素B1"）
            part = re.sub(r'^\d+\s+', '', part)
            # 去掉内嵌的独立序号（前后均非字母/数字，如 "黄曲霉 51 毒素" → "黄曲霉 毒素"）
            part = re.sub(r'(?<![A-Za-z\d])\d+(?![A-Za-z\d])', ' ', part)
            part = re.sub(r'\s+', ' ', part).strip()
            if part:
                result.append(part)

        return result if result else [raw_text]

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
    def _collapse_spaces_in_brackets(text: str) -> str:
        """
        删除全角/半角括号内的空格。
        PDF 转 HTML 时括号内的换行常被替换为空格，导致名称被后续 split() 切断。
        例: "甜蜜素（以环己 基氨基磺酸计）" → "甜蜜素（以环己基氨基磺酸计）"
        """
        result = []
        depth = 0
        for ch in text:
            if ch in '（(':
                depth += 1
                result.append(ch)
            elif ch in '）)':
                depth -= 1
                result.append(ch)
            elif ch == ' ' and depth > 0:
                pass   # 括号内的空格是换行 artifact，删除
            else:
                result.append(ch)
        return ''.join(result)

    @staticmethod
    def _is_condition_text(text: str) -> bool:
        """
        判断一段文本是否为条件说明（而非检验指标名称）。
        条件说明示例：
          - "适用于婴儿配方食品"
          - "限固态产品"
          - "仅限添加了该物质的产品"
          - "当产品含有X时适用"
        """
        if not text or len(text) < 4:
            return False
        # 适用于 / 仅适用
        if re.match(r'^(适用于|仅适用)', text):
            return True
        # 仅限（排除"仅限量"这类无意义片段）
        if re.match(r'^仅限[^量值\d]', text):
            return True
        # 限XXX（"限"后不跟"量/值/数字"，且文本 >4 字确保不误判）
        if re.match(r'^限[^量值\d]', text) and len(text) > 4:
            return True
        # 当...时 / 以下...除外
        if re.match(r'^(当.{5,}时|以下.{3,}除外)', text):
            return True
        return False

    @staticmethod
    def collect_footnote_defs(parsed_table: List[Dict[str, str]]) -> Dict[str, str]:
        """
        从解析后的表格中收集脚注定义行，返回 {字母: 定义文本} 字典。
        供 ragflow_verifier 跨 chunk 累积脚注定义使用。
        """
        col_map_name = ["检验项目", "项目名称", "项目"]
        _name_col: Optional[str] = None
        for _row in parsed_table:
            for _k in _row.keys():
                for _t in col_map_name:
                    if _t in _k:
                        _name_col = _k
                        break
                if _name_col:
                    break
            if _name_col:
                break

        defs: Dict[str, str] = {}
        if _name_col:
            for _row in parsed_table:
                raw = _row.get(_name_col, "").strip()
                m = re.match(r'^([a-z])\.\s+(.+)', raw)
                if not m:
                    m = re.match(r'^注[：:]\s*([a-z])\.\s+(.+)', raw)
                if m:
                    defs[m.group(1)] = m.group(2).strip()
        return defs

    @staticmethod
    def find_inspection_items(parsed_table: List[Dict[str, str]],
                              external_footnote_defs: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """
        从解析后的表格中提取检验项目信息
        需要识别特定的列名，如 "检验项目", "依据法律法规", "检测方法" 等

        新增：两步脚注处理
          第一步：收集表格中形如 "b. 限乳基产品..." 的脚注定义行
          第二步：解析项目名时保留脚注字母 → 关联对应条件文本
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

        # ── 预处理：展开合并了多项目的单元格 ─────────────────────────────────────
        _expanded = []
        _name_col: Optional[str] = None
        for _row in parsed_table:
            if _name_col is None:
                for _k in _row.keys():
                    for _t in col_map["name"]:
                        if _t in _k:
                            _name_col = _k
                            break
                    if _name_col:
                        break
            if _name_col and _name_col in _row:
                _subs = HtmlTableParser._split_cell_items(_row[_name_col])
                if len(_subs) > 1:
                    for _s in _subs:
                        _new = dict(_row)
                        _new[_name_col] = _s
                        _expanded.append(_new)
                    continue
            _expanded.append(_row)
        parsed_table = _expanded
        # ─────────────────────────────────────────────────────────────────────────

        # ── 第一步：收集脚注定义 ────────────────────────────────────────────────
        # 脚注行特征: 检验项目列内容以 "b. " / "k. " 等单小写字母+句点+空格 开头
        # 以外部传入的 external_footnote_defs 为基础，本 chunk 内定义的优先覆盖
        footnote_defs: Dict[str, str] = dict(external_footnote_defs) if external_footnote_defs else {}
        if _name_col:
            for _row in parsed_table:
                raw = _row.get(_name_col, "").strip()
                # 标准格式: "a. 适用于..." 或 "注：a. 适用于..."
                m = re.match(r'^([a-z])\.\s+(.+)', raw)
                if not m:
                    m = re.match(r'^注[：:]\s*([a-z])\.\s+(.+)', raw)
                if m:
                    footnote_defs[m.group(1)] = m.group(2).strip()
        if footnote_defs:
            logger.debug("脚注定义: %s", footnote_defs)
        # ─────────────────────────────────────────────────────────────────────────

        _pending_condition = ""  # 出现在指标行之前的条件文本，待绑定到首个指标
        _pending_merge = ""     # 括号未闭合时，暂存当前片段，与下一行拼接

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
                # 应用挂起的拼接：上一行括号未闭合时，把当前行内容拼在其后
                if _pending_merge:
                    raw_name = _pending_merge + raw_name.strip()
                    _pending_merge = ""
                # 去掉前置序号（如 "1  蛋白质" → "蛋白质", "12  维生素A" → "维生素A"）
                raw_name = re.sub(r'^\d+\s+', '', raw_name.strip())

                # 过滤逻辑 0: 备注行 —— 以单字母+句点开头（如 "b. 限乳基产品..."）
                # 这些行已在第一步收集到 footnote_defs，此处直接跳过
                if re.match(r'^[a-z]\.\s', raw_name.strip()):
                    logger.debug("筛选: 备注行: %s", raw_name.strip()[:40])
                    continue
                # 过滤 "注：a." / "注:1." 类中文注释标记行（如 "注：a. 适用于以豆类..."）
                if re.match(r'^注[：:]', raw_name.strip()):
                    logger.debug("筛选: 中文注释标记: %s", raw_name.strip()[:40])
                    continue

                # 去掉尾部脚注字母并保存脚注键
                # 例: "胆碱b"→"胆碱"(keys=["b"]), "乳铁蛋白bk"→"乳铁蛋白"(keys=["b","k"])
                _footnote_match = re.search(r'(?<=[\u4e00-\u9fa5\d）)）])([a-z]+)$', raw_name)
                _footnote_keys: List[str] = []
                if _footnote_match:
                    _footnote_keys = list(_footnote_match.group(1))
                    raw_name = raw_name[:_footnote_match.start()]
                raw_name_stripped = raw_name.strip()

                # ── 括号未闭合检测：开括号 > 闭括号，说明名称跨行被截断 ────────────
                # 把当前片段记入 _pending_merge，等下一行来拼接，本行不产生指标
                _open_cnt  = raw_name_stripped.count('（') + raw_name_stripped.count('(')
                _close_cnt = raw_name_stripped.count('）') + raw_name_stripped.count(')')
                if _open_cnt > _close_cnt:
                    _pending_merge = raw_name_stripped
                    logger.debug("括号未闭合，等待下行拼接: %s", raw_name_stripped[:40])
                    continue

                # ── 孤立括号开头片段（如"（以山梨酸计）"、"（续）"）──────────────────
                # 是上一行名称断行后分离出的括号补充，尝试归并到上一条指标；不成则丢弃
                if raw_name_stripped.startswith('（') or raw_name_stripped.startswith('('):
                    if items:
                        prev_name = items[-1].get("item_name", "")
                        _p_open  = prev_name.count('（') + prev_name.count('(')
                        _p_close = prev_name.count('）') + prev_name.count(')')
                        if _p_open > _p_close:
                            items[-1]["item_name"] = prev_name + raw_name_stripped
                            logger.debug("括号片段归并至上一指标: '%s' + '%s'",
                                         prev_name[:20], raw_name_stripped[:20])
                            continue
                    logger.debug("筛选: 孤立括号开头片段: %s", raw_name_stripped[:40])
                    continue
                # ─────────────────────────────────────────────────────────────────

                # ── 条件文本检测（优先于其他过滤，防止条件被丢弃）─────────────────
                # "适用于…"、"限…"等条件句不是指标，须绑定到对应指标的 condition 字段
                if HtmlTableParser._is_condition_text(raw_name_stripped):
                    if items:
                        # 追加到最近一个指标的条件
                        existing = items[-1].get("condition", "")
                        items[-1]["condition"] = (existing + "；" + raw_name_stripped).lstrip("；")
                        logger.debug("条件绑定→[%s]: %s",
                                     items[-1].get("item_name", "?")[:15], raw_name_stripped[:50])
                    else:
                        # 条件出现在所有指标之前，暂存，待首个指标出现时绑定
                        _pending_condition += ("；" if _pending_condition else "") + raw_name_stripped
                    continue
                # ─────────────────────────────────────────────────────────────────

                # 过滤逻辑 0b: 跨行fragment过滤
                # 以"或"/"和"开头的短片段、以"计）"结尾的括号残片
                if re.match(r'^(或|和)[^\u4e00-\u9fa5]{0,2}', raw_name_stripped) and len(raw_name_stripped) < 8:
                    logger.debug("筛选: 跨行fragment: %s", raw_name_stripped)
                    continue
                # 复合指标残片："与...比值/占比/之和"结构（如"与总脂肪酸比值"）
                # 这类片段是因 rowspan 展平导致复合指标被拆成了两行
                if re.match(r'^与.+(比值|比例|占比|之和|总量|总和)$', raw_name_stripped):
                    logger.debug("筛选: 复合指标残片: %s", raw_name_stripped)
                    continue
                # 短比值残片（≤3字且结尾为"比"，如"酸比"，是比值指标被拆碎后的残片）
                if len(raw_name_stripped) <= 3 and raw_name_stripped.endswith('比'):
                    logger.debug("筛选: 短比值残片: %s", raw_name_stripped)
                    continue
                if raw_name_stripped.endswith('计）') or raw_name_stripped.endswith('计)'):
                    # 只过滤孤立的括号残片（如"以Pb计）"），名称中有开括号则是完整表达式（如"铅（以Pb计）"）
                    if '（' not in raw_name_stripped and '(' not in raw_name_stripped:
                        logger.debug("筛选: 括号残片: %s", raw_name_stripped)
                        continue

                # 过滤逻辑 1: 名称太短或太长
                if not raw_name or len(raw_name_stripped) < 1:
                    continue
                if len(raw_name_stripped) == 1:
                    # 单字项目：只有同行存在其他有效数据（检测方法/依据标准）时才保留
                    # 合法的元素名（铁、锌…）必然有对应的检测方法列；噪音字符通常没有
                    row_has_other_data = any(
                        v.strip()
                        for k, v in row.items()
                        if k != item_name_key and v.strip()
                    )
                    if not row_has_other_data:
                        logger.debug("筛选: 单字无附加数据: %s", raw_name_stripped)
                        continue
                if len(raw_name_stripped) > 50:  # 过滤掉长句子和说明文字
                    logger.debug("筛选: 名称过长(%d字符): %s...", len(raw_name_stripped), raw_name_stripped[:30])
                    continue

                # 过滤逻辑 2: 无效关键字过滤（说明行、占位符、目录等）
                # ─ 子串匹配（安全：这些词不会出现在合法指标名内部）
                invalid_substr_kw = [
                    "备注", "说明", "▲", "★", "类别", "分类", "序号", "检测项目",
                    "见下表", "目录", "页码", "附录", "参考",
                    "参见", "详见", "参照",
                    "补充", "额外",
                    "不适用", "不检测",
                    "明示标准",   # "按产品明示标准检验、判定" 类说明文字
                    "判定依据",   # 同上
                ]
                # ─ 精确匹配（单字/短词，用 in 会误伤"无机砷"、"铜及其化合物"等合法指标）
                invalid_exact_kw = {
                    "注", "无", "见", "如", "同", "及", "等", "共", "第",
                    "页", "表", "蔬菜", "依据", "标准", "方法", "单位", "限量", "指标",
                }

                if any(kw in raw_name for kw in invalid_substr_kw):
                    logger.debug("筛选: 含无效子串: %s", raw_name_stripped)
                    continue
                if raw_name_stripped in invalid_exact_kw:
                    logger.debug("筛选: 精确匹配无效词: %s", raw_name_stripped)
                    continue
                
                # 过滤逻辑 3: 排除纯数字
                if raw_name_stripped.isdigit():
                    continue
                
                # 过滤逻辑 4: 排除纯英文字母序号(如 "a", "b", "c")
                if re.match(r'^[a-zA-Z]$', raw_name_stripped):
                    logger.debug("筛选: 单字母序号: %s", raw_name_stripped)
                    continue
                
                # 过滤逻辑 5: 以标准前缀开头的通常是标准依据,不是项目名称
                # 很多时候表格解析错误,把第三列放到了第一列
                std_prefixes = ("GB", "NY", "SN", "DB", "GH", "QB", "SB", "SC", "HG", "LY", "WB", "WM", "T/", "Q/", "JJG", "ISO")
                if raw_name_stripped.upper().startswith(std_prefixes):
                     logger.debug("筛选: standard-like name: %s", raw_name_stripped)
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
                    # 例外1: 单字 CJK 矿物质/元素（钠、钾、铜、镁、锌、铁…）
                    # 已在上方单字检查中确认同行有检测方法数据才能走到这里
                    if len(raw_name_stripped) == 1 and len(chinese_chars) == 1:
                        pass  # 允许通过
                    # 例外2: 全大写化学物质英文名（DDT、BHC…）
                    elif raw_name_stripped.isupper() and 2 <= len(raw_name_stripped) <= 10:
                        pass  # 允许通过
                    # 例外3: 单字CJK元素名+括号单位（如"铅（以Pb计）"、"汞（以Hg计）"）
                    # 括号内为英文/数字的计量说明，核心名称只有1个CJK字符
                    elif (len(chinese_chars) == 1
                          and ('(' in raw_name_stripped or '（' in raw_name_stripped)
                          and re.search(r'以[A-Za-z]+计', raw_name_stripped)):
                        pass  # 允许通过
                    else:
                        logger.debug("筛选: 中文字符不足: %s", raw_name_stripped)
                        continue

                item["item_name"] = raw_name
                # 存储脚注条件（如果有）
                if _footnote_keys:
                    conditions = [footnote_defs[k] for k in _footnote_keys if k in footnote_defs]
                    item["footnote_keys"] = _footnote_keys
                    item["condition"] = "；".join(conditions) if conditions else ""
                else:
                    item["footnote_keys"] = []
                    item["condition"] = ""
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
            # 若有条件出现在该指标之前（pending），应用到刚加入的指标
            if _pending_condition and not items[-1].get("condition"):
                items[-1]["condition"] = _pending_condition
                _pending_condition = ""

        # 后处理：拆分包含多个项目名称的单元格
        # 例如："阿维菌素 哒螨灵" 应该拆分为两个独立项目
        expanded_items = []
        for item in items:
            item_name = item.get("item_name", "")

            # ── 复合指标保护 ─────────────────────────────────────────────────────
            # OCR 可能在"反式脂肪酸与总脂肪酸比值"中插入空格变成多个 part。
            # 先把空格合并后判断：如果整体是复合指标（比值/占比/之和），
            # 必须作为一个整体保留，不允许拆分。
            full_no_space = re.sub(r'\s+', '', item_name)
            if is_composite_indicator(full_no_space):
                item["item_name"] = full_no_space   # 同时消除 OCR 产生的空格
                expanded_items.append(item)
                logger.debug("复合指标保护: '%s' -> '%s'", item_name, full_no_space)
                continue
            # ─────────────────────────────────────────────────────────────────────

            # 含"或"的名称表示两种备选检测指标（如"黄曲霉毒素M1或黄曲霉毒素B1"），不拆分
            if '或' in item_name:
                expanded_items.append(item)
                continue

            # ── 括号内空格合并：PDF 换行在括号内留下空格，合并后再判断是否需要拆分 ──
            item_name = HtmlTableParser._collapse_spaces_in_brackets(item_name)
            item["item_name"] = item_name
            # ──────────────────────────────────────────────────────────────────────

            # 检测是否包含多个项目名称（通过空格分隔）
            parts = item_name.split()

            # 如果只有一个部分，直接保留
            if len(parts) <= 1:
                expanded_items.append(item)
                continue

            # 检查是否所有部分都是有效的项目名称
            # 增强过滤:排除括号片段、备注等
            valid_parts = []
            for p in parts:
                # valid_parts 中也做脚注字母剥离，防止 "比b" 这类噪音绕过初始过滤
                p = re.sub(r'(?<=[\u4e00-\u9fa5\d）)）])[a-z]+$', '', p)
                # 基本长度检查
                # 例外：单字 CJK 元素名（钠、钾、铜、镁等矿物质）
                is_single_cjk = len(p) == 1 and bool(re.match(r'[\u4e00-\u9fa5]', p))
                if not is_single_cjk and (len(p) < 2 or p.isdigit()):
                    continue
                
                # 过滤括号片段(如 "计)"、"量)"、"红）c")
                if p.endswith(')') or p.endswith('）'):
                    # 如果是完整的括号表达式(如 "（以Pb计）")则保留
                    if not (p.startswith('(') or p.startswith('（')):
                        continue
                
                # 过滤以括号开头但不完整的片段(如 "（以Pb")
                if (p.startswith('(') or p.startswith('（')) and not (p.endswith(')') or p.endswith('）')):
                    continue
                
                # 过滤纯符号或单字符（保留单字CJK矿物质名称，如铁、锌、铜、钠、钾）
                if not is_single_cjk and len(p.strip('()（）')) < 2:
                    continue
                
                # 过滤条件说明类文本（与主循环逻辑保持一致）
                if HtmlTableParser._is_condition_text(p):
                    continue
                # 过滤 "注：" 类注释标记
                if re.match(r'^注[：:]', p):
                    continue
                # 过滤短比值残片（≤3字且结尾为"比"，如"比"、"酸比"）
                if len(p) <= 3 and p.endswith('比'):
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
                # 只有一个有效部分：用清理后的值更新item_name（去掉了序号前缀等噪声）
                if valid_parts:
                    item["item_name"] = valid_parts[0]
                expanded_items.append(item)
            else:
                # ── 防拆分保护：若任意 part 的中文字符数 < 2，说明是名称被 OCR 断行切碎
                # 例："山梨酸及其钾 盐" → parts=["山梨酸及其钾","盐"]，"盐"只有1个中文字
                # 此时保留整体名称（已经过括号内空格合并），不拆分
                min_cjk = min(
                    len(re.findall(r'[\u4e00-\u9fa5]', p))
                    for p in valid_parts
                )
                if min_cjk < 2:
                    logger.debug("防拆分: part中文字符不足(%d)，保留整体: %s", min_cjk, item_name)
                    expanded_items.append(item)
                    continue
                # ──────────────────────────────────────────────────────────────────

                # 有多个有效部分，拆分为独立项目
                logger.debug("拆分: 多个项目名称: %s", valid_parts)
                
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
                    
                    logger.debug("拆分: 方法='%s', 提取%d个: %s", test_method[:60], len(method_parts), method_parts)
                
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
                        logger.debug("拆分: '%s' -> 方法: %s", part, item_method)
                    else:
                        item_method = test_method
                        logger.debug("拆分: '%s' 共享所有方法", part)
                    
                    new_item = {
                        "item_name": part,
                        "standard_basis": item_basis,
                        "test_method": item_method,
                        # 保留其他字段（来源信息、脚注条件等）
                        **{k: v for k, v in item.items() if k not in ["item_name", "standard_basis", "test_method"]}
                    }
                    expanded_items.append(new_item)

            
        return expanded_items
