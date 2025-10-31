"""
RAG完整流程管道
整合所有模块，提供端到端的解决方案
"""
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from tqdm import tqdm

try:
    from .semantic_doc_generator import SemanticDocGenerator
    from .embedding_model import EmbeddingModel
    from .vector_store import VectorStore, RouteRetriever
    from .config import (
        DATASOURCE_FILE,
        SEMANTIC_DOCS_PATH,
        VECTOR_DB_PATH,
        EMBEDDING_MODEL_CONFIG,
        CHROMA_CONFIG,
        RETRIEVAL_CONFIG,
    )
except ImportError:  # 兼容直接运行脚本的场景
    from semantic_doc_generator import SemanticDocGenerator
    from embedding_model import EmbeddingModel
    from vector_store import VectorStore, RouteRetriever
    from config import (
        DATASOURCE_FILE,
        SEMANTIC_DOCS_PATH,
        VECTOR_DB_PATH,
        EMBEDDING_MODEL_CONFIG,
        CHROMA_CONFIG,
        RETRIEVAL_CONFIG,
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    RAG完整流程管道
    包含构建索引和检索两个主要功能
    """

    def __init__(
        self,
        datasource_file: Path = DATASOURCE_FILE,
        semantic_docs_path: Path = SEMANTIC_DOCS_PATH,
        vector_db_path: Path = VECTOR_DB_PATH,
        embedding_config: Dict = None,
        chroma_config: Dict = None,
        retrieval_config: Dict = None,
    ):
        """
        初始化RAG管道

        Args:
            datasource_file: 数据源定义文件
            semantic_docs_path: 语义文档存储路径
            vector_db_path: 向量数据库路径
            embedding_config: 向量模型配置
            chroma_config: ChromaDB配置
            retrieval_config: 检索配置
        """
        self.datasource_file = datasource_file
        self.semantic_docs_path = semantic_docs_path
        self.vector_db_path = vector_db_path

        # 使用默认配置
        self.embedding_config = embedding_config or EMBEDDING_MODEL_CONFIG
        self.chroma_config = chroma_config or CHROMA_CONFIG
        self.retrieval_config = retrieval_config or RETRIEVAL_CONFIG

        # 初始化组件
        logger.info("="*80)
        logger.info("初始化RAG系统组件")
        logger.info("="*80)

        # 1. 语义文档生成器
        self.doc_generator = SemanticDocGenerator(
            datasource_file=self.datasource_file,
            output_dir=self.semantic_docs_path,
        )

        # 2. 向量模型（延迟加载，需要时再加载）
        self._embedding_model = None

        # 3. 向量数据库
        self.vector_store = VectorStore(
            persist_directory=self.vector_db_path,
            collection_name=self.chroma_config["collection_name"],
            distance_metric=self.chroma_config["distance_metric"],
        )

        # 4. 检索器
        self.retriever = RouteRetriever(
            vector_store=self.vector_store,
            score_threshold=self.retrieval_config["score_threshold"],
        )

        logger.info("RAG系统初始化完成")

    @property
    def embedding_model(self) -> EmbeddingModel:
        """延迟加载向量模型（第一次使用时才加载）"""
        if self._embedding_model is None:
            logger.info("加载向量模型...")
            self._embedding_model = EmbeddingModel(**self.embedding_config)
        return self._embedding_model

    def build_index(self, force_rebuild: bool = False, batch_size: int = 32):
        """
        构建向量索引

        完整流程：
        1. 生成语义文档
        2. 向量化所有文档
        3. 存储到向量数据库

        Args:
            force_rebuild: 是否强制重建索引
            batch_size: 批处理大小
        """
        logger.info("\n" + "="*80)
        logger.info("开始构建向量索引")
        logger.info("="*80)

        # 检查是否需要重建
        if not force_rebuild and self.vector_store.collection.count() > 0:
            logger.warning(f"向量数据库已存在 {self.vector_store.collection.count()} 条记录")
            user_input = input("是否重建索引？[y/N]: ").strip().lower()
            if user_input != 'y':
                logger.info("跳过索引构建")
                return

        # 重置数据库
        if force_rebuild or self.vector_store.collection.count() > 0:
            self.vector_store.reset_collection()

        # Step 1: 生成语义文档
        logger.info("\n[1/3] 生成语义文档")
        all_docs = self.doc_generator.generate_all_docs()
        logger.info(f"✓ 生成了 {len(all_docs)} 个语义文档")

        # Step 2: 向量化
        logger.info("\n[2/3] 向量化文档")
        route_ids = list(all_docs.keys())
        semantic_docs = list(all_docs.values())

        embeddings = self.embedding_model.encode(
            texts=semantic_docs,
            batch_size=batch_size,
            show_progress=True,
        )
        logger.info(f"✓ 生成了 {len(embeddings)} 个向量")

        # Step 3: 获取完整路由定义并存储
        logger.info("\n[3/3] 存储到向量数据库")
        route_definitions = []
        for route_id in tqdm(route_ids, desc="获取路由定义"):
            route_def = self.doc_generator.get_route_definition(route_id)
            route_definitions.append(route_def)

        self.vector_store.add_documents(
            route_ids=route_ids,
            embeddings=embeddings.tolist(),
            semantic_docs=semantic_docs,
            route_definitions=route_definitions,
        )

        logger.info("\n" + "="*80)
        logger.info("✓ 索引构建完成！")
        logger.info("="*80)

        # 显示统计信息
        self.show_statistics()

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_datasource: Optional[str] = None,
        verbose: bool = True,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        搜索相关路由

        Args:
            query: 用户查询（自然语言）
            top_k: 返回结果数量（默认使用配置）
            filter_datasource: 过滤特定数据源
            verbose: 是否打印详细信息

        Returns:
            [(route_id, similarity_score, route_definition), ...]
        """
        if top_k is None:
            top_k = self.retrieval_config["top_k"]

        if verbose:
            logger.debug(f"查询: {query}")
            logger.debug("-" * 80)

        # 将查询向量化
        query_embedding = self.embedding_model.encode_queries(query)[0]

        # 检索
        results = self.retriever.search(
            query_embedding=query_embedding.tolist(),
            top_k=top_k,
            filter_datasource=filter_datasource,
        )

        # 打印结果
        if verbose:
            if not results:
                logger.info("未找到相关结果")
            else:
                logger.info(f"找到 {len(results)} 个相关结果")
                for i, (route_id, score, route_def) in enumerate(results, 1):
                    logger.debug(f"{i}. [{score:.4f}] {route_id}")
                    logger.info(f"   数据源: {route_def.get('datasource', 'N/A')}")
                    logger.info(f"   名称: {route_def.get('name', 'N/A')}")
                    logger.info(f"   描述: {route_def.get('description', 'N/A')[:100]}")

        return results

    def get_route_by_id(self, route_id: str) -> Optional[Dict[str, Any]]:
        """
        根据route_id获取完整路由定义

        Args:
            route_id: 路由ID

        Returns:
            路由定义字典
        """
        return self.vector_store.get_by_id(route_id)

    def show_statistics(self):
        """显示系统统计信息"""
        stats = self.vector_store.get_statistics()

        logger.info("\n数据库统计信息:")
        logger.info(f"  总文档数: {stats['total_documents']}")
        logger.info(f"  集合名称: {stats['collection_name']}")
        logger.info(f"  距离度量: {stats['distance_metric']}")
        logger.info("\n数据源分布:")
        for datasource, count in sorted(
            stats['datasource_distribution'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]:  # 显示前10个
            logger.info(f"    {datasource}: {count}")


def main():
    """主函数：命令行交互"""
    import argparse

    parser = argparse.ArgumentParser(description="RAG路由检索系统")
    parser.add_argument(
        "--build",
        action="store_true",
        help="构建向量索引",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="强制重建索引",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="查询字符串",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="返回结果数量",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="交互式查询模式",
    )

    args = parser.parse_args()

    # 初始化RAG管道
    pipeline = RAGPipeline()

    # 构建索引
    if args.build or args.force_rebuild:
        pipeline.build_index(force_rebuild=args.force_rebuild)

    # 单次查询
    if args.query:
        pipeline.search(query=args.query, top_k=args.top_k)

    # 交互式模式
    if args.interactive:
        logger.info("\n进入交互式查询模式（输入 'quit' 退出）")
        logger.info("="*80)

        while True:
            try:
                query = input("\n请输入查询: ").strip()
                if query.lower() in ['quit', 'exit', 'q']:
                    break
                if not query:
                    continue

                pipeline.search(query=query, top_k=args.top_k)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"查询出错: {e}")

        logger.info("\n再见！")


if __name__ == "__main__":
    main()
