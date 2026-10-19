"""
Box 3: Entity resolver.

Problem: the same real-world thing is written differently in every source.

    Jira      assignee: "sjenkins"
    Wiki      owner: "S. Jenkins"
    Slack     <@U98765ABC>
    Text      "Sarah Jenkins"

Without resolution the graph would get four separate "Sarah" nodes and every
multi-hop path through her would break.

The EntityRegistry keeps one canonical id per entity plus every known surface form
(name, aliases, Slack id, Jira user). Ingestion code asks it:

    registry.resolve("S. Jenkins", "Person")   -> "p_sjenkins"
    registry.find_mentions(chunk_text)         -> [("Person", "p_sjenkins"), ...]
    registry.canonicalize_text("S. Jenkins")   -> "Sarah Jenkins"
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from graphrag.utils import slugify


def _norm(text: str) -> str:
    """Case- and whitespace-insensitive lookup key."""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


@dataclass
class EntityRecord:
    label: str
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)


class EntityRegistry:
    """Lookup tables from every surface form to a canonical (label, id)."""

    # Labels whose names we look for inside free text (chunk MENTIONS)
    MENTIONABLE = {"Person", "Team", "Project", "Service", "Tool", "Release", "Decision", "Incident", "Ticket"}

    def __init__(self) -> None:
        self._records: dict[str, EntityRecord] = {}                    # id -> record
        self._lookup: dict[str, list[tuple[str, str]]] = defaultdict(list)  # norm form -> [(label, id)]
        self._slack: dict[str, str] = {}                               # slack id -> person id
        self._mention_forms: dict[str, tuple[str, str]] = {}           # surface form -> (label, id)
        self._abbrev_forms: dict[str, str] = {}                        # "S. Jenkins" -> "Sarah Jenkins"
        self._mention_regex: re.Pattern | None = None

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    def add(self, label: str, entity_id: str, name: str, aliases: list[str] | None = None,
            lookup_only: list[str] | None = None) -> None:
        """
        Register an entity.
        aliases      : alternative spellings that may appear in text
        lookup_only  : keys used for resolution but never searched for in text
                       (Jira usernames, emails)
        """
        aliases = [a for a in (aliases or []) if a]
        if entity_id in self._records:                                 # merge aliases on re-registration
            rec = self._records[entity_id]
            rec.aliases = sorted(set(rec.aliases) | set(aliases))
        else:
            self._records[entity_id] = EntityRecord(label, entity_id, name, aliases)

        for form in [name, entity_id, *aliases, *(lookup_only or [])]:
            key = _norm(form)
            if (label, entity_id) not in self._lookup[key]:
                self._lookup[key].append((label, entity_id))

        if label in self.MENTIONABLE:
            for form in [name, *aliases]:
                if self._is_safe_mention(form):
                    self._mention_forms[form] = (label, entity_id)
                if label == "Person" and re.fullmatch(r"[A-Z]\. ?[A-Z][a-z]+", form):
                    self._abbrev_forms[form] = name
        self._mention_regex = None                                     # rebuild lazily

    def add_slack_id(self, slack_id: str, person_id: str) -> None:
        self._slack[slack_id] = person_id

    @staticmethod
    def _is_safe_mention(form: str) -> bool:
        """Skip very short aliases (e.g. 'Raj') that would match unrelated words."""
        return len(form) >= 4 or any(c.isdigit() for c in form)

    # ------------------------------------------------------------------ #
    # Lookups
    # ------------------------------------------------------------------ #
    def resolve(self, ref: str | None, label: str | None = None) -> str | None:
        """Return the canonical id for a reference, or None if unknown or ambiguous."""
        if not ref:
            return None
        hits = self._lookup.get(_norm(ref), [])
        if label:                                   # caller knows the type: take the match of that type
            hits = [h for h in hits if h[0] == label]
            return hits[0][1] if hits else None
        return hits[0][1] if len(hits) == 1 else None   # no type given: only accept unambiguous matches

    def resolve_or_create(self, ref: str, label: str, prefix: str) -> str:
        """
        Resolve a reference; if unknown, register a new entity.
        Used for open-ended vocabularies such as tools ("Terraform", "dbt").
        """
        found = self.resolve(ref, label)
        if found:
            return found
        new_id = f"{prefix}_{slugify(ref)}"
        self.add(label, new_id, ref)
        return new_id

    def person_from_slack(self, slack_id: str) -> str | None:
        return self._slack.get(slack_id)

    def get(self, entity_id: str) -> EntityRecord | None:
        return self._records.get(entity_id)

    def name_of(self, entity_id: str) -> str:
        rec = self._records.get(entity_id)
        return rec.name if rec else entity_id

    def records(self, label: str | None = None) -> list[EntityRecord]:
        return [r for r in self._records.values() if label is None or r.label == label]

    # ------------------------------------------------------------------ #
    # Text helpers (vector side)
    # ------------------------------------------------------------------ #
    def canonicalize_text(self, text: str) -> str:
        """Replace abbreviated person names ('S. Jenkins') with full names ('Sarah Jenkins')."""
        for short, full in sorted(self._abbrev_forms.items(), key=lambda kv: -len(kv[0])):
            text = re.sub(rf"(?<![\w]){re.escape(short)}(?![\w])", full, text)
        return text

    def _build_mention_regex(self) -> re.Pattern:
        forms = sorted(self._mention_forms, key=len, reverse=True)     # longest first
        alternation = "|".join(re.escape(f) for f in forms)
        return re.compile(rf"(?<![\w\-])({alternation})(?![\w\-])", re.IGNORECASE)

    def find_mentions(self, text: str) -> list[tuple[str, str]]:
        """All (label, id) pairs whose name or alias appears in text, de-duplicated."""
        if not self._mention_forms:
            return []
        if self._mention_regex is None:
            self._mention_regex = self._build_mention_regex()
        lowered = {k.lower(): v for k, v in self._mention_forms.items()}
        found: dict[str, tuple[str, str]] = {}
        for match in self._mention_regex.finditer(text):
            hit = lowered.get(match.group(1).lower())
            if hit:
                found[hit[1]] = hit
        return list(found.values())

    def __len__(self) -> int:
        return len(self._records)
