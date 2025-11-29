import pytest
from api.schemas.panel import (
    DataBlock,
    SchemaSummary,
    SchemaFieldSummary,
    SourceInfo,
    LayoutTree,
    LayoutNode,
    PanelPayload,
)
from services.panel.envelope_builder import build_envelope_from_data_block
from services.panel.schema_encoder import build_display_schema_from_data_block
from services.panel.view_model_builder import ViewModelBuilder
from services.panel.panel_spec import PanelDSL, PanelNode, DataBinding, TransformationSpec
from services.panel.dsl_renderer import PanelDSLRenderer
from services.panel.sandbox_executor import SandboxExecutor, SandboxExecutionError
from services.panel.dsl_runtime import PanelDSLParser, PanelDSLValidationError
from services.panel.runtime import PanelRuntime
from services.panel.component_whitelist import build_component_whitelist
from services.panel.panel_generator import PanelGenerationResult
from services.panel.panel_spec_serializer import build_panel_spec_metadata


def _make_data_block() -> DataBlock:
    source_info = SourceInfo(
        datasource="test",
        route="/test/demo",
        params={},
        fetched_at=None,
        request_id=None,
    )
    schema_summary = SchemaSummary(
        fields=[
            SchemaFieldSummary(
                name="title",
                type="string",
                sample=["foo"],
                stats=None,
            ),
            SchemaFieldSummary(
                name="value",
                type="number",
                sample=[1],
                stats=None,
            ),
        ],
        stats={},
        schema_digest="title/value",
    )
    return DataBlock(
        id="block-1",
        source_info=source_info,
        records=[{"title": "foo", "value": 1}, {"title": "bar", "value": 2}],
        stats={"total": 2},
        schema_summary=schema_summary,
        full_data_ref=None,
    )


def test_sandbox_inline_python_allows_safe_expr():
    executor = SandboxExecutor()
    records = [{"value": 1}, {"value": 2}]
    spec = TransformationSpec(type="inline_python", code="[{'value': r['value'] * 2} for r in records]")
    result = executor.execute(records, spec)
    assert result == [{"value": 2}, {"value": 4}]


def test_sandbox_inline_python_disallows_builtin():
    executor = SandboxExecutor()
    records = [{"value": 1}]
    spec = TransformationSpec(type="inline_python", code="__import__('os').system('echo hello')")
    with pytest.raises(SandboxExecutionError):
        executor.execute(records, spec)


def test_sandbox_builtin_sort_slice_and_group():
    executor = SandboxExecutor()
    records = [
        {"value": 3, "category": "a"},
        {"value": 1, "category": "b"},
        {"value": 2, "category": "a"},
        {"value": 2, "category": "c"},
    ]

    sort_spec = TransformationSpec(type="builtin", code="sort_by", params={"field": "value", "order": "desc"})
    sorted_records = executor.execute(records, sort_spec)
    assert [item["value"] for item in sorted_records] == [3, 2, 2, 1]

    slice_spec = TransformationSpec(type="builtin", code="slice", params={"start": 1, "stop": 3})
    sliced_records = executor.execute(records, slice_spec)
    assert len(sliced_records) == 2
    assert sliced_records[0]["value"] == 1

    group_spec = TransformationSpec(
        type="builtin",
        code="group_count",
        params={"field": "category", "limit": 2},
    )
    grouped = executor.execute(records, group_spec)
    assert grouped[0]["category"] == "a"
    assert grouped[0]["count"] == 2
    rename_spec = TransformationSpec(
        type="builtin",
        code="rename_fields",
        params={"mapping": {"category": "platform"}},
    )
    renamed = executor.execute(records, rename_spec)
    assert "platform" in renamed[0] and "category" not in renamed[0]
    aggregate_spec = TransformationSpec(
        type="builtin",
        code="aggregate_numeric",
        params={"field": "value"},
    )
    aggregated = executor.execute(records, aggregate_spec)
    assert aggregated[0]["count"] == 4
    assert aggregated[0]["max"] == 3
    coerce_spec = TransformationSpec(
        type="builtin",
        code="coerce_number",
        params={"field": "value", "target_field": "value_num"},
    )
    coerced = executor.execute([{"value": "42.5"}], coerce_spec)
    assert coerced[0]["value_num"] == 42.5
    pipeline_spec = TransformationSpec(
        type="pipeline",
        code=None,
        params={
            "steps": [
                {
                    "code": "rename_fields",
                    "params": {"mapping": {"category": "platform"}},
                },
                {
                    "code": "group_count",
                    "params": {"field": "platform"},
                },
            ]
        },
    )
    pipeline_result = executor.execute(records, pipeline_spec)
    assert pipeline_result[0]["platform"] == "a"
    assert pipeline_result[0]["count"] == 2


def test_renderer_uses_view_model_data_binding():
    block = _make_data_block()
    envelope = build_envelope_from_data_block(block)
    builder = ViewModelBuilder()
    display_schema = build_display_schema_from_data_block(block)
    vm = builder.build(display_schema)

    dsl = PanelDSL(
        layout=[
            PanelNode(
                node=vm.component_id,
                props={"title": display_schema.title},
                data_binding=DataBinding(view_model_id=vm.view_model_id),
                events={},
                children=[],
            )
        ]
    )

    renderer = PanelDSLRenderer(SandboxExecutor())
    blocks = renderer.render(dsl, {envelope.data_id: envelope}, {vm.view_model_id: vm})
    assert blocks[0].data == vm.data


def test_renderer_handles_nested_children():
    block = _make_data_block()
    envelope = build_envelope_from_data_block(block)
    builder = ViewModelBuilder()
    display_schema = build_display_schema_from_data_block(block)
    vm = builder.build(display_schema)

    child_node = PanelNode(
        node=vm.component_id,
        props={"title": "child"},
        data_binding=DataBinding(view_model_id=vm.view_model_id),
        events={},
        children=[],
    )
    parent = PanelNode(
        node="TabGroup",
        props={"id": "tabs-1"},
        data_binding=None,
        events={},
        children=[child_node],
    )
    dsl = PanelDSL(layout=[parent])

    renderer = PanelDSLRenderer(SandboxExecutor())
    blocks = renderer.render(dsl, {envelope.data_id: envelope}, {vm.view_model_id: vm})
    assert blocks[0].children is not None
    assert blocks[0].children[0].data == vm.data


def test_panel_runtime_renders_from_model_instance():
    block = _make_data_block()
    envelope = build_envelope_from_data_block(block)
    builder = ViewModelBuilder()
    display_schema = build_display_schema_from_data_block(block)
    vm = builder.build(display_schema)

    dsl = PanelDSL(
        layout=[
            PanelNode(
                node=vm.component_id,
                props={"title": "runtime"},
                data_binding=DataBinding(view_model_id=vm.view_model_id),
                events={},
                children=[],
            )
        ]
    )

    runtime = PanelRuntime()
    blocks = runtime.render_dsl(dsl, {envelope.data_id: envelope}, {vm.view_model_id: vm})
    assert blocks[0].data == vm.data


def test_dsl_parser_respects_allowed_components():
    payload = {
        "layout": [
            {
                "node": "ListPanel",
                "props": {"title": "allowed"},
                "children": [],
                "events": {},
            }
        ]
    }
    parser = PanelDSLParser(allowed_components={"ListPanel"})
    parsed = parser.parse(payload)
    assert parsed.layout[0].node == "ListPanel"

    parser = PanelDSLParser(allowed_components={"StatisticCard"})
    with pytest.raises(PanelDSLValidationError):
        parser.parse(payload)


def test_renderer_degrades_when_envelope_missing():
    dsl = PanelDSL(
        layout=[
            PanelNode(
                node="ListPanel",
                props={"title": "missing-data"},
                data_binding=DataBinding(data_id="non-exist"),
                events={},
                children=[],
            )
        ]
    )
    renderer = PanelDSLRenderer(SandboxExecutor())
    blocks = renderer.render(dsl, envelopes={}, view_models={})
    assert blocks[0].component == "FallbackRichText"
    assert blocks[0].options.get("degraded") is True
    assert blocks[0].props.get("original_component") == "ListPanel"


def test_renderer_degrades_when_view_model_missing():
    dsl = PanelDSL(
        layout=[
            PanelNode(
                node="StatisticCard",
                props={"title": "vm-missing"},
                data_binding=DataBinding(view_model_id="vm-404"),
                events={},
                children=[],
            )
        ]
    )
    renderer = PanelDSLRenderer(SandboxExecutor())
    blocks = renderer.render(dsl, envelopes={}, view_models={})
    assert blocks[0].component == "FallbackRichText"
    assert blocks[0].options.get("original_component") == "StatisticCard"


def test_panel_runtime_enforces_whitelist_by_default():
    runtime = PanelRuntime()
    dsl = PanelDSL(
        layout=[
            PanelNode(
                node="UnknownWidget",
                props={},
                data_binding=None,
                events={},
                children=[],
            )
        ]
    )
    with pytest.raises(PanelDSLValidationError):
        runtime.render_dsl(dsl, envelopes={}, view_models={})


def test_panel_runtime_can_disable_whitelist():
    runtime = PanelRuntime(enforce_component_whitelist=False)
    dsl = PanelDSL(
        layout=[
            PanelNode(
                node="UnknownWidget",
                props={"title": "custom"},
                data_binding=None,
                events={},
                children=[],
            )
        ]
    )
    blocks = runtime.render_dsl(dsl, envelopes={}, view_models={})
    assert blocks[0].component == "UnknownWidget"


def test_whitelist_reads_frontend_manifest(tmp_path):
    manifest = tmp_path / "componentManifest.ts"
    manifest.write_text(
        """
        export const componentManifest = {
          components: [
            { id: "FooCard", props: {} },
            { id: "BarMetric", props: {} }
          ]
        };
        """,
        encoding="utf8",
    )

    whitelist = build_component_whitelist(manifest_path=manifest)
    assert "FooCard" in whitelist
    assert "BarMetric" in whitelist


def test_panel_spec_metadata_reports_degraded_blocks():
    panel_dsl = PanelDSL(
        layout=[
            PanelNode(
                node="ListPanel",
                props={"title": "broken"},
                data_binding=DataBinding(data_id="missing"),
                events={},
                children=[],
            )
        ]
    )
    layout = LayoutTree(
        mode="replace",
        nodes=[
            LayoutNode(type="row", id="root", children=[], props={}),
        ],
    )
    payload = PanelPayload(mode="replace", layout=layout, blocks=[])
    result = PanelGenerationResult(
        payload=payload,
        data_blocks={},
        data_envelopes={},
        display_schemas={},
        view_models={},
        panel_dsl=panel_dsl,
        view_descriptors=[],
        component_confidence={},
        debug={},
    )
    metadata = build_panel_spec_metadata(result)
    degraded = metadata["degraded_components"]
    assert degraded
    assert degraded[0]["original_component"] == "ListPanel"
