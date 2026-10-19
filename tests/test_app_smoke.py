"""
Smoke test for the Streamlit app (box Q1) using Streamlit's AppTest, with the real
agent replaced by the fake one from test_agent_flow.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")

import graphrag.agent.builder as builder  # noqa: E402
from tests.test_agent_flow import make_agent  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def fake_agent(monkeypatch):
    monkeypatch.setattr(builder, "build_agent", lambda settings=None: make_agent())


@pytest.mark.parametrize("mode", ["GraphRAG", "Vector-only", "Compare both"])
def test_app_answers_a_question_in_every_mode(fake_agent, mode):
    at = st_testing.AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    at.sidebar.radio[0].set_value(mode).run()
    at.chat_input[0].set_value("What tools has Sarah used?").run()
    assert not at.exception
    assert any("Project Triton" in m.value for m in at.markdown)
    assert len(at.success) == (2 if mode == "Compare both" else 1)
