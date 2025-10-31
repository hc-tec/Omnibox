# 项目文档索引

## 项目概述
智能RSS聚合系统 - 基于RAG + LLM的自然语言到API调用转换系统

## 架构文档
- `../ARCHITECTURE.md` - 项目整体分层架构说明，修改任何模块时必读
- `../README.md` - 项目使用说明和快速开始

## 技术架构文档
### 后端架构（必读）
- `backend-architecture.md` - 后端（Integration/Service/Controller层）架构设计与技术约束，修改任何后端代码时必读
  - Integration层可复用组件（DataExecutor、CacheService）使用规范
  - URL编码安全最佳实践
  - 测试策略（单元测试与真实服务隔离）
  - 同步/异步策略
  - FeedItem通用数据模型（"万物皆可RSS"）

### RAG系统
- `../rag_system/` - 向量检索模块，包含embedding模型、向量存储、检索管道

### 查询处理
- `../query_processor/` - 查询解析模块，包含LLM客户端、Prompt构建器、结果解析器

### 编排层
- `../orchestrator/` - 流程编排模块，协调RAG和LLM完成端到端处理

## 当前任务文档
- `workflow/251031-rss-aggregation-layered-architecture.md` - 实现RSS聚合系统分层架构
- `workflow/251031-rss-aggregation-architecture-refine.md` - RSS聚合架构落地改进方案，补充本地依赖、同步异步策略与接口设计

## 全局重要记忆

### 项目架构
- 项目采用单体应用分层架构，不使用微服务
- 分层结构：Controller → Service → Integration（Data/Cache）
- Integration层和Service层保持同步实现，Controller层通过线程池调度

### 代码规范
- 所有代码注释和文档使用中文（UTF-8编码）
- 严格遵循CLAUDE.md中的代码质量要求
- 单个代码文件不超过1000行
- 优先复用现有代码，避免重复造轮子

### Integration层核心组件（必须复用）
- **DataExecutor** - 所有RSSHub数据获取统一走DataExecutor，不允许直接拼接URL
- **CacheService** - 所有数据缓存统一走CacheService（全局单例），不允许使用functools.lru_cache
- **URL编码安全** - RSSHub路径包含特殊字符（如`#步行街主干道`）会被DataExecutor正确编码，不会截断

### 配置管理
- RSSHub配置统一使用`RSSHubSettings`（`query_processor/config.py`）
- `PathSettings.base_url`已废弃，不要使用
- 所有Python依赖在根目录`requirements.txt`统一维护

### 测试策略
- 真实RSSHub测试必须隔离（环境变量`RSSHUB_TEST_REAL=1`或健康检查跳过）
- CI和离线环境默认只运行纯单元测试
- pytest为必需依赖，已在requirements.txt启用

### 数据模型
- RSSHub支持"万物皆可RSS"（视频/社交/论坛/商品等），使用FeedItem通用模型
- 不要将FeedItem改名为Article或Post
- `media_type`无媒体时为`None`，不是空字符串
