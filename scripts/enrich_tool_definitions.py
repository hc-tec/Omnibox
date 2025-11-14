"""
工具定义元数据自动扩展脚本

⚠️⚠️⚠️ 警告：本脚本包含启发式推断规则 ⚠️⚠️⚠️

本脚本的作用：
- 为 datasource_definitions.json 中的每个 route 添加订阅系统所需的元数据
- 添加字段：platform, entity_type, parameter_type

推断规则（启发式，可能不准确）：
- platform: 从 provider_id 提取
- entity_type: 从 path_template 中的路径段推断（/user/... → user, /repo/... → repo）
- parameter_type: 根据参数名和描述推断（uid/id → entity_ref，其他 → literal）

⚠️ 风险提示：
1. 启发式推断不可能100%准确
2. 必须人工审核高频工具的推断结果
3. 低频工具可以使用推断结果，但发现问题时需要人工修正

日志标识：
- [HEURISTIC_INFERENCE] 表示正在进行启发式推断
- [HIGH_CONFIDENCE] 表示推断置信度高（> 0.9）
- [LOW_CONFIDENCE] 表示推断置信度低（< 0.7），需要人工审核
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ================================
# ⚠️ 启发式推断规则（慎用）
# ================================

# 实体类型推断规则（从路径模式识别）
ENTITY_TYPE_PATTERNS = {
    r'/user/': 'user',
    r'/users/': 'user',
    r'/people/': 'user',
    r'/author/': 'user',
    r'/creator/': 'user',
    r'/repo/': 'repo',
    r'/repository/': 'repo',
    r'/repos/': 'repo',
    r'/column/': 'column',
    r'/topic/': 'topic',
    r'/tag/': 'tag',
    r'/channel/': 'channel',
    r'/board/': 'board',
}

# 参数名 → entity_ref 的推断规则
ENTITY_REF_PARAM_NAMES = {
    'uid', 'user_id', 'userid', 'author_id', 'creator_id',
    'owner', 'user', 'author',
    'repo', 'repository', 'repo_name',
    'column_id', 'columnid',
    'topic_id', 'topicid',
    'tag', 'tag_id',
    'channel_id', 'channelid',
}

# 参数描述关键词 → entity_ref 的推断规则
ENTITY_REF_KEYWORDS = [
    '用户', '作者', 'UP主', '博主', '创作者',
    '仓库', 'repository',
    '专栏', 'column',
    '话题', 'topic',
    '标签', 'tag',
]


def infer_platform_from_provider(provider_id: str) -> str:
    """
    从 provider_id 提取 platform

    [HEURISTIC_INFERENCE] 简单规则：provider_id 通常就是 platform 名称
    """
    platform = provider_id.lower()
    logger.debug(f"[HEURISTIC_INFERENCE] 推断 platform: {provider_id} → {platform}")
    return platform


def infer_entity_type_from_path(path_template: str) -> Tuple[Optional[str], float]:
    """
    从 path_template 推断 entity_type

    [HEURISTIC_INFERENCE] 根据路径中的关键词推断

    Returns:
        (entity_type, confidence)
        - entity_type: 推断的实体类型，如 'user', 'repo' 等
        - confidence: 置信度 0-1.0
    """
    for pattern, entity_type in ENTITY_TYPE_PATTERNS.items():
        if re.search(pattern, path_template, re.IGNORECASE):
            confidence = 0.9  # 路径匹配的置信度较高
            logger.debug(
                f"[HEURISTIC_INFERENCE] [HIGH_CONFIDENCE] "
                f"路径 '{path_template}' 匹配 '{pattern}' → entity_type='{entity_type}' "
                f"(confidence={confidence})"
            )
            return entity_type, confidence

    # 未匹配到任何模式
    logger.warning(
        f"[HEURISTIC_INFERENCE] [LOW_CONFIDENCE] "
        f"路径 '{path_template}' 无法推断 entity_type，返回 None"
    )
    return None, 0.0


def infer_parameter_type(
    param_name: str,
    param_description: str,
    param_required: bool
) -> Tuple[str, float]:
    """
    推断参数类型：entity_ref / literal / enum

    [HEURISTIC_INFERENCE] 基于参数名和描述的关键词推断

    Returns:
        (parameter_type, confidence)
    """
    param_name_lower = param_name.lower()
    param_desc_lower = param_description.lower()

    # 规则1：参数名匹配 entity_ref 模式
    if param_name_lower in ENTITY_REF_PARAM_NAMES:
        confidence = 0.9
        logger.debug(
            f"[HEURISTIC_INFERENCE] [HIGH_CONFIDENCE] "
            f"参数 '{param_name}' 匹配 entity_ref 模式 (confidence={confidence})"
        )
        return 'entity_ref', confidence

    # 规则2：描述中包含实体相关关键词
    for keyword in ENTITY_REF_KEYWORDS:
        if keyword in param_desc_lower:
            confidence = 0.8
            logger.debug(
                f"[HEURISTIC_INFERENCE] "
                f"参数 '{param_name}' 描述包含关键词 '{keyword}' → entity_ref "
                f"(confidence={confidence})"
            )
            return 'entity_ref', confidence

    # 规则3：参数名以 _id 或 id 结尾
    if param_name_lower.endswith('_id') or param_name_lower == 'id':
        confidence = 0.7
        logger.debug(
            f"[HEURISTIC_INFERENCE] [LOW_CONFIDENCE] "
            f"参数 '{param_name}' 以 '_id' 或 'id' 结尾 → entity_ref "
            f"(confidence={confidence}，需人工审核)"
        )
        return 'entity_ref', confidence

    # 默认：literal
    confidence = 0.6
    logger.debug(
        f"[HEURISTIC_INFERENCE] "
        f"参数 '{param_name}' 无明显特征，默认为 literal (confidence={confidence})"
    )
    return 'literal', confidence


def enrich_route(
    route: dict,
    platform: str
) -> Tuple[dict, float]:
    """
    为单个 route 添加元数据

    Returns:
        (enriched_route, overall_confidence)
    """
    enriched = route.copy()

    # 获取 path_template（可能是数组）
    path_templates = route.get('path_template', [])
    if isinstance(path_templates, str):
        path_templates = [path_templates]
    primary_path = path_templates[0] if path_templates else ''

    # 1. 添加 platform
    enriched['platform'] = platform

    # 2. 推断 entity_type
    entity_type, entity_confidence = infer_entity_type_from_path(primary_path)
    if entity_type:
        enriched['entity_type'] = entity_type

    # 3. 扩展 parameters
    enriched_params = []
    param_confidences = []

    for param in route.get('parameters', []):
        enriched_param = param.copy()

        # 推断 parameter_type
        param_type, param_confidence = infer_parameter_type(
            param.get('name', ''),
            param.get('description', ''),
            param.get('required', False)
        )

        enriched_param['parameter_type'] = param_type
        if param_type == 'entity_ref':
            enriched_param['entity_field'] = param['name']

        enriched_params.append(enriched_param)
        param_confidences.append(param_confidence)

    enriched['parameters'] = enriched_params

    # 4. 提取 required_identifiers（parameter_type == 'entity_ref' 且 required == true）
    required_identifiers = [
        p['name'] for p in enriched_params
        if p.get('parameter_type') == 'entity_ref' and p.get('required', False)
    ]
    enriched['required_identifiers'] = required_identifiers

    # 5. 计算总体置信度
    all_confidences = [entity_confidence] + param_confidences
    overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    return enriched, overall_confidence


def enrich_definitions(
    input_path: Path,
    output_path: Path,
    min_confidence: float = 0.0
) -> Dict[str, int]:
    """
    批量处理工具定义文件

    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        min_confidence: 最小置信度阈值（低于此值会标记为需人工审核）

    Returns:
        统计信息
    """
    logger.info(f"开始处理工具定义文件: {input_path}")
    logger.warning(
        "⚠️⚠️⚠️ 警告：正在使用启发式推断，结果可能不准确，必须人工审核 ⚠️⚠️⚠️"
    )

    # 加载原始定义
    with open(input_path, 'r', encoding='utf-8') as f:
        providers = json.load(f)

    stats = {
        'total_providers': 0,
        'total_routes': 0,
        'high_confidence': 0,  # >= 0.9
        'medium_confidence': 0,  # 0.7 - 0.9
        'low_confidence': 0,  # < 0.7
        'needs_review': 0,  # < min_confidence
    }

    enriched_providers = []
    needs_review_routes = []

    for provider in providers:
        platform = infer_platform_from_provider(provider['provider_id'])
        enriched_provider = provider.copy()
        enriched_routes = []

        for route in provider.get('routes', []):
            enriched_route, confidence = enrich_route(route, platform)
            enriched_routes.append(enriched_route)

            # 统计置信度分布
            stats['total_routes'] += 1
            if confidence >= 0.9:
                stats['high_confidence'] += 1
            elif confidence >= 0.7:
                stats['medium_confidence'] += 1
            else:
                stats['low_confidence'] += 1

            if confidence < min_confidence:
                stats['needs_review'] += 1
                needs_review_routes.append({
                    'route_id': route.get('route_id'),
                    'platform': platform,
                    'confidence': confidence,
                    'path': route.get('path_template', [''])[0]
                })

        enriched_provider['routes'] = enriched_routes
        enriched_providers.append(enriched_provider)
        stats['total_providers'] += 1

    # 保存扩展后的定义
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enriched_providers, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 处理完成，结果已保存到: {output_path}")
    logger.info(f"统计信息:")
    logger.info(f"  - 总 Provider 数: {stats['total_providers']}")
    logger.info(f"  - 总 Route 数: {stats['total_routes']}")
    logger.info(f"  - 高置信度 (>= 0.9): {stats['high_confidence']}")
    logger.info(f"  - 中置信度 (0.7-0.9): {stats['medium_confidence']}")
    logger.info(f"  - 低置信度 (< 0.7): {stats['low_confidence']}")
    logger.info(f"  - 需人工审核 (< {min_confidence}): {stats['needs_review']}")

    # 输出需要审核的路由列表
    if needs_review_routes:
        review_file = output_path.parent / 'routes_need_review.json'
        with open(review_file, 'w', encoding='utf-8') as f:
            json.dump(needs_review_routes, f, ensure_ascii=False, indent=2)
        logger.warning(
            f"⚠️  需人工审核的路由列表已保存到: {review_file}"
        )

    return stats


def main():
    """主函数"""
    # 文件路径
    project_root = Path(__file__).parent.parent
    input_file = project_root / 'route_process' / 'datasource_definitions.json'
    output_file = project_root / 'route_process' / 'datasource_definitions_enriched.json'

    # 执行扩展
    stats = enrich_definitions(
        input_path=input_file,
        output_path=output_file,
        min_confidence=0.7  # 置信度低于0.7的需要人工审核
    )

    print("\n" + "="*60)
    print("⚠️⚠️⚠️ 重要提示 ⚠️⚠️⚠️")
    print("="*60)
    print("1. 本脚本使用启发式推断，结果可能不准确")
    print("2. 请务必人工审核高频工具（bilibili/zhihu/github）的推断结果")
    print("3. 低置信度的路由列表已保存到 routes_need_review.json")
    print("4. 发现问题时请直接修改 datasource_definitions_enriched.json")
    print("="*60)


if __name__ == '__main__':
    main()
