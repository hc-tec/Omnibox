# 项目文档索引

## 项目概述
智能RSS聚合系统 - 基于RAG + LLM的自然语言到API调用转换系统

## 架构文档
- `../ARCHITECTURE.md` - 项目整体分层架构说明，修改任何模块时必读
- `../README.md` - 项目使用说明和快速开始

## 技术架构文档
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
- 项目采用单体应用分层架构，不使用微服务
- 所有代码注释和文档使用中文
- 严格遵循CLAUDE.md中的代码质量要求
- 单个代码文件不超过1000行
- 优先复用现有代码，避免重复造轮子
