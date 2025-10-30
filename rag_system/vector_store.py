"""
向量数据库管理模块
使用ChromaDB进行向量存储和检索
"""
import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorStore:
    """
    向量数据库管理类
    封装ChromaDB操作
    """

    def __init__(
        self,
        persist_directory: Path,
        collection_name: str = "route_embeddings",
        distance_metric: str = "cosine",
    ):
        """
        初始化向量数据库

        Args:
            persist_directory: 数据库持久化目录
            collection_name: 集合名称
            distance_metric: 距离度量方式（cosine/l2/ip）
                - cosine: 余弦相似度（推荐，范围0-1）
                - l2: 欧式距离
                - ip: 内积
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.distance_metric = distance_metric

        # 创建持久化目录
        persist_directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"初始化向量数据库: {persist_directory}")

        # 初始化ChromaDB客户端（持久化模式）
        self.client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # 获取或创建集合
        try:
            self.collection = self.client.get_collection(name=collection_name)
            logger.info(f"加载已存在的集合: {collection_name}")
            logger.info(f"当前集合中的向量数量: {self.collection.count()}")
        except Exception:
            # 如果集合不存在，创建新集合
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": distance_metric},
            )
            logger.info(f"创建新集合: {collection_name}")

    def add_documents(
        self,
        route_ids: List[str],
        embeddings: List[List[float]],
        semantic_docs: List[str],
        route_definitions: List[Dict[str, Any]],
    ):
        """
        批量添加文档到向量数据库

        Args:
            route_ids: 路由ID列表
            embeddings: 向量列表
            semantic_docs: 语义文档列表
            route_definitions: 路由完整定义列表
        """
        logger.info(f"开始添加 {len(route_ids)} 个文档到向量数据库")

        # 准备元数据（将完整的路由定义存储为JSON字符串）
        metadatas = []
        for route_def, semantic_doc in zip(route_definitions, semantic_docs):
            metadata = {
                "route_definition": json.dumps(route_def, ensure_ascii=False),
                "semantic_doc": semantic_doc[:1000],  # 截取前1000字符用于预览
                "datasource": route_def.get("datasource", "unknown"),
                "name": route_def.get("name", ""),
                "categories": json.dumps(route_def.get("categories", [])),
            }
            metadatas.append(metadata)

        # 添加到ChromaDB
        self.collection.add(
            ids=route_ids,
            embeddings=embeddings,
            documents=semantic_docs,  # 完整的语义文档
            metadatas=metadatas,
        )

        logger.info(f"成功添加 {len(route_ids)} 个文档")
        logger.info(f"当前集合中的向量总数: {self.collection.count()}")

    def query(
        self,
        query_embeddings: List[List[float]],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        查询向量数据库

        Args:
            query_embeddings: 查询向量
            top_k: 返回top-k个结果
            filter_dict: 过滤条件（如：{"datasource": "hupu"}）

        Returns:
            查询结果字典
        """
        logger.info(f"执行向量检索，返回top-{top_k}结果")

        results = self.collection.query(
            query_embeddings=query_embeddings,
            n_results=top_k,
            where=filter_dict,  # 元数据过滤
        )

        return results

    def get_by_id(self, route_id: str) -> Optional[Dict[str, Any]]:
        """
        根据route_id获取完整定义

        Args:
            route_id: 路由ID

        Returns:
            路由定义字典，如果不存在返回None
        """
        try:
            result = self.collection.get(
                ids=[route_id],
                include=["metadatas", "documents"],
            )

            if result["ids"]:
                metadata = result["metadatas"][0]
                route_def = json.loads(metadata["route_definition"])
                return route_def
            else:
                return None
        except Exception as e:
            logger.error(f"获取路由定义失败: {e}")
            return None

    def delete_by_ids(self, route_ids: List[str]):
        """删除指定的文档"""
        self.collection.delete(ids=route_ids)
        logger.info(f"删除了 {len(route_ids)} 个文档")

    def reset_collection(self):
        """清空并重建集合"""
        logger.warning("正在重置集合...")
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": self.distance_metric},
        )
        logger.info("集合已重置")

    def get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        count = self.collection.count()

        # 获取所有数据源统计
        all_docs = self.collection.get(include=["metadatas"])
        datasource_counts = {}

        for metadata in all_docs["metadatas"]:
            datasource = metadata.get("datasource", "unknown")
            datasource_counts[datasource] = datasource_counts.get(datasource, 0) + 1

        return {
            "total_documents": count,
            "datasource_distribution": datasource_counts,
            "collection_name": self.collection_name,
            "distance_metric": self.distance_metric,
        }


class RouteRetriever:
    """
    路由检索器（高层封装）
    结合向量存储和相似度过滤
    """

    def __init__(
        self,
        vector_store: VectorStore,
        score_threshold: float = 0.5,
    ):
        """
        初始化检索器

        Args:
            vector_store: 向量数据库
            score_threshold: 相似度阈值（0-1之间）
        """
        self.vector_store = vector_store
        self.score_threshold = score_threshold

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_datasource: Optional[str] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        搜索相关路由

        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            filter_datasource: 过滤特定数据源

        Returns:
            [(route_id, score, route_definition), ...]
        """
        # 构建过滤条件
        filter_dict = None
        if filter_datasource:
            filter_dict = {"datasource": filter_datasource}

        # 执行查询
        results = self.vector_store.query(
            query_embeddings=[query_embedding],
            top_k=top_k,
            filter_dict=filter_dict,
        )

        # 解析结果
        retrieved_routes = []
        for i, route_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]

            # ChromaDB的余弦距离需要转换为相似度
            # cosine distance = 1 - cosine similarity
            # 所以 similarity = 1 - distance
            similarity_score = 1 - distance

            # 应用阈值过滤
            if similarity_score < self.score_threshold:
                continue

            # 获取路由定义
            metadata = results["metadatas"][0][i]
            route_def = json.loads(metadata["route_definition"])

            retrieved_routes.append((route_id, similarity_score, route_def))

        logger.info(f"检索到 {len(retrieved_routes)} 个满足阈值的结果")
        return retrieved_routes


if __name__ == "__main__":
    # 测试代码
    from config import VECTOR_DB_PATH, CHROMA_CONFIG
    import numpy as np

    # 初始化向量数据库
    vector_store = VectorStore(
        persist_directory=VECTOR_DB_PATH,
        collection_name=CHROMA_CONFIG["collection_name"],
        distance_metric=CHROMA_CONFIG["distance_metric"],
    )

    # 测试添加数据
    test_route_ids = ["test_route_1", "test_route_2"]
    test_embeddings = np.random.rand(2, 1024).tolist()  # 模拟bge-m3的1024维向量
    test_docs = ["测试文档1", "测试文档2"]
    test_definitions = [
        {"route_id": "test_route_1", "name": "测试路由1"},
        {"route_id": "test_route_2", "name": "测试路由2"},
    ]

    vector_store.add_documents(
        route_ids=test_route_ids,
        embeddings=test_embeddings,
        semantic_docs=test_docs,
        route_definitions=test_definitions,
    )

    # 测试查询
    query_embedding = np.random.rand(1024).tolist()
    results = vector_store.query(query_embeddings=[query_embedding], top_k=2)

    print("\n查询结果:")
    for i, route_id in enumerate(results["ids"][0]):
        distance = results["distances"][0][i]
        print(f"  {i + 1}. {route_id} (距离: {distance:.4f})")

    # 统计信息
    stats = vector_store.get_statistics()
    print(f"\n数据库统计: {stats}")
