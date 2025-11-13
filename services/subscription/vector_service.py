"""订阅向量检索服务

使用 ChromaDB + bge-m3 实现订阅实体的语义搜索。

功能：
- 订阅创建/更新时自动向量化
- 支持语义搜索（"那岩" → "科技美学"）
- 支持平台过滤
"""

import logging
import json
import chromadb
from chromadb.config import Settings
from typing import List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SubscriptionVectorStore:
    """订阅向量检索服务

    使用 ChromaDB 存储订阅的向量表示，支持语义搜索。
    独立的 Collection：subscription_embeddings
    """

    COLLECTION_NAME = "subscription_embeddings"

    def __init__(
        self,
        chroma_path: str = "./runtime/chroma",
        embedding_model=None
    ):
        """初始化向量存储

        Args:
            chroma_path: ChromaDB 持久化路径
            embedding_model: 向量化模型实例（可选，延迟加载）
        """
        self.chroma_path = Path(chroma_path)
        self.chroma_path.mkdir(parents=True, exist_ok=True)

        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False
            )
        )

        # 获取或创建 Collection
        try:
            self.collection = self.client.get_collection(name=self.COLLECTION_NAME)
            logger.info(f"加载已存在的订阅向量集合，当前数量: {self.collection.count()}")
        except Exception:
            self.collection = self.client.create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine", "description": "订阅实体向量"}
            )
            logger.info(f"创建新的订阅向量集合: {self.COLLECTION_NAME}")

        # 延迟加载 embedding_model（避免循环导入）
        self._embedding_model = embedding_model

    @property
    def embedding_model(self):
        """延迟加载向量化模型"""
        if self._embedding_model is None:
            from rag_system.embedding_model import EmbeddingModel
            logger.info("加载 bge-m3 向量化模型...")
            self._embedding_model = EmbeddingModel(
                model_name="BAAI/bge-m3",
                device="cuda",
                normalize_embeddings=True
            )
        return self._embedding_model

    def add_subscription(
        self,
        subscription_id: int,
        subscription_data: dict
    ) -> None:
        """向量化并添加订阅

        Args:
            subscription_id: 订阅 ID
            subscription_data: 订阅数据字典
                - display_name: 显示名称
                - platform: 平台
                - entity_type: 实体类型
                - description: 描述（可选）
                - aliases: 别名列表（可选）
                - tags: 标签列表（可选）
        """
        # 构建文本表示（用于向量化）
        text = self._build_text_representation(subscription_data)

        # 生成向量
        embedding = self.embedding_model.encode(text)

        # 准备元数据
        metadata = {
            "display_name": subscription_data.get("display_name", ""),
            "platform": subscription_data.get("platform", ""),
            "entity_type": subscription_data.get("entity_type", ""),
        }

        # 存储到 ChromaDB
        self.collection.upsert(
            ids=[str(subscription_id)],
            embeddings=[embedding.tolist()],
            metadatas=[metadata],
            documents=[text]
        )

        logger.info(f"订阅 {subscription_id} 已向量化: '{subscription_data.get('display_name')}'")

    def update_subscription(
        self,
        subscription_id: int,
        subscription_data: dict
    ) -> None:
        """更新订阅向量

        Args:
            subscription_id: 订阅 ID
            subscription_data: 更新后的订阅数据
        """
        # 更新操作与添加相同（upsert 自动处理）
        self.add_subscription(subscription_id, subscription_data)
        logger.info(f"订阅 {subscription_id} 向量已更新")

    def delete_subscription(self, subscription_id: int) -> None:
        """删除订阅向量

        Args:
            subscription_id: 订阅 ID
        """
        try:
            self.collection.delete(ids=[str(subscription_id)])
            logger.info(f"订阅 {subscription_id} 向量已删除")
        except Exception as e:
            logger.warning(f"删除订阅向量失败: {e}")

    def search(
        self,
        query: str,
        platform: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.0
    ) -> List[Tuple[int, float]]:
        """语义搜索订阅

        Args:
            query: 搜索查询（实体名称）
            platform: 平台过滤（可选）
            top_k: 返回数量
            min_similarity: 最小相似度阈值（0.0-1.0）

        Returns:
            [(subscription_id, similarity_score), ...]
            相似度从高到低排序
        """
        # 生成查询向量
        query_embedding = self.embedding_model.encode_queries(query)

        # 构建过滤条件
        where = {"platform": platform} if platform else None

        # 向量检索
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where
        )

        # 解析结果
        matches = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i, subscription_id in enumerate(results["ids"][0]):
                # ChromaDB 返回的是距离（越小越相似），需要转换为相似度
                distance = results["distances"][0][i]
                similarity = 1 - distance  # 余弦距离转相似度

                # 过滤低相似度结果
                if similarity >= min_similarity:
                    matches.append((int(subscription_id), similarity))

        logger.info(
            f"语义搜索 '{query}' (platform={platform}): "
            f"找到 {len(matches)} 个匹配（top_k={top_k}）"
        )

        return matches

    def batch_add_subscriptions(
        self,
        subscriptions: List[Tuple[int, dict]]
    ) -> None:
        """批量添加订阅向量

        Args:
            subscriptions: [(subscription_id, subscription_data), ...]
        """
        if not subscriptions:
            return

        ids = []
        embeddings = []
        metadatas = []
        documents = []

        for subscription_id, subscription_data in subscriptions:
            # 构建文本
            text = self._build_text_representation(subscription_data)

            # 收集数据
            ids.append(str(subscription_id))
            documents.append(text)
            metadatas.append({
                "display_name": subscription_data.get("display_name", ""),
                "platform": subscription_data.get("platform", ""),
                "entity_type": subscription_data.get("entity_type", ""),
            })

        # 批量生成向量
        texts = [doc for doc in documents]
        embeddings_array = self.embedding_model.encode(texts, show_progress=True)

        # 批量存储
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings_array.tolist(),
            metadatas=metadatas,
            documents=documents
        )

        logger.info(f"批量向量化完成: {len(subscriptions)} 个订阅")

    def _build_text_representation(self, subscription_data: dict) -> str:
        """构建订阅的文本表示（用于向量化）

        包含：display_name, aliases, tags, description

        Args:
            subscription_data: 订阅数据字典

        Returns:
            文本表示字符串
        """
        parts = [subscription_data.get("display_name", "")]

        # 添加别名
        aliases = subscription_data.get("aliases", [])
        if aliases:
            # 如果是 JSON 字符串，先解析
            if isinstance(aliases, str):
                try:
                    aliases = json.loads(aliases)
                except json.JSONDecodeError:
                    aliases = []
            parts.extend(aliases)

        # 添加标签
        tags = subscription_data.get("tags", [])
        if tags:
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = []
            parts.extend(tags)

        # 添加描述
        description = subscription_data.get("description")
        if description:
            parts.append(description)

        return " | ".join(parts)

    def count(self) -> int:
        """获取向量数量"""
        return self.collection.count()

    def reset(self) -> None:
        """重置向量库（谨慎使用）"""
        self.client.delete_collection(name=self.COLLECTION_NAME)
        self.collection = self.client.create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "description": "订阅实体向量"}
        )
        logger.warning("订阅向量库已重置")
