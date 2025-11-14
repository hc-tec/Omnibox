"""
RAG 向量库重建脚本（使用扩展后的工具定义）

⚠️⚠️⚠️ 重要说明 ⚠️⚠️⚠️
本脚本会使用包含订阅系统元数据的扩展工具定义重建向量库。

新增的元数据字段：
- platform: 平台标识（如 "bilibili", "zhihu"）
- entity_type: 实体类型（如 "user", "repo"）
- parameter_type: 参数类型（"entity_ref" / "literal" / "enum"）
- required_identifiers: 必需的实体标识符列表

这些元数据将存储在向量库的 metadata 中，供后续的订阅解析逻辑使用。
"""

import sys
import json
from pathlib import Path
import logging
import shutil

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rag_system.rag_pipeline import RAGPipeline
from rag_system.config import (
    VECTOR_DB_PATH,
    SEMANTIC_DOCS_PATH,
    EMBEDDING_MODEL_CONFIG,
    CHROMA_CONFIG,
    RETRIEVAL_CONFIG,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backup_existing_vector_db(vector_db_path: Path) -> bool:
    """
    备份现有向量库

    Args:
        vector_db_path: 向量库路径

    Returns:
        是否成功备份
    """
    if not vector_db_path.exists():
        logger.info("向量库不存在，无需备份")
        return False

    backup_path = vector_db_path.parent / f"{vector_db_path.name}_backup"

    # 如果备份已存在，删除旧备份
    if backup_path.exists():
        logger.warning(f"删除旧备份: {backup_path}")
        shutil.rmtree(backup_path)

    # 创建新备份
    logger.info(f"备份现有向量库: {vector_db_path} → {backup_path}")
    shutil.copytree(vector_db_path, backup_path)
    logger.info("✅ 备份完成")
    return True


def validate_enriched_definitions(enriched_file: Path) -> bool:
    """
    验证扩展后的定义文件是否包含必要的元数据

    Args:
        enriched_file: 扩展后的定义文件路径

    Returns:
        是否验证通过
    """
    logger.info(f"验证扩展定义文件: {enriched_file}")

    try:
        with open(enriched_file, 'r', encoding='utf-8') as f:
            providers = json.load(f)

        total_routes = 0
        routes_with_platform = 0
        routes_with_entity_type = 0
        routes_with_param_type = 0

        for provider in providers:
            for route in provider.get('routes', []):
                total_routes += 1

                # 检查 platform
                if 'platform' in route:
                    routes_with_platform += 1

                # 检查 entity_type
                if 'entity_type' in route:
                    routes_with_entity_type += 1

                # 检查 parameter_type
                for param in route.get('parameters', []):
                    if 'parameter_type' in param:
                        routes_with_param_type += 1
                        break

        logger.info(f"验证统计:")
        logger.info(f"  - 总路由数: {total_routes}")
        logger.info(f"  - 包含 platform: {routes_with_platform} ({routes_with_platform/total_routes*100:.1f}%)")
        logger.info(f"  - 包含 entity_type: {routes_with_entity_type} ({routes_with_entity_type/total_routes*100:.1f}%)")
        logger.info(f"  - 包含 parameter_type: {routes_with_param_type} ({routes_with_param_type/total_routes*100:.1f}%)")

        if routes_with_platform == total_routes:
            logger.info("✅ 验证通过：所有路由都包含 platform 字段")
            return True
        else:
            logger.error("❌ 验证失败：部分路由缺少 platform 字段")
            return False

    except Exception as e:
        logger.error(f"验证失败: {e}")
        return False


def rebuild_vector_store(
    enriched_definitions_file: Path,
    force: bool = False,
    backup: bool = True
) -> bool:
    """
    重建向量库（使用扩展后的定义）

    Args:
        enriched_definitions_file: 扩展后的定义文件路径
        force: 是否强制重建（不询问）
        backup: 是否备份现有向量库

    Returns:
        是否成功重建
    """
    logger.info("\n" + "="*80)
    logger.info("开始重建 RAG 向量库")
    logger.info("="*80)

    # 验证扩展定义文件
    if not validate_enriched_definitions(enriched_definitions_file):
        logger.error("扩展定义文件验证失败，终止重建")
        return False

    # 备份现有向量库
    if backup:
        backup_existing_vector_db(VECTOR_DB_PATH)

    # 初始化 RAG Pipeline（使用扩展后的定义文件）
    logger.info(f"\n使用扩展定义文件: {enriched_definitions_file}")
    pipeline = RAGPipeline(
        datasource_file=enriched_definitions_file,  # ⭐ 使用扩展后的文件
        semantic_docs_path=SEMANTIC_DOCS_PATH,
        vector_db_path=VECTOR_DB_PATH,
        embedding_config=EMBEDDING_MODEL_CONFIG,
        chroma_config=CHROMA_CONFIG,
        retrieval_config=RETRIEVAL_CONFIG,
    )

    # 构建索引
    try:
        logger.info("\n开始构建向量索引...")
        pipeline.build_index(force_rebuild=force, batch_size=32)
        logger.info("\n" + "="*80)
        logger.info("✅ 向量库重建完成")
        logger.info("="*80)
        return True

    except Exception as e:
        logger.error(f"\n❌ 向量库重建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_vector_store_metadata():
    """
    验证重建后的向量库是否包含新的元数据

    检查内容：
    - 随机抽样 10 个 route，检查 metadata 中是否包含 platform、entity_type 等字段
    """
    logger.info("\n" + "="*80)
    logger.info("验证向量库元数据")
    logger.info("="*80)

    try:
        from rag_system.vector_store import VectorStore

        # 加载向量库
        vector_store = VectorStore(
            persist_directory=VECTOR_DB_PATH,
            collection_name=CHROMA_CONFIG["collection_name"],
            distance_metric=CHROMA_CONFIG["distance_metric"],
        )

        # 随机获取 10 个文档
        results = vector_store.collection.get(limit=10)

        if not results or not results['ids']:
            logger.error("❌ 向量库为空，验证失败")
            return False

        logger.info(f"抽样检查 {len(results['ids'])} 个文档:")

        has_platform = 0
        has_entity_type = 0
        has_parameter_type = 0

        for i, (doc_id, metadata) in enumerate(zip(results['ids'], results['metadatas'])):
            # 解析 route_definition
            route_def_str = metadata.get('route_definition', '{}')
            route_def = json.loads(route_def_str)

            has_platform_field = 'platform' in route_def
            has_entity_type_field = 'entity_type' in route_def
            has_param_type_field = any(
                'parameter_type' in p
                for p in route_def.get('parameters', [])
            )

            if has_platform_field:
                has_platform += 1
            if has_entity_type_field:
                has_entity_type += 1
            if has_param_type_field:
                has_parameter_type += 1

            logger.info(
                f"  [{i+1}] {doc_id}: "
                f"platform={'✓' if has_platform_field else '✗'} "
                f"entity_type={'✓' if has_entity_type_field else '✗'} "
                f"param_type={'✓' if has_param_type_field else '✗'}"
            )

        total = len(results['ids'])
        logger.info(f"\n统计:")
        logger.info(f"  - 包含 platform: {has_platform}/{total}")
        logger.info(f"  - 包含 entity_type: {has_entity_type}/{total}")
        logger.info(f"  - 包含 parameter_type: {has_parameter_type}/{total}")

        if has_platform == total:
            logger.info("\n✅ 验证通过：向量库元数据完整")
            return True
        else:
            logger.warning("\n⚠️  验证警告：部分文档缺少新元数据")
            return False

    except Exception as e:
        logger.error(f"验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='重建 RAG 向量库（使用扩展后的工具定义）'
    )
    parser.add_argument(
        '--enriched-file',
        type=str,
        default='route_process/datasource_definitions_enriched.json',
        help='扩展后的工具定义文件路径（相对于项目根目录）'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重建，不询问确认'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='不备份现有向量库'
    )
    parser.add_argument(
        '--skip-verify',
        action='store_true',
        help='跳过元数据验证'
    )

    args = parser.parse_args()

    # 构建扩展文件的绝对路径
    enriched_file = project_root / args.enriched_file

    if not enriched_file.exists():
        logger.error(f"错误：扩展定义文件不存在: {enriched_file}")
        logger.error("请先运行 'python -m scripts.enrich_tool_definitions' 生成扩展定义")
        return 1

    # 重建向量库
    success = rebuild_vector_store(
        enriched_definitions_file=enriched_file,
        force=args.force,
        backup=not args.no_backup
    )

    if not success:
        logger.error("\n向量库重建失败")
        return 1

    # 验证元数据
    if not args.skip_verify:
        verify_success = verify_vector_store_metadata()
        if not verify_success:
            logger.warning("\n⚠️  元数据验证未通过，但向量库已重建")
            return 0

    logger.info("\n" + "="*80)
    logger.info("✅ 所有步骤完成")
    logger.info("="*80)
    logger.info("\n下一步:")
    logger.info("1. 开始实施 Phase 1：创建 entity_resolver_helper.py")
    logger.info("2. 在 RAGInAction 中集成参数验证逻辑")
    logger.info("3. 移除 DataQueryService 中的订阅预检")
    logger.info("="*80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
