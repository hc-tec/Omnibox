import pytest
from api.schemas.panel import DataBlock, SchemaSummary, SchemaFieldSummary, SourceInfo
from services.panel.envelope_builder import build_envelope_from_data_block
from services.panel.schema_encoder import build_display_schema_from_data_block
from services.panel.view_model_builder import ViewModelBuilder
from services.panel.panel_spec import PanelDSL, PanelNode, DataBinding, TransformationSpec
from services.panel.dsl_renderer import PanelDSLRenderer
from services.panel.sandbox_executor import SandboxExecutor, SandboxExecutionError


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
