"""
PanelGenerator：根据 DataBlock 与适配结果构建面板载荷。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from api.schemas.panel import LayoutHint, LayoutTree, PanelPayload, SourceInfo, UIBlock
from services.panel.adapters import AdapterBlockPlan
from services.panel.data_block_builder import BlockBuildResult, DataBlockBuilder
from services.panel.layout_engine import LayoutEngine


@dataclass
class PanelBlockInput:
    block_id: str
    records: Sequence[Any]
    source_info: SourceInfo
    title: Optional[str] = None
    full_data_ref: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    user_preferences: Optional[Dict[str, Any]] = None
    requested_components: Optional[Sequence[str]] = None


@dataclass
class PanelGenerationResult:
    payload: PanelPayload
    data_blocks: Dict[str, Any]
    view_descriptors: List[Any]
    component_confidence: Dict[str, float]
    debug: Dict[str, Any]


class PanelGenerator:
    def __init__(
        self,
        data_block_builder: Optional[DataBlockBuilder] = None,
        layout_engine: Optional[LayoutEngine] = None,
    ):
        self.data_block_builder = data_block_builder or DataBlockBuilder()
        self.layout_engine = layout_engine or LayoutEngine()

    def generate(
        self,
        mode: str,
        block_inputs: Sequence[PanelBlockInput],
        history_token: Optional[str] = None,
    ) -> PanelGenerationResult:
        data_blocks: Dict[str, Any] = {}
        ui_blocks: List[UIBlock] = []
        component_confidence: Dict[str, float] = {}
        debug_info: Dict[str, Any] = {"blocks": []}
        layout_hints: Dict[str, LayoutHint] = {}

        for block_index, block_input in enumerate(block_inputs, start=1):
            result = self._build_data_block(block_input)
            data_block = result.data_block
            data_blocks[data_block.id] = data_block

            plans = list(result.block_plans)
            if not plans:
                if block_input.requested_components:
                    debug_info["blocks"].append(
                        {
                            "data_block_id": data_block.id,
                            "planned_components": [],
                            "skipped": True,
                        }
                    )
                    continue
                plans = [self._build_fallback_plan(block_input, data_block)]
            for plan_index, plan in enumerate(plans, start=1):
                block_id = f"block-{block_index}-{plan_index}"
                ui_block = self._plan_to_ui_block(block_id, data_block, plan)
                ui_blocks.append(ui_block)
                component_confidence[block_id] = plan.confidence
                if plan.layout_hint:
                    layout_hints[ui_block.id] = plan.layout_hint

            debug_info["blocks"].append(
                {
                    "data_block_id": data_block.id,
                    "planned_components": [plan.component_id for plan in plans],
                }
            )

        layout: LayoutTree = self.layout_engine.build(
            mode=mode,
            blocks=ui_blocks,
            layout_hints=layout_hints,
            history_token=history_token,
        )

        payload = PanelPayload(mode=mode, layout=layout, blocks=ui_blocks)

        return PanelGenerationResult(
            payload=payload,
            data_blocks=data_blocks,
            view_descriptors=[],
            component_confidence=component_confidence,
            debug=debug_info,
        )

    def _build_data_block(self, block_input: PanelBlockInput) -> BlockBuildResult:
        return self.data_block_builder.build(
            block_id=block_input.block_id,
            records=block_input.records,
            source_info=block_input.source_info,
            full_data_ref=block_input.full_data_ref,
            stats=block_input.stats,
            requested_components=block_input.requested_components,
        )

    def _plan_to_ui_block(
        self,
        block_id: str,
        data_block: Any,
        plan: AdapterBlockPlan,
    ) -> UIBlock:
        options = dict(plan.options)
        if plan.layout_hint and plan.layout_hint.span is not None:
            options.setdefault("span", plan.layout_hint.span)

        return UIBlock(
            id=block_id,
            component=plan.component_id,
            data_ref=data_block.id,
            data={
                "items": data_block.records,
                "schema": data_block.schema_summary.model_dump(),
                "stats": data_block.stats,
            },
            props=plan.props,
            options=options,
            interactions=plan.interactions,
            confidence=plan.confidence,
            title=plan.title,
        )

    def _build_fallback_plan(self, block_input: PanelBlockInput, data_block: Any) -> AdapterBlockPlan:
        title_field = "title"
        if data_block.records:
            first_record = data_block.records[0]
            title_field = next(iter(first_record.keys()), "title")

        return AdapterBlockPlan(
            component_id="FallbackRichText",
            props={"title_field": title_field},
            options={"span": 12},
            interactions=[],
            title=block_input.title or data_block.source_info.route,
            layout_hint=LayoutHint(span=12, min_height=220),
            confidence=0.4,
        )
