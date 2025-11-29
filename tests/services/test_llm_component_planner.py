import types

from services.panel.llm_component_planner import LLMComponentPlanner
from services.panel.adapters.registry import RouteAdapterManifest, ComponentManifestEntry
from services.panel.component_planner import ComponentPlannerConfig, PlannerContext


def test_llm_planner_prompt_includes_pipeline_guidelines():
    manifest = RouteAdapterManifest(
        components=[
            ComponentManifestEntry(
                component_id="ListPanel",
                description="通用列表",
                required=True,
                hints={"min_items": 1},
            )
        ],
        notes="demo manifest",
    )
    context = PlannerContext(raw_query="请统计播放量并给我Top5列表", item_count=12)
    config = ComponentPlannerConfig(max_components=2)
    planner = LLMComponentPlanner(llm_client=types.SimpleNamespace(generate=lambda *args, **kwargs: "{}"))

    prompt = planner._build_prompt("/demo", manifest, context, config)

    assert "transformation_guidelines" in prompt
    assert "pipeline" in prompt
    assert "rename_fields" in prompt
    assert "aggregate_numeric" in prompt
