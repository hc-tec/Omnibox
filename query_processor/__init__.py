"""
查询处理器（Query Processor）
职责：将自然语言查询 + 路由定义 → 结构化的API调用指令

模块说明：
- llm_client.py: LLM客户端抽象层（支持OpenAI、Anthropic等）
- prompt_builder.py: 构建给LLM的Prompt
- parser.py: 解析LLM返回的结果
- path_builder.py: 根据参数构建完整的URL路径
"""

__version__ = "1.0.0"
__all__ = [
    "LLMClient",
    "PromptBuilder",
    "QueryParser",
    "PathBuilder",
]
