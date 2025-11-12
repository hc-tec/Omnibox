"""
测试 ChatService._build_dataset_preview 方法

验证修复后的数据预览功能在多数据集场景下的正确性。
"""

import pytest
from unittest.mock import Mock
from services.chat_service import ChatService
from services.data_query_service import QueryDataset


class TestBuildDatasetPreview:
    """测试数据集预览功能"""

    @pytest.fixture
    def chat_service(self):
        """创建 ChatService 实例"""
        mock_data_query_service = Mock()
        return ChatService(
            data_query_service=mock_data_query_service,
            llm_client=None,
        )

    def test_preview_single_dataset(self, chat_service):
        """测试单个数据集预览"""
        datasets = [
            QueryDataset(
                route_id="test",
                provider="test",
                name="测试数据集",
                generated_path="/test",
                items=[
                    {"title": f"标题{i}", "description": f"描述{i}"}
                    for i in range(5)
                ],
                feed_title="测试Feed",
            )
        ]

        preview, count = chat_service._build_dataset_preview(datasets, max_items=3)

        assert count == 3, "应该采样3条数据"
        assert "[测试Feed]" in preview, "应该包含数据集标题"
        assert "标题0" in preview, "应该包含第一条数据"
        assert "标题2" in preview, "应该包含第三条数据"

    def test_preview_multiple_datasets_even_distribution(self, chat_service):
        """测试多数据集均匀分配采样 - 这是修复的核心场景"""
        datasets = [
            QueryDataset(
                route_id="dataset1",
                provider="provider1",
                name="数据集1",
                generated_path="/dataset1",
                items=[{"title": f"DS1-标题{i}"} for i in range(30)],
                feed_title="数据集1",
            ),
            QueryDataset(
                route_id="dataset2",
                provider="provider2",
                name="数据集2",
                generated_path="/dataset2",
                items=[{"title": f"DS2-标题{i}"} for i in range(30)],
                feed_title="数据集2",
            ),
            QueryDataset(
                route_id="dataset3",
                provider="provider3",
                name="数据集3",
                generated_path="/dataset3",
                items=[{"title": f"DS3-标题{i}"} for i in range(30)],
                feed_title="数据集3",
            ),
        ]

        preview, count = chat_service._build_dataset_preview(datasets, max_items=20)

        # 验证所有数据集都被采样
        assert "[数据集1]" in preview, "应该包含数据集1"
        assert "[数据集2]" in preview, "应该包含数据集2"
        assert "[数据集3]" in preview, "应该包含数据集3"

        # 验证数据分布（每个数据集应该有约 20/3 ≈ 6-7 条）
        assert "DS1-标题" in preview, "应该包含数据集1的数据"
        assert "DS2-标题" in preview, "应该包含数据集2的数据"
        assert "DS3-标题" in preview, "应该包含数据集3的数据"

        # 验证总采样数不超过限制
        assert count <= 20, f"总采样数 {count} 不应超过 max_items 20"
        assert count >= 15, f"总采样数 {count} 应该接近 max_items 20"

    def test_preview_empty_datasets(self, chat_service):
        """测试空数据集列表"""
        preview, count = chat_service._build_dataset_preview([], max_items=20)
        assert preview == "", "空数据集应返回空字符串"
        assert count == 0, "空数据集应返回0条数据"

    def test_preview_datasets_with_no_items(self, chat_service):
        """测试数据集为空的场景"""
        datasets = [
            QueryDataset(
                route_id="empty",
                provider="test",
                name="空数据集",
                generated_path="/empty",
                items=[],
                feed_title="空数据集",
            )
        ]

        preview, count = chat_service._build_dataset_preview(datasets, max_items=20)
        assert "[空数据集]" in preview, "应该包含数据集标题"
        assert count == 0, "没有数据项时应返回0"

    def test_preview_respects_max_items_limit(self, chat_service):
        """测试严格遵守 max_items 限制"""
        datasets = [
            QueryDataset(
                route_id="large",
                provider="test",
                name="大数据集",
                generated_path="/large",
                items=[{"title": f"标题{i}"} for i in range(100)],
                feed_title="大数据集",
            )
        ]

        preview, count = chat_service._build_dataset_preview(datasets, max_items=10)
        assert count == 10, "应该严格限制在10条"
        assert "标题9" in preview, "应该包含第10条数据"
        assert "标题10" not in preview, "不应该包含第11条数据"

    def test_preview_with_missing_fields(self, chat_service):
        """测试数据项缺少字段的场景"""
        datasets = [
            QueryDataset(
                route_id="incomplete",
                provider="test",
                name="不完整数据",
                generated_path="/incomplete",
                items=[
                    {"title": "有标题"},
                    {"description": "只有描述"},
                    {"keyword": "关键词"},
                    {},  # 完全空的记录
                ],
                feed_title="不完整数据",
            )
        ]

        preview, count = chat_service._build_dataset_preview(datasets, max_items=10)
        assert count == 4, "应该处理所有记录"
        assert "有标题" in preview
        assert "只有描述" in preview
        assert "关键词" in preview
        assert "未命名" in preview, "空记录应显示'未命名'"

    def test_preview_description_truncation(self, chat_service):
        """测试描述文本截断"""
        long_desc = "x" * 200
        datasets = [
            QueryDataset(
                route_id="long",
                provider="test",
                name="长描述数据",
                generated_path="/long",
                items=[{"title": "测试", "description": long_desc}],
                feed_title="长描述数据",
            )
        ]

        preview, count = chat_service._build_dataset_preview(datasets, max_items=5)
        # 描述应该被截断为120字符
        assert long_desc[:120] in preview
        assert long_desc in preview or len(preview) < len(long_desc) + 50

    def test_preview_uneven_dataset_sizes(self, chat_service):
        """测试数据集大小不均的场景"""
        datasets = [
            QueryDataset(
                route_id="small",
                provider="test",
                name="小数据集",
                generated_path="/small",
                items=[{"title": f"小-{i}"} for i in range(3)],
                feed_title="小数据集",
            ),
            QueryDataset(
                route_id="large",
                provider="test",
                name="大数据集",
                generated_path="/large",
                items=[{"title": f"大-{i}"} for i in range(50)],
                feed_title="大数据集",
            ),
        ]

        preview, count = chat_service._build_dataset_preview(datasets, max_items=20)

        # 即使小数据集只有3条，也应该被包含
        assert "[小数据集]" in preview
        assert "[大数据集]" in preview
        assert "小-0" in preview
        assert "大-0" in preview
