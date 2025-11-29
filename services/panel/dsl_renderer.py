"""
Render PanelDSL nodes into UIBlock structures.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from uuid import uuid4

from api.schemas.panel import ComponentInteraction, UIBlock
from services.panel.panel_spec import PanelDSL, PanelNode, StructuredDataEnvelope
from services.panel.sandbox_executor import SandboxExecutor, SandboxExecutionError
from services.panel.view_model_builder import GeneratedViewModel


class PanelDSLRenderer:
    """将 PanelDSL 转换为 UIBlock 列表的轻量渲染器。"""

    def __init__(self, sandbox_executor: Optional[SandboxExecutor] = None):
        self.sandbox = sandbox_executor or SandboxExecutor()

    def render(
        self,
        dsl: PanelDSL,
        envelopes: Dict[str, StructuredDataEnvelope],
        view_models: Optional[Dict[str, GeneratedViewModel]] = None,
    ) -> List[UIBlock]:
        """渲染 DSL 顶层节点为 UIBlock 列表。"""

        rendered: List[UIBlock] = []
        vm_registry = view_models or {}
        for node in dsl.layout:
            rendered.append(self._render_node(node, envelopes, vm_registry))
        return rendered

    def _render_node(
        self,
        node: PanelNode,
        envelopes: Dict[str, StructuredDataEnvelope],
        view_models: Dict[str, GeneratedViewModel],
    ) -> UIBlock:
        block_id = node.props.get("id") or f"dsl-{uuid4().hex[:8]}"
        data_payload = None
        data_ref = None

        if node.data_binding:
            binding = node.data_binding
            if binding.view_model_id:
                vm = view_models.get(binding.view_model_id)
                if vm:
                    data_payload = vm.data
                    data_ref = vm.view_model_id
            elif binding.data_id:
                envelope = envelopes.get(binding.data_id)
                if not envelope:
                    raise SandboxExecutionError(
                        f"data_id '{binding.data_id}' not found in envelopes"
                    )
                records = list(envelope.preview)
                if binding.filters:
                    records = self._apply_filters(records, binding.filters)
                records = self.sandbox.execute(records, binding.transformation)
                data_payload = {"items": records}
                data_ref = binding.data_id

        children_blocks = [
            self._render_node(child, envelopes) for child in node.children
        ] if node.children else None

        interactions = self._build_interactions(node)

        return UIBlock(
            id=block_id,
            component=node.node,
            data_ref=data_ref,
            data=data_payload,
            props=node.props,
            options={},
            interactions=interactions,
            confidence=None,
            title=node.props.get("title"),
            children=children_blocks,
        )

    @staticmethod
    def _apply_filters(records: List[Dict], filters: Dict[str, object]) -> List[Dict]:
        if not filters:
            return records
        filtered = []
        for record in records:
            matched = True
            for key, expected in filters.items():
                if record.get(key) != expected:
                    matched = False
                    break
            if matched:
                filtered.append(record)
        return filtered

    @staticmethod
    def _build_interactions(node: PanelNode) -> List[ComponentInteraction]:
        interactions: List[ComponentInteraction] = []
        for event_name, handler in node.events.items():
            interactions.append(
                ComponentInteraction(
                    type=handler.action,
                    label=event_name,
                    payload={
                        "params": handler.params,
                    },
                )
            )
        return interactions
