# ActionRegistry 自动化 - 快速开始

## ✅ 已完成

所有代码已生成并测试通过：

```
services/subscription/
├── __init__.py                     # 模块初始化
├── route_analyzer.py               # 路由分析器（自动推断）
├── action_registry.py              # 动作注册表（配置驱动）
└── action_registry_config.json     # 自动生成的配置（48个动作）

scripts/
├── __init__.py                     # 模块初始化
├── generate_action_registry.py     # 主生成脚本
├── test_action_registry.py         # 测试脚本
└── README_ACTION_REGISTRY.md       # 详细文档
```

## 快速使用

### 1. 生成配置（已完成）

```bash
python -m scripts.generate_action_registry
```

**结果**：
- ✅ 分析了 3008 个 RSSHub 路由
- ✅ 成功推断 55 个路由（1.8%）
- ✅ 生成 48 个 action 定义（去重后）
- ✅ 平均置信度：0.94

**支持的平台**（前10）：
- bilibili: 13 actions
- github: 4 actions
- zhihu: 4 actions
- gitee: 3 actions
- pingwest: 2 actions
- 等等...

### 2. 查看配置

```bash
# 查看生成的配置文件
cat services/subscription/action_registry_config.json
```

### 3. 测试功能

```bash
# 运行测试
python -m scripts.test_action_registry
```

**测试结果**：
- ✅ 基本加载正常
- ✅ 获取动作定义正常
- ✅ 路径构建正常
- ✅ 获取支持的动作正常

## 典型场景

### 场景1：B站用户多种访问方式

```python
from services.subscription.action_registry import ActionRegistry

registry = ActionRegistry()

# 同一个UP主（uid=12345），多种访问方式
actions = registry.get_supported_actions("bilibili", "user")
# ['videos', 'following_videos', 'dynamics', 'favorites', 'coin', 'like', ...]

# 构建不同的路径
path1 = registry.build_path("bilibili", "user", "videos", {"uid": "12345"})
# → "/user/video-all/12345"

path2 = registry.build_path("bilibili", "user", "following_videos", {"uid": "12345"})
# → "/followings/video/12345"

path3 = registry.build_path("bilibili", "user", "dynamics", {"uid": "12345"})
# → "/user/dynamic/12345"
```

### 场景2：GitHub仓库多种操作

```python
# GitHub仓库（owner/repo）
actions = registry.get_supported_actions("github", "repo")
# ['issues', 'pull_requests', 'stars', 'file']

# 构建路径
path = registry.build_path(
    "github", "repo", "issues",
    {"owner": "langchain-ai", "repo": "langchain"}
)
# → "/issue/langchain-ai/langchain"
```

## 与订阅系统集成

### 1. 创建订阅（存储实体）

```python
subscription = Subscription(
    display_name="科技美学",
    platform="bilibili",
    entity_type="user",  # ← 只存储实体类型
    identifiers={"uid": "12345"},
    supported_actions=["videos", "following_videos", "dynamics", "favorites"]
)
```

### 2. 查询时动态选择动作

```python
# 用户查询："科技美学的关注列表"

# QueryParser 解析
parsed = QueryParser().parse("科技美学的关注列表")
# → entity_name="科技美学", entity_type="user", action="following_videos"

# SubscriptionService 查找实体
identifiers = subscription_service.resolve_entity(
    entity_name="科技美学",
    platform="bilibili",
    entity_type="user"
)
# → {"uid": "12345"}

# ActionRegistry 构建路径
path = ActionRegistry.build_path(
    platform="bilibili",
    entity_type="user",
    action="following_videos",
    identifiers=identifiers
)
# → "/followings/video/12345"
```

## 扩展推断规则

当前推断成功率只有 1.8%（55/3008），主要原因：
1. 很多路由没有标准的参数名（如 `uid`）
2. 路径模式不规则
3. 有些路由不适合订阅系统（如搜索、榜单等）

### 提高推断率的方法

**方法1：添加更多参数映射**

编辑 `services/subscription/route_analyzer.py`：

```python
PARAMETER_TO_ENTITY_TYPE = {
    # 添加更多参数映射
    "author_id": "user",
    "blogger_id": "user",
    "space_id": "space",
    # ...
}
```

**方法2：添加更多路径模式**

```python
PATH_PATTERN_TO_ACTION = [
    # 添加更多路径模式
    (r"/author/posts", "posts"),
    (r"/blogger/articles", "articles"),
    # ...
]
```

**方法3：手动编辑配置文件**

对于无法自动推断的路由，直接编辑 `action_registry_config.json`：

```json
{
  "platform": "my_platform",
  "entity_type": "user",
  "action": "posts",
  "path_template": "/my/custom/path/:user_id",
  "required_identifiers": ["user_id"],
  "display_name": "用户帖子",
  "description": "",
  "confidence": 1.0,
  "route_id": "my_platform_user_posts"
}
```

## 查看低置信度路由

```bash
# 查看需要人工审核的路由
python -m scripts.generate_action_registry --show-low-confidence
```

这会列出置信度在 0.5-0.8 之间的路由。

## 按平台过滤

```bash
# 只生成B站和知乎的配置
python -m scripts.generate_action_registry --platforms bilibili,zhihu
```

## 调整置信度阈值

```bash
# 提高置信度要求（只保留高质量推断）
python -m scripts.generate_action_registry --min-confidence 0.8
```

## 重新加载配置

```python
from services.subscription.action_registry import ActionRegistry

# 修改配置文件后，重新加载
ActionRegistry.reload()
```

## 统计信息

```python
from services.subscription.action_registry import ActionRegistry

stats = ActionRegistry.get_stats()
print(f"总动作数: {stats['total_actions']}")
print(f"支持平台: {stats['total_platforms']}")
print(f"平台分布: {stats['platforms']}")
```

## 下一步

1. **完善推断规则**：提高推断成功率
2. **实现 QueryParser**：LLM解析用户查询
3. **实现 SubscriptionService**：订阅管理
4. **前端集成**：订阅管理界面

## 相关文档

- 设计文档：`.agentdocs/subscription-system-design.md`
- 自动化方案：`.agentdocs/subscription-action-registry-automation.md`
- 详细使用文档：`scripts/README_ACTION_REGISTRY.md`

## 故障排查

### 问题1：配置文件不存在

**解决**：
```bash
python -m scripts.generate_action_registry
```

### 问题2：推断成功率太低

**解决**：
1. 添加更多推断规则（参数映射、路径模式）
2. 手动编辑配置文件
3. 降低置信度阈值：`--min-confidence 0.3`

### 问题3：中文编码错误

**解决**：已在脚本中添加 UTF-8 编码支持（Windows 兼容）

### 问题4：找不到某个平台的路由

**解决**：
```bash
# 查看该平台的路由定义
grep -A 20 '"provider_id": "platform_name"' route_process/datasource_definitions.json
```

---

**生成时间**：2025-11-13
**状态**：✅ 完成并测试通过
**当前推断率**：1.8%（可通过扩展规则提高）
