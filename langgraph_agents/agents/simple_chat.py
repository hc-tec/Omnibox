"""SimpleChatNode 节点实现

用于处理 simple_tool_call 路由的简单查询。
这些查询不需要多步骤研究，可以直接响应。
"""
from typing import Dict

from ..state import GraphState


def create_simple_chat_node():
    """
    创建简单对话节点。

    TODO: 未来需要与 ChatService 集成，目前返回占位符响应。

    处理场景：
    - 简单问候（"你好"）
    - 单次查询（"今天天气"）
    - 不需要工具调用的问答

    集成方案：
    ```python
    from services.chat_service import ChatService

    def node(state: GraphState) -> Dict[str, str]:
        query = state["original_query"]
        chat_service = ChatService()
        response = chat_service.handle(query)
        return {"final_report": response}
    ```
    """

    def node(state: GraphState) -> Dict[str, str]:
        query = state.get("original_query", "")

        # TODO: 未来集成 ChatService
        # 目前返回占位符响应
        simple_response = {
            "type": "simple_response",
            "query": query,
            "message": "简单查询路由已就绪，等待与 ChatService 集成",
            "note": "这是一个架构占位符实现",
        }

        import json

        return {"final_report": json.dumps(simple_response, ensure_ascii=False, indent=2)}

    return node
