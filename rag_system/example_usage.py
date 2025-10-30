"""
RAG系统使用示例
演示如何使用RAG管道进行路由检索
"""
from rag_pipeline import RAGPipeline
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_1_build_index():
    """
    示例1：构建向量索引
    首次使用时需要运行此函数
    """
    print("\n" + "="*80)
    print("示例1：构建向量索引")
    print("="*80)

    # 初始化RAG管道
    pipeline = RAGPipeline()

    # 构建索引（这会花费几分钟时间，取决于数据量）
    pipeline.build_index(force_rebuild=True, batch_size=32)


def example_2_simple_search():
    """
    示例2：简单查询
    根据用户的自然语言查询，找到最相关的路由
    """
    print("\n" + "="*80)
    print("示例2：简单查询")
    print("="*80)

    # 初始化RAG管道
    pipeline = RAGPipeline()

    # 查询示例
    queries = [
        "虎扑步行街的热门帖子",
        "获取GitHub trending仓库",
        "微博热搜榜单",
        "知乎热门问题",
        "B站最新视频",
    ]

    for query in queries:
        print(f"\n查询: {query}")
        print("-" * 80)

        # 执行搜索
        results = pipeline.search(query=query, top_k=3, verbose=False)

        # 打印结果
        if results:
            for i, (route_id, score, route_def) in enumerate(results, 1):
                print(f"\n{i}. 路由ID: {route_id}")
                print(f"   相似度: {score:.4f}")
                print(f"   数据源: {route_def.get('datasource', 'N/A')}")
                print(f"   名称: {route_def.get('name', 'N/A')}")
                print(f"   描述: {route_def.get('description', 'N/A')[:100]}")
        else:
            print("   未找到相关结果")


def example_3_advanced_search():
    """
    示例3：高级搜索
    使用过滤条件和自定义参数
    """
    print("\n" + "="*80)
    print("示例3：高级搜索（带过滤）")
    print("="*80)

    pipeline = RAGPipeline()

    # 只搜索虎扑相关的路由
    query = "热门帖子"
    print(f"\n查询: {query} (仅搜索虎扑数据源)")
    print("-" * 80)

    results = pipeline.search(
        query=query,
        top_k=5,
        filter_datasource="hupu",  # 过滤特定数据源
        verbose=False,
    )

    for i, (route_id, score, route_def) in enumerate(results, 1):
        print(f"{i}. [{score:.4f}] {route_id} - {route_def.get('name', 'N/A')}")


def example_4_get_route_definition():
    """
    示例4：获取完整路由定义
    根据route_id获取完整的JSON定义
    """
    print("\n" + "="*80)
    print("示例4：获取完整路由定义")
    print("="*80)

    pipeline = RAGPipeline()

    # 先搜索
    query = "虎扑步行街"
    results = pipeline.search(query=query, top_k=1, verbose=False)

    if results:
        route_id, score, route_def = results[0]
        print(f"\n查询: {query}")
        print(f"找到路由: {route_id} (相似度: {score:.4f})")
        print("\n完整路由定义:")
        print("-" * 80)

        # 打印完整定义
        import json
        print(json.dumps(route_def, ensure_ascii=False, indent=2))


def example_5_batch_search():
    """
    示例5：批量查询
    同时处理多个查询
    """
    print("\n" + "="*80)
    print("示例5：批量查询")
    print("="*80)

    pipeline = RAGPipeline()

    # 批量查询
    queries = [
        "NBA篮球新闻",
        "Python编程教程",
        "电影评分排行",
        "天气预报",
    ]

    print(f"\n批量查询 {len(queries)} 个问题:")
    print("-" * 80)

    all_results = {}
    for query in queries:
        results = pipeline.search(query=query, top_k=1, verbose=False)
        all_results[query] = results

    # 打印摘要
    for query, results in all_results.items():
        if results:
            route_id, score, _ = results[0]
            print(f"✓ {query:<30} -> {route_id} ({score:.3f})")
        else:
            print(f"✗ {query:<30} -> 未找到")


def example_6_statistics():
    """
    示例6：查看系统统计信息
    """
    print("\n" + "="*80)
    print("示例6：系统统计信息")
    print("="*80)

    pipeline = RAGPipeline()
    pipeline.show_statistics()


def example_7_semantic_understanding():
    """
    示例7：语义理解能力测试
    测试系统对不同表达方式的理解能力
    """
    print("\n" + "="*80)
    print("示例7：语义理解能力测试")
    print("="*80)

    pipeline = RAGPipeline()

    # 同一意图的不同表达
    similar_queries = [
        "虎扑步行街最新帖子",
        "给我看看虎扑社区的新内容",
        "hupu bbs latest posts",
        "虎扑论坛热门讨论",
    ]

    print("\n测试相同意图的不同表达:")
    print("-" * 80)

    for query in similar_queries:
        results = pipeline.search(query=query, top_k=1, verbose=False)
        if results:
            route_id, score, _ = results[0]
            print(f"{query:<40} -> {route_id} ({score:.3f})")


def main():
    """运行所有示例"""
    print("\n")
    print("="*80)
    print("RAG系统使用示例")
    print("="*80)

    # 注意：首次使用需要先构建索引
    # example_1_build_index()  # 取消注释来构建索引

    # 运行各种查询示例
    try:
        example_2_simple_search()
        example_3_advanced_search()
        example_4_get_route_definition()
        example_5_batch_search()
        example_6_statistics()
        example_7_semantic_understanding()
    except Exception as e:
        print(f"\n错误: {e}")
        print("\n提示: 如果向量数据库为空，请先运行 example_1_build_index() 构建索引")


if __name__ == "__main__":
    main()
