# ActionRegistry 自动化生成方案

> **问题**：不可能手动维护 ACTION_TEMPLATES，需要从 `datasource_definitions.json` 自动生成

---

## 核心思路

**从RSSHub路由定义自动推断 Entity-Action 映射**

```
RSSHub路由定义 (datasource_definitions.json)
  ↓ 自动分析
推断 entity_type + action
  ↓ 生成
ActionRegistry (配置驱动)
```

---

## 路由定义结构分析

### 示例1：B站用户关注视频

```json
{
  "route_id": "bilibili_followings-video",
  "path_template": ["/followings/video:uid/:embed?"],
  "name": "用户关注视频动态",
  "parameters": [
    {
      "name": "uid",
      "type": "string",
      "description": "用户 id",
      "required": true
    }
  ]
}
```

**推断结果：**
- platform: `bilibili`
- entity_type: `user` （从参数`:uid`推断）
- action: `following` （从路径`/followings/video`推断）
- path_template: `/followings/video/:uid`
- required_identifiers: `["uid"]`

### 示例2：知乎专栏文章

```json
{
  "route_id": "zhihu_zhuanlan",
  "path_template": ["/zhuanlan/:column_id"],
  "name": "专栏文章",
  "parameters": [
    {
      "name": "column_id",
      "type": "string",
      "description": "专栏 id",
      "required": true
    }
  ]
}
```

**推断结果：**
- platform: `zhihu`
- entity_type: `column` （从参数`:column_id`推断）
- action: `articles` （从name"专栏文章"推断）
- path_template: `/zhuanlan/:column_id`
- required_identifiers: `["column_id"]`

### 示例3：GitHub仓库commits

```json
{
  "route_id": "github_commits",
  "path_template": ["/github/commits/:owner/:repo"],
  "name": "提交记录",
  "parameters": [
    {
      "name": "owner",
      "type": "string",
      "description": "仓库所有者",
      "required": true
    },
    {
      "name": "repo",
      "type": "string",
      "description": "仓库名称",
      "required": true
    }
  ]
}
```

**推断结果：**
- platform: `github`
- entity_type: `repo` （从参数`:owner/:repo`推断）
- action: `commits` （从路径`/commits`推断）
- path_template: `/github/commits/:owner/:repo`
- required_identifiers: `["owner", "repo"]`

---

## 自动推断规则

### 规则1：参数名 → entity_type 映射

通过参数名推断实体类型：

```python
PARAMETER_TO_ENTITY_TYPE = {
    # B站
    "uid": "user",              # B站用户ID
    "mid": "user",              # B站用户ID（另一种叫法）

    # 知乎
    "column_id": "column",      # 知乎专栏
    "id": "user",               # 知乎用户（需结合platform判断）

    # 微博
    "uid": "user",              # 微博用户（需结合platform判断）

    # GitHub
    "owner": "repo",            # GitHub仓库所有者（与repo配对）
    "repo": "repo",             # GitHub仓库名称

    # 通用
    "user_id": "user",
    "channel_id": "channel",
    "topic_id": "topic",
    "tag": "tag"
}
```

### 规则2：路径模式 → action 映射

通过路径模式推断动作：

```python
PATH_PATTERN_TO_ACTION = {
    # B站动作
    r"/user/video": "videos",           # 用户投稿视频
    r"/followings/video": "following",  # 关注视频动态
    r"/user/followings": "followings",  # 关注列表
    r"/favorites": "favorites",         # 收藏
    r"/user/dynamic": "dynamics",       # 动态
    r"/user/coin": "coin",              # 投币视频
    r"/user/like": "like",              # 点赞视频

    # 知乎动作
    r"/zhuanlan": "articles",           # 专栏文章
    r"/people/activities": "activities", # 个人动态

    # GitHub动作
    r"/commits": "commits",             # 提交记录
    r"/issue": "issues",                # Issues
    r"/pull": "pull_requests",          # Pull Requests
    r"/release": "releases",            # 版本发布
}
```

### 规则3：name → action 映射（补充）

当路径模式不明确时，从 `name` 字段推断：

```python
NAME_TO_ACTION = {
    # 关键词映射
    "投稿": "videos",
    "视频列表": "videos",
    "关注": "following",
    "收藏": "favorites",
    "动态": "dynamics",
    "文章": "articles",
    "专栏": "articles",
    "提交": "commits",
    "Issue": "issues",
    "Pull Request": "pull_requests",
    "版本发布": "releases"
}
```

---

## 实现方案

### 1. 路由分析器 (RouteAnalyzer)

```python
# services/subscription/route_analyzer.py
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class AnalyzedRoute:
    """分析后的路由信息"""
    platform: str           # 平台（bilibili/zhihu/...）
    entity_type: str        # 实体类型（user/column/repo/...）
    action: str             # 动作（videos/following/...）
    path_template: str      # 路径模板
    required_identifiers: List[str]  # 必需标识符
    display_name: str       # 显示名称
    description: str        # 描述
    route_id: str          # 原始route_id
    confidence: float      # 推断置信度（0-1）


class RouteAnalyzer:
    """路由分析器

    从 datasource_definitions.json 中提取路由信息，
    自动推断 entity_type 和 action。
    """

    # 参数名 → 实体类型映射
    PARAMETER_TO_ENTITY_TYPE = {
        "uid": "user",
        "mid": "user",
        "user_id": "user",
        "column_id": "column",
        "owner": "repo",  # GitHub
        "repo": "repo",
        "channel_id": "channel",
        "topic_id": "topic",
    }

    # 路径模式 → 动作映射（正则表达式）
    PATH_PATTERN_TO_ACTION = [
        # B站
        (r"/user/video", "videos"),
        (r"/followings/video", "following"),
        (r"/user/followings", "followings_list"),
        (r"/favorites", "favorites"),
        (r"/user/dynamic", "dynamics"),
        (r"/user/coin", "coin"),
        (r"/user/like", "like"),

        # 知乎
        (r"/zhuanlan", "articles"),
        (r"/people/activities", "activities"),

        # GitHub
        (r"/commits", "commits"),
        (r"/issue", "issues"),
        (r"/pull", "pull_requests"),
        (r"/release", "releases"),
    ]

    # name关键词 → 动作映射
    NAME_TO_ACTION = {
        "投稿": "videos",
        "视频": "videos",
        "关注": "following",
        "收藏": "favorites",
        "动态": "dynamics",
        "文章": "articles",
        "专栏": "articles",
        "提交": "commits",
        "Issue": "issues",
        "Pull Request": "pull_requests",
        "版本": "releases",
    }

    def __init__(self, datasource_file: str = "route_process/datasource_definitions.json"):
        self.datasource_file = datasource_file
        self.routes_data = self._load_datasource_definitions()

    def _load_datasource_definitions(self) -> List[Dict]:
        """加载数据源定义"""
        with open(self.datasource_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def analyze_route(
        self,
        platform: str,
        route: Dict
    ) -> Optional[AnalyzedRoute]:
        """分析单个路由

        Args:
            platform: 平台标识（如"bilibili"）
            route: 路由定义字典

        Returns:
            分析后的路由信息，如果无法推断则返回None
        """
        route_id = route.get("route_id")
        path_template = route.get("path_template", [""])[0]
        name = route.get("name", "")
        description = route.get("description", "")
        parameters = route.get("parameters", [])

        # 1. 推断 entity_type
        entity_type = self._infer_entity_type(parameters, platform)
        if not entity_type:
            return None  # 无法推断实体类型

        # 2. 推断 action
        action = self._infer_action(path_template, name)
        if not action:
            return None  # 无法推断动作

        # 3. 提取必需标识符
        required_identifiers = [
            p["name"] for p in parameters if p.get("required", False)
        ]

        # 4. 计算置信度
        confidence = self._calculate_confidence(
            entity_type, action, path_template, name
        )

        return AnalyzedRoute(
            platform=platform,
            entity_type=entity_type,
            action=action,
            path_template=path_template,
            required_identifiers=required_identifiers,
            display_name=name,
            description=description,
            route_id=route_id,
            confidence=confidence
        )

    def _infer_entity_type(
        self,
        parameters: List[Dict],
        platform: str
    ) -> Optional[str]:
        """从参数推断实体类型"""
        for param in parameters:
            param_name = param.get("name")

            # GitHub特殊处理：owner+repo → repo
            if param_name in ["owner", "repo"] and platform == "github":
                return "repo"

            # 通用映射
            if param_name in self.PARAMETER_TO_ENTITY_TYPE:
                return self.PARAMETER_TO_ENTITY_TYPE[param_name]

        return None

    def _infer_action(
        self,
        path_template: str,
        name: str
    ) -> Optional[str]:
        """从路径模板和名称推断动作"""
        # 1. 先尝试路径模式匹配
        for pattern, action in self.PATH_PATTERN_TO_ACTION:
            if re.search(pattern, path_template):
                return action

        # 2. 如果路径匹配失败，尝试从name提取关键词
        for keyword, action in self.NAME_TO_ACTION.items():
            if keyword in name:
                return action

        return None

    def _calculate_confidence(
        self,
        entity_type: str,
        action: str,
        path_template: str,
        name: str
    ) -> float:
        """计算推断置信度

        置信度计算规则：
        - 路径匹配 + 参数匹配 = 1.0
        - 路径匹配 或 参数匹配 = 0.8
        - 仅name匹配 = 0.5
        """
        confidence = 0.5  # 基础置信度

        # 检查路径是否匹配
        path_matched = any(
            re.search(pattern, path_template)
            for pattern, _ in self.PATH_PATTERN_TO_ACTION
        )

        # 检查name是否匹配
        name_matched = any(
            keyword in name
            for keyword in self.NAME_TO_ACTION.keys()
        )

        if path_matched and name_matched:
            confidence = 1.0
        elif path_matched or name_matched:
            confidence = 0.8

        return confidence

    def analyze_all_routes(
        self,
        min_confidence: float = 0.5
    ) -> List[AnalyzedRoute]:
        """分析所有路由

        Args:
            min_confidence: 最小置信度阈值（默认0.5）

        Returns:
            分析后的路由列表
        """
        analyzed_routes = []

        for provider in self.routes_data:
            platform = provider.get("provider_id")
            routes = provider.get("routes", [])

            for route in routes:
                analyzed = self.analyze_route(platform, route)

                if analyzed and analyzed.confidence >= min_confidence:
                    analyzed_routes.append(analyzed)

        return analyzed_routes

    def generate_action_registry_config(
        self,
        output_file: str = "services/subscription/action_registry_config.json"
    ):
        """生成 ActionRegistry 配置文件

        自动分析所有路由并生成配置JSON。
        """
        analyzed_routes = self.analyze_all_routes()

        # 按 (platform, entity_type, action) 分组
        registry_config = {}

        for route in analyzed_routes:
            key = f"{route.platform}:{route.entity_type}:{route.action}"

            if key not in registry_config:
                registry_config[key] = {
                    "platform": route.platform,
                    "entity_type": route.entity_type,
                    "action": route.action,
                    "display_name": route.display_name,
                    "path_template": route.path_template,
                    "required_identifiers": route.required_identifiers,
                    "description": route.description,
                    "confidence": route.confidence,
                    "route_id": route.route_id
                }

        # 保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(
                list(registry_config.values()),
                f,
                ensure_ascii=False,
                indent=2
            )

        print(f"✅ 生成 ActionRegistry 配置: {output_file}")
        print(f"   共分析 {len(analyzed_routes)} 个路由")
        print(f"   生成 {len(registry_config)} 个 action 定义")

        return output_file
```

### 2. 修订后的 ActionRegistry（配置驱动）

```python
# services/subscription/action_registry.py
import json
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ActionDefinition:
    """动作定义"""
    action_name: str
    display_name: str
    path_template: str
    required_identifiers: List[str]
    description: str


class ActionRegistry:
    """动作注册表（配置驱动 v2.0）

    修订：不再手动维护 ACTION_TEMPLATES，
    而是从自动生成的配置文件加载。
    """

    _instance = None
    _actions: Dict[Tuple[str, str, str], ActionDefinition] = {}

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """从配置文件加载动作定义"""
        config_file = Path("services/subscription/action_registry_config.json")

        if not config_file.exists():
            print("⚠️ 警告：ActionRegistry 配置文件不存在，正在自动生成...")
            self._auto_generate_config()

        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # 加载到内存
        for item in config_data:
            key = (
                item["platform"],
                item["entity_type"],
                item["action"]
            )

            self._actions[key] = ActionDefinition(
                action_name=item["action"],
                display_name=item["display_name"],
                path_template=item["path_template"],
                required_identifiers=item["required_identifiers"],
                description=item["description"]
            )

        print(f"✅ ActionRegistry 加载完成：{len(self._actions)} 个动作")

    def _auto_generate_config(self):
        """自动生成配置文件（首次运行时）"""
        from services.subscription.route_analyzer import RouteAnalyzer

        analyzer = RouteAnalyzer()
        analyzer.generate_action_registry_config()

    @classmethod
    def get_action(
        cls,
        platform: str,
        entity_type: str,
        action: str
    ) -> Optional[ActionDefinition]:
        """获取动作定义"""
        instance = cls()
        return instance._actions.get((platform, entity_type, action))

    @classmethod
    def get_supported_actions(
        cls,
        platform: str,
        entity_type: str
    ) -> List[str]:
        """获取实体支持的所有动作"""
        instance = cls()
        actions = []

        for (p, et, action), _ in instance._actions.items():
            if p == platform and et == entity_type:
                actions.append(action)

        return actions

    @classmethod
    def build_path(
        cls,
        platform: str,
        entity_type: str,
        action: str,
        identifiers: Dict[str, str]
    ) -> Optional[str]:
        """构建RSSHub路径"""
        action_def = cls.get_action(platform, entity_type, action)
        if not action_def:
            return None

        # 检查必需的标识符
        for req_id in action_def.required_identifiers:
            if req_id not in identifiers:
                raise ValueError(
                    f"缺少必需的标识符: {req_id}，"
                    f"需要: {action_def.required_identifiers}"
                )

        # 替换路径模板中的占位符
        path = action_def.path_template
        for key, value in identifiers.items():
            path = path.replace(f":{key}", str(value))

        return path

    @classmethod
    def reload(cls):
        """重新加载配置（用于配置文件更新后）"""
        if cls._instance:
            cls._instance._actions.clear()
            cls._instance._load_config()
```

### 3. 初始化脚本

```python
# scripts/generate_action_registry.py
"""
生成 ActionRegistry 配置文件

运行方式：
    python -m scripts.generate_action_registry
"""

from services.subscription.route_analyzer import RouteAnalyzer

def main():
    print("开始分析 RSSHub 路由定义...")

    analyzer = RouteAnalyzer(
        datasource_file="route_process/datasource_definitions.json"
    )

    # 生成配置文件
    config_file = analyzer.generate_action_registry_config(
        output_file="services/subscription/action_registry_config.json"
    )

    print("\n✅ 完成！")
    print(f"   配置文件: {config_file}")
    print("\n下一步：")
    print("   1. 检查生成的配置文件")
    print("   2. 对于置信度较低的路由，手动调整entity_type和action")
    print("   3. 重启应用以加载新配置")

if __name__ == "__main__":
    main()
```

---

## 使用流程

### 首次使用

```bash
# 1. 生成 ActionRegistry 配置
python -m scripts.generate_action_registry

# 2. 查看生成的配置
cat services/subscription/action_registry_config.json

# 3. （可选）手动调整置信度较低的路由

# 4. 重启应用
python main.py
```

### 配置文件格式

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
  },
  {
    "platform": "bilibili",
    "entity_type": "user",
    "action": "following",
    "display_name": "用户关注视频动态",
    "path_template": "/followings/video/:uid/:embed?",
    "required_identifiers": ["uid"],
    "description": "获取用户关注的视频动态",
    "confidence": 1.0,
    "route_id": "bilibili_followings-video"
  }
]
```

---

## 修订后的 QueryParser（移除规则引擎）

```python
# services/subscription/query_parser.py
from typing import Optional, Dict, Any
from pydantic import BaseModel

class ParsedQuery(BaseModel):
    """解析后的查询结构"""
    entity_name: str
    entity_type: str
    action: str
    platform: str
    filters: Dict[str, Any] = {}


class QueryParser:
    """查询解析器（修订版 - 移除规则引擎）

    修订：绝对不使用规则引擎，始终使用LLM解析。
    """

    def __init__(self):
        from query_processor.llm_client import create_llm_client_auto
        self.llm = create_llm_client_auto()

    def parse(self, query: str) -> Optional[ParsedQuery]:
        """解析自然语言查询

        Args:
            query: 自然语言查询

        Returns:
            解析后的结构化对象，如果无法解析则返回 None
        """
        return self._parse_with_llm(query)

    def _parse_with_llm(self, query: str) -> Optional[ParsedQuery]:
        """使用 LLM 解析（唯一方法）"""
        prompt = f"""
你是一个智能查询解析器。请将用户的自然语言查询解析为结构化JSON。

用户查询: "{query}"

请提取以下信息：
1. entity_name: 实体名称（UP主/专栏/博主的名字，如"科技美学"）
2. entity_type: 实体类型（user/column/repo）
3. action: 动作名称（videos/following/favorites/dynamics等）
4. platform: 平台（bilibili/zhihu/weibo/github）
5. filters: 可选过滤条件（如时间范围、数量限制）

**重要**：entity_type 和 action 是两个不同的概念！
- entity_type 描述实体本身（是用户、专栏还是仓库）
- action 描述对实体的具体操作（看投稿、看关注、看收藏）

支持的平台、实体类型和动作：

B站 (bilibili):
- entity_type: user
  - action: videos (投稿视频)
  - action: following (关注列表)
  - action: favorites (收藏)
  - action: dynamics (动态)
  - action: coin (投币视频)
  - action: like (点赞视频)

知乎 (zhihu):
- entity_type: column
  - action: articles (专栏文章)
- entity_type: user
  - action: activities (个人动态)

微博 (weibo):
- entity_type: user
  - action: posts (微博)

GitHub (github):
- entity_type: repo
  - action: commits (提交记录)
  - action: issues (Issues)
  - action: pull_requests (Pull Requests)
  - action: releases (版本发布)

输出格式（JSON）：
{{
  "entity_name": "...",
  "entity_type": "...",
  "action": "...",
  "platform": "...",
  "filters": {{}}
}}

示例：
- "科技美学的最新投稿" → {{"entity_name": "科技美学", "entity_type": "user", "action": "videos", "platform": "bilibili"}}
- "科技美学的关注列表" → {{"entity_name": "科技美学", "entity_type": "user", "action": "following", "platform": "bilibili"}}
- "langchain的最新commits" → {{"entity_name": "langchain", "entity_type": "repo", "action": "commits", "platform": "github"}}

如果无法解析，返回 null。
"""

        response = self.llm.generate(prompt)

        try:
            import json
            parsed_json = json.loads(response)
            if not parsed_json:
                return None

            return ParsedQuery(
                entity_name=parsed_json["entity_name"],
                entity_type=parsed_json["entity_type"],
                action=parsed_json["action"],
                platform=parsed_json["platform"],
                filters=parsed_json.get("filters", {})
            )
        except Exception as e:
            logger.error(f"LLM解析失败: {e}")
            return None
```

---

## 优势

### 1. **完全自动化**
- ✅ 无需手动维护 ACTION_TEMPLATES
- ✅ 新增RSSHub路由自动识别
- ✅ 一键生成配置

### 2. **智能推断**
- ✅ 从参数名推断entity_type（`:uid` → `user`）
- ✅ 从路径推断action（`/followings/video` → `following`）
- ✅ 置信度评分（高置信度自动使用，低置信度人工审核）

### 3. **可扩展**
- ✅ 支持任意平台（B站/知乎/微博/GitHub/...）
- ✅ 支持任意动作（投稿/关注/收藏/...）
- ✅ 配置文件可人工调整

### 4. **绝对不使用规则引擎**
- ✅ QueryParser 移除 `_parse_with_rules` 方法
- ✅ 始终使用 LLM 解析用户查询
- ✅ 保证灵活性和容错性

---

## 实施计划

### Phase 1: 路由分析器（1-2天）
- [ ] 实现 RouteAnalyzer
- [ ] 实现推断规则（参数→entity_type，路径→action）
- [ ] 测试自动生成配置

### Phase 2: 配置驱动 ActionRegistry（1天）
- [ ] 修订 ActionRegistry 为配置加载模式
- [ ] 实现自动生成脚本
- [ ] 生成初始配置文件

### Phase 3: QueryParser 修订（半天）
- [ ] 移除 `_parse_with_rules` 方法
- [ ] 确保始终使用 LLM 解析
- [ ] 更新 Prompt 模板

### Phase 4: 人工审核与调优（1-2天）
- [ ] 检查自动生成的配置文件
- [ ] 调整置信度较低的路由
- [ ] 补充缺失的entity_type和action定义

### Phase 5: 集成测试（1天）
- [ ] 测试完整流程（用户查询 → 路由生成 → RSSHub调用）
- [ ] 测试各平台各动作
- [ ] 验收完成

---

**方案制定时间**：2025-11-13
**修订原因**：
1. 不可能手动维护 ACTION_TEMPLATES
2. 绝对不能使用规则引擎解析查询

**核心改进**：
- 从 datasource_definitions.json 自动生成 ActionRegistry 配置
- 移除规则引擎，始终使用 LLM 解析
- 配置驱动，灵活扩展

**文档版本**：v1.0
