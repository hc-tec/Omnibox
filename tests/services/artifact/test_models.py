"""
DataArtifact 模型测试
"""

import pytest
from datetime import datetime

from langgraph_agents.state import DataReference, EnhancedDataReference
from services.artifact.models import (
    DataArtifact,
    ArtifactType,
    ArtifactSource,
    ArtifactRef,
    ViewSpec,
    ViewType,
)


class TestDataArtifactModel:
    """DataArtifact 模型测试"""

    def test_create_basic_artifact(self):
        """测试创建基本产物"""
        artifact = DataArtifact(
            step_id=1,
            tool_name="fetch_public_data",
            data_id="lg-abc123",
            summary="获取了 10 条数据",
            status="success",
        )

        assert artifact.artifact_id.startswith("artifact-")
        assert artifact.artifact_type == ArtifactType.DATASET
        assert artifact.step_id == 1
        assert artifact.tool_name == "fetch_public_data"
        assert artifact.name  # 自动生成的名称
        assert artifact.source is not None
        assert artifact.source.step_id == 1

    def test_auto_generate_name(self):
        """测试自动生成名称"""
        artifact = DataArtifact(
            step_id=1,
            tool_name="data_operator",
            summary="测试",
            status="success",
        )

        # 名称格式: {tool_name}_{MMdd_HHmm}
        assert "data_operator_" in artifact.name

    def test_from_enhanced_reference(self):
        """测试从 EnhancedDataReference 创建"""
        ref = EnhancedDataReference(
            step_id=1,
            tool_name="fetch_public_data",
            data_id="lg-abc123",
            summary="获取了 10 条数据",
            status="success",
            schema_info={"title": "str", "date": "datetime", "views": "int"},
            statistics={"record_count": 10},
            sample_items=[{"title": "test", "date": "2024-01-01", "views": 100}],
            quality_score=0.9,
        )

        artifact = DataArtifact.from_enhanced_reference(
            ref,
            workflow_id="wf-123",
            artifact_type=ArtifactType.DATASET,
        )

        assert artifact.artifact_type == ArtifactType.DATASET
        assert artifact.source.workflow_id == "wf-123"
        assert artifact.source.step_id == 1
        assert artifact.data_id == "lg-abc123"
        assert artifact.schema_info == {"title": "str", "date": "datetime", "views": "int"}
        assert artifact.quality_score == 0.9

    def test_from_basic_reference(self):
        """测试从基础 DataReference 创建"""
        ref = DataReference(
            step_id=2,
            tool_name="data_operator",
            data_id="lg-xyz789",
            summary="过滤后剩余 5 条",
            status="success",
        )

        # 先转换为 EnhancedDataReference
        enhanced = EnhancedDataReference(
            step_id=ref.step_id,
            tool_name=ref.tool_name,
            data_id=ref.data_id,
            summary=ref.summary,
            status=ref.status,
        )

        artifact = DataArtifact.from_enhanced_reference(enhanced)

        assert artifact.artifact_type == ArtifactType.ANALYSIS  # data_operator 推断为 analysis
        assert artifact.step_id == 2
        assert artifact.data_id == "lg-xyz789"

    def test_infer_artifact_type(self):
        """测试产物类型推断"""
        assert DataArtifact._infer_artifact_type("fetch_public_data") == ArtifactType.DATASET
        assert DataArtifact._infer_artifact_type("fetch_private_data") == ArtifactType.DATASET
        assert DataArtifact._infer_artifact_type("data_operator") == ArtifactType.ANALYSIS
        assert DataArtifact._infer_artifact_type("data_filter") == ArtifactType.ANALYSIS
        assert DataArtifact._infer_artifact_type("synthesizer") == ArtifactType.INSIGHT
        assert DataArtifact._infer_artifact_type("unknown_tool") == ArtifactType.DATASET

    def test_generate_workflow_id(self):
        """测试生成工作流 ID"""
        wf_id = DataArtifact.generate_workflow_id()
        assert wf_id.startswith("wf-")
        assert len(wf_id) == 15  # wf- + 12 hex chars

    def test_artifact_with_views(self):
        """测试带可视化建议的产物"""
        views = [
            ViewSpec(view_type=ViewType.TABLE, title="数据详情"),
            ViewSpec(view_type=ViewType.LINE_CHART, title="趋势图", config={"x": "date", "y": "value"}),
        ]

        artifact = DataArtifact(
            step_id=1,
            tool_name="fetch_public_data",
            summary="测试",
            status="success",
            suggested_views=views,
        )

        assert len(artifact.suggested_views) == 2
        assert artifact.suggested_views[0].view_type == ViewType.TABLE
        assert artifact.suggested_views[1].config == {"x": "date", "y": "value"}

    def test_artifact_with_relations(self):
        """测试带引用关系的产物"""
        artifact = DataArtifact(
            step_id=2,
            tool_name="data_operator",
            summary="测试",
            status="success",
            derived_from=[ArtifactRef(artifact_id="artifact-parent", relation_type="derived_from")],
        )

        assert len(artifact.derived_from) == 1
        assert artifact.derived_from[0].artifact_id == "artifact-parent"

    def test_artifact_with_tags(self):
        """测试带标签的产物"""
        artifact = DataArtifact(
            step_id=1,
            tool_name="fetch_public_data",
            summary="测试",
            status="success",
            tags=["bilibili", "video", "tech"],
        )

        assert len(artifact.tags) == 3
        assert "bilibili" in artifact.tags


class TestViewSpec:
    """ViewSpec 测试"""

    def test_create_view_spec(self):
        """测试创建可视化规格"""
        spec = ViewSpec(
            view_type=ViewType.BAR_CHART,
            title="分布统计",
            config={"x_field": "category", "y_field": "count"},
        )

        assert spec.view_type == ViewType.BAR_CHART
        assert spec.title == "分布统计"
        assert spec.config["x_field"] == "category"

    def test_view_spec_minimal(self):
        """测试最小化可视化规格"""
        spec = ViewSpec(view_type=ViewType.TEXT)

        assert spec.view_type == ViewType.TEXT
        assert spec.title is None
        assert spec.config == {}


class TestArtifactSource:
    """ArtifactSource 测试"""

    def test_create_source(self):
        """测试创建来源信息"""
        source = ArtifactSource(
            workflow_id="wf-123",
            step_id=1,
            tool_name="fetch_public_data",
        )

        assert source.workflow_id == "wf-123"
        assert source.step_id == 1
        assert isinstance(source.created_at, datetime)

    def test_source_without_workflow(self):
        """测试无工作流的来源信息"""
        source = ArtifactSource(
            step_id=1,
            tool_name="fetch_public_data",
        )

        assert source.workflow_id is None
