"""
RAGInAction 订阅解析集成测试

验证参数验证与订阅解析逻辑在 RAG 流程中的正确集成。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from orchestrator.rag_in_action import RAGInAction


@pytest.fixture
def mock_rag_pipeline():
    """Mock RAG Pipeline"""
    pipeline = Mock()
    # 模拟返回完整的 bilibili_video schema
    pipeline.search.return_value = [
        (
            "bilibili_video",
            0.95,
            {
                "route_id": "bilibili_video",
                "name": "UP 主投稿",
                "path_template": ["/user/video/:uid/:embed?"],
                "platform": "bilibili",  # ✅ 包含 platform
                "entity_type": "user",    # ✅ 包含 entity_type
                "parameters": [  # ✅ 列表形式
                    {
                        "name": "uid",
                        "type": "string",
                        "description": "用户 id",
                        "required": True,
                        "parameter_type": "entity_ref"  # ✅ 明确标记
                    },
                    {
                        "name": "embed",
                        "type": "string",
                        "required": False,
                        "parameter_type": "literal"
                    }
                ],
                "required_identifiers": ["uid"]
            }
        )
    ]
    return pipeline


@pytest.fixture
def mock_llm_client():
    """Mock LLM Client"""
    client = Mock()
    return client


@pytest.fixture
def mock_query_parser():
    """Mock Query Parser"""
    parser = Mock()
    # 模拟返回解析结果（LLM 提取的参数可能是名字）
    parser.parse.return_value = {
        "status": "success",
        "selected_tool": {
            "route_id": "bilibili_video",
            "name": "UP 主投稿"
        },
        "parameters_filled": {
            "uid": "行业101",  # ⚠️ 名字，不是ID
            "embed": "true"
        },
        "reasoning": "用户想查看 UP 主行业101的投稿视频"
    }
    return parser


class TestRAGInActionSubscriptionIntegration:
    """测试 RAGInAction 中的订阅解析集成"""

    @patch('orchestrator.rag_in_action.validate_and_resolve_params')
    @patch('orchestrator.rag_in_action.QueryParser')
    def test_subscription_resolution_success(
        self,
        mock_parser_class,
        mock_validate_func,
        mock_rag_pipeline,
        mock_llm_client,
        mock_query_parser
    ):
        """测试：订阅解析成功，参数被正确替换"""
        # Setup mocks
        mock_parser_class.return_value = mock_query_parser

        # Mock validate_and_resolve_params（订阅解析成功）
        mock_validate_func.return_value = {
            "uid": "1566847",  # ✅ 解析后的真实 ID
            "embed": "true"
        }

        # 创建 RAGInAction 实例
        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline,
            llm_client=mock_llm_client
        )

        # 执行查询
        result = rag_in_action.process(
            user_query="我想看看行业101的投稿视频",
            verbose=False
        )

        # 验证结果
        assert result["status"] == "success"
        assert result["parameters_filled"] == {
            "uid": "1566847",  # ✅ 应该是解析后的ID
            "embed": "true"
        }

        # 验证 validate_and_resolve_params 被调用
        mock_validate_func.assert_called_once()
        call_args = mock_validate_func.call_args[1]
        assert call_args["params"] == {"uid": "行业101", "embed": "true"}
        assert call_args["user_query"] == "我想看看行业101的投稿视频"
        assert "platform" in call_args["tool_schema"]
        assert call_args["tool_schema"]["platform"] == "bilibili"

    @patch('orchestrator.rag_in_action.validate_and_resolve_params')
    @patch('orchestrator.rag_in_action.QueryParser')
    def test_subscription_resolution_fallback(
        self,
        mock_parser_class,
        mock_validate_func,
        mock_rag_pipeline,
        mock_llm_client,
        mock_query_parser
    ):
        """测试：订阅解析失败，降级使用原始参数"""
        # Setup mocks
        mock_parser_class.return_value = mock_query_parser

        # Mock validate_and_resolve_params（订阅解析失败，返回原值）
        mock_validate_func.return_value = {
            "uid": "行业101",  # ⚠️ 未找到订阅，返回原值
            "embed": "true"
        }

        # 创建 RAGInAction 实例
        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline,
            llm_client=mock_llm_client
        )

        # 执行查询
        result = rag_in_action.process(
            user_query="我想看看未订阅UP主的投稿",
            verbose=False
        )

        # 验证结果
        assert result["status"] == "success"
        assert result["parameters_filled"]["uid"] == "行业101"  # 降级使用原值

    @patch('orchestrator.rag_in_action.validate_and_resolve_params')
    @patch('orchestrator.rag_in_action.QueryParser')
    def test_subscription_resolution_exception_handling(
        self,
        mock_parser_class,
        mock_validate_func,
        mock_rag_pipeline,
        mock_llm_client,
        mock_query_parser
    ):
        """测试：订阅解析抛出异常，降级处理"""
        # Setup mocks
        mock_parser_class.return_value = mock_query_parser

        # Mock validate_and_resolve_params 抛出异常
        mock_validate_func.side_effect = Exception("订阅服务不可用")

        # 创建 RAGInAction 实例
        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline,
            llm_client=mock_llm_client
        )

        # 执行查询（不应该崩溃）
        result = rag_in_action.process(
            user_query="我想看看行业101的投稿视频",
            verbose=False
        )

        # 验证结果：降级使用原始参数
        assert result["status"] == "success"
        assert result["parameters_filled"] == {
            "uid": "行业101",  # 原始参数
            "embed": "true"
        }

    @patch('orchestrator.rag_in_action.validate_and_resolve_params')
    @patch('orchestrator.rag_in_action.QueryParser')
    def test_no_subscription_needed(
        self,
        mock_parser_class,
        mock_validate_func,
        mock_rag_pipeline,
        mock_llm_client
    ):
        """测试：参数不需要订阅解析（直接使用）"""
        # 修改 mock_query_parser 返回数字 uid
        parser = Mock()
        parser.parse.return_value = {
            "status": "success",
            "selected_tool": {
                "route_id": "bilibili_video",
                "name": "UP 主投稿"
            },
            "parameters_filled": {
                "uid": "1566847",  # ✅ 已经是数字ID
                "embed": "false"
            },
            "reasoning": "用户提供了精确的 uid"
        }
        mock_parser_class.return_value = parser

        # Mock validate_and_resolve_params（无需解析，直接返回）
        mock_validate_func.return_value = {
            "uid": "1566847",
            "embed": "false"
        }

        # 创建 RAGInAction 实例
        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline,
            llm_client=mock_llm_client
        )

        # 执行查询
        result = rag_in_action.process(
            user_query="我想看看uid为1566847的up主投稿",
            verbose=False
        )

        # 验证结果
        assert result["status"] == "success"
        assert result["parameters_filled"]["uid"] == "1566847"

        # 验证 validate_and_resolve_params 被调用（即使不需要解析）
        mock_validate_func.assert_called_once()


class TestRAGInActionBackwardCompatibility:
    """测试向后兼容性（不影响���有流程）"""

    @patch('orchestrator.rag_in_action.validate_and_resolve_params')
    @patch('orchestrator.rag_in_action.QueryParser')
    def test_parse_failure_skips_validation(
        self,
        mock_parser_class,
        mock_validate_func,
        mock_rag_pipeline,
        mock_llm_client
    ):
        """测试：LLM 解析失败时，跳过订阅解析"""
        # 修改 mock_query_parser 返回失败状态
        parser = Mock()
        parser.parse.return_value = {
            "status": "needs_clarification",
            "selected_tool": None,
            "parameters_filled": {},
            "clarification_question": "请明确指定UP主名称"
        }
        mock_parser_class.return_value = parser

        # 创建 RAGInAction 实例
        rag_in_action = RAGInAction(
            rag_pipeline=mock_rag_pipeline,
            llm_client=mock_llm_client
        )

        # 执行查询
        result = rag_in_action.process(
            user_query="模糊查询",
            verbose=False
        )

        # 验证结果
        assert result["status"] == "needs_clarification"

        # 验证 validate_and_resolve_params 未被调用
        mock_validate_func.assert_not_called()
