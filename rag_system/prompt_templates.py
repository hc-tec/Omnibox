"""
Prompt 模板
用于 AI 提问解析（RAG-in-Action）
"""

# 工具调用解析 Prompt
TOOL_CALLING_PROMPT = """你是一个智能API调用助手，负责将用户的自然语言请求转换为结构化的API调用。

# 1. 可用的工具 (API)

以下是通过RAG检索到的最相关工具定义：

{retrieved_tools}

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
- 根据 `path_template` 和提取的参数，生成完整的 URL 路径
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
工具：hupu_bbs（虎扑社区）

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
工具：多个社区API

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


# 简化版 Prompt（适用于性能较弱的 LLM）
SIMPLE_TOOL_CALLING_PROMPT = """将用户请求转换为API调用。

工具定义：
{retrieved_tools}

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


# 多轮对话优化 Prompt
CONVERSATIONAL_PROMPT = """你是一个智能助手，负责帮助用户调用API获取数据。

# 对话历史
{conversation_history}

# 当前可用工具
{retrieved_tools}

# 用户最新请求
{user_query}

# 任务
基于对话历史和用户当前请求：
1. 理解用户的完整意图（结合上下文）
2. 如果之前有未完成的参数，尝试从当前请求中补充
3. 生成API调用或提出澄清问题

输出JSON：
{{
  "status": "success/needs_clarification/not_found",
  "reasoning": "结合上下文的分析",
  "selected_tool": {{"route_id": "...", "provider": "...", "name": "..."}},
  "generated_path": "/provider/path/...",
  "parameters_filled": {{"param": "value"}},
  "clarification_question": null
}}

输出："""


def format_tool_json(route_def: dict, max_length: int = 2000) -> str:
    """
    格式化工具定义为 JSON 字符串

    Args:
        route_def: 路由定义字典
        max_length: 最大长度（避免 prompt 过长）

    Returns:
        格式化的 JSON 字符串
    """
    import json

    # 提取关键字段
    essential_fields = {
        "route_id": route_def.get("route_id"),
        "provider": route_def.get("datasource") or route_def.get("provider_id"),
        "name": route_def.get("name"),
        "description": route_def.get("description", ""),
        "path_template": route_def.get("path_template"),
        "parameters": route_def.get("parameters", []),
        "categories": route_def.get("categories", []),
    }

    # 转为 JSON
    json_str = json.dumps(essential_fields, ensure_ascii=False, indent=2)

    # 截断过长的内容
    if len(json_str) > max_length:
        json_str = json_str[:max_length] + "\n  ...(内容过长，已截断)\n}"

    return json_str


def format_multiple_tools(route_defs: list, max_tools: int = 3) -> str:
    """
    格式化多个工具定义

    Args:
        route_defs: 路由定义列表
        max_tools: 最多包含几个工具

    Returns:
        格式化的工具列表字符串
    """
    tools_str = []

    for i, route_def in enumerate(route_defs[:max_tools], 1):
        tool_json = format_tool_json(route_def)
        tools_str.append(f"## 工具 {i}\n\n{tool_json}")

    if len(route_defs) > max_tools:
        tools_str.append(f"\n（共检索到 {len(route_defs)} 个相关工具，仅显示前 {max_tools} 个）")

    return "\n\n".join(tools_str)


def build_prompt(
    user_query: str,
    retrieved_tools: list,
    prompt_template: str = TOOL_CALLING_PROMPT,
    conversation_history: list = None,
) -> str:
    """
    构建完整的 Prompt

    Args:
        user_query: 用户查询
        retrieved_tools: 检索到的工具列表
        prompt_template: 使用的模板
        conversation_history: 对话历史（可选）

    Returns:
        完整的 prompt 字符串
    """
    # 格式化工具定义
    tools_formatted = format_multiple_tools(retrieved_tools)

    # 填充模板
    if conversation_history and prompt_template == CONVERSATIONAL_PROMPT:
        history_str = "\n".join([
            f"{'用户' if msg['role'] == 'user' else '助手'}: {msg['content']}"
            for msg in conversation_history
        ])

        prompt = prompt_template.format(
            user_query=user_query,
            retrieved_tools=tools_formatted,
            conversation_history=history_str,
        )
    else:
        prompt = prompt_template.format(
            user_query=user_query,
            retrieved_tools=tools_formatted,
        )

    return prompt
