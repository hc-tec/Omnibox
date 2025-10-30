"""
查询处理器配置
使用 Pydantic Settings 管理环境变量（最佳实践）
"""
from typing import Optional, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM配置（从环境变量读取）"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",  # 不使用前缀
        case_sensitive=False,
        extra="ignore",
    )

    # LLM提供商
    llm_provider: Literal["openai", "anthropic", "custom"] = Field(
        default="openai",
        description="LLM提供商"
    )

    # OpenAI配置
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API Key"
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI模型名称"
    )
    openai_base_url: Optional[str] = Field(
        default=None,
        description="OpenAI API Base URL（可选，用于代理）"
    )

    # Anthropic配置
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API Key"
    )
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic模型名称"
    )
    anthropic_base_url: Optional[str] = Field(
        default=None,
        description="Anthropic API Base URL（可选，用于代理或服务模拟器）"
    )

    # 生成参数
    llm_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="生成温度"
    )
    llm_max_tokens: int = Field(
        default=1500,
        gt=0,
        description="最大token数"
    )
    llm_max_retries: int = Field(
        default=2,
        ge=0,
        description="JSON解析失败时的最大重试次数"
    )


class PromptSettings(BaseSettings):
    """Prompt配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PROMPT_",
        case_sensitive=False,
        extra="ignore",
    )

    max_tools: int = Field(
        default=3,
        gt=0,
        le=10,
        description="最多向LLM展示几个工具"
    )
    max_tool_length: int = Field(
        default=2000,
        gt=0,
        description="单个工具JSON的最大长度"
    )
    use_simple_prompt: bool = Field(
        default=False,
        description="是否使用简化版Prompt"
    )


class PathSettings(BaseSettings):
    """路径构建配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PATH_",
        case_sensitive=False,
        extra="ignore",
    )

    base_url: str = Field(
        default="",
        description="RSSHub基础URL（如果需要）"
    )
    path_prefix: str = Field(
        default="",
        description="路径前缀"
    )


# 全局配置实例（单例模式）
llm_settings = LLMSettings()
prompt_settings = PromptSettings()
path_settings = PathSettings()


def reload_settings():
    """重新加载配置（主要用于测试）"""
    global llm_settings, prompt_settings, path_settings
    llm_settings = LLMSettings()
    prompt_settings = PromptSettings()
    path_settings = PathSettings()
