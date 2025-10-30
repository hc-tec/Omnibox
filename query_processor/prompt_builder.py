"""
Prompt构建器
职责：根据工具定义和用户查询构建给LLM的Prompt
"""
import json
from typing import List, Dict, Any, Optional


# 标准Prompt模板
STANDARD_PROMPT_TEMPLATE = """你是一个智能API调用助手，负责将用户的自然语言请求转换为结构化的API调用。

# 1. 可用的工具 (API)

以下是通过RAG检索到的最相关工具定义：

{tools_json}

# 2. 用户的请求

用户输入：{user_query}

# 3. 你的任务

请严格按照以下步骤分析：

**步骤1: 意图分析**
- 用户的请求是否与提供的工具(API)匹配？
- 如果有多个工具，选择最匹配的那个

**步骤2: 参数提取**
- 从用户的请求中提取所有可以填充到API参数的值
- 仔细检查每个参数的描述和可选值

**步骤3: 逻辑推理**
- 如果用户提到了一个值（如"最新发布"），在 `parameters.options` 中找到对应的 `value`（如 '1'）
- 如果用户提到了一个实体（如"步行街"），尝试匹配到对应参数（如 `id`）
- 如果无法确定参数值，使用 `default_value`
- 如果缺少必需参数或意图不明确，设置 `status` 为 `needs_clarification`

**步骤4: 路径生成**
- 根据 `path_template` 和提取的参数，生成完整的URL路径
- 路径格式：`/{{provider}}/{{route_path}}`，其中参数用实际值替换

# 4. 输出格式

你**必须**且**只能**返回一个JSON对象，**不要**包含任何 "```json" 标记或其他解释文字。

JSON结构如下：

{{
  "status": "success" | "needs_clarification" | "not_found",
  "reasoning": "你的分析推理过程（简短说明）",
  "selected_tool": {{
    "route_id": "选中的路由ID",
    "provider": "数据源标识",
    "name": "功能名称"
  }},
  "path_template": "选中的路径模板",
  "generated_path": "生成的完整路径（如 /hupu/bbs/bxj/1）",
  "parameters_filled": {{
    "参数名": "参数值"
  }},
  "clarification_question": "如果需要澄清，在这里提问（否则为null）"
}}

**状态说明：**
- `success`: 成功匹配并提取了所有必要参数
- `needs_clarification`: 需要用户提供更多信息
- `not_found`: 提供的工具都不匹配用户需求

# 5. 示例

**示例1：成功匹配**
用户输入："帮我看看虎扑步行街今天最新发布的帖子"

输出：
{{
  "status": "success",
  "reasoning": "用户请求虎扑社区的帖子。'步行街'对应id参数（默认值'#步行街主干道'）。'最新发布'对应order参数的'1'。",
  "selected_tool": {{
    "route_id": "hupu_bbs",
    "provider": "hupu",
    "name": "社区"
  }},
  "path_template": "/bbs/:id?/:order?",
  "generated_path": "/hupu/bbs/#步行街主干道/1",
  "parameters_filled": {{
    "id": "#步行街主干道",
    "order": "1"
  }},
  "clarification_question": null
}}

**示例2：需要澄清**
用户输入："给我看看帖子"

输出：
{{
  "status": "needs_clarification",
  "reasoning": "用户未指定具体平台，无法确定使用哪个API。",
  "selected_tool": null,
  "path_template": null,
  "generated_path": null,
  "parameters_filled": {{}},
  "clarification_question": "您想查看哪个平台的帖子？我找到了：虎扑社区、知乎、微博等。"
}}

# 现在开始分析

请直接输出JSON，不要有任何额外文字："""


# 简化版Prompt（适用于性能较弱的LLM）
SIMPLE_PROMPT_TEMPLATE = """将用户请求转换为API调用。

工具定义：
{tools_json}

用户请求：{user_query}

分析并输出JSON（不要包含```json标记）：
{{
  "status": "success/needs_clarification/not_found",
  "reasoning": "分析说明",
  "selected_tool": {{"route_id": "...", "provider": "...", "name": "..."}},
  "generated_path": "/provider/path/...",
  "parameters_filled": {{"param": "value"}},
  "clarification_question": null
}}

输出："""


class PromptBuilder:
    """Prompt构建器"""

    def __init__(
        self,
        max_tools: int = 3,
        max_tool_length: int = 2000,
        use_simple_prompt: bool = False,
    ):
        """
        初始化Prompt构建器

        Args:
            max_tools: 最多向LLM展示几个工具
            max_tool_length: 单个工具JSON的最大长度
            use_simple_prompt: 是否使用简化版Prompt
        """
        self.max_tools = max_tools
        self.max_tool_length = max_tool_length
        self.template = SIMPLE_PROMPT_TEMPLATE if use_simple_prompt else STANDARD_PROMPT_TEMPLATE
        self._max_field_length = max(200, max_tool_length // 2)
        self._max_list_items = 10

    def build(
        self,
        user_query: str,
        tools: List[Dict[str, Any]],
    ) -> str:
        """
        构建完整的Prompt

        Args:
            user_query: 用户查询
            tools: 工具定义列表（来自RAG检索）

        Returns:
            完整的prompt字符串
        """
        # 格式化工具定义
        tools_json = self._format_tools(tools)

        # 填充模板
        prompt = self.template.format(
            user_query=user_query,
            tools_json=tools_json,
        )

        return prompt

    def _format_tools(self, tools: List[Dict[str, Any]]) -> str:
        """
        格式化工具定义为JSON字符串

        Args:
            tools: 工具定义列表

        Returns:
            格式化的JSON字符串
        """
        formatted_tools = []

        for i, tool in enumerate(tools[:self.max_tools], 1):
            # 提取关键字段
            essential_fields = {
                "route_id": tool.get("route_id"),
                "provider": tool.get("datasource") or tool.get("provider_id"),
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "path_template": tool.get("path_template"),
                "parameters": tool.get("parameters", []),
                "categories": tool.get("categories", []),
            }

            trimmed_fields = self._trim_tool_fields(essential_fields)

            # 转为JSON
            tool_json = json.dumps(trimmed_fields, ensure_ascii=False, indent=2)

            # 如果仍然超长，则提示而不是截断JSON结构
            if len(tool_json) > self.max_tool_length:
                tool_json = json.dumps(
                    {
                        "route_id": trimmed_fields.get("route_id"),
                        "provider": trimmed_fields.get("provider"),
                        "name": trimmed_fields.get("name"),
                        "warning": "工具定义过长，部分内容已省略",
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            formatted_tools.append(f"## 工具 {i}\n\n{tool_json}")

        # 添加提示信息
        if len(tools) > self.max_tools:
            formatted_tools.append(
                f"\n（共检索到 {len(tools)} 个相关工具，仅显示前 {self.max_tools} 个）"
            )

        return "\n\n".join(formatted_tools)

    def _trim_tool_fields(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """递归裁剪工具字段，保持有效的JSON结构"""
        trimmed = {}
        for key, value in fields.items():
            trimmed[key] = self._trim_value(value)
        return trimmed

    def _trim_value(self, value: Any):
        if isinstance(value, str):
            if len(value) > self._max_field_length:
                return value[: self._max_field_length - 3] + "..."
            return value
        if isinstance(value, list):
            sliced = value[: self._max_list_items]
            trimmed_list = [self._trim_value(item) for item in sliced]
            if len(value) > self._max_list_items:
                trimmed_list.append(f"...(共 {len(value)} 项，已截断)")
            return trimmed_list
        if isinstance(value, dict):
            return {k: self._trim_value(v) for k, v in value.items()}
        return value


# 便捷函数
def build_prompt(
    user_query: str,
    tools: List[Dict[str, Any]],
    max_tools: int = 3,
    use_simple: bool = False,
) -> str:
    """
    便捷函数：构建Prompt

    Args:
        user_query: 用户查询
        tools: 工具定义列表
        max_tools: 最多展示几个工具
        use_simple: 是否使用简化版

    Returns:
        完整的prompt
    """
    builder = PromptBuilder(
        max_tools=max_tools,
        use_simple_prompt=use_simple,
    )
    return builder.build(user_query, tools)
