"""测试 JSON 解析工具"""
import pytest
import json
from langgraph_agents.json_utils import parse_json_payload


class TestParseJsonPayload:
    """测试 parse_json_payload 函数"""

    def test_parse_valid_json(self):
        """测试解析有效的 JSON"""
        text = '{"plugin_id": "test", "args": {}}'
        result = parse_json_payload(text)
        assert result == {"plugin_id": "test", "args": {}}

    def test_parse_json_with_whitespace(self):
        """测试解析带空白字符的 JSON"""
        text = '  \n{"plugin_id": "test"}\n  '
        result = parse_json_payload(text)
        assert result == {"plugin_id": "test"}

    def test_parse_json_with_extra_text_before(self):
        """测试解析前面带额外文本的 JSON"""
        text = 'Here is the result: {"plugin_id": "test", "value": 123}'
        result = parse_json_payload(text)
        assert result["plugin_id"] == "test"
        assert result["value"] == 123

    def test_parse_json_with_extra_text_after(self):
        """测试解析后面带额外文本的 JSON"""
        text = '{"plugin_id": "test"} and some more text'
        result = parse_json_payload(text)
        assert result["plugin_id"] == "test"

    def test_parse_invalid_json_raises_error(self):
        """测试解析无效 JSON 抛出异常"""
        text = "not a json at all"
        with pytest.raises(json.JSONDecodeError):
            parse_json_payload(text)

    def test_parse_nested_json(self):
        """测试解析嵌套 JSON"""
        text = '{"outer": {"inner": "value"}, "array": [1, 2, 3]}'
        result = parse_json_payload(text)
        assert result["outer"]["inner"] == "value"
        assert result["array"] == [1, 2, 3]
