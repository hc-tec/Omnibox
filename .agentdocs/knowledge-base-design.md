# 知识库系统设计方案

> **目标**：在现有 RSS 聚合系统基础上，引入个人知识库能力，支持笔记管理、收藏管理、标签系统、知识检索和智能关联，将系统从"工具"升级为"个人知识助手"。

---

## 核心功能概览

### 1. 笔记管理
- **Markdown 编辑器** - 实时预览、代码高亮、图片上传
- **层级组织** - 支持文件夹/嵌套笔记
- **双向链接** - `[[笔记名称]]` 语法，自动建立关联
- **版本历史** - 保存编辑历史，支持回滚（可选）

### 2. 收藏管理
- **多类型收藏** - Panel 结果、研究任务、RSS 条目、网页链接
- **快照保存** - 保存完整布局/数据快照，防止数据丢失
- **快速恢复** - 一键恢复到原始 Panel/研究任务状态

### 3. 标签系统
- **灵活标签** - 自定义颜色、图标、描述
- **标签推荐** - 基于内容自动推荐标签（AI辅助）
- **标签云** - 可视化展示标签使用频率

### 4. 知识检索
- **混合检索** - 全文搜索（SQLite FTS5）+ 语义搜索（RAG）
- **高级过滤** - 按标签、日期、类型、收藏状态筛选
- **搜索结果高亮** - 关键词高亮、上下文预览

### 5. 智能关联
- **自动推荐** - 在 Panel 查询时推荐相关笔记
- **研究时引用** - LangGraph Agents 可以检索知识库
- **知识图谱** - 可视化笔记间的关联关系

---

## 设计原则

### 1. Markdown 为中心
- **为什么不是 WYSIWYG（所见即所得）？**
  - Markdown 是纯文本，易于版本控制（Git）
  - 易于导入/导出，不被特定平台绑定
  - 符合技术用户习惯（开发者友好）
  - 支持代码块、公式、图表等高级格式

**参考案例**：Obsidian、Logseq、Typora

### 2. 双向链接优于单向引用
- **双向链接** - 点击 `[[笔记A]]` 跳转，笔记A 自动显示"被引用列表"
- **网状知识结构** - 而非树状文件夹，更符合人脑联想
- **知识涌现** - 随着笔记增多，关联关系自然形成知识网络

**参考案例**：Roam Research、Obsidian Graph View

### 3. 标签优于文件夹
- **多标签** - 一篇笔记可以有多个标签，而文件夹只能属于一个
- **动态组织** - 标签可以随时调整，文件夹移动成本高
- **保留层级** - 仍支持 `parent_id` 实现简单层级，但不强制

**参考案例**：Notion、Bear

### 4. 本地优先，云端同步
- **数据主权** - SQLite 本地数据库，用户完全控制
- **快速响应** - 无需网络，即时加载
- **隐私保护** - 敏感笔记不上传云端
- **可选同步** - 后续可扩展 WebDAV/Git 同步（可选）

**参考案例**：Obsidian、Joplin

### 5. 渐进式增强
- **Phase 1** - 基础笔记 + 收藏 + 标签（MVP）
- **Phase 2** - 语义搜索 + 双向链接
- **Phase 3** - 知识图谱 + AI 辅助写作
- **Phase 4** - 协作分享 + 云端同步（可选）

---

## 架构设计

### 1. 数据模型设计

#### 1.1 核心实体

```python
# services/database/knowledge_models.py
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional, List

class Note(SQLModel, table=True):
    """笔记

    Markdown 为中心的笔记系统，支持层级组织和双向链接。
    """
    __tablename__ = "notes"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True, description="笔记标题")
    content: str = Field(description="Markdown 格式内容")
    content_plain: str = Field(description="纯文本内容，用于全文搜索")

    # 层级组织
    parent_id: Optional[int] = Field(default=None, foreign_key="notes.id", description="父笔记ID（文件夹）")

    # 状态标记
    is_favorite: bool = Field(default=False, description="是否收藏")
    is_archived: bool = Field(default=False, description="是否归档")
    is_pinned: bool = Field(default=False, description="是否置顶")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 多用户支持（可选）
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)

    # 元数据
    word_count: int = Field(default=0, description="字数统计")
    read_time_minutes: int = Field(default=0, description="预计阅读时间（分钟）")


class Tag(SQLModel, table=True):
    """标签

    支持颜色、图标、描述，用于灵活组织笔记。
    """
    __tablename__ = "tags"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, description="标签名称")
    color: str = Field(default="#6B7280", description="标签颜色（Hex）")
    icon: Optional[str] = Field(default=None, description="标签图标（emoji 或 icon name）")
    description: Optional[str] = Field(default=None, description="标签说明")

    # 多用户支持（可选）
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)

    created_at: datetime = Field(default_factory=datetime.now)


class NoteTag(SQLModel, table=True):
    """笔记-标签关联（多对多）"""
    __tablename__ = "note_tags"

    note_id: int = Field(foreign_key="notes.id", primary_key=True)
    tag_id: int = Field(foreign_key="tags.id", primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)


class Bookmark(SQLModel, table=True):
    """收藏

    支持多种类型的收藏：Panel结果、研究任务、RSS条目、网页链接。
    采用多态设计，使用 type 字段区分类型。
    """
    __tablename__ = "bookmarks"

    id: Optional[int] = Field(default=None, primary_key=True)

    # 多态类型
    type: str = Field(index=True, description="类型：panel_session/research_task/rss_item/web_link")

    # 引用（如果是系统内对象）
    reference_id: Optional[int] = Field(default=None, index=True, description="引用的对象ID")
    reference_data: str = Field(description="完整数据快照（JSON格式）")

    # 显示信息
    title: str = Field(description="收藏标题")
    description: Optional[str] = Field(default=None, description="描述/摘要")
    thumbnail_url: Optional[str] = Field(default=None, description="缩略图URL")
    source_url: Optional[str] = Field(default=None, description="源链接")

    # 元数据
    tags_snapshot: str = Field(default="[]", description="收藏时的标签快照（JSON数组）")

    created_at: datetime = Field(default_factory=datetime.now, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)


class NoteLink(SQLModel, table=True):
    """笔记链接（双向链接）

    记录笔记间的关联关系，支持多种链接类型。
    """
    __tablename__ = "note_links"

    id: Optional[int] = Field(default=None, primary_key=True)

    source_note_id: int = Field(foreign_key="notes.id", index=True, description="源笔记ID")
    target_note_id: int = Field(foreign_key="notes.id", index=True, description="目标笔记ID")

    link_type: str = Field(default="mention", description="链接类型：mention/reference/related")
    context: Optional[str] = Field(default=None, description="链接上下文（链接周围的文本）")

    created_at: datetime = Field(default_factory=datetime.now)


class NoteEmbedding(SQLModel, table=True):
    """笔记向量化记录

    记录笔记的向量化状态，实际向量存储在 ChromaDB。
    """
    __tablename__ = "note_embeddings"

    note_id: int = Field(foreign_key="notes.id", primary_key=True)
    embedding_version: str = Field(description="向量模型版本，如 'bge-m3-v1'")
    last_embedded_at: datetime = Field(description="最后向量化时间")
    is_stale: bool = Field(default=False, description="内容是否已过时（需要重新向量化）")
```

#### 1.2 数据模型关系图

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    Note     │──────<│  NoteTag    │>──────│     Tag     │
│             │       │             │       │             │
│  - title    │       │ - note_id   │       │  - name     │
│  - content  │       │ - tag_id    │       │  - color    │
│  - parent_id│       └─────────────┘       │  - icon     │
└─────────────┘                             └─────────────┘
      │ ▲
      │ │ parent_id (self-reference)
      │ │
      └─┘

┌─────────────┐       ┌─────────────┐
│  NoteLink   │       │  Bookmark   │
│             │       │             │
│ - source_id │       │  - type     │
│ - target_id │       │  - ref_id   │
│ - type      │       │  - snapshot │
└─────────────┘       └─────────────┘

┌─────────────┐
│NoteEmbedding│  ──→  ChromaDB (user_knowledge)
│             │       存储实际向量
│ - note_id   │
│ - version   │
└─────────────┘
```

#### 1.3 数据库集成

知识库表与现有数据库架构的集成方案。

**集成到统一模型文件**

所有知识库表定义应集成到现有的 `services/database/models.py` 中,与运行时配置表保持一致:

```python
# services/database/models.py (统一模型文件)

from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

# ==================== 运行时配置表 ====================
class LLMProfile(SQLModel, table=True):
    """LLM配置"""
    __tablename__ = "llm_profiles"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    # ... 其他字段 ...

class RSSHubProfile(SQLModel, table=True):
    """RSSHub配置"""
    __tablename__ = "rsshub_profiles"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    # ... 其他字段 ...

# ==================== 知识库表 ====================
class Note(SQLModel, table=True):
    """笔记"""
    __tablename__ = "notes"
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    content: str
    content_plain: str = Field(description="纯文本内容(自动生成)")
    word_count: int = Field(default=0, description="字数(自动计算)")
    read_time_minutes: int = Field(default=0, description="阅读时间(自动计算)")

    # 层级组织
    parent_id: Optional[int] = Field(default=None, foreign_key="notes.id")

    # 状态标记
    is_favorite: bool = Field(default=False)
    is_archived: bool = Field(default=False)
    is_pinned: bool = Field(default=False)

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 多用户支持(可选,Stage 4之前为NULL)
    user_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        description="NULL表示公共笔记(单用户阶段)"
    )

class Tag(SQLModel, table=True):
    """标签"""
    __tablename__ = "tags"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    color: str = Field(default="#6B7280")
    icon: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.now)

class NoteTag(SQLModel, table=True):
    """笔记-标签关联"""
    __tablename__ = "note_tags"
    note_id: int = Field(foreign_key="notes.id", primary_key=True)
    tag_id: int = Field(foreign_key="tags.id", primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)

class Bookmark(SQLModel, table=True):
    """收藏"""
    __tablename__ = "bookmarks"
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(index=True, description="类型:panel_session/research_task/rss_item/web_link")
    reference_id: Optional[int] = Field(default=None, index=True)
    reference_data: str = Field(description="数据快照(JSON)")
    title: str
    description: Optional[str] = Field(default=None)
    thumbnail_url: Optional[str] = Field(default=None)
    source_url: Optional[str] = Field(default=None)
    tags_snapshot: str = Field(default="[]")
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)

class NoteLink(SQLModel, table=True):
    """笔记链接(双向)"""
    __tablename__ = "note_links"
    id: Optional[int] = Field(default=None, primary_key=True)
    source_note_id: int = Field(foreign_key="notes.id", index=True)
    target_note_id: int = Field(foreign_key="notes.id", index=True)
    link_type: str = Field(default="mention")
    context: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)

class NoteEmbedding(SQLModel, table=True):
    """笔记向量化记录"""
    __tablename__ = "note_embeddings"
    note_id: int = Field(foreign_key="notes.id", primary_key=True)
    embedding_version: str = Field(description="向量模型版本")
    last_embedded_at: datetime
    is_stale: bool = Field(default=False, description="是否需要重新向量化")
```

**Alembic 迁移集成**

按照现有的 Alembic 工作流创建迁移:

```bash
# 1. 生成迁移脚本
alembic revision --autogenerate -m "add knowledge base tables"

# 2. 审查生成的迁移脚本
# alembic/versions/xxxx_add_knowledge_base_tables.py

# 3. 执行迁移
alembic upgrade head
```

**用户ID处理策略**

在 Stage 4 用户系统实现之前:

1. **Phase 1-3**: `user_id` 字段允许为 `NULL`
   - 所有数据的 `user_id` 保持 `NULL`
   - 系统按"单用户模式"运行
   - 不进行任何用户隔离

2. **Stage 4 实现后**:
   - 创建 `users` 表
   - 为默认用户创建记录 (id=1)
   - 执行数据迁移: `UPDATE notes SET user_id = 1 WHERE user_id IS NULL`
   - 在 API 层添加用户认证和隔离逻辑

3. **向后兼容**:
   - Service 层的查询在 Stage 4 之前忽略 `user_id`
   - Stage 4 之后自动从请求上下文获取 `user_id`

```python
# services/knowledge/note_service.py
class NoteService:
    def list_notes(self, user_id: Optional[int] = None, **filters):
        """列出笔记

        Args:
            user_id: 用户ID (Stage 4之前为None,忽略用户隔离)
        """
        with self.db.get_session() as session:
            statement = select(Note)

            # Stage 4 之前: 忽略 user_id
            # Stage 4 之后: 添加 user_id 过滤
            if user_id is not None:
                statement = statement.where(Note.user_id == user_id)

            # 应用其他过滤器...
            return session.exec(statement).all()
```

**依赖关系管理**

知识库功能对其他模块的依赖:

| 功能 | 依赖阶段 | 说明 |
|------|---------|------|
| 基础笔记/标签 | Phase 1 | 独立,无依赖 |
| Panel 收藏 (数据引用) | Phase 1 | 只保存 reference_id 和基本信息 |
| Panel 收藏 (完整快照) | Phase 2 | 依赖 `PanelSession` 表 (持久化计划 Phase 2) |
| 研究任务收藏 | Phase 1 | 只需 research_task 表已存在 |
| 向量搜索 | Phase 2 | 依赖 ChromaDB 和 bge-m3 (已存在) |

**Phase 实施顺序**

按照依赖关系,推荐实施顺序:

1. **知识库 Phase 1** (基础笔记/标签/收藏) - 可立即开始
2. **持久化计划 Phase 2** (PanelSession 表) - 并行开发
3. **知识库 Phase 2** (向量搜索) - 依赖 Phase 1 完成
4. **知识库 Phase 3** (双向链接/LangGraph 集成) - 依赖 Phase 2 完成
5. **持久化计划 Stage 4** (用户系统) - 长期规划

#### 1.4 派生字段自动计算

`content_plain`、`word_count`、`read_time_minutes` 字段的计算逻辑。

**计算工具函数**

```python
# services/knowledge/note_utils.py
import re
from typing import Dict
from markdown import markdown
from bs4 import BeautifulSoup

def calculate_derived_fields(content: str) -> Dict[str, any]:
    """从 Markdown 内容计算派生字段

    Args:
        content: Markdown 格式的笔记内容

    Returns:
        {
            "content_plain": str,      # 纯文本内容
            "word_count": int,         # 字数统计
            "read_time_minutes": int   # 预计阅读时间(分钟)
        }
    """
    # 1. 将 Markdown 转换为 HTML
    html = markdown(content, extensions=['extra', 'codehilite'])

    # 2. 提取纯文本
    soup = BeautifulSoup(html, 'html.parser')

    # 移除代码块(不计入字数)
    for code in soup.find_all(['code', 'pre']):
        code.decompose()

    content_plain = soup.get_text(separator=' ', strip=True)

    # 3. 计算字数(中文字符 + 英文单词)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content_plain))
    english_words = len(re.findall(r'\b[a-zA-Z]+\b', content_plain))
    word_count = chinese_chars + english_words

    # 4. 计算阅读时间
    # 假设: 中文 300字/分钟, 英文 200词/分钟
    reading_speed_cn = 300  # 字/分钟
    reading_speed_en = 200  # 词/分钟

    read_time = (chinese_chars / reading_speed_cn) + (english_words / reading_speed_en)
    read_time_minutes = max(1, int(read_time))  # 至少1分钟

    return {
        "content_plain": content_plain,
        "word_count": word_count,
        "read_time_minutes": read_time_minutes
    }


def update_note_derived_fields(note: Note) -> None:
    """更新笔记的派生字段(原地修改)

    Args:
        note: 笔记对象
    """
    derived = calculate_derived_fields(note.content)
    note.content_plain = derived["content_plain"]
    note.word_count = derived["word_count"]
    note.read_time_minutes = derived["read_time_minutes"]
```

**在 Service 层集成**

```python
# services/knowledge/note_service.py
from services.knowledge.note_utils import update_note_derived_fields

class NoteService:
    def create_note(self, title: str, content: str, **kwargs) -> Note:
        """创建笔记(自动计算派生字段)"""
        note = Note(title=title, content=content, **kwargs)

        # 自动计算派生字段
        update_note_derived_fields(note)

        with self.db.get_session() as session:
            session.add(note)
            session.commit()
            session.refresh(note)

        return note

    def update_note(self, note_id: int, **updates) -> Note:
        """更新笔记(自动重新计算派生字段)"""
        with self.db.get_session() as session:
            note = session.get(Note, note_id)
            if not note:
                raise ValueError(f"笔记不存在: {note_id}")

            # 应用更新
            for key, value in updates.items():
                setattr(note, key, value)

            # 如果内容被修改,重新计算派生字段
            if "content" in updates:
                update_note_derived_fields(note)
                note.updated_at = datetime.now()

            session.add(note)
            session.commit()
            session.refresh(note)

        return note
```

**依赖安装**

```bash
pip install markdown beautifulsoup4
```

---

### 2. 向量检索策略

#### 2.1 独立 Collection 设计（推荐）

为知识库创建独立的 ChromaDB Collection，与 RSSHub 路由分离。

```python
# services/knowledge/vector_service.py
import json
from rag_system.vector_store import VectorStore
from rag_system.embedding_model import EmbeddingModel
from pathlib import Path

class KnowledgeVectorStore:
    """知识库向量存储

    为用户笔记创建独立的 ChromaDB Collection，
    与 RSSHub 路由检索分离，避免互相干扰。
    """

    def __init__(self, persist_directory: Path):
        self.embedding_model = EmbeddingModel()  # 复用现有 bge-m3

        # 创建独立的 Collection
        self.vector_store = VectorStore(
            persist_directory=persist_directory,
            collection_name="user_knowledge",  # 独立Collection
            distance_metric="cosine"
        )

    def add_note(self, note_id: int, title: str, content: str, tags: List[str]):
        """向量化笔记并存储

        Args:
            note_id: 笔记ID
            title: 笔记标题
            content: Markdown内容
            tags: 标签列表
        """
        # 1. 构建语义文档（标题 + 内容 + 标签）
        semantic_doc = f"{title}\n\n{content}\n\n标签: {', '.join(tags)}"

        # 2. 向量化
        embedding = self.embedding_model.encode(semantic_doc)

        # 3. 存储到 ChromaDB
        self.vector_store.add_documents(
            route_ids=[f"note_{note_id}"],
            embeddings=[embedding.tolist()],
            semantic_docs=[semantic_doc],
            route_definitions=[{
                "note_id": note_id,
                "title": title,
                "tags": tags,
                "content_preview": content[:200]  # 前200字符预览
            }]
        )

    def search_notes(
        self,
        query: str,
        top_k: int = 5,
        filter_tags: Optional[List[str]] = None
    ) -> List[Tuple[int, float, Dict]]:
        """语义搜索笔记

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            filter_tags: 按标签过滤（可选）

        Returns:
            [(note_id, score, note_metadata), ...]
        """
        # 1. 向量化查询
        query_embedding = self.embedding_model.encode_queries(query)

        # 2. 执行向量检索
        results = self.vector_store.query(
            query_embeddings=[query_embedding.tolist()],
            top_k=top_k
        )

        # 3. 解析结果
        search_results = []
        for i, doc_id in enumerate(results["ids"][0]):
            note_id = int(doc_id.replace("note_", ""))
            distance = results["distances"][0][i]
            score = 1 - distance  # 转换为相似度

            metadata = results["metadatas"][0][i]
            note_def = json.loads(metadata["route_definition"])

            # 标签过滤
            if filter_tags:
                note_tags = set(note_def.get("tags", []))
                if not note_tags.intersection(filter_tags):
                    continue

            search_results.append((note_id, score, note_def))

        return search_results
```

#### 2.2 混合检索策略

结合全文搜索（快速、精确）和语义搜索（智能、模糊），提供最佳搜索体验。

```python
# services/knowledge/search_service.py
from typing import List, Literal
from sqlmodel import select, or_

class KnowledgeSearchService:
    """知识库搜索服务

    混合全文搜索（SQLite FTS5）和语义搜索（RAG），
    提供快速精确 + 智能模糊的双重体验。
    """

    def __init__(self, db: DatabaseConnection, vector_store: KnowledgeVectorStore):
        self.db = db
        self.vector_store = vector_store

    def search(
        self,
        query: str,
        search_type: Literal["fulltext", "semantic", "hybrid"] = "hybrid",
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """统一搜索接口

        Args:
            query: 搜索查询
            search_type: 搜索类型
                - fulltext: 仅全文搜索（快速、精确）
                - semantic: 仅语义搜索（智能、模糊）
                - hybrid: 混合搜索（推荐）
            top_k: 返回结果数量
            filters: 过滤条件 {tags: [...], date_range: {...}}

        Returns:
            搜索结果列表（已去重、排序）
        """
        if search_type == "fulltext":
            return self._fulltext_search(query, top_k, filters)
        elif search_type == "semantic":
            return self._semantic_search(query, top_k, filters)
        else:  # hybrid
            return self._hybrid_search(query, top_k, filters)

    def _fulltext_search(self, query: str, top_k: int, filters: Optional[Dict]) -> List[Dict]:
        """全文搜索（SQLite FTS5）

        利用 SQLite 的全文搜索能力，快速匹配关键词。
        """
        with self.db.get_session() as session:
            # 简化版本：使用 LIKE 查询（生产环境应使用 FTS5）
            statement = select(Note).where(
                or_(
                    Note.title.contains(query),
                    Note.content_plain.contains(query)
                )
            ).limit(top_k)

            # 应用过滤器
            if filters and filters.get("tags"):
                # 需要 JOIN note_tags 表
                pass

            notes = session.exec(statement).all()
            return [self._format_search_result(note, score=1.0, match_type="fulltext") for note in notes]

    def _semantic_search(self, query: str, top_k: int, filters: Optional[Dict]) -> List[Dict]:
        """语义搜索（RAG）

        利用向量检索，理解语义相似性。
        """
        filter_tags = filters.get("tags") if filters else None
        results = self.vector_store.search_notes(query, top_k, filter_tags)

        search_results = []
        with self.db.get_session() as session:
            for note_id, score, metadata in results:
                note = session.get(Note, note_id)
                if note:
                    search_results.append(self._format_search_result(note, score, "semantic"))

        return search_results

    def _hybrid_search(self, query: str, top_k: int, filters: Optional[Dict]) -> List[Dict]:
        """混合搜索

        结合全文和语义，使用加权合并策略。
        """
        # 1. 分别执行两种搜索
        fulltext_results = self._fulltext_search(query, top_k, filters)
        semantic_results = self._semantic_search(query, top_k, filters)

        # 2. 合并去重（按 note_id）
        merged = {}
        for result in fulltext_results:
            note_id = result["id"]
            merged[note_id] = {
                **result,
                "fulltext_score": result["score"],
                "semantic_score": 0.0
            }

        for result in semantic_results:
            note_id = result["id"]
            if note_id in merged:
                merged[note_id]["semantic_score"] = result["score"]
            else:
                merged[note_id] = {
                    **result,
                    "fulltext_score": 0.0,
                    "semantic_score": result["score"]
                }

        # 3. 加权合并分数（全文:语义 = 0.4:0.6）
        for note_id, item in merged.items():
            item["score"] = item["fulltext_score"] * 0.4 + item["semantic_score"] * 0.6

        # 4. 排序并返回
        results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _format_search_result(self, note: Note, score: float, match_type: str) -> Dict:
        """格式化搜索结果"""
        return {
            "id": note.id,
            "title": note.title,
            "content_preview": note.content_plain[:200],
            "score": score,
            "match_type": match_type,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
            "is_favorite": note.is_favorite,
            "word_count": note.word_count
        }
```

---

### 3. 与现有功能的集成

#### 3.1 Panel 结果收藏

在 Panel 查询完成后，前端显示"收藏"按钮。

**依赖说明**

Panel 收藏功能分两个阶段实现:

| 阶段 | 功能 | 依赖 | 说明 |
|------|------|------|------|
| Phase 1 | 数据引用收藏 | 仅需知识库表 | 保存 `reference_id` 和基本元信息 |
| Phase 2+ | 完整快照收藏 | 需要 `PanelSession` 表 | 保存完整布局快照,支持一键恢复 |

**Phase 1 实现 (基础收藏)**

不依赖 `PanelSession` 表,仅保存数据引用:

```python
# api/controllers/bookmark_controller.py (Phase 1)
from fastapi import APIRouter, Depends
from services.knowledge.bookmark_service import BookmarkService

router = APIRouter(prefix="/api/v1/bookmarks", tags=["knowledge"])

@router.post("/panel-result", status_code=201)
def bookmark_panel_result(
    query: str,
    route_id: str,
    title: str,
    description: Optional[str] = None,
    service: BookmarkService = Depends(get_bookmark_service)
):
    """收藏 Panel 查询结果 (Phase 1: 数据引用)

    保存查询信息和路由ID,不依赖 PanelSession 持久化。
    """
    # 构建引用数据(轻量级)
    reference_data = {
        "query": query,
        "route_id": route_id,
        "timestamp": datetime.now().isoformat()
    }

    bookmark = service.create_bookmark(
        type="panel_query",
        reference_id=None,  # Phase 1 无 session_id
        reference_data=json.dumps(reference_data),
        title=title,
        description=description or f"查询: {query}",
        source_url=None
    )

    return bookmark
```

**Phase 2 实现 (完整快照)**

依赖 `PanelSession` 表(持久化计划 Phase 2):

```python
# api/controllers/bookmark_controller.py (Phase 2+)
@router.post("/panel-session", status_code=201)
def bookmark_panel_session(
    session_id: int,
    title: str,
    service: BookmarkService = Depends(get_bookmark_service)
):
    """收藏 Panel 会话 (Phase 2+: 完整快照)

    依赖: PanelSession 表 (持久化计划 Phase 2)
    保存完整的布局快照和数据，方便后续一键恢复。
    """
    # 1. 从 panel_sessions 表加载完整数据
    panel_session = service.get_panel_session(session_id)

    if not panel_session:
        raise HTTPException(status_code=404, detail="Panel 会话不存在")

    # 2. 创建收藏
    bookmark = service.create_bookmark(
        type="panel_session",
        reference_id=session_id,
        reference_data=panel_session.layout_snapshot,  # 完整JSON
        title=title,
        description=f"查询: {panel_session.query}",
        thumbnail_url=None  # 可选：生成缩略图
    )

    return bookmark
```

**前端集成**：

```vue
<!-- frontend/src/features/panel/components/PanelResultActions.vue -->
<template>
  <div class="panel-actions">
    <Button @click="handleBookmark">
      <Bookmark class="w-4 h-4 mr-2" />
      收藏此结果
    </Button>
  </div>
</template>

<script setup lang="ts">
import { usePanelStore } from '@/store/panelStore'
import { useKnowledgeStore } from '@/store/knowledgeStore'

const panelStore = usePanelStore()
const knowledgeStore = useKnowledgeStore()

async function handleBookmark() {
  const sessionId = panelStore.currentSessionId
  const title = `Panel结果 - ${panelStore.lastQuery}`

  await knowledgeStore.bookmarkPanelSession(sessionId, title)
  // 显示成功提示
}
</script>
```

#### 3.2 研究任务关联笔记

在研究过程中，用户可以随时创建笔记记录思考。

```python
# api/controllers/research_controller.py (新增接口)
@router.post("/tasks/{task_id}/notes", status_code=201)
def create_research_note(
    task_id: int,
    note_title: str,
    note_content: str,
    service: KnowledgeService = Depends(get_knowledge_service)
):
    """为研究任务创建关联笔记

    研究过程中的思考可以随时记录为笔记。
    """
    # 1. 创建笔记
    note = service.create_note(
        title=note_title,
        content=note_content
    )

    # 2. 在笔记中插入指向研究任务的链接
    # （使用特殊语法，如 [[research://task_id]]）
    link_text = f"\n\n---\n关联研究任务: [[research://{task_id}]]\n"
    service.append_to_note(note.id, link_text)

    return note
```

**前端集成**：

```vue
<!-- frontend/src/views/ResearchView.vue -->
<template>
  <div class="research-container">
    <!-- 左侧：研究上下文 -->
    <ResearchContextPanel />

    <!-- 右侧：数据面板 + 快速笔记按钮 -->
    <ResearchDataPanel>
      <Button @click="showNoteDialog = true">
        <NotebookPen class="w-4 h-4 mr-2" />
        记录思考
      </Button>
    </ResearchDataPanel>

    <!-- 笔记对话框 -->
    <Dialog v-model:open="showNoteDialog">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>记录研究思考</DialogTitle>
        </DialogHeader>
        <Textarea v-model="noteContent" placeholder="记录你的想法..." />
        <Button @click="handleSaveNote">保存笔记</Button>
      </DialogContent>
    </Dialog>
  </div>
</template>
```

#### 3.3 在研究模式中引用知识库

LangGraph Agents 新增工具 `search_knowledge_base`，可以在研究过程中检索用户知识库。

**服务层依赖注入设计**

为确保测试性和依赖管理,使用依赖注入模式:

```python
# services/knowledge/dependencies.py
from functools import lru_cache
from services.knowledge.search_service import KnowledgeSearchService
from services.knowledge.vector_service import KnowledgeVectorStore
from services.database.connection import get_database
from pathlib import Path

@lru_cache()
def get_knowledge_vector_store() -> KnowledgeVectorStore:
    """获取知识库向量存储单例"""
    persist_dir = Path("data/chroma/user_knowledge")
    return KnowledgeVectorStore(persist_directory=persist_dir)

@lru_cache()
def get_knowledge_search_service() -> KnowledgeSearchService:
    """获取知识库搜索服务单例"""
    db = get_database()
    vector_store = get_knowledge_vector_store()
    return KnowledgeSearchService(db=db, vector_store=vector_store)
```

**LangGraph 工具实现**

```python
# services/langgraph_agents/tools/knowledge_tool.py
from services.knowledge.dependencies import get_knowledge_search_service

@register_tool("search_knowledge_base")
def search_knowledge_base(query: str, max_results: int = 3) -> str:
    """搜索用户知识库

    在用户的私有笔记中搜索相关内容，用于辅助研究。

    Args:
        query: 搜索关键词（自然语言）
        max_results: 最多返回结果数量

    Returns:
        搜索结果摘要（Markdown格式）
    """
    # 通过依赖注入获取服务实例
    search_service = get_knowledge_search_service()

    # 执行混合搜索
    results = search_service.search(
        query=query,
        search_type="hybrid",
        top_k=max_results
    )

    # 格式化为 Markdown
    if not results:
        return f"未在知识库中找到与 '{query}' 相关的笔记。"

    output = f"## 知识库搜索结果（共{len(results)}条）\n\n"
    for i, result in enumerate(results, 1):
        output += f"### {i}. {result['title']} (相似度: {result['score']:.2f})\n"
        output += f"{result['content_preview']}...\n\n"
        output += f"*创建于: {result['created_at']}*\n\n"

    return output
```

**API 控制器依赖注入**

```python
# api/controllers/knowledge_controller.py
from fastapi import Depends
from services.knowledge.dependencies import get_knowledge_search_service
from services.knowledge.note_service import NoteService
from services.database.connection import get_database

def get_note_service(db = Depends(get_database)) -> NoteService:
    """获取笔记服务实例"""
    return NoteService(db=db)

def get_bookmark_service(db = Depends(get_database)):
    """获取收藏服务实例"""
    from services.knowledge.bookmark_service import BookmarkService
    return BookmarkService(db=db)

@router.post("/search")
def search_knowledge(
    data: SearchRequest,
    service: KnowledgeSearchService = Depends(get_knowledge_search_service)
):
    """搜索知识库(依赖注入)"""
    results = service.search(
        query=data.query,
        search_type=data.search_type,
        top_k=data.top_k,
        filters=data.filters
    )
    return {
        "query": data.query,
        "total": len(results),
        "results": results
    }
```

**在 LangGraph Planner 中的使用**：

```python
# PlannerAgent 的 Prompt 示例
"""
你是一个研究规划助手。用户提出了以下研究问题：

{original_query}

你可以使用以下工具：
1. search_knowledge_base(query) - 搜索用户的私有笔记
2. fetch_public_data(query) - 获取公共互联网数据（B站、知乎等）
3. emit_panel_preview(query) - 向前端推送数据卡片

当前已收集的数据：
{data_stash_summary}

请决定下一步应该做什么。如果用户之前有相关笔记，优先检索知识库。
"""
```

#### 3.4 智能推荐

在 Panel 查询时，根据语义相似度推荐相关笔记。

```python
# services/panel/recommendation_service.py
class PanelRecommendationService:
    """面板推荐服务

    在 Panel 查询时推荐相关的笔记和收藏。
    """

    def __init__(self, knowledge_search: KnowledgeSearchService):
        self.knowledge_search = knowledge_search

    def get_recommendations(self, query: str, top_k: int = 3) -> Dict:
        """获取推荐内容

        Args:
            query: 用户查询
            top_k: 推荐数量

        Returns:
            {
                "related_notes": [...],
                "related_bookmarks": [...]
            }
        """
        # 1. 搜索相关笔记
        related_notes = self.knowledge_search.search(
            query=query,
            search_type="semantic",
            top_k=top_k
        )

        # 2. 搜索相关收藏（简化：按标签匹配）
        # TODO: 实现 BookmarkSearchService

        return {
            "related_notes": related_notes,
            "related_bookmarks": []
        }
```

**前端集成**：

```vue
<!-- frontend/src/features/panel/components/RecommendationSidebar.vue -->
<template>
  <aside class="recommendation-sidebar">
    <h3>相关笔记</h3>
    <div v-if="relatedNotes.length > 0">
      <Card v-for="note in relatedNotes" :key="note.id">
        <CardHeader>
          <CardTitle class="text-sm">{{ note.title }}</CardTitle>
        </CardHeader>
        <CardContent class="text-xs text-muted-foreground">
          {{ note.content_preview }}
        </CardContent>
        <CardFooter>
          <Button variant="ghost" size="sm" @click="openNote(note.id)">
            查看笔记
          </Button>
        </CardFooter>
      </Card>
    </div>
    <div v-else class="text-sm text-muted-foreground">
      暂无相关笔记
    </div>
  </aside>
</template>
```

---

### 4. API 设计

#### 4.1 RESTful 接口规范

```python
# api/controllers/knowledge_controller.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from services.knowledge.note_service import NoteService
from services.knowledge.search_service import KnowledgeSearchService
from api.schemas.knowledge import (
    NoteCreate, NoteUpdate, NoteResponse,
    TagCreate, TagResponse,
    BookmarkCreate, BookmarkResponse,
    SearchRequest, SearchResponse
)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

# ========== 笔记管理 ==========

@router.get("/notes", response_model=List[NoteResponse])
def list_notes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tag_ids: Optional[List[int]] = Query(None),
    is_favorite: Optional[bool] = None,
    is_archived: Optional[bool] = None,
    parent_id: Optional[int] = None,
    service: NoteService = Depends(get_note_service)
):
    """列出笔记

    支持按标签、收藏状态、归档状态、父笔记筛选。
    """
    return service.list_notes(
        limit=limit,
        offset=offset,
        tag_ids=tag_ids,
        is_favorite=is_favorite,
        is_archived=is_archived,
        parent_id=parent_id
    )


@router.post("/notes", response_model=NoteResponse, status_code=201)
def create_note(
    data: NoteCreate,
    service: NoteService = Depends(get_note_service)
):
    """创建笔记"""
    return service.create_note(
        title=data.title,
        content=data.content,
        parent_id=data.parent_id,
        tag_ids=data.tag_ids
    )


@router.get("/notes/{note_id}", response_model=NoteResponse)
def get_note(
    note_id: int,
    service: NoteService = Depends(get_note_service)
):
    """获取笔记详情"""
    note = service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return note


@router.patch("/notes/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: int,
    data: NoteUpdate,
    service: NoteService = Depends(get_note_service)
):
    """更新笔记"""
    return service.update_note(note_id, **data.dict(exclude_unset=True))


@router.delete("/notes/{note_id}")
def delete_note(
    note_id: int,
    service: NoteService = Depends(get_note_service)
):
    """删除笔记"""
    service.delete_note(note_id)
    return {"success": True, "message": "笔记已删除"}


# ========== 标签管理 ==========

@router.get("/tags", response_model=List[TagResponse])
def list_tags(service: NoteService = Depends(get_note_service)):
    """列出所有标签"""
    return service.list_tags()


@router.post("/tags", response_model=TagResponse, status_code=201)
def create_tag(
    data: TagCreate,
    service: NoteService = Depends(get_note_service)
):
    """创建标签"""
    return service.create_tag(**data.dict())


@router.patch("/tags/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: int,
    data: TagCreate,
    service: NoteService = Depends(get_note_service)
):
    """更新标签"""
    return service.update_tag(tag_id, **data.dict(exclude_unset=True))


@router.delete("/tags/{tag_id}")
def delete_tag(
    tag_id: int,
    service: NoteService = Depends(get_note_service)
):
    """删除标签"""
    service.delete_tag(tag_id)
    return {"success": True, "message": "标签已删除"}


# ========== 收藏管理 ==========

@router.get("/bookmarks", response_model=List[BookmarkResponse])
def list_bookmarks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    type: Optional[str] = None,
    service: BookmarkService = Depends(get_bookmark_service)
):
    """列出收藏

    支持按类型筛选（panel_session/research_task/rss_item/web_link）。
    """
    return service.list_bookmarks(limit=limit, offset=offset, type=type)


@router.post("/bookmarks", response_model=BookmarkResponse, status_code=201)
def create_bookmark(
    data: BookmarkCreate,
    service: BookmarkService = Depends(get_bookmark_service)
):
    """创建收藏"""
    return service.create_bookmark(**data.dict())


@router.delete("/bookmarks/{bookmark_id}")
def delete_bookmark(
    bookmark_id: int,
    service: BookmarkService = Depends(get_bookmark_service)
):
    """删除收藏"""
    service.delete_bookmark(bookmark_id)
    return {"success": True, "message": "收藏已删除"}


# ========== 知识检索 ==========

@router.post("/search", response_model=SearchResponse)
def search_knowledge(
    data: SearchRequest,
    service: KnowledgeSearchService = Depends(get_search_service)
):
    """搜索知识库

    支持全文搜索、语义搜索、混合搜索。
    """
    results = service.search(
        query=data.query,
        search_type=data.search_type,
        top_k=data.top_k,
        filters=data.filters
    )

    return {
        "query": data.query,
        "search_type": data.search_type,
        "total": len(results),
        "results": results
    }


# ========== 笔记关联 ==========

@router.get("/notes/{note_id}/links")
def get_note_links(
    note_id: int,
    service: NoteService = Depends(get_note_service)
):
    """获取笔记的所有链接（双向）

    返回：
    - outgoing: 此笔记链接到其他笔记
    - incoming: 其他笔记链接到此笔记（反向链接）
    """
    return service.get_note_links(note_id)


@router.post("/notes/{note_id}/links")
def create_note_link(
    note_id: int,
    target_note_id: int,
    link_type: str = "mention",
    service: NoteService = Depends(get_note_service)
):
    """创建笔记链接"""
    return service.create_note_link(
        source_note_id=note_id,
        target_note_id=target_note_id,
        link_type=link_type
    )


# ========== 知识图谱 ==========

@router.get("/graph")
def get_knowledge_graph(
    service: KnowledgeGraphService = Depends(get_graph_service)
):
    """获取知识图谱数据

    返回节点（笔记）和边（链接）的图数据结构，
    供前端可视化（如使用 D3.js/Cytoscape.js）。
    """
    return service.get_graph_data()
```

---

### 5. 前端设计

#### 5.1 路由设计

```typescript
// frontend/src/router/index.ts
const routes = [
  // ... 现有路由 ...

  // 知识库路由
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/KnowledgeView.vue'),
    children: [
      {
        path: 'notes',
        name: 'Notes',
        component: () => import('@/views/knowledge/NotesView.vue')
      },
      {
        path: 'notes/:id',
        name: 'NoteDetail',
        component: () => import('@/views/knowledge/NoteDetailView.vue')
      },
      {
        path: 'bookmarks',
        name: 'Bookmarks',
        component: () => import('@/views/knowledge/BookmarksView.vue')
      },
      {
        path: 'graph',
        name: 'KnowledgeGraph',
        component: () => import('@/views/knowledge/GraphView.vue')
      }
    ]
  }
]
```

#### 5.2 核心组件设计

**1. 笔记编辑器组件**

```vue
<!-- frontend/src/components/knowledge/NoteEditor.vue -->
<template>
  <div class="note-editor">
    <!-- 工具栏 -->
    <div class="editor-toolbar">
      <Button variant="ghost" size="sm" @click="toggleBold">
        <Bold class="w-4 h-4" />
      </Button>
      <Button variant="ghost" size="sm" @click="toggleItalic">
        <Italic class="w-4 h-4" />
      </Button>
      <Button variant="ghost" size="sm" @click="insertCodeBlock">
        <Code class="w-4 h-4" />
      </Button>
      <Button variant="ghost" size="sm" @click="insertImage">
        <Image class="w-4 h-4" />
      </Button>
      <Button variant="ghost" size="sm" @click="insertLink">
        <Link class="w-4 h-4" />
      </Button>
    </div>

    <!-- 编辑区域（使用 vditor 或 tiptap） -->
    <div ref="editorContainer" class="editor-content"></div>

    <!-- 状态栏 -->
    <div class="editor-statusbar">
      <span>字数: {{ wordCount }}</span>
      <span>行数: {{ lineCount }}</span>
      <span>最后保存: {{ lastSavedAt }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import Vditor from 'vditor'
import 'vditor/dist/index.css'

const props = defineProps<{
  initialContent: string
}>()

const emit = defineEmits<{
  (e: 'update:content', value: string): void
  (e: 'save'): void
}>()

const editorContainer = ref<HTMLElement>()
let vditor: Vditor

onMounted(() => {
  vditor = new Vditor(editorContainer.value!, {
    value: props.initialContent,
    mode: 'wysiwyg',  // 或 'ir'（即时渲染）
    cache: {
      enable: false
    },
    input: (value) => {
      emit('update:content', value)
    },
    toolbar: [
      'emoji',
      'headings',
      'bold',
      'italic',
      'strike',
      '|',
      'line',
      'quote',
      'list',
      'ordered-list',
      'check',
      'outdent',
      'indent',
      '|',
      'code',
      'inline-code',
      'insert-before',
      'insert-after',
      '|',
      'upload',
      'link',
      'table',
      '|',
      'undo',
      'redo',
      '|',
      'fullscreen',
      'preview',
      'help'
    ]
  })
})

// 自动保存
watch(
  () => props.initialContent,
  (newValue) => {
    if (vditor && vditor.getValue() !== newValue) {
      vditor.setValue(newValue)
    }
  }
)
</script>
```

**2. 笔记列表组件**

```vue
<!-- frontend/src/components/knowledge/NotesList.vue -->
<template>
  <div class="notes-list">
    <!-- 搜索框 -->
    <div class="search-bar">
      <Input
        v-model="searchQuery"
        placeholder="搜索笔记..."
        @update:model-value="handleSearch"
      >
        <template #prefix>
          <Search class="w-4 h-4" />
        </template>
      </Input>
    </div>

    <!-- 标签过滤 -->
    <div class="tag-filters">
      <Badge
        v-for="tag in selectedTags"
        :key="tag.id"
        :style="{ backgroundColor: tag.color }"
        @click="removeTagFilter(tag.id)"
      >
        {{ tag.name }}
        <X class="w-3 h-3 ml-1" />
      </Badge>
    </div>

    <!-- 笔记列表 -->
    <div class="notes-items">
      <Card
        v-for="note in filteredNotes"
        :key="note.id"
        @click="handleNoteClick(note.id)"
        class="cursor-pointer hover:border-primary transition-colors"
      >
        <CardHeader>
          <CardTitle class="flex items-center justify-between">
            {{ note.title }}
            <Star v-if="note.is_favorite" class="w-4 h-4 text-yellow-500" />
          </CardTitle>
          <CardDescription>
            {{ note.content_preview }}
          </CardDescription>
        </CardHeader>
        <CardFooter class="text-xs text-muted-foreground">
          <Calendar class="w-3 h-3 mr-1" />
          {{ formatDate(note.updated_at) }}
          <span class="ml-4">{{ note.word_count }} 字</span>
        </CardFooter>
      </Card>
    </div>

    <!-- 空状态 -->
    <div v-if="filteredNotes.length === 0" class="empty-state">
      <FileText class="w-12 h-12 text-muted-foreground" />
      <p class="text-muted-foreground mt-2">暂无笔记</p>
      <Button @click="handleCreateNote">创建第一篇笔记</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useKnowledgeStore } from '@/store/knowledgeStore'

const router = useRouter()
const knowledgeStore = useKnowledgeStore()

const searchQuery = ref('')
const selectedTags = ref([])

const filteredNotes = computed(() => {
  return knowledgeStore.notes.filter(note => {
    // 搜索过滤
    if (searchQuery.value && !note.title.includes(searchQuery.value)) {
      return false
    }
    // 标签过滤
    if (selectedTags.value.length > 0) {
      // TODO: 实现标签过滤逻辑
    }
    return true
  })
})

function handleNoteClick(noteId: number) {
  router.push({ name: 'NoteDetail', params: { id: noteId } })
}

function handleCreateNote() {
  router.push({ name: 'NoteDetail', params: { id: 'new' } })
}
</script>
```

**3. 知识图谱组件**

```vue
<!-- frontend/src/components/knowledge/KnowledgeGraph.vue -->
<template>
  <div class="knowledge-graph">
    <div ref="graphContainer" class="graph-container"></div>

    <!-- 图谱控制 -->
    <div class="graph-controls">
      <Button @click="resetView">重置视图</Button>
      <Button @click="togglePhysics">{{ physicsEnabled ? '暂停' : '启动' }}物理引擎</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import cytoscape from 'cytoscape'
import { useKnowledgeStore } from '@/store/knowledgeStore'

const knowledgeStore = useKnowledgeStore()
const graphContainer = ref<HTMLElement>()
let cy: cytoscape.Core

onMounted(async () => {
  // 1. 加载图谱数据
  const graphData = await knowledgeStore.loadGraphData()

  // 2. 初始化 Cytoscape
  cy = cytoscape({
    container: graphContainer.value,
    elements: graphData.elements,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#666',
          'label': 'data(label)',
          'width': 40,
          'height': 40
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#ccc',
          'target-arrow-color': '#ccc',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier'
        }
      }
    ],
    layout: {
      name: 'cose',  // 力导向布局
      animate: true
    }
  })

  // 3. 交互事件
  cy.on('tap', 'node', (evt) => {
    const node = evt.target
    const noteId = node.data('id')
    // 跳转到笔记详情
    router.push({ name: 'NoteDetail', params: { id: noteId } })
  })
})

function resetView() {
  cy.fit()
  cy.center()
}

function togglePhysics() {
  // TODO: 实现物理引擎开关
}
</script>
```

---

## 实施路线图

### Phase 1: 基础MVP（2-3周）

**目标**：实现核心笔记和收藏功能

**任务清单**：
- [ ] 数据模型设计与数据库迁移（Note/Tag/Bookmark）
- [ ] 笔记CRUD服务层（NoteService）
- [ ] 标签CRUD服务层（TagService）
- [ ] 收藏CRUD服务层（BookmarkService）
- [ ] RESTful API接口实现
- [ ] 前端笔记编辑器集成（vditor）
- [ ] 前端笔记列表/详情页面
- [ ] 前端收藏页面
- [ ] Panel收藏按钮集成
- [ ] 单元测试和集成测试

**验收标准**：
- ✅ 可以创建/编辑/删除笔记
- ✅ 可以为笔记添加标签
- ✅ 可以收藏Panel结果
- ✅ 可以查看收藏列表并恢复

---

### Phase 2: 知识检索（2周）

**目标**：实现全文搜索和语义搜索

**任务清单**：
- [ ] SQLite FTS5全文搜索配置
- [ ] 知识库独立ChromaDB Collection
- [ ] KnowledgeVectorStore实现
- [ ] KnowledgeSearchService实现（混合检索）
- [ ] 笔记自动向量化（创建/更新时触发）
- [ ] 搜索API接口
- [ ] 前端搜索界面
- [ ] 搜索结果高亮和预览

**验收标准**：
- ✅ 全文搜索快速准确
- ✅ 语义搜索能理解同义词/近义词
- ✅ 混合搜索结果排序合理

---

### Phase 3: 智能关联（2-3周）

**目标**：实现双向链接和LangGraph集成

**任务清单**：
- [ ] 双向链接解析器（`[[笔记名称]]`语法）
- [ ] NoteLink自动创建
- [ ] 反向链接展示
- [ ] LangGraph工具 `search_knowledge_base`
- [ ] 研究任务关联笔记功能
- [ ] Panel查询推荐笔记功能
- [ ] 前端双向链接UI

**验收标准**：
- ✅ 笔记中可以使用`[[]]`语法链接其他笔记
- ✅ 笔记详情页显示反向链接列表
- ✅ LangGraph研究时可以检索知识库
- ✅ Panel查询时显示相关笔记推荐

---

### Phase 4: 知识图谱（1-2周）

**目标**：可视化笔记关联关系

**任务清单**：
- [ ] KnowledgeGraphService实现
- [ ] 图谱数据API接口
- [ ] 前端图谱可视化（Cytoscape.js）
- [ ] 图谱交互（缩放/拖拽/点击跳转）
- [ ] 图谱过滤（按标签/时间）

**验收标准**：
- ✅ 可以查看全局知识图谱
- ✅ 节点和边清晰可辨
- ✅ 点击节点跳转到笔记详情

---

### Phase 5: 高级功能（可选，按需实施）

**可选功能列表**：
- [ ] 笔记版本历史和回滚
- [ ] 笔记协作编辑（多人实时）
- [ ] 笔记导入/导出（Markdown/HTML/PDF）
- [ ] 笔记加密（端到端加密）
- [ ] AI辅助写作（续写/润色/总结）
- [ ] 笔记发布/分享（生成公开链接）
- [ ] WebDAV/Git同步
- [ ] 移动端适配（PWA）

---

## 技术栈总结

| 层级 | 技术栈 | 说明 |
|------|--------|------|
| **数据库** | SQLite + SQLModel + Alembic | 与现有持久化方案一致 |
| **向量存储** | ChromaDB（独立Collection `user_knowledge`） | 复用现有RAG基础设施 |
| **Embedding** | bge-m3（1024维） | 复用现有模型 |
| **全文搜索** | SQLite FTS5 | 原生支持，无需额外依赖 |
| **后端框架** | FastAPI + Service层 | 符合现有架构 |
| **前端框架** | Vue 3 + TypeScript + shadcn-vue | 符合现有技术栈 |
| **Markdown编辑器** | Vditor（推荐）或 Tiptap | Vditor更轻量，Tiptap更灵活 |
| **图谱可视化** | Cytoscape.js 或 D3.js | Cytoscape更易用，D3更灵活 |

---

## 重要决策记录

### 决策1: 为什么选择Markdown而非富文本编辑器？

**理由**：
1. **开放格式** - Markdown是纯文本，不被特定平台绑定
2. **版本控制友好** - 可以用Git管理笔记历史
3. **技术用户友好** - 支持代码块、公式、图表
4. **导入导出容易** - 几乎所有笔记工具都支持Markdown

**参考案例**：Obsidian、Logseq、Typora

---

### 决策2: 为什么创建独立的ChromaDB Collection？

**理由**：
1. **避免干扰** - RSSHub路由检索和笔记检索的语义空间不同
2. **独立调优** - 可以为笔记检索设置不同的相似度阈值
3. **便于管理** - 可以单独清空/重建笔记向量，不影响RSSHub

**替代方案**：统一向量空间（不推荐，会降低检索准确性）

---

### 决策3: 为什么用混合检索而非单纯语义搜索？

**理由**：
1. **互补优势** - 全文搜索快速精确，语义搜索智能模糊
2. **覆盖不同场景** - 用户可能记得精确关键词，也可能只记得大概意思
3. **最佳实践** - 主流知识库产品（Notion、Obsidian）都采用混合检索

**权重配置**：全文:语义 = 0.4:0.6（可根据实际效果调整）

---

### 决策4: 为什么支持双向链接而非单向引用？

**理由**：
1. **知识网络** - 双向链接更符合人脑联想和知识涌现
2. **发现隐藏关联** - 反向链接能发现意想不到的知识关联
3. **用户期待** - 受Roam Research影响，用户已习惯双向链接

**参考案例**：Roam Research、Obsidian、Logseq

---

## 风险与应对

### 风险1: 向量化性能问题

**影响**：笔记数量多（>1000篇）时，向量化耗时长
**概率**：中
**应对**：
- 异步向量化（后台任务队列）
- 增量更新（只向量化修改部分）
- 批量向量化（定时批处理）

---

### 风险2: 全文搜索中文分词不准确

**影响**：中文搜索结果不理想
**概率**：中
**应对**：
- 使用jieba分词预处理content_plain
- 配置SQLite FTS5的tokenizer
- 如果仍不理想，考虑引入Elasticsearch（后续）

---

### 风险3: 前端编辑器性能问题

**影响**：大文档（>10000字）编辑卡顿
**概率**：低
**应对**：
- 选择性能优异的编辑器（Vditor/Tiptap）
- 延迟加载（虚拟滚动）
- 警告用户拆分大文档

---

### 风险4: 双向链接解析冲突

**影响**：`[[]]`语法与Markdown代码块冲突
**概率**：低
**应对**：
- 在代码块内禁用链接解析
- 使用转义语法`\[\[不是链接\]\]`

---

## 参考资料

- [Obsidian 官方文档](https://obsidian.md/)
- [Logseq 设计理念](https://logseq.com/)
- [Roam Research Whitepaper](https://roamresearch.com/)
- [Vditor 文档](https://b3log.org/vditor/)
- [Cytoscape.js 示例](https://js.cytoscape.org/)
- [SQLite FTS5 文档](https://www.sqlite.org/fts5.html)

---

**方案制定时间**：2025-11-13
**预计实施周期**：Phase 1-3 共 6-8 周，Phase 4-5 可选

---

## 修订历史

### v1.1 (2025-11-13)

**修复问题**：

1. **P0 - 安全修复**：
   - 移除 `eval()` 调用,替换为 `json.loads()` (services/knowledge/vector_service.py:334)
   - 添加 `import json` 导入语句

2. **P0 - 数据库集成**：
   - 新增 "1.3 数据库集成" 章节
   - 说明如何集成到现有 `services/database/models.py`
   - 定义 Alembic 迁移工作流
   - 明确 `user_id` 在 Stage 4 之前的处理策略 (NULL = 单用户模式)
   - 添加依赖关系管理表格和 Phase 实施顺序

3. **P1 - 派生字段计算**：
   - 新增 "1.4 派生字段自动计算" 章节
   - 定义 `calculate_derived_fields()` 函数
   - 说明在 Service 层自动调用的机制
   - 添加依赖包 (markdown, beautifulsoup4)

4. **P1 - Bookmark 依赖关系**：
   - 在 "3.1 Panel 结果收藏" 添加依赖说明表格
   - 区分 Phase 1 (数据引用) 和 Phase 2+ (完整快照) 实现
   - Phase 1 不依赖 PanelSession,可立即开发
   - Phase 2+ 依赖持久化计划 Phase 2

5. **P1 - 服务层依赖注入**：
   - 在 "3.3 在研究模式中引用知识库" 添加 DI 设计
   - 新增 `services/knowledge/dependencies.py` 模块
   - 使用 `@lru_cache()` 实现服务单例
   - 为 API 控制器和 LangGraph 工具提供统一的 DI 模式

**文档版本**：v1.1 (基于 Codex 审查反馈修正)
