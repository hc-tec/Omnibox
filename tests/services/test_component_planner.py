"""
组件规划器测试

测试各种边界情况和配置选项，确保组件选择逻辑正确。
"""
from services.panel.component_planner import (
    ComponentPlannerConfig,
    plan_components_for_route,
)


def test_plan_components_for_route_defaults_to_required_and_optional():
    """测试默认配置：选择必需组件和默认可选组件"""
    components = plan_components_for_route("/github/trending/daily")
    assert components is not None
    assert components == ["ListPanel", "LineChart"]


def test_plan_respects_max_components_and_preferences():
    """测试最大组件数限制和偏好组件配置"""
    config = ComponentPlannerConfig(max_components=1, preferred_components=["LineChart"])
    components = plan_components_for_route("/github/trending/daily", config=config)
    # 由于 ListPanel 是必需组件（不计入 max_components），应该被选中
    assert components == ["ListPanel"]

    config2 = ComponentPlannerConfig(max_components=1, preferred_components=["LineChart"], allow_optional=False)
    components2 = plan_components_for_route("/github/trending/daily", config=config2)
    assert components2 == ["ListPanel"]

    config3 = ComponentPlannerConfig(max_components=3, preferred_components=["LineChart"])
    components3 = plan_components_for_route("/github/trending/daily", config=config3)
    assert components3 == ["ListPanel", "LineChart"]


def test_plan_returns_none_when_manifest_missing():
    """测试无 manifest 时返回 None"""
    assert plan_components_for_route("/non/existing/route") is None


def test_plan_handles_allow_optional_false():
    """测试 allow_optional=False 时不选择可选组件"""
    config = ComponentPlannerConfig(max_components=0, allow_optional=False)
    components = plan_components_for_route("/github/trending/daily", config=config)

    # 应该只包含必需组件（ListPanel 是 required=True）
    assert components == ["ListPanel"]


def test_plan_handles_invalid_preferred_components():
    """测试偏好组件包含无效 ID 时能正确过滤"""
    config = ComponentPlannerConfig(
        max_components=2,
        preferred_components=["InvalidComponent", "LineChart", "AnotherInvalidComponent"]
    )
    components = plan_components_for_route("/github/trending/daily", config=config)

    # 应该选择必需组件 + 有效的偏好组件
    assert components == ["ListPanel", "LineChart"]


def test_plan_fallback_logic_when_allow_optional_true():
    """测试兜底逻辑：当 allow_optional=True 且没有可选组件被选中时选择最低成本组件"""
    # 使用 max_components=0 阻止默认选择，但必需组件仍会包含
    config = ComponentPlannerConfig(max_components=0, allow_optional=True)
    components = plan_components_for_route("/github/trending/daily", config=config)

    # ListPanel 是必需组件，总是会被包含
    assert components == ["ListPanel"]


def test_plan_fallback_logic_when_allow_optional_false():
    """测试兜底逻辑在 allow_optional=False 时不触发"""
    config = ComponentPlannerConfig(max_components=0, allow_optional=False)
    components = plan_components_for_route("/github/trending/daily", config=config)

    # 只包含必需组件（ListPanel），兜底逻辑不会触发
    assert components == ["ListPanel"]


def test_plan_respects_required_components_over_limit():
    """测试必需组件超过 max_components 限制时仍然被包含"""
    config = ComponentPlannerConfig(max_components=0)  # 设置为 0，应该只影响可选组件

    components = plan_components_for_route("/github/trending/daily", config=config)
    # 必需组件（ListPanel）不计入 max_components 限制，仍会被包含
    assert components == ["ListPanel"]
