import pytest

from langgraph_agents.component_contracts import resolve_contracts_for_step, get_contract_by_id


def test_resolve_contracts_for_step_matches_step_target():
    working_memory = {
        "component_contracts": {
            "contracts": {
                "StatisticCard-contract-v2": {
                    "component_id": "StatisticCard",
                    "contract_id": "StatisticCard-contract-v2",
                    "status": "planned",
                    "targets": ["$step.3"],
                },
                "ListPanel-contract-v3": {
                    "component_id": "ListPanel",
                    "contract_id": "ListPanel-contract-v3",
                    "status": "planned",
                    "targets": ["$step.2"],
                },
            }
        }
    }

    matches = resolve_contracts_for_step(working_memory, 3)
    assert len(matches) == 1
    match = matches[0]
    assert match["contract_id"] == "StatisticCard-contract-v2"
    assert "definition" in match
    assert match["definition"]["component_id"] == "StatisticCard"


def test_resolve_contracts_for_step_handles_missing():
    working_memory = {"component_contracts": {"contracts": {}}}
    matches = resolve_contracts_for_step(working_memory, 99)
    assert matches == []

