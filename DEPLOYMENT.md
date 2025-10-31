# RSS聚合系统 - 部署文档

本文档详细说明如何部署RSS聚合系统，包括开发环境、测试环境和生产环境。

## 目录

- [系统架构](#系统架构)
- [前置要求](#前置要求)
- [快速开始](#快速开始)
- [环境配置](#环境配置)
- [RSSHub部署](#rsshub部署)
- [应用部署](#应用部署)
- [运维监控](#运维监控)
- [故障排查](#故障排查)

---

## 系统架构

```
┌─────────────────┐
│  FastAPI App    │ ← REST API + WebSocket
│  (Port 8000)    │
└────────┬────────┘
         │
         ├─→ ChatService (Service层)
         │   └─→ DataQueryService
         │       ├─→ RAGInAction (RAG检索)
         │       ├─→ DataExecutor (RSS获取)
         │       └─→ CacheService (TTL缓存)
         │
         └─→ RSSHub服务
             ├─→ 本地RSSHub (localhost:1200) ← 优先
             └─→ 公共RSSHub (rsshub.app)    ← 降级
```

### 服务依赖关系

1. **RSSHub** (可选但推荐) - RSS数据源
2. **Redis** (RSSHub依赖) - RSSHub缓存
3. **Browserless** (可选) - RSSHub渲染动态内容
4. **向量数据库** (必需) - RAG检索
5. **FastAPI应用** (必需) - API服务

---

## 前置要求

### 硬件要求

**最低配置**:
- CPU: 2核
- 内存: 4GB
- 磁盘: 10GB

**推荐配置**:
- CPU: 4核+
- 内存: 8GB+
- 磁盘: 20GB+

### 软件要求

- **Docker** >= 20.10
- **Docker Compose** >= 2.0
- **Python** >= 3.10
- **Git**

**安装Docker和Docker Compose** (如未安装):

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io docker-compose-plugin

# CentOS/RHEL
sudo yum install docker docker-compose-plugin

# macOS
brew install docker docker-compose

# Windows
# 下载并安装 Docker Desktop: https://www.docker.com/products/docker-desktop
```

---

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd omni
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置（必须配置OPENAI_API_KEY）
vim .env
```

**最小化配置** (.env):
```bash
# LLM配置（必填）
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini

# RSSHub配置（使用默认值即可）
RSSHUB_BASE_URL=http://localhost:1200
RSSHUB_FALLBACK_URL=https://rsshub.app
```

### 3. 启动RSSHub服务（推荐）

```bash
cd deploy
docker-compose up -d

# 验证服务
docker-compose ps
curl http://localhost:1200/healthz
```

### 4. 安装Python依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 5. 初始化RAG系统

```bash
# 构建向量索引（首次运行）
python rag_system/main.py --build-index

# 验证索引
python rag_system/main.py --test-query "虎扑步行街"
```

### 6. 启动API服务

```bash
# 开发模式（带热重载）
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload

# 生产模式
uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

### 7. 验证部署

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 测试对话接口
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "虎扑步行街最新帖子"}'

# 查看运维指标
curl http://localhost:8000/api/v1/metrics
```

---

## 环境配置

### .env配置详解

完整的环境变量配置说明：

```bash
# ============================================================
# LLM 配置
# ============================================================

# LLM提供商选择
LLM_PROVIDER=openai              # openai | anthropic | custom

# OpenAI配置
OPENAI_API_KEY=sk-xxx            # 必填，从 https://platform.openai.com/api-keys 获取
OPENAI_MODEL=gpt-4o-mini         # 模型选择：gpt-4o-mini（推荐）| gpt-4o | gpt-4-turbo
OPENAI_BASE_URL=                 # 可选，代理地址

# LLM生成参数
LLM_TEMPERATURE=0.1              # 温度：0.0-2.0，越低越确定
LLM_MAX_TOKENS=1500              # 最大token数
LLM_MAX_RETRIES=2                # 失败重试次数

# ============================================================
# RSSHub 配置
# ============================================================

# RSSHub服务地址
RSSHUB_BASE_URL=http://localhost:1200      # 本地RSSHub（优先使用）
RSSHUB_FALLBACK_URL=https://rsshub.app     # 降级地址（本地不可用时）

# 超时和重试设置
RSSHUB_HEALTH_CHECK_TIMEOUT=3    # 健康检查超时（秒）
RSSHUB_REQUEST_TIMEOUT=30        # RSS请求超时（秒）
RSSHUB_MAX_RETRIES=2             # 请求失败重试次数

# ============================================================
# API服务配置
# ============================================================

# 服务模式（仅影响测试）
CHAT_SERVICE_MODE=auto           # auto（推荐）| mock（测试）| production（强制真实服务）

# 日志级别
LOG_LEVEL=INFO                   # DEBUG | INFO | WARNING | ERROR

# ============================================================
# RAG配置
# ============================================================
# 注意：RAG配置在 rag_system/config.py 中
# 包括向量模型、向量数据库路径等
```

### 配置优先级

1. **环境变量** (.env文件或系统环境变量) - 最高优先级
2. **默认配置** (代码中的默认值) - 最低优先级

### 环境特定配置

#### 开发环境

```bash
# .env.development
CHAT_SERVICE_MODE=auto
LOG_LEVEL=DEBUG
RSSHUB_BASE_URL=http://localhost:1200
```

#### 测试环境

```bash
# .env.test
CHAT_SERVICE_MODE=mock           # 无需真实依赖
LOG_LEVEL=INFO
```

#### 生产环境

```bash
# .env.production
CHAT_SERVICE_MODE=production     # 强制真实服务
LOG_LEVEL=INFO
RSSHUB_BASE_URL=http://rsshub:1200  # Docker内部网络
```

---

## RSSHub部署

### 使用Docker Compose部署（推荐）

**位置**: `deploy/docker-compose.yml`

```bash
cd deploy
docker-compose up -d
```

**服务说明**:

1. **rsshub** - RSSHub主服务 (端口1200)
2. **redis** - Redis缓存 (内部端口6379)
3. **browserless** - 无头浏览器 (内部端口3000)

### 验证RSSHub部署

```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f rsshub

# 健康检查
curl http://localhost:1200/healthz

# 测试RSS获取
curl http://localhost:1200/bilibili/user/video/2
```

### RSSHub配置说明

**环境变量** (deploy/docker-compose.yml):

```yaml
environment:
  NODE_ENV: production
  CACHE_TYPE: redis                          # 使用Redis缓存
  REDIS_URL: 'redis://redis:6379/'          # Redis连接地址
  PUPPETEER_WS_ENDPOINT: 'ws://browserless:3000'  # 无头浏览器（可选）

  # Cookie配置（按需添加）
  BILIBILI_COOKIE_<UID>: "your_cookie_here"
  ZHIHU_COOKIES: "your_cookie_here"
  XIAOHONGSHU_COOKIE: "your_cookie_here"
```

**持久化存储**:

Redis数据存储在Docker卷 `redis-data` 中，容器重启不会丢失数据。

### 停止和重启RSSHub

```bash
# 停止服务
docker-compose down

# 停止并删除数据
docker-compose down -v

# 重启服务
docker-compose restart

# 查看资源使用
docker stats
```

---

## 应用部署

### 方式1：直接运行（开发环境）

```bash
# 激活虚拟环境
source venv/bin/activate

# 启动应用（带热重载）
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

### 方式2：生产模式（多进程）

```bash
# 使用Gunicorn + Uvicorn Workers
gunicorn api.app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

**参数说明**:
- `--workers 4` - 4个工作进程（推荐CPU核心数×2）
- `--timeout 120` - 请求超时120秒
- `--access-logfile -` - 访问日志输出到stdout
- `--error-logfile -` - 错误日志输出到stderr

### 方式3：使用systemd（Linux生产环境）

创建systemd服务文件 `/etc/systemd/system/rss-api.service`:

```ini
[Unit]
Description=RSS Aggregation API Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/omni
Environment="PATH=/path/to/omni/venv/bin"
EnvironmentFile=/path/to/omni/.env
ExecStart=/path/to/omni/venv/bin/gunicorn api.app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**管理服务**:

```bash
# 启动服务
sudo systemctl start rss-api

# 设置开机自启
sudo systemctl enable rss-api

# 查看状态
sudo systemctl status rss-api

# 查看日志
sudo journalctl -u rss-api -f

# 重启服务
sudo systemctl restart rss-api
```

### 方式4：使用Docker（完整容器化）

创建 `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["gunicorn", "api.app:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

**构建和运行**:

```bash
# 构建镜像
docker build -t rss-api:latest .

# 运行容器
docker run -d \
  --name rss-api \
  --env-file .env \
  -p 8000:8000 \
  --network deploy_default \
  rss-api:latest

# 查看日志
docker logs -f rss-api
```

---

## 启动顺序

### 标准启动流程

```bash
# 1. 启动RSSHub服务（可选但推荐）
cd deploy
docker-compose up -d
sleep 10  # 等待服务完全启动

# 2. 验证RSSHub
curl http://localhost:1200/healthz

# 3. 初始化RAG索引（首次部署）
cd ..
source venv/bin/activate
python rag_system/main.py --build-index

# 4. 启动API服务
uvicorn api.app:app --host 0.0.0.0 --port 8000

# 5. 验证API服务
curl http://localhost:8000/api/v1/health
```

### 依赖检查

应用启动时会自动检查依赖：

1. **RSSHub健康检查** - 检查本地RSSHub是否可用
   - ✅ 可用 → 使用本地服务
   - ❌ 不可用 → 自动降级到公共RSSHub

2. **RAG索引检查** - 检查向量索引是否存在
   - ✅ 存在 → 正常加载
   - ❌ 不存在 → 提示需要构建索引

3. **LLM配置检查** - 检查API密钥是否配置
   - ✅ 已配置 → 正常初始化
   - ❌ 未配置 → 启动失败（生产模式）

### 服务模式

应用支持3种服务模式（通过`CHAT_SERVICE_MODE`环境变量控制）：

**1. auto模式（默认，推荐）**:
```bash
CHAT_SERVICE_MODE=auto uvicorn api.app:app
```
- 尝试初始化真实服务
- 如果失败，自动回退到Mock模式
- 适合开发和测试环境

**2. mock模式**:
```bash
CHAT_SERVICE_MODE=mock uvicorn api.app:app
```
- 直接使用Mock服务
- 无需RAG/LLM/RSSHub依赖
- 适合快速测试和CI环境

**3. production模式**:
```bash
CHAT_SERVICE_MODE=production uvicorn api.app:app
```
- 必须成功初始化真实服务
- 任何依赖缺失都会导致启动失败
- 适合生产环境

---

## 运维监控

### 健康检查端点

**GET /api/v1/health**

返回示例:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "mode": "production",
  "services": {
    "chat_service": "ready",
    "rsshub": "local",      // local | fallback | unknown
    "rag": "ready",
    "cache": "ready"
  }
}
```

### 运维指标端点

**GET /api/v1/metrics**

返回示例:
```json
{
  "status": "success",
  "data": {
    "uptime_hours": 12.5,
    "cache": {
      "rag_hit_rate": "85.3%",
      "rss_hit_rate": "72.1%"
    },
    "rsshub": {
      "fallback_rate": "5.2%",
      "local_success": 1850,
      "fallback_success": 102
    },
    "api": {
      "total_requests": 2500,
      "success_rate": "98.4%"
    },
    "performance": {
      "avg_response_time": "0.452s",
      "p95_response_time": "1.234s"
    }
  }
}
```

### 日志监控

**日志格式**:

所有关键操作使用统一的结构化日志格式：

```
# RSSHub源切换
[RSSHub切换] local → fallback | 原因: 健康检查失败 | 路径: /bilibili/user/video/2

# RSSHub错误
[RSSHub错误] 来源: local | 类型: http_error | 错误: 连接超时 | HTTP: 504

# 缓存事件
[缓存事件] 类型: rag | 事件: hit | 键: query:虎扑步行街 | 命中: true

# API请求
[API请求] POST /api/v1/chat | 状态: 200 | 耗时: 0.523s

# WebSocket事件
[WebSocket] [stream-abc123] connect | 客户端已连接
```

**查看实时日志**:

```bash
# 应用日志
tail -f logs/app.log

# RSSHub日志
cd deploy
docker-compose logs -f rsshub

# 按级别过滤
tail -f logs/app.log | grep ERROR
tail -f logs/app.log | grep "RSSHub切换"
```

### Prometheus集成（可选）

指标收集器已实现，可轻松对接Prometheus：

```python
# monitoring/prometheus_exporter.py (待实现)
from prometheus_client import Counter, Histogram, Gauge
from monitoring import get_metrics_collector

# 导出指标到Prometheus格式
```

---

## 故障排查

### 问题1：RSSHub无法访问

**症状**:
```
[RSSHub错误] 来源: local | 类型: request_error | 错误: 连接拒绝
```

**解决方案**:

```bash
# 1. 检查RSSHub服务是否运行
cd deploy
docker-compose ps

# 2. 检查端口是否开放
netstat -tuln | grep 1200
# 或
ss -tuln | grep 1200

# 3. 检查防火墙
sudo ufw status
sudo ufw allow 1200

# 4. 重启RSSHub
docker-compose restart rsshub

# 5. 查看RSSHub日志
docker-compose logs rsshub | tail -100
```

### 问题2：RAG索引未找到

**症状**:
```
FileNotFoundError: RAG索引文件不存在
```

**解决方案**:

```bash
# 1. 构建RAG索引
python rag_system/main.py --build-index

# 2. 验证索引文件
ls -lh rag_system/indexes/

# 3. 如果构建失败，检查工具JSON
ls -lh tools/
cat tools/rsshub_routes.json | jq . | head
```

### 问题3：API响应慢

**症状**:
- 响应时间超过5秒
- P95响应时间过高

**排查步骤**:

```bash
# 1. 查看运维指标
curl http://localhost:8000/api/v1/metrics | jq .

# 2. 检查缓存命中率
# 如果命中率低，考虑：
# - 增加缓存TTL
# - 预热热门查询

# 3. 检查RSSHub降级率
# 如果降级率高，考虑：
# - 增加本地RSSHub资源
# - 优化健康检查策略

# 4. 检查系统资源
top
htop
docker stats

# 5. 分析慢查询日志
tail -f logs/app.log | grep "耗时: [5-9]"
```

### 问题4：内存占用过高

**症状**:
- 应用内存持续增长
- OOM (Out of Memory) 错误

**解决方案**:

```bash
# 1. 检查缓存大小
# 缓存默认保留最近1000个响应时间记录
# 如果需要调整，修改 monitoring/metrics.py

# 2. 限制工作进程数
gunicorn api.app:app --workers 2  # 减少worker数量

# 3. 定期重启服务（临时方案）
# 使用systemd Restart策略

# 4. 启用内存分析
pip install memory_profiler
python -m memory_profiler api/app.py
```

### 问题5：WebSocket连接断开

**症状**:
```
[WebSocket] [stream-abc123] disconnect | 连接已关闭
```

**排查步骤**:

```bash
# 1. 检查反向代理配置（如Nginx）
# WebSocket需要特殊配置

# Nginx配置示例：
location /api/v1/chat/stream {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
}

# 2. 检查超时设置
# Gunicorn超时设置
gunicorn --timeout 300 api.app:app

# 3. 测试WebSocket连接
pip install websockets
python -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:8000/api/v1/chat/stream') as ws:
        await ws.send(json.dumps({'query': '测试'}))
        async for msg in ws:
            print(msg)
            break
asyncio.run(test())
"
```

### 问题6：测试失败

**症状**:
```
FAILED tests/api/test_chat_controller.py::test_chat_basic_query
```

**解决方案**:

```bash
# 1. 使用Mock模式运行测试
CHAT_SERVICE_MODE=mock pytest tests/

# 2. 查看详细错误信息
pytest tests/ -v --tb=long

# 3. 单独运行失败的测试
pytest tests/api/test_chat_controller.py::test_chat_basic_query -v

# 4. 检查依赖安装
pip install -r requirements.txt --upgrade

# 5. 清理缓存重新测试
pytest --cache-clear tests/
```

---

## 性能优化建议

### 1. 缓存优化

```python
# config/settings.py
RAG_CACHE_TTL = 3600      # RAG缓存1小时
RSS_CACHE_TTL = 600       # RSS缓存10分钟

# 根据实际情况调整TTL
# - 数据更新频繁：降低TTL
# - 数据相对静态：提高TTL
```

### 2. 并发优化

```bash
# 增加Uvicorn workers
uvicorn api.app:app --workers 8

# 或使用Gunicorn
gunicorn api.app:app \
  --workers 8 \
  --worker-class uvicorn.workers.UvicornWorker
```

### 3. RSSHub优化

```yaml
# deploy/docker-compose.yml
services:
  rsshub:
    environment:
      # 增加缓存时间
      CACHE_EXPIRE: 3600

      # 启用请求去重
      REQUEST_DEDUPE: 'true'
```

### 4. 数据库优化

```python
# 如果使用向量数据库，优化索引参数
# rag_system/config.py
FAISS_INDEX_TYPE = "IVF100,Flat"  # 根据数据量调整
```

---

## 安全建议

### 1. 环境变量保护

```bash
# 确保.env文件权限正确
chmod 600 .env

# 不要将.env文件提交到Git
echo ".env" >> .gitignore
```

### 2. API访问控制

```python
# 添加API密钥验证（可选）
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key
```

### 3. CORS配置

```python
# api/app.py
# 生产环境应限制允许的域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],  # 替换 "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### 4. HTTPS配置

使用Nginx作为反向代理并配置HTTPS：

```nginx
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/v1/chat/stream {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 备份和恢复

### 备份内容

1. **RAG索引** - `rag_system/indexes/`
2. **配置文件** - `.env`
3. **Redis数据** (如果需要) - RSSHub缓存
4. **应用代码** - Git仓库

### 备份脚本

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/rss-api"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p "$BACKUP_DIR/$DATE"

# 备份RAG索引
cp -r rag_system/indexes "$BACKUP_DIR/$DATE/"

# 备份配置
cp .env "$BACKUP_DIR/$DATE/"

# 备份Redis数据（可选）
cd deploy
docker-compose exec redis redis-cli SAVE
docker cp deploy_redis_1:/data/dump.rdb "$BACKUP_DIR/$DATE/redis_dump.rdb"

# 压缩备份
cd "$BACKUP_DIR"
tar -czf "rss-api-backup-$DATE.tar.gz" "$DATE"
rm -rf "$DATE"

echo "备份完成: $BACKUP_DIR/rss-api-backup-$DATE.tar.gz"
```

### 恢复步骤

```bash
# 1. 解压备份
tar -xzf rss-api-backup-20250131_120000.tar.gz

# 2. 恢复RAG索引
cp -r 20250131_120000/indexes/* rag_system/indexes/

# 3. 恢复配置
cp 20250131_120000/.env .

# 4. 重启服务
systemctl restart rss-api
```

---

## 联系方式

如有问题或建议，请提交Issue或Pull Request。

- GitHub: <repository-url>
- 文档: [README.md](README.md)
- API文档: http://localhost:8000/docs
