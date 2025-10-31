# 251101-intelligent-panel-backend

## 背景
智能数据面板的设计文档已对输出结构（DataBlock、ViewDescriptor、LayoutTree 等）做出严格约束，但实现中仍存在兼容性与功能缺陷：Python 3.8 环境无法加载面板推荐模块、组件只会退化为基础列表、布局信息缺失，同时缺少与任务相关的文档与测试沉淀。

## 目标
- 修复面板模块核心缺陷，确保 Python 3.8 环境可用且能推荐多样化组件。
- 丰富布局属性输出，满足前端渲染需求。
- 补齐任务文档、索引记录，并完成测试执行。

## 方案概述
1. **兼容性修复**：调整类型提示与字段匹配策略，补充 canonical 字段映射，保证 Python 3.8 正常运行。
2. **布局增强**：读取组件默认布局与 ViewDescriptor 提示，生成包含 span/order 等信息的 LayoutTree。
3. **文档与测试**：建立任务文档、更新索引，安装 pytest 并运行核心 API/WebSocket 用例。

## TODO
- [x] 修复 ComponentSuggester 的兼容性与字段匹配问题。
- [x] 调整 LayoutEngine/PanelGenerator，输出包含 span/order 等信息的布局。
- [x] 安装 pytest 并运行 `tests/api/test_chat_controller.py` 与 `tests/api/test_chat_stream.py`。
- [x] 更新 `.agentdocs/index.md`，记录本任务文档并同步勾选 TODO 状态。

## 结果
- 面板推荐在 Python 3.8+ 环境正常运行，折线图、统计卡等组件可按 Schema 自动匹配。
- LayoutTree 现携带 `span`/`min_height` 等信息，REST 与 WebSocket 返回一致的布局结构。
- `D:\Anaconda\envs\torch-cuda\python.exe -m pytest tests/api/test_chat_controller.py tests/api/test_chat_stream.py` 全部通过（26 项）。
