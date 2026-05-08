"""
Contract Intelligence DLT Pipeline
====================================
Medallion architecture: bronze → silver → gold
Built using Databricks AI Dev Kit via Claude Code MCP tools.

Showcases what AI Dev Kit enables that Genie Code cannot:
  - Full pipeline creation, deployment & orchestration from the editor
  - Managed via mcp__databricks__manage_pipeline tool
"""

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

# ── Bronze: Raw contracts (already in workspace.sec_intelligence.bronze_contracts) ──
@dlt.table(
    name="bronze_contracts_stream",
    comment="Raw SEC contract files ingested via Auto Loader",
    table_properties={"quality": "bronze"}
)
def bronze_contracts_stream():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "binaryFile")
        .option("cloudFiles.includeExistingFiles", "true")
        .load("/Volumes/workspace/sec_intelligence/contracts_raw/")
    )

# ── Silver: Parsed contract elements ──
@dlt.table(
    name="silver_contract_elements_clean",
    comment="Cleaned and validated contract elements with standardised columns",
    table_properties={"quality": "silver"},
    expectations={
        "valid_confidence": "confidence_score BETWEEN 0 AND 1",
        "non_null_content": "content_text IS NOT NULL"
    }
)
def silver_contract_elements_clean():
    return (
        dlt.read("workspace.sec_intelligence.silver_contract_elements")
        .withColumn("document_name", F.regexp_extract(F.col("path"), r"([^/]+)$", 1))
        .withColumn("governing_law",
            F.col("extracted_fields.governing_law").cast(StringType()))
        .withColumn("party_1_name",
            F.col("extracted_fields.party_1_name").cast(StringType()))
        .withColumn("party_2_name",
            F.col("extracted_fields.party_2_name").cast(StringType()))
        .withColumn("contract_type",
            F.col("extracted_fields.contract_type").cast(StringType()))
        .select(
            "path", "document_name", "element_type", "content_text",
            "confidence_score", "governing_law", "party_1_name",
            "party_2_name", "contract_type"
        )
        .filter(F.col("confidence_score") > 0.5)
    )

# ── Gold: Contract insights aggregated ──
@dlt.table(
    name="gold_contract_insights_dlt",
    comment="Aggregated contract intelligence — governing law, parties, clause counts",
    table_properties={"quality": "gold"}
)
def gold_contract_insights_dlt():
    return (
        dlt.read("silver_contract_elements_clean")
        .groupBy("document_name", "governing_law", "party_1_name",
                  "party_2_name", "contract_type")
        .agg(
            F.count("*").alias("total_clauses"),
            F.avg("confidence_score").alias("avg_confidence"),
            F.collect_list("element_type").alias("clause_types"),
            F.max(F.length("content_text")).alias("longest_clause_chars")
        )
        .withColumn("risk_score",
            F.when(F.col("avg_confidence") < 0.7, "HIGH")
             .when(F.col("avg_confidence") < 0.85, "MEDIUM")
             .otherwise("LOW"))
        .withColumn("processed_at", F.current_timestamp())
    )
