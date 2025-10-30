"""
快速开始脚本
一键构建索引并测试查询
"""
from rag_pipeline import RAGPipeline
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def quick_start():
    """快速开始"""
    print("\n" + "="*80)
    print("RAG系统 - 快速开始")
    print("="*80)

    # 初始化
    logger.info("\n1. 初始化RAG管道...")
    pipeline = RAGPipeline()

    # 检查是否已有索引
    count = pipeline.vector_store.collection.count()
    if count == 0:
        logger.info("\n2. 首次运行，开始构建向量索引...")
        logger.info("   这可能需要几分钟时间，请耐心等待...\n")
        pipeline.build_index(force_rebuild=True, batch_size=32)
    else:
        logger.info(f"\n2. 检测到已有索引 ({count} 条记录)，跳过构建步骤")

    # 显示统计信息
    logger.info("\n3. 系统统计信息:")
    pipeline.show_statistics()

    # 测试查询
    logger.info("\n4. 测试查询功能")
    logger.info("="*80)

    test_queries = [
        "虎扑步行街热帖",
        "GitHub trending",
        "微博热搜",
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 80)
        results = pipeline.search(query=query, top_k=3, verbose=False)

        for i, (route_id, score, route_def) in enumerate(results, 1):
            print(f"{i}. [{score:.4f}] {route_id}")
            print(f"   {route_def.get('datasource', 'N/A')} - {route_def.get('name', 'N/A')}")

    # 进入交互模式
    logger.info("\n\n5. 进入交互式查询模式")
    logger.info("="*80)
    logger.info("输入查询内容，或输入 'quit' 退出\n")

    while True:
        try:
            query = input("查询 >>> ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                break

            if not query:
                continue

            results = pipeline.search(query=query, top_k=5, verbose=False)

            if not results:
                print("未找到相关结果\n")
            else:
                print("")
                for i, (route_id, score, route_def) in enumerate(results, 1):
                    print(f"{i}. [{score:.4f}] {route_id}")
                    print(f"   数据源: {route_def.get('datasource', 'N/A')}")
                    print(f"   名称: {route_def.get('name', 'N/A')}")
                    print(f"   描述: {route_def.get('description', 'N/A')[:100]}")
                    print("")

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"查询出错: {e}")

    logger.info("\n再见！")


if __name__ == "__main__":
    quick_start()
