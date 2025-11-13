"""
路由分析器

从 datasource_definitions.json 中提取路由信息，
自动推断 entity_type 和 action。
"""

import json
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class AnalyzedRoute:
    """分析后的路由信息"""
    platform: str           # 平台（bilibili/zhihu/...）
    entity_type: str        # 实体类型（user/column/repo/...）
    action: str             # 动作（videos/following/...）
    path_template: str      # 路径模板
    required_identifiers: List[str]  # 必需标识符
    display_name: str       # 显示名称
    description: str        # 描述
    route_id: str          # 原始route_id
    confidence: float      # 推断置信度（0-1）


class RouteAnalyzer:
    """路由分析器

    从 datasource_definitions.json 中提取路由信息，
    自动推断 entity_type 和 action。
    """

    # 参数名 → 实体类型映射
    PARAMETER_TO_ENTITY_TYPE = {
        # B站
        "uid": "user",
        "mid": "user",
        "user_id": "user",

        # 知乎
        "column_id": "column",
        "id": "user",  # 需要结合平台判断

        # 微博
        # "uid": "user",  # 与B站重复，需要结合platform判断

        # GitHub
        "owner": "repo",  # 与repo配对
        "repo": "repo",

        # 通用
        "channel_id": "channel",
        "topic_id": "topic",
        "tag": "tag",
    }

    # 路径模式 → 动作映射（正则表达式）
    # 注意：顺序很重要！更具体的模式应该放在前面
    PATH_PATTERN_TO_ACTION = [
        # B站
        (r"/user/video", "videos"),
        (r"/user/dynamic", "dynamics"),
        (r"/user/coin", "coin"),
        (r"/user/like", "like"),
        (r"/user/fav", "favorites"),
        (r"/user/channel", "channel_videos"),
        (r"/user/collection", "collection"),
        (r"/user/bangumi", "bangumi"),
        (r"/user/followings", "followings_list"),
        (r"/followings/video", "following_videos"),
        (r"/followings/dynamic", "following_dynamics"),
        (r"/followings/article", "following_articles"),
        (r"/favorites", "favorites"),

        # 知乎
        (r"/zhuanlan", "articles"),
        (r"/people/activities", "activities"),
        (r"/people/answers", "answers"),
        (r"/people/pins", "pins"),

        # 微博
        (r"/user", "posts"),

        # GitHub
        (r"/commits", "commits"),
        (r"/issue", "issues"),
        (r"/pull", "pull_requests"),
        (r"/release", "releases"),
        (r"/stars", "stars"),
        (r"/file", "file"),
    ]

    # name关键词 → 动作映射
    NAME_TO_ACTION = {
        "投稿": "videos",
        "视频": "videos",
        "关注列表": "followings_list",
        "关注视频": "following_videos",
        "关注动态": "following_dynamics",
        "关注专栏": "following_articles",
        "收藏": "favorites",
        "动态": "dynamics",
        "文章": "articles",
        "专栏": "articles",
        "提交": "commits",
        "Issue": "issues",
        "Pull Request": "pull_requests",
        "版本": "releases",
        "点赞": "like",
        "投币": "coin",
        "追番": "bangumi",
        "频道": "channel_videos",
        "合集": "collection",
    }

    def __init__(self, datasource_file: str = "route_process/datasource_definitions.json"):
        self.datasource_file = Path(datasource_file)
        if not self.datasource_file.exists():
            raise FileNotFoundError(f"数据源定义文件不存在: {self.datasource_file}")

        self.routes_data = self._load_datasource_definitions()

    def _load_datasource_definitions(self) -> List[Dict]:
        """加载数据源定义"""
        print(f"正在加载数据源定义: {self.datasource_file}")
        with open(self.datasource_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[OK] 加载完成，共 {len(data)} 个平台")
        return data

    def analyze_route(
        self,
        platform: str,
        route: Dict
    ) -> Optional[AnalyzedRoute]:
        """分析单个路由

        Args:
            platform: 平台标识（如"bilibili"）
            route: 路由定义字典

        Returns:
            分析后的路由信息，如果无法推断则返回None
        """
        route_id = route.get("route_id", "")
        path_templates = route.get("path_template", [""])
        path_template = path_templates[0] if path_templates else ""
        name = route.get("name", "")
        description = route.get("description", "")
        parameters = route.get("parameters", [])

        # 1. 推断 entity_type
        entity_type = self._infer_entity_type(parameters, platform, path_template)
        if not entity_type:
            return None  # 无法推断实体类型

        # 2. 推断 action
        action = self._infer_action(path_template, name)
        if not action:
            return None  # 无法推断动作

        # 3. 提取必需标识符
        required_identifiers = [
            p["name"] for p in parameters if p.get("required", False)
        ]

        # 4. 计算置信度
        confidence = self._calculate_confidence(
            entity_type, action, path_template, name, parameters
        )

        return AnalyzedRoute(
            platform=platform,
            entity_type=entity_type,
            action=action,
            path_template=path_template,
            required_identifiers=required_identifiers,
            display_name=name,
            description=description,
            route_id=route_id,
            confidence=confidence
        )

    def _infer_entity_type(
        self,
        parameters: List[Dict],
        platform: str,
        path_template: str
    ) -> Optional[str]:
        """从参数推断实体类型"""
        # GitHub特殊处理：owner+repo → repo
        param_names = {p.get("name") for p in parameters}
        if "owner" in param_names and "repo" in param_names:
            return "repo"

        # 遍历参数，按优先级匹配
        for param in parameters:
            param_name = param.get("name")
            if not param_name:
                continue

            # 平台特定处理
            if platform == "bilibili" and param_name in ["uid", "mid"]:
                return "user"
            elif platform == "zhihu":
                if param_name == "column_id":
                    return "column"
                elif param_name == "id" and "/people/" in path_template:
                    return "user"
            elif platform == "weibo" and param_name == "uid":
                return "user"

            # 通用映射
            if param_name in self.PARAMETER_TO_ENTITY_TYPE:
                entity_type = self.PARAMETER_TO_ENTITY_TYPE[param_name]
                # 如果是通用的id，需要结合路径判断
                if entity_type == "user" and param_name == "id":
                    continue
                return entity_type

        return None

    def _infer_action(
        self,
        path_template: str,
        name: str
    ) -> Optional[str]:
        """从路径模板和名称推断动作"""
        # 1. 先尝试路径模式匹配（优先级高）
        for pattern, action in self.PATH_PATTERN_TO_ACTION:
            if re.search(pattern, path_template, re.IGNORECASE):
                return action

        # 2. 如果路径匹配失败，尝试从name提取关键词
        for keyword, action in self.NAME_TO_ACTION.items():
            if keyword in name:
                return action

        return None

    def _calculate_confidence(
        self,
        entity_type: str,
        action: str,
        path_template: str,
        name: str,
        parameters: List[Dict]
    ) -> float:
        """计算推断置信度

        置信度计算规则：
        - 路径匹配 + 参数匹配 + name匹配 = 1.0
        - 路径匹配 + 参数匹配 = 0.9
        - 路径匹配 或 参数匹配 = 0.8
        - 仅name匹配 = 0.5
        """
        confidence = 0.0

        # 检查路径是否匹配
        path_matched = any(
            re.search(pattern, path_template, re.IGNORECASE)
            for pattern, _ in self.PATH_PATTERN_TO_ACTION
        )

        # 检查参数是否匹配
        param_names = {p.get("name") for p in parameters}
        param_matched = any(
            param in self.PARAMETER_TO_ENTITY_TYPE
            for param in param_names
        )

        # 检查name是否匹配
        name_matched = any(
            keyword in name
            for keyword in self.NAME_TO_ACTION.keys()
        )

        # 计算置信度
        if path_matched and param_matched and name_matched:
            confidence = 1.0
        elif path_matched and param_matched:
            confidence = 0.9
        elif path_matched or param_matched:
            confidence = 0.8
        elif name_matched:
            confidence = 0.5
        else:
            confidence = 0.3  # 基础置信度

        return confidence

    def analyze_all_routes(
        self,
        min_confidence: float = 0.5,
        platforms_filter: Optional[List[str]] = None
    ) -> List[AnalyzedRoute]:
        """分析所有路由

        Args:
            min_confidence: 最小置信度阈值（默认0.5）
            platforms_filter: 平台过滤列表（None表示全部平台）

        Returns:
            分析后的路由列表
        """
        analyzed_routes = []
        total_routes = 0
        skipped_low_confidence = 0
        skipped_no_inference = 0

        print(f"\n开始分析路由（最小置信度: {min_confidence}）...")

        for provider in self.routes_data:
            platform = provider.get("provider_id")

            # 平台过滤
            if platforms_filter and platform not in platforms_filter:
                continue

            routes = provider.get("routes", [])
            total_routes += len(routes)

            for route in routes:
                analyzed = self.analyze_route(platform, route)

                if not analyzed:
                    skipped_no_inference += 1
                    continue

                if analyzed.confidence < min_confidence:
                    skipped_low_confidence += 1
                    continue

                analyzed_routes.append(analyzed)

        print(f"\n分析统计：")
        print(f"  总路由数: {total_routes}")
        print(f"  成功推断: {len(analyzed_routes)}")
        print(f"  无法推断: {skipped_no_inference}")
        print(f"  低置信度: {skipped_low_confidence}")
        print(f"  推断成功率: {len(analyzed_routes) / total_routes * 100:.1f}%")

        return analyzed_routes

    def generate_action_registry_config(
        self,
        output_file: str = "services/subscription/action_registry_config.json",
        min_confidence: float = 0.5,
        platforms_filter: Optional[List[str]] = None
    ) -> str:
        """生成 ActionRegistry 配置文件

        自动分析所有路由并生成配置JSON。

        Args:
            output_file: 输出文件路径
            min_confidence: 最小置信度阈值
            platforms_filter: 平台过滤列表

        Returns:
            输出文件路径
        """
        analyzed_routes = self.analyze_all_routes(
            min_confidence=min_confidence,
            platforms_filter=platforms_filter
        )

        # 按 (platform, entity_type, action) 分组去重
        registry_config = {}

        for route in analyzed_routes:
            key = f"{route.platform}:{route.entity_type}:{route.action}"

            # 如果已存在，选择置信度更高的
            if key in registry_config:
                if route.confidence > registry_config[key]["confidence"]:
                    registry_config[key] = asdict(route)
            else:
                registry_config[key] = asdict(route)

        # 转换为列表并排序
        config_list = sorted(
            registry_config.values(),
            key=lambda x: (x["platform"], x["entity_type"], x["action"])
        )

        # 保存到文件
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config_list, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 生成 ActionRegistry 配置: {output_path}")
        print(f"   共 {len(config_list)} 个 action 定义")
        print(f"   平均置信度: {sum(r['confidence'] for r in config_list) / len(config_list):.2f}")

        # 统计各平台action数量
        platform_stats = {}
        for item in config_list:
            platform = item["platform"]
            platform_stats[platform] = platform_stats.get(platform, 0) + 1

        print(f"\n平台统计（前10）：")
        for platform, count in sorted(
            platform_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]:
            print(f"  {platform}: {count} actions")

        return str(output_path)

    def print_low_confidence_routes(
        self,
        min_confidence: float = 0.5,
        max_confidence: float = 0.8,
        limit: int = 20
    ):
        """打印低置信度路由（需要人工审核）

        Args:
            min_confidence: 最小置信度
            max_confidence: 最大置信度
            limit: 最多打印数量
        """
        analyzed_routes = self.analyze_all_routes(min_confidence=min_confidence)

        low_confidence_routes = [
            r for r in analyzed_routes
            if r.confidence <= max_confidence
        ]

        low_confidence_routes.sort(key=lambda x: x.confidence)

        print(f"\n需要人工审核的路由（置信度 {min_confidence}-{max_confidence}）：")
        print(f"共 {len(low_confidence_routes)} 个")
        print("\n" + "=" * 100)

        for i, route in enumerate(low_confidence_routes[:limit], 1):
            print(f"\n{i}. [{route.confidence:.2f}] {route.platform} - {route.display_name}")
            print(f"   route_id: {route.route_id}")
            print(f"   path: {route.path_template}")
            print(f"   推断: entity_type={route.entity_type}, action={route.action}")
            print(f"   identifiers: {route.required_identifiers}")

        if len(low_confidence_routes) > limit:
            print(f"\n... 还有 {len(low_confidence_routes) - limit} 个路由未显示")
