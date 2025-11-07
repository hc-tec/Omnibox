from services.panel.component_planner import (
    ComponentPlannerConfig,
    PlannerContext,
    plan_components_for_route,
)


def test_plan_defaults_include_required_and_optional():
    components = plan_components_for_route("/github/trending/daily")
    assert components == ["ListPanel", "LineChart"]


def test_plan_respects_max_components_and_preferences():
    config = ComponentPlannerConfig(max_components=1, preferred_components=["LineChart"])
    components = plan_components_for_route("/github/trending/daily", config=config)
    assert components == ["ListPanel"]

    config_allow_optional = ComponentPlannerConfig(max_components=3, preferred_components=["LineChart"])
    components_allow_optional = plan_components_for_route("/github/trending/daily", config=config_allow_optional)
    assert components_allow_optional == ["ListPanel", "LineChart"]


def test_plan_returns_none_when_manifest_missing():
    assert plan_components_for_route("/non/exist/route") is None


def test_required_components_always_present():
    config = ComponentPlannerConfig(max_components=0, allow_optional=False)
    components = plan_components_for_route("/github/trending/daily", config=config)
    assert components == ["ListPanel"]


def test_line_chart_filtered_when_item_count_low():
    context = PlannerContext(item_count=2)
    components = plan_components_for_route("/github/trending/daily", context=context)
    assert components == ["ListPanel"]


def test_metrics_hint_requires_available_metrics():
    """测试依赖指标的组件需要 available_metrics"""
    # Without metrics, optional metric-based components should be skipped (currently followings only required ListPanel)
    context_no_metrics = PlannerContext(item_count=5, available_metrics=set())
    components_no_metrics = plan_components_for_route(
        "/bilibili/user/followings/2267573/3",
        context=context_no_metrics,
    )
    assert components_no_metrics == ["ListPanel"]

    context_with_metrics = PlannerContext(item_count=5, available_metrics={"count"})
    components_with_metrics = plan_components_for_route(
        "/bilibili/user/followings/2267573/3",
        context=context_with_metrics,
    )
    assert components_with_metrics == ["ListPanel"]


def test_plan_handles_invalid_preferred_components():
    """测试偏好组件包含无效 ID 时能正确过滤"""
    config = ComponentPlannerConfig(
        max_components=2,
        preferred_components=["InvalidComponent", "LineChart", "AnotherInvalidComponent"]
    )
    components = plan_components_for_route("/github/trending/daily", config=config)

    # 应该选择必需组件 + 有效的偏好组件
    assert components == ["ListPanel", "LineChart"]


def test_fallback_logic_respects_allow_optional():
    """测试兜底逻辑在 allow_optional=False 时不触发"""
    # 使用一个没有默认选中组件的路由（假设的场景）
    # 这里用 github 测试，设置 max_components=0 且 allow_optional=False
    config = ComponentPlannerConfig(max_components=0, allow_optional=False)
    components = plan_components_for_route("/github/trending/daily", config=config)

    # 只包含必需组件（ListPanel），兜底逻辑不会触发
    assert components == ["ListPanel"]


def test_user_preferences_skip_filtering():
    """测试用户偏好组件跳过 _should_include 过滤"""
    # 用户明确指定 LineChart，即使 item_count < 3 也应该包含
    context = PlannerContext(item_count=2, user_preferences=["LineChart"])
    components = plan_components_for_route("/github/trending/daily", context=context)

    # 应该包含 ListPanel（必选）+ LineChart（用户偏好，跳过过滤）
    assert "ListPanel" in components
    assert "LineChart" in components


def test_config_preferences_apply_filtering():
    """测试配置偏好组件应用 _should_include 过滤"""
    # 配置偏好 LineChart，但 item_count < 3 会被过滤
    config = ComponentPlannerConfig(max_components=2, preferred_components=["LineChart"])
    context = PlannerContext(item_count=2)
    components = plan_components_for_route("/github/trending/daily", config=config, context=context)

    # LineChart 因为 item_count < 3 被过滤，只包含 ListPanel
    assert components == ["ListPanel"]


def test_required_components_over_max_limit():
    """测试必选组件超过 max_components 限制时仍然被包含"""
    config = ComponentPlannerConfig(max_components=0)  # 设置为 0，应该只影响可选组件

    components = plan_components_for_route("/github/trending/daily", config=config)
    # 必选组件（ListPanel）不计入 max_components 限制，仍会被包含
    assert components == ["ListPanel"]
