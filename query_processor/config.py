"""
查询处理器配置
"""
from pathlib import Path

# LLM配置
LLM_CONFIG = {
    # LLM提供商：openai, anthropic, custom
    "provider": "openai",

    # OpenAI配置
    "openai": {
        "api_key": None,  # 从环境变量读取: os.getenv("OPENAI_API_KEY")
        "model": "gpt-4",  # 或 gpt-3.5-turbo
        "base_url": None,  # 自定义端点（如代理）
    },

    # Anthropic配置
    "anthropic": {
        "api_key": None,  # 从环境变量读取: os.getenv("ANTHROPIC_API_KEY")
        "model": "claude-3-sonnet-20240229",
    },

    # 生成参数
    "generation": {
        "temperature": 0.1,  # 低温度，更确定性
        "max_tokens": 1500,
        "max_retries": 2,  # JSON解析失败时的重试次数
    },
}

# Prompt配置
PROMPT_CONFIG = {
    "max_tools": 3,  # 最多向LLM展示几个工具
    "max_tool_length": 2000,  # 单个工具JSON的最大长度
    "use_simple_prompt": False,  # 是否使用简化版Prompt
}

# 路径构建配置
PATH_CONFIG = {
    "base_url": "",  # RSSHub基础URL（如果需要）
    "path_prefix": "",  # 路径前缀
}
