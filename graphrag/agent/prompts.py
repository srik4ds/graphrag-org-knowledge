"""
All prompts in one place.

Keeping prompts out of the logic makes them easy to iterate on and to quote in the
project write-up ("prompts and agent instructions used").
Placeholders use str.format: {question}, {context}, ...
Literal JSON braces are doubled: {{ and }}.
"""

# --------------------------------------------------------------------------- #
# Q2  Router + entity linker
# --------------------------------------------------------------------------- #
ROUTER_PROMPT = """You are the query router for a question-answering system about the company Fintara:
its people, teams, projects, services, releases, decisions (ADRs), incidents, Jira tickets and tools.
Today's date is {today}.

Graph schema:
{schema}

Cypher templates you can choose from:
{templates}

Read the question and return ONLY a JSON object, no other text:
{{
  "mentions": [
    {{"text": "<phrase from the question>",
      "label": "<Person|Team|Project|Service|Tool|Release|Decision|Incident|Ticket>",
      "category": "<audit|infrastructure|data-platform|product, or null>",
      "temporal": "<latest, or null>"}}
  ],
  "template": "<one template name, or none>",
  "reason": "<one short sentence>"
}}

Rules:
1. List every specific entity the question refers to, including descriptions instead of names.
   "the last compliance audit" -> label Project, category audit, temporal latest.
   "the most recent incident" or "last week's outage" -> label Incident, temporal latest.
   "the next release" -> label Release, temporal latest.
   A decision described by its topic ("the decision to use X instead of Y") -> label Decision, text = the topic.
2. Put the template's anchor entity FIRST in the mentions list.
3. Choose the template whose description fits the question. Use "none" if no template fits.
4. If the question names no specific entity (for example a general "how do we..." question), return an empty mentions list.

Examples:
Question: Who approved ADR-007?
{{"mentions": [{{"text": "ADR-007", "label": "Decision", "category": null, "temporal": null}}], "template": "decision_details", "reason": "Approvals are relationships of one decision."}}

Question: Which tickets are blocking the next release?
{{"mentions": [{{"text": "the next release", "label": "Release", "category": null, "temporal": "latest"}}], "template": "release_blockers", "reason": "Blocking tickets are linked to a release."}}

Question: What is our policy for naming Kafka topics?
{{"mentions": [{{"text": "Kafka", "label": "Service", "category": null, "temporal": null}}], "template": "none", "reason": "Policy wording lives in documents, not in relationships."}}

Question: {question}
"""

# --------------------------------------------------------------------------- #
# Q5  Answer synthesis
# --------------------------------------------------------------------------- #
SYNTHESIS_PROMPT = """You answer questions about the company Fintara using ONLY the context below.

The context has two kinds of evidence:
- GRAPH FACTS tagged [G1], [G2], ... come from the knowledge graph. Trust them for structured data:
  owners, assignments, statuses, dates, dependencies and approvals.
- PASSAGES tagged [V1], [V2], ... come from wiki pages and Slack threads. Use them for explanations,
  reasons, procedures and narrative detail.

Rules:
1. Use only the context. Never add outside knowledge.
2. End every sentence with the tag(s) that support it, for example [G1] or [V2][G3].
3. If the question asks about open or current items, leave out items the context marks as Done or closed.
4. If graph facts and passages disagree, prefer the graph facts and mention the disagreement.
5. If the context does not contain the answer, reply with exactly: INSUFFICIENT_CONTEXT
6. Be concise: a short paragraph or a numbered list.

Question: {question}

Context:
{context}

Answer:"""

INSUFFICIENT_MARKER = "INSUFFICIENT_CONTEXT"

# --------------------------------------------------------------------------- #
# Q6  Grounding check (LLM judge)
# --------------------------------------------------------------------------- #
GROUNDING_PROMPT = """You are a strict fact-checker.

Split the ANSWER into atomic factual claims. For each claim decide whether it is fully supported
by the CONTEXT item(s) it cites. If a claim cites nothing, check it against the whole context.
A claim is unsupported if any part of it is missing from, or contradicts, the context.

Return ONLY a JSON object:
{{"claims": [{{"claim": "<text>", "citations": ["G1"], "supported": true, "note": "<short reason>"}}]}}

CONTEXT:
{context}

ANSWER:
{answer}
"""

# --------------------------------------------------------------------------- #
# Q3A fallback  Text2Cypher
# --------------------------------------------------------------------------- #
TEXT2CYPHER_PROMPT = """Write one read-only Cypher query for Neo4j that answers the question.

Schema:
{schema}

Entities already identified in the question (use their ids with {{id: '...'}}):
{entities}

Rules:
1. Read-only: MATCH, OPTIONAL MATCH, WHERE, WITH, RETURN, ORDER BY, LIMIT only.
2. Return names and properties (for example p.name), never whole nodes.
3. Add LIMIT 50.
4. Output only the Cypher query, no explanation.

Question: {question}
Cypher:"""

# --------------------------------------------------------------------------- #
# Q3B optional rerank
# --------------------------------------------------------------------------- #
RERANK_PROMPT = """Order the candidate passages by how useful they are for answering the question.
Return ONLY JSON: {{"order": [<candidate numbers, most useful first>]}}

Question: {question}

Candidates:
{candidates}
"""

# --------------------------------------------------------------------------- #
# Q7b  Refusal
# --------------------------------------------------------------------------- #
REFUSAL_MESSAGE = "I cannot verify this from our organizational records."
