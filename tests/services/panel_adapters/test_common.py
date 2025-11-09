"""
测试 panel adapters 的通用功能

包括：装饰器、注册表、契约验证、manifest、向后兼容性等
"""

import pytest

import services.panel.adapters as adapters
from api.schemas.panel import SourceInfo
from services.panel.view_models import ContractViolation, validate_records


def test_route_adapter_decorator_registers_prefix():
    """测试路由适配器装饰器能够注册前缀匹配"""

    @adapters.route_adapter("/demo/prefix")
    def _demo_adapter(source_info, records):
        return adapters.RouteAdapterResult(records=[], block_plans=[])

    adapter = adapters.get_route_adapter("/demo/prefix/resource")
    assert adapter is _demo_adapter


def test_contract_violation_raises():
    """测试缺少必填字段时抛出契约违反异常"""
    with pytest.raises(ContractViolation):
        validate_records("ListPanel", [{"id": "abc"}])  # 缺少 title 字段


def test_statistic_card_contract():
    """测试统计卡片组件契约"""
    record = {
        "id": "metric-total",
        "metric_title": "新增关注",
        "metric_value": 1024.0,
        "metric_trend": "up",
        "metric_delta_text": "+12.5% 环比",
    }
    validated = validate_records("StatisticCard", [record])
    assert validated[0]["metric_title"] == "新增关注"
    assert validated[0]["metric_trend"] == "up"

    # 测试缺少必填字段
    with pytest.raises(ContractViolation):
        validate_records("StatisticCard", [{"id": "broken", "metric_value": 100}])  # 缺少 metric_title


def test_bar_chart_contract():
    """测试柱状图组件契约"""
    record = {
        "id": "python-stars",
        "x": "Python",
        "y": 1234.0,
        "series": "Languages",
        "color": "#3776ab",
        "tooltip": "Python: 1,234 stars",
    }
    validated = validate_records("BarChart", [record])
    assert validated[0]["x"] == "Python"
    assert validated[0]["y"] == 1234.0
    assert validated[0]["color"] == "#3776ab"

    # 测试缺少必填字段
    with pytest.raises(ContractViolation):
        validate_records("BarChart", [{"id": "broken", "y": 100}])  # 缺少 x 字段


def test_pie_chart_contract():
    """测试饼图组件契约"""
    record = {
        "id": "python-projects",
        "name": "Python",
        "value": 1234.0,
        "color": "#3776ab",
        "tooltip": "Python: 1,234 projects (34.5%)",
    }
    validated = validate_records("PieChart", [record])
    assert validated[0]["name"] == "Python"
    assert validated[0]["value"] == 1234.0
    assert validated[0]["color"] == "#3776ab"
    assert validated[0]["tooltip"] == "Python: 1,234 projects (34.5%)"

    # 测试最小必填字段
    minimal_record = {
        "id": "js-projects",
        "name": "JavaScript",
        "value": 2100.0,
    }
    validated_minimal = validate_records("PieChart", [minimal_record])
    assert validated_minimal[0]["name"] == "JavaScript"
    assert validated_minimal[0]["value"] == 2100.0
    assert validated_minimal[0].get("color") is None
    assert validated_minimal[0].get("tooltip") is None

    # 测试缺少必填字段
    with pytest.raises(ContractViolation):
        validate_records("PieChart", [{"id": "broken", "value": 100}])  # 缺少 name 字段

    with pytest.raises(ContractViolation):
        validate_records("PieChart", [{"id": "broken", "name": "Test"}])  # 缺少 value 字段


def test_table_contract():
    """测试表格组件契约"""
    # 正确的 TableViewModel 数据
    table_data = {
        "columns": [
            {
                "key": "name",
                "label": "项目名称",
                "type": "text",
                "sortable": True,
                "align": "left",
                "width": 0.4,
            },
            {
                "key": "stars",
                "label": "Stars",
                "type": "number",
                "sortable": True,
                "align": "right",
                "width": 0.2,
            },
            {
                "key": "language",
                "label": "语言",
                "type": "tag",
                "sortable": False,
                "align": "center",
                "width": 0.2,
            },
        ],
        "rows": [
            {
                "id": "row-1",
                "name": "vue",
                "stars": 45000,
                "language": "TypeScript",
            },
            {
                "id": "row-2",
                "name": "react",
                "stars": 220000,
                "language": "JavaScript",
            },
        ],
    }

    # Table 组件接受单个对象，不是列表
    validated = validate_records("Table", [table_data])
    assert validated[0]["columns"][0]["key"] == "name"
    assert validated[0]["columns"][1]["type"] == "number"
    assert len(validated[0]["rows"]) == 2
    assert validated[0]["rows"][0]["name"] == "vue"
    assert validated[0]["rows"][1]["stars"] == 220000

    # 测试空表格（0行，但有列定义）
    empty_table_data = {
        "columns": [
            {"key": "id", "label": "ID", "type": "text"},
            {"key": "value", "label": "Value", "type": "number"},
        ],
        "rows": [],
    }
    validated_empty = validate_records("Table", [empty_table_data])
    assert len(validated_empty[0]["columns"]) == 2
    assert len(validated_empty[0]["rows"]) == 0


def test_manifest_lists_available_components():
    """测试 manifest 列出可用组件"""
    manifest = adapters.get_route_manifest("/github/trending/weekly")
    assert manifest is not None

    component_ids = {entry.component_id for entry in manifest.components}
    assert component_ids == {"ListPanel", "LineChart"}

    line_chart_entry = next(entry for entry in manifest.components if entry.component_id == "LineChart")
    assert line_chart_entry.default_selected is False
    assert line_chart_entry.cost == "medium"


def test_backwards_compat_adapter_without_context_param():
    """测试向后兼容：不接受 context 参数的旧 adapter 也能正常工作"""
    from services.panel.adapters.registry import route_adapter, RouteAdapterResult

    # 创建一个旧风格的 adapter（只有2个参数）
    @route_adapter("/test/old-style")
    def old_style_adapter(source_info, records):
        return RouteAdapterResult(
            records=[{"id": "test", "value": "old-style"}], block_plans=[], stats={"route": source_info.route}
        )

    adapter = adapters.get_route_adapter("/test/old-style")
    source_info = SourceInfo(
        datasource="test",
        route="/test/old-style",
        params={},
        fetched_at=None,
        request_id=None,
    )

    # 即使传入 context，旧 adapter 也应该正常工作
    result = adapter(source_info, [{"sample": "data"}], context=None)
    assert result.records[0]["value"] == "old-style"


def test_default_adapter_warning():
    """测试默认适配器会返回警告信息"""
    adapter = adapters.get_route_adapter("/nonexistent/route")
    source_info = SourceInfo(
        datasource="test",
        route="/nonexistent/route",
        params={},
        fetched_at=None,
        request_id=None,
    )

    result = adapter(source_info, [{"title": "test"}])

    # 验证返回了警告信息
    assert result.stats.get("using_default_adapter") is True
    assert "warning" in result.stats
    assert "/nonexistent/route" in result.stats["warning"]
    assert result.block_plans == []
