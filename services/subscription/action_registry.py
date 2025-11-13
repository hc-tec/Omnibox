"""
动作注册表（配置驱动）

从自动生成的配置文件加载 action 定义，
不再手动维护 ACTION_TEMPLATES。
"""

import json
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ActionDefinition:
    """动作定义

    描述一个实体支持的某个动作及其RSSHub路径模板。
    """
    action_name: str  # "videos", "following", "favorites"
    display_name: str  # "投稿视频", "关注列表", "收藏"
    path_template: str  # "/bilibili/user/video/:uid"
    required_identifiers: List[str]  # ["uid"]
    description: str  # "获取UP主的投稿视频"


class ActionRegistry:
    """动作注册表（配置驱动 v2.0）

    修订：不再手动维护 ACTION_TEMPLATES，
    而是从自动生成的配置文件加载。

    使用单例模式确保全局只有一个实例。
    """

    _instance = None
    _actions: Dict[Tuple[str, str, str], ActionDefinition] = {}
    _loaded = False

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化（只执行一次）"""
        if not self._loaded:
            self._load_config()
            self._loaded = True

    def _load_config(self):
        """从配置文件加载动作定义"""
        config_file = Path("services/subscription/action_registry_config.json")

        if not config_file.exists():
            logger.warning(
                "⚠️  ActionRegistry 配置文件不存在，正在自动生成...\n"
                "   如果这是首次运行，请稍候..."
            )
            self._auto_generate_config(config_file)

        if not config_file.exists():
            logger.error("❌ 无法生成 ActionRegistry 配置文件")
            return

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 加载到内存
            for item in config_data:
                key = (
                    item["platform"],
                    item["entity_type"],
                    item["action"]
                )

                self._actions[key] = ActionDefinition(
                    action_name=item["action"],
                    display_name=item["display_name"],
                    path_template=item["path_template"],
                    required_identifiers=item["required_identifiers"],
                    description=item["description"]
                )

            logger.info(f"✅ ActionRegistry 加载完成：{len(self._actions)} 个动作")

        except Exception as e:
            logger.error(f"❌ 加载 ActionRegistry 配置失败: {e}")

    def _auto_generate_config(self, config_file: Path):
        """自动生成配置文件（首次运行时）"""
        try:
            from services.subscription.route_analyzer import RouteAnalyzer

            logger.info("正在自动生成 ActionRegistry 配置...")

            analyzer = RouteAnalyzer()
            analyzer.generate_action_registry_config(
                output_file=str(config_file),
                min_confidence=0.5
            )

            logger.info("✅ 配置文件生成成功")

        except FileNotFoundError as e:
            logger.error(
                f"❌ 无法找到数据源定义文件: {e}\n"
                f"   请确保 route_process/datasource_definitions.json 存在"
            )
        except Exception as e:
            logger.error(f"❌ 自动生成配置失败: {e}")

    @classmethod
    def get_action(
        cls,
        platform: str,
        entity_type: str,
        action: str
    ) -> Optional[ActionDefinition]:
        """获取动作定义

        Args:
            platform: 平台（bilibili/zhihu/...）
            entity_type: 实体类型（user/column/repo/...）
            action: 动作名称（videos/following/...）

        Returns:
            动作定义，如果不存在则返回 None
        """
        instance = cls()
        return instance._actions.get((platform, entity_type, action))

    @classmethod
    def get_supported_actions(
        cls,
        platform: str,
        entity_type: str
    ) -> List[str]:
        """获取实体支持的所有动作

        Args:
            platform: 平台
            entity_type: 实体类型

        Returns:
            动作名称列表
        """
        instance = cls()
        actions = []

        for (p, et, action), _ in instance._actions.items():
            if p == platform and et == entity_type:
                actions.append(action)

        return actions

    @classmethod
    def get_all_platforms(cls) -> List[str]:
        """获取所有支持的平台"""
        instance = cls()
        platforms = set()

        for (platform, _, _), _ in instance._actions.items():
            platforms.add(platform)

        return sorted(platforms)

    @classmethod
    def get_platform_entity_types(cls, platform: str) -> List[str]:
        """获取平台支持的所有实体类型"""
        instance = cls()
        entity_types = set()

        for (p, entity_type, _), _ in instance._actions.items():
            if p == platform:
                entity_types.add(entity_type)

        return sorted(entity_types)

    @classmethod
    def build_path(
        cls,
        platform: str,
        entity_type: str,
        action: str,
        identifiers: Dict[str, str]
    ) -> Optional[str]:
        """构建RSSHub路径

        Args:
            platform: 平台
            entity_type: 实体类型
            action: 动作
            identifiers: 标识符字典（如 {"uid": "12345"}）

        Returns:
            完整的RSSHub路径，如果无法构建则返回 None

        示例：
            build_path(
                platform="bilibili",
                entity_type="user",
                action="following_videos",
                identifiers={"uid": "12345"}
            )
            → "/followings/video/12345"
        """
        action_def = cls.get_action(platform, entity_type, action)
        if not action_def:
            logger.warning(
                f"未找到动作定义: platform={platform}, "
                f"entity_type={entity_type}, action={action}"
            )
            return None

        # 检查必需的标识符
        for req_id in action_def.required_identifiers:
            if req_id not in identifiers:
                raise ValueError(
                    f"缺少必需的标识符: {req_id}，"
                    f"需要: {action_def.required_identifiers}，"
                    f"提供: {list(identifiers.keys())}"
                )

        # 替换路径模板中的占位符
        path = action_def.path_template

        # 处理必需参数（:param）
        for key, value in identifiers.items():
            path = re.sub(f":{key}(?![a-zA-Z])", str(value), path)

        # 移除可选参数（:param?）
        path = re.sub(r"/:[a-zA-Z_]+\?", "", path)

        return path

    @classmethod
    def reload(cls):
        """重新加载配置（用于配置文件更新后）"""
        if cls._instance:
            cls._instance._actions.clear()
            cls._instance._loaded = False
            cls._instance._load_config()
            cls._instance._loaded = True
            logger.info("✅ ActionRegistry 重新加载完成")

    @classmethod
    def get_stats(cls) -> Dict:
        """获取统计信息"""
        instance = cls()

        platforms = {}
        entity_types = {}

        for (platform, entity_type, _), _ in instance._actions.items():
            platforms[platform] = platforms.get(platform, 0) + 1
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

        return {
            "total_actions": len(instance._actions),
            "total_platforms": len(platforms),
            "total_entity_types": len(entity_types),
            "platforms": dict(sorted(platforms.items(), key=lambda x: x[1], reverse=True)),
            "entity_types": dict(sorted(entity_types.items(), key=lambda x: x[1], reverse=True))
        }


# 导入 re 模块
import re
