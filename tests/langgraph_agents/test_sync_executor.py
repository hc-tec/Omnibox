from __future__ import annotations

from types import SimpleNamespace

import pytest

from langgraph_agents.sync_executor import SyncLangGraphExecutor


class DummyDataStore:
    def load(self, data_id):
        return None


class DummyApp:
    def __init__(self, final_state):
        self.final_state = final_state
        self.captured_configs = []

    def invoke(self, state, config):
        self.captured_configs.append(config)
        return self.final_state


@pytest.fixture()
def executor_with_dummy_app(monkeypatch):
    executor = object.__new__(SyncLangGraphExecutor)
    executor.llm_client = None
    executor.data_query_service = None
    executor.llm_tracker = None
    executor.runtime = SimpleNamespace(data_store=DummyDataStore())
    final_state = {
        "data_stash": [],
        "final_report": "done",
        "router_decision": None,
    }
    executor.app = DummyApp(final_state)
    yield executor, executor.app


def test_execute_generates_unique_thread_id(monkeypatch, executor_with_dummy_app):
    executor, app = executor_with_dummy_app

    ids = []
    for hex_value in ["aaa111", "bbb222"]:
        monkeypatch.setattr("langgraph_agents.sync_executor.uuid4", lambda h=hex_value: SimpleNamespace(hex=h))
        executor.execute("hello world")
        ids.append(app.captured_configs[-1]["configurable"]["thread_id"])

    assert ids[0] == "sync-aaa111"
    assert ids[1] == "sync-bbb222"
    assert ids[0] != ids[1]


def test_execute_respects_custom_thread_id(executor_with_dummy_app):
    executor, app = executor_with_dummy_app
    executor.execute("hello world", thread_id="custom-thread")
    assert app.captured_configs[-1]["configurable"]["thread_id"] == "custom-thread"
