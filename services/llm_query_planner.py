"""
LLM 查询规划器
分析复杂查询，分解为多个独立的子查询任务
"""

import logging
import json
from typing import List, Dict, Any, Optional, Sequence
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SubQuery:
    """子查询定义"""
    query: str  # 查询文本
    datasource: Optional[str] = None  # 目标数据源（可选）
    priority: int = 1  # 优先级（1=最高）
    reasoning: str = ""  # 为什么需要这个子查询


@dataclass
class QueryPlan:
    """查询计划"""
    sub_queries: List[SubQuery]
    reasoning: str  # 整体规划理由
    estimated_time: Optional[int] = None  # 预估耗时（秒）
    debug: Dict[str, Any] = field(default_factory=dict)


class LLMQueryPlanner:
    """
    使用 LLM 规划复杂查询

    功能：
    1. 分析用户的复杂查询意图
    2. 分解为多个独立的子查询
    3. 为每个子查询指定数据源和优先级
    """

    SYSTEM_PROMPT = """你是一个智能查询规划器，负责将复杂的用户查询分解为多个独立的子查询任务。

**可用的数据源平台**：
- bilibili / b站：视频、动态、排行榜、热搜
- douyin / 抖音：视频、热点
- weibo / 微博：热搜、博文
- zhihu / 知乎：问答、热榜
- github：仓库、趋势、issues
- hupu / 虎扑：帖子、步行街
- v2ex：帖子、节点
- douban / 豆瓣：影评、书评

**规划原则**：
1. 识别用户查询涉及的**所有数据源**
2. 对比类查询：需要查询所有被对比的平台
3. 分析类查询：需要查询相关的多个维度数据
4. 每个子查询应该是**独立的、可并行执行的**
5. 限制子查询数量：最多 5 个（避免过度拆分）

**返回格式**：
必须返回严格的 JSON 格式：
```json
{
    "sub_queries": [
        {
            "query": "具体的查询文本",
            "datasource": "平台名称（可选）",
            "priority": 1,
            "reasoning": "为什么需要这个子查询"
        }
    ],
    "reasoning": "整体规划理由",
    "estimated_time": 预估耗时秒数
}
```

**示例 1 - 对比查询**：
输入："对比B站和抖音的热门视频"
输出：
```json
{
    "sub_queries": [
        {
            "query": "B站热门视频排行榜",
            "datasource": "bilibili",
            "priority": 1,
            "reasoning": "需要获取B站的热门视频数据"
        },
        {
            "query": "抖音热门视频排行",
            "datasource": "douyin",
            "priority": 1,
            "reasoning": "需要获取抖音的热门视频数据"
        }
    ],
    "reasoning": "对比查询需要分别获取两个平台的热门视频数据",
    "estimated_time": 15
}
```

**示例 2 - 趋势分析**：
输入："分析最近一周GitHub上Python和JavaScript项目的趋势"
输出：
```json
{
    "sub_queries": [
        {
            "query": "GitHub Python 项目最近一周趋势",
            "datasource": "github",
            "priority": 1,
            "reasoning": "获取 Python 语言的项目趋势数据"
        },
        {
            "query": "GitHub JavaScript 项目最近一周趋势",
            "datasource": "github",
            "priority": 1,
            "reasoning": "获取 JavaScript 语言的项目趋势数据"
        }
    ],
    "reasoning": "需要分别查询两种编程语言的项目趋势进行对比分析",
    "estimated_time": 20
}
```

**注意**：
- 如果查询已经足够具体，不需要拆分，返回单个子查询即可
- datasource 可以省略，让 RAG 系统自动识别
- priority 用于控制执行顺序（目前暂未使用，默认并行）
"""

    def __init__(self, llm_client):
        """
        初始化 LLM 查询规划器

        Args:
            llm_client: LLM 客户端实例
        """
        self.llm_client = llm_client
        logger.info("LLMQueryPlanner 初始化完成")

    def plan(self, user_query: str) -> QueryPlan:
        """
        规划复杂查询，分解为子查询列表

        Args:
            user_query: 用户查询文本

        Returns:
            QueryPlan: 查询计划
        """
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"用户查询：{user_query}\n\n请规划查询方案。"},
        ]

        try:
            response = self.llm_client.chat(
                messages=messages,
                temperature=0.2,
            )

            plan = self._parse_response(response, user_query)
            plan.debug.update(self._build_debug_entry(messages, response))

            logger.info(
                "查询规划完成: %d 个子查询 - %s",
                len(plan.sub_queries),
                plan.reasoning
            )

            for idx, sub_query in enumerate(plan.sub_queries, start=1):
                logger.debug(
                    "  子查询 %d: %s (datasource=%s)",
                    idx,
                    sub_query.query,
                    sub_query.datasource or "auto"
                )

            return plan

        except Exception as exc:
            logger.error("查询规划失败: %s", exc, exc_info=True)
            fallback_plan = QueryPlan(
                sub_queries=[SubQuery(
                    query=user_query,
                    datasource=None,
                    priority=1,
                    reasoning=f"LLM 规划失败，使用原始查询: {exc}"
                )],
                reasoning="降级策略：使用原始查询",
            )
            fallback_plan.debug.update(self._build_debug_entry(messages, response=None, error=str(exc)))
            return fallback_plan

    def _parse_response(self, response: str, original_query: str) -> QueryPlan:
        """解析 LLM 响应"""
        try:
            # 移除可能的 markdown 代码块标记
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                # 找到第一个和最后一个 ``` 之间的内容
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block:
                        json_lines.append(line)
                response = "\n".join(json_lines)

            # 解析 JSON
            data = json.loads(response)

            # 解析子查询列表
            sub_queries = []
            for item in data.get("sub_queries", []):
                sub_queries.append(SubQuery(
                    query=item.get("query", original_query),
                    datasource=item.get("datasource"),
                    priority=item.get("priority", 1),
                    reasoning=item.get("reasoning", "")
                ))

            # 验证：至少要有一个子查询
            if not sub_queries:
                logger.warning("LLM 返回的子查询列表为空，使用原始查询")
                sub_queries = [SubQuery(
                    query=original_query,
                    datasource=None,
                    priority=1,
                    reasoning="LLM 未返回子查询，使用原始查询"
                )]

            # 限制子查询数量
            if len(sub_queries) > 5:
                logger.warning(f"子查询数量过多 ({len(sub_queries)})，限制为前 5 个")
                sub_queries = sub_queries[:5]

            return QueryPlan(
                sub_queries=sub_queries,
                reasoning=data.get("reasoning", ""),
                estimated_time=data.get("estimated_time")
            )

        except json.JSONDecodeError as exc:
            logger.warning("JSON 解析失败: %s，原始响应: %s", exc, response[:200])
            # 降级：返回原始查询
            return QueryPlan(
                sub_queries=[SubQuery(
                    query=original_query,
                    datasource=None,
                    priority=1,
                    reasoning="JSON 解析失败，使用原始查询"
                )],
                reasoning="降级策略：JSON 解析失败"
            )

    def _build_debug_entry(
        self,
        messages: Sequence[Dict[str, str]],
        response: Optional[str],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        preview_messages = [
            {
                "role": message.get("role"),
                "content": self._trim(message.get("content", "")),
            }
            for message in messages
        ]
        entry: Dict[str, Any] = {
            "stage": "query_planner",
            "provider": getattr(self.llm_client, "model_name", self.llm_client.__class__.__name__),
            "messages": preview_messages,
        }
        if response is not None:
            entry["response"] = self._trim(response, limit=800)
        if error:
            entry["error"] = error
        return entry

    @staticmethod
    def _trim(text: str, limit: int = 400) -> str:
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."


# 全局单例（可选）
_planner_instance: Optional[LLMQueryPlanner] = None


def get_llm_query_planner(llm_client=None) -> LLMQueryPlanner:
    """获取 LLM 查询规划器单例"""
    global _planner_instance
    if _planner_instance is None:
        if llm_client is None:
            raise ValueError("首次调用必须提供 llm_client")
        _planner_instance = LLMQueryPlanner(llm_client)
    return _planner_instance
