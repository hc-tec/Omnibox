"""
LLM 意图分类器
使用 LLM 判断用户请求的意图类型，区分寒暄、简单查询和复杂研究
"""

import logging
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IntentClassification:
    """意图分类结果"""
    intent: str  # chitchat/simple_query/complex_research
    confidence: float
    reasoning: str


class LLMIntentClassifier:
    """
    使用 LLM 进行意图分类

    意图类型：
    - chitchat: 寒暄、问候、帮助请求、闲聊
    - simple_query: 单一数据源查询（如"B站热搜"）
    - complex_research: 复杂研究，需要多个数据源或深度分析
    """

    SYSTEM_PROMPT = """你是一个智能意图分类器，负责判断用户请求的类型。

**意图类型定义**：

1. **chitchat（寒暄/帮助）**
   - 问候语：你好、早上好、晚上好
   - 帮助请求：怎么用、能干什么、有什么功能
   - 感谢/告别：谢谢、再见、拜拜
   - 无明确查询目标的对话

2. **simple_query（简单查询）**
   - 明确的单一数据源查询
   - 特征：指定了平台/内容类型，查询目标单一
   - 示例："B站热搜"、"虎扑步行街最新帖子"、"GitHub trending"
   - 可以一次 RAG 调用完成

3. **complex_research（复杂研究）**
   - 需要多个数据源的对比/分析
   - 需要深度研究、趋势分析
   - 特征：包含"对比"、"分析"、"研究"等关键词，或需要多平台数据
   - 示例："对比B站和抖音的热门视频"、"分析最近一周GitHub的Python项目趋势"

**返回格式**：
必须返回严格的 JSON 格式，不要有任何额外文本：
```json
{
    "intent": "chitchat|simple_query|complex_research",
    "confidence": 0.0-1.0,
    "reasoning": "判断理由"
}
```

**判断原则**：
- 优先识别 chitchat（避免对寒暄触发数据查询）
- simple_query 和 complex_research 的区分：是否需要多个数据源或深度分析
- 置信度：明确匹配 0.9+，部分匹配 0.7-0.9，模糊匹配 0.5-0.7
"""

    def __init__(self, llm_client):
        """
        初始化 LLM 意图分类器

        Args:
            llm_client: LLM 客户端实例
        """
        self.llm_client = llm_client
        logger.info("LLMIntentClassifier 初始化完成")

    def classify(self, user_query: str) -> IntentClassification:
        """
        使用 LLM 判断用户查询的意图

        Args:
            user_query: 用户查询文本

        Returns:
            IntentClassification: 意图分类结果
        """
        try:
            # 构建 prompt
            user_prompt = f"用户请求：{user_query}"

            # 调用 LLM
            response = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # 低温度，保证分类稳定性
            )

            # 解析响应
            result = self._parse_response(response)

            logger.info(
                "意图分类完成: %s (置信度 %.2f) - %s",
                result.intent,
                result.confidence,
                result.reasoning
            )

            return result

        except Exception as exc:
            logger.error("意图分类失败: %s", exc, exc_info=True)
            # 降级：返回 simple_query，让后续流程处理
            return IntentClassification(
                intent="simple_query",
                confidence=0.5,
                reasoning=f"LLM 分类失败，降级为简单查询: {exc}"
            )

    def _parse_response(self, response: str) -> IntentClassification:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON
            response = response.strip()

            # 移除可能的 markdown 代码块标记
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1])

            # 解析 JSON
            data = json.loads(response)

            # 验证字段
            intent = data.get("intent", "simple_query")
            if intent not in ["chitchat", "simple_query", "complex_research"]:
                logger.warning(f"无效的意图类型: {intent}，降级为 simple_query")
                intent = "simple_query"

            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            reasoning = data.get("reasoning", "")

            return IntentClassification(
                intent=intent,
                confidence=confidence,
                reasoning=reasoning
            )

        except json.JSONDecodeError as exc:
            logger.warning("JSON 解析失败: %s，原始响应: %s", exc, response)
            # 降级策略：基于关键词判断
            return self._fallback_classify(response)

    def _fallback_classify(self, response: str) -> IntentClassification:
        """降级分类策略（基于关键词）"""
        response_lower = response.lower()

        # 检查是否包含意图关键词
        if any(word in response_lower for word in ["chitchat", "寒暄", "问候"]):
            return IntentClassification(
                intent="chitchat",
                confidence=0.6,
                reasoning="基于 LLM 响应内容判断为寒暄"
            )

        if any(word in response_lower for word in ["complex", "复杂", "research", "研究"]):
            return IntentClassification(
                intent="complex_research",
                confidence=0.6,
                reasoning="基于 LLM 响应内容判断为复杂研究"
            )

        # 默认为简单查询
        return IntentClassification(
            intent="simple_query",
            confidence=0.5,
            reasoning="无法解析 LLM 响应，降级为简单查询"
        )


# 全局单例（可选）
_classifier_instance: Optional[LLMIntentClassifier] = None


def get_llm_intent_classifier(llm_client=None) -> LLMIntentClassifier:
    """获取 LLM 意图分类器单例"""
    global _classifier_instance
    if _classifier_instance is None:
        if llm_client is None:
            raise ValueError("首次调用必须提供 llm_client")
        _classifier_instance = LLMIntentClassifier(llm_client)
    return _classifier_instance
