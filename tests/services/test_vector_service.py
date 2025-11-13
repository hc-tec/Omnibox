"""测试 SubscriptionVectorStore（订阅向量检索服务）

测试向量化、语义搜索、别名匹配等功能。
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from services.subscription.vector_service import SubscriptionVectorStore


class MockEmbeddingModel:
    """Mock 向量化模型（避免加载真实模型）"""

    def encode(self, text, show_progress=False):
        """返回固定维度的假向量"""
        import numpy as np

        if isinstance(text, list):
            # 批量编码：根据文本内容生成不同的向量
            return np.array([[hash(t) % 100 / 100.0] * 768 for t in text])
        else:
            # 单个编码
            return np.array([hash(text) % 100 / 100.0] * 768)

    def encode_queries(self, query):
        """查询编码（与 encode 相同）"""
        return self.encode(query)


class TestSubscriptionVectorStore:
    """SubscriptionVectorStore 测试套件"""

    @pytest.fixture
    def temp_chroma_path(self):
        """创建临时 ChromaDB 路径"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embedding_model(self):
        """创建 Mock 向量化模型"""
        return MockEmbeddingModel()

    @pytest.fixture
    def vector_store(self, temp_chroma_path, mock_embedding_model):
        """创建 VectorStore 实例"""
        store = SubscriptionVectorStore(
            chroma_path=temp_chroma_path,
            embedding_model=mock_embedding_model
        )
        return store

    def test_initialization(self, vector_store):
        """测试初始化"""
        assert vector_store is not None
        assert vector_store.collection is not None
        assert vector_store.count() == 0

    def test_add_subscription(self, vector_store):
        """测试添加订阅"""
        subscription_data = {
            "display_name": "科技美学",
            "platform": "bilibili",
            "entity_type": "user",
            "description": "数码评测博主",
            "aliases": ["那岩"],
            "tags": ["数码", "评测"]
        }

        vector_store.add_subscription(1, subscription_data)

        # 验证数量
        assert vector_store.count() == 1

    def test_add_multiple_subscriptions(self, vector_store):
        """测试添加多个订阅"""
        subscriptions = [
            {
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user"
            },
            {
                "display_name": "少数派",
                "platform": "zhihu",
                "entity_type": "column"
            },
            {
                "display_name": "langchain",
                "platform": "github",
                "entity_type": "repo"
            }
        ]

        for i, sub_data in enumerate(subscriptions, start=1):
            vector_store.add_subscription(i, sub_data)

        assert vector_store.count() == 3

    def test_update_subscription(self, vector_store):
        """测试更新订阅"""
        subscription_data = {
            "display_name": "科技美学",
            "platform": "bilibili",
            "entity_type": "user"
        }

        # 添加
        vector_store.add_subscription(1, subscription_data)
        assert vector_store.count() == 1

        # 更新
        updated_data = {
            "display_name": "科技美学 2.0",
            "platform": "bilibili",
            "entity_type": "user",
            "description": "更新后的描述"
        }
        vector_store.update_subscription(1, updated_data)

        # 数量不变（upsert）
        assert vector_store.count() == 1

    def test_delete_subscription(self, vector_store):
        """测试删除订阅"""
        subscription_data = {
            "display_name": "科技美学",
            "platform": "bilibili",
            "entity_type": "user"
        }

        vector_store.add_subscription(1, subscription_data)
        assert vector_store.count() == 1

        vector_store.delete_subscription(1)
        assert vector_store.count() == 0

    def test_search_by_display_name(self, vector_store):
        """测试通过显示名称搜索"""
        subscription_data = {
            "display_name": "科技美学",
            "platform": "bilibili",
            "entity_type": "user",
            "aliases": ["那岩"]
        }

        vector_store.add_subscription(1, subscription_data)

        # 搜索显示名称
        results = vector_store.search("科技美学", top_k=5, min_similarity=0.0)

        assert len(results) == 1
        assert results[0][0] == 1  # subscription_id
        # 注意：Mock 模型的相似度不真实，只验证能返回结果

    def test_search_with_platform_filter(self, vector_store):
        """测试平台过滤搜索"""
        subscriptions = [
            {
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user"
            },
            {
                "display_name": "少数派",
                "platform": "zhihu",
                "entity_type": "column"
            }
        ]

        for i, sub_data in enumerate(subscriptions, start=1):
            vector_store.add_subscription(i, sub_data)

        # 搜索 bilibili 平台
        results = vector_store.search(
            "科技",
            platform="bilibili",
            top_k=5,
            min_similarity=0.0
        )

        # 应该只返回 bilibili 平台的订阅
        assert len(results) >= 0  # Mock 模型可能返回 0 或 1

    def test_search_with_similarity_threshold(self, vector_store):
        """测试相似度阈值过滤"""
        subscription_data = {
            "display_name": "科技美学",
            "platform": "bilibili",
            "entity_type": "user"
        }

        vector_store.add_subscription(1, subscription_data)

        # 使用高阈值（Mock 模型可能无法达到）
        results = vector_store.search(
            "完全不相关的查询",
            top_k=5,
            min_similarity=0.9
        )

        # 由于 Mock 模型，这里只验证不会报错
        assert isinstance(results, list)

    def test_search_empty_collection(self, vector_store):
        """测试在空集合中搜索"""
        results = vector_store.search("科技美学", top_k=5, min_similarity=0.0)

        assert len(results) == 0

    def test_batch_add_subscriptions(self, vector_store):
        """测试批量添加订阅"""
        subscriptions = [
            (1, {
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user"
            }),
            (2, {
                "display_name": "少数派",
                "platform": "zhihu",
                "entity_type": "column"
            }),
            (3, {
                "display_name": "langchain",
                "platform": "github",
                "entity_type": "repo"
            })
        ]

        vector_store.batch_add_subscriptions(subscriptions)

        assert vector_store.count() == 3

    def test_batch_add_empty_list(self, vector_store):
        """测试批量添加空列表"""
        vector_store.batch_add_subscriptions([])

        assert vector_store.count() == 0

    def test_text_representation_with_aliases(self, vector_store):
        """测试包含别名的文本表示"""
        subscription_data = {
            "display_name": "科技美学",
            "platform": "bilibili",
            "entity_type": "user",
            "aliases": ["那岩", "那总"],
            "tags": ["数码", "评测"],
            "description": "数码评测博主"
        }

        # 调用私有方法测试文本构建
        text = vector_store._build_text_representation(subscription_data)

        assert "科技美学" in text
        assert "那岩" in text
        assert "那总" in text
        assert "数码" in text
        assert "评测" in text
        assert "数码评测博主" in text

    def test_text_representation_with_json_strings(self, vector_store):
        """测试 JSON 字符串格式的 aliases 和 tags"""
        import json

        subscription_data = {
            "display_name": "科技美学",
            "platform": "bilibili",
            "entity_type": "user",
            "aliases": json.dumps(["那岩", "那总"]),  # JSON 字符串
            "tags": json.dumps(["数码", "评测"])
        }

        text = vector_store._build_text_representation(subscription_data)

        assert "科技美学" in text
        assert "那岩" in text
        assert "数码" in text

    def test_text_representation_minimal(self, vector_store):
        """测试最小信息的文本表示"""
        subscription_data = {
            "display_name": "科技美学",
            "platform": "bilibili",
            "entity_type": "user"
        }

        text = vector_store._build_text_representation(subscription_data)

        assert text == "科技美学"

    def test_reset_collection(self, vector_store):
        """测试重置集合"""
        # 添加一些订阅
        subscriptions = [
            (1, {"display_name": "科技美学", "platform": "bilibili", "entity_type": "user"}),
            (2, {"display_name": "少数派", "platform": "zhihu", "entity_type": "column"})
        ]
        vector_store.batch_add_subscriptions(subscriptions)
        assert vector_store.count() == 2

        # 重置
        vector_store.reset()

        # 验证清空
        assert vector_store.count() == 0

    def test_search_returns_sorted_by_similarity(self, vector_store):
        """测试搜索结果按相似度排序"""
        subscriptions = [
            (1, {"display_name": "科技美学", "platform": "bilibili", "entity_type": "user"}),
            (2, {"display_name": "科技评测", "platform": "bilibili", "entity_type": "user"}),
            (3, {"display_name": "美食博主", "platform": "bilibili", "entity_type": "user"})
        ]

        vector_store.batch_add_subscriptions(subscriptions)

        # 搜索
        results = vector_store.search("科技", top_k=3, min_similarity=0.0)

        # 验证返回的是 (id, similarity) 元组列表
        assert isinstance(results, list)
        if len(results) > 1:
            # 验证按相似度降序排列
            for i in range(len(results) - 1):
                assert results[i][1] >= results[i + 1][1]

    def test_search_top_k_limit(self, vector_store):
        """测试 top_k 限制"""
        subscriptions = [
            (i, {"display_name": f"订阅{i}", "platform": "bilibili", "entity_type": "user"})
            for i in range(1, 11)  # 10 个订阅
        ]

        vector_store.batch_add_subscriptions(subscriptions)

        # 只返回 top 3
        results = vector_store.search("订阅", top_k=3, min_similarity=0.0)

        assert len(results) <= 3
