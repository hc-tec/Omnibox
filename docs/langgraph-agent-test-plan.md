# LangGraph V5 Agent 全量测试方案

## 1. 测试目标与范围
- 自 Omnibox（前端）发起查询到 LangGraph V5 Agent、工具层、DataStasher、Synthesizer 直至面板渲染的端到端行为均需覆盖。
- 核实 Planner/Reflector/Synthesizer 的协作逻辑、数据缓存、工作记忆、人机交互、工具容错、性能与监控是否满足 CLAUDE/AGENT 规范中“泛化优先、禁止补丁”的架构约束。
- 构建可持续复用的测试资产，后续可脚本化接入 `scripts/test_langgraph_agents.py` 或 CI。

## 2. 测试环境与准备
| 项目 | 要求 |
| --- | --- |
| 前端 | Desktop Intelligence Studio（dev 或打包版），确保 Omnibox、Live Insight Card、Action Inbox、panelStore append 模式可用；Chrome DevTools 打开 Network/WebSocket 面板。 |
| 后端 | FastAPI + LangGraph V5 最新分支，启用 `/api/v1/chat/research-stream`，`.env` 中 RSSHub / 语雀 / 私有源配置齐全；`DATA_QUERY_SINGLE_ROUTE=0` 以便多数据集验证。 |
| 数据 | 影视飓风 UID=290526284、何同学 UID=163637592、老师好我叫何同学 UID=245983；微博/知乎热点词；至少一份语雀或本地私有笔记样本；必要时准备 RSSHub Mock。 |
| 监控 | 打开 `services/chat_service.py` 与 `langgraph_agents/agents/*.py` 调试日志；若有 Grafana/Prometheus，记录延迟与错误；保留 Planner JSON 与 data_stash dump。 |

## 3. 覆盖维度矩阵
| 类别 | 关键能力 | 相关模块/工具 | 观测点 |
| --- | --- | --- | --- |
| 1. 基础数据获取 | 单路 fetch、公用 panel adapter、RAG 命中率 | Router → Planner → ToolExecutor → Synthesizer；bilibili 热搜/UP 主投稿 | datasets 元数据、panel 渲染、retrieved_tools |
| 2. 组合/过滤/分析 | 多路 fetch、filter/compare/aggregate 协同 | filter_data / compare_data / aggregate_data、DataStasher | data_stash 引用链、Synthesizer 摘要 |
| 3. 私有数据/记忆 | fetch_private_data、working_memory、任务回溯 | context_manager、working_memory、私有源凭据 | working_memory 内容、Synthesizer 引述、权限隔离 |
| 4. 人机交互/多轮 | ask_user_clarification、Action Inbox、取消恢复 | Reflector、wait_for_human、WebSocket 消息 | human 请求/响应、任务状态切换 |
| 5. 异常与兜底 | RAG 未命中、工具失败、权限拒绝 | orchestrator fallback、ErrorStasher、订阅系统 | 错误文案、回退策略、缓存与 state 清理 |
| 6. 性能与可靠性 | 并发、token 控制、缓存命中、断线重连 | Synthesizer summary-only、CacheService、WS Manager | TP95、token 使用、缓存命中、重连次数 |

## 4. 测试类别与用例

### 4.1 基础数据获取
| ID | 查询 | 测试目标 | 验证要点 |
| --- | --- | --- | --- |
| 1.1 | `B站热搜` | 验证热搜工具 happy path | Planner 仅调用 fetch；datasets feed_title=“B站热搜”；面板显示排名；Synthesizer 不拉原始数据。 |
| 1.2 | `看看影视飓风最近发的视频` | RAG 命中 UID + 双组件渲染 | retrieved_tools 命中 `UP 主投稿`；面板含列表 + 统计卡；summary 使用 DataStasher 输出。 |
| 1.3 | `何同学的视频` | 别名解析/Query Expander | Planner 输入新增关键词；ToolExecutor 使用 UID；UI 同 1.2。 |
| 1.4 | `同时展示B站热搜和微博热搜` | 多 datasets + append | datasets 中出现两条记录；panelStore 处理 append；日志无重复 node id。 |
| 1.5 | `把影视飓风和老师好我叫何同学最近投稿放在两个卡片里` | 同 query 多路路由 | Planner 输出两个 fetch；Synthesizer 描述对比差异；UI 同屏显示两卡。 |

执行步骤：Omnibox 发起 → 观察 Live Card 任务列表 → WebSocket 日志对齐 Planner 子任务 → 校验 `services/data_query_service.py` 日志中的 datasets 元信息与面板 JSON。

### 4.2 组合/过滤/分析
| ID | 查询 | 测试目标 | 验证要点 |
| --- | --- | --- | --- |
| 2.1 | `B站影视飓风投稿视频中，标题包含"英雄联盟"` | fetch → filter_data 自动链路 | Planner 生成 filter 步骤；无 filter_hint 字段；过滤结果面板仅剩匹配项；Synthesizer 引用过滤条件。 |
| 2.2 | `把影视飓风最近10条视频和知乎讨论Sora的问题做对比` | compare_data 合并多源 | DataStasher 记录两个 data_id；Synthesizer 输出对比；UI 可用表格 + FallbackRichText。 |
| 2.3 | `统计B站热搜前20条里科技、游戏的比例` | aggregate_data + 可视化 | aggregate_data 参数包含 bucket；面板为柱状图/统计卡；Synthesizer 给出比例。 |
| 2.4 | `列出B站和微博热搜都出现的关键词` | 多源交集 + filter/compare | Planner 生成交叉任务；Synthesizer 列出交集列表；UI 以列表/表格呈现。 |
| 2.5 | `最近一周影视飓风投稿的平均播放量` | 聚合统计 + 时间窗口 | aggregate_data 入参含日期约束；DataStasher summary 带均值；UI 统计卡展示均值。 |

执行步骤：记录 Planner JSON、data_stash dump；前端验证组件 props（`options.mode`、`max_items` 等）符合 `frontend-panel-components.md`；日志确认 Synthesizer 仅读 summary。

### 4.3 私有数据与工作记忆
| ID | 查询 | 测试目标 | 验证要点 |
| --- | --- | --- | --- |
| 3.1 | `用我语雀中“AI视频”笔记的要点，和B站Sora热度做个对比` | fetch_private_data + fetch_public_data 联动 | 私有工具调用成功，Synthesizer 标注来源（private/public）；权限校验日志正常。 |
| 3.2 | `延续刚才的数据，再给我列出需要跟进的3个主题` | working_memory 复用 | Planner 直接引用 data_stash/working_memory；UI append 新内容。 |
| 3.3 | `记住“影视飓风=严行方工作室”，之后遇到提及时直接引用` | 记忆写入 + 查询复用 | context_manager 记录映射；再次查询“严行方工作室视频”无需澄清。 |
| 3.4 | `如果我说“继续之前的分析，帮我加一个图表”` | 同任务多次生成 + append | layout_engine row id 唯一；panel 增量渲染；Synthesizer 引用既有分析。 |

执行步骤：检查 `langgraph_agents/agents/research_agent.py` state dump；验证 `researchViewStore` 中 `mode=append`，`DynamicBlockRenderer` ID 不重复；确保私有数据日志显示 user_id/权限。

### 4.4 人机交互与多轮规划
| ID | 查询 | 测试目标 | 验证要点 |
| --- | --- | --- | --- |
| 4.1 | `帮我找近期讨论Sora的视频，如果需要精确范围可以问我` | ask_user_clarification 流程 | WebSocket `human_in_loop_request` 触发 Action Inbox；用户输入写回后 planner 继续；日志无超时。 |
| 4.2 | `列出我收藏夹里AI视频的要点`（无凭据） | 权限确认对话 | Router/Reflector 请求用户提供 token；前端主输入框锁定；Action Inbox 提醒。 |
| 4.3 | `把刚才报告里的结论翻译成英文`（立即回应） | 同 session 继续执行 | WebSocket 发送 `human_response` 后，任务无重启，日志显示 `wait_for_human` 恢复。 |
| 4.4 | `我反悔了，停止这个任务` | 取消任务 | Action Inbox 触发 cancel；LangGraph 终止，卡片状态=取消，数据清理。 |
| 4.5 | `要是查询太慢请告诉我`（模拟长耗时） | 进度/心跳提示 | 流式日志持续更新；心跳丢失时前端提示重试。 |

执行步骤：使用 DevTools 观察 WS 帧；确认前端 `useResearchWebSocketManager` 发送 `human_response`/`cancel`；后端日志标记 `wait_for_human -> continue` 或 `cancelled`。

### 4.5 异常场景与兜底
| ID | 查询 | 测试目标 | 验证要点 |
| --- | --- | --- | --- |
| 5.1 | `B站用户“这肯定不存在”发布的视频` | RAG 未命中 → 友好提示 | Planner 返回空；Synthesizer 提示“未找到实体”并建议澄清；Action Inbox 或 Omnibox 文案清晰。 |
| 5.2 | `帮我看UP主粉丝`（缺 Cookie） | 必需配置缺失 | ToolExecutor 抛可读错误；Synthesizer 给出自建指引；数据缓存不落错误内容。 |
| 5.3 | 模拟 `/bilibili/hot-search` 返回 500 | DataExecutor 重试与缓存 | 日志显示重试/降级；若缓存存在则回退；若失败，前端卡片状态=error。 |
| 5.4 | `给我一个知乎登录后的私信内容` | 权限拒绝 | Router 在意图阶段拒绝；Synthesizer 说明限制，避免错误调用。 |
| 5.5 | 人工注入 LangGraph 节点异常 | 错误路径 | ErrorStasher 记录堆栈；卡片显示错误摘要；Action Inbox 清理提醒；无僵尸 WS。 |

执行步骤：必要时在 Integration 层注入 mock；检查 `services/chat_service.py` 错误处理逻辑、state 清理；确认 data_stash 不残留失败引用。

### 4.6 性能与可靠性
| ID | 场景 | 目标 | 验证要点 |
| --- | --- | --- | --- |
| 6.1 | 5 个并发查询（热搜 + 多路 + 私有） | 并发隔离 | WS 连接池无串线；TP95 < 5s（视环境）；日志无锁等待。 |
| 6.2 | 长响应摘要（>30 条记录） | Token 控制 | Synthesizer 仅读 summary；token < 10k；无 `BadRequestError`。 |
| 6.3 | 重复查询命中缓存 | 缓存命中率 | 第二次查询耗时显著下降；metadata.datasets 标记 `cache_hit=True`。 |
| 6.4 | Append 连续 3 轮 | 布局稳定性 | layout_engine UUID 唯一；UI 不重复；日志无“duplicate node”。 |
| 6.5 | WebSocket 中断重连 | 稳定性 | 断网 5s → 自动重试 ≤5 次；恢复后继续接受进度，不重新执行；日志记录重连。 |

执行步骤：可借助脚本模拟并发；统计 `run_server.py` 日志或监控指标；前端 DevTools 观察 WS 心跳与重连逻辑；确保缓存命中率与 token 使用被记录。

## 5. 执行顺序与输出
1. 先完成类别 1（基线）→ 类别 2（工具协同）→ 类别 3（记忆/私有）→ 类别 4（人机）→ 类别 5（异常）→ 类别 6（性能），避免在功能未稳定时就进行压力测试。
2. 每次测试记录：时间、查询、Planner JSON、工具执行结果、面板截图/JSON、关键日志；失败附堆栈与数据引用，确保可复现。
3. 常规场景（1.1/1.2/2.1/2.3/5.2/6.3）建议脚本化纳入 `scripts/test_langgraph_agents.py` 或新增 Playwright/pytest WebSocket 集成测试，形成每日回归。
4. 如引入新的跨模块约束（例如新的人机交互模式、私有数据权限），需同步更新 `.agentdocs/index.md` 及相关设计文档。

## 6. 度量与合格门槛
- 功能项通过率 ≥ 95%，关键路径（1.1、1.2、2.1、3.1、4.1、5.2）必须全部通过。
- 并发查询 TP95 < 5s（可按环境调整），WS 重连成功率 100%，token 使用无超限错误。
- 缓存命中率、数据面板渲染成功率、人机交互响应率需在日报中跟踪；一旦发现结构性问题需回写文档与测试脚本。
