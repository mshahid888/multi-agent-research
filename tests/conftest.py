import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.datasources import DemoDataSource
from src.llm import TemplateBackend
from src.memory import AgentMemory

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "demo_companies.json"


@pytest.fixture
def demo_source():
    return DemoDataSource(DATA_PATH, "nordwind")


@pytest.fixture
def findings(demo_source):
    return [f.to_dict() for f in demo_source.fetch("Nordwind Logistics GmbH")]


@pytest.fixture
def llm():
    return TemplateBackend()


@pytest.fixture
def memory():
    return AgentMemory("test-run")
