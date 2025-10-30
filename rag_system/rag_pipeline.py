"""
RAG瀹屾暣娴佺▼绠￠亾
鏁村悎鎵€鏈夋ā鍧楋紝鎻愪緵绔埌绔殑瑙ｅ喅鏂规
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
except ImportError:  # 鍏煎鐩存帴杩愯鑴氭湰鐨勫満鏅?    from semantic_doc_generator import SemanticDocGenerator
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
    RAG瀹屾暣娴佺▼绠￠亾
    鍖呭惈鏋勫缓绱㈠紩鍜屾绱袱涓富瑕佸姛鑳?
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
        鍒濆鍖朢AG绠￠亾

        Args:
            datasource_file: 鏁版嵁婧愬畾涔夋枃浠?
            semantic_docs_path: 璇箟鏂囨。瀛樺偍璺緞
            vector_db_path: 鍚戦噺鏁版嵁搴撹矾寰?
            embedding_config: 鍚戦噺妯″瀷閰嶇疆
            chroma_config: ChromaDB閰嶇疆
            retrieval_config: 妫€绱㈤厤缃?
        """
        self.datasource_file = datasource_file
        self.semantic_docs_path = semantic_docs_path
        self.vector_db_path = vector_db_path

        # 浣跨敤榛樿閰嶇疆
        self.embedding_config = embedding_config or EMBEDDING_MODEL_CONFIG
        self.chroma_config = chroma_config or CHROMA_CONFIG
        self.retrieval_config = retrieval_config or RETRIEVAL_CONFIG

        # 鍒濆鍖栫粍浠?
        logger.info("="*80)
        logger.info("鍒濆鍖朢AG绯荤粺缁勪欢")
        logger.info("="*80)

        # 1. 璇箟鏂囨。鐢熸垚鍣?
        self.doc_generator = SemanticDocGenerator(
            datasource_file=self.datasource_file,
            output_dir=self.semantic_docs_path,
        )

        # 2. 鍚戦噺妯″瀷锛堝欢杩熷姞杞斤紝闇€瑕佹椂鍐嶅姞杞斤級
        self._embedding_model = None

        # 3. 鍚戦噺鏁版嵁搴?
        self.vector_store = VectorStore(
            persist_directory=self.vector_db_path,
            collection_name=self.chroma_config["collection_name"],
            distance_metric=self.chroma_config["distance_metric"],
        )

        # 4. 妫€绱㈠櫒
        self.retriever = RouteRetriever(
            vector_store=self.vector_store,
            score_threshold=self.retrieval_config["score_threshold"],
        )

        logger.info("RAG绯荤粺鍒濆鍖栧畬鎴?)

    @property
    def embedding_model(self) -> EmbeddingModel:
        """寤惰繜鍔犺浇鍚戦噺妯″瀷锛堢涓€娆′娇鐢ㄦ椂鎵嶅姞杞斤級"""
        if self._embedding_model is None:
            logger.info("鍔犺浇鍚戦噺妯″瀷...")
            self._embedding_model = EmbeddingModel(**self.embedding_config)
        return self._embedding_model

    def build_index(self, force_rebuild: bool = False, batch_size: int = 32):
        """
        鏋勫缓鍚戦噺绱㈠紩

        瀹屾暣娴佺▼锛?
        1. 鐢熸垚璇箟鏂囨。
        2. 鍚戦噺鍖栨墍鏈夋枃妗?
        3. 瀛樺偍鍒板悜閲忔暟鎹簱

        Args:
            force_rebuild: 鏄惁寮哄埗閲嶅缓绱㈠紩
            batch_size: 鎵瑰鐞嗗ぇ灏?
        """
        logger.info("\n" + "="*80)
        logger.info("寮€濮嬫瀯寤哄悜閲忕储寮?)
        logger.info("="*80)

        # 妫€鏌ユ槸鍚﹂渶瑕侀噸寤?
        if not force_rebuild and self.vector_store.collection.count() > 0:
            logger.warning(f"鍚戦噺鏁版嵁搴撳凡瀛樺湪 {self.vector_store.collection.count()} 鏉¤褰?)
            user_input = input("鏄惁閲嶅缓绱㈠紩锛焄y/N]: ").strip().lower()
            if user_input != 'y':
                logger.info("璺宠繃绱㈠紩鏋勫缓")
                return

        # 閲嶇疆鏁版嵁搴?
        if force_rebuild or self.vector_store.collection.count() > 0:
            self.vector_store.reset_collection()

        # Step 1: 鐢熸垚璇箟鏂囨。
        logger.info("\n[1/3] 鐢熸垚璇箟鏂囨。")
        all_docs = self.doc_generator.generate_all_docs()
        logger.info(f"鉁?鐢熸垚浜?{len(all_docs)} 涓涔夋枃妗?)

        # Step 2: 鍚戦噺鍖?
        logger.info("\n[2/3] 鍚戦噺鍖栨枃妗?)
        route_ids = list(all_docs.keys())
        semantic_docs = list(all_docs.values())

        embeddings = self.embedding_model.encode(
            texts=semantic_docs,
            batch_size=batch_size,
            show_progress=True,
        )
        logger.info(f"鉁?鐢熸垚浜?{len(embeddings)} 涓悜閲?)

        # Step 3: 鑾峰彇瀹屾暣璺敱瀹氫箟骞跺瓨鍌?
        logger.info("\n[3/3] 瀛樺偍鍒板悜閲忔暟鎹簱")
        route_definitions = []
        for route_id in tqdm(route_ids, desc="鑾峰彇璺敱瀹氫箟"):
            route_def = self.doc_generator.get_route_definition(route_id)
            route_definitions.append(route_def)

        self.vector_store.add_documents(
            route_ids=route_ids,
            embeddings=embeddings.tolist(),
            semantic_docs=semantic_docs,
            route_definitions=route_definitions,
        )

        logger.info("\n" + "="*80)
        logger.info("鉁?绱㈠紩鏋勫缓瀹屾垚锛?)
        logger.info("="*80)

        # 鏄剧ず缁熻淇℃伅
        self.show_statistics()

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_datasource: Optional[str] = None,
        verbose: bool = True,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        鎼滅储鐩稿叧璺敱

        Args:
            query: 鐢ㄦ埛鏌ヨ锛堣嚜鐒惰瑷€锛?
            top_k: 杩斿洖缁撴灉鏁伴噺锛堥粯璁や娇鐢ㄩ厤缃級
            filter_datasource: 杩囨护鐗瑰畾鏁版嵁婧?
            verbose: 鏄惁鎵撳嵃璇︾粏淇℃伅

        Returns:
            [(route_id, similarity_score, route_definition), ...]
        """
        if top_k is None:
            top_k = self.retrieval_config["top_k"]

        if verbose:
            logger.debug(f"查询: {query}")
            logger.info("-" * 80)

        # 灏嗘煡璇㈠悜閲忓寲
        query_embedding = self.embedding_model.encode_queries(query)[0]

        # 妫€绱?
        results = self.retriever.search(
            query_embedding=query_embedding.tolist(),
            top_k=top_k,
            filter_datasource=filter_datasource,
        )

        # 鎵撳嵃缁撴灉
        if verbose:
            if not results:
                logger.info("鏈壘鍒扮浉鍏崇粨鏋?)
            else:
                logger.info(f"鎵惧埌 {len(results)} 涓浉鍏崇粨鏋?)
                for i, (route_id, score, route_def) in enumerate(results, 1):
                    logger.info(f"{i}. [{score:.4f}] {route_id}")
                    logger.info(f"   鏁版嵁婧? {route_def.get('datasource', 'N/A')}")
                    logger.info(f"   鍚嶇О: {route_def.get('name', 'N/A')}")
                    logger.info(f"   鎻忚堪: {route_def.get('description', 'N/A')[:100]}")

        return results

    def get_route_by_id(self, route_id: str) -> Optional[Dict[str, Any]]:
        """
        鏍规嵁route_id鑾峰彇瀹屾暣璺敱瀹氫箟

        Args:
            route_id: 璺敱ID

        Returns:
            璺敱瀹氫箟瀛楀吀
        """
        return self.vector_store.get_by_id(route_id)

    def show_statistics(self):
        """鏄剧ず绯荤粺缁熻淇℃伅"""
        stats = self.vector_store.get_statistics()

        logger.info("\n鏁版嵁搴撶粺璁′俊鎭?")
        logger.info(f"  鎬绘枃妗ｆ暟: {stats['total_documents']}")
        logger.info(f"  闆嗗悎鍚嶇О: {stats['collection_name']}")
        logger.info(f"  璺濈搴﹂噺: {stats['distance_metric']}")
        logger.info("\n鏁版嵁婧愬垎甯?")
        for datasource, count in sorted(
            stats['datasource_distribution'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]:  # 鏄剧ず鍓?0涓?
            logger.info(f"    {datasource}: {count}")


def main():
    """涓诲嚱鏁帮細鍛戒护琛屼氦浜?""
    import argparse

    parser = argparse.ArgumentParser(description="RAG璺敱妫€绱㈢郴缁?)
    parser.add_argument(
        "--build",
        action="store_true",
        help="鏋勫缓鍚戦噺绱㈠紩",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="寮哄埗閲嶅缓绱㈠紩",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="鏌ヨ瀛楃涓?,
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="杩斿洖缁撴灉鏁伴噺",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="浜や簰寮忔煡璇㈡ā寮?,
    )

    args = parser.parse_args()

    # 鍒濆鍖朢AG绠￠亾
    pipeline = RAGPipeline()

    # 鏋勫缓绱㈠紩
    if args.build or args.force_rebuild:
        pipeline.build_index(force_rebuild=args.force_rebuild)

    # 鍗曟鏌ヨ
    if args.query:
        pipeline.search(query=args.query, top_k=args.top_k)

    # 浜や簰寮忔ā寮?
    if args.interactive:
        logger.info("\n杩涘叆浜や簰寮忔煡璇㈡ā寮忥紙杈撳叆 'quit' 閫€鍑猴級")
        logger.info("="*80)

        while True:
            try:
                query = input("\n璇疯緭鍏ユ煡璇? ").strip()
                if query.lower() in ['quit', 'exit', 'q']:
                    break
                if not query:
                    continue

                pipeline.search(query=query, top_k=args.top_k)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"鏌ヨ鍑洪敊: {e}")

        logger.info("\n鍐嶈锛?)


if __name__ == "__main__":
    main()


