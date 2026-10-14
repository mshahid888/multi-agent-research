"""Memory passing: researcher output must be visible to analyst/writer,
namespaces must stay isolated, and save/load must round-trip."""
from src.memory import AgentMemory


def test_researcher_findings_visible_to_analyst(memory):
    memory.write("researcher", "findings", [{"id": "f1", "text": "hello"}])
    assert memory.read("researcher", "findings") == [{"id": "f1", "text": "hello"}]


def test_namespaces_are_isolated(memory):
    memory.write("researcher", "findings", [1, 2, 3])
    memory.write("analyst", "findings", ["different"])
    assert memory.read("researcher", "findings") == [1, 2, 3]
    assert memory.read("analyst", "findings") == ["different"]


def test_read_missing_key_returns_default(memory):
    assert memory.read("writer", "draft", default="none") == "none"
    assert memory.read_all("nobody") == {}


def test_shared_blackboard(memory):
    memory.share("company", "Nordwind Logistics GmbH")
    assert memory.get_shared("company") == "Nordwind Logistics GmbH"
    assert memory.get_shared("missing", "dflt") == "dflt"


def test_events_are_logged(memory):
    memory.write("researcher", "findings", [])
    memory.log("supervisor", "route", "research -> analyze")
    actors = [e["actor"] for e in memory.events]
    assert "researcher" in actors and "supervisor" in actors


def test_save_load_roundtrip(memory, tmp_path):
    memory.write("researcher", "findings", [{"id": "f1"}])
    memory.share("company", "Bluefin Bakery Co.")
    memory.log("analyst", "analysis_complete", "ok")
    path = tmp_path / "memory.json"
    memory.save(path)

    loaded = AgentMemory.load(path)
    assert loaded.run_id == "test-run"
    assert loaded.read("researcher", "findings") == [{"id": "f1"}]
    assert loaded.get_shared("company") == "Bluefin Bakery Co."
    assert any(e["actor"] == "analyst" for e in loaded.events)
