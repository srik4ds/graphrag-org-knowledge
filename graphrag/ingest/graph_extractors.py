"""
Box 4A (part 1): turn parsed records into graph nodes and edges.

Two passes:
    Pass 1  build_registry()   register every entity and all its names, so that
                               references can be resolved regardless of file order.
    Pass 2  extract_*()        emit Node and Edge records, resolving every reference
                               through the registry.

Nothing here talks to Neo4j; graph_writer.py does the writing. That keeps this
module easy to unit test.
"""

from __future__ import annotations

from pathlib import Path

from graphrag.ingest.entity_resolver import EntityRegistry
from graphrag.ingest.models import Edge, GraphBatch, JiraIssue, Node, WikiPage
from graphrag.utils import slugify

# Wiki page types that describe an entity (the page's frontmatter `id` is the entity id)
ENTITY_PAGE_LABEL = {"project": "Project", "service": "Service", "decision": "Decision"}


def _aliases_text(aliases: list[str] | None) -> str:
    """Aliases joined into one string so the full-text index can search them."""
    return " | ".join(aliases or [])


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def wiki_doc_id(page: WikiPage) -> str:
    """
    Id of the (:Document) node for a wiki page.
    Entity pages (project/service/decision) get doc_<file stem> so the document and
    the entity it describes have different ids.
    """
    if page.meta.get("type") in ENTITY_PAGE_LABEL or not page.meta.get("id"):
        return f"doc_{Path(page.path).stem}"
    return page.meta["id"]


# =========================================================================== #
# Pass 1: registry
# =========================================================================== #
def build_registry(directory: dict, pages: list[WikiPage], issues: list[JiraIssue]) -> EntityRegistry:
    """Register every person, team, project, service, decision, release, tool, ticket and incident."""
    reg = EntityRegistry()

    # 1D directory: teams and people (Slack ids and Jira users are lookup-only keys)
    for team in directory["teams"]:
        reg.add("Team", team["id"], team["name"], team.get("aliases"))
    for p in directory["people"]:
        reg.add("Person", p["id"], p["name"], p.get("aliases"),
                lookup_only=[p.get("jira_user"), p.get("email"), p.get("slack_id")])
        reg.add_slack_id(p["slack_id"], p["id"])

    # 1B wiki: entity pages, releases inside project pages, tools in `uses`
    for page in pages:
        meta = page.meta
        label = ENTITY_PAGE_LABEL.get(meta.get("type"))
        if label:
            reg.add(label, meta["id"], meta["name"], _as_list(meta.get("aliases")))
        for rel in _as_list(meta.get("releases")):
            reg.add("Release", rel["id"], rel["name"])
        for tool in _as_list(meta.get("uses")):
            reg.resolve_or_create(tool, "Tool", "tool")

    # 1A Jira: ticket keys and incidents
    for issue in issues:
        d = issue.data
        label = "Incident" if d["issue_type"] == "Incident" else "Ticket"
        reg.add(label, d["key"], f"{d['key']}: {d['summary']}", [d["key"]])

    return reg


# =========================================================================== #
# Pass 2: extractors
# =========================================================================== #
class _Builder:
    """Collects nodes and edges and records references that could not be resolved."""

    def __init__(self, reg: EntityRegistry) -> None:
        self.reg = reg
        self.batch = GraphBatch()

    def node(self, label: str, node_id: str, **props) -> None:
        self.batch.nodes.append(Node(label, node_id, {k: v for k, v in props.items() if v is not None}))

    def edge(self, src_label: str, src_id: str, rel: str, dst_label: str, ref: str | None,
             context: str, **props) -> None:
        """Resolve `ref` to an id of dst_label and add the edge, or log it as unresolved."""
        if not ref:
            return
        dst_id = self.reg.resolve(ref, dst_label)
        if dst_id is None:
            self.batch.unresolved.append(f"{context}: {dst_label} '{ref}'")
            return
        self.batch.edges.append(Edge(src_label, src_id, rel, dst_label, dst_id,
                                     {k: v for k, v in props.items() if v is not None}))

    def edge_any(self, src_label: str, src_id: str, rel: str, dst_labels: list[str], ref: str, context: str) -> None:
        """Like edge(), but the target may be one of several labels (e.g. ABOUT Project or Service)."""
        for label in dst_labels:
            if self.reg.resolve(ref, label):
                return self.edge(src_label, src_id, rel, label, ref, context)
        self.batch.unresolved.append(f"{context}: {'/'.join(dst_labels)} '{ref}'")


# ---- 1D directory ---------------------------------------------------------- #
def extract_directory(directory: dict, reg: EntityRegistry) -> GraphBatch:
    b = _Builder(reg)
    for team in directory["teams"]:
        b.node("Team", team["id"], name=team["name"], aliases_text=_aliases_text(team.get("aliases")))
    for p in directory["people"]:
        b.node("Person", p["id"], name=p["name"], title=p.get("title"), email=p.get("email"),
               aliases_text=_aliases_text(p.get("aliases")))
        b.edge("Person", p["id"], "MEMBER_OF", "Team", p.get("team"), f"directory {p['id']}")
    return b.batch


# ---- 1B wiki --------------------------------------------------------------- #
def extract_wiki(pages: list[WikiPage], reg: EntityRegistry) -> GraphBatch:
    b = _Builder(reg)
    for page in pages:
        meta, ctx = page.meta, page.path
        page_type = meta.get("type", "page")
        doc_id = wiki_doc_id(page)

        # Every page becomes a Document node (the vector chunks hang off it)
        b.node("Document", doc_id, name=meta.get("name", page.path), doc_type=page_type,
               path=page.path, updated=meta.get("updated"), source="wiki")
        b.edge("Document", doc_id, "AUTHORED_BY", "Person", meta.get("author"), ctx)
        for ref in _as_list(meta.get("about")):
            b.edge_any("Document", doc_id, "ABOUT", ["Project", "Service"], ref, ctx)

        if page_type == "project":
            _extract_project(b, meta, doc_id, ctx)
        elif page_type == "service":
            _extract_service(b, meta, doc_id, ctx)
        elif page_type == "decision":
            _extract_decision(b, meta, doc_id, ctx)
        elif page_type == "postmortem":
            b.edge("Document", doc_id, "DOCUMENTS", "Incident", meta.get("incident"), ctx)
    return b.batch


def _extract_project(b: _Builder, meta: dict, doc_id: str, ctx: str) -> None:
    pid = meta["id"]
    b.node("Project", pid, name=meta["name"], category=meta.get("category"), status=meta.get("status"),
           start_date=meta.get("start_date"), end_date=meta.get("end_date"),
           aliases_text=_aliases_text(meta.get("aliases")))
    b.edge("Document", doc_id, "ABOUT", "Project", pid, ctx)
    b.edge("Project", pid, "OWNED_BY", "Team", meta.get("owner_team"), ctx)
    for tool in _as_list(meta.get("uses")):
        b.edge("Project", pid, "USES", "Tool", tool, ctx)
    for m in _as_list(meta.get("members")):
        # WORKED_ON goes Person -> Project, so resolve the person and add the edge directly
        person_id = b.reg.resolve(m["person"], "Person")
        if person_id is None:
            b.batch.unresolved.append(f"{ctx}: Person '{m['person']}'")
            continue
        b.batch.edges.append(Edge("Person", person_id, "WORKED_ON", "Project", pid, {
            k: v for k, v in {"role": m.get("role"), "start_date": _iso(m.get("start")),
                              "end_date": _iso(m.get("end"))}.items() if v is not None}))
    for rel in _as_list(meta.get("releases")):
        b.node("Release", rel["id"], name=rel["name"], target_date=_iso(rel.get("target_date")))
        b.edge("Release", rel["id"], "PART_OF", "Project", pid, ctx)
        for svc in _as_list(rel.get("depends_on")):
            b.edge("Release", rel["id"], "DEPENDS_ON", "Service", svc, ctx)


def _extract_service(b: _Builder, meta: dict, doc_id: str, ctx: str) -> None:
    sid = meta["id"]
    b.node("Service", sid, name=meta["name"], tier=meta.get("tier"), aliases_text=_aliases_text(meta.get("aliases")))
    b.edge("Document", doc_id, "ABOUT", "Service", sid, ctx)
    team_id = b.reg.resolve(meta.get("owner_team"), "Team")
    if team_id:
        b.batch.edges.append(Edge("Team", team_id, "OWNS", "Service", sid))
    else:
        b.batch.unresolved.append(f"{ctx}: Team '{meta.get('owner_team')}'")
    owner_id = b.reg.resolve(meta.get("owner"), "Person")
    if owner_id:
        b.batch.edges.append(Edge("Person", owner_id, "OWNS", "Service", sid))
    for dep in _as_list(meta.get("depends_on")):
        b.edge("Service", sid, "DEPENDS_ON", "Service", dep, ctx)
    for tool in _as_list(meta.get("uses")):
        b.edge("Service", sid, "USES", "Tool", tool, ctx)


def _extract_decision(b: _Builder, meta: dict, doc_id: str, ctx: str) -> None:
    did = meta["id"]
    b.node("Decision", did, name=meta["name"], status=meta.get("status"), date=meta.get("date"),
           tags=_as_list(meta.get("tags")), aliases_text=_aliases_text(meta.get("aliases")))
    b.edge("Document", doc_id, "DOCUMENTS", "Decision", did, ctx)
    b.edge("Decision", did, "DECIDED_BY", "Team", meta.get("decided_by"), ctx)
    b.edge("Decision", did, "PROPOSED_BY", "Person", meta.get("proposed_by"), ctx)
    for approver in _as_list(meta.get("approved_by")):
        b.edge("Decision", did, "APPROVED_BY", "Person", approver, ctx)
    for project in _as_list(meta.get("affects")):
        b.edge("Decision", did, "AFFECTS", "Project", project, ctx)


def _iso(value) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)


# ---- 1A Jira --------------------------------------------------------------- #
def extract_jira(issues: list[JiraIssue], reg: EntityRegistry) -> GraphBatch:
    b = _Builder(reg)
    for issue in issues:
        d, ctx = issue.data, f"{issue.path} {issue.data['key']}"
        key = d["key"]
        common = dict(key=key, name=f"{key}: {d['summary']}", summary=d["summary"], status=d.get("status"),
                      priority=d.get("priority"), created=d.get("created"), resolved=d.get("resolved"),
                      description=d.get("description") or None, aliases_text=key)

        if d["issue_type"] == "Incident":
            b.node("Incident", key, severity=d.get("severity"), **common)
            b.edge("Incident", key, "AFFECTED", "Service", d.get("affected_service"), ctx)
            b.edge("Incident", key, "ASSIGNED_TO", "Person", d.get("assignee"), ctx)
            continue

        b.node("Ticket", key, issue_type=d["issue_type"], **common)
        b.edge("Ticket", key, "PART_OF", "Project", d.get("epic"), ctx)
        b.edge("Ticket", key, "ASSIGNED_TO", "Person", d.get("assignee"), ctx)
        b.edge("Ticket", key, "REPORTED_BY", "Person", d.get("reporter"), ctx)
        for link in d.get("links", []):
            if link.get("type") != "blocks":
                continue
            target = link["target"]
            if reg.resolve(target, "Release"):
                b.edge("Ticket", key, "BLOCKS", "Release", target, ctx)
            else:
                b.edge("Ticket", key, "BLOCKS", "Ticket", target, ctx)
    return b.batch


def tool_nodes(reg: EntityRegistry) -> GraphBatch:
    """Tools are registered on the fly (from `uses` lists); emit one node per tool."""
    b = _Builder(reg)
    for rec in reg.records("Tool"):
        b.node("Tool", rec.id, name=rec.name, aliases_text="")
    return b.batch


def slack_document_nodes(docs, reg: EntityRegistry) -> GraphBatch:
    """
    Slack threads go to the VECTOR side only, but each thread still needs a
    (:Document) node so its chunks have a parent document and a source to cite.
    No structural entities are extracted from Slack.
    """
    b = _Builder(reg)
    for doc in docs:
        b.node("Document", doc.doc_id, name=doc.title, doc_type="slack_thread", path=doc.path,
               updated=doc.metadata.get("updated"), source="slack", channel=doc.metadata.get("channel"))
    return b.batch


__all__ = [
    "build_registry", "extract_directory", "extract_wiki", "extract_jira",
    "tool_nodes", "slack_document_nodes", "wiki_doc_id", "slugify",
]
