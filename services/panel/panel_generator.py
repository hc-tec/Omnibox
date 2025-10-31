"""
智能数据面板生成器：负责串联数据块构建、组件推荐与布局输出。
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from api.schemas.panel import (
    DataBlock,
    PanelPayload,
    UIBlock,
    ViewDescriptor,
    LayoutTree,
    LayoutHint,
    SourceInfo,
)
from services.panel.component_suggester import ComponentSuggester
from services.panel.data_block_builder import DataBlockBuilder
from services.panel.layout_engine import LayoutEngine


@dataclass
class PanelBlockInput:
    """单个数据块输入描述。"""

    block_id: str
    records: Sequence[Any]
    source_info: SourceInfo
    title: Optional[str] = None
    full_data_ref: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    user_preferences: Optional[Dict[str, Any]] = None


@dataclass
class PanelGenerationResult:
    """面板生成结果。"""

    payload: PanelPayload
    data_blocks: Dict[str, DataBlock]
    view_descriptors: List[ViewDescriptor]
    component_confidence: Dict[str, float]
    debug: Dict[str, Any]


class PanelGenerator:
    """将数据块转换为UI面板结构的入口。"""

    def __init__(
        self,
        data_block_builder: Optional[DataBlockBuilder] = None,
        component_suggester: Optional[ComponentSuggester] = None,
        layout_engine: Optional[LayoutEngine] = None,
    ):
        self.data_block_builder = data_block_builder or DataBlockBuilder()
        self.component_suggester = component_suggester or ComponentSuggester()
        self.layout_engine = layout_engine or LayoutEngine()

    def generate(
        self,
        mode: str,
        block_inputs: Sequence[PanelBlockInput],
        history_token: Optional[str] = None,
    ) -> PanelGenerationResult:
        data_blocks: Dict[str, DataBlock] = {}
        ui_blocks: List[UIBlock] = []
        view_descriptors: List[ViewDescriptor] = []
        component_confidence: Dict[str, float] = {}
        debug_info: Dict[str, Any] = {"blocks": []}
        layout_hints: Dict[str, LayoutHint] = {}

        for block_index, block_input in enumerate(block_inputs, start=1):
            data_block = self.data_block_builder.build(
                block_id=block_input.block_id,
                records=block_input.records,
                source_info=block_input.source_info,
                full_data_ref=block_input.full_data_ref,
                stats=block_input.stats,
            )
            data_blocks[data_block.id] = data_block

            descriptors = self.component_suggester.suggest(
                data_block_id=data_block.id,
                schema_fields=data_block.schema_summary.fields,
                user_preferences=block_input.user_preferences,
            )
            view_descriptors.extend(descriptors)

            for view_index, descriptor in enumerate(descriptors, start=1):
                block_id = f"block-{block_index}-{view_index}"
                ui_block = self._descriptor_to_ui_block(
                    descriptor=descriptor,
                    ui_block_id=block_id,
                    data_block=data_block,
                    title=block_input.title,
                )
                ui_blocks.append(ui_block)
                component_confidence[block_id] = descriptor.confidence
                if descriptor.layout_hint:
                    layout_hints[ui_block.id] = descriptor.layout_hint

            debug_info["blocks"].append(
                {
                    "data_block_id": data_block.id,
                    "available_semantic": {
                        field.name: field.semantic for field in data_block.schema_summary.fields
                    },
                    "descriptor_ids": [descriptor.id for descriptor in descriptors],
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
            view_descriptors=view_descriptors,
            component_confidence=component_confidence,
            debug=debug_info,
        )

    def _descriptor_to_ui_block(
        self,
        descriptor: ViewDescriptor,
        ui_block_id: str,
        data_block: DataBlock,
        title: Optional[str],
    ) -> UIBlock:
        """将ViewDescriptor转换为UIBlock实体。"""
        data_payload = {
            "items": data_block.records,
            "schema": data_block.schema_summary.model_dump(),
            "stats": data_block.stats,
        }

        options = dict(descriptor.options or {})
        if descriptor.layout_hint and descriptor.layout_hint.span is not None:
            options.setdefault("span", descriptor.layout_hint.span)

        return UIBlock(
            id=ui_block_id,
            component=descriptor.component_id,
            data_ref=data_block.id,
            data=data_payload,
            props=descriptor.props,
            options=options,
            interactions=descriptor.interactions,
            confidence=descriptor.confidence,
            title=title,
        )
