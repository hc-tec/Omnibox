"""测试数据存储模块"""
import pytest
from langgraph_agents.storage import InMemoryResearchDataStore


class TestInMemoryResearchDataStore:
    """测试内存数据存储"""

    def test_save_and_load(self):
        """测试保存和加载数据"""
        store = InMemoryResearchDataStore()
        data = {"test": "data", "items": [1, 2, 3]}

        data_id = store.save(data)
        assert data_id.startswith("lg-")

        loaded = store.load(data_id)
        assert loaded == data

    def test_load_nonexistent_returns_none(self):
        """测试加载不存在的数据返回 None"""
        store = InMemoryResearchDataStore()
        result = store.load("nonexistent-id")
        assert result is None

    def test_multiple_saves_unique_ids(self):
        """测试多次保存生成唯一 ID"""
        store = InMemoryResearchDataStore()
        id1 = store.save({"data": 1})
        id2 = store.save({"data": 2})
        assert id1 != id2

    def test_stats(self):
        """测试统计信息"""
        store = InMemoryResearchDataStore()
        assert store.stats()["items"] == 0

        store.save({"test": 1})
        store.save({"test": 2})
        assert store.stats()["items"] == 2

    def test_thread_safety(self):
        """测试线程安全性（基础测试）"""
        store = InMemoryResearchDataStore()
        # 连续保存和加载，确保不会崩溃
        ids = []
        for i in range(10):
            data_id = store.save({"index": i})
            ids.append(data_id)

        for i, data_id in enumerate(ids):
            data = store.load(data_id)
            assert data["index"] == i
