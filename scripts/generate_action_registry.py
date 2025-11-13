"""
生成 ActionRegistry 配置文件

从 datasource_definitions.json 自动分析路由定义，
推断 entity_type 和 action，生成配置文件。

运行方式：
    python -m scripts.generate_action_registry

参数：
    --min-confidence: 最小置信度阈值（默认0.5）
    --platforms: 平台过滤（逗号分隔，如 bilibili,zhihu）
    --output: 输出文件路径
    --show-low-confidence: 显示低置信度路由
"""

import sys
import io
import argparse
from pathlib import Path

# 设置 UTF-8 编码输出（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.subscription.route_analyzer import RouteAnalyzer


def main():
    parser = argparse.ArgumentParser(
        description="生成 ActionRegistry 配置文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 生成配置（默认）
  python -m scripts.generate_action_registry

  # 只分析B站和知乎
  python -m scripts.generate_action_registry --platforms bilibili,zhihu

  # 提高置信度阈值
  python -m scripts.generate_action_registry --min-confidence 0.8

  # 显示需要人工审核的路由
  python -m scripts.generate_action_registry --show-low-confidence
        """
    )

    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.5,
        help="最小置信度阈值（0-1，默认0.5）"
    )

    parser.add_argument(
        "--platforms",
        type=str,
        default=None,
        help="平台过滤（逗号分隔，如 bilibili,zhihu）"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="services/subscription/action_registry_config.json",
        help="输出文件路径"
    )

    parser.add_argument(
        "--show-low-confidence",
        action="store_true",
        help="显示低置信度路由（需要人工审核）"
    )

    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="只显示统计信息，不生成配置文件"
    )

    args = parser.parse_args()

    # 解析平台过滤
    platforms_filter = None
    if args.platforms:
        platforms_filter = [p.strip() for p in args.platforms.split(",")]
        print(f"平台过滤: {platforms_filter}")

    try:
        # 创建分析器
        analyzer = RouteAnalyzer(
            datasource_file="route_process/datasource_definitions.json"
        )

        # 只显示统计
        if args.stats_only:
            print("\n" + "=" * 80)
            print("路由分析统计")
            print("=" * 80)

            analyzed = analyzer.analyze_all_routes(
                min_confidence=args.min_confidence,
                platforms_filter=platforms_filter
            )

            # 统计各平台
            platform_stats = {}
            for route in analyzed:
                platform_stats[route.platform] = \
                    platform_stats.get(route.platform, 0) + 1

            print(f"\n各平台 action 数量（前20）：")
            for platform, count in sorted(
                platform_stats.items(),
                key=lambda x: x[1],
                reverse=True
            )[:20]:
                print(f"  {platform:20s}: {count:3d} actions")

            return

        # 显示低置信度路由
        if args.show_low_confidence:
            print("\n" + "=" * 80)
            print("低置信度路由（需要人工审核）")
            print("=" * 80)

            analyzer.print_low_confidence_routes(
                min_confidence=args.min_confidence,
                max_confidence=0.8,
                limit=30
            )

            print("\n提示：")
            print("  1. 检查推断的 entity_type 和 action 是否正确")
            print("  2. 如有错误，可手动编辑生成的配置文件")
            print("  3. 或者调整 RouteAnalyzer 的推断规则")

            return

        # 生成配置文件
        print("\n" + "=" * 80)
        print("开始生成 ActionRegistry 配置")
        print("=" * 80)

        config_file = analyzer.generate_action_registry_config(
            output_file=args.output,
            min_confidence=args.min_confidence,
            platforms_filter=platforms_filter
        )

        print("\n✅ 完成！")
        print(f"\n配置文件: {config_file}")
        print("\n下一步：")
        print("  1. 检查生成的配置文件")
        print("  2. 对于置信度较低的路由，手动调整 entity_type 和 action")
        print("  3. 运行以下命令查看低置信度路由：")
        print(f"     python -m scripts.generate_action_registry --show-low-confidence")
        print("  4. 重启应用以加载新配置")

    except FileNotFoundError as e:
        print(f"\n❌ 错误: {e}")
        print("\n请确保以下文件存在：")
        print("  - route_process/datasource_definitions.json")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
