"""
LLM客户端抽象层
职责：使用成熟的LangChain聊天模型接口统一不同LLM提供商的调用方式
"""
import logging
from abc import ABC, abstractmethod
from typing import Callable, Optional

from .config import llm_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """LLM客户端抽象基类"""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 输入prompt
            **kwargs: temperature, max_tokens等参数

        Returns:
            生成的文本
        """
        raise NotImplementedError

    def chat(self, messages, **kwargs) -> str:
        """聊天接口（子类可根据需要实现）。"""
        raise NotImplementedError("chat() 未在该 LLM 客户端实现")


class OpenAIClient(LLMClient):
    """基于LangChain的OpenAI聊天模型客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        except ImportError as exc:
            raise ImportError(
                "请先安装 langchain-openai 依赖: pip install langchain-openai"
            ) from exc

        self._ChatOpenAI = ChatOpenAI
        self._HumanMessage = HumanMessage
        self._SystemMessage = SystemMessage
        self._AIMessage = AIMessage

        # 优先使用参数，否则从配置读取
        api_key = api_key or llm_settings.openai_api_key
        if not api_key:
            raise ValueError(
                "未提供 OPENAI_API_KEY，请设置环境变量或在.env文件中配置"
            )

        # 优先使用参数，否则从配置读取
        self.model_name = model or llm_settings.openai_model
        base_url = base_url or llm_settings.openai_base_url
        self.system_prompt = system_prompt or (
            "You are a helpful API calling assistant. Always return valid JSON."
        )

        self.client = self._ChatOpenAI(
            model=self.model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
        )

        logger.info("✓ 使用 LangChain ChatOpenAI 初始化成功: %s", self.model_name)

    def generate(self, prompt: str, **kwargs) -> str:
        """调用OpenAI聊天模型"""
        temperature = kwargs.get("temperature", None)
        max_tokens = kwargs.get("max_tokens", None)

        messages = []
        if self.system_prompt:
            messages.append(self._SystemMessage(content=self.system_prompt))
        messages.append(self._HumanMessage(content=prompt))

        invoke_kwargs = {}
        if temperature is not None:
            invoke_kwargs["temperature"] = temperature
        if max_tokens is not None:
            invoke_kwargs["max_tokens"] = max_tokens

        response = self.client.invoke(messages, **invoke_kwargs)

        content = response.content
        if isinstance(content, list):
            content = "".join(
                piece.get("text", "") if isinstance(piece, dict) else str(piece)
                for piece in content
            )

        return str(content)

    def chat(self, messages, **kwargs) -> str:
        lc_messages = []
        has_system = False
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                lc_messages.append(self._SystemMessage(content=content))
                has_system = True
            elif role == "assistant":
                lc_messages.append(self._AIMessage(content=content))
            else:
                lc_messages.append(self._HumanMessage(content=content))

        if self.system_prompt and not has_system:
            lc_messages.insert(0, self._SystemMessage(content=self.system_prompt))

        temperature = kwargs.get("temperature")
        max_tokens = kwargs.get("max_tokens")
        invoke_kwargs = {}
        if temperature is not None:
            invoke_kwargs["temperature"] = temperature
        if max_tokens is not None:
            invoke_kwargs["max_tokens"] = max_tokens

        response = self.client.invoke(lc_messages, **invoke_kwargs)

        content = response.content
        if isinstance(content, list):
            content = "".join(
                piece.get("text", "") if isinstance(piece, dict) else str(piece)
                for piece in content
            )

        return str(content)


class AnthropicClient(LLMClient):
    """基于LangChain的Anthropic聊天模型客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        初始化 Anthropic 客户端

        Args:
            api_key: API Key（可选，默认从配置读取）
            model: 模型名称（可选，默认从配置读取）
            base_url: API Base URL（可选，用于代理或服务模拟器）
            system_prompt: 系统提示（可选）
        """
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        except ImportError as exc:
            raise ImportError(
                "请先安装 langchain-anthropic 依赖: pip install langchain-anthropic"
            ) from exc

        self._ChatAnthropic = ChatAnthropic
        self._HumanMessage = HumanMessage
        self._SystemMessage = SystemMessage
        self._AIMessage = AIMessage

        # 优先使用参数，否则从配置读取
        api_key = api_key or llm_settings.anthropic_api_key
        if not api_key:
            raise ValueError(
                "未提供 ANTHROPIC_API_KEY，请设置环境变量或在.env文件中配置"
            )

        self.model_name = model or llm_settings.anthropic_model
        base_url = base_url or llm_settings.anthropic_base_url
        self.system_prompt = system_prompt

        # 构建 ChatAnthropic 参数
        client_kwargs = {
            "model": self.model_name,
            "anthropic_api_key": api_key,
        }

        # 只有在提供 base_url 时才添加
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = self._ChatAnthropic(**client_kwargs)

        logger.info("✓ 使用 LangChain ChatAnthropic 初始化成功: %s", self.model_name)

    def generate(self, prompt: str, **kwargs) -> str:
        """调用Anthropic聊天模型"""
        temperature = kwargs.get("temperature", None)
        max_tokens = kwargs.get("max_tokens", None)

        messages = []
        if self.system_prompt:
            messages.append(self._SystemMessage(content=self.system_prompt))
        messages.append(self._HumanMessage(content=prompt))

        invoke_kwargs = {}
        if temperature is not None:
            invoke_kwargs["temperature"] = temperature
        if max_tokens is not None:
            invoke_kwargs["max_tokens"] = max_tokens

        response = self.client.invoke(messages, **invoke_kwargs)

        content = response.content
        if isinstance(content, list):
            content = "".join(
                piece.get("text", "") if isinstance(piece, dict) else str(piece)
                for piece in content
            )

        return str(content)

    def chat(self, messages, **kwargs) -> str:
        lc_messages = []
        has_system = False
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                lc_messages.append(self._SystemMessage(content=content))
                has_system = True
            elif role == "assistant":
                lc_messages.append(self._AIMessage(content=content))
            else:
                lc_messages.append(self._HumanMessage(content=content))

        if self.system_prompt and not has_system:
            lc_messages.insert(0, self._SystemMessage(content=self.system_prompt))

        temperature = kwargs.get("temperature")
        max_tokens = kwargs.get("max_tokens")
        invoke_kwargs = {}
        if temperature is not None:
            invoke_kwargs["temperature"] = temperature
        if max_tokens is not None:
            invoke_kwargs["max_tokens"] = max_tokens

        response = self.client.invoke(lc_messages, **invoke_kwargs)

        content = response.content
        if isinstance(content, list):
            content = "".join(
                piece.get("text", "") if isinstance(piece, dict) else str(piece)
                for piece in content
            )

        return str(content)


class CustomLLMClient(LLMClient):
    """自定义LLM客户端（使用回调函数）"""

    def __init__(self, generate_func: Callable[[str], str], name: str = "Custom"):
        self.generate_func = generate_func
        self.name = name
        logger.info("✓ 初始化自定义LLM客户端: %s", name)

    def generate(self, prompt: str, **kwargs) -> str:
        logger.debug("调用自定义LLM: %s", self.name)
        return self.generate_func(prompt)

    def chat(self, messages, **kwargs) -> str:
        parts = []
        for message in messages:
            role = message.get("role", "user").upper()
            content = message.get("content", "")
            parts.append(f"[{role}] {content}")
        prompt = "\n".join(parts)
        return self.generate(prompt, **kwargs)


def create_llm_client(
    provider: str,
    **kwargs,
) -> LLMClient:
    """
    工厂函数：创建LLM客户端

    Args:
        provider: 提供商名称（openai, anthropic, custom）
        **kwargs: 传递给客户端的参数

    Returns:
        LLMClient实例
    """
    if provider == "openai":
        return OpenAIClient(**kwargs)
    if provider == "anthropic":
        return AnthropicClient(**kwargs)
    if provider == "custom":
        return CustomLLMClient(**kwargs)
    raise ValueError(f"不支持的LLM提供商: {provider}")
