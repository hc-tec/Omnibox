"""
订阅系统实体解析辅助函数（基于 Schema）

⚠️⚠️⚠️ 警告：本模块包含启发式兜底逻辑 ⚠️⚠️⚠️

核心原则：
1. ✅ 优先使用 schema 明确标记（parameter_type: "entity_ref"）
2. ⚠️ 只在 schema 缺失时才使用启发式兜底
3. ⚠️ 启发式判断必须有明显的日志前缀：[HEURISTIC_FALLBACK]

职责定位：
- ✅ 基于 schema 判断哪些参数需要订阅解析
- ✅ 调用 SubscriptionService.resolve_entity() 获取标识符
- ❌ 不承担查询理解职责
- ❌ 不生成路径
- ❌ 不获取数据

使用场景：
- RAGInAction: 在参数提取后，验证并解析 entity_ref 参数
- LangGraph: 在工具调用前，验证并解析实体标识符
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


def should_resolve_param(
    param_name: str,
    param_value: str,
    tool_schema: dict
) -> bool:
    """
    判断参数是否需要订阅解析（基于 schema）

    ✅ 正确方式：检查 schema 中的 parameter_type 标记
    ⚠️ 兜底方式：schema 缺失时使用启发式判断（不推荐）

    Args:
        param_name: 参数名（如 "uid"）
        param_value: 参数值（如 "行业101" 或 "1566847"）
        tool_schema: 工具定义 schema（真实结构，parameters 是列表）：
            {
              "platform": "bilibili",
              "entity_type": "user",
              "parameters": [  # ⚠️ 注意：是列表，不是字典
                {
                  "name": "uid",
                  "parameter_type": "entity_ref",  # 关键标记
                  ...
                }
              ]
            }

    Returns:
        True: 需要订阅解析
        False: 无需解析（直接使用）

    示例：
        >>> should_resolve_param("uid", "行业101", {
        ...     "parameters": [{"name": "uid", "parameter_type": "entity_ref"}]
        ... })
        True
        >>> should_resolve_param("uid", "1566847", {
        ...     "parameters": [{"name": "uid", "parameter_type": "literal"}]
        ... })
        False
    """
    # =========================================================================
    # ✅ 优先：基于 schema 的明确判断（推荐方式）
    # =========================================================================

    # 标准化 parameters 结构（兼容列表和字典）
    params_def = tool_schema.get("parameters", [])

    # 如果是列表，转换为字典（keyed by name）
    if isinstance(params_def, list):
        params_dict = {p.get("name"): p for p in params_def if "name" in p}
    else:
        # 已经是字典，直接使用
        params_dict = params_def

    # 查找目标参数的定义
    param_def = params_dict.get(param_name, {})
    param_type = param_def.get("parameter_type")

    # 如果 schema 明确标记为 entity_ref，需要解析
    if param_type == "entity_ref":
        logger.info(
            f"✅ [SCHEMA_BASED] 参数 '{param_name}' 被 schema 标记为 entity_ref，需要订阅解析"
        )
        return True

    # 如果 schema 标记为 literal 或 enum，无需解析
    if param_type in ("literal", "enum"):
        logger.info(
            f"✅ [SCHEMA_BASED] 参数 '{param_name}' 被 schema 标记为 {param_type}，无需解析"
        )
        return False

    # =========================================================================
    # ⚠️ 兜底：Schema 缺失时直接跳过（禁用启发式判断）
    # =========================================================================
    logger.error(
        f"❌ [SCHEMA_INCOMPLETE] 参数 '{param_name}' 在 schema 中缺少 parameter_type 标记。"
    )
    logger.error(
        f"   提示：请运行 'python -m scripts.rebuild_rag_vector_store --force' 重建向量库"
    )

    # 严格模式：Schema 缺失时假设不需要解析，避免误判
    # 这样可以让查询继续执行（使用原始参数值），而不是因为误判导致查询失败
    logger.warning(
        f"⚠️ [FALLBACK_SKIP] Schema 不完整，跳过订阅解析，使用原始参数值"
    )
    return False


def resolve_entity_from_schema(
    entity_name: str,
    tool_schema: dict,
    extracted_params: dict,
    target_params: List[str],
    user_id: Optional[int] = None
) -> Optional[Dict[str, str]]:
    """
    从工具 schema 解析订阅实体（基于 schema 的正确方式）

    ✅ 核心改进：从 schema 直接获取 platform 和 entity_type，不需要猜测
    ⚠️ 当 schema 信息缺失时提供回退逻辑

    Args:
        entity_name: 实体名称（如"行业101"）
        tool_schema: RAG检索到的工具定义（真实结构）：
            {
              "platform": "bilibili",           # ✅ 从 schema 直接获取
              "entity_type": "user",             # ✅ 从 schema 直接获取
              "parameters": [  # ⚠️ 注意：是列表
                {
                  "name": "uid",
                  "parameter_type": "entity_ref"  # ✅ 明确标记
                }
              ]
            }
        extracted_params: LLM已提取的所有参数（用于日志和调试）
        target_params: 需要解析的参数名列表（如 ["uid"]）
        user_id: 用户ID（用于订阅隔离，可选）

    Returns:
        {"uid": "1566847"} 或 None（解析失败）

    示例：
        >>> resolve_entity_from_schema(
        ...     entity_name="行业101",
        ...     tool_schema={
        ...         "platform": "bilibili",
        ...         "entity_type": "user",
        ...         "parameters": [{"name": "uid", "parameter_type": "entity_ref"}]
        ...     },
        ...     extracted_params={"uid": "行业101"},
        ...     target_params=["uid"]
        ... )
        {"uid": "1566847"}
    """
    # 步骤1：从 schema 直接获取 platform 和 entity_type
    platform = tool_schema.get("platform")
    entity_type = tool_schema.get("entity_type")

    # =========================================================================
    # =========================================================================
    # 为缺少元数据的情况提供安全回退
    # =========================================================================
    if not platform or not entity_type:
        logger.warning(
            f"⚠️ [SCHEMA_INCOMPLETE] [HEURISTIC_FALLBACK] "
            f"工具 schema 缺少必要字段: "
            f"platform={platform}, entity_type={entity_type}。"
        )

        # ⚠️ 禁用启发式推断：Schema 缺失时直接返回 None
        # 启发式推断从相对路径推断 platform 注定会失败（如 "/user/video/:uid" → "user" 而不是 "bilibili"）
        # 必须依赖 schema 中的明确标记
        logger.error(
            f"❌ [SCHEMA_INCOMPLETE] Schema 缺少必要字段，无法进行订阅解析："
        )
        logger.error(f"   platform={platform}, entity_type={entity_type}")
        logger.error(
            f"   提示：请运行 'python -m scripts.rebuild_rag_vector_store --force' 重建向量库"
        )
        return None

    logger.info(
        f"✅ [SCHEMA_BASED] 订阅解析: entity_name='{entity_name}', "
        f"platform='{platform}', entity_type='{entity_type}', "
        f"target_params={target_params}"
    )

    # 步骤2：调用 SubscriptionService
    try:
        from services.database.subscription_service import SubscriptionService

        service = SubscriptionService()
        identifiers = service.resolve_entity(
            entity_name=entity_name,
            platform=platform,
            entity_type=entity_type,
            user_id=user_id,
            is_active=True
        )

        if identifiers:
            logger.info(
                f"✅ [SUBSCRIPTION_RESOLVED] 订阅解析成功: "
                f"'{entity_name}' → {identifiers}"
            )
            return identifiers
        else:
            logger.warning(
                f"⚠️ [SUBSCRIPTION_NOT_FOUND] 订阅解析失败: "
                f"未找到订阅 '{entity_name}' "
                f"(platform={platform}, entity_type={entity_type})"
            )
            logger.info(
                f"   提示：用户可能需要先创建订阅，或使用精确的实体标识符"
            )
            return None

    except Exception as e:
        logger.error(
            f"❌ [SUBSCRIPTION_ERROR] 订阅解析异常: {e}",
            exc_info=True
        )
        return None


def validate_and_resolve_params(
    params: Dict[str, str],
    tool_schema: dict,
    user_query: str,
    user_id: Optional[int] = None
) -> Dict[str, str]:
    """
    验证参数并通过订阅系统解析（高级接口）

    这是一个便捷函数，用于 RAGInAction 等场景，自动判断哪些参数需要解析。

    Args:
        params: LLM提取的参数（如 {"uid": "行业101", "embed": "true"}）
        tool_schema: 工具定义 schema（包含完整元数据）
        user_query: 原始用户查询（用于日志）
        user_id: 用户ID（可选）

    Returns:
        验证后的参数（如 {"uid": "1566847", "embed": "true"}）

    流程：
        1. 遍历所有参数，基于 schema 判断是否需要解析
        2. 需要解析的参数调用 resolve_entity_from_schema()
        3. 解析失败时使用原值（降级处理）
    """
    validated = {}
    params_needing_resolution = []

    logger.info(
        f"开始参数验证与解析: 用户查询='{user_query}', "
        f"提取参数={params}"
    )

    # 步骤1：基于 schema 识别哪些参数需要订阅解析
    for param_name, param_value in params.items():
        if should_resolve_param(param_name, param_value, tool_schema):
            params_needing_resolution.append(param_name)
            logger.info(
                f"  → 参数 '{param_name}'='{param_value}' 需要订阅解析"
            )
        else:
            validated[param_name] = param_value
            logger.info(
                f"  → 参数 '{param_name}'='{param_value}' 无需解析，直接使用"
            )

    # 步骤2：如果有参数需要解析，调用订阅系统
    if params_needing_resolution:
        # 假设第一个需要解析的参数是主要实体标识符
        primary_param = params_needing_resolution[0]
        entity_name = params[primary_param]

        logger.info(
            f"调用订阅解析: 主实体='{entity_name}' "
            f"(param={primary_param})"
        )

        # 调用订阅解析（基于 schema）
        resolved_identifiers = resolve_entity_from_schema(
            entity_name=entity_name,
            tool_schema=tool_schema,
            extracted_params=params,
            target_params=params_needing_resolution,
            user_id=user_id
        )

        if resolved_identifiers:
            # 解析成功，合并标识符
            validated.update(resolved_identifiers)
            logger.info(
                f"✅ 订阅解析成功: {entity_name} → {resolved_identifiers}"
            )
        else:
            # 降级：使用原值
            logger.warning(
                f"⚠️ 订阅解析失败，使用原值进行降级处理"
            )
            for param_name in params_needing_resolution:
                validated[param_name] = params[param_name]

    logger.info(f"参数验证与解析完成: {validated}")
    return validated
