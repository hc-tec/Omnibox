"""
测试 ActionRegistry 功能

验证配置文件加载和路径构建是否正确。

运行方式：
    python -m scripts.test_action_registry
"""

import sys
import io
from pathlib import Path

# 设置 UTF-8 编码输出（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.subscription.action_registry import ActionRegistry


def test_basic_loading():
    """测试基本加载"""
    print("=" * 80)
    print("测试1: 基本加载")
    print("=" * 80)

    registry = ActionRegistry()
    stats = registry.get_stats()

    print(f"\n✅ 加载成功")
    print(f"   总动作数: {stats['total_actions']}")
    print(f"   支持平台: {stats['total_platforms']}")
    print(f"   实体类型: {stats['total_entity_types']}")

    print(f"\n平台分布（前10）：")
    for platform, count in list(stats['platforms'].items())[:10]:
        print(f"   {platform:20s}: {count:3d} actions")

    print(f"\n实体类型分布：")
    for entity_type, count in stats['entity_types'].items():
        print(f"   {entity_type:20s}: {count:3d} actions")


def test_get_action():
    """测试获取动作"""
    print("\n" + "=" * 80)
    print("测试2: 获取动作定义")
    print("=" * 80)

    registry = ActionRegistry()

    # 测试B站用户视频
    test_cases = [
        ("bilibili", "user", "videos"),
        ("bilibili", "user", "following_videos"),
        ("bilibili", "user", "dynamics"),
        ("zhihu", "column", "articles"),
        ("github", "repo", "commits"),
    ]

    for platform, entity_type, action in test_cases:
        action_def = registry.get_action(platform, entity_type, action)

        if action_def:
            print(f"\n✅ 找到: ({platform}, {entity_type}, {action})")
            print(f"   显示名称: {action_def.display_name}")
            print(f"   路径模板: {action_def.path_template}")
            print(f"   必需标识: {action_def.required_identifiers}")
        else:
            print(f"\n❌ 未找到: ({platform}, {entity_type}, {action})")


def test_build_path():
    """测试路径构建"""
    print("\n" + "=" * 80)
    print("测试3: 构建RSSHub路径")
    print("=" * 80)

    registry = ActionRegistry()

    # 测试用例
    test_cases = [
        {
            "platform": "bilibili",
            "entity_type": "user",
            "action": "videos",
            "identifiers": {"uid": "12345"},
            "expected": "/user/video/12345"
        },
        {
            "platform": "bilibili",
            "entity_type": "user",
            "action": "following_videos",
            "identifiers": {"uid": "12345"},
            "expected": "/followings/video/12345"
        },
        {
            "platform": "zhihu",
            "entity_type": "column",
            "action": "articles",
            "identifiers": {"column_id": "sspai"},
            "expected": "/zhuanlan/sspai"
        },
        {
            "platform": "github",
            "entity_type": "repo",
            "action": "commits",
            "identifiers": {"owner": "langchain-ai", "repo": "langchain"},
            "expected": "/github/commits/langchain-ai/langchain"
        },
    ]

    for i, test in enumerate(test_cases, 1):
        path = registry.build_path(
            platform=test["platform"],
            entity_type=test["entity_type"],
            action=test["action"],
            identifiers=test["identifiers"]
        )

        if path:
            status = "✅" if path == test["expected"] else "⚠️ "
            print(f"\n{status} 测试 {i}:")
            print(f"   平台: {test['platform']}")
            print(f"   实体: {test['entity_type']}")
            print(f"   动作: {test['action']}")
            print(f"   标识: {test['identifiers']}")
            print(f"   结果: {path}")
            if path != test["expected"]:
                print(f"   期望: {test['expected']}")
        else:
            print(f"\n❌ 测试 {i}: 无法构建路径")


def test_get_supported_actions():
    """测试获取支持的动作"""
    print("\n" + "=" * 80)
    print("测试4: 获取支持的动作")
    print("=" * 80)

    registry = ActionRegistry()

    test_cases = [
        ("bilibili", "user"),
        ("zhihu", "column"),
        ("github", "repo"),
    ]

    for platform, entity_type in test_cases:
        actions = registry.get_supported_actions(platform, entity_type)

        print(f"\n{platform} - {entity_type}:")
        if actions:
            print(f"   支持 {len(actions)} 个动作:")
            for action in sorted(actions):
                action_def = registry.get_action(platform, entity_type, action)
                print(f"     - {action:20s} ({action_def.display_name})")
        else:
            print(f"   ❌ 未找到支持的动作")


def main():
    """运行所有测试"""
    try:
        test_basic_loading()
        test_get_action()
        test_build_path()
        test_get_supported_actions()

        print("\n" + "=" * 80)
        print("✅ 所有测试完成")
        print("=" * 80)

    except FileNotFoundError as e:
        print(f"\n❌ 错误: {e}")
        print("\n请先运行:")
        print("   python -m scripts.generate_action_registry")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
