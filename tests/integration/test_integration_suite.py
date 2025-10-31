"""
Integration层完整测试套件
包含：
1. DataExecutor 测试
2. CacheService 测试
3. 集成测试
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from integration.data_executor import DataExecutor
from integration.cache_service import CacheService, reset_cache_service
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)


def test_executor_cache_integration():
    """测试DataExecutor与CacheService的集成"""
    print("\n" + "="*80)
    print("集成测试：DataExecutor + CacheService")
    print("="*80)

    cache = CacheService()
    executor = DataExecutor()

    try:
        # 测试路径
        test_path = "/hupu/bbs/bxj/1"

        # 1. 检查缓存中是否有数据（应该没有）
        cached_result = cache.get_rss_cache(test_path)
        assert cached_result is None, "首次测试时缓存应该为空"
        print("✓ 初始状态：缓存为空")

        # 2. 执行请求
        result = executor.fetch_rss(test_path)
        print(f"✓ 执行请求: {result.status}")

        # 3. 将结果存入缓存
        if result.status == "success":
            cache.set_rss_cache(test_path, result)
            print("✓ 结果已存入缓存")

            # 4. 从缓存读取
            cached_result = cache.get_rss_cache(test_path)
            assert cached_result is not None, "缓存应该存在"
            assert cached_result.status == "success", "缓存结果状态应该正确"
            assert len(cached_result.items) == len(result.items), "缓存数据应该完整"
            print(f"✓ 从缓存读取: {len(cached_result.items)}条数据")

            # 5. 验证缓存命中统计
            stats = cache.get_stats()
            assert stats['rss_hits'] >= 1, "应该有缓存命中"
            print(f"✓ 缓存统计: 命中率 {stats['rss_hit_rate']:.2%}")

        else:
            print(f"⚠️ 请求失败: {result.error_message}")
            print("继续测试其他功能...")

    finally:
        executor.close()


def test_cache_ttl_with_real_data():
    """测试TTL在实际数据上的效果"""
    print("\n" + "="*80)
    print("集成测试：TTL在实际数据上的效果")
    print("="*80)

    # 使用短TTL进行测试
    cache = CacheService(rss_cache_ttl=2)  # 2秒TTL
    executor = DataExecutor()

    try:
        test_path = "/bilibili/user/video/2267573"

        # 执行请求并缓存
        result = executor.fetch_rss(test_path)
        if result.status == "success":
            cache.set_rss_cache(test_path, result)
            print(f"✓ 请求数据并缓存: {len(result.items)}条")

            # 立即从缓存获取
            cached = cache.get_rss_cache(test_path)
            assert cached is not None, "刚缓存的数据应该能获取到"
            print("✓ 立即从缓存获取成功")

            # 等待过期
            print("等待2.1秒让缓存过期...")
            time.sleep(2.1)

            # 再次获取应该失败
            cached = cache.get_rss_cache(test_path)
            assert cached is None, "过期的缓存应该被清理"
            print("✓ 过期缓存自动清理")
        else:
            print(f"⚠️ 请求失败: {result.error_message}")

    finally:
        executor.close()


def test_multiple_sources_caching():
    """测试不同数据源的缓存"""
    print("\n" + "="*80)
    print("集成测试：多数据源缓存")
    print("="*80)

    cache = CacheService()
    executor = DataExecutor()

    # 不同数据源的测试路径
    test_paths = [
        "/hupu/bbs/bxj/1",      # 虎扑论坛
        "/bilibili/user/video/2267573",  # B站视频
    ]

    try:
        results = {}

        # 分别请求不同数据源
        for path in test_paths:
            print(f"\n请求数据源: {path}")
            result = executor.fetch_rss(path)
            results[path] = result

            if result.status == "success":
                # 缓存结果
                cache.set_rss_cache(path, result)
                print(f"✓ 缓存成功: {result.feed_title} ({len(result.items)}条)")

                # 立即验证缓存
                cached = cache.get_rss_cache(path)
                assert cached is not None, "刚缓存的数据应该能获取到"
                assert cached.feed_title == result.feed_title, "缓存标题应该匹配"
                print(f"✓ 缓存验证成功")
            else:
                print(f"⚠️ 请求失败: {result.error_message}")

        # 验证不同数据源的缓存是独立的
        cached_data = {}
        for path in test_paths:
            cached = cache.get_rss_cache(path)
            if cached is not None:
                cached_data[path] = cached.feed_title

        print(f"\n✓ 成功缓存了 {len(cached_data)} 个数据源:")
        for path, title in cached_data.items():
            print(f"  {path}: {title}")

    finally:
        executor.close()


def test_cache_invalidation():
    """测试缓存失效功能"""
    print("\n" + "="*80)
    print("集成测试：缓存失效")
    print("="*80)

    cache = CacheService()

    # 设置一些测试缓存
    test_keys = ["/test1", "/test2", "/test3"]
    test_data = {"items": [{"title": f"test item {i}"} for i in range(3)]}

    for key in test_keys:
        cache.set_rss_cache(key, test_data)
        print(f"✓ 设置缓存: {key}")

    # 验证缓存存在
    for key in test_keys:
        cached = cache.get_rss_cache(key)
        assert cached is not None, f"缓存 {key} 应该存在"
        print(f"✓ 缓存存在: {key}")

    # 失效其中一个缓存
    key_to_invalidate = test_keys[1]
    success = cache.invalidate_rss_cache(key_to_invalidate)
    assert success, "缓存失效应该成功"
    print(f"✓ 缓存失效: {key_to_invalidate}")

    # 验证失效结果
    cached = cache.get_rss_cache(key_to_invalidate)
    assert cached is None, "失效的缓存应该不存在"
    print(f"✓ 失效验证: {key_to_invalidate}")

    # 验证其他缓存仍然存在
    for key in test_keys:
        if key != key_to_invalidate:
            cached = cache.get_rss_cache(key)
            assert cached is not None, f"未失效的缓存 {key} 应该存在"
            print(f"✓ 未受影响: {key}")

    # 尝试失效不存在的缓存
    success = cache.invalidate_rss_cache("/nonexistent")
    assert not success, "不存在的缓存失效应该返回False"
    print("✓ 不存在缓存的失效操作正确")


def test_error_handling_with_cache():
    """测试错误处理与缓存的结合"""
    print("\n" + "="*80)
    print("集成测试：错误处理与缓存")
    print("="*80)

    cache = CacheService()
    executor = DataExecutor()

    try:
        # 1. 测试无效路径的缓存处理
        invalid_path = "/invalid/nonexistent/path"
        result = executor.fetch_rss(invalid_path)

        print(f"无效路径请求结果: {result.status}")
        if result.status == "error":
            # 不缓存错误结果（这是策略选择）
            print("✓ 错误结果不缓存")

            # 验证缓存中没有错误结果
            cached = cache.get_rss_cache(invalid_path)
            assert cached is None, "错误结果不应该被缓存"
            print("✓ 错误结果未被缓存")

        # 2. 测试网络错误（通过不存在的地址模拟）
        # 注意：这个测试可能会比较慢，因为需要等待超时
        print("\n测试网络超时处理...")
        original_timeout = executor.request_timeout
        executor.request_timeout = 1  # 1秒超时

        # 使用一个可能不存在的地址
        result = executor.fetch_rss("/test/timeout")
        print(f"超时测试结果: {result.status}")

        executor.request_timeout = original_timeout  # 恢复超时设置

    finally:
        executor.close()


def test_performance_with_cache():
    """测试缓存的性能提升"""
    print("\n" + "="*80)
    print("集成测试：缓存性能提升")
    print("="*80)

    cache = CacheService()
    executor = DataExecutor()

    try:
        test_path = "/hupu/bbs/bxj/1"

        # 1. 第一次请求（无缓存）
        start_time = time.time()
        result1 = executor.fetch_rss(test_path)
        first_request_time = time.time() - start_time

        if result1.status == "success":
            print(f"✓ 第一次请求耗时: {first_request_time:.3f}秒")

            # 缓存结果
            cache.set_rss_cache(test_path, result1)

            # 2. 第二次请求（从缓存）
            start_time = time.time()
            result2 = cache.get_rss_cache(test_path)
            cache_request_time = time.time() - start_time

            print(f"✓ 缓存请求耗时: {cache_request_time:.3f}秒")

            # 3. 性能比较
            if cache_request_time > 0:
                speedup = first_request_time / cache_request_time
                print(f"✓ 缓存加速比: {speedup:.1f}x")

                # 缓存应该明显更快
                assert speedup > 10, f"缓存应该显著更快，但只加速了 {speedup:.1f}x"
                print("✓ 性能提升验证通过")
            else:
                print("⚠️ 缓存请求太快，无法准确测量")

            # 4. 验证数据一致性
            assert result2.items == result1.items, "缓存数据应该与原始数据一致"
            assert result2.feed_title == result1.feed_title, "缓存标题应该一致"
            print("✓ 数据一致性验证通过")

        else:
            print(f"⚠️ 第一次请求失败: {result1.error_message}")

    finally:
        executor.close()


def main():
    """主函数"""
    print("="*80)
    print("Integration层完整测试套件")
    print("="*80)

    try:
        # 重置缓存状态
        reset_cache_service()

        # 集成测试
        test_executor_cache_integration()
        test_cache_ttl_with_real_data()
        test_multiple_sources_caching()
        test_cache_invalidation()
        test_error_handling_with_cache()
        test_performance_with_cache()

        print("\n" + "="*80)
        print("🎉 所有集成测试通过！")
        print("="*80)

    except Exception as e:
        print(f"\n❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
