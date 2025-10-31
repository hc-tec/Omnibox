"""
DataExecutor 手动测试脚本（非自动化测试）

使用场景：
- 验证本地 RSSHub 服务是否正常
- 查看 DataExecutor 返回的数据结构

默认不会在 CI 中执行。如果需要运行，建议先启动本地 RSSHub 服务：
    cd deploy && docker-compose up -d
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from integration.data_executor import DataExecutor, create_data_executor_from_config

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_health_check() -> bool:
    """检查本地 RSSHub 是否可用"""
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


def run_fetch_demo():
    """调用 DataExecutor 获取示例数据"""
    print("\n" + "=" * 80)
    print("测试2：获取RSS数据（示例数据源）")
    print("=" * 80)

    path = os.getenv("DATA_EXECUTOR_DEMO_PATH", "/bilibili/user/video/2267573")
    print(f"请求路径: {path}")

    with DataExecutor() as executor:
        result = executor.fetch_rss(path)

        print(f"\n结果状态: {result.status}")
        print(f"数据来源: {result.source}")
        if result.status == "success":
            print(f"Feed标题: {result.feed_title}")
            print(f"数据条数: {len(result.items)}")
            for i, item in enumerate(result.items[:3], 1):
                print(f"\n  {i}. {item.title}")
                print(f"     链接: {item.link}")
                print(f"     发布时间: {item.pub_date}")
                print(f"     描述: {item.description[:100]}...")
        else:
            print(f"错误信息: {result.error_message}")


def run_path_encoding_demo():
    """演示路径编码效果"""
    print("\n" + "=" * 80)
    print("测试3：路径编码安全性")
    print("=" * 80)

    with DataExecutor() as executor:
        url = executor._build_request_url(
            "http://localhost:1200",
            "/hupu/bbs/#步行街主干道/1",
        )
        print(f"构建后的URL: {url}")


def run_config_demo():
    """演示通过配置创建 DataExecutor"""
    print("\n" + "=" * 80)
    print("测试4：配置加载")
    print("=" * 80)

    executor = create_data_executor_from_config()
    print("✓ 从配置创建成功")
    print(f"  本地地址: {executor.base_url}")
    print(f"  降级地址: {executor.fallback_url}")
    print(f"  请求超时: {executor.request_timeout}秒")
    executor.close()


def main():
    print("=" * 80)
    print("DataExecutor 手动测试")
    print("=" * 80)

    try:
        healthy = run_health_check()
        run_fetch_demo()
        run_path_encoding_demo()
        run_config_demo()

        if not healthy:
            print("\n提示：本地RSSHub未启动，已使用降级地址")
            print("启动命令: cd deploy && docker-compose up -d")

    except Exception as exc:
        logger.error("测试过程中发生错误", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
