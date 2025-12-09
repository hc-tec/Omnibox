# Phase 1: DataArtifact 基础设施设计方案

**创建日期**: 2025-12-09
**状态**: ✅ 已完成
**完成日期**: 2025-12-09
**目标**: 建立"数据产物"核心模型，作为工作流工作台的基础设施

---

## 一、现状分析

### 1.1 可直接复用的现有组件

经过代码分析，项目中已有完善的数据存储和工作流基础设施：

| 组件 | 文件位置 | 功能 | 复用策略 |
|------|---------|------|---------|
| **ResearchDataStore** | `langgraph_agents/storage.py` | 内存数据存储（LRU + TTL） | ✅ 直接复用，扩展持久化 |
| **EnhancedDataReference** | `langgraph_agents/state.py` | 数据引用 + 元数据 | ✅ 作为 DataArtifact 基础 |
| **SchemaRegistry** | `langgraph_agents/schema_registry.py` | Schema 注册 | ✅ 直接复用 |
| **ExecutionPlan** | `langgraph_agents/state.py` | 执行计划 DAG | ✅ 后续 Phase 复用 |
| **ExecutionEngine** | `langgraph_agents/execution_engine.py` | 执行调度器 | ✅ 后续 Phase 复用 |
| **KnowledgeGraph** | `langgraph_agents/knowledge_graph.py` | 数据血缘关系 | ✅ 直接复用 |
| **MetadataExtractor** | `langgraph_agents/metadata_extractor.py` | 自动元数据提取 | ✅ 直接复用 |
| **DataStasher** | `langgraph_agents/agents/data_stasher.py` | 数据摘要生成 | ✅ 直接复用 |

### 1.2 现有 EnhancedDataReference 结构

```python
# langgraph_agents/state.py
class DataReference(BaseModel):
    step_id: int                    # 步骤编号
    tool_name: str                  # 工具名称
    data_id: Optional[str]          # 外部存储 ID
    summary: str                    # 摘要
    status: Literal["success", "error", "needs_user_input"]
    error_message: Optional[str]

class EnhancedDataReference(DataReference):
    schema_info: Optional[Dict[str, str]]     # 字段类型
    statistics: Optional[Dict[str, Any]]       # 统计信息
    sample_items: Optional[List[Dict]]         # 样本数据
    quality_score: Optional[float]             # 质量评分
```

### 1.3 差距分析

| 需求 | 现有支持 | 缺失部分 |
|------|---------|---------|
| 数据产物标识 | ✅ data_id | - |
| 元数据（schema/统计） | ✅ EnhancedDataReference | - |
| 数据摘要 | ✅ summary | - |
| 来源追溯 | ⚠️ step_id + tool_name | 缺少 workflow_id、timestamp |
| 可视化建议 | ❌ 无 | 需新增 suggested_views |
| 引用关系 | ⚠️ KnowledgeGraph 有 | 未集成到 DataReference |
| 数据类型分类 | ❌ 无 | 需新增 artifact_type |
| 持久化 | ❌ 仅内存 | 需扩展 SQLite/Redis |
| 导出能力 | ❌ 无 | 需新增 export 方法 |

---

## 二、改造方案

### 2.1 设计原则

1. **渐进式扩展** - 不修改现有 DataReference/EnhancedDataReference，新增 DataArtifact 类继承它们
2. **向后兼容** - 现有 LangGraph 工作流继续使用 DataReference，无需修改
3. **可选升级** - 需要完整功能时使用 DataArtifact，简单场景继续用 DataReference
4. **复用存储层** - 扩展 ResearchDataStore 接口，不重新实现

### 2.2 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DataArtifact 层（新增）                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  DataArtifact(EnhancedDataReference)                        │   │
│  │  + artifact_type: dataset/analysis/insight/document         │   │
│  │  + source: {workflow_id, step_id, created_at}              │   │
│  │  + suggested_views: List[ViewSpec]                         │   │
│  │  + derived_from: List[ArtifactRef]                         │   │
│  │  + used_by: List[ArtifactRef]                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ArtifactStore(ResearchDataStore)                           │   │
│  │  + save_artifact() / load_artifact()                        │   │
│  │  + list_by_workflow() / list_by_type()                     │   │
│  │  + export_to_json() / export_to_csv()                      │   │
│  │  + SQLite 持久化适配器（新增）                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ 继承
┌─────────────────────────────────────────────────────────────────────┐
│                    现有 LangGraph 基础设施（不修改）                  │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐  │
│  │  EnhancedDataReference  │  │  ResearchDataStore              │  │
│  │  (langgraph_agents/     │  │  (langgraph_agents/storage.py)  │  │
│  │   state.py)             │  │  - save() / load()              │  │
│  └─────────────────────────┘  │  - InMemoryResearchDataStore    │  │
│                               └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、数据模型设计

### 3.1 DataArtifact 模型

**文件位置**: `services/artifact/models.py`（新建）

```python
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from langgraph_agents.state import EnhancedDataReference


class ArtifactType(str, Enum):
    """数据产物类型"""
    DATASET = "dataset"       # 原始数据集（来自 fetch_public_data 等）
    ANALYSIS = "analysis"     # 分析结果（来自 data_operator）
    INSIGHT = "insight"       # 洞察/见解（来自 synthesizer）
    DOCUMENT = "document"     # 文档/报告


class ViewType(str, Enum):
    """可视化类型"""
    TABLE = "table"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    LIST = "list"
    CARD = "card"
    TEXT = "text"


class ViewSpec(BaseModel):
    """可视化规格"""
    view_type: ViewType
    title: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    # 例如: {"x_field": "date", "y_field": "value", "group_by": "category"}


class ArtifactSource(BaseModel):
    """数据产物来源"""
    workflow_id: Optional[str] = None   # 所属工作流 ID
    step_id: int                        # 步骤编号
    tool_name: str                      # 生成工具
    created_at: datetime = Field(default_factory=datetime.now)


class ArtifactRef(BaseModel):
    """数据产物引用"""
    artifact_id: str
    relation_type: str = "derived_from"  # derived_from / compared_with / generated


class DataArtifact(EnhancedDataReference):
    """
    数据产物 - 工作流工作台的核心数据单元

    继承自 EnhancedDataReference，扩展以下能力：
    - 产物类型分类
    - 完整来源追溯
    - 可视化建议
    - 引用关系追踪
    """

    # 产物分类
    artifact_type: ArtifactType = ArtifactType.DATASET

    # 产物命名（人类可读）
    name: str = ""
    description: str = ""

    # 来源追溯（扩展 step_id + tool_name）
    source: Optional[ArtifactSource] = None

    # 可视化建议
    suggested_views: List[ViewSpec] = Field(default_factory=list)

    # 引用关系
    derived_from: List[ArtifactRef] = Field(default_factory=list)
    used_by: List[ArtifactRef] = Field(default_factory=list)

    # 标签（便于检索）
    tags: List[str] = Field(default_factory=list)

    @classmethod
    def from_enhanced_reference(
        cls,
        ref: EnhancedDataReference,
        workflow_id: Optional[str] = None,
        artifact_type: ArtifactType = ArtifactType.DATASET,
        name: str = "",
    ) -> "DataArtifact":
        """从现有 EnhancedDataReference 创建 DataArtifact"""
        return cls(
            # 继承所有父类字段
            step_id=ref.step_id,
            tool_name=ref.tool_name,
            data_id=ref.data_id,
            summary=ref.summary,
            status=ref.status,
            error_message=ref.error_message,
            schema_info=ref.schema_info,
            statistics=ref.statistics,
            sample_items=ref.sample_items,
            quality_score=ref.quality_score,
            # 新增字段
            artifact_type=artifact_type,
            name=name or f"{ref.tool_name}_output",
            source=ArtifactSource(
                workflow_id=workflow_id,
                step_id=ref.step_id,
                tool_name=ref.tool_name,
            ),
        )
```

### 3.2 ArtifactStore 存储层

**文件位置**: `services/artifact/store.py`（新建）

```python
from abc import ABC, abstractmethod
from typing import Optional, List, Any, Dict
from datetime import datetime
from langgraph_agents.storage import ResearchDataStore, InMemoryResearchDataStore
from .models import DataArtifact, ArtifactType


class ArtifactStore(ABC):
    """
    数据产物存储层抽象接口

    继承 ResearchDataStore 的能力，扩展产物特有操作
    """

    def __init__(self, data_store: ResearchDataStore):
        """复用现有 ResearchDataStore 作为底层存储"""
        self._data_store = data_store
        self._artifacts: Dict[str, DataArtifact] = {}  # artifact_id -> DataArtifact

    # ========== 核心操作（复用 ResearchDataStore）==========

    def save_data(self, payload: Any) -> str:
        """保存原始数据，返回 data_id（委托给底层存储）"""
        return self._data_store.save(payload)

    def load_data(self, data_id: str) -> Optional[Any]:
        """加载原始数据（委托给底层存储）"""
        return self._data_store.load(data_id)

    # ========== 产物元数据操作（新增）==========

    def save_artifact(self, artifact: DataArtifact) -> str:
        """保存产物元数据，返回 artifact_id"""
        artifact_id = artifact.data_id or f"artifact_{datetime.now().timestamp()}"
        self._artifacts[artifact_id] = artifact
        return artifact_id

    def load_artifact(self, artifact_id: str) -> Optional[DataArtifact]:
        """加载产物元数据"""
        return self._artifacts.get(artifact_id)

    def list_artifacts(
        self,
        workflow_id: Optional[str] = None,
        artifact_type: Optional[ArtifactType] = None,
        tags: Optional[List[str]] = None,
    ) -> List[DataArtifact]:
        """按条件查询产物列表"""
        results = list(self._artifacts.values())

        if workflow_id:
            results = [a for a in results if a.source and a.source.workflow_id == workflow_id]
        if artifact_type:
            results = [a for a in results if a.artifact_type == artifact_type]
        if tags:
            results = [a for a in results if set(tags) & set(a.tags)]

        return results

    # ========== 导出能力（新增）==========

    def export_to_json(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """导出产物为 JSON"""
        artifact = self.load_artifact(artifact_id)
        if not artifact:
            return None

        data = self.load_data(artifact.data_id) if artifact.data_id else None
        return {
            "metadata": artifact.model_dump(),
            "data": data,
        }

    def export_to_csv(self, artifact_id: str) -> Optional[str]:
        """导出产物为 CSV（仅支持表格型数据）"""
        import csv
        import io

        artifact = self.load_artifact(artifact_id)
        if not artifact or not artifact.data_id:
            return None

        data = self.load_data(artifact.data_id)
        if not isinstance(data, list) or not data:
            return None

        output = io.StringIO()
        if isinstance(data[0], dict):
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return output.getvalue()


class InMemoryArtifactStore(ArtifactStore):
    """内存实现（开发/测试用）"""

    def __init__(self, max_items: int = 1000, ttl_seconds: int = 3600):
        super().__init__(InMemoryResearchDataStore(max_items, ttl_seconds))


# 后续可添加：
# class SQLiteArtifactStore(ArtifactStore): ...
# class RedisArtifactStore(ArtifactStore): ...
```

### 3.3 ViewSpec 推断器

**文件位置**: `services/artifact/view_suggester.py`（新建）

```python
from typing import List, Dict, Any, Optional
from .models import ViewSpec, ViewType


def suggest_views(
    schema_info: Optional[Dict[str, str]],
    statistics: Optional[Dict[str, Any]],
    sample_items: Optional[List[Dict]],
) -> List[ViewSpec]:
    """
    根据数据特征自动推荐合适的可视化方式

    复用现有 metadata_extractor 的输出
    """
    suggestions = []

    if not schema_info or not sample_items:
        # 无法推断，返回默认文本视图
        return [ViewSpec(view_type=ViewType.TEXT)]

    # 检测字段类型
    numeric_fields = [k for k, v in schema_info.items() if v in ("int", "float", "number")]
    date_fields = [k for k, v in schema_info.items() if v in ("date", "datetime", "timestamp")]
    text_fields = [k for k, v in schema_info.items() if v in ("str", "string", "text")]

    record_count = statistics.get("record_count", 0) if statistics else len(sample_items)

    # 规则1: 有日期 + 有数值 → 折线图
    if date_fields and numeric_fields:
        suggestions.append(ViewSpec(
            view_type=ViewType.LINE_CHART,
            title="趋势分析",
            config={"x_field": date_fields[0], "y_field": numeric_fields[0]},
        ))

    # 规则2: 有分类字段 + 有数值 → 柱状图
    category_fields = [k for k, v in schema_info.items() if v == "str" and k not in ("id", "url", "link")]
    if category_fields and numeric_fields:
        suggestions.append(ViewSpec(
            view_type=ViewType.BAR_CHART,
            title="分布统计",
            config={"x_field": category_fields[0], "y_field": numeric_fields[0]},
        ))

    # 规则3: 少量数值字段（<= 5）→ 饼图
    if len(numeric_fields) <= 5 and record_count <= 10:
        suggestions.append(ViewSpec(
            view_type=ViewType.PIE_CHART,
            title="占比分析",
            config={"value_field": numeric_fields[0] if numeric_fields else None},
        ))

    # 规则4: 多行数据 → 表格（通用）
    if record_count > 1:
        suggestions.append(ViewSpec(
            view_type=ViewType.TABLE,
            title="数据详情",
            config={"columns": list(schema_info.keys())[:10]},  # 限制列数
        ))

    # 规则5: 有 title/name 字段 → 列表
    if any(f in schema_info for f in ("title", "name", "label")):
        title_field = next(f for f in ("title", "name", "label") if f in schema_info)
        suggestions.append(ViewSpec(
            view_type=ViewType.LIST,
            title="数据列表",
            config={"title_field": title_field},
        ))

    return suggestions if suggestions else [ViewSpec(view_type=ViewType.TEXT)]
```

---

## 四、集成方案

### 4.1 与 LangGraph 集成

在 DataStasher 中添加可选的 DataArtifact 创建：

```python
# langgraph_agents/agents/data_stasher.py 中添加

from services.artifact.models import DataArtifact, ArtifactType
from services.artifact.view_suggester import suggest_views

def _create_artifact_if_needed(
    ref: EnhancedDataReference,
    workflow_id: Optional[str] = None,
) -> Optional[DataArtifact]:
    """可选：将 EnhancedDataReference 升级为 DataArtifact"""
    if not workflow_id:
        return None  # 非工作流模式，不创建 Artifact

    # 推断产物类型
    artifact_type = _infer_artifact_type(ref.tool_name)

    # 推断可视化建议
    suggested_views = suggest_views(
        ref.schema_info,
        ref.statistics,
        ref.sample_items,
    )

    artifact = DataArtifact.from_enhanced_reference(
        ref,
        workflow_id=workflow_id,
        artifact_type=artifact_type,
    )
    artifact.suggested_views = suggested_views

    return artifact

def _infer_artifact_type(tool_name: str) -> ArtifactType:
    """根据工具名推断产物类型"""
    if tool_name in ("fetch_public_data", "fetch_private_data"):
        return ArtifactType.DATASET
    elif tool_name in ("data_operator",):
        return ArtifactType.ANALYSIS
    elif tool_name in ("synthesizer",):
        return ArtifactType.INSIGHT
    else:
        return ArtifactType.DATASET
```

### 4.2 与前端集成

扩展现有类型定义：

```typescript
// frontend/src/types/artifact.ts（新建）

export interface DataArtifact {
  // 继承 DataReference
  data_id: string;
  step_id: number;
  tool_name: string;
  summary: string;
  status: 'success' | 'error' | 'needs_user_input';

  // 元数据
  schema_info?: Record<string, string>;
  statistics?: Record<string, any>;
  sample_items?: Record<string, any>[];
  quality_score?: number;

  // 新增字段
  artifact_type: 'dataset' | 'analysis' | 'insight' | 'document';
  name: string;
  description: string;
  source: {
    workflow_id?: string;
    step_id: number;
    tool_name: string;
    created_at: string;
  };
  suggested_views: ViewSpec[];
  derived_from: ArtifactRef[];
  used_by: ArtifactRef[];
  tags: string[];
}

export interface ViewSpec {
  view_type: 'table' | 'line_chart' | 'bar_chart' | 'pie_chart' | 'list' | 'card' | 'text';
  title?: string;
  config: Record<string, any>;
}

export interface ArtifactRef {
  artifact_id: string;
  relation_type: 'derived_from' | 'compared_with' | 'generated';
}
```

---

## 五、迁移计划

### 5.1 Phase 1 分阶段实施

| 阶段 | 内容 | 预计工作量 |
|------|------|-----------|
| 1.1 | 创建 `services/artifact/` 目录结构 | 0.5 天 |
| 1.2 | 实现 DataArtifact 模型 | 1 天 |
| 1.3 | 实现 InMemoryArtifactStore | 1 天 |
| 1.4 | 实现 ViewSpec 推断器 | 0.5 天 |
| 1.5 | 与 DataStasher 集成（可选升级） | 1 天 |
| 1.6 | 前端类型定义 + Store 扩展 | 1 天 |
| 1.7 | 单元测试 + 集成测试 | 1 天 |

**总计**: 约 6 天

### 5.2 向后兼容保证

1. **现有 LangGraph 工作流**：继续使用 DataReference/EnhancedDataReference，无需修改
2. **新工作流模式**：传入 `workflow_id` 参数时，自动创建 DataArtifact
3. **前端**：现有 ResearchViewStore 保持不变，新增 ArtifactStore

### 5.3 回滚策略

如果出现问题：
1. 删除 `services/artifact/` 目录
2. 从 DataStasher 移除 `_create_artifact_if_needed` 调用
3. 不影响现有任何功能

---

## 六、测试策略

### 6.1 单元测试

```python
# tests/services/artifact/test_models.py

def test_data_artifact_from_enhanced_reference():
    """测试从 EnhancedDataReference 创建 DataArtifact"""
    ref = EnhancedDataReference(
        step_id=1,
        tool_name="fetch_public_data",
        data_id="lg-abc123",
        summary="获取了 10 条数据",
        status="success",
        schema_info={"title": "str", "date": "datetime", "views": "int"},
        statistics={"record_count": 10},
        sample_items=[{"title": "test", "date": "2024-01-01", "views": 100}],
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


def test_view_suggester_with_time_series():
    """测试时序数据的可视化推荐"""
    views = suggest_views(
        schema_info={"date": "datetime", "value": "float"},
        statistics={"record_count": 30},
        sample_items=[{"date": "2024-01-01", "value": 100}],
    )

    assert any(v.view_type == ViewType.LINE_CHART for v in views)
```

### 6.2 集成测试

```python
# tests/services/artifact/test_integration.py

def test_artifact_lifecycle():
    """测试产物完整生命周期"""
    store = InMemoryArtifactStore()

    # 1. 保存原始数据
    data_id = store.save_data([{"title": "test", "value": 100}])

    # 2. 创建产物
    artifact = DataArtifact(
        step_id=1,
        tool_name="fetch_public_data",
        data_id=data_id,
        summary="测试数据",
        status="success",
        artifact_type=ArtifactType.DATASET,
        name="测试产物",
    )
    artifact_id = store.save_artifact(artifact)

    # 3. 查询产物
    loaded = store.load_artifact(artifact_id)
    assert loaded.name == "测试产物"

    # 4. 导出
    exported = store.export_to_json(artifact_id)
    assert exported["data"] == [{"title": "test", "value": 100}]
```

---

## 七、TODO 清单

- [x] Stage 1.1: 创建目录结构
  - [x] `services/artifact/__init__.py`
  - [x] `services/artifact/models.py`
  - [x] `services/artifact/store.py`
  - [x] `services/artifact/view_suggester.py`
  - [x] `services/artifact/langgraph_integration.py`
- [x] Stage 1.2: 实现 DataArtifact 模型
- [x] Stage 1.3: 实现 ArtifactStore + SQLite 持久化
- [x] Stage 1.4: 实现 ViewSpec 推断器
- [x] Stage 1.5: 与 DataStasher 集成（通过 langgraph_integration.py）
- [x] Stage 1.6: 前端类型定义
- [x] Stage 1.7: 单元测试 + 集成测试（24 个测试全部通过）

---

## 八、已确认决策

| 问题 | 决策 | 理由 |
|------|------|------|
| **持久化** | ✅ 需要 SQLite | 数据产物需要跨会话保留 |
| **工作流 ID** | ✅ 后端生成 | UUID，更可控，避免前端重复 |
| **产物命名** | ✅ 全部自动生成 | 基于工具名 + 时间戳 |
| **导出格式** | ✅ 仅 JSON/CSV | 暂不需要 Excel/Parquet |

---

## 九、实施进度

- [x] 用户确认设计方案 (2025-12-09)
- [x] Stage 1.1: 创建目录结构 (2025-12-09)
- [x] Stage 1.2: 实现 DataArtifact 模型 (2025-12-09)
- [x] Stage 1.3: 实现 ArtifactStore + SQLite 持久化 (2025-12-09)
- [x] Stage 1.4: 实现 ViewSpec 推断器 (2025-12-09)
- [x] Stage 1.5: 与 DataStasher 集成 (2025-12-09)
- [x] Stage 1.6: 前端类型定义 (2025-12-09)
- [x] Stage 1.7: 单元测试 + 集成测试 (2025-12-09)

---

## 十、实施总结

### 10.1 创建的文件

| 文件 | 说明 |
|------|------|
| `services/artifact/__init__.py` | 模块入口，导出所有公共接口 |
| `services/artifact/models.py` | DataArtifact 模型定义 |
| `services/artifact/store.py` | ArtifactStore + SQLite 持久化 |
| `services/artifact/view_suggester.py` | ViewSpec 自动推荐 |
| `services/artifact/langgraph_integration.py` | LangGraph 集成辅助函数 |
| `frontend/src/types/artifact.ts` | 前端 TypeScript 类型定义 |
| `tests/services/artifact/test_models.py` | 模型单元测试 |
| `tests/services/artifact/test_store.py` | 存储层单元测试 |

### 10.2 复用的现有组件

- `langgraph_agents.state.EnhancedDataReference` - 作为 DataArtifact 基类
- `langgraph_agents.storage.ResearchDataStore` - 委托原始数据存储
- `services.database.connection.DatabaseConnection` - SQLite 连接管理

### 10.3 测试覆盖

- 24 个单元测试全部通过
- 覆盖：模型创建、类型推断、存储 CRUD、导出功能、记录转换
