from __future__ import annotations

"""fetch_private_data 工具实现：私有数据获取（框架预留）。

V5.0 Phase 3 (P1) 工具 - 当前为简化实现，返回未授权错误。
完整的 OAuth 集成和 Token 管理将在后续版本实现。
"""

import logging
from typing import Any, Dict, List, Literal

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


# 支持的平台
SUPPORTED_PLATFORMS = [
    "bilibili", "xiaohongshu", "youtube", "github", "yuque", "weread", "jike"
]

# 支持的数据类型
SUPPORTED_DATA_TYPES = [
    "favorites", "history", "starred", "watching", "subscriptions", "likes", "collections"
]

# 平台 + 数据类型的映射示例
PLATFORM_DATA_TYPE_MAPPING = {
    ("bilibili", "favorites"): "B站收藏夹",
    ("bilibili", "history"): "B站观看历史",
    ("github", "starred"): "GitHub Starred 仓库",
    ("github", "watching"): "GitHub 关注的仓库",
    ("yuque", "watching"): "语雀关注的知识库",
    ("weread", "collections"): "微信读书收藏",
    ("xiaohongshu", "favorites"): "小红书收藏",
    ("xiaohongshu", "likes"): "小红书点赞",
}


def register_private_data_tool(registry: ToolRegistry) -> None:
    """向注册表注册 fetch_private_data 工具。"""

    @tool(
        registry,
        plugin_id="fetch_private_data",
        description="获取用户的私有数据（收藏、历史、关注等）",
        execution_mode="full",  # 需要授权检查和数据持久化
        schema={
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "平台名称（必填）",
                    "enum": SUPPORTED_PLATFORMS
                },
                "data_type": {
                    "type": "string",
                    "description": "数据类型（必填）",
                    "enum": SUPPORTED_DATA_TYPES
                },
                "params": {
                    "type": "object",
                    "description": "额外参数（可选）",
                    "properties": {
                        "folder_id": {
                            "type": "string",
                            "description": "收藏夹 ID（如 B站收藏夹）"
                        },
                        "time_range": {
                            "type": "string",
                            "description": "时间范围（如 '7d', '30d'）"
                        },
                        "category": {
                            "type": "string",
                            "description": "分类过滤"
                        }
                    }
                },
                "limit": {
                    "type": "number",
                    "description": "返回数量限制",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20
                },
                "offset": {
                    "type": "number",
                    "description": "偏移量（分页）",
                    "minimum": 0,
                    "default": 0
                }
            },
            "required": ["platform", "data_type"]
        }
    )
    def fetch_private_data(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        """
        获取用户的私有数据。

        当前实现：返回 E201 未授权错误，引导用户进行 OAuth 授权。
        未来版本将实现完整的授权流程和数据获取。

        支持平台：bilibili, xiaohongshu, youtube, github, yuque, weread, jike
        支持类型：favorites, history, starred, watching, subscriptions, likes, collections
        """
        # 1. 参数验证
        platform = call.args.get("platform")
        if not platform:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "private_data",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 platform"
            )

        data_type = call.args.get("data_type")
        if not data_type:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "private_data",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 data_type"
            )

        # 2. 验证平台和数据类型组合
        if (platform, data_type) not in PLATFORM_DATA_TYPE_MAPPING:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "private_data",
                    "error_code": "E102"
                },
                status="error",
                error_message=f"不支持的组合：{platform} + {data_type}"
            )

        data_source_name = PLATFORM_DATA_TYPE_MAPPING[(platform, data_type)]

        # 3. 检查用户授权
        # 优先检查 context.extras 中的 platform_tokens
        platform_tokens = context.extras.get("platform_tokens", {})
        user_id = context.extras.get("user_id")

        # 检查是否有对应平台的 token
        has_token = platform in platform_tokens and platform_tokens[platform]

        # 4. 如果已授权，返回模拟数据（Phase 3 简化实现）
        if has_token:
            logger.info(
                f"fetch_private_data: 用户已授权访问 {data_source_name}，返回模拟数据"
            )

            # 生成模拟私有数据
            mock_items = _generate_mock_private_data(
                platform, data_type, call.args.get("limit", 20)
            )

            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "private_data",
                    "platform": platform,
                    "data_type": data_type,
                    "data_source_name": data_source_name,
                    "user_id": user_id,
                    "items": mock_items,
                    "total_count": len(mock_items),
                    "is_mock": True,  # 标记为模拟数据
                    "note": "Phase 3 简化实现：返回模拟数据，完整 API 集成待 Phase 6 实现"
                },
                status="success"
            )

        # 5. 未授权，返回 E201 错误并引导授权
        logger.info(
            f"fetch_private_data: 请求访问 {data_source_name}，但用户未授权"
        )

        # 生成授权引导消息
        auth_url = _generate_mock_auth_url(platform)
        required_scopes = _get_required_scopes(platform, data_type)

        return ToolExecutionPayload(
            call=call,
            raw_output={
                "type": "private_data",
                "error_code": "E201",
                "auth_required": True,
                "auth_url": auth_url,
                "scopes_needed": required_scopes,
                "platform": platform,
                "data_type": data_type,
                "data_source_name": data_source_name,
                "user_friendly_message": (
                    f"需要授权才能访问：{data_source_name}\n\n"
                    f"请点击下方链接完成 OAuth 授权：\n{auth_url}\n\n"
                    f"需要的权限：{', '.join(required_scopes)}\n\n"
                    f"注意：当前为 Phase 3 预览版，完整 OAuth 流程将在 Phase 6 实现。"
                )
            },
            status="error",
            error_message=f"[E201] 未授权访问 {platform}，请先完成 OAuth 授权"
        )


def _generate_mock_auth_url(platform: str) -> str:
    """生成模拟的授权 URL（占位符）。"""
    # 未来实现：真实的 OAuth 授权 URL
    return f"https://example.com/oauth/{platform}?redirect_uri=app://callback"


def _get_required_scopes(platform: str, data_type: str) -> List[str]:
    """获取所需的权限范围。"""
    # 根据平台和数据类型返回所需权限
    scope_mapping = {
        ("bilibili", "favorites"): ["user:favorites:read"],
        ("bilibili", "history"): ["user:history:read"],
        ("github", "starred"): ["user:read", "repo:read"],
        ("github", "watching"): ["user:read", "repo:read"],
        ("yuque", "watching"): ["user:read", "repo:read"],
        ("weread", "collections"): ["user:read", "shelf:read"],
        ("xiaohongshu", "favorites"): ["user:read", "favorites:read"],
        ("xiaohongshu", "likes"): ["user:read", "likes:read"],
    }

    return scope_mapping.get((platform, data_type), ["user:read"])


def _generate_mock_private_data(platform: str, data_type: str, limit: int) -> List[Dict]:
    """
    生成模拟的私有数据（Phase 3 简化实现）。

    Phase 6 将替换为真实的 API 调用。
    """
    # 模拟数据模板
    templates = {
        ("bilibili", "favorites"): lambda i: {
            "id": f"mock_fav_{i}",
            "title": f"我收藏的视频 {i}",
            "author": f"UP主_{i}",
            "bvid": f"BV{1000000 + i}",
            "view_count": 10000 + i * 1000,
            "collected_at": "2025-01-15T10:00:00Z",
            "url": f"https://www.bilibili.com/video/BV{1000000 + i}"
        },
        ("github", "starred"): lambda i: {
            "id": f"mock_star_{i}",
            "name": f"awesome-project-{i}",
            "full_name": f"user/awesome-project-{i}",
            "description": f"An awesome project about topic {i}",
            "stars": 1000 + i * 100,
            "language": "Python",
            "starred_at": "2025-01-15T10:00:00Z",
            "url": f"https://github.com/user/awesome-project-{i}"
        },
        ("xiaohongshu", "favorites"): lambda i: {
            "id": f"mock_xhs_fav_{i}",
            "title": f"我收藏的笔记 {i}",
            "author": f"博主_{i}",
            "likes": 500 + i * 50,
            "collected_at": "2025-01-15T10:00:00Z",
            "url": f"https://www.xiaohongshu.com/note/{1000000 + i}"
        },
    }

    # 获取对应的模板
    template = templates.get((platform, data_type))
    if not template:
        # 通用模板
        template = lambda i: {
            "id": f"mock_{platform}_{data_type}_{i}",
            "title": f"{PLATFORM_DATA_TYPE_MAPPING.get((platform, data_type), '数据')} {i}",
            "created_at": "2025-01-15T10:00:00Z"
        }

    # 生成指定数量的模拟数据
    return [template(i) for i in range(1, min(limit, 20) + 1)]
