# 路由适配器说明（首批数据源）

> 本文列出当前已实现的路由级适配器、依赖的 RSSHub 字段、可输出的组件组合及 Manifest 关键信息。新增或调整适配器后，请同步更新此文件，便于 Planner、前端和运营快速了解字段契约。组件选择默认由 `plan_components_for_route`（max_components=2）执行，如有特殊需求请同时更新 manifest hints 和 Planner 配置。

---

## Bilibili 系列

适配器位于 `services/panel/adapters/bilibili/` 下，按功能拆分模块。

### 1. `/bilibili/user/dynamic`、`/bilibili/user/video`
- **模块**：`feed.py` 中的 `bilibili_feed_adapter`  
- **Manifest**：
  - `ListPanel`（cost=`low`，default=`True`，required）——展示投稿/动态列表  
- **字段映射**：

  | RSSHub 字段 | Adapter 字段 | 说明 |
  | ----------- | ------------ | ---- |
  | `title` / `name` | `title` | 标题 |
  | `link` / `url` | `link` | 详情链接 |
  | `description` / `summary` / `content_html` | `summary` | 通过 `short_text` 去除 HTML |
  | `pubDate` / `date_published` | `published_at` | 发布时间 |
  | `author` | `author` | 作者 |
  | `tags` | `categories` | 标签数组 |

- **组件组合**：`ListPanel`，默认开启 `show_description`，交互为 `open_link`。  
- **统计信息**：`feed_title`、`total_items`、`api_endpoint`。  
- **扩展建议**：若需展示播放量、点赞数等指标，可在 `stats` 中累计并追加 `StatisticCard`。

### 2. `/bilibili/user/followings/:uid/:loginUid`
- **模块**：`followings.py` 中的 `bilibili_followings_adapter`  
- **Manifest**：
  - `ListPanel`（cost=`low`，default=`True`，required，hints=`{"metrics": ["follower_count"]}`）——Planner 会在检测到 `count/total` 字段时保留该组件  
- **字段映射**：

  | RSSHub 字段 | Adapter 字段 | 说明 |
  | ----------- | ------------ | ---- |
  | `title` | `title` | 如 “Alice 新关注 Bob” |
  | `link` | `link` | 关注用户空间地址 |
  | `description` | `summary` | 通过 `short_text` 处理，展示签名等信息 |
  | `pubDate` | `published_at` | 关注时间 |

- **统计信息**：优先读取 `payload["count"]`；若缺失则从 `description` 中的 “总计X” 解析，最终写入 `stats["follower_count"]`，同时保留 `api_endpoint`、`total_items`。  
- **扩展建议**：后续可根据业务需求新增关注变化趋势并输出 `StatisticCard`。

---

## GitHub 系列

### `/github/trending`
- **模块**：`services/panel/adapters/github.py` 中的 `github_trending_adapter`  
- **Manifest**：
  - `ListPanel`（cost=`medium`，default=`True`，required）  
  - `LineChart`（cost=`medium`，default=`False`，共享 `ListPanel` 数据集）  
- **字段映射**：

  | RSSHub 字段 | Adapter 字段 | 说明 |
  | ----------- | ------------ | ---- |
  | `title` | `title` | 仓库全名 |
  | `url` | `link` | 仓库地址 |
  | `description` | `summary` | 使用 `short_text` 限制长度 |
  | `date_published` | `published_at` | 发布时间 |
  | `extra.language` | `language` | 编程语言 |
  | `extra.stars` | `stars` | Star 数（转换为整数） |
  | `extra.stars_today` | `stars_today` | 当日新增 Star |
  | `extra.forks` | `forks` | Fork 数 |

- **组件组合**：
  1. `ListPanel` —— 展示仓库概览、语言等信息。  
  2. `LineChart` —— 以排名为 `x`，Star 数为 `y`，语言作为系列维度。  
- **统计信息**：`top_language`、`top_stars`、`total_items`、`api_endpoint`。  
- **扩展建议**：可追加 `StatisticCard` 展示总 Star、增量等关键指标，并在 Manifest 中补充描述。

---

## Hupu 系列

### `/hupu/bbs/bxj/:id` 等
- **模块**：`services/panel/adapters/hupu.py` 中的 `hupu_board_list_adapter`  
- **Manifest**：
  - `ListPanel`（cost=`low`，default=`True`，required）  
- **字段映射**：

  | RSSHub 字段 | Adapter 字段 | 说明 |
  | ----------- | ------------ | ---- |
  | `title` | `title` | 帖子标题 |
  | `url` | `link` | 帖子链接 |
  | `content_html` | `summary` | 去除 HTML 后的帖子预览 |
  | `date_published` | `published_at` | 发布时间 |
  | `authors[0].name` | `author` | 作者昵称 |

- **组件组合**：`ListPanel`。  
- **统计信息**：`feed_title`、`total_items`、`api_endpoint`。  
- **扩展建议**：如需展示热度或回帖数，可在 `stats` 中存储聚合指标，再衍生 `StatisticCard` 或 `TableView`。

---

## 通用兜底

### `/github/issue`、`/sspai/*`
- **模块**：`services/panel/adapters/generic.py` 中的 `_build_simple_list`  
- **Manifest**：
  - `ListPanel`（cost=`low`，default=`True`）  
- **字段映射**：保留 `id`、`title`、`link`、`summary`、`published_at` 等基本信息。  
- **组件组合**：`ListPanel`。  
- **统计信息**：`datasource`、`route`、`feed_title`、`total_items`、`api_endpoint`。  
- **注意事项**：一旦前端需要额外字段，应迁移到专门的数据源模块中定制适配器，避免“万能适配器”膨胀。

---

## 开发 Checklist

1. 新增路由前先撰写/更新 Manifest，涵盖组件、成本、备注。  
2. 在适配器中使用 `AdapterExecutionContext.wants` 控制组件生成，避免无用计算。  
3. 将字段映射、组件组合、统计信息记录在本文档，便于前后端查阅。  
4. 编写单元测试覆盖：Manifest 暴露的组件、`requested_components` 控制、stats 字段。  
5. 文档更新与代码变更保持同步，Planner 才能基于最新信息做出正确决策。

> Manifest 与本文档互为补充：Manifest 提供机器可读的组件能力，本文档记录人工可读的字段说明。维护好两者，才能快速扩展适配器矩阵并保持契约一致。***
