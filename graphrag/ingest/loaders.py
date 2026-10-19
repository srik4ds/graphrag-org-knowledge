"""
Boxes 1A to 1D: read raw source files.

Loaders only read and parse. They do not clean or interpret anything, so a broken
file fails here with a clear message instead of deep inside the pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from graphrag.ingest.models import JiraIssue, SlackChannel, WikiPage
from graphrag.utils import log


def load_directory(path: Path) -> dict:
    """1D: employee directory with people and teams."""
    data = json.loads(path.read_text(encoding="utf-8"))
    log.info("Loaded directory: %d people, %d teams", len(data["people"]), len(data["teams"]))
    return data


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """
    Split '---\\n<yaml>\\n---\\n<body>' into (metadata, body).
    Pages without frontmatter return ({}, text).
    """
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    meta = yaml.safe_load(fm) or {}
    # YAML turns 2026-04-22 into a date object; keep ISO strings everywhere
    meta = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in meta.items()}
    return meta, body.lstrip("\n")


def load_wiki(folder: Path, root: Path) -> list[WikiPage]:
    """1B: every *.md file in the wiki folder."""
    pages = []
    for file in sorted(folder.glob("*.md")):
        meta, body = _split_frontmatter(file.read_text(encoding="utf-8"))
        pages.append(WikiPage(path=str(file.relative_to(root)), meta=meta, body=body))
    log.info("Loaded wiki: %d pages", len(pages))
    return pages


def load_jira(folder: Path, root: Path) -> list[JiraIssue]:
    """1A: every Jira export file; each file holds {"issues": [...]}."""
    issues = []
    for file in sorted(folder.glob("*.json")):
        payload = json.loads(file.read_text(encoding="utf-8"))
        for item in payload.get("issues", []):
            issues.append(JiraIssue(path=str(file.relative_to(root)), data=item))
    log.info("Loaded Jira: %d issues", len(issues))
    return issues


def load_slack(folder: Path, root: Path) -> list[SlackChannel]:
    """1C: every Slack channel export file; each holds {"channel", "messages"}."""
    channels = []
    for file in sorted(folder.glob("*.json")):
        payload = json.loads(file.read_text(encoding="utf-8"))
        channels.append(SlackChannel(path=str(file.relative_to(root)), channel=payload["channel"], messages=payload["messages"]))
    log.info("Loaded Slack: %d channels, %d messages", len(channels), sum(len(c.messages) for c in channels))
    return channels
