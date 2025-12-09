"""Session 存储层

职责：
1. Session CRUD
2. 状态持久化
3. 过期清理
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

from sqlmodel import Session as DBSession, select, col

from services.database.connection import DatabaseConnection, get_db_connection

from .models import Session, SessionState, SessionStatus
from .config import get_session_config

logger = logging.getLogger(__name__)


class SessionStore:
    """
    Session 存储层

    职责：
    1. Session CRUD
    2. 状态持久化
    3. 过期清理
    """

    def __init__(self, db_connection: Optional[DatabaseConnection] = None):
        self.db = db_connection or get_db_connection()
        self._ensure_tables()

    def _ensure_tables(self):
        """确保表存在"""
        from sqlmodel import SQLModel
        # 导入模型以注册到元数据
        from .models import Session  # noqa: F401
        SQLModel.metadata.create_all(self.db.engine, checkfirst=True)

    def create_session(
        self,
        workspace_id: Optional[str] = None,
        source_workflow_id: Optional[str] = None,
        name: str = ""
    ) -> Session:
        """
        创建新 Session

        Args:
            workspace_id: 关联的 Workspace ID
            source_workflow_id: 来源 Workflow ID（如果从模板创建）
            name: Session 名称

        Returns:
            Session 实例
        """
        session = Session.create(
            workspace_id=workspace_id,
            source_workflow_id=source_workflow_id,
            name=name
        )

        with self.db.get_session() as db_session:
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

        logger.info(f"SessionStore: 创建 Session {session.session_id}")
        return session

    def load_session(self, session_id: str) -> Optional[Session]:
        """
        加载 Session

        Args:
            session_id: Session ID

        Returns:
            Session 实例，不存在返回 None
        """
        with self.db.get_session() as db_session:
            statement = select(Session).where(Session.session_id == session_id)
            result = db_session.exec(statement).first()
            return result

    def save_session(self, session: Session) -> bool:
        """
        保存 Session

        Args:
            session: Session 实例

        Returns:
            是否保存成功
        """
        try:
            with self.db.get_session() as db_session:
                db_session.add(session)
                db_session.commit()
                db_session.refresh(session)
            return True
        except Exception as e:
            logger.error(f"SessionStore: 保存 Session 失败 - {e}")
            return False

    def update_state(self, session_id: str, state: SessionState) -> bool:
        """
        更新 Session 状态

        Args:
            session_id: Session ID
            state: SessionState 实例

        Returns:
            是否更新成功
        """
        with self.db.get_session() as db_session:
            statement = select(Session).where(Session.session_id == session_id)
            session = db_session.exec(statement).first()

            if not session:
                logger.warning(f"SessionStore: Session 不存在 {session_id}")
                return False

            session.set_state(state)
            db_session.add(session)
            db_session.commit()

        logger.debug(f"SessionStore: 更新状态 {session_id}")
        return True

    def close_session(self, session_id: str) -> bool:
        """
        关闭 Session

        Args:
            session_id: Session ID

        Returns:
            是否关闭成功
        """
        with self.db.get_session() as db_session:
            statement = select(Session).where(Session.session_id == session_id)
            session = db_session.exec(statement).first()

            if not session:
                return False

            session.status = SessionStatus.CLOSED.value
            session.closed_at = datetime.now()

            # 更新内部状态
            state = session.get_state()
            state.status = SessionStatus.CLOSED
            session.set_state(state)

            db_session.add(session)
            db_session.commit()

        logger.info(f"SessionStore: 关闭 Session {session_id}")
        return True

    def list_sessions(
        self,
        workspace_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
        limit: int = 100
    ) -> List[Session]:
        """
        列出 Sessions

        Args:
            workspace_id: 过滤 Workspace ID
            status: 过滤状态
            limit: 最大返回数量

        Returns:
            Session 列表
        """
        with self.db.get_session() as db_session:
            statement = select(Session)

            if workspace_id:
                statement = statement.where(Session.workspace_id == workspace_id)

            if status:
                statement = statement.where(Session.status == status.value)

            statement = statement.order_by(col(Session.last_active_at).desc()).limit(limit)

            results = db_session.exec(statement).all()
            return list(results)

    def cleanup_expired(self, older_than_minutes: Optional[int] = None) -> int:
        """
        清理过期 Sessions

        Args:
            older_than_minutes: 超过多少分钟视为过期（默认使用配置）

        Returns:
            清理的 Session 数量
        """
        config = get_session_config()
        minutes = older_than_minutes or config.timeout_minutes * 2

        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        with self.db.get_session() as db_session:
            # 查找过期的活跃 Sessions
            statement = select(Session).where(
                Session.status.in_([SessionStatus.ACTIVE.value, SessionStatus.IDLE.value]),
                Session.last_active_at < cutoff_time
            )
            expired_sessions = db_session.exec(statement).all()

            count = 0
            for session in expired_sessions:
                session.status = SessionStatus.EXPIRED.value
                session.closed_at = datetime.now()
                db_session.add(session)
                count += 1

            db_session.commit()

        if count > 0:
            logger.info(f"SessionStore: 清理 {count} 个过期 Session")

        return count

    def delete_session(self, session_id: str) -> bool:
        """
        删除 Session（物理删除）

        Args:
            session_id: Session ID

        Returns:
            是否删除成功
        """
        with self.db.get_session() as db_session:
            statement = select(Session).where(Session.session_id == session_id)
            session = db_session.exec(statement).first()

            if not session:
                return False

            db_session.delete(session)
            db_session.commit()

        logger.info(f"SessionStore: 删除 Session {session_id}")
        return True


# 全局单例
_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """获取 SessionStore 单例"""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def reset_session_store():
    """重置存储（测试用）"""
    global _store
    _store = None
