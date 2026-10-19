"""
Boxes 2A to 2C: cleaning before anything is chunked or loaded.

    2A  Jira    : no text cleaning needed (structured), handled in graph_extractors.py
    2B  Wiki    : split frontmatter (graph) from body (vector); strip markdown syntax
    2C  Slack   : resolve <@U123> ids to names, drop bot/join noise, group by thread
"""

from __future__ import annotations

import html
import re
from collections import defaultdict
from datetime import datetime, timezone

from graphrag.ingest.entity_resolver import EntityRegistry
from graphrag.ingest.models import SlackChannel, TextDocument, WikiPage

# --------------------------------------------------------------------------- #
# 2B: Markdown -> plain text
# --------------------------------------------------------------------------- #
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")          # [text](url) -> text
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")          # images are dropped
_MD_EMPHASIS = re.compile(r"(\*\*|__|\*|_|`)")           # bold, italic, inline code markers
_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_MD_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}.*$", re.MULTILINE)
_MULTI_BLANK = re.compile(r"\n{3,}")


def strip_markdown(markdown: str) -> str:
    """
    Remove markdown syntax but keep the words and the paragraph structure.

    Headings keep their text (they carry meaning, e.g. "Root cause"), so a heading
    becomes a plain line followed by its paragraph.
    """
    text = markdown.replace("```", "")
    text = _MD_IMAGE.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_HEADING.sub("", text)
    text = _MD_TABLE_RULE.sub("", text)
    text = _MD_EMPHASIS.sub("", text)
    text = html.unescape(text)                                # &amp; -> &
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def wiki_to_text_document(page: WikiPage, doc_id: str, registry: EntityRegistry) -> TextDocument:
    """Body text of a wiki page, cleaned and with person names canonicalized."""
    body = registry.canonicalize_text(strip_markdown(page.body))
    title = page.meta.get("name") or page.path
    return TextDocument(
        doc_id=doc_id, title=title, source="wiki", path=page.path,
        # Title helps both BM25 and embeddings; skip it if the body already starts with it
        text=body if body.lower().startswith(str(title).lower()) else f"{title}\n\n{body}",
        metadata={"doc_type": page.meta.get("type", "page"), "updated": page.meta.get("updated")},
    )


# --------------------------------------------------------------------------- #
# 2C: Slack
# --------------------------------------------------------------------------- #
_SLACK_USER = re.compile(r"<@(U[A-Z0-9]+)>")
_NOISE_SUBTYPES = {"channel_join", "channel_leave", "bot_message", "channel_topic", "channel_purpose"}


def clean_slack_text(raw_text: str, registry: EntityRegistry) -> str:
    """
    Resolve Slack user mentions and strip formatting.

        "Hey <@U12345XYZ> can you **deploy**?"  ->  "Hey Alex Chen can you deploy?"
    """
    def _replace(match: re.Match) -> str:
        person_id = registry.person_from_slack(match.group(1))
        return registry.name_of(person_id) if person_id else f"Unknown_User_{match.group(1)}"

    text = _SLACK_USER.sub(_replace, raw_text)
    text = text.replace("**", "").replace("`", "")
    return html.unescape(text).strip()


def is_noise(message: dict) -> bool:
    """Bot posts and join/leave events add no knowledge."""
    return message.get("subtype") in _NOISE_SUBTYPES or "bot_id" in message


def _ts_to_iso(ts: str) -> str:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def slack_threads_to_documents(channel: SlackChannel, registry: EntityRegistry) -> list[TextDocument]:
    """
    Group a channel's messages by thread and render each thread as one document:

        Slack #incidents, thread started 2026-10-12 14:21 UTC
        Tom Brooks: SEV1 declared ...
        Alex Chen: Looking. ...
    """
    threads: dict[str, list[dict]] = defaultdict(list)
    for msg in channel.messages:
        if is_noise(msg):
            continue
        threads[msg.get("thread_ts") or msg["ts"]].append(msg)

    docs = []
    for thread_ts, msgs in threads.items():
        msgs.sort(key=lambda m: float(m["ts"]))
        lines, participants = [], set()
        for m in msgs:
            person_id = registry.person_from_slack(m.get("user", ""))
            author = registry.name_of(person_id) if person_id else "Unknown user"
            if person_id:
                participants.add(person_id)
            lines.append(f"{author}: {clean_slack_text(m.get('text', ''), registry)}")
        started = _ts_to_iso(thread_ts)
        title = f"Slack #{channel.channel} thread, {started}"
        docs.append(TextDocument(
            doc_id=f"slack_{channel.channel}_{thread_ts.replace('.', '_')}",
            title=title, source="slack", path=channel.path,
            text=title + "\n" + "\n".join(lines),
            metadata={"doc_type": "slack_thread", "channel": channel.channel, "updated": started[:10],
                      "participants": sorted(participants)},
        ))
    return docs
