"""
RAGInAction 低置信度检测测试

验证当 RAG 检索结果相似度不够高时，系统能正确返回 low_confidence 状态，
而不是盲目使用第一个结果调用 LLM。
"""

import pytest
from unittest.mock import Mock, patch
from orchestrator.rag_in_action import RAGInAction


@pytest.fixture
def mock_rag_pipeline_low_score():
    """Mock RAG Pipeline - 返回低相似度结果"""
    pipeline = Mock()
    # 模拟返回低于高置信度阈值（0.7）但高于最低阈值（0.5）的结果
    pipeline.search.return_value = [
        (
            "hupu_bbs",
            0.55,  # 低于 0.7 的高置信度阈值
            {
                "route_id": "hupu_bbs",
                "name": "虎扑社区",
                "datasource": "hupu",
                "description": "虎扑社区帖子列表",
                "path_template": ["/bbs/:id"],
                "parameters": [{"name": "id", "type": "string", "required": True}],
            }
        ),
        (
            "tieba_post",
            0.52,
            {
                "route_id": "tieba_post",
                "name": "贴吧帖子",
                "datasource": "tieba",
                "description": "百度贴吧帖子",
                "path_template": ["/tieba/:name"],
                "parameters": [{"name": "name", "type": "string", "required": True}],
            }
        ),
    ]
    return pipeline


@pytest.fixture
def mock_rag_pipeline_high_score():
    """Mock RAG Pipeline - 返回高相似度结果"""
    pipeline = Mock()
    pipeline.search.return_value = [
        (
            "hupu_bbs",
            0.85,  # 高于 0.7 的高置信度阈值
            {
                "route_id": "hupu_bbs",
                "name": "虎扑社区",
                "datasource": "hupu",
                "description": "虎扑社区帖子列表",
                "path_template": ["/bbs/:id"],
                "parameters": [{"name": "id", "type": "string", "required": True}],
            }
        ),
    ]
    return pipeline


@pytest.fixture
def mock_llm_client():
    """Mock LLM Client"""
    client = Mock()
    # 模拟 LLM 返回成功的解析结果
    client.generate.return_value = '''
    {
        "status": "success",
        "reasoning": "用户想查看虎扑步行街帖子",
        "selected_tool": {
            "route_id": "hupu_bbs",
            "provider": "hupu",
            "name": "虎扑社区"
        },
        "generated_path": "/hupu/bbs/bxj",
        "parameters_filled": {"id": "bxj"},
        "post_filters": []
    }
    '''
    return client


class TestLowConfidenceDetection:
    """低置信度检测测试"""

    def test_low_confidence_returns_early(
        self, mock_rag_pipeline_low_score, mock_llm_client
    ):
        """测试：当最高相似度低于高置信度阈值时，应该返回 low_confidence 而不调用 LLM"""
        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline_low_score,
            llm_client=mock_llm_client,
        )

        result = rag_in_action.process("查看今天的天气预报")

        # 验证返回 low_confidence 状态
        assert result["status"] == "low_confidence"
        assert "置信度" in result["reasoning"] or "confidence" in result["reasoning"].lower()
        assert result["generated_path"] is None
        assert result["selected_tool"] is None

        # 验证提供了候选工具列表
        assert "retrieved_tools" in result
        assert len(result["retrieved_tools"]) == 2

        # 验证包含最高分数信息
        assert "top_score" in result
        assert result["top_score"] == 0.55

        # 关键：验证 LLM 没有被调用（节省成本和时间）
        mock_llm_client.generate.assert_not_called()

    def test_high_confidence_continues_to_llm(
        self, mock_rag_pipeline_high_score, mock_llm_client
    ):
        """测试：当最高相似度高于高置信度阈值时，应该正常调用 LLM"""
        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline_high_score,
            llm_client=mock_llm_client,
        )

        result = rag_in_action.process("虎扑步行街最新帖子")

        # 验证正常流程：调用了 LLM 并返回成功
        assert result["status"] == "success"
        assert result["generated_path"] is not None

        # 关键：验证 LLM 被调用了
        mock_llm_client.generate.assert_called_once()

    def test_clarification_question_contains_candidates(
        self, mock_rag_pipeline_low_score, mock_llm_client
    ):
        """测试：低置信度时的澄清问题应该包含候选数据源信息"""
        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline_low_score,
            llm_client=mock_llm_client,
        )

        result = rag_in_action.process("随便什么查询")

        clarification = result.get("clarification_question", "")

        # 验证澄清问题包含有用信息
        assert "虎扑" in clarification or "hupu" in clarification.lower()
        assert "匹配度" in clarification or "55%" in clarification

    def test_empty_rag_returns_not_found(self, mock_llm_client):
        """测试：当 RAG 没有返回任何结果时，应该返回 not_found"""
        mock_rag_pipeline = Mock()
        mock_rag_pipeline.search.return_value = []

        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline,
            llm_client=mock_llm_client,
        )

        result = rag_in_action.process("完全不相关的查询 xyz123")

        assert result["status"] == "not_found"
        mock_llm_client.generate.assert_not_called()


class TestLowConfidenceThresholdConfiguration:
    """低置信度阈值配置测试"""

    def test_threshold_from_config(self, mock_rag_pipeline_low_score, mock_llm_client):
        """测试：阈值应该从配置中读取"""
        with patch("orchestrator.rag_in_action.RETRIEVAL_CONFIG", {
            "high_confidence_threshold": 0.9,  # 设置更高的阈值
            "score_threshold": 0.5,
            "top_k": 5,
        }):
            rag_in_action = RAGInAction(
                rag_pipeline=mock_rag_pipeline_low_score,
                llm_client=mock_llm_client,
            )

            # 0.55 < 0.9，应该返回 low_confidence
            result = rag_in_action.process("测试查询")
            assert result["status"] == "low_confidence"

    def test_borderline_score_passes(self, mock_llm_client):
        """测试：刚好等于阈值的分数应该通过"""
        mock_rag_pipeline = Mock()
        mock_rag_pipeline.search.return_value = [
            (
                "test_route",
                0.70,  # 刚好等于默认阈值 0.7
                {
                    "route_id": "test_route",
                    "name": "测试路由",
                    "datasource": "test",
                    "path_template": ["/test/:id"],
                    "parameters": [{"name": "id", "type": "string", "required": True}],
                }
            ),
        ]

        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline,
            llm_client=mock_llm_client,
        )

        result = rag_in_action.process("测试查询")

        # 0.70 >= 0.70，应该继续调用 LLM
        assert result["status"] != "low_confidence"
        mock_llm_client.generate.assert_called_once()


class TestFormatLowConfidenceCandidates:
    """候选工具格式化测试"""

    def test_format_candidates_with_description(self):
        """测试：格式化带描述的候选工具"""
        tools = [
            {
                "name": "虎扑社区",
                "datasource": "hupu",
                "description": "虎扑步行街等社区帖子列表",
                "score": 0.65,
            },
            {
                "name": "贴吧帖子",
                "datasource": "tieba",
                "description": "百度贴吧各版块帖子",
                "score": 0.55,
            },
        ]

        result = RAGInAction._format_low_confidence_candidates(tools)

        assert "虎扑社区" in result
        assert "贴吧帖子" in result
        assert "65%" in result
        assert "55%" in result
        assert "hupu" in result
        assert "tieba" in result

    def test_format_candidates_empty_list(self):
        """测试：空列表应该返回空字符串"""
        result = RAGInAction._format_low_confidence_candidates([])
        assert result == ""

    def test_format_candidates_truncates_long_description(self):
        """测试：过长的描述应该被截断"""
        # 创建一个超过 60 字符的描述
        long_description = "A" * 80  # 80 个字符，肯定超过 60
        tools = [
            {
                "name": "测试工具",
                "datasource": "test",
                "description": long_description,
                "score": 0.60,
            },
        ]

        result = RAGInAction._format_low_confidence_candidates(tools)

        # 描述应该被截断到 60 字符以内（加省略号）
        assert "..." in result
        # 原始的 80 个 A 不应该完整出现
        assert long_description not in result
