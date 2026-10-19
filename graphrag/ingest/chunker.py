"""
Box 4B: parent-child chunking.

Why two sizes?
    Small chunks (children, ~256 tokens) give sharp embeddings, so search is precise.
    Large chunks (parents, ~1024 tokens) give the LLM enough surrounding context.
Search runs on children; the LLM receives each matching child's parent.

Slack threads are short, so one thread = one parent (split only if it is longer
than the parent size).
"""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from graphrag.ingest.entity_resolver import EntityRegistry
from graphrag.ingest.models import ChildChunk, ParentChunk, TextDocument
from graphrag.utils import token_len

# Split on paragraph, then line, then sentence, then word boundaries
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


class ParentChildChunker:
    def __init__(self, parent_tokens: int = 1024, child_tokens: int = 256, child_overlap: int = 32,
                 registry: EntityRegistry | None = None) -> None:
        # Both splitters measure length in tokens (token_len), not characters
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_tokens, chunk_overlap=0, length_function=token_len, separators=_SEPARATORS)
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_tokens, chunk_overlap=child_overlap, length_function=token_len, separators=_SEPARATORS)
        self.parent_tokens = parent_tokens
        self.registry = registry

    def split(self, doc: TextDocument) -> tuple[list[ParentChunk], list[ChildChunk]]:
        """Return (parents, children) for one document."""
        if doc.source == "slack" and token_len(doc.text) <= self.parent_tokens:
            parent_texts = [doc.text]                       # one thread = one parent
        else:
            parent_texts = self.parent_splitter.split_text(doc.text)

        parents: list[ParentChunk] = []
        children: list[ChildChunk] = []
        for p_idx, p_text in enumerate(parent_texts):
            parent_id = f"{doc.doc_id}::p{p_idx}"
            parents.append(ParentChunk(id=parent_id, doc_id=doc.doc_id, text=p_text, position=p_idx))

            for c_idx, c_text in enumerate(self.child_splitter.split_text(p_text)):
                # Prefix each child with the document title. The title often carries the
                # key entity ("ADR-005: Snowpipe Streaming ...") that the paragraph omits.
                text = c_text if c_idx == 0 else f"{doc.title}\n{c_text}"
                mentions = self.registry.find_mentions(text) if self.registry else []
                children.append(ChildChunk(
                    id=f"{parent_id}::c{c_idx}", parent_id=parent_id, doc_id=doc.doc_id,
                    text=text, position=c_idx, mentions=mentions))
        return parents, children

    def split_all(self, docs: list[TextDocument]) -> tuple[list[ParentChunk], list[ChildChunk]]:
        all_parents, all_children = [], []
        for doc in docs:
            p, c = self.split(doc)
            all_parents.extend(p)
            all_children.extend(c)
        return all_parents, all_children
