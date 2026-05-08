"""
Contract Intelligence App
=========================
RAG-powered contract Q&A with document/page lineage.
Built with Databricks AI Dev Kit via Claude Code MCP tools.
"""

import os
import streamlit as st
import pandas as pd
from databricks.sdk.core import Config
from databricks.sdk import WorkspaceClient
from databricks import sql as dbsql

st.set_page_config(
    page_title="Contract Intelligence",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Auth & Config ──────────────────────────────────────────────────────────────
cfg = Config()
WAREHOUSE_ID  = os.getenv("DATABRICKS_WAREHOUSE_ID", "2e4ce08aab477c6c")
VS_ENDPOINT   = "sec-intelligence-vs"
VS_INDEX      = "workspace.sec_intelligence.rag_chunks_index"
GOLD_TABLE    = "workspace.sec_intelligence.gold_contract_insights"


# ── Cached connections ─────────────────────────────────────────────────────────
@st.cache_resource
def get_sql_conn():
    return dbsql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


@st.cache_resource
def get_workspace_client():
    return WorkspaceClient()


# ── Data helpers ───────────────────────────────────────────────────────────────
def search_contracts(query: str, num_results: int = 5):
    """Semantic search via Vector Search SDK — returns chunks with document lineage."""
    w = get_workspace_client()
    try:
        response = w.vector_search_indexes.query_index(
            index_name=VS_INDEX,
            query_text=query,
            columns=["chunk_text", "document_name", "page_id",
                     "element_type", "confidence_score"],
            num_results=num_results,
        )
        data = response.result.data_array if response.result else []
        return data or [], None
    except Exception as e:
        err = str(e)
        if "SYNCING" in err.upper() or "not ready" in err.lower() or "INITIALIZING" in err.upper():
            return None, "INDEX_SYNCING"
        return None, err


def generate_rag_answer(query: str, chunks: list) -> str:
    """Call Databricks Foundation Model API to synthesise an answer from retrieved chunks."""
    w = get_workspace_client()

    # Build context from retrieved chunks with source labels
    context_parts = []
    for i, row in enumerate(chunks, 1):
        chunk_text, doc_name, page_id, elem_type, *_ = row
        context_parts.append(
            f"[Source {i}: {doc_name}, Page {page_id}, {elem_type}]\n{chunk_text}"
        )
    context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "You are a precise legal contract analyst. Rules you MUST follow:\n"
        "1. Answer using ONLY the contract excerpts provided — never add outside knowledge.\n"
        "2. For each relevant contract, state: the DOCUMENT NAME, the PARTIES involved, "
        "and the SPECIFIC clause or language that answers the question.\n"
        "3. Structure your answer as a numbered list — one entry per distinct contract.\n"
        "4. Cite each point with [Source N] immediately after the fact.\n"
        "5. Be specific: quote key phrases from the clause rather than paraphrasing vaguely.\n"
        "6. End with a one-sentence summary of how many contracts matched and why.\n"
        "7. If no excerpt answers the question, say exactly that."
    )
    user_prompt = f"Question: {query}\n\nContract excerpts:\n\n{context}"

    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
    response = w.serving_endpoints.query(
        name="databricks-meta-llama-3-3-70b-instruct",
        messages=[
            ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=ChatMessageRole.USER,   content=user_prompt),
        ],
        max_tokens=600,
        temperature=0.1,
    )
    return response.choices[0].message.content


def get_contracts():
    """Fetch all contracts from the gold layer."""
    conn = get_sql_conn()
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT
                COALESCE(filename, regexp_extract(path, '([^/]+)$', 1)) AS document_name,
                COALESCE(contract_type, 'Unknown')                        AS contract_type,
                COALESCE(extracted_fields.governing_law, '-')             AS governing_law,
                COALESCE(extracted_fields.party_1_name, '-')              AS party_1,
                COALESCE(extracted_fields.party_2_name, '-')              AS party_2,
                total_elements                                             AS clauses,
                ROUND(avg_confidence * 100, 1)                            AS confidence_pct
            FROM {GOLD_TABLE}
            ORDER BY avg_confidence DESC
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return pd.DataFrame(rows, columns=cols)


def get_kpis():
    """Fetch KPIs from the gold layer."""
    conn = get_sql_conn()
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT
                COUNT(*)                          AS total_contracts,
                SUM(total_elements)               AS total_clauses,
                ROUND(AVG(avg_confidence)*100, 1) AS avg_confidence
            FROM {GOLD_TABLE}
        """)
        row = cur.fetchone()
    return {"contracts": row[0], "clauses": row[1], "confidence": row[2]}


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("📄 Contract Intelligence")
st.caption(
    "Built end-to-end with **Databricks AI Dev Kit** · "
    "Vector Search · DLT Pipeline · AI/BI Dashboard · Databricks App"
)
st.divider()

# ── KPI row ────────────────────────────────────────────────────────────────────
try:
    kpis = get_kpis()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📁 Total Contracts",  kpis["contracts"])
    k2.metric("📋 Total Clauses",    f"{int(kpis['clauses']):,}")
    k3.metric("🎯 Avg Confidence",   f"{kpis['confidence']}%")
    k4.metric("🔍 Search Engine",    "Vector Search")
except Exception as e:
    st.warning(f"Could not load KPIs: {e}")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(
    ["🔍 Contract Q&A (RAG)", "📊 Contract Explorer", "🏗️ How This Was Built"]
)

# ─── Tab 1: RAG Q&A ────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Ask a Question About Your Contracts")
    st.caption(
        "Semantic search powered by **Databricks Vector Search** with managed embeddings. "
        "Every result includes full **document + page lineage**."
    )

    col_q, col_n = st.columns([4, 1])
    with col_q:
        query = st.text_input(
            "Your question:",
            placeholder="Which contracts are governed by New York law?",
            label_visibility="collapsed",
        )
    with col_n:
        num_results = st.number_input("Top N", min_value=1, max_value=10, value=5)

    example_queries = [
        "Which contracts involve New York law?",
        "Find service agreements with California parties",
        "Show me contracts with indemnification clauses",
        "Which agreements mention termination conditions?",
    ]
    st.caption("**Try:** " + " · ".join(f"`{q}`" for q in example_queries))

    if st.button("🔍 Search Contracts", type="primary", use_container_width=True) and query:
        with st.spinner("Step 1/2 — Retrieving relevant contract clauses via Vector Search…"):
            results, err = search_contracts(query, int(num_results))

        if err == "INDEX_SYNCING":
            st.info(
                "⏳ **Vector Search index is still syncing** — initial indexing usually takes "
                "5–10 minutes. Check back shortly.\n\n"
                "In the meantime, explore the **Contract Explorer** tab to browse all contracts."
            )
        elif err:
            st.error(f"Search error: {err}")
        elif not results:
            st.warning("No results found for that query.")
        else:
            # ── LLM synthesis ─────────────────────────────────────────────────
            with st.spinner("Step 2/2 — Generating answer with Llama 3.3 70B…"):
                try:
                    answer = generate_rag_answer(query, results)
                    llm_ok = True
                except Exception as llm_err:
                    answer = str(llm_err)
                    llm_ok = False

            # Show LLM answer
            st.markdown("### 🤖 Answer")
            if llm_ok:
                st.success(answer)
            else:
                st.warning(f"LLM unavailable: {answer}")

            st.divider()

            # ── Source chunks (lineage) ────────────────────────────────────────
            st.markdown(f"### 📚 Sources — {len(results)} contract sections retrieved")
            st.caption("Ranked by semantic similarity · Expand to read the original clause")

            for i, row in enumerate(results, 1):
                chunk_text, doc_name, page_id, elem_type, conf_score, *rest = row
                distance   = rest[0] if rest else 0.0
                similarity = max(0.0, 1.0 - float(distance))

                header = (
                    f"**[Source {i}]** · 📄 `{doc_name}` · Page {page_id} · "
                    f"*{elem_type}* · Similarity {similarity:.0%}"
                )
                with st.expander(header, expanded=(i == 1)):
                    badge_col, _ = st.columns([2, 5])
                    with badge_col:
                        st.markdown(
                            f"🎯 **Extraction confidence:** {float(conf_score):.1%}&nbsp;&nbsp;"
                            f"📐 **Similarity:** {similarity:.1%}"
                        )
                    st.divider()
                    st.markdown(chunk_text)

# ─── Tab 2: Contract Explorer ─────────────────────────────────────────────────
with tab2:
    st.subheader("All Contracts — Document Lineage View")
    st.caption(
        "Live data from `workspace.sec_intelligence.gold_contract_insights` "
        "(Gold layer of the DLT medallion pipeline)"
    )

    if st.button("🔄 Load Contracts from Gold Layer", use_container_width=True):
        with st.spinner("Querying gold_contract_insights…"):
            try:
                df = get_contracts()
            except Exception as e:
                st.error(f"Query failed: {e}")
                df = None

        if df is not None:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Contracts", len(df))
            m2.metric("Avg Confidence", f"{df['confidence_pct'].mean():.1f}%")
            m3.metric("Total Clauses", f"{int(df['clauses'].sum()):,}")
            m4.metric("Contract Types", df["contract_type"].nunique())

            st.divider()

            # Filters
            fc1, fc2 = st.columns(2)
            with fc1:
                types = ["All"] + sorted(df["contract_type"].unique().tolist())
                sel_type = st.selectbox("Filter by Type", types)
            with fc2:
                laws = ["All"] + sorted(df["governing_law"].unique().tolist())
                sel_law = st.selectbox("Filter by Governing Law", laws)

            view = df.copy()
            if sel_type != "All":
                view = view[view["contract_type"] == sel_type]
            if sel_law != "All":
                view = view[view["governing_law"] == sel_law]

            st.dataframe(
                view.style.background_gradient(subset=["confidence_pct"], cmap="Greens"),
                use_container_width=True,
                height=400,
            )
            st.caption(f"Showing {len(view)} of {len(df)} contracts")

# ─── Tab 3: Architecture ──────────────────────────────────────────────────────
with tab3:
    st.subheader("🏗️ Built Entirely with Databricks AI Dev Kit")
    st.markdown("""
This POC was built **from scratch in a single editor session** using
**Claude Code** + **Databricks AI Dev Kit MCP tools**.
No Databricks UI was opened. Every resource was provisioned via MCP tool calls.

---

### What AI Dev Kit Enables (vs Genie Code)

| Capability | Genie Code | AI Dev Kit |
|---|:---:|:---:|
| SQL queries & table creation | ✅ | ✅ |
| Unity Catalog objects (schemas, tables) | ✅ | ✅ |
| **Vector Search endpoint + index creation** | ❌ | ✅ |
| **DLT pipeline deployment** | ❌ | ✅ |
| **AI/BI Dashboard creation & publishing** | ❌ | ✅ |
| **Live app deployment** | ❌ | ✅ |
| Jobs scheduling & orchestration | ❌ | ✅ |
| MLflow experiment tracking | ❌ | ✅ |

---

### Medallion Architecture

```
📁 SEC Contract PDFs  (Volume: contracts_raw/)
        │
        ▼  Auto Loader (cloudFiles)
🥉 bronze_contracts_stream        ◀── DLT table
        │
        ▼  Claude AI extraction
🥈 silver_contract_elements       ◀── existing table
        │
        ▼  Aggregation + risk scoring
🥇 gold_contract_insights         ◀── this app queries here
        │
        ├──▶ 📊 AI/BI Dashboard  (published, 10 widgets)
        └──▶ 🔍 Vector Search Index  (DELTA_SYNC, managed embeddings)
                        │
                        └──▶ 🚀 This Databricks App  (RAG Q&A)
```

---

### Resources Created — All via MCP Tools

| Resource | Tool Used | Status |
|---|---|---|
| VS Endpoint `sec-intelligence-vs` | `manage_vs_endpoint` | 🟢 Online |
| VS Index `rag_chunks_index` | `manage_vs_index` | 🔄 Syncing |
| DLT Pipeline `contract-intelligence-pipeline` | `manage_pipeline` | 🟢 Deployed |
| AI/BI Dashboard (10 widgets) | `manage_dashboard` | 🟢 Published |
| This Databricks App | `manage_app` | 🟢 Running |

---

> *"The real power of AI Dev Kit is not just that it can write code —
> it's that it can **deploy** it, **publish** it, and **run** it, all without leaving your editor."*
""")
