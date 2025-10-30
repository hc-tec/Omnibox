"""
向量化处理模块
使用bge-m3模型进行文本向量化
支持 ModelScope 国内镜像加速下载
"""
import torch
from sentence_transformers import SentenceTransformer
from typing import List, Union, Optional
import logging
import numpy as np
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    向量化模型封装类
    默认使用 bge-m3，支持中英文混合场景
    支持 ModelScope 镜像加速下载
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = "cuda",
        normalize_embeddings: bool = True,
        max_length: int = 8192,
        use_modelscope: bool = True,
        modelscope_model_id: Optional[str] = None,
    ):
        """
        初始化向量模型

        Args:
            model_name: 模型名称（Hugging Face ID），默认为bge-m3
            device: 设备（cuda/cpu）
            normalize_embeddings: 是否归一化向量（推荐True，用于余弦相似度）
            max_length: 最大文本长度
            use_modelscope: 是否使用ModelScope镜像下载（国内推荐）
            modelscope_model_id: ModelScope上的模型ID（如果与Hugging Face不同）
        """
        self.model_name = model_name
        self.normalize_embeddings = normalize_embeddings
        self.max_length = max_length
        self.use_modelscope = use_modelscope

        # 检查GPU可用性
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA不可用，切换到CPU")
            device = "cpu"

        self.device = device

        logger.info(f"准备加载模型: {model_name}")
        logger.info(f"使用设备: {device}")

        # 根据配置选择加载方式
        model_path = model_name

        if use_modelscope:
            try:
                model_path = self._download_from_modelscope(
                    model_name, modelscope_model_id
                )
            except Exception as e:
                logger.warning(f"ModelScope下载失败: {e}")
                logger.info("降级使用Hugging Face下载")
                # 降级使用 Hugging Face
                model_path = model_name

        # 加载模型
        logger.info(f"正在加载模型...")
        self.model = SentenceTransformer(
            model_path,
            device=device,
        )

        # 设置最大序列长度（不可超过模型本身的限制）
        model_default_max_length = getattr(self.model, "max_seq_length", None)
        if model_default_max_length is not None and model_default_max_length <= 0:
            model_default_max_length = None

        target_max_length = max_length or model_default_max_length

        if (
            model_default_max_length is not None
            and target_max_length is not None
            and target_max_length > model_default_max_length
        ):
            logger.warning(
                "请求的最大序列长度 %s 超过模型支持的上限 %s，自动调整为模型上限",
                target_max_length,
                model_default_max_length,
            )
            target_max_length = model_default_max_length

        if target_max_length is not None:
            self.model.max_seq_length = target_max_length

        self.max_length = target_max_length
        logger.info(
            "最大序列长度设置为 %s (模型默认: %s)",
            self.max_length if self.max_length is not None else "未限制",
            model_default_max_length if model_default_max_length is not None else "未知",
        )

        logger.info("✓ 模型加载完成")

        # 打印模型信息
        if device == "cuda":
            logger.info(f"GPU显存占用: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")

    def _download_from_modelscope(
        self,
        model_name: str,
        modelscope_model_id: Optional[str] = None
    ) -> str:
        """
        使用ModelScope下载模型（国内镜像，速度快）

        Args:
            model_name: Hugging Face 模型ID
            modelscope_model_id: ModelScope模型ID（如果不同）

        Returns:
            本地模型路径
        """
        try:
            from modelscope.hub.snapshot_download import snapshot_download
        except ImportError:
            logger.warning("未安装modelscope，请运行: pip install modelscope")
            raise

        # ModelScope模型ID映射
        MODELSCOPE_MODEL_MAP = {
            "BAAI/bge-m3": "Xorbits/bge-m3",
            "BAAI/bge-large-zh-v1.5": "Xorbits/bge-large-zh-v1.5",
            "BAAI/bge-small-zh-v1.5": "Xorbits/bge-small-zh-v1.5",
            "BAAI/bge-base-zh-v1.5": "Xorbits/bge-base-zh-v1.5",
            "moka-ai/m3e-base": "xrunda/m3e-base",
        }

        # 确定ModelScope的模型ID
        if modelscope_model_id:
            ms_model_id = modelscope_model_id
        elif model_name in MODELSCOPE_MODEL_MAP:
            ms_model_id = MODELSCOPE_MODEL_MAP[model_name]
        else:
            # 尝试直接使用原始ID
            ms_model_id = model_name

        logger.info(f"使用ModelScope镜像下载: {ms_model_id}")
        logger.info("提示: 首次下载会较慢，后续会使用缓存")

        # 下载模型到本地
        model_dir = snapshot_download(
            ms_model_id,
            cache_dir=os.path.expanduser("~/.cache/modelscope")
        )

        logger.info(f"✓ 模型已下载到: {model_dir}")
        return model_dir

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress: bool = True,
    ) -> np.ndarray:
        """
        将文本转换为向量

        Args:
            texts: 单个文本或文本列表
            batch_size: 批处理大小
            show_progress: 是否显示进度条

        Returns:
            向量数组 (n_texts, embedding_dim)
        """
        # 确保输入是列表
        if isinstance(texts, str):
            texts = [texts]

        logger.info(f"开始向量化 {len(texts)} 个文本")

        # 使用模型编码
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
        )

        logger.info(f"向量化完成，向量维度: {embeddings.shape}")

        return embeddings

    def encode_queries(
        self,
        queries: Union[str, List[str]],
        batch_size: int = 32,
    ) -> np.ndarray:
        """
        为查询文本生成向量（部分模型对query有特殊处理）

        bge-m3的最佳实践：
        - 为了获得更好的检索效果，可以在查询前添加指令
        - 例如："为这个句子生成表示以用于检索相关文章："

        Args:
            queries: 查询文本
            batch_size: 批处理大小

        Returns:
            查询向量
        """
        # 确保输入是列表
        if isinstance(queries, str):
            queries = [queries]

        # bge模型的查询优化：添加指令前缀
        # 注意：这是可选的，bge-m3即使不加也有很好的效果
        instruction = "为这个句子生成表示以用于检索相关文章："
        queries_with_instruction = [instruction + q for q in queries]

        return self.encode(queries_with_instruction, batch_size=batch_size, show_progress=False)

    def get_embedding_dimension(self) -> int:
        """获取向量维度"""
        return self.model.get_sentence_embedding_dimension()

    def similarity(self, embeddings1: np.ndarray, embeddings2: np.ndarray) -> np.ndarray:
        """
        计算两组向量之间的余弦相似度

        Args:
            embeddings1: 第一组向量 (n, dim)
            embeddings2: 第二组向量 (m, dim)

        Returns:
            相似度矩阵 (n, m)
        """
        # 如果已经归一化，直接点积即为余弦相似度
        if self.normalize_embeddings:
            return np.dot(embeddings1, embeddings2.T)
        else:
            # 否则需要归一化
            from numpy.linalg import norm
            embeddings1_norm = embeddings1 / norm(embeddings1, axis=1, keepdims=True)
            embeddings2_norm = embeddings2 / norm(embeddings2, axis=1, keepdims=True)
            return np.dot(embeddings1_norm, embeddings2_norm.T)


class HybridRetriever:
    """
    混合检索器（bge-m3的高级特性）

    bge-m3支持三种检索方式：
    1. Dense Retrieval（密集向量检索）- 默认方式
    2. Sparse Retrieval（稀疏检索，类似BM25）
    3. Multi-Vector Retrieval（多向量检索）

    最佳实践：结合密集和稀疏检索可以获得更好的效果
    """

    def __init__(self, model: EmbeddingModel):
        """
        初始化混合检索器

        Args:
            model: 已加载的向量模型
        """
        self.model = model
        logger.info("混合检索器已初始化（支持密集+稀疏检索）")

    def encode_for_retrieval(
        self,
        texts: Union[str, List[str]],
        return_dense: bool = True,
        return_sparse: bool = False,
        return_colbert_vecs: bool = False,
    ):
        """
        为检索任务编码文本

        Args:
            texts: 输入文本
            return_dense: 返回密集向量
            return_sparse: 返回稀疏向量
            return_colbert_vecs: 返回多向量表示

        Returns:
            根据参数返回不同类型的向量表示
        """
        # 注意：这需要 FlagEmbedding 库来完整支持bge-m3的高级特性
        # 简化版本：只返回密集向量
        if return_dense:
            return self.model.encode(texts)
        else:
            raise NotImplementedError("稀疏检索需要使用FlagEmbedding库")


if __name__ == "__main__":
    # 测试代码
    from config import EMBEDDING_MODEL_CONFIG

    # 初始化模型
    model = EmbeddingModel(**EMBEDDING_MODEL_CONFIG)

    # 测试文本
    test_texts = [
        "虎扑社区的热门帖子",
        "获取步行街最新发布的内容",
        "NBA篮球新闻和讨论",
    ]

    # 生成向量
    embeddings = model.encode(test_texts)
    print(f"生成向量形状: {embeddings.shape}")
    print(f"向量维度: {model.get_embedding_dimension()}")

    # 测试相似度
    query = "虎扑步行街的帖子"
    query_embedding = model.encode_queries(query)
    similarities = model.similarity(query_embedding, embeddings)

    print(f"\n查询: {query}")
    print("相似度分数:")
    for i, (text, score) in enumerate(zip(test_texts, similarities[0])):
        print(f"  {i + 1}. [{score:.4f}] {text}")
