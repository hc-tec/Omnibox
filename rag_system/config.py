"""
RAG绯荤粺閰嶇疆鏂囦欢
"""
import os
from pathlib import Path

# 椤圭洰鏍圭洰褰?
ROOT_DIR = Path(__file__).parent.parent
RAG_DIR = Path(__file__).parent

# 鏁版嵁璺緞
DATASOURCE_FILE = ROOT_DIR / "route_process" / "datasource_definitions.json"
ROUTES_FILE = ROOT_DIR / "route_process" / "routes.json"

# 鍚戦噺鏁版嵁搴撻厤缃?
VECTOR_DB_PATH = RAG_DIR / "vector_db"
SEMANTIC_DOCS_PATH = RAG_DIR / "semantic_docs"

# 妯″瀷閰嶇疆
EMBEDDING_MODEL_CONFIG = {
    # 鎺ㄨ崘锛歜ge-m3 (鏈€浣充腑鑻辨枃鎬ц兘)
    "model_name": "moka-ai/m3e-base",
    "device": "cuda",  # 浣跨敤GPU锛屽鏋滄病鏈塆PU鍒欐敼涓?cpu"
    "normalize_embeddings": True,
    "max_length": None,  # 使用模型默认的最大序列长度

    # ModelScope 鍥藉唴闀滃儚鍔犻€燂紙鎺ㄨ崘寮€鍚級
    "use_modelscope": True,  # 浣跨敤ModelScope闀滃儚锛屼笅杞介€熷害蹇?
    "modelscope_model_id": None,  # 鑷姩鏄犲皠锛屼篃鍙墜鍔ㄦ寚瀹氾紙濡?"Xorbits/bge-m3"锛?
}

# 澶囬€夋ā鍨嬮厤缃紙鍙牴鎹渶姹傚垏鎹級
ALTERNATIVE_MODELS = {
    # 涓枃浼樺寲
    "bge-large-zh": {
        "model_name": "BAAI/bge-large-zh-v1.5",
        "device": "cuda",
        "normalize_embeddings": True,
        "max_length": 512,
        "use_modelscope": True,
    },
    # 杞婚噺绾э紙閫熷害蹇級
    "bge-small-zh": {
        "model_name": "BAAI/bge-small-zh-v1.5",
        "device": "cuda",
        "normalize_embeddings": True,
        "max_length": 512,
        "use_modelscope": True,
    },
    # m3e-base锛堣交閲忕骇锛屼腑鏂囷級
    "m3e-base": {
        "model_name": "moka-ai/m3e-base",
        "device": "cuda",
        "normalize_embeddings": True,
        "max_length": 512,
        "use_modelscope": True,
        "modelscope_model_id": "xrunda/m3e-base",  # ModelScope涓婄殑ID
    },
}

# ChromaDB閰嶇疆
CHROMA_CONFIG = {
    "collection_name": "route_embeddings",
    "distance_metric": "cosine",  # 浣欏鸡鐩镐技搴?
}

# 妫€绱㈤厤缃?
RETRIEVAL_CONFIG = {
    "top_k": 5,  # 杩斿洖top5缁撴灉
    "score_threshold": 0.5,  # 鐩镐技搴﹂槇鍊硷紙0-1涔嬮棿锛?
}

# 鏃ュ織閰嶇疆
LOG_LEVEL = "INFO"
LOG_FILE = RAG_DIR / "rag_system.log"
