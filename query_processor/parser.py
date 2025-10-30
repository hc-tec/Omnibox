"""
查询解析器
职责：使用LLM解析用户查询，提取参数
"""
import json
import re
import logging
from typing import Dict, Any

from .llm_client import LLMClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryParser:
    """
    查询解析器
    负责调用LLM并解析返回的JSON结果
    """

    def __init__(
        self,
        llm_client: LLMClient,
        max_retries: int = 2,
    ):
        """
        初始化解析器

        Args:
            llm_client: LLM客户端实例
            max_retries: JSON解析失败时的最大重试次数
        """
        self.llm_client = llm_client
        self.max_retries = max_retries

    def parse(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        """
        解析用户查询

        Args:
            prompt: 完整的prompt（由PromptBuilder构建）
            temperature: 生成温度
            max_tokens: 最大token数

        Returns:
            解析结果字典

        Raises:
            ValueError: JSON解析失败且重试次数用尽
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"调用LLM解析查询（尝试 {attempt + 1}/{self.max_retries + 1}）")

                # 调用LLM
                raw_response = self.llm_client.generate(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                logger.debug(f"LLM原始响应:\n{raw_response}")

                # 提取并解析JSON
                parsed_result = self._extract_and_parse_json(raw_response)

                # 验证结构
                self._validate_result(parsed_result)

                logger.debug(f"成功解析查询: status={parsed_result.get('status')}")
                return parsed_result

            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                logger.warning(f"解析失败（尝试 {attempt + 1}）: {e}")

                if attempt < self.max_retries:
                    logger.debug("重试中...")
                    continue

        # 所有重试都失败
        logger.error(f"解析失败，已达最大重试次数: {last_error}")

        return {
            "status": "error",
            "reasoning": f"LLM返回格式错误: {str(last_error)}",
            "selected_tool": None,
            "generated_path": None,
            "parameters_filled": {},
            "clarification_question": "抱歉，我无法理解您的请求，请换一种方式描述。",
        }

    def _extract_and_parse_json(self, text: str) -> Dict[str, Any]:
        """
        从LLM返回的文本中提取并解析JSON

        Args:
            text: LLM返回的原始文本

        Returns:
            解析后的JSON字典

        Raises:
            json.JSONDecodeError: JSON解析失败
        """
        text = text.strip()

        # 移除可能的markdown代码块
        fenced_json = re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
        if fenced_json:
            text = fenced_json.group(1).strip()

        # 找到第一个 { 和最后一个 }
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
            raise json.JSONDecodeError("未找到有效的JSON对象", text, 0)

        json_text = text[start_idx:end_idx + 1]

        # 解析JSON
        return json.loads(json_text)

    def _validate_result(self, result: Dict[str, Any]) -> None:
        """
        验证解析结果的结构

        Args:
            result: 解析后的结果字典

        Raises:
            ValueError: 结构不符合要求
        """
        # 必需字段
        required_fields = ["status", "reasoning"]

        for field in required_fields:
            if field not in result:
                raise ValueError(f"缺少必需字段: {field}")

        # 状态值检查
        valid_statuses = ["success", "needs_clarification", "not_found", "error"]
        if result["status"] not in valid_statuses:
            raise ValueError(f"无效的状态值: {result['status']}")

        # 如果状态是success，检查必要字段
        if result["status"] == "success":
            success_fields = ["selected_tool", "generated_path", "parameters_filled"]
            for field in success_fields:
                if field not in result:
                    raise ValueError(f"success状态下缺少字段: {field}")
