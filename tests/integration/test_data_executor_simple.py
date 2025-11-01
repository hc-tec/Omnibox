"""
DataExecutor简单测试脚本（手动跑）

注意：该文件仅供开发者在本地手动验证使用，默认不会在pytest中执行。
如需在测试中运行，请设置环境变量 RSSHUB_TEST_REAL=1。
"""

import os
import sys
from pathlib import Path

import pytest

if os.getenv("RSSHUB_TEST_REAL", "0") != "1":
    pytest.skip(
        "仅当 RSSHUB_TEST_REAL=1 时才运行手动测试脚本",
        allow_module_level=True
    )

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from integration.data_executor import DataExecutor, create_data_executor_from_config
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_health_check():
    """测试健康检查"""
    print("\n" + "=" * 80)
    print("测试1：健康检查")
    print("=" * 80)

    executor = DataExecutor()
    healthy = executor.ensure_rsshub_alive()

    if healthy:
        print("✓ 本地RSSHub健康")
    else:
        print("✗ 本地RSSHub不可用")

    executor.close()
    return healthy


def test_fetch_rss():
    """测试RSS数据获取 - 万物皆可RSS"""
    print("\n" + "=" * 80)
    print("测试2：获取RSS数据（万物皆可RSS）")
    print("=" * 80)

    with DataExecutor() as executor:
        path = "/bilibili/user/video/2267573"
        print(f"\n请求路径: {path}")
        print("提示：RSSHub支持各种数据源（视频/动态/帖子/商品等）")

        result = executor.fetch_rss(path)

        print(f"\n结果状态: {result.status}")
        print(f"数据来源: {result.source}")

        if result.status == "success":
            print(f"Feed标题: {result.feed_title}")
            print(f"Feed链接: {result.feed_link}")
            print(f"Feed描述: {result.feed_description}")
            print(f"返回payload类型: {type(result.payload).__name__}")
            if isinstance(result.payload, dict):
                print(f"payload键: {list(result.payload.keys())[:10]}")
        else:
            print(f"错误信息: {result.error_message}")


def test_url_encoding():
    """测试路径编码，确保特殊字符不会丢失"""
    print("\n" + "=" * 80)
    print("测试3：路径编码安全性")
    print("=" * 80)

    with DataExecutor() as executor:
        url = executor._build_request_url(
            "http://localhost:1200",
            "/hupu/bbs/#步行街主干道/1"
        )
        print(f"构建后的URL: {url}")
        assert "%23步行街主干道" in url, "路径中的#未正确编码"
        assert "format=json" in url, "缺少format参数"


def test_from_config():
    """测试从配置文件创建"""
    print("\n" + "=" * 80)
    print("测试4：从配置文件创建")
    print("=" * 80)

    executor = create_data_executor_from_config()
    print("✓ 从配置创建成功")
    print(f"  本地地址: {executor.base_url}")
    print(f"  降级地址: {executor.fallback_url}")
    print(f"  健康检查超时: {executor.health_check_timeout}秒")
    print(f"  请求超时: {executor.request_timeout}秒")
    print(f"  最大重试: {executor.max_retries}次")
    executor.close()


def main():
    """主函数：手动运行所有测试"""
    print("=" * 80)
    print("DataExecutor 手动功能测试")
    print("=" * 80)

    try:
        healthy = test_health_check()
        test_fetch_rss()
        test_url_encoding()
        test_from_config()

        print("\n" + "=" * 80)
        print("所有测试完成！")
        print("=" * 80)

        if not healthy:
            print("\n提示：本地RSSHub未启动，已自动降级到公共服务")
            print("启动本地RSSHub: cd deploy && docker-compose up -d")

    except Exception as exc:
        logger.error(f"测试失败: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
