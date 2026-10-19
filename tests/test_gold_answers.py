"""
Data consistency: the gold answers in eval/queries.json must be derivable from the
extracted graph. This re-implements each Cypher template's logic in plain Python
over the in-memory GraphBatch, so it runs without Neo4j.
"""

from __future__ import annotations

from collections import defaultdict

import pytest


class MemGraph:
    def __init__(self, batch):
        self.nodes = {}
        for n in batch.nodes:
            self.nodes.setdefault(n.id, {"label": n.label, **n.props}).update(n.props)
        self.out = defaultdict(list)    # src -> [(rel, dst, props)]
        self.inc = defaultdict(list)    # dst -> [(rel, src, props)]
        for e in batch.edges:
            self.out[e.src_id].append((e.rel, e.dst_id, e.props))
            self.inc[e.dst_id].append((e.rel, e.src_id, e.props))

    def name(self, i):
        return self.nodes[i]["name"]

    def outs(self, i, rel):
        return [(d, p) for r, d, p in self.out[i] if r == rel]

    def ins(self, i, rel, label=None):
        return [(s, p) for r, s, p in self.inc[i] if r == rel and (label is None or self.nodes[s]["label"] == label)]


@pytest.fixture(scope="module")
def g(prepared):
    return MemGraph(prepared.graph)


def test_no_unresolved_references(prepared):
    assert prepared.graph.unresolved == []


def test_q01_last_audit_people_and_next_project_tools(g, settings):
    audits = [i for i, n in g.nodes.items() if n["label"] == "Project" and n.get("category") == "audit"
              and n.get("end_date") and n["end_date"] <= settings.today]
    last = max(audits, key=lambda i: g.nodes[i]["end_date"])
    assert g.name(last) == "Q2 2026 SOX Audit"
    people = {g.name(p) for p, _ in g.ins(last, "WORKED_ON")}
    assert people == {"Raj Malhotra", "Sarah Jenkins", "Linh Nguyen"}

    next_tools = {}
    for p, _ in g.ins(last, "WORKED_ON"):
        later = [(props["start_date"], proj) for proj, props in g.outs(p, "WORKED_ON")
                 if proj != last and props.get("start_date", "") >= g.nodes[last]["end_date"]]
        if later:
            proj = min(later)[1]
            next_tools[g.name(p)] = (g.name(proj), {g.name(t) for t, _ in g.outs(proj, "USES")})
    assert next_tools["Sarah Jenkins"] == ("Project Triton", {"Terraform", "Kubernetes", "ArgoCD"})
    assert next_tools["Linh Nguyen"] == ("Project Atlas", {"Snowflake", "dbt", "Airflow", "Snowpipe Streaming"})
    assert "Raj Malhotra" not in next_tools


def test_q02_latest_incident_owner_team_api_security_decisions(g, settings):
    incidents = [i for i, n in g.nodes.items() if n["label"] == "Incident" and n["created"] <= settings.today]
    latest = max(incidents, key=lambda i: g.nodes[i]["created"])
    assert latest == "INC-142"
    service = g.outs(latest, "AFFECTED")[0][0]
    assert g.name(service) == "ledger-db"
    team = g.ins(service, "OWNS", "Team")[0][0]
    assert g.name(team) == "Platform Team"
    api_sec = {d for d, _ in g.ins(team, "DECIDED_BY") if "api-security" in g.nodes[d].get("tags", [])}
    assert api_sec == {"adr_007", "adr_009"}


def test_q03_alex_departure_impact(g):
    owned = {s for s, _ in g.outs("p_achen", "OWNS")}
    assert {g.name(s) for s in owned} == {"ledger-db", "auth-service"}

    def reaches_owned(node, depth=0):
        if node in owned:
            return True
        return depth < 3 and any(reaches_owned(d, depth + 1) for d, _ in g.outs(node, "DEPENDS_ON"))

    releases = {g.name(r) for r, n in g.nodes.items() if n["label"] == "Release"
                if any(reaches_owned(d, 1) for d, _ in g.outs(r, "DEPENDS_ON"))}
    assert releases == {"Triton GA", "Horizon v3 GA"}
    blocking = {t for t, _ in g.ins("p_achen", "ASSIGNED_TO", "Ticket")
                if g.nodes[t]["status"] != "Done" and g.outs(t, "BLOCKS")}
    assert blocking == {"TRI-12", "HOR-8"}


def test_q04_adr_005_approval_and_projects(g):
    assert {g.name(p) for p, _ in g.outs("adr_005", "APPROVED_BY")} == {"Elena Fischer"}
    assert {g.name(p) for p, _ in g.outs("adr_005", "AFFECTS")} == {"Project Atlas", "Project Horizon"}


def test_q05_open_triton_ga_blockers(g):
    open_blockers = {t: g.name(g.outs(t, "ASSIGNED_TO")[0][0]) for t, _ in g.ins("rel_triton_ga", "BLOCKS")
                     if g.nodes[t]["status"] != "Done"}
    assert open_blockers == {"TRI-12": "Alex Chen", "TRI-15": "Sarah Jenkins", "TRI-19": "Tom Brooks"}


def test_q06_linh_tools(g):
    tools = {g.name(t) for p, _ in g.outs("p_lnguyen", "WORKED_ON") for t, _ in g.outs(p, "USES")}
    assert tools == {"AuditBoard", "Snowflake", "dbt", "Airflow", "Snowpipe Streaming"}


def test_q10_atlas_open_ticket_load(g):
    load = defaultdict(list)
    for t, _ in g.ins("proj_atlas", "PART_OF", "Ticket"):
        if g.nodes[t]["status"] != "Done":
            load[g.name(g.outs(t, "ASSIGNED_TO")[0][0])].append(t)
    top = max(load, key=lambda k: len(load[k]))
    assert top == "Ben Wright" and sorted(load[top]) == ["ATL-3", "ATL-5", "ATL-7"]
