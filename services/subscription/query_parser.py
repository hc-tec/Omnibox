"""订阅查询解析器

使用 LLM 将自然语言查询解析为结构化的订阅查询。

示例：
- 输入："科技美学的最新投稿"
- 输出：ParsedQuery(entity_name="科技美学", action="投稿视频", platform="bilibili", confidence=0.9)
"""

import logging
import json
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ParsedQuery(BaseModel):
    """解析后的查询结果"""

    entity_name: str = Field(
        ...,
        description="实体名称（UP主、专栏、仓库等）"
    )
    action: Optional[str] = Field(
        None,
        description="用户想查看的动作（投稿视频、关注列表、commits 等）"
    )
    platform: Optional[str] = Field(
        None,
        description="平台（bilibili/zhihu/weibo/github 等）"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="解析置信度（0.0-1.0）"
    )


class QueryParser:
    """查询解析器（LLM 驱动）

    将自然语言查询解析为结构化信息，提取实体名称、动作和平台。
    """

    SYSTEM_PROMPT = """你是一个订阅查询解析助手。

用户会输入对订阅内容的查询，你需要提取：
1. **entity_name**: 实体名称（UP主、专栏、仓库等）
2. **action**: 用户想查看的动作（可选）
3. **platform**: 平台（可选，如果能推断出来）
4. **confidence**: 解析置信度（0.0-1.0）

**平台识别规则**：
- B站/bilibili/哔哩哔哩 → "bilibili"
- 知乎 → "zhihu"
- 微博 → "weibo"
- GitHub/github → "github"
- Gitee/gitee → "gitee"

**动作识别规则**：
- 投稿/视频/作品 → "投稿视频"
- 关注/following → "关注列表"
- 收藏/favorites → "收藏"
- 动态/dynamics → "动态"
- 文章/专栏 → "文章"
- commits/提交 → "commits"
- issues → "issues"
- pull requests/pr → "pull_requests"
- releases/发布 → "releases"

**示例**：

输入："科技美学的最新投稿"
输出：
```json
{
    "entity_name": "科技美学",
    "action": "投稿视频",
    "platform": "bilibili",
    "confidence": 0.9
}
```

输入："少数派专栏的文章"
输出：
```json
{
    "entity_name": "少数派",
    "action": "文章",
    "platform": "zhihu",
    "confidence": 0.9
}
```

输入："langchain的最新commits"
输出：
```json
{
    "entity_name": "langchain",
    "action": "commits",
    "platform": "github",
    "confidence": 0.85
}
```

输入："那岩"（只有实体名称）
输出：
```json
{
    "entity_name": "那岩",
    "action": null,
    "platform": null,
    "confidence": 0.7
}
```

**重要**：
- 必须返回严格的 JSON 格式
- 不要添加任何额外的文本或解释
- 如果无法推断某个字段，使用 null
- confidence 范围：完全确定=0.9+，基本确定=0.7-0.9，不太确定=0.5-0.7
"""

    def __init__(self, llm_client):
        """初始化查询解析器

        Args:
            llm_client: LLM 客户端实例（支持 chat() 方法）
        """
        self.llm_client = llm_client
        logger.info("QueryParser 初始化完成")

    def parse(self, query: str) -> ParsedQuery:
        """解析查询

        Args:
            query: 用户输入的自然语言查询

        Returns:
            ParsedQuery: 解析后的结构化查询

        Raises:
            ValueError: 解析失败时抛出
        """
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"用户查询：{query}"}
        ]

        try:
            # 调用 LLM 解析
            response = self.llm_client.chat(
                messages=messages,
                temperature=0.1  # 低温度，追求确定性
            )

            logger.debug(f"LLM 原始响应: {response}")

            # 解析 JSON 响应
            result = json.loads(response)

            # 验证必需字段
            if "entity_name" not in result:
                raise ValueError("LLM 响应缺少 entity_name 字段")

            # 构建 ParsedQuery 对象
            parsed = ParsedQuery(
                entity_name=result["entity_name"],
                action=result.get("action"),
                platform=result.get("platform"),
                confidence=result.get("confidence", 0.8)
            )

            logger.info(
                f"解析成功: query='{query}' → "
                f"entity='{parsed.entity_name}', action='{parsed.action}', "
                f"platform='{parsed.platform}', confidence={parsed.confidence}"
            )

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"LLM 响应不是有效的 JSON: {response}")
            raise ValueError(f"LLM 响应格式错误: {e}") from e

        except Exception as e:
            logger.error(f"解析查询失败: {e}")
            raise ValueError(f"解析查询失败: {e}") from e
