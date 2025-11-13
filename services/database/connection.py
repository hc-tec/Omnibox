"""数据库连接管理

单例模式，全局唯一数据库连接实例。

设计原则：
- 单例模式：确保全局只有一个数据库连接实例
- 延迟初始化：首次调用时才创建连接
- 线程安全：使用 SQLModel Session 机制
- 测试友好：提供 reset() 方法用于测试环境重置
"""

from sqlmodel import SQLModel, Session, create_engine
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """数据库连接管理（单例模式）

    使用示例：
    ```python
    # 方式1：获取全局单例
    db = get_db_connection()

    # 方式2：使用上下文管理器
    with db.get_session() as session:
        subscription = session.get(Subscription, 1)

    # 方式3：测试时重置
    DatabaseConnection.reset()
    ```
    """

    _instance: Optional['DatabaseConnection'] = None
    _engine = None

    def __new__(cls):
        """单例模式：全局唯一实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化数据库连接（只执行一次）"""
        if self._engine is not None:
            return

        # 优先使用测试环境的 DATABASE_URL（支持测试环境自定义）
        test_db_url = os.getenv("DATABASE_URL")
        if test_db_url:
            # 测试环境：直接使用环境变量
            if test_db_url.startswith("sqlite:///"):
                database_url = test_db_url
            else:
                database_url = f"sqlite:///{test_db_url}"
            logger.info(f"初始化测试数据库连接: {database_url}")
        else:
            # 生产环境：使用统一配置
            from services.config import get_database_config
            db_config = get_database_config()
            database_url = db_config.get_database_url()
            logger.info(f"初始化生产数据库连接: {database_url}")

        # 创建引擎
        # echo=False: 不输出 SQL 日志（生产环境）
        # check_same_thread=False: 允许多线程访问（SQLite 特有）
        self._engine = create_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False}
        )

    @property
    def engine(self):
        """获取数据库引擎"""
        return self._engine

    def create_tables(self):
        """创建所有表（开发环境用，生产环境用 Alembic）

        注意：这个方法仅用于开发环境快速创建表。
        生产环境应该使用 Alembic 进行版本控制的迁移。
        """
        from .models import Subscription, SubscriptionEmbedding

        logger.info("创建数据库表...")
        SQLModel.metadata.create_all(self._engine)
        logger.info("✅ 数据库表创建完成")

    def get_session(self) -> Session:
        """获取数据库会话

        返回的 Session 应该使用上下文管理器：
        ```python
        with db.get_session() as session:
            # 数据库操作
            subscription = session.get(Subscription, 1)
        ```
        """
        return Session(self._engine)

    @classmethod
    def reset(cls):
        """重置单例实例（仅用于测试）

        测试用例应该在 teardown 时调用此方法重置数据库连接。
        """
        if cls._instance:
            if cls._instance._engine:
                cls._instance._engine.dispose()
            cls._instance = None
            cls._engine = None
            logger.debug("数据库连接已重置")


# 全局单例获取函数
def get_db_connection() -> DatabaseConnection:
    """获取全局数据库连接单例

    推荐使用此函数而非直接实例化 DatabaseConnection。

    示例：
    ```python
    from services.database import get_db_connection

    db = get_db_connection()
    with db.get_session() as session:
        subscriptions = list(session.exec(select(Subscription)).all())
    ```
    """
    return DatabaseConnection()
