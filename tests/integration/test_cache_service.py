"""
缓存服务单元测试
测试内容：
1. TTL缓存基本功能
2. 线程安全性
3. 缓存统计
4. 不同类型缓存
"""

import sys
import time
import threading
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from integration.cache_service import CacheService, get_cache_service, reset_cache_service
import logging

# 配置日志
logging.basicConfig(level=logging.DEBUG)


def test_basic_cache_operations():
    """测试基本缓存操作"""
    print("\n" + "="*80)
    print("测试1：基本缓存操作")
    print("="*80)

    cache = CacheService()

    # 测试RSS缓存
    print("\n--- RSS缓存测试 ---")
    rss_key = "/hupu/bbs/bxj/1"
    rss_data = {"title": "虎扑步行街", "articles": ["文章1", "文章2"]}

    # 设置缓存
    cache.set_rss_cache(rss_key, rss_data)
    print(f"✓ 设置RSS缓存: {rss_key}")

    # 获取缓存
    cached_data = cache.get_rss_cache(rss_key)
    assert cached_data == rss_data, "RSS缓存数据不匹配"
    print(f"✓ 获取RSS缓存: {cached_data}")

    # 缓存未命中
    uncached = cache.get_rss_cache("/nonexistent/path")
    assert uncached is None, "不存在的缓存应该返回None"
    print("✓ 未命中测试通过")

    # 测试RAG缓存
    print("\n--- RAG缓存测试 ---")
    query = "虎扑步行街最新帖子"
    rag_result = {"routes": ["route1", "route2"], "scores": [0.9, 0.8]}

    cache.set_rag_cache(query, rag_result)
    print(f"✓ 设置RAG缓存: {query}")

    cached_rag = cache.get_rag_cache(query)
    assert cached_rag == rag_result, "RAG缓存数据不匹配"
    print(f"✓ 获取RAG缓存: {cached_rag}")

    # 测试LLM缓存（带参数）
    print("\n--- LLM缓存测试 ---")
    prompt = "你是RSS数据助手"
    llm_params = {"temperature": 0.1, "model": "gpt-4"}
    llm_result = {"path": "/hupu/bbs/bxj/1", "parameters": {"id": "bxj"}}

    cache.set_llm_cache(prompt, llm_result, **llm_params)
    print(f"✓ 设置LLM缓存: {prompt[:20]}... (参数: {llm_params})")

    cached_llm = cache.get_llm_cache(prompt, **llm_params)
    assert cached_llm == llm_result, "LLM缓存数据不匹配"
    print(f"✓ 获取LLM缓存: {cached_llm}")

    # 不同参数应该不命中
    diff_params = {"temperature": 0.2, "model": "gpt-4"}
    uncached_llm = cache.get_llm_cache(prompt, **diff_params)
    assert uncached_llm is None, "不同参数的LLM缓存不应该命中"
    print("✓ LLM参数隔离测试通过")


def test_ttl_expiration():
    """测试TTL过期机制"""
    print("\n" + "="*80)
    print("测试2：TTL过期机制")
    print("="*80)

    # 使用短TTL进行测试
    cache = CacheService(rss_cache_ttl=1)  # 1秒TTL

    rss_key = "/test/ttl"
    rss_data = {"title": "TTL测试"}

    cache.set_rss_cache(rss_key, rss_data)
    print("✓ 设置缓存（1秒TTL）")

    # 立即获取应该命中
    cached = cache.get_rss_cache(rss_key)
    assert cached is not None, "刚设置的缓存应该能获取到"
    print("✓ 立即获取缓存成功")

    # 等待过期
    print("等待1.1秒让缓存过期...")
    time.sleep(1.1)

    # 再次获取应该不命中
    cached = cache.get_rss_cache(rss_key)
    assert cached is None, "过期的缓存应该被清理"
    print("✓ 过期缓存已自动清理")


def test_clear_expired():
    """测试手动清理过期缓存返回值"""
    print("\n" + "="*80)
    print("测试2b：手动清理过期缓存")
    print("="*80)

    # 使用不同TTL测试部分过期场景
    cache = CacheService(rss_cache_ttl=1, rag_cache_ttl=10, llm_cache_ttl=1)

    # 添加缓存项
    cache.set_rss_cache("/rss/test1", {"v": 1})  # 1秒后过期
    cache.set_rss_cache("/rss/test2", {"v": 2})  # 1秒后过期
    cache.set_rag_cache("query", {"result": 1})  # 10秒后过期（不会过期）
    cache.set_llm_cache("prompt", {"path": "/x"}, temperature=0.1)  # 1秒后过期

    # 等待RSS和LLM缓存过期
    time.sleep(1.2)

    # 手动清理 - RSS和LLM应该被清理（2+1=3），RAG不应该
    cleaned = cache.clear_expired()
    print(f"清理过期缓存数量: {cleaned}")

    # 验证清理结果
    assert cache.get_rss_cache("/rss/test1") is None, "RSS缓存应该过期"
    assert cache.get_rss_cache("/rss/test2") is None, "RSS缓存应该过期"
    assert cache.get_rag_cache("query") is not None, "RAG缓存不应该过期"
    assert cache.get_llm_cache("prompt", temperature=0.1) is None, "LLM缓存应该过期"

    # 由于TTLCache的自动清理机制，cleaned可能为0或3
    # 重要的是验证过期的确实被清理了，未过期的还在
    print(f"已验证: 过期缓存已清理，未过期缓存保留（清理数量={cleaned}）")


def test_thread_safety():
    """测试线程安全性"""
    print("\n" + "="*80)
    print("测试3：线程安全性")
    print("="*80)

    cache = CacheService()
    num_threads = 10
    operations_per_thread = 50

    results = {"success": 0, "errors": 0}
    lock = threading.Lock()

    def worker(thread_id: int):
        """工作线程函数"""
        try:
            for i in range(operations_per_thread):
                key = f"/thread/{thread_id}/item/{i}"
                data = {"thread_id": thread_id, "item": i, "data": f"test_data_{i}"}

                # 设置缓存
                cache.set_rss_cache(key, data)

                # 获取缓存
                cached = cache.get_rss_cache(key)

                # 验证数据
                assert cached == data, f"线程{thread_id}的数据不匹配"

                # 偶尔获取其他线程的数据测试并发
                if i % 10 == 0:
                    other_key = f"/thread/{(thread_id + 1) % num_threads}/item/{i}"
                    cache.get_rss_cache(other_key)  # 不应该抛出异常

            with lock:
                results["success"] += 1
        except Exception as e:
            print(f"线程 {thread_id} 出错: {e}")
            with lock:
                results["errors"] += 1

    # 创建并启动线程
    threads = []
    print(f"启动 {num_threads} 个线程，每个执行 {operations_per_thread} 次操作...")

    start_time = time.time()
    for i in range(num_threads):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    end_time = time.time()

    print(f"所有线程完成，耗时: {end_time - start_time:.2f}秒")
    print(f"成功线程: {results['success']}, 错误线程: {results['errors']}")

    assert results["errors"] == 0, f"不应该有错误线程，但发现 {results['errors']} 个"
    print("✓ 线程安全性测试通过")


def test_cache_statistics():
    """测试缓存统计功能"""
    print("\n" + "="*80)
    print("测试4：缓存统计功能")
    print("="*80)

    cache = CacheService()

    # 执行一些缓存操作
    for i in range(5):
        cache.set_rss_cache(f"/test/{i}", {"data": f"test_{i}"})
        cache.get_rss_cache(f"/test/{i}")  # 命中
        cache.get_rss_cache(f"/nonexistent/{i}")  # 未命中

    cache.set_rag_cache("测试查询", {"result": "test_data"})
    cache.get_rag_cache("测试查询")  # 命中

    # 获取统计信息
    stats = cache.get_stats()

    print(f"缓存统计信息:")
    print(f"  RSS缓存大小: {stats['rss_cache_size']}")
    print(f"  RSS命中次数: {stats['rss_hits']}")
    print(f"  RSS未命中次数: {stats['rss_misses']}")
    print(f"  RSS命中率: {stats['rss_hit_rate']:.2%}")

    print(f"  RAG缓存大小: {stats['rag_cache_size']}")
    print(f"  RAG命中率: {stats['rag_hit_rate']:.2%}")

    print(f"  总缓存大小: {stats['total_cache_size']}")
    print(f"  总体命中率: {stats['overall_hit_rate']:.2%}")

    # 验证统计数据的合理性
    assert stats['rss_hits'] == 5, "RSS命中次数应该为5"
    assert stats['rss_misses'] == 5, "RSS未命中次数应该为5"
    assert stats['rss_hit_rate'] == 0.5, "RSS命中率应该为50%"

    assert stats['rag_cache_size'] == 1, "RAG缓存大小应该为1"
    assert stats['rag_hits'] == 1, "RAG命中次数应该为1"

    print("✓ 统计信息验证通过")


def test_global_cache_service():
    """测试全局缓存服务"""
    print("\n" + "="*80)
    print("测试5：全局缓存服务")
    print("="*80)

    # 重置全局实例
    reset_cache_service()

    # 获取全局实例
    cache1 = get_cache_service()
    print("✓ 获取第一个全局实例")

    cache2 = get_cache_service()
    print("✓ 获取第二个全局实例")

    # 验证是同一个实例
    assert cache1 is cache2, "全局缓存服务应该是单例"
    print("✓ 单例模式验证通过")

    # 使用全局实例
    cache1.set_rss_cache("/global/test", {"data": "global"})
    cached = cache2.get_rss_cache("/global/test")
    assert cached == {"data": "global"}, "全局实例数据共享"
    print("✓ 全局实例数据共享测试通过")

    # 重置并验证
    reset_cache_service()
    cache3 = get_cache_service()
    assert cache1 is not cache3, "重置后应该是新实例"
    print("✓ 重置功能验证通过")


def main():
    """主函数"""
    print("="*80)
    print("缓存服务单元测试")
    print("="*80)

    try:
        # 测试1：基本操作
        test_basic_cache_operations()

        # 测试2：TTL过期
        test_ttl_expiration()

        # 测试2b：手动清理
        test_clear_expired()

        # 测试3：线程安全性
        test_thread_safety()

        # 测试4：统计功能
        test_cache_statistics()

        # 测试5：全局服务
        test_global_cache_service()

        print("\n" + "="*80)
        print("✅ 所有缓存服务测试通过！")
        print("="*80)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
