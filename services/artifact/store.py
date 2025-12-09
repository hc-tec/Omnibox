"""
数据产物存储层

设计原则：
1. 复用 ResearchDataStore 作为原始数据存储
2. 使用 SQLite 持久化元数据（ArtifactRecord 表）
3. 全局单例模式，线程安全
4. 支持导出为 JSON/CSV

存储架构：
┌──────────────────────────────────────────────────────────────┐
│                      ArtifactStore                           │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │  SQLite (元数据)     │    │  ResearchDataStore (原始)   │ │
│  │  - artifact_id      │    │  - data_id → payload       │ │
│  │  - name, type       │    │  - LRU + TTL               │ │
│  │  - source, views    │    │  - InMemory (开发)          │ │
│  │  - tags, relations  │    │  - Redis (生产，可选)        │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
"""

import json
import csv
import io
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Session, select

from langgraph_agents.storage import ResearchDataStore, InMemoryResearchDataStore
from services.database.connection import get_db_connection
from .models import DataArtifact, ArtifactType, ArtifactSource, ViewSpec

logger = logging.getLogger(__name__)


class ArtifactRecord(SQLModel, table=True):
    """
    数据产物元数据持久化表

    存储 DataArtifact 的所有元数据，原始数据存储在 ResearchDataStore 中。
    """
    __tablename__ = "artifact_records"

    id: Optional[int] = Field(default=None, primary_key=True)

    # 产物标识
    artifact_id: str = Field(index=True, unique=True, description="产物唯一标识")
    data_id: Optional[str] = Field(default=None, description="原始数据存储 ID")

    # 基本信息
    name: str = Field(description="产物名称（自动生成）")
    description: str = Field(default="", description="产物描述")
    artifact_type: str = Field(description="产物类型: dataset/analysis/insight/document")

    # 来源信息
    workflow_id: Optional[str] = Field(default=None, index=True, description="所属工作流 ID")
    step_id: int = Field(description="步骤编号")
    tool_name: str = Field(description="生成工具")

    # LangGraph 兼容字段
    summary: str = Field(description="数据摘要（用于 LLM 推理）")
    status: str = Field(default="success", description="执行状态")
    error_message: Optional[str] = Field(default=None, description="错误信息")

    # 元数据（JSON 序列化）
    schema_info_json: Optional[str] = Field(default=None, description="Schema 信息 JSON")
    statistics_json: Optional[str] = Field(default=None, description="统计信息 JSON")
    sample_items_json: Optional[str] = Field(default=None, description="样本数据 JSON")
    quality_score: Optional[float] = Field(default=None, description="质量评分")

    # 可视化建议（JSON 序列化）
    suggested_views_json: str = Field(default="[]", description="可视化建议 JSON")

    # 引用关系（JSON 序列化）
    derived_from_json: str = Field(default="[]", description="来源引用 JSON")
    used_by_json: str = Field(default="[]", description="被引用 JSON")

    # 标签
    tags_json: str = Field(default="[]", description="标签 JSON")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def to_artifact(self) -> DataArtifact:
        """转换为 DataArtifact 对象"""
        return DataArtifact(
            artifact_id=self.artifact_id,
            data_id=self.data_id,
            name=self.name,
            description=self.description,
            artifact_type=ArtifactType(self.artifact_type),
            step_id=self.step_id,
            tool_name=self.tool_name,
            summary=self.summary,
            status=self.status,
            error_message=self.error_message,
            schema_info=json.loads(self.schema_info_json) if self.schema_info_json else None,
            statistics=json.loads(self.statistics_json) if self.statistics_json else None,
            sample_items=json.loads(self.sample_items_json) if self.sample_items_json else None,
            quality_score=self.quality_score,
            source=ArtifactSource(
                workflow_id=self.workflow_id,
                step_id=self.step_id,
                tool_name=self.tool_name,
                created_at=self.created_at,
            ),
            suggested_views=[ViewSpec(**v) for v in json.loads(self.suggested_views_json)],
            derived_from=json.loads(self.derived_from_json),
            used_by=json.loads(self.used_by_json),
            tags=json.loads(self.tags_json),
        )

    @classmethod
    def from_artifact(cls, artifact: DataArtifact) -> "ArtifactRecord":
        """从 DataArtifact 对象创建记录"""
        return cls(
            artifact_id=artifact.artifact_id,
            data_id=artifact.data_id,
            name=artifact.name,
            description=artifact.description,
            artifact_type=artifact.artifact_type.value,
            workflow_id=artifact.source.workflow_id if artifact.source else None,
            step_id=artifact.step_id,
            tool_name=artifact.tool_name,
            summary=artifact.summary,
            status=artifact.status,
            error_message=artifact.error_message,
            schema_info_json=json.dumps(artifact.schema_info) if artifact.schema_info else None,
            statistics_json=json.dumps(artifact.statistics) if artifact.statistics else None,
            sample_items_json=json.dumps(artifact.sample_items) if artifact.sample_items else None,
            quality_score=artifact.quality_score,
            suggested_views_json=json.dumps([v.model_dump() for v in artifact.suggested_views]),
            derived_from_json=json.dumps([r.model_dump() if hasattr(r, 'model_dump') else r for r in artifact.derived_from]),
            used_by_json=json.dumps([r.model_dump() if hasattr(r, 'model_dump') else r for r in artifact.used_by]),
            tags_json=json.dumps(artifact.tags),
        )


class ArtifactStore:
    """
    数据产物存储管理器

    职责：
    1. 管理数据产物的完整生命周期
    2. 持久化元数据到 SQLite
    3. 委托原始数据存储给 ResearchDataStore
    4. 提供查询和导出能力
    """

    def __init__(self, data_store: Optional[ResearchDataStore] = None):
        """
        初始化存储管理器

        Args:
            data_store: 原始数据存储，默认使用 InMemoryResearchDataStore
        """
        self._data_store = data_store or InMemoryResearchDataStore(
            max_items=1000,
            ttl_seconds=3600 * 24  # 24 小时
        )
        self._db = get_db_connection()
        self._ensure_tables()

    def _ensure_tables(self):
        """确保数据库表存在"""
        try:
            SQLModel.metadata.create_all(self._db.engine)
            logger.debug("ArtifactRecord 表已就绪")
        except Exception as e:
            logger.warning(f"创建 ArtifactRecord 表时出错: {e}")

    # ========== 原始数据操作（委托给 ResearchDataStore）==========

    def save_data(self, payload: Any) -> str:
        """
        保存原始数据，返回 data_id

        这是底层存储操作，通常通过 save_artifact 间接调用
        """
        return self._data_store.save(payload)

    def load_data(self, data_id: str) -> Optional[Any]:
        """
        加载原始数据

        注意：此方法仅供前端展示或工具处理时使用，
        禁止在 Agent 节点中调用（参见 CLAUDE.md 铁律）
        """
        return self._data_store.load(data_id)

    # ========== 产物元数据操作（SQLite 持久化）==========

    def save_artifact(
        self,
        artifact: DataArtifact,
        payload: Optional[Any] = None,
    ) -> str:
        """
        保存数据产物

        Args:
            artifact: 数据产物对象
            payload: 原始数据（如果提供，会保存到 data_store）

        Returns:
            artifact_id
        """
        # 如果提供了原始数据，先保存
        if payload is not None:
            data_id = self._data_store.save(payload)
            artifact.data_id = data_id

        # 保存元数据到 SQLite
        record = ArtifactRecord.from_artifact(artifact)
        with self._db.get_session() as session:
            # 检查是否已存在
            existing = session.exec(
                select(ArtifactRecord).where(ArtifactRecord.artifact_id == artifact.artifact_id)
            ).first()

            if existing:
                # 更新现有记录
                for key, value in record.model_dump(exclude={"id"}).items():
                    setattr(existing, key, value)
                existing.updated_at = datetime.now()
                session.add(existing)
            else:
                # 创建新记录
                session.add(record)

            session.commit()
            logger.debug(f"已保存产物: {artifact.artifact_id}")

        return artifact.artifact_id

    def load_artifact(self, artifact_id: str) -> Optional[DataArtifact]:
        """
        加载数据产物元数据

        Args:
            artifact_id: 产物唯一标识

        Returns:
            DataArtifact 对象，不存在返回 None
        """
        with self._db.get_session() as session:
            record = session.exec(
                select(ArtifactRecord).where(ArtifactRecord.artifact_id == artifact_id)
            ).first()

            if not record:
                return None

            return record.to_artifact()

    def list_artifacts(
        self,
        workflow_id: Optional[str] = None,
        artifact_type: Optional[ArtifactType] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DataArtifact]:
        """
        查询产物列表

        Args:
            workflow_id: 按工作流筛选
            artifact_type: 按类型筛选
            tags: 按标签筛选（任意匹配）
            limit: 返回数量限制
            offset: 分页偏移

        Returns:
            DataArtifact 列表
        """
        with self._db.get_session() as session:
            query = select(ArtifactRecord)

            if workflow_id:
                query = query.where(ArtifactRecord.workflow_id == workflow_id)
            if artifact_type:
                query = query.where(ArtifactRecord.artifact_type == artifact_type.value)

            # 按创建时间倒序
            query = query.order_by(ArtifactRecord.created_at.desc())
            query = query.offset(offset).limit(limit)

            records = session.exec(query).all()
            artifacts = [r.to_artifact() for r in records]

            # 标签筛选（JSON 字段，需要后处理）
            if tags:
                artifacts = [
                    a for a in artifacts
                    if set(tags) & set(a.tags)
                ]

            return artifacts

    def delete_artifact(self, artifact_id: str) -> bool:
        """
        删除数据产物

        Args:
            artifact_id: 产物唯一标识

        Returns:
            是否删除成功
        """
        with self._db.get_session() as session:
            record = session.exec(
                select(ArtifactRecord).where(ArtifactRecord.artifact_id == artifact_id)
            ).first()

            if not record:
                return False

            session.delete(record)
            session.commit()
            logger.debug(f"已删除产物: {artifact_id}")
            return True

    # ========== 导出能力 ==========

    def export_to_json(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """
        导出产物为 JSON

        Returns:
            包含 metadata 和 data 的字典
        """
        artifact = self.load_artifact(artifact_id)
        if not artifact:
            return None

        data = self.load_data(artifact.data_id) if artifact.data_id else None
        return {
            "metadata": artifact.model_dump(),
            "data": data,
        }

    def export_to_csv(self, artifact_id: str) -> Optional[str]:
        """
        导出产物为 CSV（仅支持表格型数据）

        Returns:
            CSV 字符串，不支持的数据类型返回 None
        """
        artifact = self.load_artifact(artifact_id)
        if not artifact or not artifact.data_id:
            return None

        data = self.load_data(artifact.data_id)
        if not isinstance(data, list) or not data:
            return None

        # 检查是否是字典列表
        if not isinstance(data[0], dict):
            return None

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    # ========== 统计信息 ==========

    def stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        with self._db.get_session() as session:
            total = session.exec(select(ArtifactRecord)).all()
            by_type = {}
            for record in total:
                by_type[record.artifact_type] = by_type.get(record.artifact_type, 0) + 1

        return {
            "total_artifacts": len(total),
            "by_type": by_type,
            "data_store": self._data_store.stats(),
        }


# ========== 全局单例 ==========

_artifact_store: Optional[ArtifactStore] = None


def get_artifact_store() -> ArtifactStore:
    """获取全局 ArtifactStore 单例"""
    global _artifact_store
    if _artifact_store is None:
        _artifact_store = ArtifactStore()
    return _artifact_store


def reset_artifact_store():
    """重置全局单例（仅用于测试）"""
    global _artifact_store
    _artifact_store = None
