# RSS聚合系统分层架构改进方案

## 背景
CLAUDE 方案已经梳理出 Controller / Service / Integration 层的目标，但在本地部署依赖、同步异步策略、缓存设计、接口形态等方面仍存在风险。本方案用于在原有规划基础上补齐关键决策，避免后续开发返工。

## 核心问题回顾
- **外部 RSSHub 依赖**：示例直接指向 `https://rsshub.app/...`，容易让实现绕过仓库内的本地 RSSHub 部署。
- **同步/异步不一致**：`RAGInAction` 与 LLM 客户端均为同步阻塞实现，若 Service / Controller 按异步写法落地会导致事件循环阻塞。
- **缓存策略不适配**：计划使用 `functools.lru_cache`，但 `async def` 接口无法直接套用；缺少 TTL 管理和缓存失效策略。
- **WebSocket 支撑缺位**：阶段规划强调需要流式响应，但未给出具体实现步骤。
- **依赖管理缺口**：`httpx`、`feedparser` 等新依赖未纳入统一的安装文档或 requirements，部署会失败。

## 改进目标
1. 默认走仓库自带的本地 RSSHub 服务，远端地址仅作为降级方案，并通过配置项显式管理。
2. 制定明确的同步/异步边界，保证 FastAPI 不被同步调用阻塞，同时避免大规模改写现有模块。
3. 设计可扩展的 TTL 缓存方案，兼容同步与异步调用。
4. 在任务规划中补齐 WebSocket 流式接口的设计与验收。
5. 将新增依赖纳入统一的依赖清单与安装说明，保证 CI/CD 一致性。

## 关键设计决策

### 1. RSSHub 访问策略
- **默认 Base URL**：在 `query_processor/path_settings` 里新增 `rsshub_base_url`（或沿用 `PATH_BASE_URL`），配置默认为 `http://localhost:1200`，与 `deploy/docker-compose.yml` 对齐。
- **降级机制**：当本地实例不可达时才切换到公共 RSSHub，必须在日志里写明降级原因。
- **健康检查**：DataExecutor 初始化时提供 `ensure_rsshub_alive()`，启动阶段即可发现本地服务未启动的问题。

### 2. 同步 / 异步策略
- **Service 层保持同步实现**：`DataExecutor` 使用 `httpx.Client`，`DataQueryService` 调用同步的 `RAGInAction.process()`，简化测试与复用。
- **Controller 层解耦**：FastAPI 控制器通过 `fastapi.concurrency.run_in_threadpool` 或 `starlette.concurrency.run_in_threadpool` 调度 Service，避免阻塞事件循环。
- **可选 Async Wrapper**：若后续需要异步能力，可在 Service 层补充 `async` 包装方法，内部通过 `asyncio.to_thread` 调用同步实现。

### 3. 缓存与会话
- **缓存组件**：采用 `cachetools.TTLCache` 或自建带 TTL 的字典封装，提供线程安全访问；若后续接入 Redis，只需替换实现。
- **缓存粒度**：区分 `RSS 数据缓存` 与 `RAG 结果缓存`，分别配置 TTL（默认 10 分钟 / 1 小时），缓存键包含用户查询 + 路由 ID，避免交叉污染。
- **会话上下文**：沿用原计划的抽象接口，但实现默认同步，后续需要多进程部署时再扩展至 Redis。

### 4. API & WebSocket
- **REST 接口**：保持 CLAUDE 方案中的 `/api/v1/chat`，返回结构中增加 `source` 字段（local / fallback）以标识是否命中本地 RSSHub。
- **WebSocket 实现**：新增 `api/controllers/chat_stream.py`，通过 `FastAPI WebSocket` 在后续阶段提供流式响应；内部使用生成器按阶段推送（意图判定 → 检索 → 数据 → 总结），并使用线程池避免阻塞。
- **统一错误处理**：REST 与 WebSocket 都走统一的异常封装，包含降级状态与错误码。

### 5. 依赖管理
- **Python 依赖**：在项目根目录新增 `requirements.txt`（聚合 `rag_system` 和 `query_processor` 现有依赖），并补充 `httpx`, `feedparser`, `cachetools`。
- **安装说明**：更新 `README.md` 与 `CONFIGURATION.md` 的安装章节，指导一次性安装根目录依赖或按模块安装。
- **镜像支持**：如需国内镜像，写入 `pip` 源配置指引，保证新依赖能顺利拉取。

## 实施阶段

### 阶段0：方案落地准备 ✅
- [x] 完成改进方案文档
- [ ] 将本方案纳入 `.agentdocs/index.md` 的“当前任务文档”

### 阶段1：配置与依赖
- [ ] 扩展 `query_processor/config.py`（或新增配置模块）支持 `rsshub_base_url`、降级列表。
- [ ] 根目录新增 `requirements.txt` 并收敛依赖；更新 `README.md` 安装说明。
- [ ] 检查 Docker Compose 文档，提示开发者默认启动 `rsshub` 服务。

### 阶段2：Integration 层
- [ ] 创建 `integration/data_executor.py`，实现同步 `DataExecutor`，支持健康检查、降级与源信息。
- [ ] 实现同步的缓存封装（`integration/cache_service.py`），提供 TTL 缓存。
- [ ] 覆盖单元测试（本地成功、远端降级、缓存命中/失效、错误处理）。

### 阶段3：Service 层
- [ ] `DataQueryService` 整合 `RAGInAction`、`DataExecutor`、缓存；提供同步方法与可选 `async` 包装。
- [ ] `IntentService`、`ChatService` 保持同步接口，以便线程池复用。
- [ ] 为不同意图编写单元测试，验证线程池调用的可重入性。

### 阶段4：Controller 层
- [ ] `api/controllers/chat_controller.py` 的 REST 端点内使用 `run_in_threadpool` 调用 Service，同步返回结果。
- [ ] 定义统一响应 Schema，包含降级状态、缓存命中标记。
- [ ] 集成 FastAPI 异常处理中间件，确保阻塞线程在超时时能回收。
- [ ] 编写集成测试（可使用 `httpx.AsyncClient` + FastAPI TestClient）。

### 阶段5：WebSocket 流式接口
- [ ] 设计并实现 `chat_stream.py`，按阶段推送处理进度。
- [ ] WebSocket 内部仍走线程池，避免阻塞事件循环；对外暴露 `stream_id` 以关联日志。
- [ ] 增加端到端测试（可使用 `websockets` 或 FastAPI 内置测试工具）。

### 阶段6：运维与监控
- [ ] 记录 RSSHub 源切换/失败日志到统一日志格式。
- [ ] 增加 Prometheus 指标或简单统计（命中率、降级次数、单次响应耗时）。
- [ ] 更新部署文档，明确需要先启动 `docker-compose` 并配置 `.env`。

## 验收标准
- REST `/api/v1/chat` 在本地 RSSHub 正常启动时命中本地数据，关闭本地服务后自动降级至公共 RSSHub 并返回 `source=fallback`。
- WebSocket 接口能按阶段推送消息，长时间阻塞不会拖垮事件循环。
- 缓存逻辑在 TTL 内命中，过期后重新拉取；缓存切换实现可替换为 Redis 不改业务代码。
- 所有新增依赖均写入 `requirements.txt` 并在 README 中有安装指引；CI 能成功安装并通过单元测试。
- 集成测试覆盖数据查询成功、降级、缓存命中、闲聊回复等关键路径。

## 后续关注点
- 后续若改造 `RAGInAction` 为异步版本，需要同步调整 Service 层线程池调用逻辑。
- RSSHub 本地实例需要与 `deploy/rsshub.env` 中的隐私数据隔离，建议提供清空或示例配置。
- 流式接口上线后，要关注前端消费协议，必要时补充兼容的 JSON Lines / SSE 方案。
