"""
ResearchConfig 配置对象测试
"""

import pytest
from services.research_constants import ResearchConfig, DefaultConfig


def test_research_config_valid_basic():
    """测试基本的有效配置"""
    config = ResearchConfig(user_query="测试查询")
    assert config.user_query == "测试查询"
    assert config.filter_datasource is None
    assert config.max_steps == DefaultConfig.MAX_STEPS
    assert config.task_id is None
    assert config.callback is None
    assert config.initial_state is None
    assert config.reuse_task is False


def test_research_config_valid_full():
    """测试完整的有效配置"""
    def mock_callback(data):
        pass

    config = ResearchConfig(
        user_query="完整配置测试",
        filter_datasource="github",
        max_steps=10,
        task_id="test-task-123",
        callback=mock_callback,
        initial_state={"foo": "bar"},
        reuse_task=True,
    )
    assert config.user_query == "完整配置测试"
    assert config.filter_datasource == "github"
    assert config.max_steps == 10
    assert config.task_id == "test-task-123"
    assert config.callback == mock_callback
    assert config.initial_state == {"foo": "bar"}
    assert config.reuse_task is True


def test_research_config_empty_query_raises():
    """测试空查询抛出异常"""
    with pytest.raises(ValueError, match="user_query 不能为空"):
        ResearchConfig(user_query="")

    with pytest.raises(ValueError, match="user_query 不能为空"):
        ResearchConfig(user_query="   ")


def test_research_config_query_too_long_raises():
    """测试查询过长抛出异常"""
    long_query = "x" * 5001
    with pytest.raises(ValueError, match="user_query 长度不能超过 5000 字符"):
        ResearchConfig(user_query=long_query)


def test_research_config_max_steps_invalid_raises():
    """测试无效的 max_steps 抛出异常"""
    with pytest.raises(ValueError, match="max_steps 必须大于 0"):
        ResearchConfig(user_query="test", max_steps=0)

    with pytest.raises(ValueError, match="max_steps 必须大于 0"):
        ResearchConfig(user_query="test", max_steps=-1)

    with pytest.raises(ValueError, match="max_steps 不能超过 100"):
        ResearchConfig(user_query="test", max_steps=101)


def test_research_config_task_id_invalid_raises():
    """测试无效的 task_id 抛出异常"""
    with pytest.raises(ValueError, match="task_id 必须是非空字符串"):
        ResearchConfig(user_query="test", task_id="")

    with pytest.raises(ValueError, match="task_id 必须是非空字符串"):
        ResearchConfig(user_query="test", task_id="   ")

    long_task_id = "x" * 129
    with pytest.raises(ValueError, match="task_id 长度不能超过 128 字符"):
        ResearchConfig(user_query="test", task_id=long_task_id)


def test_research_config_filter_datasource_invalid_raises():
    """测试无效的 filter_datasource 抛出异常"""
    with pytest.raises(ValueError, match="filter_datasource 必须是非空字符串"):
        ResearchConfig(user_query="test", filter_datasource="")

    with pytest.raises(ValueError, match="filter_datasource 必须是非空字符串"):
        ResearchConfig(user_query="test", filter_datasource="   ")


def test_research_config_initial_state_invalid_raises():
    """测试无效的 initial_state 抛出异常"""
    with pytest.raises(ValueError, match="initial_state 必须是字典类型"):
        ResearchConfig(user_query="test", initial_state="not a dict")

    with pytest.raises(ValueError, match="initial_state 必须是字典类型"):
        ResearchConfig(user_query="test", initial_state=[1, 2, 3])


def test_research_config_callback_invalid_raises():
    """测试无效的 callback 抛出异常"""
    with pytest.raises(ValueError, match="callback 必须是可调用对象"):
        ResearchConfig(user_query="test", callback="not callable")

    with pytest.raises(ValueError, match="callback 必须是可调用对象"):
        ResearchConfig(user_query="test", callback=123)


def test_research_config_from_dict():
    """测试从字典创建配置对象"""
    data = {
        "user_query": "字典测试",
        "filter_datasource": "bilibili",
        "max_steps": 15,
        "task_id": "dict-task",
        "reuse_task": True,
        "extra_field": "ignored",  # 应该被忽略
    }
    config = ResearchConfig.from_dict(data)

    assert config.user_query == "字典测试"
    assert config.filter_datasource == "bilibili"
    assert config.max_steps == 15
    assert config.task_id == "dict-task"
    assert config.reuse_task is True
    assert config.callback is None
    assert config.initial_state is None


def test_research_config_edge_cases():
    """测试边界情况"""
    # 最小有效 max_steps
    config1 = ResearchConfig(user_query="test", max_steps=1)
    assert config1.max_steps == 1

    # 最大有效 max_steps
    config2 = ResearchConfig(user_query="test", max_steps=100)
    assert config2.max_steps == 100

    # 最长有效 query
    long_query = "x" * 5000
    config3 = ResearchConfig(user_query=long_query)
    assert len(config3.user_query) == 5000

    # 最长有效 task_id
    long_task_id = "x" * 128
    config4 = ResearchConfig(user_query="test", task_id=long_task_id)
    assert len(config4.task_id) == 128
