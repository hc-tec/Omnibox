# ModelScope 国内镜像使用指南

## 为什么使用 ModelScope？

在国内使用 Hugging Face 下载模型经常遇到：
- 下载速度慢（几KB/s）
- 经常连接超时
- 下载中断后需要重新开始

**ModelScope** 是阿里云推出的模型托管平台，提供国内镜像加速，下载速度可达到几MB/s甚至几十MB/s。

## 快速开始

### 1. 已自动集成

本系统已经默认集成了 ModelScope 支持，**无需额外配置**。

首次运行时会自动：
1. 检测 ModelScope 是否可用
2. 从 ModelScope 镜像下载模型
3. 如果失败，自动降级到 Hugging Face

### 2. 验证配置

查看 `config.py`：

```python
EMBEDDING_MODEL_CONFIG = {
    "model_name": "BAAI/bge-m3",
    "use_modelscope": True,  # ✓ 已启用
    # ...
}
```

## 支持的模型

系统已内置以下模型的 ModelScope 映射：

| Hugging Face ID | ModelScope ID | 说明 |
|----------------|---------------|------|
| BAAI/bge-m3 | Xorbits/bge-m3 | 推荐，中英文混合 |
| BAAI/bge-large-zh-v1.5 | Xorbits/bge-large-zh-v1.5 | 中文优化 |
| BAAI/bge-small-zh-v1.5 | Xorbits/bge-small-zh-v1.5 | 轻量级 |
| BAAI/bge-base-zh-v1.5 | Xorbits/bge-base-zh-v1.5 | 平衡版 |
| moka-ai/m3e-base | xrunda/m3e-base | 轻量级中文 |

## 使用示例

### 方式1：使用默认配置（推荐）

```python
from rag_pipeline import RAGPipeline

# 直接使用，会自动从 ModelScope 下载
pipeline = RAGPipeline()
pipeline.build_index()
```

### 方式2：手动指定 ModelScope ID

```python
from embedding_model import EmbeddingModel

# 使用 m3e-base 模型
model = EmbeddingModel(
    model_name="moka-ai/m3e-base",
    use_modelscope=True,
    modelscope_model_id="xrunda/m3e-base"  # ModelScope 上的 ID
)
```

### 方式3：禁用 ModelScope（使用 Hugging Face）

```python
from embedding_model import EmbeddingModel

model = EmbeddingModel(
    model_name="BAAI/bge-m3",
    use_modelscope=False  # 使用 Hugging Face
)
```

## 模型下载位置

ModelScope 下载的模型会缓存到：
```
~/.cache/modelscope/
```

Windows 示例：
```
C:\Users\YourName\.cache\modelscope\
```

Linux/Mac 示例：
```
/home/username/.cache/modelscope/
```

## 常见问题

### Q1: 首次下载很慢怎么办？

**A:** 首次下载模型（约2GB）需要一些时间，这是正常的。后续使用会直接从缓存加载，速度很快。

**下载进度参考：**
- ModelScope 国内镜像：5-10分钟
- Hugging Face 直连：30-60分钟或更久

### Q2: 如何查看下载进度？

**A:** 运行时会显示日志：

```
INFO - 使用ModelScope镜像下载: Xorbits/bge-m3
INFO - 提示: 首次下载会较慢，后续会使用缓存
INFO - ✓ 模型已下载到: /home/user/.cache/modelscope/...
```

### Q3: 下载失败怎么办？

**A:** 系统会自动降级到 Hugging Face：

```
WARNING - ModelScope下载失败: ...
INFO - 降级使用Hugging Face下载
```

如果 Hugging Face 也失败，可以尝试：

**方案1：手动下载**
```bash
# 使用 modelscope CLI
pip install modelscope
modelscope download --model Xorbits/bge-m3
```

**方案2：设置代理（如果有）**
```bash
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
```

### Q4: 如何清理缓存？

**A:** 删除缓存目录：

```bash
# Linux/Mac
rm -rf ~/.cache/modelscope/

# Windows
rmdir /s /q C:\Users\YourName\.cache\modelscope
```

### Q5: 能否使用本地模型？

**A:** 可以，直接指定本地路径：

```python
from embedding_model import EmbeddingModel

model = EmbeddingModel(
    model_name="/path/to/local/bge-m3",
    use_modelscope=False  # 本地模型不需要下载
)
```

### Q6: 如何添加新的模型映射？

**A:** 编辑 `embedding_model.py`，在 `MODELSCOPE_MODEL_MAP` 中添加：

```python
MODELSCOPE_MODEL_MAP = {
    "BAAI/bge-m3": "Xorbits/bge-m3",
    # 添加你的模型
    "your/hf-model": "your/ms-model",
}
```

## 切换其他模型

### 使用 m3e-base（轻量级中文模型）

修改 `config.py`：

```python
EMBEDDING_MODEL_CONFIG = {
    "model_name": "moka-ai/m3e-base",
    "device": "cuda",
    "normalize_embeddings": True,
    "max_length": 512,
    "use_modelscope": True,
    "modelscope_model_id": "xrunda/m3e-base",
}
```

或在代码中：

```python
from config import ALTERNATIVE_MODELS
from rag_pipeline import RAGPipeline

# 使用 m3e-base
pipeline = RAGPipeline(
    embedding_config=ALTERNATIVE_MODELS["m3e-base"]
)
```

### 使用 bge-small-zh（追求速度）

```python
from config import ALTERNATIVE_MODELS
from rag_pipeline import RAGPipeline

pipeline = RAGPipeline(
    embedding_config=ALTERNATIVE_MODELS["bge-small-zh"]
)
```

## 性能对比

| 下载方式 | 平均速度 | 2GB模型下载时间 |
|---------|---------|----------------|
| ModelScope 镜像 | 10-50 MB/s | 5-10分钟 |
| Hugging Face 直连 | 0.1-1 MB/s | 30-120分钟 |

## ModelScope 模型搜索

访问 ModelScope 官网查找更多模型：
- https://modelscope.cn/models

搜索关键词：
- `embedding`
- `bge`
- `m3e`
- `text2vec`

## 最佳实践

1. **国内用户**：始终保持 `use_modelscope=True`
2. **海外用户**：可以设置 `use_modelscope=False`
3. **首次使用**：提前下载模型，避免在构建索引时等待
4. **网络不稳定**：先手动下载模型到本地，再使用本地路径

## 预下载模型

如果想提前下载模型：

```python
from embedding_model import EmbeddingModel

# 仅用于下载，不使用
model = EmbeddingModel(
    model_name="BAAI/bge-m3",
    use_modelscope=True
)

print("模型已下载完成，缓存在 ~/.cache/modelscope/")
```

## 技术细节

ModelScope 下载流程：

1. 检查本地缓存（`~/.cache/modelscope/`）
2. 如果存在，直接使用缓存
3. 如果不存在，从 ModelScope 下载
4. 下载完成后，SentenceTransformer 从本地路径加载

这样确保：
- ✓ 首次下载速度快
- ✓ 后续使用无需下载
- ✓ 离线也能使用（如果已缓存）

## 故障排除

### 问题：提示 "未安装modelscope"

**解决方案：**
```bash
pip install modelscope
```

### 问题：下载卡住不动

**解决方案：**
```bash
# 1. 取消当前下载（Ctrl+C）
# 2. 删除不完整的缓存
rm -rf ~/.cache/modelscope/*
# 3. 重新运行
```

### 问题：SSL 错误

**解决方案：**
```bash
# 忽略 SSL 验证（不推荐，仅临时使用）
export CURL_CA_BUNDLE=""
```

或在代码中禁用 ModelScope：
```python
EMBEDDING_MODEL_CONFIG["use_modelscope"] = False
```

## 总结

- ✓ 默认启用 ModelScope，无需配置
- ✓ 自动降级到 Hugging Face
- ✓ 国内下载速度提升 10-100 倍
- ✓ 支持所有常用中文向量模型

**推荐配置：**
```python
EMBEDDING_MODEL_CONFIG = {
    "model_name": "BAAI/bge-m3",
    "use_modelscope": True,  # 国内必开
    # ...
}
```
