"""测试 QueryParser（订阅查询解析器）

测试 LLM 驱动的自然语言查询解析功能。
"""

import pytest
import json
from unittest.mock import Mock
from services.subscription.query_parser import QueryParser, ParsedQuery


class TestQueryParser:
    """QueryParser 测试套件"""

    @pytest.fixture
    def mock_llm_client(self):
        """创建 Mock LLM 客户端"""
        client = Mock()
        return client

    @pytest.fixture
    def parser(self, mock_llm_client):
        """创建 QueryParser 实例"""
        return QueryParser(mock_llm_client)

    def test_parse_bilibili_video_query(self, parser, mock_llm_client):
        """测试解析 B站投稿视频查询"""
        # 模拟 LLM 响应
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": "投稿视频",
            "platform": "bilibili",
            "confidence": 0.9
        })

        # 执行解析
        result = parser.parse("科技美学的最新投稿")

        # 验证结果
        assert result.entity_name == "科技美学"
        assert result.action == "投稿视频"
        assert result.platform == "bilibili"
        assert result.confidence == 0.9

    def test_parse_bilibili_following_query(self, parser, mock_llm_client):
        """测试解析 B站关注列表查询"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "那岩",
            "action": "关注列表",
            "platform": "bilibili",
            "confidence": 0.85
        })

        result = parser.parse("那岩关注了谁")

        assert result.entity_name == "那岩"
        assert result.action == "关注列表"
        assert result.platform == "bilibili"
        assert result.confidence == 0.85

    def test_parse_zhihu_column_query(self, parser, mock_llm_client):
        """测试解析知乎专栏查询"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "少数派",
            "action": "文章",
            "platform": "zhihu",
            "confidence": 0.9
        })

        result = parser.parse("少数派专栏的最新文章")

        assert result.entity_name == "少数派"
        assert result.action == "文章"
        assert result.platform == "zhihu"

    def test_parse_github_commits_query(self, parser, mock_llm_client):
        """测试解析 GitHub commits 查询"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "langchain",
            "action": "commits",
            "platform": "github",
            "confidence": 0.85
        })

        result = parser.parse("langchain的最新提交记录")

        assert result.entity_name == "langchain"
        assert result.action == "commits"
        assert result.platform == "github"

    def test_parse_github_issues_query(self, parser, mock_llm_client):
        """测试解析 GitHub issues 查询"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "langchain",
            "action": "issues",
            "platform": "github",
            "confidence": 0.9
        })

        result = parser.parse("查看langchain项目的issues")

        assert result.entity_name == "langchain"
        assert result.action == "issues"
        assert result.platform == "github"

    def test_parse_entity_only(self, parser, mock_llm_client):
        """测试只包含实体名称的查询"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": None,
            "platform": None,
            "confidence": 0.7
        })

        result = parser.parse("科技美学")

        assert result.entity_name == "科技美学"
        assert result.action is None
        assert result.platform is None
        assert result.confidence == 0.7

    def test_parse_with_alias(self, parser, mock_llm_client):
        """测试使用别名的查询"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "那岩",
            "action": "投稿视频",
            "platform": "bilibili",
            "confidence": 0.8
        })

        result = parser.parse("那岩的视频")

        assert result.entity_name == "那岩"
        assert result.action == "投稿视频"

    def test_parse_invalid_json_response(self, parser, mock_llm_client):
        """测试 LLM 返回无效 JSON 的情况"""
        mock_llm_client.chat.return_value = "This is not JSON"

        with pytest.raises(ValueError, match="LLM 响应格式错误"):
            parser.parse("测试查询")

    def test_parse_missing_entity_name(self, parser, mock_llm_client):
        """测试 LLM 响应缺少 entity_name 字段"""
        mock_llm_client.chat.return_value = json.dumps({
            "action": "投稿视频",
            "platform": "bilibili"
        })

        with pytest.raises(ValueError, match="缺少 entity_name 字段"):
            parser.parse("测试查询")

    def test_parse_default_confidence(self, parser, mock_llm_client):
        """测试默认置信度"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": "投稿视频",
            "platform": "bilibili"
            # 没有 confidence 字段
        })

        result = parser.parse("科技美学的投稿")

        assert result.confidence == 0.8  # 默认值

    def test_parse_with_temperature(self, parser, mock_llm_client):
        """测试 LLM 调用时使用低温度参数"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": "投稿视频",
            "platform": "bilibili",
            "confidence": 0.9
        })

        parser.parse("科技美学的投稿")

        # 验证 LLM 调用参数
        assert mock_llm_client.chat.called
        call_kwargs = mock_llm_client.chat.call_args[1]
        assert call_kwargs["temperature"] == 0.1  # 低温度确保确定性
