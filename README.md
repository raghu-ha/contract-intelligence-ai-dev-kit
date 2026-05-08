# Contract Intelligence — Databricks AI Dev Kit

> A production-grade contract intelligence system built end-to-end using the **Databricks AI Dev Kit** (50+ MCP tools · 19 Databricks skills) in a single Claude Code session.  
> **0 times the Databricks UI was opened.**

---

## What this builds

A fully governed RAG system over 20 real SEC contract PDFs:

| Layer | What it does | MCP tool used |
|---|---|---|
| Databricks Volume | Stores 20 raw SEC contract PDFs | `manage_volume_files` |
| Bronze (DLT) | Auto Loader ingests raw PDFs | `manage_pipeline` |
| Silver (DLT) | Parses clauses, applies DQ expectations | `manage_pipeline` |
| Gold (DLT) | Risk scoring + aggregated contract insights | `manage_pipeline` |
| Vector Search | DELTA_SYNC index with managed embeddings | `manage_vs_index` |
| AI/BI Dashboard | Live SQL — KPIs, contract types, jurisdictions | `manage_dashboard` |
| Streamlit RAG App | LLM Q&A with exact document + page citations | `manage_app` |
| UC Permissions | Grants to app service principal | `manage_uc_grants` |

**Numbers:**
- ✅ 20 SEC contracts processed
- ✅ 2,497 contract clauses extracted and indexed
- ✅ 99% avg extraction confidence
- ✅ 7 MCP tool categories used
- ✅ 0 manual Databricks UI interactions

---

## Architecture

```
Claude Code + AI Dev Kit (50+ MCP tools · 19 Databricks skills)
│
├── manage_uc_objects   →  workspace.sec_intelligence schema + Delta tables
├── manage_volume_files →  /Volumes/workspace/sec_intelligence/contracts_raw/
│
├── manage_pipeline     →  DLT Pipeline (medallion architecture)
│                              Bronze  — Auto Loader, raw PDF ingest
│                              Silver  — clause extraction, DQ expectations
│                              Gold    — risk scoring, aggregations
│
├── manage_vs_endpoint  →  Vector Search endpoint (sec-intelligence-vs)
├── manage_vs_index     →  DELTA_SYNC index, databricks-bge-large-en embeddings
│
├── manage_dashboard    →  AI/BI Dashboard (live SQL, 3 KPIs, 2 charts, lineage table)
├── manage_app          →  Streamlit RAG App (3 tabs: Q&A · Explorer · Architecture)
│
└── manage_uc_grants    →  USE_CATALOG · USE_SCHEMA · SELECT on all objects
                            granted to app service principal
```

---

## AI Dev Kit vs Genie Code vs Databricks MCP Server

A question I get asked often. Here's the honest breakdown:

| Tool | Lives | Builds? | Queries? | Best for |
|---|---|---|---|---|
| **Genie Code** | Inside Databricks workspace | ✅ Writes & runs code | ✅ Native UC context | Daily data work inside Databricks |
| **Databricks MCP Server** (4 managed) | External editor | ❌ | ✅ Genie, Vector Search, DBSQL, UC Functions | Connecting external tools to your lakehouse |
| **AI Dev Kit** | External editor (Claude Code, Cursor) | ✅ Full platform provisioning | ✅ | Building new data products end-to-end |

**The key insight:** MCP Server accesses your lakehouse. AI Dev Kit *builds* it.

These are complementary, not competing. I've posted about all three:

- 📌 Post 1: [Genie Code — Databricks Observability Platform](#) *(link your LinkedIn post)*
- 📌 Post 2: [Databricks MCP Server](#) *(link your LinkedIn post)*
- 📌 Post 3: [AI Dev Kit — Contract Intelligence](#) *(link your LinkedIn post)*

---

## Prerequisites

- Databricks workspace with serverless compute enabled
- Claude Code installed ([docs.anthropic.com](https://docs.anthropic.com))
- Databricks AI Dev Kit: `pip install databricks-ai-dev-kit`
- Python 3.12+

---

## Setup

```bash
# Clone this repo
git clone https://github.com/raghu-ha/contract-intelligence-ai-dev-kit

# Install dependencies
pip install -r requirements.txt

# Configure Databricks connection
databricks configure

# Launch Claude Code and point it at this repo
claude
```

Once Claude Code is running, the AI Dev Kit MCP tools are available. You can then run prompts like:

```
"Create the full sec_intelligence schema with Bronze, Silver, and Gold 
Delta tables in Unity Catalog, upload the PDFs from /data/contracts/ 
to a Databricks Volume, and build a DLT pipeline with Auto Loader 
to process them through the medallion architecture."
```

---

## What I learned (the honest section)

**What worked well:**
- `manage_pipeline` handled the full DLT spec including `@dq_expectations` with zero iteration
- `manage_vs_index` correctly configured the DELTA_SYNC pattern — I expected to debug this
- UC grants to the app service principal worked first try via `manage_uc_grants`

**What required iteration:**
- PDF extraction quality varies significantly by contract format — some older SEC filings needed prompt tuning in the Silver transformation logic
- The Vector Search endpoint takes 3-5 minutes to become ONLINE after creation — Claude Code needed to be prompted to wait and poll status before indexing
- Dashboard dataset SQL needed one manual adjustment for a join key mismatch between Silver and Gold schemas

**What surprised me:**
- The 19 Databricks skills files (Auto Loader, DLT patterns, SCD Type 2 etc.) made a bigger difference than expected — Claude Code generated production-quality DLT code first try, not toy examples
- Llama 3.3 70B via Model Serving gave 99% extraction confidence on SEC legal text — I expected 85-90%

---

## Related

- 📖 Full technical walkthrough: [Medium post](#) *(add your Medium link)*
- 🔧 Databricks AI Dev Kit repo: [github.com/databricks-solutions/ai-dev-kit](https://github.com/databricks-solutions/ai-dev-kit)
- 📊 More projects: [github.com/raghu-ha](https://github.com/raghu-ha)

---

## About

Built by **Raghu** — Associate Director / Solution Architect at Deloitte India, specialising in Databricks, Azure data platforms, and agentic AI systems.

[LinkedIn](https://www.linkedin.com/in/raghu-ha) · [GitHub](https://github.com/raghu-ha)
