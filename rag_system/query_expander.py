"""
查询扩展器
职责：在 RAG 检索前，使用 LLM 将用户查询扩展为包含平台/功能关键词的形式

解决问题：
- 用户查询"影视飓风最近发的视频"无法匹配到"UP 主投稿"路由
- 因为 RAG 向量模型不知道"影视飓风"是一个 B 站 UP 主

解决方案：
- 使用 LLM 识别查询中的隐含平台和意图
- 将原始查询扩展为"bilibili B站 UP主 视频投稿 影视飓风"这样的形式
"""
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# 查询扩展 Prompt 模板
QUERY_EXPANSION_PROMPT = """你是一个查询扩展助手，负责将用户的自然语言查询扩展为更适合向量检索的形式。

# 任务
分析用户查询，识别其中隐含的平台和功能意图，然后生成扩展后的查询。

# 扩展规则
1. **识别平台**：如果提到某个内容创作者/UP主/博主，推断对应的平台
   - 影视飓风、何同学、老师好我叫何同学 → bilibili B站
   - 科技美学、TESTV → bilibili B站
   - 李永乐老师 → bilibili B站 / YouTube

2. **识别功能**：根据用户意图推断功能类型
   - "视频"、"投稿"、"发的" → UP主投稿、用户视频
   - "热搜"、"热门" → 热搜榜、热门
   - "动态" → 用户动态
   - "关注的" → 关注列表

3. **保留原始实体**：保留用户提到的具体名称（如 UP 主名字）

4. **输出格式**：直接输出扩展后的查询字符串，不要有任何解释

# 示例

用户查询：看看影视飓风最近发的视频
扩展查询：bilibili B站 UP主投稿 用户视频 影视飓风

用户查询：何同学的视频
扩展查询：bilibili B站 UP主投稿 用户视频 何同学

用户查询：B站热搜
扩展查询：bilibili B站 热搜榜 热搜

用户查询：虎扑步行街最新帖子
扩展查询：虎扑 论坛 社区 帖子 步行街 最新

用户查询：GitHub trending
扩展查询：GitHub 热门 趋势 trending 仓库

# 现在扩展以下查询

用户查询：{query}
扩展查询："""


@dataclass
class QueryExpansionResult:
    """查询扩展结果"""
    original_query: str
    expanded_query: str
    used_llm: bool


class QueryExpander:
    """
    查询扩展器

    使用 LLM 将用户查询扩展为更适合向量检索的形式。
    """

    def __init__(self, llm_client=None):
        """
        初始化查询扩展器

        Args:
            llm_client: LLM 客户端（可选，如果不提供则不进行扩展）
        """
        self.llm_client = llm_client

    def expand(
        self,
        query: str,
        use_cache: bool = True,
        timeout: float = 5.0
    ) -> QueryExpansionResult:
        """
        扩展用户查询

        Args:
            query: 原始用户查询
            use_cache: 是否使用缓存（预留）
            timeout: LLM 调用超时时间（秒）

        Returns:
            QueryExpansionResult 包含原始查询和扩展后的查询
        """
        # 如果没有 LLM 客户端，直接返回原始查询
        if self.llm_client is None:
            logger.debug("QueryExpander: 没有 LLM 客户端，跳过扩展")
            return QueryExpansionResult(
                original_query=query,
                expanded_query=query,
                used_llm=False
            )

        # 检查是否需要扩展
        # 如果查询已经包含明确的平台关键词，可能不需要扩展
        if self._should_skip_expansion(query):
            logger.debug(f"QueryExpander: 查询已包含平台关键词，跳过扩展: {query}")
            return QueryExpansionResult(
                original_query=query,
                expanded_query=query,
                used_llm=False
            )

        try:
            # 构建 Prompt
            prompt = QUERY_EXPANSION_PROMPT.format(query=query)

            # 调用 LLM
            expanded = self.llm_client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=200,
            )

            # 清理结果
            expanded = expanded.strip()

            # 验证结果
            if not expanded or len(expanded) < 3:
                logger.warning(f"QueryExpander: LLM 返回空结果，使用原始查询")
                return QueryExpansionResult(
                    original_query=query,
                    expanded_query=query,
                    used_llm=True
                )

            logger.info(f"QueryExpander: '{query}' -> '{expanded}'")

            return QueryExpansionResult(
                original_query=query,
                expanded_query=expanded,
                used_llm=True
            )

        except Exception as e:
            # LLM 调用失败，降级使用原始查询
            logger.warning(f"QueryExpander: LLM 调用失败，使用原始查询: {e}")
            return QueryExpansionResult(
                original_query=query,
                expanded_query=query,
                used_llm=False
            )

    def _should_skip_expansion(self, query: str) -> bool:
        """
        检查是否应该跳过查询扩展

        如果查询已经包含明确的平台关键词，可能不需要扩展。

        Args:
            query: 用户查询

        Returns:
            是否跳过扩展
        """
        # 已经包含平台关键词的查询
        platform_keywords = [
            'bilibili', 'b站', 'B站', '哔哩哔哩',
            'github', 'GitHub',
            '虎扑', 'hupu',
            '知乎', 'zhihu',
            '微博', 'weibo',
            '豆瓣', 'douban',
            '小红书', 'xiaohongshu',
            'youtube', 'YouTube',
        ]

        query_lower = query.lower()
        for keyword in platform_keywords:
            if keyword.lower() in query_lower:
                return True

        return False


# 便捷函数
def expand_query(query: str, llm_client=None) -> str:
    """
    便捷函数：扩展查询

    Args:
        query: 原始查询
        llm_client: LLM 客户端

    Returns:
        扩展后的查询
    """
    expander = QueryExpander(llm_client=llm_client)
    result = expander.expand(query)
    return result.expanded_query
