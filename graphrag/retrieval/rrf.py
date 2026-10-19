"""
Reciprocal Rank Fusion (RRF), used inside box Q3B.

Dense (cosine) and BM25 scores live on different scales, so they cannot be added.
RRF ignores the raw scores and uses only each item's RANK in each list:

    RRF(item) = 1/(k + dense_rank) + 1/(k + bm25_rank)        k = 60 by default

A term is 0 when the item is missing from that list. Items that both methods agree
on rise to the top.

Worked example (k = 60):
    chunk A: dense #1, BM25 #3  -> 1/61 + 1/63 = 0.0323
    chunk C: dense #4, BM25 #1  -> 1/64 + 1/61 = 0.0320
    chunk B: dense #2 only      -> 1/62        = 0.0161
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FusedItem:
    id: str
    score: float
    ranks: dict[str, int] = field(default_factory=dict)   # e.g. {"dense": 1, "bm25": 3}


def reciprocal_rank_fusion(ranked_lists: dict[str, list[str]], k: int = 60) -> list[FusedItem]:
    """
    ranked_lists: {"dense": [id1, id2, ...], "bm25": [id3, id1, ...]}, best first.
    Returns items sorted by fused score, best first.
    """
    fused: dict[str, FusedItem] = {}
    for list_name, ids in ranked_lists.items():
        for rank, item_id in enumerate(ids, start=1):          # ranks start at 1
            item = fused.setdefault(item_id, FusedItem(item_id, 0.0))
            item.score += 1.0 / (k + rank)
            item.ranks[list_name] = rank
    return sorted(fused.values(), key=lambda it: it.score, reverse=True)
