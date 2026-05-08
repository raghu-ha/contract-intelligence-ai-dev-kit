# I Built a Production Contract Intelligence System with Databricks AI Dev Kit — Here's What "15 Minutes" Doesn't Tell You

*A hands-on walkthrough of 50+ MCP tools, a full medallion pipeline on unstructured data, and the honest parts most demos skip.*

---

There's a great article by the Hiflylabs team showing you can build a Databricks app in 15 minutes using the AI Dev Kit. It's a solid intro and worth reading.

But I wanted to know what happens when the input isn't a clean CSV.

So I took 20 real SEC contract PDFs — unstructured, no schema, no labels — and tried to build a fully governed contract intelligence system. One Claude Code session. Zero manual UI interactions.

This is what I found.

---

## What is the Databricks AI Dev Kit, exactly?

Before the walkthrough, a quick clarification — because this tool is genuinely easy to confuse with two other Databricks AI tools.

**Genie Code** is an AI agent that lives *inside* your Databricks workspace. It writes and runs code natively, with full Unity Catalog context and zero configuration. Think of it as your AI pair programmer inside the platform.

**Databricks MCP Server** exposes 4 managed servers (Genie Space, Vector Search, UC Functions, DBSQL) so that external editors like Claude Code or Cursor can *query* your existing lakehouse data.

**The AI Dev Kit is different from both.** It lives in your external editor — Claude Code, Cursor, Windsurf — and gives it genuine Databricks *construction* capability:

- **50+ MCP tools** that execute real Databricks REST API calls — create schemas, deploy pipelines, provision Vector Search endpoints, publish dashboards, deploy apps
- **19 Databricks skills** — markdown files encoding production patterns like Auto Loader, DLT streaming tables, SCD Type 2, CDC, model serving
- A Python core library for custom integrations
- Works alongside Genie Code and the MCP Server — they solve different layers of the same problem

The clearest way I can put it:

> *MCP Server connects you to your data. AI Dev Kit builds the platform that holds it.*

---

## The build: 20 SEC PDFs → production RAG system

Here's the full architecture I built in one session:

```
Volume (20 SEC PDFs)
    ↓ manage_volume_files
Bronze DLT layer (Auto Loader — raw PDF ingest)
    ↓ manage_pipeline
Silver DLT layer (clause extraction, DQ expectations)
    ↓ manage_pipeline
Gold DLT layer (risk scoring, aggregations)
    ↓
    ├── Vector Search endpoint + DELTA_SYNC index (managed embeddings)
    │       manage_vs_endpoint · manage_vs_index
    │
    ├── AI/BI Dashboard (live SQL — KPIs, contract types, jurisdictions)
    │       manage_dashboard
    │
    └── Streamlit RAG App (Llama 3.3 70B — exact page citations)
            manage_app

Unity Catalog governance across all layers
    manage_uc_objects · manage_uc_grants
```

**Numbers:** 2,497 clauses extracted. 99% avg confidence. 7 MCP tool categories. 0 UI clicks.

---

## Tool-by-tool: what each MCP call actually does

### 1. `manage_uc_objects` — Unity Catalog schema + tables

The first call I made. Created the full `workspace.sec_intelligence` catalog with Bronze, Silver, and Gold Delta table specs, all schema-defined. This took one natural language prompt:

> *"Create the sec_intelligence schema in the workspace catalog with three Delta tables: contracts_bronze (raw), contracts_silver (parsed clauses with confidence scores), and contracts_gold (aggregated risk insights). Apply appropriate table properties for DLT."*

What surprised me: the AI Dev Kit's UC skill already knew the correct table property patterns for DLT-managed tables. No iteration.

### 2. `manage_volume_files` — uploading PDFs to a Databricks Volume

This is the step most demos skip entirely — because they start with a CSV that's already in the lakehouse. For unstructured PDFs, you need to get them into a Volume first.

```
/Volumes/workspace/sec_intelligence/contracts_raw/
```

20 PDFs uploaded programmatically. The tool handles chunked upload and verifies completion.

### 3. `manage_pipeline` — the full DLT medallion architecture

This is where the 19 skills files earn their keep. I asked for a DLT pipeline with three layers and got production-quality Spark Declarative code on the first attempt — not toy examples.

**Bronze layer:** Auto Loader ingesting raw PDFs from the Volume with schema inference and file metadata.

**Silver layer:** The extraction logic — parsing contract clauses, identifying parties, governing law, clause type, and confidence score. DQ expectations applied:
```python
@dq_expectations(
    {"valid_confidence": "confidence_score >= 0.8"},
    "drop_on_failure"
)
```

**Gold layer:** Aggregated insights — contract counts by type, jurisdiction distribution, avg confidence, risk flags.

The pipeline was deployed via `manage_pipeline`, run triggered, and status polled — all within the session. One thing to note: pipeline runs take real time. Claude Code needed to be prompted to wait and check status before moving to the next step.

### 4. `manage_vs_endpoint` + `manage_vs_index` — Vector Search

Two separate tool calls. First creates the dedicated endpoint (`sec-intelligence-vs`), then creates a DELTA_SYNC index on the Silver clauses table using `databricks-bge-large-en` managed embeddings.

The DELTA_SYNC pattern means the index stays live as new clauses land in Silver — no manual re-indexing.

One friction point: the endpoint takes 3-5 minutes to reach ONLINE status. You need to explicitly prompt Claude Code to poll before indexing begins.

### 5. `manage_dashboard` — AI/BI Dashboard

A live dashboard with six components, all backed by real SQL datasets:
- Total Contracts counter
- Total Clauses counter  
- Avg Confidence % counter
- Contracts by Type bar chart
- Contracts by Governing Law bar chart
- Full document lineage table

No static data. Every number updates as new contracts flow through the pipeline.

### 6. `manage_app` — Streamlit RAG App

The deployed app has three tabs:

**Contract Q&A (RAG):** Semantic search over the Vector Search index, LLM synthesis via Llama 3.3 70B on Model Serving, with every answer returning the exact document name, clause text, and page number. This is the part that stopped me — asking "which contracts involve New York law?" and getting back exact clause text with source attribution, from PDFs I'd uploaded 20 minutes earlier.

**Contract Explorer:** Live filtered table from the Gold layer — filter by contract type, jurisdiction, risk flag.

**How This Was Built:** Architecture tab showing the full AI Dev Kit vs Genie Code comparison (useful for internal demos).

### 7. `manage_uc_grants` — permissions

The app runs under a service principal. UC grants needed:
- `USE_CATALOG` on workspace
- `USE_SCHEMA` on sec_intelligence
- `SELECT` on all three Delta tables
- `SELECT` on the Vector Search index

All granted programmatically. Full audit trail in Unity Catalog.

---

## Where it got hard (the honest section)

Most demo posts skip this. I'm including it because it's the most useful part.

**PDF extraction quality varies by format.** Older SEC filings from the late 1990s used different layout conventions. The Silver layer extraction logic needed prompt tuning for two contract batches where the clause boundaries weren't cleanly delimited.

**Vector Search endpoint startup time.** 3-5 minutes for ONLINE status. In an automated session, you need explicit polling logic — otherwise Claude Code moves to indexing against an endpoint that isn't ready and fails silently.

**Dashboard SQL join key mismatch.** The dashboard SQL referenced a join key between Silver and Gold that I'd named slightly differently during the DLT build. One manual fix in the dashboard SQL editor — the only UI interaction of the entire session.

**Llama 3.3 70B on SEC legal text.** I expected 85-90% confidence. Got 99%. Legal clause boundaries are clean and well-structured, which helps the extraction model significantly. Your results will vary with less structured documents.

---

## AI Dev Kit vs the 4 managed MCP servers: when to use what

I've now built with all three layers of Databricks' AI tooling:

| Tool | Use when | Don't use when |
|---|---|---|
| Genie Code | Inside workspace, daily data work, debugging | You're working in an external editor |
| Databricks MCP Server | External editor + need to query/explore existing data | You need to create new resources |
| AI Dev Kit | External editor + building new data products end-to-end | You just need to query existing data |

The full decision framework and architecture diagram are in my GitHub repo (link below).

---

## What I'd build next

The natural extension of this system is making it multi-tenant — different schemas per client, with row-level security in Unity Catalog controlling which service principal sees which contracts. The AI Dev Kit's `manage_uc_grants` tool makes this programmatically manageable at scale.

The other extension: adding a DLT CDC pipeline so that contract amendments automatically update the Silver layer and trigger Vector Search re-indexing. The CDC skill is already in the AI Dev Kit's 19 skills — I just haven't built it yet.

---

## Resources

- **GitHub repo** (full architecture + README): [github.com/raghu-ha/contract-intelligence-ai-dev-kit](#)
- **Databricks AI Dev Kit**: [github.com/databricks-solutions/ai-dev-kit](https://github.com/databricks-solutions/ai-dev-kit)
- **My LinkedIn series** (Genie Code → MCP Server → AI Dev Kit): [linkedin.com/in/raghu-ha](#)

---

*Raghu is an Associate Director / Solution Architect at Deloitte India specialising in Databricks, Azure data platforms, and agentic AI systems. He writes about data engineering and AI at the intersection of real delivery work.*

*Claps and responses welcome — especially if you've built something similar and hit different friction points.*
