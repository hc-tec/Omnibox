# 251101-intelligent-panel-backend

## 背景
后端智能数据面板链路原本依赖固定字段和正则去“猜测” RSSHub 返回的数据字段，这在“万物皆可 RSS”场景下无法工作。为了承接后续前端工作，需要改为“保留原始数据 + 适配器可扩展”的模式。

## 当前进展
- DataExecutor 仅裁剪并返回 RSSHub 原始 JSON，不再强制映射字段（integration/data_executor.py）。
- DataBlockBuilder / PanelGenerator 引入路由级适配器机制（services/panel/adapters.py），未注册时默认使用 FallbackRichText 展示原始数据。
- SchemaSummary 仅统计字段类型和样本，去掉语义标签（services/panel/schema_summary.py）。
- 联调文档 `docs/backend-intelligent-panel-overview.md` 已更新适配器使用说明。
- 回归测试通过：`D:\Anaconda\envs\torch-cuda\python.exe -m pytest tests/api/test_chat_controller.py tests/api/test_chat_stream.py`。

## 未完成事项
1. **路由适配器实现为空白**：目前除了兜底逻辑外没有任何 route 的具体适配实现，需要按数据源逐一补齐。
2. **组件约定待确认**：适配器返回的 props/options 需与前端组件保持一致，后续要与前端协同定义契约。
3. **大数据与敏感字段处理**：原始 JSON 可能很大，也可能含敏感字段，后续需补充裁剪/过滤策略。
4. **测试不足**：缺少针对适配器和 PanelGenerator 的单元/集成测试，应在编写适配器时同步补上。

## 测试记录
- `D:\Anaconda\envs\torch-cuda\python.exe -m pytest tests/api/test_chat_controller.py tests/api/test_chat_stream.py`

## 后续建议
- 在 `services/panel/adapters.py` 中为各个 RSSHub route 注册适配器，例如：
  ```python
  from services.panel.adapters import register_route_adapter, AdapterBlockPlan, RouteAdapterResult

  def bilibili_video_adapter(source_info, records):
      refined = [{"title": r.get("title"), "url": r.get("link") } for r in records]
      return RouteAdapterResult(
          records=refined,
          block_plans=[AdapterBlockPlan(
              component_id="ListPanel",
              props={"title_field": "title", "link_field": "url"},
              options={"span": 12},
          )],
      )

  register_route_adapter("/bilibili/user/video/", bilibili_video_adapter)
  ```
- 适配器可以决定字段映射、输出多个 block、配置交互等；未注册的路由不会影响整体流程，可按优先级逐步补齐。
- 前端保持与 PanelPayload/AdapterBlockPlan 契约一致，针对未适配的数据保留兜底展示，避免数据格式变动导致渲染失败。
