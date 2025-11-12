import threading

from services.research_task_hub import ResearchTaskHub


def test_task_hub_publish_and_listen():
    hub = ResearchTaskHub()
    context = hub.ensure_task("task-1", "thread-1", "base query", None)
    assert context.task_id == "task-1"

    queue = hub.register_listener("task-1")
    hub.publish_event("task-1", {"type": "step", "data": {"node": "router"}})

    event = queue.get()
    assert event["type"] == "step"
    assert event["data"]["node"] == "router"


def test_task_hub_cancel_and_has_task():
    hub = ResearchTaskHub()
    hub.ensure_task("task-2", "thread-2", "query", None)
    queue = hub.register_listener("task-2")

    assert hub.has_task("task-2") is True

    hub.cancel_task("task-2", reason="test")
    cancel_event = queue.get()
    assert cancel_event["type"] == "cancelled"
    assert cancel_event["data"]["reason"] == "test"

    assert hub.is_cancelled("task-2") is True


def test_task_hub_store_last_state():
    hub = ResearchTaskHub()
    hub.ensure_task("task-3", "thread-3", "query", "github")
    hub.set_last_state("task-3", {"final_report": "ok"})
    context = hub.get_task("task-3")
    assert context and context.last_state == {"final_report": "ok"}
