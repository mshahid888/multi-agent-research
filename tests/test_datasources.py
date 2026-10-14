"""Data sources: demo source serves fictional data offline; unknown ids fail
loudly instead of inventing a company."""
import pytest

from src.datasources import DemoDataSource
from tests.conftest import DATA_PATH


def test_demo_source_returns_labeled_findings():
    src = DemoDataSource(DATA_PATH, "bluefin")
    assert src.company_name == "Bluefin Bakery Co."
    assert "FICTIONAL" in src.name
    findings = src.fetch("Bluefin Bakery Co.")
    assert len(findings) >= 3
    assert all(f.source == src.name for f in findings)
    assert {f.kind for f in findings} >= {"about", "signal"}


def test_unknown_demo_company_raises():
    with pytest.raises(ValueError, match="unknown demo company"):
        DemoDataSource(DATA_PATH, "acme-real-corp")
