"""
RAG-in-Action 完整流程
职责：协调RAG检索和查询解析，实现端到端的处理
"""
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rag_system.rag_pipeline import RAGPipeline
from query_processor.llm_client import LLMClient, create_llm_client
from query_processor.prompt_builder import PromptBuilder
from query_processor.parser import QueryParser
from query_processor.path_builder import PathBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGInAction:
    """
    RAG-in-Action 主流程
    整合向量检索 + LLM解析 = 自然语言 → API调用
    """

    def __init__(
        self,
        rag_pipeline: RAGPipeline,
        llm_client: LLMClient,
        prompt_builder: Optional[PromptBuilder] = None,
        path_builder: Optional[PathBuilder] = None,
        retrieval_top_k: int = 3,
        llm_temperature: float = 0.1,
    ):
        """
        初始化RAG-in-Action流程

        Args:
            rag_pipeline: RAG检索管道
            llm_client: LLM客户端
            prompt_builder: Prompt构建器（可选）
            path_builder: 路径构建器（可选）
            retrieval_top_k: RAG检索返回的结果数量
            llm_temperature: LLM生成温度
        """
        self.rag_pipeline = rag_pipeline
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.path_builder = path_builder or PathBuilder()
        self.query_parser = QueryParser(llm_client)
        self.retrieval_top_k = retrieval_top_k
        self.llm_temperature = llm_temperature

        logger.info("✓ RAG-in-Action 流程初始化完成")

    def process(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        处理用户查询

        完整流程：
        1. RAG检索：找到相关的路由定义
        2. 构建Prompt：将路由定义和用户查询组合
        3. LLM解析：提取意图和参数
        4. 路径构建：生成完整的API调用路径

        Args:
            user_query: 用户的自然语言查询
            filter_datasource: 过滤特定数据源（可选）
            verbose: 是否打印详细日志

        Returns:
            处理结果字典，包含：
            - status: 状态（success/needs_clarification/not_found/error）
            - generated_path: 生成的API路径
            - selected_tool: 选中的工具信息
            - parameters_filled: 填充的参数
            - reasoning: LLM的推理过程
            - clarification_question: 如果需要澄清的问题
            - retrieved_tools: RAG检索到的所有工具
        """
        if verbose:
            logger.info("="*80)
            logger.info(f"开始处理查询: {user_query}")
            logger.info("="*80)

        try:
            # ========== 阶段1: RAG检索 ==========
            if verbose:
                logger.info("\n[阶段1] RAG向量检索")
                logger.info("-" * 80)

            rag_results = self.rag_pipeline.search(
                query=user_query,
                top_k=self.retrieval_top_k,
                filter_datasource=filter_datasource,
                verbose=verbose,
            )

            if not rag_results:
                return {
                    "status": "not_found",
                    "reasoning": "未找到相关的API工具",
                    "generated_path": None,
                    "selected_tool": None,
                    "parameters_filled": {},
                    "clarification_question": "抱歉，我没有找到相关的功能。请换一种方式描述您的需求。",
                    "retrieved_tools": [],
                }

            # 提取路由定义
            retrieved_tools = [route_def for _, _, route_def in rag_results]

            if verbose:
                logger.info(f"✓ 检索到 {len(retrieved_tools)} 个相关工具")

            # ========== 阶段2: 构建Prompt ==========
            if verbose:
                logger.info("\n[阶段2] 构建LLM Prompt")
                logger.info("-" * 80)

            prompt = self.prompt_builder.build(
                user_query=user_query,
                tools=retrieved_tools,
            )

            if verbose:
                logger.info(f"✓ Prompt构建完成（长度: {len(prompt)} 字符）")

            # ========== 阶段3: LLM解析 ==========
            if verbose:
                logger.info("\n[阶段3] LLM查询解析")
                logger.info("-" * 80)

            parse_result = self.query_parser.parse(
                prompt=prompt,
                temperature=self.llm_temperature,
            )

            if verbose:
                logger.info(f"✓ 解析完成: status={parse_result.get('status')}")
                if parse_result.get('reasoning'):
                    logger.info(f"  推理: {parse_result['reasoning']}")

            # ========== 阶段4: 路径构建（如果成功） ==========
            if parse_result["status"] == "success":
                if verbose:
                    logger.info("\n[阶段4] 构建API路径")
                    logger.info("-" * 80)

                # 从retrieved_tools中找到对应的完整路由定义
                selected_route_id = parse_result["selected_tool"]["route_id"]
                selected_route_def = None

                for route_def in retrieved_tools:
                    if route_def.get("route_id") == selected_route_id:
                        selected_route_def = route_def
                        break

                if selected_route_def:
                    # 使用PathBuilder重新构建路径（验证）
                    verified_path = self.path_builder.build(
                        route_def=selected_route_def,
                        parameters=parse_result["parameters_filled"],
                    )

                    parse_result["generated_path"] = verified_path

                    if verbose:
                        logger.info(f"✓ 路径已构建: {verified_path}")

            # ========== 返回结果 ==========
            parse_result["retrieved_tools"] = retrieved_tools

            if verbose:
                logger.info("\n" + "="*80)
                logger.info("处理完成！")
                logger.info("="*80)
                self._print_result(parse_result)

            return parse_result

        except Exception as e:
            logger.error(f"处理失败: {e}", exc_info=True)

            return {
                "status": "error",
                "reasoning": f"处理过程中发生错误: {str(e)}",
                "generated_path": None,
                "selected_tool": None,
                "parameters_filled": {},
                "clarification_question": "抱歉，处理您的请求时出现了错误。",
                "retrieved_tools": [],
            }

    def _print_result(self, result: Dict[str, Any]) -> None:
        """打印处理结果（美化输出）"""
        print("\n📊 处理结果:")
        print(f"  状态: {result['status']}")

        if result['status'] == 'success':
            print(f"\n✅ 成功生成API调用:")
            print(f"  路径: {result['generated_path']}")
            print(f"  工具: {result['selected_tool']['name']} ({result['selected_tool']['route_id']})")
            print(f"  参数: {result['parameters_filled']}")

        elif result['status'] == 'needs_clarification':
            print(f"\n❓ 需要更多信息:")
            print(f"  问题: {result.get('clarification_question')}")

        elif result['status'] == 'not_found':
            print(f"\n❌ 未找到匹配的功能")

        elif result['status'] == 'error':
            print(f"\n❌ 处理错误:")
            print(f"  原因: {result.get('reasoning')}")


# 便捷函数
def create_rag_in_action(
    llm_provider: str = "openai",
    llm_config: Optional[Dict] = None,
    rag_pipeline: Optional[RAGPipeline] = None,
) -> RAGInAction:
    """
    便捷函数：创建RAG-in-Action实例

    Args:
        llm_provider: LLM提供商（openai/anthropic/custom）
        llm_config: LLM配置字典
        rag_pipeline: RAG管道（None则自动创建）

    Returns:
        RAGInAction实例

    Example:
        >>> ria = create_rag_in_action(
        ...     llm_provider="openai",
        ...     llm_config={"model": "gpt-4"}
        ... )
        >>> result = ria.process("虎扑步行街最新帖子")
    """
    # 创建RAG管道
    if rag_pipeline is None:
        rag_pipeline = RAGPipeline()

    # 创建LLM客户端
    llm_config = llm_config or {}
    llm_client = create_llm_client(llm_provider, **llm_config)

    # 创建RAG-in-Action
    return RAGInAction(
        rag_pipeline=rag_pipeline,
        llm_client=llm_client,
    )
