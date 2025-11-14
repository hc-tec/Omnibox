"""
RAG-in-Action 完整流程
职责：协调RAG检索和查询解析，实现端到端的处理
"""
import logging
from typing import Dict, Any, Optional, List


from rag_system.rag_pipeline import RAGPipeline
from query_processor.llm_client import LLMClient, create_llm_client
from query_processor.prompt_builder import PromptBuilder
from query_processor.parser import QueryParser
from query_processor.path_builder import PathBuilder
from services.subscription.entity_resolver_helper import validate_and_resolve_params

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
        # 关键业务事件：开始处理查询
        logger.info(f"开始处理查询: {user_query}")

        if verbose:
            logger.debug("="*80)

        try:
            # ========== 阶段1: RAG检索 ==========
            if verbose:
                logger.debug("[阶段1] RAG向量检索")
                logger.debug("-" * 80)

            rag_results = self.rag_pipeline.search(
                query=user_query,
                top_k=self.retrieval_top_k,
                filter_datasource=filter_datasource,
                verbose=verbose,
            )

            if not rag_results:
                logger.warning(f"未找到匹配工具: {user_query}")
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
            retrieved_tools = [
                self._enrich_retrieved_tool(route_id, score, route_def)
                for route_id, score, route_def in rag_results
            ]

            if verbose:
                logger.debug(f"检索到 {len(retrieved_tools)} 个相关工具")

            # ========== 阶段2: 构建Prompt ==========
            if verbose:
                logger.debug("[阶段2] 构建LLM Prompt")
                logger.debug("-" * 80)

            prompt = self.prompt_builder.build(
                user_query=user_query,
                tools=retrieved_tools,
            )

            if verbose:
                logger.debug(f"Prompt构建完成（长度: {len(prompt)} 字符）")

            # ========== 阶段3: LLM解析 ==========
            if verbose:
                logger.debug("[阶段3] LLM查询解析")
                logger.debug("-" * 80)

            parse_result = self.query_parser.parse(
                prompt=prompt,
                temperature=self.llm_temperature,
            )

            if verbose:
                logger.debug(f"解析完成: status={parse_result.get('status')}")
                if parse_result.get('reasoning'):
                    logger.debug(f"推理: {parse_result['reasoning']}")

            # ========== 阶段4: 参数验证与订阅解析（扩展支持） ==========
            # ⭐ 修复：订阅解析应该在 needs_clarification 时也能介入
            if parse_result["status"] in ("success", "needs_clarification"):
                # 防御性检查：确保 selected_tool 存在
                if not parse_result.get("selected_tool"):
                    logger.warning("⚠️ LLM 返回的 selected_tool 为空，跳过订阅解析")
                else:
                    # 从retrieved_tools中找到对应的完整路由定义
                    selected_route_id = parse_result["selected_tool"]["route_id"]
                    selected_route_def = None

                    for route_def in retrieved_tools:
                        if route_def.get("route_id") == selected_route_id:
                            selected_route_def = route_def
                            break

                    if selected_route_def:
                        if verbose:
                            logger.debug("[阶段4] 参数验证与订阅解析")
                            logger.debug("-" * 80)

                        # ⭐ 新增：参数验证与订阅解析（基于 schema）
                        try:
                            original_params = parse_result.get("parameters_filled", {})

                            # 即使 LLM 说需要澄清，也尝试订阅解析
                            # 因为 LLM 可能提取到了人类友好名称（如"行业101"），只是不确定是否是有效ID
                            if original_params:
                                validated_params, resolution_status = validate_and_resolve_params(
                                    params=original_params,
                                    tool_schema=selected_route_def,  # 完整的 schema
                                    user_query=user_query,
                                    user_id=None  # TODO: 从上下文获取 user_id
                                )

                                # 更新参数
                                parse_result["parameters_filled"] = validated_params

                                if verbose:
                                    logger.debug(f"参数验证完成: {validated_params}")
                                    logger.debug(f"解析状态: {resolution_status}")

                                # ⭐ 关键修复：如果订阅解析成功，将状态改为 success
                                # 不再检查键是否存在，而是检查解析是否真正成功
                                if parse_result["status"] == "needs_clarification":
                                    # 检查是否所有必需参数都已成功解析
                                    required_params = selected_route_def.get("required_identifiers", [])
                                    all_resolved = all(
                                        resolution_status.get(param, False)
                                        for param in required_params
                                    )
                                    if all_resolved and required_params:
                                        logger.info(
                                            f"✅ 订阅解析成功，将状态从 needs_clarification 改为 success"
                                        )
                                        parse_result["status"] = "success"
                                        parse_result["clarification_question"] = None
                                        parse_result["reasoning"] = "通过订阅系统成功解析实体标识符"
                                    else:
                                        failed_params = [
                                            param for param in required_params
                                            if not resolution_status.get(param, False)
                                        ]
                                        logger.warning(
                                            f"⚠️ 部分参数解析失败，保持 needs_clarification 状态: {failed_params}"
                                        )

                        except Exception as e:
                            logger.warning(
                                f"⚠️ 参数验证失败，使用原始参数: {e}",
                                exc_info=True
                            )
                            # 降级：继续使用 LLM 提取的原始参数

            # ========== 阶段5: 路径构建（仅在成功时） ==========
            if parse_result["status"] == "success":
                # 防御性检查：确保 selected_tool 存在
                if not parse_result.get("selected_tool"):
                    logger.error("❌ 处理状态为 success 但 selected_tool 为空，这是一个异常状态")
                else:
                    # 从retrieved_tools中找到对应的完整路由定义
                    selected_route_id = parse_result["selected_tool"]["route_id"]
                    selected_route_def = None

                    for route_def in retrieved_tools:
                        if route_def.get("route_id") == selected_route_id:
                            selected_route_def = route_def
                            break

                    if selected_route_def:
                        if verbose:
                            logger.debug("[阶段5] 构建API路径")
                            logger.debug("-" * 80)

                        # 使用PathBuilder重新构建路径（验证）
                        verified_path = self.path_builder.build(
                            route_def=selected_route_def,
                            parameters=parse_result["parameters_filled"],
                        )

                        parse_result["generated_path"] = verified_path

                        if verbose:
                            logger.debug(f"路径已构建: {verified_path}")

            # ========== 返回结果 ==========
            parse_result["retrieved_tools"] = retrieved_tools

            # 关键业务事件：处理完成
            status = parse_result['status']
            if status == 'success':
                logger.info(f"处理成功: {parse_result.get('generated_path')}")
            elif status == 'needs_clarification':
                logger.warning(f"需要澄清: {parse_result.get('clarification_question', 'N/A')}")
            elif status == 'not_found':
                logger.warning("未找到匹配工具")
            else:
                logger.error(f"处理失败: {parse_result.get('reasoning', 'Unknown')}")

            if verbose:
                logger.debug("="*80)
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

    @staticmethod
    def _enrich_retrieved_tool(route_id: str, score: float, route_def: Dict[str, Any]) -> Dict[str, Any]:
        """附加检索得分和路由模板，便于前端透明展示。"""

        enriched = dict(route_def)
        enriched.setdefault("route_id", route_id)
        enriched["score"] = score
        enriched.setdefault("route", RAGInAction._extract_route_path(route_def))
        if route_def.get("example_path") and not enriched.get("example_path"):
            enriched["example_path"] = route_def.get("example_path")
        return enriched

    @staticmethod
    def _extract_route_path(route_def: Dict[str, Any]) -> Optional[str]:
        path_template = route_def.get("route")
        if path_template:
            return path_template

        path_template = route_def.get("path_template")
        if isinstance(path_template, list) and path_template:
            return path_template[0]
        if isinstance(path_template, str):
            return path_template

        example_path = route_def.get("example_path")
        if example_path:
            return example_path

        return None


    def plan_with_tool(self, user_query: str, tool_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        针对指定工具重新规划参数，便于一次查询生成多路数据。

        该方法用于多路由查询场景：当 RAG 检索返回多个候选工具时，
        可以针对每个候选工具单独调用此方法，生成对应的路径参数。

        Args:
            user_query: 用户查询文本
            tool_def: 工具定义字典，包含 route_id、name、parameters 等字段

        Returns:
            Dict 包含以下字段：
                - status: 状态（success/error/needs_clarification）
                - generated_path: 生成的 RSSHub 路径
                - selected_tool: 选中的工具信息
                - parameters_filled: 填充后的参数
                - reasoning: 推理过程或错误信息
        """
        prompt = self.prompt_builder.build(user_query=user_query, tools=[tool_def])
        parse_result = self.query_parser.parse(prompt)

        if parse_result.get("status") != "success":
            return parse_result

        try:
            verified_path = self.path_builder.build(
                route_def=tool_def,
                parameters=parse_result.get("parameters_filled", {}),
            )
            parse_result["generated_path"] = verified_path
            parse_result.setdefault(
                "selected_tool",
                {
                    "route_id": tool_def.get("route_id"),
                    "provider": tool_def.get("datasource") or tool_def.get("provider_id"),
                    "name": tool_def.get("name"),
                },
            )
        except Exception as exc:
            parse_result["status"] = "error"
            parse_result["reasoning"] = f"路径验证失败: {exc}"

        return parse_result

    def _print_result(self, result: Dict[str, Any]) -> None:
        """打印处理结果（美化输出）"""
        print("\n[处理结果]")
        print(f"  状态: {result['status']}")

        if result['status'] == 'success':
            print(f"\n[成功] 生成API调用:")
            print(f"  路径: {result['generated_path']}")
            print(f"  工具: {result['selected_tool']['name']} ({result['selected_tool']['route_id']})")
            print(f"  参数: {result['parameters_filled']}")

        elif result['status'] == 'needs_clarification':
            print(f"\n[需要澄清] 需要更多信息:")
            print(f"  问题: {result.get('clarification_question')}")

        elif result['status'] == 'not_found':
            print(f"\n[错误] 未找到匹配的功能")

        elif result['status'] == 'error':
            print(f"\n[错误] 处理失败:")
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
