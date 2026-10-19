"""
Plain data classes passed between ingestion steps.

Using small typed records (instead of raw dicts) makes each step's input and output
explicit and easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Raw inputs (output of loaders.py)
# --------------------------------------------------------------------------- #
@dataclass
class WikiPage:
    """One Notion markdown page: YAML frontmatter + markdown body."""
    path: str                      # relative path, e.g. "wiki/adr_005_snowpipe_streaming.md"
    meta: dict[str, Any]           # parsed frontmatter
    body: str                      # raw markdown body


@dataclass
class JiraIssue:
    """One Jira issue as exported to JSON."""
    path: str
    data: dict[str, Any]


@dataclass
class SlackChannel:
    """All messages of one Slack channel export."""
    path: str
    channel: str
    messages: list[dict[str, Any]]


# --------------------------------------------------------------------------- #
# Graph records (output of graph_extractors.py, input of graph_writer.py)
# --------------------------------------------------------------------------- #
@dataclass
class Node:
    label: str
    id: str
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    src_label: str
    src_id: str
    rel: str
    dst_label: str
    dst_id: str
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphBatch:
    """Nodes and edges produced by one extractor. Batches can be merged with +."""
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)   # references we could not resolve

    def __add__(self, other: "GraphBatch") -> "GraphBatch":
        return GraphBatch(self.nodes + other.nodes, self.edges + other.edges, self.unresolved + other.unresolved)


# --------------------------------------------------------------------------- #
# Text for the vector side (output of cleaners.py, input of chunker.py)
# --------------------------------------------------------------------------- #
@dataclass
class TextDocument:
    """Cleaned narrative text ready for chunking (wiki body or one Slack thread)."""
    doc_id: str                    # same id as the (:Document) node
    title: str
    source: str                    # "wiki" or "slack"
    path: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParentChunk:
    id: str
    doc_id: str
    text: str
    position: int


@dataclass
class ChildChunk:
    id: str
    parent_id: str
    doc_id: str
    text: str
    position: int
    mentions: list[tuple[str, str]] = field(default_factory=list)   # [(label, entity_id)]
