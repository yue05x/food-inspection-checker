import requests
import json
import re
from typing import List, Dict, Any, Optional

class RAGFlowClient:
    def __init__(self, api_url: str, api_key: str, kb_id: str):
        """
        初始化 RAGFlow 客户端
        :param api_url: RAGFlow API 地址
        :param api_key: API 密钥
        :param kb_id: 知识库 ID
        """
        self.api_url = api_url
        self.api_key = api_key
        self.kb_id = kb_id
        # 使用官方 API 格式: Bearer 认证
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 调试输出
        print(f"RAGFlowClient 初始化: URL={self.api_url}, KB_ID={self.kb_id}")

    def query_inspection_items(self, food_name: str, custom_query: str = None) -> List[Dict[str, Any]]:
        """
        查询食品检验项目
        :param food_name: 食品名称
        :param custom_query: 自定义查询语句(可选,用于优化查询)
        """
        # 使用自定义查询或默认查询
        question = custom_query if custom_query else f"{food_name}检验项目"
        return self._search(question)

    def query_test_methods(self, item_name: str) -> List[Dict[str, Any]]:
        """
        查询检验方法
        """
        question = f"{item_name}检测方法"
        return self._search(question)

    def query_gb_standards(self, standard_num: str) -> List[Dict[str, Any]]:
        """
        查询国标内容
        """
        question = f"GB {standard_num}"
        return self._search(question)
        
    def query_standard_limit(self, standard_code: str, item_name: str, kb_id: str = None) -> List[Dict[str, Any]]:
        """
        查询标准中的具体指标限量
        """
        # 构建更精确的查询词
        # 尝试包含 "限量", "指标", "要求" 等词汇
        question = f"{standard_code} {item_name} 标准限量 指标要求"
        return self._search(question, kb_id=kb_id)

    def query_standard_indicators(self, food_name: str, item_name: str, standard_code: str = None, kb_id: str = None) -> List[Dict[str, Any]]:
        """
        查询标准指标 (app.py API 兼容方法的别名)
        """
        code = standard_code if standard_code else "GB 2763"
        return self.query_standard_limit(code, item_name, kb_id=kb_id)

    def query(self, question: str, dataset_ids: List[str] = None, page_size: int = 30) -> List[Dict[str, Any]]:
        """
        通用查询方法
        :param question: 查询问题
        :param dataset_ids: 知识库 ID 列表 (可选，默认为 self.kb_id)
        :param page_size: 返回结果数量
        """
        target_kb_ids = dataset_ids if dataset_ids else [self.kb_id]
        
        # 复用 _search 逻辑，由于 _search 目前只支持单个 kb_id 参数，我们需要略微修改 _search 或者直接在这里实现
        # 为了不破坏现有逻辑，我们直接在这里调用底层请求，或者增强 _search
        # 考虑到 _search 比较复杂（重试、代理），最好增强 _search
        
        return self._search(question, dataset_ids=target_kb_ids, page_size=page_size)

    def _search(self, question: str, kb_id: str = None, dataset_ids: List[str] = None, page_size: int = 30) -> List[Dict[str, Any]]:
        """
        执行 RAGFlow 搜索 (使用官方 API 格式)
        :param kb_id: 可选，已废弃，兼容旧代码
        :param dataset_ids: 知识库 ID 列表
        :param page_size: 页大小
        """
        # 确定 dataset_ids
        target_ids = dataset_ids
        if not target_ids:
            if kb_id:
                target_ids = [kb_id]
            else:
                target_ids = [self.kb_id]
        
        # 使用官方 API 参数格式
        data = {
            "question": question,
            "dataset_ids": target_ids,
            "page": 1,
            "page_size": page_size
        }

        try:
            print(f"正在查询 RAGFlow: {question}")
            
            # 添加重试机制
            max_retries = 2
            retry_count = 0
            last_error = None
            
            while retry_count <= max_retries:
                try:
                    # 调试输出
                    print(f"DEBUG: 请求 URL: {self.api_url}")
                    print(f"DEBUG: 请求数据: {json.dumps(data, ensure_ascii=False)}")
                    print(f"DEBUG: 请求头: {self.headers}")
                    
                    # 使用系统代理设置（已配置例外地址），增加超时时间到 60 秒
                    # 强制绕过代理访问 RagFlow
                    import os
                    os.environ['NO_PROXY'] = '218.244.149.115,47.110.141.115,localhost,127.0.0.1'

                    response = requests.post(
                        self.api_url,
                        json=data,
                        headers=self.headers,
                        timeout=60,  # 增加到 60 秒
                        proxies={'http': None, 'https': None}  # 明确禁用代理
                    )
                    
                    # 成功获取响应,跳出重试循环
                    break
                    
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    last_error = e
                    retry_count += 1
                    if retry_count <= max_retries:
                        print(f"RAGFlow 连接失败,正在重试 ({retry_count}/{max_retries})...")
                        import time
                        time.sleep(2)  # 等待 2 秒后重试
                    else:
                        print(f"RAGFlow 连接失败,已达到最大重试次数")
                        raise
            
            if response.status_code == 200:
                result = response.json()
                # 检查 RAGFlow 官方 API 响应结构 (code=0 表示成功)
                if result.get("code") == 0:
                    # 官方 API 响应格式: {"code": 0, "data": {"chunks": [...], "total": N}}
                    chunks = result.get("data", {}).get("chunks", [])
                    total = result.get("data", {}).get("total", 0)
                    print(f"RAGFlow 查询成功: 找到 {len(chunks)} 个结果")
                    return self._process_results(chunks)
                else:
                    print(f"RAGFlow API 错误: {result}")
                    return []
            else:
                print(f"RAGFlow HTTP 错误: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"RAGFlow 请求异常: {str(e)}")
            return []

    def _process_results(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        处理搜索结果，提取页码和内容
        """
        processed_results = []
        
        for chunk in chunks:
            # 官方 API 字段: content, content_ltks, content_with_weight
            content = chunk.get("content", "")
            if not content:
                content = chunk.get("content_with_weight", "")
            if not content:
                content = chunk.get("content_ltks", "")  # 备用字段
            
            # 提取页码
            # RAGFlow 官方 API 的页码在 positions 字段中
            # positions 格式: [[page, x, y, width, height], ...]
            page_num = None
            positions = chunk.get("positions", [])
            if positions and len(positions) > 0 and len(positions[0]) > 0:
                page_num = positions[0][0]  # 第一个position的第一个值是页码
            
            # 备用方案:尝试其他字段
            if page_num is None:
                page_num = chunk.get("page_num") or chunk.get("page_num_int")
                
            processed_results.append({
                "content": content,
                "score": chunk.get("similarity", 0),
                "chunk_id": chunk.get("id", chunk.get("chunk_id", "")),  # 官方 API 使用 id
                "doc_name": chunk.get("document_keyword", chunk.get("docnm_kwd", "")),  # 官方 API 字段
                "document_id": chunk.get("document_id", ""),
                "page_num": page_num or 1  # 默认为 1
            })
            
        return processed_results

# 全局单例
_ragflow_client = None

def get_ragflow_client(config: Dict[str, Any]) -> Optional[RAGFlowClient]:
    """
    获取 RAGFlowClient 单例
    """
    global _ragflow_client
    
    if _ragflow_client is None:
        api_url = config.get("RAGFLOW_API_URL")
        api_key = config.get("RAGFLOW_API_KEY")
        kb_id = config.get("RAGFLOW_KB_ID")
        
        if api_url and api_key and kb_id:
            _ragflow_client = RAGFlowClient(api_url, api_key, kb_id)
        else:
            print("RAGFlow 配置不完整，无法初始化客户端")
            
    return _ragflow_client
