"""
ArtifactStore 存储层测试
"""

import os
import pytest
import tempfile

from services.artifact.models import DataArtifact, ArtifactType, ViewSpec, ViewType
from services.artifact.store import (
    ArtifactStore,
    ArtifactRecord,
    reset_artifact_store,
)
from langgraph_agents.storage import InMemoryResearchDataStore


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # 设置环境变量指向临时数据库
    old_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_path

    yield db_path

    # 清理
    os.environ.pop("DATABASE_URL", None)
    if old_env:
        os.environ["DATABASE_URL"] = old_env
    reset_artifact_store()

    # 删除临时文件
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def artifact_store(temp_db):
    """创建测试用的 ArtifactStore"""
    from services.database.connection import DatabaseConnection
    DatabaseConnection.reset()  # 重置连接以使用新的数据库

    data_store = InMemoryResearchDataStore(max_items=100, ttl_seconds=3600)
    store = ArtifactStore(data_store)
    return store


class TestArtifactStore:
    """ArtifactStore 测试"""

    def test_save_and_load_artifact(self, artifact_store):
        """测试保存和加载产物"""
        artifact = DataArtifact(
            step_id=1,
            tool_name="fetch_public_data",
            data_id="lg-test123",
            summary="测试数据",
            status="success",
            artifact_type=ArtifactType.DATASET,
            name="测试产物",
            tags=["test", "demo"],
        )

        # 保存
        artifact_id = artifact_store.save_artifact(artifact)
        assert artifact_id == artifact.artifact_id

        # 加载
        loaded = artifact_store.load_artifact(artifact_id)
        assert loaded is not None
        assert loaded.name == "测试产物"
        assert loaded.artifact_type == ArtifactType.DATASET
        assert loaded.tags == ["test", "demo"]

    def test_save_artifact_with_payload(self, artifact_store):
        """测试保存带原始数据的产物"""
        artifact = DataArtifact(
            step_id=1,
            tool_name="fetch_public_data",
            summary="测试数据",
            status="success",
        )

        payload = [{"title": "test1"}, {"title": "test2"}]

        # 保存（同时保存原始数据）
        artifact_id = artifact_store.save_artifact(artifact, payload=payload)

        # 验证 data_id 被设置
        loaded = artifact_store.load_artifact(artifact_id)
        assert loaded.data_id is not None

        # 验证原始数据可以加载
        data = artifact_store.load_data(loaded.data_id)
        assert data == payload

    def test_list_artifacts_by_workflow(self, artifact_store):
        """测试按工作流查询产物"""
        # 创建多个产物
        for i in range(3):
            artifact = DataArtifact(
                step_id=i,
                tool_name="fetch_public_data",
                summary=f"数据 {i}",
                status="success",
            )
            artifact.source.workflow_id = "wf-test"
            artifact_store.save_artifact(artifact)

        # 创建另一个工作流的产物
        other = DataArtifact(
            step_id=0,
            tool_name="fetch_public_data",
            summary="其他工作流",
            status="success",
        )
        other.source.workflow_id = "wf-other"
        artifact_store.save_artifact(other)

        # 查询
        results = artifact_store.list_artifacts(workflow_id="wf-test")
        assert len(results) == 3

    def test_list_artifacts_by_type(self, artifact_store):
        """测试按类型查询产物"""
        # 创建不同类型的产物
        dataset = DataArtifact(
            step_id=1,
            tool_name="fetch_public_data",
            summary="数据集",
            status="success",
            artifact_type=ArtifactType.DATASET,
        )
        artifact_store.save_artifact(dataset)

        analysis = DataArtifact(
            step_id=2,
            tool_name="data_operator",
            summary="分析结果",
            status="success",
            artifact_type=ArtifactType.ANALYSIS,
        )
        artifact_store.save_artifact(analysis)

        # 查询
        datasets = artifact_store.list_artifacts(artifact_type=ArtifactType.DATASET)
        analyses = artifact_store.list_artifacts(artifact_type=ArtifactType.ANALYSIS)

        assert len(datasets) == 1
        assert len(analyses) == 1
        assert datasets[0].artifact_type == ArtifactType.DATASET

    def test_delete_artifact(self, artifact_store):
        """测试删除产物"""
        artifact = DataArtifact(
            step_id=1,
            tool_name="fetch_public_data",
            summary="待删除",
            status="success",
        )
        artifact_id = artifact_store.save_artifact(artifact)

        # 删除
        result = artifact_store.delete_artifact(artifact_id)
        assert result is True

        # 验证已删除
        loaded = artifact_store.load_artifact(artifact_id)
        assert loaded is None

    def test_delete_nonexistent_artifact(self, artifact_store):
        """测试删除不存在的产物"""
        result = artifact_store.delete_artifact("nonexistent-id")
        assert result is False

    def test_export_to_json(self, artifact_store):
        """测试导出为 JSON"""
        artifact = DataArtifact(
            step_id=1,
            tool_name="fetch_public_data",
            summary="测试数据",
            status="success",
            schema_info={"title": "str"},
        )

        payload = [{"title": "test"}]
        artifact_store.save_artifact(artifact, payload=payload)

        # 导出
        exported = artifact_store.export_to_json(artifact.artifact_id)
        assert exported is not None
        assert "metadata" in exported
        assert "data" in exported
        assert exported["data"] == payload

    def test_export_to_csv(self, artifact_store):
        """测试导出为 CSV"""
        artifact = DataArtifact(
            step_id=1,
            tool_name="fetch_public_data",
            summary="测试数据",
            status="success",
        )

        payload = [
            {"title": "test1", "value": 100},
            {"title": "test2", "value": 200},
        ]
        artifact_store.save_artifact(artifact, payload=payload)

        # 导出
        csv_content = artifact_store.export_to_csv(artifact.artifact_id)
        assert csv_content is not None
        assert "title,value" in csv_content
        assert "test1,100" in csv_content

    def test_stats(self, artifact_store):
        """测试统计信息"""
        # 创建一些产物
        for i in range(5):
            artifact = DataArtifact(
                step_id=i,
                tool_name="fetch_public_data",
                summary=f"数据 {i}",
                status="success",
            )
            artifact_store.save_artifact(artifact)

        stats = artifact_store.stats()
        assert stats["total_artifacts"] == 5
        assert "data_store" in stats


class TestArtifactRecord:
    """ArtifactRecord 测试"""

    def test_to_artifact_conversion(self):
        """测试记录转换为产物"""
        record = ArtifactRecord(
            artifact_id="artifact-test",
            data_id="lg-test",
            name="测试产物",
            description="测试描述",
            artifact_type="dataset",
            workflow_id="wf-123",
            step_id=1,
            tool_name="fetch_public_data",
            summary="测试摘要",
            status="success",
            schema_info_json='{"title": "str"}',
            statistics_json='{"record_count": 10}',
            suggested_views_json='[{"view_type": "table", "title": "数据"}]',
            tags_json='["test"]',
        )

        artifact = record.to_artifact()

        assert artifact.artifact_id == "artifact-test"
        assert artifact.name == "测试产物"
        assert artifact.artifact_type == ArtifactType.DATASET
        assert artifact.schema_info == {"title": "str"}
        assert artifact.tags == ["test"]
        assert len(artifact.suggested_views) == 1

    def test_from_artifact_conversion(self):
        """测试产物转换为记录"""
        artifact = DataArtifact(
            artifact_id="artifact-test",
            data_id="lg-test",
            step_id=1,
            tool_name="fetch_public_data",
            summary="测试摘要",
            status="success",
            name="测试产物",
            artifact_type=ArtifactType.ANALYSIS,
            schema_info={"value": "int"},
            suggested_views=[ViewSpec(view_type=ViewType.BAR_CHART, title="图表")],
            tags=["demo"],
        )

        record = ArtifactRecord.from_artifact(artifact)

        assert record.artifact_id == "artifact-test"
        assert record.artifact_type == "analysis"
        assert '"value": "int"' in record.schema_info_json
        assert "demo" in record.tags_json
