"""
IntentService单元测试
测试内容：
1. 数据查询意图识别
2. 闲聊意图识别
3. 边缘情况处理
4. 单例模式
"""

import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.intent_service import IntentService, IntentResult, get_intent_service


class TestIntentRecognition:
    """意图识别测试"""

    def test_data_query_intent_with_keywords(self):
        """测试包含数据查询关键词的识别"""
        service = IntentService()

        test_cases = [
            "虎扑步行街最新帖子",
            "B站热门视频",
            "微博热搜",
            "GitHub trending",
            "V2EX最新讨论",
            "给我看看知乎的热门文章",
        ]

        for query in test_cases:
            result = service.recognize(query)
            assert result.intent_type == "data_query", f"应识别为数据查询: {query}"
            assert result.confidence > 0.5

    def test_chitchat_intent_with_keywords(self):
        """测试包含闲聊关键词的识别"""
        service = IntentService()

        test_cases = [
            "你好",
            "您好",
            "hi",
            "hello",
            "谢谢",
            "再见",
        ]

        for query in test_cases:
            result = service.recognize(query)
            assert result.intent_type == "chitchat", f"应识别为闲聊: {query}"
            assert result.confidence > 0.5

    def test_question_mark_implies_data_query(self):
        """测试包含问号的查询默认为数据查询"""
        service = IntentService()

        result1 = service.recognize("有什么推荐的吗？")
        assert result1.intent_type == "data_query"

        result2 = service.recognize("What's new?")
        assert result2.intent_type == "data_query"

    def test_short_query_implies_chitchat(self):
        """测试短查询默认为闲聊"""
        service = IntentService()

        result = service.recognize("嗯嗯")
        assert result.intent_type == "chitchat"

    def test_empty_query_is_chitchat(self):
        """测试空查询为闲聊"""
        service = IntentService()

        result = service.recognize("")
        assert result.intent_type == "chitchat"
        assert result.confidence == 1.0

    def test_default_fallback_to_data_query(self):
        """测试默认fallback为数据查询"""
        service = IntentService()

        # 中等长度的模糊查询
        result = service.recognize("最近有什么好看的内容")
        assert result.intent_type == "data_query"
        assert result.confidence >= 0.5


class TestIntentConfidence:
    """置信度测试"""

    def test_more_keywords_higher_confidence(self):
        """测试更多关键词 -> 更高或相等置信度（有上限）"""
        service = IntentService()

        # 1个关键词
        result1 = service.recognize("虎扑")
        confidence1 = result1.confidence

        # 2个关键词
        result2 = service.recognize("虎扑最新帖子")
        confidence2 = result2.confidence

        # 3个关键词
        result3 = service.recognize("虎扑步行街最新帖子")
        confidence3 = result3.confidence

        # 置信度应该递增或达到上限
        assert confidence1 <= confidence2 <= confidence3
        assert confidence3 >= confidence1  # 至少应该不低于起始值

    def test_confidence_range(self):
        """测试置信度范围在[0, 1]之间"""
        service = IntentService()

        test_queries = [
            "虎扑步行街最新帖子",
            "你好",
            "",
            "随便说点什么",
        ]

        for query in test_queries:
            result = service.recognize(query)
            assert 0.0 <= result.confidence <= 1.0, f"置信度超出范围: {query}"


class TestIsDataQuery:
    """is_data_query快捷方法测试"""

    def test_is_data_query_method(self):
        """测试is_data_query快捷方法"""
        service = IntentService()

        assert service.is_data_query("虎扑步行街最新帖子") is True
        assert service.is_data_query("你好") is False

    def test_is_data_query_with_threshold(self):
        """测试is_data_query的阈值参数"""
        service = IntentService()

        # 低置信度的数据查询
        query = "有什么吗？"  # 只有问号，置信度0.6

        assert service.is_data_query(query, threshold=0.5) is True
        assert service.is_data_query(query, threshold=0.7) is False


class TestGlobalSingleton:
    """全局单例测试"""

    def test_get_intent_service_singleton(self):
        """测试get_intent_service返回单例"""
        service1 = get_intent_service()
        service2 = get_intent_service()

        assert service1 is service2


class TestEdgeCases:
    """边缘情况测试"""

    def test_mixed_keywords(self):
        """测试同时包含数据查询和闲聊关键词"""
        service = IntentService()

        # 数据查询关键词更多
        result1 = service.recognize("你好，帮我查看虎扑步行街最新帖子")
        assert result1.intent_type == "data_query"

        # 闲聊关键词更多（但实际很少见）
        result2 = service.recognize("你好你好谢谢")
        assert result2.intent_type == "chitchat"

    def test_long_query_without_keywords(self):
        """测试没有关键词的长查询"""
        service = IntentService()

        result = service.recognize("我想要一些有趣的内容来看看")
        # 默认fallback为data_query
        assert result.intent_type == "data_query"

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        service = IntentService()

        result1 = service.recognize("虎扑步行街")
        result2 = service.recognize("HUPU步行街")
        result3 = service.recognize("HuPu步行街")

        # 都应该识别为数据查询
        assert result1.intent_type == "data_query"
        assert result2.intent_type == "data_query"
        assert result3.intent_type == "data_query"

    def test_whitespace_handling(self):
        """测试空白字符处理"""
        service = IntentService()

        result1 = service.recognize("  虎扑步行街  ")
        result2 = service.recognize("虎扑步行街")

        assert result1.intent_type == result2.intent_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
