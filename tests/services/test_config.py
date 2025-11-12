"""
测试服务层配置管理

验证统一配置管理的正确性。
"""

import pytest
import os
from services.config import DataQueryConfig, get_data_query_config, reset_data_query_config


class TestDataQueryConfig:
    """测试数据查询配置"""

    def teardown_method(self):
        """每个测试后重置配置单例"""
        reset_data_query_config()

    def test_default_values(self):
        """测试默认配置值"""
        config = DataQueryConfig()

        assert config.single_route_default is False, "默认应该不启用单路模式"
        assert config.multi_route_limit == 3, "默认多路限制应为3"
        assert config.analysis_preview_max_items == 20, "默认预览采样数应为20"
        assert config.description_max_length == 120, "默认描述长度应为120"

    def test_env_override(self, monkeypatch):
        """测试环境变量覆盖配置"""
        # 设置环境变量
        monkeypatch.setenv("DATA_QUERY_SINGLE_ROUTE", "1")
        monkeypatch.setenv("DATA_QUERY_MULTI_ROUTE_LIMIT", "5")
        monkeypatch.setenv("DATA_QUERY_ANALYSIS_PREVIEW_MAX_ITEMS", "30")

        config = DataQueryConfig()

        assert config.single_route_default is True, "环境变量应生效"
        assert config.multi_route_limit == 5
        assert config.analysis_preview_max_items == 30

    def test_singleton_pattern(self):
        """测试配置单例模式"""
        config1 = get_data_query_config()
        config2 = get_data_query_config()

        assert config1 is config2, "应该返回相同的实例"

    def test_reset_singleton(self):
        """测试重置配置单例"""
        config1 = get_data_query_config()
        reset_data_query_config()
        config2 = get_data_query_config()

        assert config1 is not config2, "重置后应返回新实例"

    def test_bool_env_parsing(self, monkeypatch):
        """测试布尔类型环境变量解析"""
        # Pydantic 对布尔值的解析：1/true/True/yes -> True, 0/false/False/no -> False
        test_cases = [
            ("1", True),
            ("0", False),
            ("true", True),
            ("false", False),
        ]

        for env_value, expected in test_cases:
            monkeypatch.setenv("DATA_QUERY_SINGLE_ROUTE", env_value)
            reset_data_query_config()
            config = get_data_query_config()
            assert config.single_route_default == expected, f"环境变量 {env_value} 应解析为 {expected}"
