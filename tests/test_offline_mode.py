"""Offline provider (LLM_PROVIDER=offline): router picks the right template for every eval question."""
import json

from graphrag.agent.prompts import ROUTER_PROMPT
from graphrag.offline import HashingEmbeddings, OfflineLLM

EXPECTED = {"Q01": "project_people_next_projects", "Q02": "incident_owner_decisions", "Q03": "person_departure_impact",
            "Q04": "decision_details", "Q05": "release_blockers", "Q06": "person_projects_tools",
            "Q07": "none", "Q08": "none", "Q09": "none", "Q10": "project_open_ticket_load"}


def test_offline_router_templates(settings):
    llm = OfflineLLM()
    for q in json.loads(settings.eval_file.read_text())["queries"]:
        out = json.loads(llm.invoke(ROUTER_PROMPT.format(today="", schema="", templates="", question=q["question"])).content)
        assert out["template"] == EXPECTED[q["id"]], q["id"]


def test_hashing_embeddings_similarity():
    e = HashingEmbeddings()
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    assert dot(e.embed_query("ledger-db outage root cause"), e.embed_query("root cause of the ledger-db outage")) > 0.5
