# 251113 - 研究视图与流式接口修复记录

## 背景
- CLAUDE 版专属研究视图合入后，主界面 ResearchLiveCard/ActionInbox 不再更新，用户刷新 `/research/:taskId` 也会因缺少 query 直接报错。
- WebSocket 端点始终返回新 task_id，前端无法用预先分配的任务号追踪研究流程；同时流式研究路径忽略了客户端的 `filter_datasource`。
- 需要补齐上述缺陷并同步 AGENTS 约定的任务文档。

## 主要改动
### 后端
- `api/controllers/research_stream.py`：允许从 query-param 或消息体复用 `task_id`，缺省时仍旧生成随机 ID。
- `services/chat_service.py`：流式研究执行数据子查询时优先使用客户端 `filter_datasource`，并根据该过滤项计算 `prefer_single_route`。
- `tests/services/test_chat_service.py`：补充回归用例确保 `_handle_complex_research_streaming` 真正下发用户过滤条件。

### 前端
- `useResearchWebSocket` 重写：
  - 默认使用 `RESEARCH_WS_BASE`，自动拼接 `task_id`，并将 WebSocket 消息同步到 `researchStore`（步骤、预览、完成状态）。
  - 消息解析失败、自动重连与错误处理逻辑保持不变。
- `researchStore`：移除旧版 `ResearchStreamClient`，新增 `ensureTask`/`markTaskProcessing` 以供视图与 WebSocket 复用，同步保留预览与人工介入结构。
- `MainView`：研究模式时继续创建 `ResearchTask`、缓存 query，并跳转到 `/research/:taskId`。
- `ResearchView`：可从 URL 或 sessionStorage 恢复 query，缺失时给出提示；初始化时也会确保主界面任务盒存在对应条目。
- `useResearchWebSocket` + `taskStorage`：统一任务上下文存储，实现刷新/恢复能力。
- `researchStream.ts`：`RESEARCH_WS_BASE` 默认指向 `/api/v1/chat/research-stream`，供所有客户端共用。

## 验证
- `pytest tests/services/test_chat_service.py::test_streaming_research_respects_filter_datasource`
- 手动：
  - `npm run dev` 下触发研究模式，确认主界面出现 LiveCard 且 ActionInbox 正常；
  - 访问 `/research/<taskId>`，刷新仍能自动恢复查询并继续 streaming。
