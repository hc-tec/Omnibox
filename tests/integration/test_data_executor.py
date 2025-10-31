"""
DataExecutor单元测试
测试内容：
1. 初始化参数
2. URL构建与编码
3. FeedItem/FetchResult 数据结构
4. 配置加载
5. （可选）真实 RSSHub 调用：仅当设置 RSSHUB_TEST_REAL=1 且服务可用
"""

import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from integration.data_executor import DataExecutor, FeedItem, FetchResult, create_data_executor_from_config

import logging

# 配置日志（调试时使用）
logging.basicConfig(level=logging.INFO)


REAL_RSSHUB_ENABLED = os.getenv("RSSHUB_TEST_REAL", "0") == "1"


@pytest.fixture(scope="module")
def executor():
    """提供 DataExecutor 实例"""
    exec_ = DataExecutor()
    yield exec_
    exec_.close()


class TestDataExecutorUnit:
    """DataExecutor 单元测试"""

    def test_init_default_values(self, executor):
        """测试默认初始化值"""
        assert executor.base_url == "http://localhost:1200"
        assert executor.fallback_url == "https://rsshub.app"
        assert executor.health_check_timeout == 3
        assert executor.request_timeout == 30
        assert executor.max_retries == 2

    def test_init_custom_values(self):
        """测试自定义初始化值"""
        custom = DataExecutor(
            base_url="http://custom:8080",
            fallback_url="https://fallback.rsshub.app",
            health_check_timeout=5,
            request_timeout=60,
            max_retries=3,
        )

        assert custom.base_url == "http://custom:8080"
        assert custom.fallback_url == "https://fallback.rsshub.app"
        assert custom.health_check_timeout == 5
        assert custom.request_timeout == 60
        assert custom.max_retries == 3
        custom.close()

    def test_context_manager(self):
        """测试上下文管理器"""
        with DataExecutor() as manager_executor:
            assert manager_executor.base_url == "http://localhost:1200"

    def test_build_request_url_basic(self, executor):
        """测试基本URL构建"""
        url = executor._build_request_url(
            "http://localhost:1200",
            "/hupu/bbs/bxj/1"
        )
        assert url == "http://localhost:1200/hupu/bbs/bxj/1?format=json"

    def test_build_request_url_with_query(self, executor):
        """测试带查询参数的URL构建"""
        url = executor._build_request_url(
            "http://localhost:1200",
            "/hupu/bbs/bxj/1?order=1&limit=10"
        )
        assert "format=json" in url
        assert "order=1" in url
        assert "limit=10" in url

    def test_build_request_url_with_special_chars(self, executor):
        """测试特殊字符URL编码"""
        url = executor._build_request_url(
            "http://localhost:1200",
            "/hupu/bbs/#步行街主干道/1"
        )
        # # 号应该被编码为 %23
        assert "%23" in url
        # 中文应该被正确URL编码
        assert "%E6%AD%A5%E8%A1%8C%E8%A1%97" in url  # "步行街"的UTF-8编码
        assert "format=json" in url

    def test_build_request_url_format_duplicate(self, executor):
        """测试format参数重复处理"""
        url = executor._build_request_url(
            "http://localhost:1200",
            "/hupu/bbs/1?format=xml"
        )
        assert url.count("format=") == 1
        assert "format=json" in url

    def test_split_path_and_query(self):
        """测试路径和查询参数拆分"""
        cases = [
            ("/path/only", ("/path/only", "")),
            ("/path/with?query=1", ("/path/with", "query=1")),
            ("path/without/leading/slash", ("/path/without/leading/slash", "")),
        ]

        for input_path, expected in cases:
            result = DataExecutor._split_path_and_query(input_path)
            assert result == expected

    def test_encode_path(self):
        """测试路径编码"""
        cases = [
            ("/simple/path", "/simple/path"),
            ("/path with space", "/path%20with%20space"),
            ("/path/#fragment", "/path/%23fragment"),
            ("/中文/path", "/%E4%B8%AD%E6%96%87/path"),
        ]

        for input_path, expected in cases:
            result = DataExecutor._encode_path(input_path)
            assert result == expected

    def test_build_query_params(self):
        """测试查询参数构建"""
        params = DataExecutor._build_query_params("a=1&b=2")
        assert ("a", "1") in params
        assert ("b", "2") in params
        assert ("format", "json") in params

        params = DataExecutor._build_query_params("a=1&format=xml")
        assert ("format", "json") in params
        assert ("format", "xml") not in params

        params = DataExecutor._build_query_params("")
        assert ("format", "json") in params
        assert len(params) == 1

    @pytest.mark.parametrize("input_data,expected_title", [
        ({"title": "测试标题", "link": "http://example.com"}, "测试标题"),
        ({"title": "", "link": "http://example.com"}, ""),
        ({}, ""),
    ])
    def test_feed_item_from_rsshub_item(self, input_data, expected_title):
        """测试FeedItem.from_rsshub_item"""
        item = FeedItem.from_rsshub_item(input_data)
        assert item.title == expected_title
        assert item.link == input_data.get("link", "")

    def test_feed_item_media_extraction(self):
        """测试媒体信息提取"""
        item_with_media = {
            "title": "视频",
            "link": "http://example.com/video",
            "enclosure": {
                "url": "http://example.com/video.mp4",
                "type": "video/mp4"
            }
        }
        feed_item = FeedItem.from_rsshub_item(item_with_media)
        assert feed_item.media_url == "http://example.com/video.mp4"
        assert feed_item.media_type == "video"

        item_without_media = {
            "title": "文本",
            "link": "http://example.com/text"
        }
        feed_item = FeedItem.from_rsshub_item(item_without_media)
        assert feed_item.media_url is None
        assert feed_item.media_type is None

    def test_feed_item_category_handling(self):
        """测试分类处理"""
        item_str_category = {
            "title": "测试",
            "category": "tech"
        }
        feed_item = FeedItem.from_rsshub_item(item_str_category)
        assert feed_item.category == ["tech"]

        item_list_category = {
            "title": "测试",
            "category": ["tech", "ai"]
        }
        feed_item = FeedItem.from_rsshub_item(item_list_category)
        assert feed_item.category == ["tech", "ai"]

        item_no_category = {"title": "测试"}
        feed_item = FeedItem.from_rsshub_item(item_no_category)
        assert feed_item.category is None

    def test_fetch_result_post_init(self):
        """测试FetchResult的自动时间戳"""
        result = FetchResult(
            status="success",
            items=[],
            source="local"
        )
        assert result.fetched_at is not None

        custom_time = "2024-01-01T00:00:00"
        result_with_time = FetchResult(
            status="success",
            items=[],
            source="local",
            fetched_at=custom_time
        )
        assert result_with_time.fetched_at == custom_time

    def test_create_data_executor_from_config(self):
        """测试从配置文件创建"""
        try:
            executor = create_data_executor_from_config()
            assert executor is not None
            executor.close()
        except ImportError:
            pytest.skip("无法导入配置文件，跳过测试")


@pytest.fixture(scope="module")
def real_executor():
    """
    真实 RSSHub 测试专用实例。
    仅当设置了 RSSHUB_TEST_REAL=1 且本地服务健康时才运行，避免阻塞CI。
    """
    if not REAL_RSSHUB_ENABLED:
        pytest.skip("未开启真实RSSHub测试，设置 RSSHUB_TEST_REAL=1 以启用")

    exec_ = DataExecutor()
    healthy = exec_.ensure_rsshub_alive()
    if not healthy:
        exec_.close()
        pytest.skip("本地RSSHub未启动，跳过真实请求测试")

    yield exec_
    exec_.close()


class TestDataExecutorReal:
    """真实RSSHub请求测试（可选）"""

    @pytest.mark.slow
    def test_health_check(self, real_executor):
        """测试健康检查"""
        assert real_executor.ensure_rsshub_alive() is True

    @pytest.mark.slow
    def test_fetch_rss_real_data(self, real_executor):
        """测试真实RSS数据获取"""
        result = real_executor.fetch_rss("/hupu/bbs/bxj/1")

        assert isinstance(result, FetchResult)
        assert result.status in ["success", "error"]
        assert result.source in ["local", "fallback"]

        if result.status == "success":
            assert isinstance(result.items, list)
            if result.items:
                assert all(isinstance(item, FeedItem) for item in result.items)
            assert isinstance(result.feed_title, (str, type(None)))
            assert result.fetched_at is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
