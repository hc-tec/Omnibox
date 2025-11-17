"""V5.0 Phase 5 - 真实 RSSHub 数据格式测试。

测试使用真实的 B 站、知乎等平台的数据格式，验证元数据提取器能正确处理：
1. 复杂的嵌套字段（author、stats 对象）
2. 大量记录（100+ 条）
3. 字段缺失和 None 值
4. 多样化的字段类型
"""

import pytest
from langgraph_agents.metadata_extractor import (
    extract_schema_info,
    extract_statistics,
    extract_sample_items,
    calculate_quality_score
)


class TestBilibiliDataFormat:
    """测试 B 站真实数据格式。"""

    @pytest.fixture
    def bilibili_user_video_data(self):
        """模拟 B 站用户视频数据格式。"""
        return {
            "items": [
                {
                    "id": "BV1234567890",
                    "title": "【科技】2024年度科技趋势总结",
                    "description": "这是一个测试描述...",
                    "author": {
                        "name": "科技美学",
                        "uid": "12345678",
                        "avatar": "https://i0.hdslb.com/..."
                    },
                    "stats": {
                        "view": 1234567,
                        "like": 98765,
                        "coin": 12345,
                        "favorite": 23456,
                        "share": 3456,
                        "reply": 1234
                    },
                    "duration": "15:32",
                    "pubDate": "2024-01-15T10:30:00.000Z",
                    "link": "https://www.bilibili.com/video/BV1234567890",
                    "category": ["科技", "数码"],
                    "media_url": "https://example.com/video.mp4",
                    "media_thumbnail": "https://i0.hdslb.com/cover.jpg"
                },
                {
                    "id": "BV9876543210",
                    "title": "测试视频2",
                    "description": None,  # 可能为 None
                    "author": {
                        "name": "测试UP主",
                        "uid": "87654321",
                        "avatar": None
                    },
                    "stats": {
                        "view": 500,
                        "like": 10,
                        "coin": 2,
                        "favorite": 5,
                        "share": 0,
                        "reply": 1
                    },
                    "duration": "2:15",
                    "pubDate": "2024-01-16T08:00:00.000Z",
                    "link": "https://www.bilibili.com/video/BV9876543210",
                    "category": [],  # 可能为空列表
                    "media_url": None,
                    "media_thumbnail": None
                }
            ]
        }

    def test_extract_schema_with_nested_objects(self, bilibili_user_video_data):
        """测试提取包含嵌套对象的 Schema。"""
        schema = extract_schema_info(bilibili_user_video_data)

        assert schema is not None
        # 基本字段
        assert schema["id"] == "str"
        assert schema["title"] == "str"
        assert schema["description"] == "str"  # 第一条是 str

        # 嵌套对象
        assert schema["author"] == "dict"
        assert schema["stats"] == "dict"

        # 其他字段
        assert schema["category"] == "list"
        assert schema["duration"] == "str"

    def test_extract_statistics_with_nested_fields(self, bilibili_user_video_data):
        """测试提取嵌套字段的统计信息。"""
        stats = extract_statistics(bilibili_user_video_data)

        assert stats is not None
        assert stats["record_count"] == 2

        # 顶层字段统计
        field_stats = stats["field_stats"]
        assert field_stats["title"]["non_null_count"] == 2
        assert field_stats["title"]["completeness"] == 1.0

        # description 有一个 None
        assert field_stats["description"]["non_null_count"] == 1
        assert field_stats["description"]["completeness"] == 0.5

        # media_url 有一个 None
        assert field_stats["media_url"]["non_null_count"] == 1
        assert field_stats["media_url"]["completeness"] == 0.5

    def test_quality_score_with_partial_completeness(self, bilibili_user_video_data):
        """测试部分完整性的质量评分。"""
        schema = extract_schema_info(bilibili_user_video_data)
        stats = extract_statistics(bilibili_user_video_data)
        score = calculate_quality_score(schema, stats)

        # Schema 完整性：1.0（有 schema）
        # 字段完整性：约 0.75-0.85（大部分字段完整，少数 None）
        # 预期：0.85-0.95
        assert score > 0.8
        assert score <= 1.0


class TestZhihuDataFormat:
    """测试知乎真实数据格式。"""

    @pytest.fixture
    def zhihu_user_answer_data(self):
        """模拟知乎用户回答数据格式。"""
        return {
            "items": [
                {
                    "id": "123456789",
                    "title": "如何评价 2024 年的技术趋势？",
                    "content": "<p>这是一个很好的问题...</p>",
                    "content_plain": "这是一个很好的问题...",
                    "author": {
                        "name": "张三",
                        "url_token": "zhang-san-123",
                        "headline": "软件工程师",
                        "avatar_url": "https://pic1.zhimg.com/..."
                    },
                    "question": {
                        "id": "987654321",
                        "title": "如何评价 2024 年的技术趋势？"
                    },
                    "stats": {
                        "voteup_count": 1234,
                        "comment_count": 56,
                        "thanks_count": 78
                    },
                    "created_time": 1705305600,
                    "updated_time": 1705392000,
                    "url": "https://www.zhihu.com/question/987654321/answer/123456789"
                },
                {
                    "id": "234567890",
                    "title": "Python 和 JavaScript 哪个更好？",
                    "content": "<p>各有优势...</p>",
                    "content_plain": None,  # 可能缺失
                    "author": {
                        "name": "李四",
                        "url_token": "li-si-456",
                        "headline": None,
                        "avatar_url": None
                    },
                    "question": {
                        "id": "876543210",
                        "title": "Python 和 JavaScript 哪个更好？"
                    },
                    "stats": {
                        "voteup_count": 45,
                        "comment_count": 8,
                        "thanks_count": 2
                    },
                    "created_time": 1705219200,
                    "updated_time": 1705219200,
                    "url": "https://www.zhihu.com/question/876543210/answer/234567890"
                }
            ]
        }

    def test_extract_schema_zhihu_format(self, zhihu_user_answer_data):
        """测试知乎格式的 Schema 提取。"""
        schema = extract_schema_info(zhihu_user_answer_data)

        assert schema is not None
        assert schema["id"] == "str"
        assert schema["title"] == "str"
        assert schema["content"] == "str"
        assert schema["author"] == "dict"
        assert schema["question"] == "dict"
        assert schema["stats"] == "dict"
        assert schema["created_time"] == "int"

    def test_extract_statistics_zhihu_format(self, zhihu_user_answer_data):
        """测试知乎格式的统计信息。"""
        stats = extract_statistics(zhihu_user_answer_data)

        assert stats["record_count"] == 2
        field_stats = stats["field_stats"]

        # content_plain 有一个 None
        assert field_stats["content_plain"]["non_null_count"] == 1
        assert field_stats["content_plain"]["completeness"] == 0.5


class TestLargeDataset:
    """测试大数据集场景。"""

    def test_extract_schema_from_large_dataset(self):
        """测试从大数据集（100+ 条）提取 Schema。"""
        # 生成 100 条数据
        items = [
            {
                "id": str(i),
                "title": f"标题 {i}",
                "view_count": i * 100,
                "author": {"name": f"作者{i}", "uid": str(i * 10)},
                "tags": [f"tag{i}", f"tag{i+1}"]
            }
            for i in range(100)
        ]

        data = {"items": items}
        schema = extract_schema_info(data)

        # 应该只从第一条提取，不会遍历所有 100 条
        assert schema is not None
        assert schema["id"] == "str"
        assert schema["view_count"] == "int"
        assert schema["author"] == "dict"
        assert schema["tags"] == "list"

    def test_extract_statistics_from_large_dataset(self):
        """测试从大数据集提取统计信息（会遍历所有记录）。"""
        # 生成 100 条数据，其中 10 条缺失 title
        items = [
            {
                "id": str(i),
                "title": f"标题 {i}" if i % 10 != 0 else None,  # 每 10 条有 1 条 None
                "view_count": i * 100
            }
            for i in range(100)
        ]

        data = {"items": items}
        stats = extract_statistics(data)

        assert stats["record_count"] == 100
        field_stats = stats["field_stats"]

        # title 有 10 个 None
        assert field_stats["title"]["non_null_count"] == 90
        assert field_stats["title"]["completeness"] == 0.9

        # id 和 view_count 全部非 None
        assert field_stats["id"]["completeness"] == 1.0
        assert field_stats["view_count"]["completeness"] == 1.0

    def test_sample_items_from_large_dataset(self):
        """测试从大数据集采样。"""
        items = [{"id": str(i)} for i in range(100)]
        data = {"items": items}

        samples = extract_sample_items(data, sample_size=5)

        # 只返回前 5 条
        assert len(samples) == 5
        assert samples[0]["id"] == "0"
        assert samples[4]["id"] == "4"


class TestEdgeCasesRealData:
    """测试真实数据的边界情况。"""

    def test_mixed_data_types_in_field(self):
        """测试字段类型不一致的真实场景。"""
        # 真实场景：有些平台的 view_count 可能是数字或字符串
        data = {
            "items": [
                {"id": "1", "view_count": 1000},  # int
                {"id": "2", "view_count": "2.3万"},  # str（中文格式化）
                {"id": "3", "view_count": 3000}
            ]
        }

        schema = extract_schema_info(data)
        # 使用第一条的类型
        assert schema["view_count"] == "int"

    def test_very_deep_nesting(self):
        """测试非常深的嵌套结构。"""
        data = {
            "items": [
                {
                    "id": "1",
                    "user": {
                        "profile": {
                            "info": {
                                "name": "张三",
                                "level": {
                                    "value": 6,
                                    "label": "大神"
                                }
                            }
                        }
                    }
                }
            ]
        }

        schema = extract_schema_info(data)
        # 只提取第一层
        assert schema["id"] == "str"
        assert schema["user"] == "dict"

    def test_unicode_and_emoji_content(self):
        """测试 Unicode 和 Emoji 内容。"""
        data = {
            "items": [
                {
                    "id": "1",
                    "title": "🚀 2024年AI技术大盘点 🎉",
                    "content": "这是一个包含中文、English、日本語、한국어的内容",
                    "emoji_reaction": "👍❤️😂"
                },
                {
                    "id": "2",
                    "title": "测试标题",
                    "content": None,
                    "emoji_reaction": None
                }
            ]
        }

        schema = extract_schema_info(data)
        stats = extract_statistics(data)

        assert schema is not None
        assert stats["record_count"] == 2
        assert stats["field_stats"]["content"]["completeness"] == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
