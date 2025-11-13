# ActionRegistry 自动生成工具

## 功能

从 `route_process/datasource_definitions.json` 自动分析 RSSHub 路由定义，推断 `entity_type` 和 `action`，生成 ActionRegistry 配置文件。

## 快速开始

### 1. 基本使用

```bash
# 生成配置文件（默认配置）
python -m scripts.generate_action_registry
```

这将：
- 分析所有 RSSHub 路由
- 自动推断 entity_type 和 action
- 生成配置文件到 `services/subscription/action_registry_config.json`
- 最小置信度阈值：0.5

### 2. 查看统计信息

```bash
# 只显示统计，不生成文件
python -m scripts.generate_action_registry --stats-only
```

### 3. 查看低置信度路由

```bash
# 显示需要人工审核的路由
python -m scripts.generate_action_registry --show-low-confidence
```

这会列出置信度在 0.5-0.8 之间的路由，这些路由可能需要人工审核。

### 4. 按平台过滤

```bash
# 只分析特定平台
python -m scripts.generate_action_registry --platforms bilibili,zhihu,github
```

### 5. 调整置信度阈值

```bash
# 提高置信度要求
python -m scripts.generate_action_registry --min-confidence 0.8
```

### 6. 自定义输出路径

```bash
# 指定输出文件
python -m scripts.generate_action_registry --output my_config.json
```

## 推断规则

### 1. entity_type 推断

根据参数名推断实体类型：

| 参数名 | entity_type | 示例平台 |
|--------|-------------|----------|
| `uid`, `mid` | `user` | B站用户 |
| `column_id` | `column` | 知乎专栏 |
| `owner` + `repo` | `repo` | GitHub仓库 |
| `channel_id` | `channel` | 频道 |
| `topic_id` | `topic` | 话题 |

### 2. action 推断

根据路径模式推断动作：

| 路径模式 | action | 说明 |
|----------|--------|------|
| `/user/video` | `videos` | 用户投稿视频 |
| `/followings/video` | `following_videos` | 关注视频动态 |
| `/favorites` | `favorites` | 收藏 |
| `/user/dynamic` | `dynamics` | 动态 |
| `/zhuanlan` | `articles` | 知乎专栏文章 |
| `/commits` | `commits` | GitHub提交记录 |

### 3. 置信度计算

- 路径匹配 + 参数匹配 + name匹配 = **1.0**
- 路径匹配 + 参数匹配 = **0.9**
- 路径匹配 或 参数匹配 = **0.8**
- 仅name匹配 = **0.5**

## 配置文件格式

生成的配置文件 `action_registry_config.json` 格式：

```json
[
  {
    "platform": "bilibili",
    "entity_type": "user",
    "action": "videos",
    "display_name": "UP 主投稿视频",
    "path_template": "/user/video/:uid",
    "required_identifiers": ["uid"],
    "description": "获取UP主的投稿视频",
    "confidence": 1.0,
    "route_id": "bilibili_user-video"
  }
]
```

## 人工审核

对于置信度较低的路由（< 0.8），建议人工审核：

1. 运行 `--show-low-confidence` 查看低置信度路由
2. 检查推断的 `entity_type` 和 `action` 是否正确
3. 手动编辑生成的配置文件进行修正
4. 或者调整 `RouteAnalyzer` 的推断规则

## 典型工作流

```bash
# 1. 首次生成配置
python -m scripts.generate_action_registry

# 2. 查看低置信度路由
python -m scripts.generate_action_registry --show-low-confidence

# 3. 手动编辑配置文件（如需要）
vim services/subscription/action_registry_config.json

# 4. 查看统计
python -m scripts.generate_action_registry --stats-only

# 5. 重启应用加载新配置
python main.py
```

## 扩展推断规则

如果发现推断错误，可以修改 `services/subscription/route_analyzer.py`：

### 添加参数映射

```python
PARAMETER_TO_ENTITY_TYPE = {
    # 添加新的参数映射
    "my_param": "my_entity_type",
}
```

### 添加路径模式

```python
PATH_PATTERN_TO_ACTION = [
    # 添加新的路径模式（正则表达式）
    (r"/my/pattern", "my_action"),
]
```

### 添加关键词映射

```python
NAME_TO_ACTION = {
    # 添加新的关键词映射
    "我的关键词": "my_action",
}
```

## 故障排查

### 配置文件未生成

**问题**：运行脚本后没有生成配置文件

**解决**：
1. 检查 `route_process/datasource_definitions.json` 是否存在
2. 检查文件权限
3. 查看错误日志

### 推断结果不准确

**问题**：entity_type 或 action 推断错误

**解决**：
1. 使用 `--show-low-confidence` 查看问题路由
2. 手动编辑配置文件
3. 或者添加新的推断规则

### 平台缺失

**问题**：某些平台的路由没有被识别

**解决**：
1. 检查该平台的路由参数名是否在 `PARAMETER_TO_ENTITY_TYPE` 中
2. 检查路径模式是否在 `PATH_PATTERN_TO_ACTION` 中
3. 添加新的推断规则

## 相关文档

- 设计文档：`.agentdocs/subscription-system-design.md`
- 自动化方案：`.agentdocs/subscription-action-registry-automation.md`
- ActionRegistry 源码：`services/subscription/action_registry.py`
- RouteAnalyzer 源码：`services/subscription/route_analyzer.py`
