from services.panel.component_planner import (
    ComponentPlannerConfig,
    PlannerContext,
    plan_components_for_route,
)


def test_planner_returns_decision_with_reasons():
    """测试规划器返回包含理由的决策对象"""
    decision = plan_components_for_route("/github/trending/daily")
    assert decision is not None
    assert decision.components == ["ListPanel", "LineChart"]
    assert decision.reasons  # reasons should not be empty


def test_planner_respects_max_components():
    """测试规划器遵守 max_components 限制"""
    config = ComponentPlannerConfig(max_components=1)
    decision = plan_components_for_route("/github/trending/daily", config=config)
    assert decision is not None
    assert decision.components == ["ListPanel"]


def test_line_chart_requires_min_items():
    """测试 LineChart 需要最小数据项数（通过 hints 机制）"""
    context = PlannerContext(item_count=2)
    decision = plan_components_for_route("/github/trending/daily", context=context)
    assert decision is not None
    assert decision.components == ["ListPanel"]
    assert any("Skip LineChart" in reason for reason in decision.reasons)


def test_user_query_preference_promotes_chart():
    """测试用户查询中的关键词能提升组件优先级"""
    context = PlannerContext(item_count=5, raw_query="请展示趋势图")
    decision = plan_components_for_route("/github/trending/daily", context=context)
    assert decision is not None
    assert "LineChart" in decision.components


def test_missing_manifest_returns_none():
    """测试缺失 manifest 时返回 None"""
    assert plan_components_for_route("/unknown/route") is None


def test_required_components_always_present():
    """测试必选组件在任何配置下都会被包含"""
    config = ComponentPlannerConfig(max_components=0, allow_optional=False)
    decision = plan_components_for_route("/github/trending/daily", config=config)
    assert decision is not None
    assert "ListPanel" in decision.components


def test_fallback_logic_respects_allow_optional():
    """测试兜底逻辑在 allow_optional=False 时不触发"""
    # 使用 max_components=0 且 allow_optional=False
    # 应该只包含必选组件，不触发兜底逻辑
    config = ComponentPlannerConfig(max_components=0, allow_optional=False)
    decision = plan_components_for_route("/github/trending/daily", config=config)
    assert decision is not None
    # 只包含必选组件（ListPanel）
    assert decision.components == ["ListPanel"]


def test_user_preferences_skip_filtering():
    """测试用户偏好组件跳过 _should_include 过滤"""
    # 用户明确指定 LineChart，即使 item_count < 3 也应该包含
    context = PlannerContext(item_count=2, user_preferences=["chart"])
    decision = plan_components_for_route("/github/trending/daily", context=context)
    assert decision is not None
    # 应该包含 ListPanel（必选）+ LineChart（用户偏好，跳过过滤）
    assert "ListPanel" in decision.components
    assert "LineChart" in decision.components


def test_required_components_over_max_limit():
    """测试必选组件超过 max_components 限制时仍然被包含"""
    config = ComponentPlannerConfig(max_components=0)  # 设置为 0，应该只影响可选组件
    decision = plan_components_for_route("/github/trending/daily", config=config)
    assert decision is not None
    # 必选组件（ListPanel）不计入 max_components 限制，仍会被包含
    assert "ListPanel" in decision.components


def test_allow_optional_false_excludes_optional_components():
    """测试 allow_optional=False 时排除可选组件"""
    config = ComponentPlannerConfig(max_components=10, allow_optional=False)
    decision = plan_components_for_route("/github/trending/daily", config=config)
    assert decision is not None
    # 只包含必选组件
    assert decision.components == ["ListPanel"]
    # 不包含可选的 LineChart
    assert "LineChart" not in decision.components
