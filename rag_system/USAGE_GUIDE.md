# RAG系统使用指南

## 完整工作流程

### 步骤1：环境准备

#### 1.1 检查系统要求

```bash
# 检查Python版本（需要3.8+）
python --version

# 检查内存（推荐16GB+）
# Windows: wmic OS get TotalVisibleMemorySize
# Linux: free -h
```

#### 1.2 安装依赖

**方式A：自动安装（推荐）**
```bash
python install_and_test.py
```

**方式B：手动安装**
```bash
# 基础安装（包含 ModelScope 国内镜像）
pip install sentence-transformers chromadb numpy pandas tqdm modelscope

# 如果需要API服务
pip install fastapi uvicorn pydantic
```

**国内用户提示**：系统已集成 ModelScope 镜像，模型下载速度提升 10-100 倍。详见 [MODELSCOPE_GUIDE.md](MODELSCOPE_GUIDE.md)

#### 1.3 GPU配置（可选但推荐）

如果有NVIDIA GPU：
```bash
# 安装CUDA版本的PyTorch
# CUDA 11.8
pip install torch --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

验证GPU：
```python
import torch
print(torch.cuda.is_available())  # 应该返回True
print(torch.cuda.get_device_name(0))
```

### 步骤2：首次使用

#### 2.1 快速开始（推荐）

```bash
python quick_start.py
```

这个脚本会：
1. 初始化系统
2. 自动构建索引（首次运行）
3. 测试查询
4. 进入交互模式

#### 2.2 手动构建索引

```bash
# 构建索引
python rag_pipeline.py --build

# 强制重建（如果数据源有更新）
python rag_pipeline.py --build --force-rebuild
```

构建时间：
- 100个路由：~1分钟
- 1000个路由：~5分钟
- 10000个路由：~30分钟

### 步骤3：使用系统

#### 3.1 命令行查询

```bash
# 单次查询
python rag_pipeline.py --query "虎扑步行街热帖" --top-k 5

# 交互式查询
python rag_pipeline.py --interactive
```

#### 3.2 Python脚本

```python
from rag_pipeline import RAGPipeline

# 初始化
pipeline = RAGPipeline()

# 查询
results = pipeline.search("虎扑步行街", top_k=5)

# 处理结果
for route_id, score, route_def in results:
    print(f"{route_id}: {score:.3f}")
    print(f"  {route_def['name']}")
```

#### 3.3 API服务（可选）

```bash
# 启动API服务器
python api_server.py --host 0.0.0.0 --port 8000

# 访问API文档
# http://localhost:8000/docs
```

使用curl测试：
```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "虎扑步行街", "top_k": 5}'
```

## 常见使用场景

### 场景1：用户意图识别

**需求**：用户说"我想看虎扑的热帖"，找到对应的路由

```python
pipeline = RAGPipeline()

# 用户输入
user_input = "我想看虎扑的热帖"

# 检索
results = pipeline.search(user_input, top_k=1)

if results:
    route_id, score, route_def = results[0]

    if score > 0.7:  # 高置信度
        print(f"找到路由: {route_id}")
        print(f"路径: {route_def['path_template']}")
    else:
        print("没有找到确切匹配")
```

### 场景2：智能推荐

**需求**：根据用户兴趣推荐相关路由

```python
# 用户兴趣描述
user_interest = "我喜欢篮球和体育新闻"

# 检索相关路由
results = pipeline.search(user_interest, top_k=10)

# 按数据源分组
from collections import defaultdict
by_datasource = defaultdict(list)

for route_id, score, route_def in results:
    datasource = route_def['datasource']
    by_datasource[datasource].append(route_id)

# 推荐
for datasource, routes in by_datasource.items():
    print(f"{datasource}: {', '.join(routes[:3])}")
```

### 场景3：多轮对话

**需求**：在对话中逐步细化查询

```python
# 第一轮：宽泛查询
results_1 = pipeline.search("体育新闻", top_k=10)
datasources = set(r[2]['datasource'] for r in results_1)
print(f"找到数据源: {datasources}")

# 第二轮：细化查询
results_2 = pipeline.search(
    "虎扑NBA新闻",
    filter_datasource="hupu"  # 限定数据源
)
```

### 场景4：批量处理

**需求**：批量处理多个查询

```python
queries = [
    "GitHub trending",
    "微博热搜",
    "知乎热榜",
    "豆瓣电影",
    "B站视频",
]

# 批量处理
results_dict = {}
for query in queries:
    results = pipeline.search(query, top_k=3, verbose=False)
    results_dict[query] = results

# 生成报告
import json
with open("batch_results.json", "w", encoding="utf-8") as f:
    json.dump(results_dict, f, ensure_ascii=False, indent=2)
```

## 高级功能

### 自定义模型配置

修改`config.py`：

```python
# 使用更轻量的模型（速度优先）
EMBEDDING_MODEL_CONFIG = {
    "model_name": "BAAI/bge-small-zh-v1.5",
    "device": "cuda",
    "normalize_embeddings": True,
    "max_length": 512,
}

# 或使用本地模型
EMBEDDING_MODEL_CONFIG = {
    "model_name": "/path/to/local/model",
    "device": "cuda",
    "normalize_embeddings": True,
    "max_length": 8192,
}
```

### 调整检索参数

```python
# 初始化时自定义配置
from config import RETRIEVAL_CONFIG

RETRIEVAL_CONFIG["top_k"] = 10
RETRIEVAL_CONFIG["score_threshold"] = 0.7  # 提高精度

pipeline = RAGPipeline(retrieval_config=RETRIEVAL_CONFIG)
```

### 定期更新索引

```python
# 定时任务示例
import schedule
import time

def rebuild_index():
    pipeline = RAGPipeline()
    pipeline.build_index(force_rebuild=True)
    print("索引重建完成")

# 每天凌晨3点重建
schedule.every().day.at("03:00").do(rebuild_index)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### 监控和日志

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rag_system.log'),
        logging.StreamHandler()
    ]
)

# 使用系统
pipeline = RAGPipeline()
results = pipeline.search("test query")

# 检查日志
# tail -f rag_system.log
```

## 性能优化技巧

### 1. 批处理优化

```python
# 不推荐：逐个编码
for text in texts:
    embedding = model.encode(text)

# 推荐：批量编码
embeddings = model.encode(texts, batch_size=32)
```

### 2. 缓存查询结果

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(query: str, top_k: int = 5):
    return tuple(pipeline.search(query, top_k))

# 相同查询会使用缓存
results = cached_search("虎扑")  # 首次查询
results = cached_search("虎扑")  # 使用缓存，瞬间返回
```

### 3. 异步处理

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def async_search(query):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(
            executor,
            pipeline.search,
            query
        )

# 并发查询
async def batch_search(queries):
    tasks = [async_search(q) for q in queries]
    return await asyncio.gather(*tasks)

# 运行
results = asyncio.run(batch_search([
    "虎扑", "GitHub", "微博"
]))
```

## 故障排除

### 问题1：内存不足

**症状**：`MemoryError` 或系统卡顿

**解决方案**：
```python
# 减小batch_size
pipeline.build_index(batch_size=8)

# 或分批处理
from semantic_doc_generator import SemanticDocGenerator

generator = SemanticDocGenerator(DATASOURCE_FILE, SEMANTIC_DOCS_PATH)
all_docs = generator.generate_all_docs()

# 分批添加
route_ids = list(all_docs.keys())
batch_size = 100

for i in range(0, len(route_ids), batch_size):
    batch_ids = route_ids[i:i+batch_size]
    batch_docs = [all_docs[rid] for rid in batch_ids]
    # ... 处理批次
```

### 问题2：GPU显存不足

**症状**：`CUDA out of memory`

**解决方案**：
```python
# 方案1：减小batch_size
EMBEDDING_MODEL_CONFIG["batch_size"] = 8

# 方案2：使用CPU
EMBEDDING_MODEL_CONFIG["device"] = "cpu"

# 方案3：使用更小的模型
EMBEDDING_MODEL_CONFIG["model_name"] = "BAAI/bge-small-zh-v1.5"
```

### 问题3：检索结果不准确

**诊断**：
```python
# 检查相似度分数
results = pipeline.search("虎扑", top_k=10)
for route_id, score, _ in results:
    print(f"{route_id}: {score:.4f}")

# 如果分数普遍很低（<0.5），说明向量化质量有问题
```

**解决方案**：
```python
# 1. 降低阈值
RETRIEVAL_CONFIG["score_threshold"] = 0.3

# 2. 增加返回结果
results = pipeline.search("虎扑", top_k=20)

# 3. 重建索引
pipeline.build_index(force_rebuild=True)

# 4. 检查语义文档质量
from semantic_doc_generator import SemanticDocGenerator
generator = SemanticDocGenerator(DATASOURCE_FILE, SEMANTIC_DOCS_PATH)
doc = generator.generate_semantic_doc("hupu_bbs", route_def)
print(doc)  # 检查是否包含足够的语义信息
```

### 问题4：模型下载失败

**症状**：网络超时或下载中断

**解决方案**：
```bash
# 手动下载模型
git lfs install
git clone https://huggingface.co/BAAI/bge-m3

# 使用本地路径
EMBEDDING_MODEL_CONFIG["model_name"] = "./bge-m3"
```

或使用镜像：
```bash
# 设置Hugging Face镜像
export HF_ENDPOINT=https://hf-mirror.com
python rag_pipeline.py --build
```

## 最佳实践总结

1. **首次使用**：运行`python quick_start.py`快速上手
2. **生产环境**：使用GPU，batch_size=32，定期重建索引
3. **资源受限**：使用bge-small模型，CPU模式，减小batch_size
4. **高精度需求**：调高score_threshold，使用bge-m3或bge-large
5. **高召回需求**：调低score_threshold，增加top_k
6. **监控**：定期检查日志和统计信息
7. **更新**：数据源变更后及时重建索引

## 参考资料

- bge-m3模型: https://huggingface.co/BAAI/bge-m3
- ChromaDB文档: https://docs.trychroma.com/
- Sentence Transformers: https://www.sbert.net/
