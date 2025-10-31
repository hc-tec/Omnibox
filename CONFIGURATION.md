# 配置指南

本项目使用 **Pydantic Settings** 管理配置，这是 Python 的最佳实践。

## 快速开始

### 1. 复制配置模板

```bash
cp .env.example .env
```

### 2. 编辑 .env 文件

```bash
# 使用你喜欢的编辑器
nano .env
# 或
vim .env
# 或
code .env
```

### 3. 填写必要配置

```env
# 最少只需要这一个
OPENAI_API_KEY=sk-your-key-here
```

### 4. 运行系统

```python
from orchestrator.rag_in_action import create_rag_in_action

# 配置会自动从.env加载
ria = create_rag_in_action()
```

## 配置层次

### 优先级（从高到低）

1. **代码中显式传入的参数**
2. **环境变量**
3. **.env 文件**
4. **默认值**

示例：

```python
from query_processor.llm_client import OpenAIClient

# 方式1：代码中传入（最高优先级）
client = OpenAIClient(api_key="sk-xxx", model="gpt-4")

# 方式2：从环境变量读取
# export OPENAI_API_KEY=sk-xxx
client = OpenAIClient()

# 方式3：从.env文件读取（最常用）
# .env文件中: OPENAI_API_KEY=sk-xxx
client = OpenAIClient()

# 方式4：使用默认值
# 会使用 config.py 中定义的默认值
```

## 配置项详解

### LLM 配置

#### OpenAI

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `OPENAI_API_KEY` | str | None | **必填**，OpenAI API密钥 |
| `OPENAI_MODEL` | str | gpt-4o-mini | 模型名称 |
| `OPENAI_BASE_URL` | str | None | 自定义API端点（可选） |

**获取API Key**：
- 访问 https://platform.openai.com/api-keys
- 创建新的API Key
- 复制到 `.env` 文件

**模型选择**：
- `gpt-4o`：最新最强（推荐）
- `gpt-4o-mini`：更便宜，速度快（默认）
- `gpt-4-turbo`：旧版GPT-4
- `gpt-3.5-turbo`：最便宜

#### Anthropic Claude

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `ANTHROPIC_API_KEY` | str | None | **必填**，Anthropic API密钥 |
| `ANTHROPIC_MODEL` | str | claude-3-5-sonnet-20241022 | 模型名称 |
| `ANTHROPIC_BASE_URL` | str | None | 自定义API端点（可选） |

**获取API Key**：
- 访问 https://console.anthropic.com/
- 创建API Key

**模型选择**：
- `claude-3-5-sonnet-20241022`：最新最强（推荐，默认）
- `claude-3-opus-20240229`：旧版最强
- `claude-3-haiku-20240307`：最快最便宜

**使用代理**：
```env
# 方式1：使用 base_url（推荐）
ANTHROPIC_BASE_URL=https://api.anthropic-proxy.com

# 方式2：系统代理环境变量
HTTP_PROXY=http://proxy.com:8080
HTTPS_PROXY=http://proxy.com:8080
```

#### 通用LLM参数

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `LLM_PROVIDER` | str | openai | LLM提供商 |
| `LLM_TEMPERATURE` | float | 0.1 | 生成温度（0-2） |
| `LLM_MAX_TOKENS` | int | 1500 | 最大token数 |
| `LLM_MAX_RETRIES` | int | 2 | 重试次数 |

### Prompt 配置

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `PROMPT_MAX_TOOLS` | int | 3 | 向LLM展示几个工具 |
| `PROMPT_MAX_TOOL_LENGTH` | int | 2000 | 单个工具JSON最大长度 |
| `PROMPT_USE_SIMPLE_PROMPT` | bool | false | 使用简化版Prompt |

### 路径配置

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `PATH_PATH_PREFIX` | str | "" | 路径前缀 |

### RSSHub 配置

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `RSSHUB_BASE_URL` | str | http://localhost:1200 | 本地RSSHub服务地址 |
| `RSSHUB_FALLBACK_URL` | str | https://rsshub.app | 本地不可用时的降级地址 |
| `RSSHUB_HEALTH_CHECK_TIMEOUT` | int | 3 | 健康检查超时时间（秒） |
| `RSSHUB_REQUEST_TIMEOUT` | int | 30 | RSS请求超时时间（秒） |
| `RSSHUB_MAX_RETRIES` | int | 2 | 请求失败重试次数 |

**重要说明**：

本系统**默认使用本地RSSHub服务**，这样可以：
- 避免公共RSSHub限流
- 提升响应速度
- 保护隐私
- 支持自定义配置

**启动本地RSSHub服务**：

```bash
# 进入部署目录
cd deploy

# 启动Docker Compose服务
docker-compose up -d

# 验证服务启动成功
curl http://localhost:1200/
# 应该看到RSSHub欢迎页面

# 查看服务状态
docker-compose ps

# 查看日志（如有问题）
docker-compose logs rsshub

# 停止服务
# docker-compose down
```

**服务组件**：
- `rsshub`：RSSHub主服务（端口1200）
- `redis`：缓存服务
- `browserless`：浏览器渲染支持

**降级机制**：

系统会自动检测本地RSSHub健康状态：
- ✅ 本地服务正常 → 使用 `RSSHUB_BASE_URL`（默认 http://localhost:1200）
- ❌ 本地服务不可用 → 自动降级到 `RSSHUB_FALLBACK_URL`（默认 https://rsshub.app）

降级时会在日志中明确标记，并在响应中返回 `source: "fallback"` 字段。

**配置示例**：

```env
# 默认配置（推荐）
RSSHUB_BASE_URL=http://localhost:1200
RSSHUB_FALLBACK_URL=https://rsshub.app

# 使用自定义部署
RSSHUB_BASE_URL=http://192.168.1.100:1200

# 调整超时时间
RSSHUB_HEALTH_CHECK_TIMEOUT=5
RSSHUB_REQUEST_TIMEOUT=60
```

## 使用技巧

### 1. 本地开发

创建 `.env.local`（也会被git忽略）：

```env
# .env.local - 本地开发配置
OPENAI_API_KEY=sk-dev-key
LLM_TEMPERATURE=0.3  # 开发时可以稍高一点
```

加载本地配置：

```python
from query_processor.config import LLMSettings
from pydantic_settings import SettingsConfigDict

class DevLLMSettings(LLMSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
    )

# 使用开发配置
settings = DevLLMSettings()
```

### 2. 多环境配置

```python
import os

# 根据环境加载不同配置
env = os.getenv("APP_ENV", "development")

env_file = {
    "development": ".env.dev",
    "staging": ".env.staging",
    "production": ".env.prod",
}.get(env, ".env")

from query_processor.config import LLMSettings

settings = LLMSettings(_env_file=env_file)
```

### 3. 配置验证

```python
from query_processor.config import llm_settings

# 检查配置是否有效
if not llm_settings.openai_api_key:
    raise ValueError("请设置 OPENAI_API_KEY")

# 打印配置（注意：会显示敏感信息）
print(llm_settings.model_dump())

# 安全打印（隐藏敏感信息）
print(llm_settings.model_dump(exclude={"openai_api_key", "anthropic_api_key"}))
```

### 4. 动态修改配置

```python
from query_processor.config import llm_settings

# 临时修改（仅在运行时生效）
llm_settings.llm_temperature = 0.5

# 重新加载配置
from query_processor.config import reload_settings
reload_settings()
```

## 安全最佳实践

### ✅ 推荐做法

1. **使用 .env 文件**
   ```env
   OPENAI_API_KEY=sk-xxx
   ```

2. **添加到 .gitignore**
   ```gitignore
   .env
   .env.local
   .env.*.local
   ```

3. **使用环境变量（生产环境）**
   ```bash
   # 服务器上设置
   export OPENAI_API_KEY=sk-xxx
   ```

4. **使用密钥管理服务**
   - AWS Secrets Manager
   - Azure Key Vault
   - Google Secret Manager

### ❌ 不要这样做

1. **不要硬编码密钥**
   ```python
   # ❌ 危险！
   api_key = "sk-1234567890abcdef"
   ```

2. **不要提交 .env 到 Git**
   ```bash
   # ❌ 危险！
   git add .env
   git commit -m "add config"
   ```

3. **不要在日志中打印密钥**
   ```python
   # ❌ 危险！
   logger.info(f"Using API key: {api_key}")
   ```

## 故障排除

### 问题1：配置未生效

**检查优先级**：

```python
from query_processor.config import llm_settings

# 1. 检查配置值
print(f"API Key: {llm_settings.openai_api_key}")

# 2. 检查.env文件位置
# .env应该在项目根目录（D:\AIProject\omni\.env）

# 3. 检查环境变量
import os
print(f"ENV: {os.getenv('OPENAI_API_KEY')}")
```

### 问题2：找不到.env文件

**确保.env在正确位置**：

```
D:\AIProject\omni/
├── .env              ← 这里
├── .env.example
├── rag_system/
├── query_processor/
└── orchestrator/
```

### 问题3：pydantic-settings 未安装

```bash
pip install pydantic-settings python-dotenv
```

## 配置示例

### 基础配置（OpenAI）

```env
# .env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxx
```

### 完整配置（OpenAI + 自定义）

```env
# .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1

LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2000
LLM_MAX_RETRIES=3

PROMPT_MAX_TOOLS=5
PROMPT_MAX_TOOL_LENGTH=3000
```

### Anthropic 配置

```env
# .env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-3-sonnet-20240229
```

### 代理配置（OpenAI）

```env
# .env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://your-proxy.com/v1
```

### 代理配置（Anthropic）

```env
# .env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_BASE_URL=https://your-anthropic-proxy.com

# 或使用系统代理
# HTTP_PROXY=http://proxy.com:8080
# HTTPS_PROXY=http://proxy.com:8080
```

### 同时使用两个LLM

```env
# .env - 同时配置 OpenAI 和 Anthropic
LLM_PROVIDER=openai  # 默认使用OpenAI

OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini

ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

代码中切换：

```python
from query_processor.llm_client import create_llm_client

# 使用 OpenAI
openai_client = create_llm_client("openai")

# 使用 Anthropic
anthropic_client = create_llm_client("anthropic")

# 比较两个模型的结果
openai_result = openai_client.generate("你好")
anthropic_result = anthropic_client.generate("你好")
```

## 参考资料

- [Pydantic Settings 文档](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [python-dotenv 文档](https://github.com/theskumar/python-dotenv)
- [12-Factor App 配置原则](https://12factor.net/config)
