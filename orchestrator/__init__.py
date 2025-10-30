"""
编排器（Orchestrator）
职责：协调RAG系统和查询处理器，实现完整的RAG-in-Action流程

流程：
1. 用户输入 → RAG系统检索 → 获取相关路由定义
2. 路由定义 + 用户输入 → 查询处理器 → 结构化API调用指令
3. 返回可执行的API调用结果
"""

__version__ = "1.0.0"
__all__ = ["RAGInAction", "ConversationManager"]
