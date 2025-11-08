#!/usr/bin/env python
"""
CLI helper to inspect planner decisions for a given route + manifest context.
"""

from __future__ import annotations

import argparse
import json
import sys

from services.panel.component_planner import (
    ComponentPlannerConfig,
    PlannerContext,
    plan_components_for_route,
)
from services.panel.llm_component_planner import LLMComponentPlanner
from services.panel.adapters import get_route_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect planner decisions.")
    parser.add_argument("--route", required=True, help="RSSHub route, e.g. /github/trending/daily")
    parser.add_argument("--user-query", default="", help="User natural language query")
    parser.add_argument("--max-components", type=int, default=2, help="Planner max components")
    parser.add_argument("--llm", action="store_true", help="Use LLM planner when available")
    parser.add_argument("--layout", default=None, help="Layout mode hint")
    parser.add_argument("--preferred", nargs="*", default=[], help="Preferred component IDs")
    parser.add_argument("--item-count", type=int, help="Override item count for planner context")
    args = parser.parse_args()

    manifest = get_route_manifest(args.route)
    if manifest is None:
        print(f"[error] manifest not found for route: {args.route}", file=sys.stderr)
        sys.exit(1)

    context = PlannerContext(
        item_count=args.item_count,
        user_preferences=args.preferred,
        raw_query=args.user_query,
        layout_mode=args.layout,
    )
    config = ComponentPlannerConfig(
        max_components=args.max_components,
        preferred_components=args.preferred,
        allow_optional=True,
    )

    decision = None
    planner_engine = "rule"
    if args.llm:
        llm_planner = LLMComponentPlanner()
        if llm_planner.is_available():
            decision = llm_planner.plan(
                route=args.route,
                manifest=manifest,
                context=context,
                config=config,
            )
            if decision:
                planner_engine = "llm"

    if decision is None:
        decision = plan_components_for_route(
            args.route,
            config=config,
            context=context,
            manifest=manifest,
        )

    output = {
        "route": args.route,
        "engine": planner_engine if decision else "rule",
        "context": {
            "item_count": context.item_count,
            "layout_mode": context.layout_mode,
            "user_query": context.raw_query,
            "user_preferences": list(context.user_preferences),
        },
        "manifest_components": [entry.component_id for entry in manifest.components],
        "decision": decision.__dict__ if decision else None,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
