"""数据库服务模块

负责订阅系统的数据持久化，包括数据模型、连接管理和服务层。

模块结构：
- models.py - 数据模型（Subscription + SubscriptionEmbedding）
- connection.py - 数据库连接管理（单例模式）
- subscription_service.py - 订阅管理服务（CRUD + ID映射）
"""

from .models import Subscription, SubscriptionEmbedding
from .connection import DatabaseConnection, get_db_connection
from .subscription_service import SubscriptionService

__all__ = [
    "Subscription",
    "SubscriptionEmbedding",
    "DatabaseConnection",
    "get_db_connection",
    "SubscriptionService",
]
