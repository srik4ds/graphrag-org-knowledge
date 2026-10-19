"""
Shared pytest fixtures. All tests run offline: no Neo4j, no Nebius.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graphrag.config import get_settings  # noqa: E402
from graphrag.ingest.pipeline import prepare  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def prepared(settings):
    """Run the offline half of ingestion once for the whole test session."""
    return prepare(settings)


@pytest.fixture(scope="session")
def registry(prepared):
    return prepared.registry
