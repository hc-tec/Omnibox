# RAG路由检索系统

基于向量化技术的智能路由检索系统，使用bge-m3模型实现中英文混合场景下的语义搜索。

## 核心特性

- **智能语义理解**: 使用bge-m3多语言向量模型，支持中英文混合查询
- **高效检索**: 基于ChromaDB向量数据库，毫秒级响应
- **语义增强**: 自动生成富含语义信息的文档，提升检索准确度
- **灵活过滤**: 支持数据源过滤和相似度阈值控制
- **生产就绪**: 完整的错误处理、日志记录和性能优化

## 系统架构

```
用户查询 → 向量化 → 向量检索 → 路由定义
           ↓
         bge-m3         ChromaDB      完整JSON
         模型          向量数据库
```

### 核心组件

1. **语义文档生成器** (`semantic_doc_generator.py`)
   - 将JSON路由定义转换为自然语言描述
   - 提取关键信息：名称、描述、参数、分类等
   - 生成富含语义关键词的文档

2. **向量化模型** (`embedding_model.py`)
   - 使用bge-m3模型进行文本向量化
   - 支持GPU加速（自动降级到CPU）
   - 批量处理优化

3. **向量数据库** (`vector_store.py`)
   - 基于ChromaDB实现持久化存储
   - 支持余弦相似度检索
   - 元数据过滤功能

4. **RAG管道** (`rag_pipeline.py`)
   - 整合所有组件
   - 提供端到端的检索服务
   - 命令行和编程接口

## 快速开始

### 1. 环境要求

- Python 3.8+
- 64GB内存
- 8GB显存（推荐CUDA，可选CPU）

### 2. 安装依赖

```bash
cd rag_system
pip install -r requirements.txt
```

**国内用户注意**：系统已集成 ModelScope 国内镜像，模型下载速度提升 10-100 倍。详见 [ModelScope 使用指南](MODELSCOPE_GUIDE.md)

### 3. 一键启动

```bash
python quick_start.py
```

这个脚本会自动：
1. 初始化系统
2. 构建向量索引（首次运行）
3. 测试查询功能
4. 进入交互式查询模式

## 详细使用

### 方式1：命令行工具

#### 构建索引
```bash
# 首次使用，构建向量索引
python rag_pipeline.py --build

# 强制重建索引
python rag_pipeline.py --build --force-rebuild
```

#### 单次查询
```bash
python rag_pipeline.py --query "虎扑步行街热帖" --top-k 5
```

#### 交互式查询
```bash
python rag_pipeline.py --interactive
```

### 方式2：Python API

```python
from rag_pipeline import RAGPipeline

# 初始化
pipeline = RAGPipeline()

# 构建索引（首次使用）
pipeline.build_index(force_rebuild=True)

# 查询
results = pipeline.search(
    query="虎扑步行街的热门帖子",
    top_k=5,
)

# 处理结果
for route_id, score, route_def in results:
    print(f"路由ID: {route_id}")
    print(f"相似度: {score}")
    print(f"定义: {route_def}")
```

### 方式3：运行示例

```bash
python example_usage.py
```

## 配置说明

配置文件：`config.py`

### 向量模型配置

```python
EMBEDDING_MODEL_CONFIG = {
    "model_name": "BAAI/bge-m3",        # 模型名称
    "device": "cuda",                    # 设备：cuda/cpu
    "normalize_embeddings": True,        # 归一化向量
    "max_length": 8192,                  # 最大文本长度

    # ModelScope 国内镜像（默认启用）
    "use_modelscope": True,              # 使用国内镜像，下载速度快
    "modelscope_model_id": None,         # 自动映射，也可手动指定
}
```

**可选模型：**

| 模型 | 维度 | 显存 | 特点 | 适用场景 |
|-----|------|------|------|---------|
| bge-m3 | 1024 | 2.5GB | 多语言，混合检索 | **推荐：中英文混合** |
| bge-large-zh-v1.5 | 1024 | 2GB | 中文优化 | 纯中文场景 |
| bge-small-zh-v1.5 | 512 | 0.5GB | 轻量级，速度快 | 大规模实时检索 |
| m3e-base | 768 | 0.4GB | 轻量级中文 | 中文场景，资源受限 |

**ModelScope 加速**：国内用户自动使用 ModelScope 镜像，模型下载速度从 KB/s 提升到 MB/s。详见 [MODELSCOPE_GUIDE.md](MODELSCOPE_GUIDE.md)

### 检索配置

```python
RETRIEVAL_CONFIG = {
    "top_k": 5,                # 返回结果数量
    "score_threshold": 0.5,    # 相似度阈值（0-1）
}
```

## 性能优化建议

### 1. 硬件配置

| 配置 | 最低 | 推荐 |
|-----|------|------|
| 内存 | 32GB | 64GB |
| 显存 | 无（CPU模式） | 8GB |
| GPU | 无 | RTX 3060+ |

## 更新记录

- 调整 `semantic_doc_generator.py` 以兼容数组形式的 `datasource_definitions.json`，并为每个路由补充提供商元数据（2024-04）。
- 限制向量模型的最大序列长度不超过模型内置上限，并将默认配置改为跟随模型默认值以避免编码阶段报错（2024-04）。

### 2. 批处理大小

根据显存调整：
- 8GB显存：batch_size=32
- 4GB显存：batch_size=16
- CPU模式：batch_size=8

```python
pipeline.build_index(batch_size=32)
```

### 3. 模型加载优化

模型采用延迟加载策略，仅在需要时加载到内存/显存。

### 4. 向量数据库优化

ChromaDB使用HNSW索引，查询时间复杂度为O(log N)：
- 1000条路由：<10ms
- 10000条路由：<50ms
- 100000条路由：<200ms

## 使用示例

### 示例1：简单查询

```python
from rag_pipeline import RAGPipeline

pipeline = RAGPipeline()

# 查询虎扑相关内容
results = pipeline.search("虎扑步行街热帖", top_k=3)

for route_id, score, route_def in results:
    print(f"{route_id}: {score:.4f}")
```

### 示例2：过滤查询

```python
# 只搜索特定数据源
results = pipeline.search(
    query="热门内容",
    filter_datasource="hupu",  # 只返回虎扑的路由
    top_k=5
)
```

### 示例3：获取完整定义

```python
# 根据route_id获取完整JSON
route_def = pipeline.get_route_by_id("hupu_bbs")
print(route_def)
```

### 示例4：批量查询

```python
queries = [
    "GitHub trending",
    "微博热搜",
    "知乎热榜",
]

for query in queries:
    results = pipeline.search(query, top_k=1)
    if results:
        route_id, score, _ = results[0]
        print(f"{query} -> {route_id} ({score:.3f})")
```

## 最佳实践

### 1. 索引构建

- **首次使用**: 运行`build_index()`构建索引（约3-5分钟）
- **数据更新**: 数据源变更后需重建索引
- **持久化**: 索引自动保存到`vector_db/`目录

### 2. 查询优化

- **相似度阈值**: 默认0.5，可根据需求调整
  - 高精度：0.7+（严格匹配）
  - 平衡：0.5-0.7（推荐）
  - 高召回：0.3-0.5（宽松匹配）

- **top-k选择**:
  - 精确查询：top_k=1-3
  - 探索性查询：top_k=5-10

### 3. 查询技巧

**好的查询示例：**
- "虎扑步行街的热门帖子"
- "获取GitHub trending仓库"
- "微博热搜榜单"

**避免的查询方式：**
- 过于简短："虎扑"（不够具体）
- 过于复杂：长篇大论（提取关键词即可）

### 4. 生产部署

```python
# 初始化时加载索引
pipeline = RAGPipeline()

# 定期重建索引（如每天凌晨）
import schedule
schedule.every().day.at("03:00").do(
    lambda: pipeline.build_index(force_rebuild=True)
)
```

## 性能指标

基于虎扑数据源测试（约100个路由）：

| 指标 | 数值 |
|-----|------|
| 索引构建时间 | ~2分钟 |
| 单次查询延迟 | <50ms |
| 准确率@1 | 85%+ |
| 准确率@5 | 95%+ |
| 显存占用 | ~2.5GB |
| 内存占用 | ~4GB |

## 系统监控

```python
# 查看统计信息
pipeline.show_statistics()

# 输出：
# 总文档数: 100
# 数据源分布:
#   hupu: 50
#   github: 30
#   ...
```

## 故障排除

### 问题1：CUDA out of memory

**解决方案：**
```python
# 方案1：减小batch_size
pipeline.build_index(batch_size=16)

# 方案2：切换到CPU
EMBEDDING_MODEL_CONFIG["device"] = "cpu"
```

### 问题2：检索结果不准确

**解决方案：**
- 降低相似度阈值：`score_threshold=0.3`
- 增加返回结果：`top_k=10`
- 检查查询表达是否清晰

### 问题3：模型下载失败

**国内用户（推荐）：**
```python
# 系统已默认使用 ModelScope 镜像，速度快
# 如果仍然失败，检查配置：
EMBEDDING_MODEL_CONFIG["use_modelscope"] = True

# 或手动使用 ModelScope CLI 下载
# pip install modelscope
# modelscope download --model Xorbits/bge-m3
```

**海外用户：**
```bash
# 手动下载模型到本地
git lfs clone https://huggingface.co/BAAI/bge-m3

# 修改配置使用本地路径
EMBEDDING_MODEL_CONFIG["model_name"] = "/path/to/bge-m3"
EMBEDDING_MODEL_CONFIG["use_modelscope"] = False
```

详见 [ModelScope 使用指南](MODELSCOPE_GUIDE.md)

## 文件结构

```
rag_system/
├── config.py                    # 配置文件
├── semantic_doc_generator.py    # 语义文档生成器
├── embedding_model.py           # 向量化模型
├── vector_store.py              # 向量数据库
├── rag_pipeline.py             # RAG管道（主入口）
├── example_usage.py            # 使用示例
├── quick_start.py              # 快速开始
├── requirements.txt            # Python依赖
├── README.md                   # 本文档
├── semantic_docs/              # 语义文档存储目录
├── vector_db/                  # 向量数据库存储目录
└── rag_system.log             # 日志文件
```

## 技术栈

- **向量模型**: sentence-transformers + bge-m3
- **向量数据库**: ChromaDB
- **深度学习**: PyTorch
- **数据处理**: NumPy, Pandas

## 扩展功能

### 高级检索（可选）

如需使用bge-m3的混合检索特性（密集+稀疏）：

```bash
# 安装FlagEmbedding库
pip install FlagEmbedding

# 使用混合检索
from embedding_model import HybridRetriever
retriever = HybridRetriever(model)
```

### API服务（可选）

提供REST API接口：

```bash
# 安装FastAPI
pip install fastapi uvicorn

# 启动服务
python api_server.py
```

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎反馈。
