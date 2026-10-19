"""Unit tests for cleaning (2B, 2C), entity resolution (3) and chunking (4B)."""

from graphrag.ingest.chunker import ParentChildChunker
from graphrag.ingest.cleaners import clean_slack_text, is_noise, strip_markdown
from graphrag.ingest.models import TextDocument
from graphrag.utils import token_len


# ---- 2C Slack -------------------------------------------------------------- #
def test_slack_user_ids_are_resolved(registry):
    raw = "Hey <@U12345XYZ>, check **Project Triton** with <@U98765ABC>."
    assert clean_slack_text(raw, registry) == "Hey Alex Chen, check Project Triton with Sarah Jenkins."


def test_unknown_slack_id_is_marked(registry):
    assert "Unknown_User_U00000000" in clean_slack_text("ping <@U00000000>", registry)


def test_bot_and_join_messages_are_noise():
    assert is_noise({"subtype": "channel_join", "text": "x"})
    assert is_noise({"bot_id": "B1", "text": "x"})
    assert not is_noise({"user": "U1", "text": "real message"})


# ---- 2B Markdown ------------------------------------------------------------- #
def test_strip_markdown_keeps_words():
    md = "# Title\n\n**Bold** and [a link](http://x) and `code` &amp; more"
    assert strip_markdown(md) == "Title\n\nBold and a link and code & more"


# ---- 3 Entity resolver ------------------------------------------------------------ #
def test_all_name_variants_resolve_to_one_person(registry):
    for variant in ["Sarah Jenkins", "S. Jenkins", "sjenkins", "U98765ABC", "sarah.jenkins@fintara.example"]:
        assert registry.resolve(variant, "Person") == "p_sjenkins", variant


def test_canonicalize_text_expands_abbreviations(registry):
    assert registry.canonicalize_text("authored by S. Jenkins") == "authored by Sarah Jenkins"


def test_find_mentions_links_text_to_entities(registry):
    found = set(registry.find_mentions("Alex Chen paged Tom Brooks about ledger-db and TRI-12."))
    assert {("Person", "p_achen"), ("Person", "p_tbrooks"), ("Service", "svc_ledger_db"), ("Ticket", "TRI-12")} <= found


def test_short_aliases_are_not_used_for_mentions(registry):
    # "Raj" is a 3-letter alias: too short to search for safely in free text
    assert ("Person", "p_rmalhotra") not in registry.find_mentions("the raj palace")


# ---- 4B Chunking ------------------------------------------------------------------ #
def test_children_respect_token_limit(prepared, settings):
    # children carry a title prefix, so allow a small margin
    assert all(token_len(c.text) <= settings.child_chunk_tokens + 40 for c in prepared.children)


def test_every_child_points_to_an_existing_parent(prepared):
    parent_ids = {p.id for p in prepared.parents}
    assert all(c.parent_id in parent_ids for c in prepared.children)


def test_slack_thread_is_one_parent():
    doc = TextDocument("slack_x", "Slack #x thread", "slack", "comms/x.json", "Alex Chen: hi\nTom Brooks: hello")
    parents, children = ParentChildChunker(1024, 256, 32).split(doc)
    assert len(parents) == 1 and len(children) == 1


def test_long_text_is_split_into_several_parents_and_children():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(20))
    doc = TextDocument("wiki_long", "Long page", "wiki", "wiki/long.md", text)
    parents, children = ParentChildChunker(1024, 256, 32).split(doc)
    assert len(parents) >= 2 and len(children) > len(parents)
