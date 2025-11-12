# Omnibox（万界）

**一句话介绍**：用自然语言获取和可视化网络数据，无需记忆复杂 API。

---

## ✨ 它能做什么？

### 示例 1：查看 GitHub 热门项目

**💬 你说**：
```
我想看看 GitHub 今日热门项目
```

**📊 Omnibox 返回**：
- **热门仓库列表**：项目名称、描述、Star 数、主要语言
- **趋势图表**：Star 数随排名的分布
- **统计摘要**：最热门语言、最高 Star 数
- **数据量**：25 个热门项目

### 示例 2：追踪 B 站动态

**💬 你说**：
```
帮我看看 B 站热搜榜
```

**📊 Omnibox 返回**：
- **热搜列表**：热搜标题、热度值、分类
- **热度统计**：平均热度、最高热度
- **实时更新**：自动缓存，避免频繁请求

### 示例 3：关注虎扑论坛

**💬 你说**：
```
虎扑步行街最近在聊什么
```

**📊 Omnibox 返回**：
- **帖子列表**：标题、作者、回复数、发布时间
- **热度指标**：总回复数、平均回复数
- **内容清洗**：自动过滤 HTML 标签和无用字符

---

## 🎯 核心特性

### 🗣️ 智能理解需求

不需要记住复杂的 API 路径，用自然语言描述想看什么：

- ❌ **不用这样**：`GET /api/rsshub/github/trending?language=python&since=daily`
- ✅ **只需说**："查看 Python 今日热门项目"

Omnibox 会自动：
- 理解你的意图（查看热门项目）
- 识别数据源（GitHub）
- 提取参数（语言=Python，时间=今日）
- 调用正确的 RSSHub 路由

### 📊 自适应可视化

根据数据特点自动选择最佳展示方式：

| 数据特征 | 自动选择 | 示例 |
|---------|---------|------|
| 数据量少（<3条） | 只显示列表 | GitHub 今日只有 2 个新项目 |
| 有数值趋势 | 列表 + 折线图 | GitHub 热门项目的 Star 数分布 |
| 有统计指标 | 列表 + 统计卡片 | B 站 UP 主的粉丝数、视频总数 |
| 需要详细信息 | 卡片式展示 | 单个项目的详细介绍 |

**智能决策原理**：
- 基于组件清单（Manifest）声明每个数据源支持的可视化组件
- 根据运行时上下文（数据量、可用指标）动态选择组件
- 只生成需要的数据，避免无效计算

### 🌐 多数据源支持

整合主流平台数据，基于 [RSSHub](https://docs.rsshub.app/)：

- **开发者平台**：GitHub、GitLab、Stack Overflow
- **社交媒体**：微博、知乎、豆瓣
- **视频平台**：B 站、YouTube、抖音
- **新闻资讯**：虎扑、少数派、V2EX
- **更多**：支持 300+ 数据源和路由

### 🔄 智能缓存

- **自动缓存**：相同查询 5 分钟内直接返回缓存
- **后台更新**：缓存过期时自动刷新
- **降级策略**：RSSHub 服务不可用时切换到备用源

---

## 🚀 快速开始（5 分钟上手）

### 环境要求

- Python 3.10+
- Docker & Docker Compose
- OpenAI API Key（或兼容的 API）

### 第一步：克隆项目

```bash
git clone https://github.com/hc-tec/omnibox.git
cd omnibox
```

### 第二步：安装依赖

```bash
# 使用国内镜像加速（可选）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或使用默认源
pip install -r requirements.txt
```

### 第三步：启动 RSSHub 服务

```bash
cd deploy
docker-compose up -d

# 验证服务启动
docker-compose ps
# 应该看到 rsshub、redis、browserless 三个服务都在运行
```

### 第四步：配置 API 密钥

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，填写必要的配置
# 最重要的是 OPENAI_API_KEY
```

`.env` 示例配置：
```bash
# OpenAI API 配置
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1  # 或其他兼容服务

# RSSHub 配置（通常使用默认值即可）
RSSHUB_BASE_URL=http://localhost:1200
# 数据查询策略（1=仅执行 primary route）
DATA_QUERY_SINGLE_ROUTE=1
`

### 第五步：启动 Electron 桌面端

> 桌面外壳位于 `frontend/`，需要在本地启动 Vite Dev Server 后再启动 Electron。

```bash
cd frontend
npm install
npm run electron:dev
```

- `npm run electron:dev` 会同时启动 Vite (`npm run dev`) 与 Electron (`npm run electron:start`)，预加载脚本通过 `window.desktop` 注入窗口控制能力。
- 打包发行版时使用 `npm run electron:build`。该命令会先运行 `npm run build` 产出前端静态资源，再自动复制 `electron/preload.cjs` 到 `dist-electron/electron`，无需手动处理 preload 路径。

### 第六步：构建知识库

```bash
cd rag_system
python quick_start.py

# 这一步会：
# 1. 下载 RSSHub 路由文档
# 2. 使用 bge-m3 模型构建向量索引
# 3. 存储到 ChromaDB（大约需要 2-3 分钟）
```

### 第六步：运行示例

```bash
cd ../orchestrator
python example_usage.py

# 你会看到类似这样的输出：
# ✅ 查询成功！
# 📊 获取了 25 条数据
# 🎨 生成了 2 个可视化组件（ListPanel + LineChart）
```

---

## 💡 使用示例

### 基础用法

```python
from orchestrator.chat_orchestrator import ChatOrchestrator

# 初始化
orchestrator = ChatOrchestrator()

# 查询数据
result = orchestrator.process_query("我想看看 GitHub 今日热门项目")

# 查看结果
print(result["message"])  # 用户友好的消息
print(result["data"])     # 结构化数据
print(result["panels"])   # 可视化组件配置
```

### 输出示例

```python
{
  "status": "success",
  "message": "为您找到了 GitHub 热门项目（25条数据）",
  "data": {
    "records": [
      {
        "title": "microsoft/TypeChat",
        "description": "TypeChat is a library that makes it easy to build natural language interfaces using types.",
        "link": "https://github.com/microsoft/TypeChat",
        "stars": 8234,
        "language": "TypeScript"
      },
      # ... 更多数据
    ],
    "stats": {
      "total": 25,
      "top_language": "Python",
      "top_stars": 8234,
      "datasource": "GitHub"
    }
  },
  "panels": {
    "ui_blocks": [
      {
        "component": "ListPanel",
        "props": {
          "title_field": "title",
          "link_field": "link",
          "description_field": "description",
          "meta_fields": ["stars", "language"]
        }
      },
      {
        "component": "LineChart",
        "props": {
          "x_field": "rank",
          "y_field": "stars",
          "title": "Star 数分布"
        }
      }
    ]
  }
}
```

### 高级用法：自定义组件选择

```python
from services.chat_service import ChatService
from services.panel.component_planner import ComponentPlannerConfig

# 自定义组件选择策略
config = ComponentPlannerConfig(
    max_components=3,              # 最多生成 3 个组件
    preferred_components=["LineChart"],  # 优先生成图表
    allow_optional=True            # 允许可选组件
)

# 使用自定义配置
chat_service = ChatService(
    data_query_service=...,
    component_planner_config=config
)
```

### 使用缓存

```python
from services.cache_service import CacheService

# 查询会自动使用缓存
result1 = orchestrator.process_query("GitHub 热门项目")  # 首次查询，调用 API
result2 = orchestrator.process_query("GitHub 热门项目")  # 5分钟内，返回缓存

# 手动清除缓存
cache = CacheService()
cache.clear("github_trending")
```

---

## 🔧 技术架构

<details>
<summary><b>点击展开查看技术实现细节</b></summary>

### 工作流程

```
用户输入 "GitHub 热门项目"
    ↓
┌─────────────────────────────────────┐
│  1. RAG 检索                         │
│  - 使用 bge-m3 模型理解用户意图      │
│  - 在 ChromaDB 中检索相关路由        │
│  - 返回: /github/trending/daily      │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  2. 参数提取                         │
│  - LLM 解析自然语言中的参数         │
│  - 提取: language=None, since=daily  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  3. 数据获取                         │
│  - 调用 RSSHub API                  │
│  - 获取 RSS/JSON 数据               │
│  - 自动缓存结果                     │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  4. 组件规划                         │
│  - 分析数据特征（数量、指标）        │
│  - 查询组件清单（Manifest）         │
│  - 决定生成哪些组件                 │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  5. 数据适配                         │
│  - 路由适配器转换数据格式            │
│  - 生成可视化组件配置                │
│  - Pydantic 校验数据契约             │
└─────────────────────────────────────┘
    ↓
返回结构化结果给前端
```

### 核心技术栈

| 模块 | 技术选型 | 说明 |
|------|---------|------|
| **向量检索** | bge-m3 + ChromaDB | 多语言语义检索模型 |
| **LLM 理解** | OpenAI API / 兼容服务 | 参数提取和意图理解 |
| **数据源** | RSSHub | 统一的 RSS 数据接口 |
| **缓存** | Redis / 本地缓存 | 避免重复请求 |
| **数据校验** | Pydantic | 前后端契约一致性 |
| **组件规划** | 自研 Component Planner | 自适应可视化决策 |

### 关键设计模式

#### 1. 路由适配器模式

每个数据源都有对应的适配器，负责：
- 将 RSSHub 原始数据转换为标准格式
- 声明支持的可视化组件（Manifest）
- 根据运行时上下文生成组件

```python
@route_adapter("/github/trending", manifest=GITHUB_MANIFEST)
def github_trending_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    # 数据转换逻辑
    normalized = [normalize_record(r) for r in records]

    # 根据 context 决定生成哪些组件
    block_plans = []
    if context.wants("ListPanel"):
        block_plans.append(create_list_panel(...))
    if context.wants("LineChart"):
        block_plans.append(create_line_chart(...))

    return RouteAdapterResult(
        records=normalized,
        block_plans=block_plans,
        stats={"total": len(normalized)}
    )
```

#### 2. 组件清单（Manifest）

每个适配器声明它支持的组件及元信息。Manifest 也是前后端共享的“组件契约”，例如 ListPanel 需要的 `link`/`summary`/`published_at` 字段必须通过 `field_requirements` 说明；Planner（包括 LLM）只会依据 manifest + hints + 用户上下文决策，而不会去解析 payload：

```python
GITHUB_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="ListPanel",
            description="展示热门仓库列表",
            cost="medium",           # 计算成本
            default_selected=True,   # 是否默认选中
            required=True,           # 是否必需
        ),
        ComponentManifestEntry(
            component_id="LineChart",
            description="Star 数趋势图",
            cost="medium",
            default_selected=False,
            hints={"min_items": 3},  # 至少需要 3 条数据
        ),
    ]
)
```

#### 3. 智能组件规划

根据数据特征动态选择组件：

```python
# 运行时上下文
context = PlannerContext(
    item_count=25,                    # 数据项数量
    available_metrics={"stars", "forks"},  # 可用的统计指标
    user_preferences=[]               # 用户偏好（可选）
)

# 自动决策
components = plan_components_for_route(
    route="/github/trending",
    context=context
)
# 返回: ["ListPanel", "LineChart"]
# - ListPanel: 必需组件，总是包含
# - LineChart: 数据量 >= 3，符合 min_items 要求
```

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│                     Orchestrator                         │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ IntentService │  │ ChatService  │  │ DataQuery    │ │
│  └───────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
└──────────┼──────────────────┼──────────────────┼─────────┘
           │                  │                  │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
    │ RAG System  │   │   Panel     │   │   RSSHub    │
    │ (bge-m3 +   │   │  Generator  │   │   Executor  │
    │  ChromaDB)  │   │             │   │             │
    └─────────────┘   └──────┬──────┘   └─────────────┘
                             │
                   ┌─────────▼─────────┐
                   │ Component Planner │
                   │   + Adapters      │
                   └───────────────────┘
```

</details>

---

## 📁 项目结构

```
omnibox/
├── rag_system/              # RAG 向量检索系统
│   ├── quick_start.py      # 构建知识库脚本
│   ├── indexer.py          # 索引构建器
│   └── retriever.py        # 向量检索器
│
├── services/               # 核心服务模块
│   ├── panel/             # 面板生成相关
│   │   ├── adapters/      # 路由适配器
│   │   │   ├── github.py  # GitHub 适配器
│   │   │   ├── bilibili/  # B 站适配器
│   │   │   ├── hupu.py    # 虎扑适配器
│   │   │   └── utils.py   # 通用工具
│   │   ├── component_planner.py   # 组件规划器
│   │   ├── panel_generator.py     # 面板生成器
│   │   └── registry.py            # 适配器注册表
│   │
│   ├── chat_service.py    # 对话服务（整合 RAG + Panel）
│   ├── data_query_service.py  # 数据查询服务
│   └── cache_service.py   # 缓存服务
│
├── orchestrator/          # 对外 API 层
│   ├── chat_orchestrator.py  # 主编排器
│   └── example_usage.py       # 使用示例
│
├── query_processor/       # 查询处理
│   ├── intent_parser.py   # 意图解析
│   └── param_extractor.py # 参数提取
│
├── tests/                 # 测试用例
│   └── services/
│       ├── test_component_planner.py
│       └── test_panel_adapters.py
│
├── docs/                  # 文档
│   ├── adapters/         # 适配器文档
│   │   └── overview.md   # 路由映射说明
│   ├── backend-panel-adapter-spec.md    # 适配器规范
│   └── backend-panel-view-models.md     # 视图模型契约
│
├── deploy/               # 部署配置
│   └── docker-compose.yml  # RSSHub + Redis
│
├── .env.example          # 环境变量模板
├── requirements.txt      # Python 依赖
└── README.md            # 本文档
```

### 关键目录说明

| 目录 | 职责 |
|------|------|
| `rag_system/` | 负责将自然语言映射到 RSSHub 路由 |
| `services/panel/adapters/` | 各数据源的适配器（数据转换 + 组件生成） |
| `services/panel/component_planner.py` | 智能决策生成哪些可视化组件 |
| `orchestrator/` | 对外暴露的统一 API，封装内部复杂度 |
| `docs/` | 前后端契约、适配器规范等文档 |

---

## 🧪 运行测试

### 运行所有测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定模块测试
python -m pytest tests/services/test_component_planner.py -v
python -m pytest tests/services/test_panel_adapters.py -v

# 查看测试覆盖率
python -m pytest tests/ --cov=services --cov-report=html
```

### 测试说明

| 测试文件 | 覆盖内容 | 测试数量 |
|---------|---------|---------|
| `test_component_planner.py` | 组件规划逻辑、边界情况 | 11 个 |
| `test_panel_adapters.py` | 各路由适配器、数据转换 | 15 个 |

**重要**：修改适配器或 Planner 时，请务必运行测试并补充新的测试用例。

---

## 📚 更多文档

### 开发文档

- **[适配器开发指南](docs/adapters/overview.md)** - 如何添加新的数据源适配器
- **[组件规范](docs/backend-panel-adapter-spec.md)** - 适配器开发规范和最佳实践
- **[视图模型契约](docs/backend-panel-view-models.md)** - 前后端数据契约定义
- **[配置说明](CONFIGURATION.md)** - 详细的环境配置说明

### 架构文档

- **[整体架构](ARCHITECTURE.md)** - 系统架构和模块交互
- **[RAG 系统说明](rag_system/README.md)** - 向量检索系统的实现细节

### API 文档

```python
# 核心 API 参考
from orchestrator.chat_orchestrator import ChatOrchestrator

orchestrator = ChatOrchestrator()

# process_query - 主要接口
result = orchestrator.process_query(
    query: str,                    # 用户自然语言查询
    context: Optional[dict] = None # 可选的上下文信息
) -> dict

# 返回结构
{
    "status": "success" | "error",
    "message": str,               # 用户友好的消息
    "data": {...},               # 结构化数据
    "panels": {...},             # 可视化组件配置
    "debug": {...}               # 调试信息（可选）
}
```

---

## ❓ 常见问题

### Q1: 如何添加新的数据源？

**A**: 创建新的适配器并注册即可：

1. 在 `services/panel/adapters/` 下创建适配器文件
2. 使用 `@route_adapter` 装饰器注册路由
3. 实现数据转换和组件生成逻辑
4. 在 `docs/adapters/overview.md` 中补充文档

参考示例：
```python
from services.panel.adapters import route_adapter, RouteAdapterManifest

MANIFEST = RouteAdapterManifest(
    components=[...]
)

@route_adapter("/your/route", manifest=MANIFEST)
def your_adapter(source_info, records, context=None):
    # 实现转换逻辑
    return RouteAdapterResult(...)
```

### Q2: 为什么有些组件没有生成？

**A**: 可能的原因：
1. **数据量不足** - 例如 LineChart 需要至少 3 条数据（`min_items: 3`）
2. **缺少必需指标** - 某些组件依赖特定的统计指标
3. **max_components 限制** - 默认最多生成 2 个组件

解决方法：
```python
# 方法 1: 调整配置
config = ComponentPlannerConfig(
    max_components=5,
    allow_optional=True
)

# 方法 2: 明确指定用户偏好
context = PlannerContext(
    user_preferences=["LineChart", "StatisticCard"]
)
```

### Q3: 如何调试 RAG 检索不准确的问题？

**A**: 启用调试模式查看检索过程：

```python
from rag_system.retriever import RAGRetriever

retriever = RAGRetriever(debug=True)
results = retriever.retrieve("GitHub 热门项目", top_k=5)

# 查看检索到的路由和相似度分数
for result in results:
    print(f"路由: {result.route}, 分数: {result.score}")
```

如果检索不准确：
1. **重建索引** - `cd rag_system && python quick_start.py --rebuild`
2. **调整 top_k** - 增加候选路由数量
3. **补充语料** - 在 RAG 语料库中添加更多描述

### Q4: RSSHub 服务连接失败怎么办？

**A**: 检查以下几点：

```bash
# 1. 确认 Docker 服务运行中
docker-compose ps

# 2. 查看 RSSHub 日志
docker-compose logs rsshub

# 3. 测试连接
curl http://localhost:1200/github/trending

# 4. 若本地服务不可用，请先启动 deploy/docker-compose.yml 提供的 RSSHub
```

### Q5: 如何自定义可视化组件？

**A**: 修改适配器的组件生成逻辑：

```python
# 在适配器中自定义组件配置
block_plans.append(
    AdapterBlockPlan(
        component_id="ListPanel",
        props={
            "title_field": "custom_title",
            "link_field": "custom_link",
            "meta_fields": ["field1", "field2"]  # 自定义显示字段
        },
        layout_hint=LayoutHint(
            span=12,        # 占据 12 列（全宽）
            min_height=400  # 最小高度
        )
    )
)
```

---

## 🤝 贡献指南

欢迎贡献代码、文档或提出建议！

### 贡献流程

1. **Fork 项目** - 点击右上角 Fork 按钮
2. **创建分支** - `git checkout -b feature/your-feature`
3. **提交代码** - `git commit -m "feat: add your feature"`
4. **运行测试** - `python -m pytest tests/`
5. **推送分支** - `git push origin feature/your-feature`
6. **创建 PR** - 提交 Pull Request

### 代码规范

- 遵循 PEP 8 编码规范
- 使用中文注释（与用户沟通语言一致）
- 所有公共 API 必须有文档字符串
- 新功能必须补充测试用例
- 提交前运行 `pytest` 确保测试通过

### 提交信息规范

```bash
# 功能开发
git commit -m "feat: 添加 Twitter 数据源适配器"

# Bug 修复
git commit -m "fix: 修复缓存键冲突问题"

# 文档更新
git commit -m "docs: 更新适配器开发指南"

# 测试补充
git commit -m "test: 添加组件规划器边界测试"
```

---

## 🔭 研究模式实时卡片速览

- **多路 Panel 数据**：一次查询即可返回多条 `datasets`（例如 “B 站热搜 + 指定 UP 投稿”），后端自动将其转成多张卡片；`ChatService.metadata.datasets` 会列出每组数据的 `route / feed_title / item_count`，便于调试。
- **WebSocket `panel_preview` 事件**：研究流程（`mode=research`）中可调用 `emit_panel_preview` 工具把阶段性数据推送到前端，事件 payload 形如 `{ "previews": [{ "title": "...", "items": [...] }] }`，`ResearchLiveCard` 会即时展示。
- **启用条件**：确保 `client_task_id` 与 `/research/stream` WebSocket 已连接，必要时通过 `VITE_RESEARCH_WS_BASE` / `VITE_API_BASE` 配置前端访问路径。
- **可选同步**：如需把预览同步进主画布，可在收到 `panel_preview` 事件后调用现有 `panelStore.fetchPanel` 或自定义 append 逻辑。

---

## 🌟 致谢

本项目基于以下优秀开源项目：

- **[RSSHub](https://github.com/DIYgod/RSSHub)** - 万物皆可 RSS
- **[ChromaDB](https://github.com/chroma-core/chroma)** - 向量数据库
- **[bge-m3](https://huggingface.co/BAAI/bge-m3)** - 多语言语义检索模型
- **[Pydantic](https://github.com/pydantic/pydantic)** - 数据校验库

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 许可证。

---

## 💬 联系方式

- **Issues**: [GitHub Issues](https://github.com/hc-tec/omnibox/issues)
- **讨论**: [GitHub Discussions](https://github.com/hc-tec/omnibox/discussions)

---

<p align="center">
  <b>Omnibox（万界）</b> - 让数据获取和可视化像说话一样简单
</p>

<p align="center">
  ⭐ 如果这个项目对你有帮助，欢迎 Star 支持！
</p>
