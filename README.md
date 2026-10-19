# GraphRAG for Organizational Knowledge

Answer multi-hop questions about people, projects, services, decisions and incidents by combining a
**knowledge graph** (relationships) with **hybrid vector search** (prose), and compare it against a
plain vector-RAG baseline on 10 test questions.

> **One-liner:** My RAG app helps engineering managers and tech leads answer multi-hop questions about
> people, projects, dependencies and decisions from 19 Notion wiki pages, 41 Jira issues and 11 Slack
> threads of a fictional fintech (Fintara), in a Streamlit chat, with 90% faithfulness, 85% answer
> relevance and under 8 s p95 latency.

![Data flow](docs/graphrag_dataflow_v3.png)

Box-by-box notes: [docs/graphrag_design_notes_v3.png](docs/graphrag_design_notes_v3.png)

---

## 1. Framework (Week 2 handout)

| # | Field | Choice |
|---|---|---|
| 1 | Use case | Multi-hop org questions ("who worked on the last audit and what tools do they use now?") for managers and tech leads, in a Streamlit chat |
| 2 | Corpus | Synthetic company Fintara: 12 people, 5 teams, 19 Notion-style wiki pages (projects, services, ADRs, postmortems, runbook), 41 Jira issues, 11 Slack threads. English. Owners: wiki = page author, Jira = assignee, directory = HR |
| 3 | Ingestion + cleaning | Markdown stripped, HTML entities decoded, Slack `<@U123>` ids resolved to names, bot and join messages dropped, every name variant mapped to one canonical id |
| 4 | Ingestion + freshness | `python ingest.py` is idempotent (MERGE), so it can be scheduled (for example every 30 minutes); demo runs on demand |
| 5 | Chunking + embedding | Parent 1024 tokens / child 256 tokens with 32 overlap; Slack thread = one parent; Nebius `BAAI/bge-en-icl` embeddings (configurable) |
| 6 | Retrieve | Neo4j only: graph (Cypher templates, Text2Cypher fallback) + vector index (dense top-20) + full-text index (BM25 top-20), merged with RRF, top-5 children swapped for parents |

## 2. Project layout (mapped to diagram boxes)

```
graphrag-org-knowledge/
├── app.py                     Q1      Streamlit chat (GraphRAG / Vector-only / Compare both)
├── ingest.py                  1A-6B   build graph + chunk store
├── ask.py                             one question from the terminal (--debug shows Cypher, context)
├── evaluate.py                E1-E4   10 questions x 2 modes -> results/eval_report_vN.md
├── check_setup.py                     verifies Nebius + Neo4j credentials
├── data/raw/                  1A-1D   directory_map.json, wiki/*.md, issues/*.json, comms/*.json
├── eval/queries.json          E1      10 questions with gold answers and must-include facts
├── graphrag/
│   ├── config.py                      every setting, read from .env
│   ├── clients.py                     ChatOpenAI / OpenAIEmbeddings (Nebius), Neo4jGraph
│   ├── schema.py                      labels, relationships, indexes, schema text for the LLM
│   ├── utils.py                       token counting, JSON parsing, Lucene escaping, timers
│   ├── ingest/
│   │   ├── loaders.py         1A-1D   read files
│   │   ├── cleaners.py        2A-2C   markdown + Slack cleaning, thread grouping
│   │   ├── entity_resolver.py 3       one canonical id per entity, mention detection
│   │   ├── graph_extractors.py 4A     records -> nodes and edges
│   │   ├── graph_writer.py    4A->6A  MERGE into Neo4j
│   │   ├── chunker.py         4B      parent-child chunking
│   │   ├── vector_writer.py   5B->6B  embed children, write chunks, MENTIONS links
│   │   └── pipeline.py                runs the steps in order
│   ├── retrieval/
│   │   ├── entity_linker.py   Q2      phrases -> node ids (latest-by-date or fuzzy full-text)
│   │   ├── cypher_templates.py Q3A    9 parameterized multi-hop queries
│   │   ├── graph_retriever.py Q3A     template -> Text2Cypher -> neighbourhood fallback
│   │   ├── text2cypher.py     Q3A     LLM-written Cypher with a read-only guard
│   │   ├── rrf.py             Q3B     Reciprocal Rank Fusion
│   │   └── hybrid_retriever.py Q3B    dense + BM25 + RRF (+ optional rerank) -> parents
│   ├── agent/
│   │   ├── state.py                   LangGraph state (reducers for parallel writes)
│   │   ├── prompts.py                 every prompt in one place
│   │   ├── nodes.py           Q2-Q7   one method per box
│   │   └── builder.py                 StateGraph wiring + ask()
│   └── evaluation/
│       ├── judges.py          E3      LLM judge + fact recall
│       └── runner.py          E2-E4   runs both modes, writes CSV + Markdown report
├── tests/                             49 offline tests (no Neo4j or Nebius needed)
└── docs/                              diagram and design notes
```

## 3. Setup

### 3.1 Accounts (about 20 minutes)

1. **Nebius:** create an API key. In the model list, confirm a chat model (default
   `meta-llama/Llama-3.3-70B-Instruct`) and an embedding model (default `BAAI/bge-en-icl`) are available.
2. **Neo4j AuraDB Free:** create an instance at console.neo4j.io and download the credentials file
   (URI, username, password). Free instances pause after inactivity; resume them from the console.

### 3.2 Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in NEBIUS_API_KEY, NEO4J_URI, NEO4J_PASSWORD
```

### 3.3 Run

```bash
python -m pytest -q                # 49 offline tests, about 5 seconds
python check_setup.py              # Nebius chat, Nebius embeddings, Neo4j version
python ingest.py --dry-run         # parse + chunk only: prints counts, no API calls
python ingest.py --reset           # load graph + embeddings into Neo4j (about 1 minute)
python ask.py "If Alex Chen leaves the company next month, which product releases are at risk?" --debug
streamlit run app.py               # chat UI at http://localhost:8501
python evaluate.py                 # 10 questions x 2 modes -> results/eval_report_v1.md
```

### 3.4 Explore the graph in Neo4j Browser

```cypher
MATCH (p:Person)-[r:WORKED_ON]->(pr:Project)-[:USES]->(t:Tool) RETURN p, r, pr, t
```

### 3.5 No Nebius credits?

| # | Option | .env settings | Notes |
|---|---|---|---|
| 1 | Offline mode (no API at all) | `LLM_PROVIDER=offline` | Rule-based router, extractive answers, hashing embeddings. Graph side (Neo4j, Cypher, RRF) is unchanged |
| 2 | Local Ollama (free) | `LLM_PROVIDER=nebius`, `NEBIUS_BASE_URL=http://localhost:11434/v1/`, `NEBIUS_API_KEY=ollama`, `LLM_MODEL=llama3.1:8b`, `EMBEDDING_MODEL=nomic-embed-text` | Run `ollama pull llama3.1:8b` and `ollama pull nomic-embed-text` first |
| 3 | Any OpenAI-compatible key (OpenAI, Groq, Together) | set `NEBIUS_BASE_URL`, `NEBIUS_API_KEY`, `LLM_MODEL`, `EMBEDDING_MODEL` | Groq has no embeddings endpoint, so pair it with another provider |

After switching provider or embedding model, re-run `python ingest.py --reset` (vector size changes).

## 4. The 10 evaluation questions

| # | Id | Question | Shape | Expected winner |
|---|---|---|---|---|
| 1 | Q01 | Who worked on the last compliance audit, and what tools are used on the project each of them moved to next? | multi-hop + temporal | GraphRAG |
| 2 | Q02 | What API security decisions were made by the team that owns the service that failed in the most recent incident? | 3 hops | GraphRAG |
| 3 | Q03 | If Alex Chen leaves the company next month, which product releases are at risk? | dependency chain | GraphRAG |
| 4 | Q04 | Who approved the decision to use Snowpipe Streaming instead of Kafka Connect, and which projects does it affect? | relationship lookup | Tie |
| 5 | Q05 | Which open tickets are blocking the Triton GA release, and who is each one assigned to? | structured filter | GraphRAG |
| 6 | Q06 | Which tools has Linh Nguyen used across all of her projects? | 2-hop aggregation | GraphRAG |
| 7 | Q07 | Why did the data team choose Snowpipe Streaming over Kafka Connect? | rationale in prose | Vector |
| 8 | Q08 | What was the root cause of the ledger-db outage in October 2026? | narrative in prose | Vector |
| 9 | Q09 | What is the escalation process for a SEV1 on payments-api? | procedure in prose | Vector |
| 10 | Q10 | Who has the most open tickets on Project Atlas, and what are they? | counting | GraphRAG |

Gold answers and must-include facts are in `eval/queries.json`. `tests/test_gold_answers.py` proves
every graph-type gold answer is derivable from the data.

## 5. Key design decisions

| # | Decision | Why |
|---|---|---|
| 1 | One Neo4j database for graph, vectors and BM25 | Chunks link to graph nodes (`PART_OF`, `MENTIONS`); one connection; AuraDB Free is enough |
| 2 | Cypher templates first, Text2Cypher second | Templates are reliable, fast and read-only; the LLM only picks a name and an entity |
| 3 | LLM in the router | Resolves descriptions ("the last compliance audit") and typos to node ids |
| 4 | Entity resolver at ingest | One node per real person; also normalizes names in text so BM25 matches |
| 5 | Parent-child chunks | Small children match precisely; parents give the LLM context |
| 6 | RRF instead of score blending | Dense and BM25 scores are on different scales; RRF uses ranks: `1/(60 + dense_rank) + 1/(60 + bm25_rank)` |
| 7 | Synthesis, then grounding check | Claims can only be checked once a draft exists; Q4 refuses early when nothing is retrieved |
| 8 | Baseline = same pipeline with the graph switched off | Same LLM and prompts, so differences come from the graph |

## 6. Troubleshooting

| # | Symptom | Fix |
|---|---|---|
| 1 | `check_setup.py` fails on the chat model | Model name not available in your Nebius account: change `LLM_MODEL` |
| 2 | Embeddings error mentioning tokens or input type | Keep `check_embedding_ctx_length=False` (already set in `clients.py`) |
| 3 | `There is no such vector schema index` | Run `python ingest.py --reset` so the index is created with the right dimension |
| 4 | Neo4j `ServiceUnavailable` | AuraDB Free instance is paused: resume it in the console |
| 5 | Too many refusals | Lower `GROUNDING_THRESHOLD` (for example 0.7) or try a larger `LLM_MODEL` |
| 6 | "last audit" picks the wrong one | Set `TODAY=2026-10-19` in `.env` (the synthetic data is dated October 2026) |
