"""
RAGFlow Chat Client - 基于 Chat Completion API 的大模型增强检索
与 ragflow_client.py（向量检索）互补：
  - 向量检索 → 返回原始 chunks，适合结构化提取
  - Chat Completion → LLM 理解后合成答案，适合复杂语义查询
"""
import logging
import threading
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class RagflowChatClient:
    """
    封装 RAGFlow Chat Completion API。
    线程安全：每个实例维护一个 session，使用锁保护并发访问。
    """

    def __init__(self, address: str, chat_id: str, api_key: str,
                 session_name: str = "backend_session", max_messages: int = 50):
        """
        :param address: RAGFlow 服务地址（不含端口，如 "121.196.158.35"）
        :param chat_id:  RAGFlow 中配置好的 Chat 应用 ID
        :param api_key:  RAGFlow API Key
        :param session_name:   会话名称（用于复用已有会话）
        :param max_messages:   会话消息超过此数量时自动重建
        """
        self.address = address
        self.chat_id = chat_id
        self.api_key = api_key
        self.session_name = session_name
        self.max_messages = max_messages
        self._session_id: Optional[str] = None
        self._lock = threading.Lock()

        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def ask(self, question: str, timeout: int = 120,
            similarity_threshold: float = 0.2, top_k: int = 10) -> Optional[Dict[str, Any]]:
        """
        向 RAGFlow Chat 提问，返回 LLM 合成的答案。

        :param question: 查询问题
        :param timeout:  请求超时（秒）
        :param similarity_threshold: 向量检索相似度阈值
        :param top_k:    检索 top-k 片段数
        :return: {"answer": str, "reference": list} 或 None
        """
        with self._lock:
            session_id = self._get_or_create_session()
            if not session_id:
                logger.error("RagflowChatClient: 无法获取会话，跳过 chat 查询")
                return None

            result = self._completions(session_id, question, timeout,
                                       similarity_threshold, top_k)
            if result is None:
                return None

            # 检查会话是否需要重建
            self._check_and_rotate_session(session_id)
            return result

    # ------------------------------------------------------------------ #
    #  Session management                                                  #
    # ------------------------------------------------------------------ #

    def _get_or_create_session(self) -> Optional[str]:
        """返回可用的 session_id（复用已有或新建）。"""
        if self._session_id:
            return self._session_id

        # 先查已有会话
        sessions = self._list_sessions()
        for s in sessions:
            if s.get("name") == self.session_name:
                self._session_id = s["id"]
                logger.info("RagflowChatClient: 复用会话 %s", self._session_id)
                return self._session_id

        # 新建
        self._session_id = self._create_session()
        return self._session_id

    def _create_session(self) -> Optional[str]:
        url = f"http://{self.address}/api/v1/chats/{self.chat_id}/sessions"
        try:
            resp = requests.post(url, headers=self._headers,
                                 json={"name": self.session_name}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 0:
                sid = data["data"]["id"]
                logger.info("RagflowChatClient: 新建会话 %s", sid)
                return sid
            logger.warning("RagflowChatClient: 新建会话失败 %s", data.get("message"))
        except Exception as e:
            logger.error("RagflowChatClient: 新建会话异常 %s", e)
        return None

    def _list_sessions(self):
        url = f"http://{self.address}/api/v1/chats/{self.chat_id}/sessions"
        try:
            resp = requests.get(url, headers=self._headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", []) if data.get("code") == 0 else []
        except Exception as e:
            logger.warning("RagflowChatClient: 获取会话列表失败 %s", e)
            return []

    def _delete_session(self, session_id: str) -> bool:
        url = f"http://{self.address}/api/v1/chats/{self.chat_id}/sessions/{session_id}"
        try:
            resp = requests.delete(url, headers=self._headers, timeout=15)
            data = resp.json()
            ok = data.get("code") == 0
            if ok:
                logger.info("RagflowChatClient: 已删除会话 %s", session_id)
            return ok
        except Exception as e:
            logger.warning("RagflowChatClient: 删除会话失败 %s", e)
            return False

    def _get_message_count(self, session_id: str) -> int:
        url = (f"http://{self.address}/api/v1/chats/{self.chat_id}"
               f"/sessions/{session_id}/messages")
        try:
            resp = requests.get(url, headers=self._headers, timeout=15)
            data = resp.json()
            return len(data.get("data", [])) if data.get("code") == 0 else 0
        except Exception:
            return 0

    def _check_and_rotate_session(self, session_id: str):
        """若消息数超限则删除旧会话，下次自动新建。"""
        count = self._get_message_count(session_id)
        if count > self.max_messages:
            logger.info("RagflowChatClient: 消息数 %d 超限，重建会话", count)
            self._delete_session(session_id)
            self._session_id = None

    # ------------------------------------------------------------------ #
    #  Completions                                                         #
    # ------------------------------------------------------------------ #

    def _completions(self, session_id: str, question: str, timeout: int,
                     similarity_threshold: float, top_k: int) -> Optional[Dict[str, Any]]:
        url = f"http://{self.address}/api/v1/chats/{self.chat_id}/completions"
        payload = {
            "question": question,
            "session_id": session_id,
            "stream": False,
            "similarity_threshold": similarity_threshold,
            "top_k": top_k
        }
        print(f"\n{'─'*60}")
        print(f"[LLM调用] URL: {url}")
        print(f"[LLM调用] 发送问题（前300字）:\n{question[:300]}")
        print(f"{'─'*60}")
        try:
            resp = requests.post(url, headers=self._headers,
                                 json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 0:
                inner = data.get("data", {})
                answer = inner.get("answer", "")
                print(f"[LLM响应] code=0  答案（前200字）: {answer[:200]}")
                print(f"{'─'*60}\n")
                return {
                    "answer": answer,
                    "reference": inner.get("reference", [])
                }
            print(f"[LLM响应] code≠0  错误信息: {data.get('message')}")
            logger.warning("RagflowChatClient: completions 错误 %s", data.get("message"))
        except Exception as e:
            print(f"[LLM响应] 请求异常: {e}")
            logger.error("RagflowChatClient: completions 异常 %s", e)
        print(f"{'─'*60}\n")
        return None


# ------------------------------------------------------------------ #
#  全局单例                                                            #
# ------------------------------------------------------------------ #
_chat_client: Optional[RagflowChatClient] = None


def get_ragflow_chat_client(config: Dict[str, Any]) -> Optional[RagflowChatClient]:
    """
    获取 RagflowChatClient 单例。
    config 需包含：
      RAGFLOW_CHAT_ADDRESS  - 服务器地址（不带端口）
      RAGFLOW_CHAT_ID       - Chat 应用 ID
      RAGFLOW_API_KEY       - API Key（与检索共用）
    """
    global _chat_client
    if _chat_client is None:
        address = config.get("RAGFLOW_CHAT_ADDRESS")
        chat_id = config.get("RAGFLOW_CHAT_ID")
        api_key = config.get("RAGFLOW_API_KEY")

        if address and chat_id and api_key:
            _chat_client = RagflowChatClient(address, chat_id, api_key)
            print(f"[LLM初始化] RagflowChatClient 已创建: address={address} chat_id={chat_id}")
            logger.info("RagflowChatClient 初始化完成: address=%s chat_id=%s",
                        address, chat_id)
        else:
            print(f"[LLM初始化] ❌ 配置不完整 → address={address} chat_id={chat_id} api_key={'有' if api_key else '无'}")
            print(f"[LLM初始化]    config.local.json 需包含 RAGFLOW_CHAT_ADDRESS / RAGFLOW_CHAT_ID / RAGFLOW_API_KEY")
            logger.warning("RagflowChatClient 配置不完整，chat 增强功能不可用 "
                           "(需要 RAGFLOW_CHAT_ADDRESS / RAGFLOW_CHAT_ID / RAGFLOW_API_KEY)")
    return _chat_client
