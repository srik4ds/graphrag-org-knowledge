"""
Box Q3A: parameterized Cypher templates.

Why templates instead of letting the LLM write Cypher every time?
    1. Reliability: hand-written, tested queries do not hallucinate labels.
    2. Safety: read-only by construction.
    3. Speed: no extra LLM call.
The router (Q2) only has to pick a template name and link one entity id.
Questions that fit no template fall back to Text2Cypher (text2cypher.py).

Each template declares:
    name            identifier the router returns
    description     shown to the router LLM so it can choose
    entity_label    label of the entity whose id fills $id
    statements      one or more Cypher queries (all take $id)
    formatter       turns result rows into short, human-readable facts
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

Rows = list[dict]
Formatter = Callable[[list[Rows]], list[str]]


@dataclass(frozen=True)
class CypherTemplate:
    name: str
    description: str
    entity_label: str
    statements: tuple[str, ...]
    formatter: Formatter


def _join(items) -> str:
    items = [i for i in (items or []) if i]
    return ", ".join(items) if items else "none recorded"


# --------------------------------------------------------------------------- #
# 1. People on a project, and the project each moved to next (with its tools)
# --------------------------------------------------------------------------- #
_PROJECT_PEOPLE_NEXT = """
MATCH (a:Project {id: $id})<-[w1:WORKED_ON]-(p:Person)
OPTIONAL MATCH (p)-[w2:WORKED_ON]->(nxt:Project)
  WHERE nxt <> a AND a.end_date IS NOT NULL AND w2.start_date >= a.end_date
WITH a, p, w1, nxt, w2 ORDER BY w2.start_date ASC
WITH a, p, w1, collect({id: nxt.id, name: nxt.name, start: w2.start_date})[0] AS following
OPTIONAL MATCH (np:Project {id: following.id})-[:USES]->(t:Tool)
RETURN a.name AS project, a.start_date AS project_start, a.end_date AS project_end,
       p.name AS person, w1.role AS role,
       following.name AS next_project, following.start AS next_start, collect(t.name) AS next_tools
ORDER BY person
"""


def _fmt_project_people_next(results: list[Rows]) -> list[str]:
    facts = []
    for r in results[0]:
        line = f"{r['person']} worked on {r['project']} ({r['project_start']} to {r['project_end'] or 'ongoing'}) as {r['role']}."
        if r.get("next_project"):
            line += f" Next project: {r['next_project']} (from {r['next_start']}), which uses {_join(r['next_tools'])}."
        else:
            line += " No later project is recorded."
        facts.append(line)
    return facts


# --------------------------------------------------------------------------- #
# 2. Incident -> affected service -> owning team -> that team's decisions
# --------------------------------------------------------------------------- #
_INCIDENT_OWNER_DECISIONS = """
MATCH (i:Incident {id: $id})-[:AFFECTED]->(s:Service)<-[:OWNS]-(team:Team)
OPTIONAL MATCH (d:Decision)-[:DECIDED_BY]->(team)
OPTIONAL MATCH (d)-[:APPROVED_BY]->(ap:Person)
WITH i, s, team, d, collect(ap.name) AS approvers
RETURN i.key AS incident, i.summary AS summary, i.created AS date, i.severity AS severity,
       s.name AS service, team.name AS owner_team,
       d.name AS decision, d.tags AS tags, d.date AS decision_date, approvers
ORDER BY decision
"""


def _fmt_incident_owner_decisions(results: list[Rows]) -> list[str]:
    rows = results[0]
    if not rows:
        return []
    r0 = rows[0]
    facts = [f"Incident {r0['incident']} ({r0['severity']}, {r0['date']}: {r0['summary']}) affected the service "
             f"{r0['service']}, which is owned by {r0['owner_team']}."]
    for r in rows:
        if r.get("decision"):
            facts.append(f"{r['owner_team']} decision {r['decision']} (date {r['decision_date']}, "
                         f"tags: {_join(r['tags'])}; approved by {_join(r['approvers'])}).")
    return facts


# --------------------------------------------------------------------------- #
# 3. Person leaves: owned services -> releases depending on them; blocking tickets
# --------------------------------------------------------------------------- #
_PERSON_IMPACT_OWNED = """
MATCH (p:Person {id: $id})-[:OWNS]->(s:Service)
OPTIONAL MATCH path = (r:Release)-[:DEPENDS_ON*1..3]->(s)
RETURN p.name AS person, s.name AS service, r.name AS release, r.target_date AS target_date,
       [n IN nodes(path) | n.name] AS chain
"""
_PERSON_IMPACT_TICKETS = """
MATCH (p:Person {id: $id})<-[:ASSIGNED_TO]-(t:Ticket)-[:BLOCKS]->(r:Release)
WHERE t.status <> 'Done'
RETURN p.name AS person, t.key AS ticket, t.summary AS summary, t.status AS status, r.name AS release
ORDER BY ticket
"""


def _fmt_person_impact(results: list[Rows]) -> list[str]:
    owned, tickets = results[0], results[1]
    facts, seen = [], set()
    services = sorted({r["service"] for r in owned})
    if owned:
        facts.append(f"{owned[0]['person']} is the primary owner of: {_join(services)}.")
    for r in owned:
        if r.get("release") and tuple(r["chain"]) not in seen:
            seen.add(tuple(r["chain"]))
            facts.append(f"Release {r['release']} (target {r['target_date']}) depends on {r['service']} "
                         f"through the chain {' -> '.join(r['chain'])}.")
    for r in tickets:
        facts.append(f"{r['person']} is assigned open ticket {r['ticket']} ({r['summary']}, status {r['status']}), "
                     f"which blocks release {r['release']}.")
    return facts


# --------------------------------------------------------------------------- #
# 4. Decision: who proposed, approved, decided, and what it affects
# --------------------------------------------------------------------------- #
_DECISION_DETAILS = """
MATCH (d:Decision {id: $id})
OPTIONAL MATCH (d)-[:APPROVED_BY]->(a:Person)
OPTIONAL MATCH (d)-[:PROPOSED_BY]->(pp:Person)
OPTIONAL MATCH (d)-[:DECIDED_BY]->(t:Team)
OPTIONAL MATCH (d)-[:AFFECTS]->(pr:Project)
RETURN d.name AS decision, d.date AS date, d.status AS status, d.tags AS tags,
       collect(DISTINCT a.name) AS approved_by, collect(DISTINCT pp.name) AS proposed_by,
       collect(DISTINCT t.name) AS decided_by, collect(DISTINCT pr.name) AS affects
"""


def _fmt_decision(results: list[Rows]) -> list[str]:
    return [
        f"{r['decision']} (status {r['status']}, dated {r['date']}) was decided by {_join(r['decided_by'])}, "
        f"proposed by {_join(r['proposed_by'])}, approved by {_join(r['approved_by'])}, "
        f"and affects {_join(r['affects'])}."
        for r in results[0]
    ]


# --------------------------------------------------------------------------- #
# 5. Tickets blocking a release (all statuses, so the LLM can exclude Done ones)
# --------------------------------------------------------------------------- #
_RELEASE_BLOCKERS = """
MATCH (r:Release {id: $id})
OPTIONAL MATCH (t:Ticket)-[:BLOCKS]->(r)
OPTIONAL MATCH (t)-[:ASSIGNED_TO]->(p:Person)
RETURN r.name AS release, r.target_date AS target_date, t.key AS ticket, t.summary AS summary,
       t.status AS status, t.priority AS priority, p.name AS assignee
ORDER BY ticket
"""


def _fmt_release_blockers(results: list[Rows]) -> list[str]:
    facts = []
    for r in results[0]:
        if not r.get("ticket"):
            facts.append(f"No tickets are linked as blocking {r['release']}.")
            continue
        state = "closed, no longer blocking" if r["status"] == "Done" else "open"
        facts.append(f"Ticket {r['ticket']} ({r['summary']}) blocks {r['release']} (target {r['target_date']}); "
                     f"status {r['status']} ({state}); priority {r['priority']}; assigned to {r['assignee']}.")
    return facts


# --------------------------------------------------------------------------- #
# 6. Person -> projects -> tools
# --------------------------------------------------------------------------- #
_PERSON_PROJECTS_TOOLS = """
MATCH (p:Person {id: $id})-[w:WORKED_ON]->(pr:Project)
OPTIONAL MATCH (pr)-[:USES]->(t:Tool)
RETURN p.name AS person, pr.name AS project, w.role AS role, w.start_date AS start_date,
       w.end_date AS end_date, collect(t.name) AS tools
ORDER BY start_date
"""


def _fmt_person_projects(results: list[Rows]) -> list[str]:
    return [
        f"{r['person']} worked on {r['project']} as {r['role']} ({r['start_date']} to {r['end_date'] or 'present'}); "
        f"that project uses {_join(r['tools'])}."
        for r in results[0]
    ]


# --------------------------------------------------------------------------- #
# 7. Open ticket load per person on a project
# --------------------------------------------------------------------------- #
_PROJECT_TICKET_LOAD = """
MATCH (pr:Project {id: $id})<-[:PART_OF]-(t:Ticket)-[:ASSIGNED_TO]->(p:Person)
WHERE t.status <> 'Done'
RETURN pr.name AS project, p.name AS assignee, count(t) AS open_tickets,
       collect(t.key + ' ' + t.summary + ' [' + t.status + ']') AS tickets
ORDER BY open_tickets DESC, assignee
"""


def _fmt_ticket_load(results: list[Rows]) -> list[str]:
    return [
        f"On {r['project']}, {r['assignee']} has {r['open_tickets']} open ticket(s): {'; '.join(r['tickets'])}."
        for r in results[0]
    ]


# --------------------------------------------------------------------------- #
# 8. Service: owners, dependencies, dependents, incidents
# --------------------------------------------------------------------------- #
_SERVICE_OVERVIEW = """
MATCH (s:Service {id: $id})
OPTIONAL MATCH (team:Team)-[:OWNS]->(s)
OPTIONAL MATCH (owner:Person)-[:OWNS]->(s)
OPTIONAL MATCH (s)-[:DEPENDS_ON]->(dep:Service)
OPTIONAL MATCH (x)-[:DEPENDS_ON]->(s)
OPTIONAL MATCH (i:Incident)-[:AFFECTED]->(s)
RETURN s.name AS service, collect(DISTINCT team.name) AS owner_team, collect(DISTINCT owner.name) AS owner,
       collect(DISTINCT dep.name) AS depends_on, collect(DISTINCT x.name) AS depended_on_by,
       collect(DISTINCT i.name) AS incidents
"""


def _fmt_service(results: list[Rows]) -> list[str]:
    return [
        f"Service {r['service']} is owned by team {_join(r['owner_team'])} (primary owner {_join(r['owner'])}); "
        f"it depends on {_join(r['depends_on'])}; it is depended on by {_join(r['depended_on_by'])}; "
        f"incidents: {_join(r['incidents'])}."
        for r in results[0]
    ]


# --------------------------------------------------------------------------- #
# 9. Generic 1-hop neighbourhood of any entity (used when nothing else fits)
# --------------------------------------------------------------------------- #
_NEIGHBORHOOD = """
MATCH (n {id: $id})-[r]-(m)
WHERE NOT m:Chunk AND NOT m:Parent AND NOT m:Document
RETURN n.name AS entity, type(r) AS rel, startNode(r) = n AS outgoing, m.name AS neighbor,
       labels(m)[0] AS neighbor_label, properties(r) AS rel_props
LIMIT 60
"""


def _fmt_neighborhood(results: list[Rows]) -> list[str]:
    facts = []
    for r in results[0]:
        props = {k: v for k, v in (r.get("rel_props") or {}).items() if v}
        extra = f" {props}" if props else ""
        if r["outgoing"]:
            facts.append(f"{r['entity']} -[{r['rel']}{extra}]-> {r['neighbor']} ({r['neighbor_label']})")
        else:
            facts.append(f"{r['neighbor']} ({r['neighbor_label']}) -[{r['rel']}{extra}]-> {r['entity']}")
    return facts


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
TEMPLATES: dict[str, CypherTemplate] = {t.name: t for t in [
    CypherTemplate("project_people_next_projects",
                   "People who worked on a project, and the project each person moved to next with its tools. "
                   "Use for 'who worked on X and what did they do/use afterwards'.",
                   "Project", (_PROJECT_PEOPLE_NEXT,), _fmt_project_people_next),
    CypherTemplate("incident_owner_decisions",
                   "Service affected by an incident, the team that owns it, and that team's decisions. "
                   "Use for 'decisions made by the team that owns the service that failed'.",
                   "Incident", (_INCIDENT_OWNER_DECISIONS,), _fmt_incident_owner_decisions),
    CypherTemplate("person_departure_impact",
                   "Services a person owns, releases that depend on them (up to 3 hops), and open tickets "
                   "assigned to the person that block releases. Use for 'if X leaves, what is at risk'.",
                   "Person", (_PERSON_IMPACT_OWNED, _PERSON_IMPACT_TICKETS), _fmt_person_impact),
    CypherTemplate("decision_details",
                   "Who proposed, approved and decided a decision (ADR), and which projects it affects.",
                   "Decision", (_DECISION_DETAILS,), _fmt_decision),
    CypherTemplate("release_blockers",
                   "Tickets that block a release, with status and assignee.",
                   "Release", (_RELEASE_BLOCKERS,), _fmt_release_blockers),
    CypherTemplate("person_projects_tools",
                   "Projects a person worked on, their role and dates, and the tools each project uses.",
                   "Person", (_PERSON_PROJECTS_TOOLS,), _fmt_person_projects),
    CypherTemplate("project_open_ticket_load",
                   "Open tickets on a project grouped and counted per assignee. Use for 'who has the most open tickets'.",
                   "Project", (_PROJECT_TICKET_LOAD,), _fmt_ticket_load),
    CypherTemplate("service_overview",
                   "Owner team, primary owner, dependencies, dependents and incidents of a service.",
                   "Service", (_SERVICE_OVERVIEW,), _fmt_service),
    CypherTemplate("entity_neighborhood",
                   "All direct relationships of one entity. Use when the question is about one entity "
                   "but no other template fits.",
                   "*", (_NEIGHBORHOOD,), _fmt_neighborhood),
]}


def describe_templates() -> str:
    """Bullet list of templates for the router prompt."""
    return "\n".join(f"- {t.name} (needs a {t.entity_label if t.entity_label != '*' else 'any'} entity): {t.description}"
                     for t in TEMPLATES.values())
