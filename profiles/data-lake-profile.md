# RCP-2 Profile A: Data Lake

> **Profile:** A | **Status:** Draft 0.1 | **Part of:** [RCP Protocol](../README.md)

This profile specifies how RCP-0 and RCP-1 are implemented in **data lake** infrastructures, including Delta Lake, Apache Iceberg, Apache Hudi, and compatible object-store-backed table formats.

---

## 1. Scope

This profile applies to any system that:
- Stores datasets in a table format with queryable metadata (Delta Lake, Iceberg, Hudi, Parquet+Hive Metastore).
- Serves queries via a SQL engine (Spark, Trino, Dremio, Athena, BigQuery, Databricks SQL).
- Ingests datasets from external sources that may carry RCP-0 envelopes.

---

## 2. Envelope Storage

### 2.1 Table-level attachment

The RCP-0 envelope is stored as **table-level metadata**, not as a separate sidecar file. This ensures it travels with the table through snapshots, clones, and exports.

| Platform | Mechanism |
|----------|-----------|
| Delta Lake | `TBLPROPERTIES` with key prefix `rcp.*` |
| Apache Iceberg | Table properties with key prefix `rcp.*` |
| Apache Hudi | Table config with key prefix `hoodie.rcp.*` |
| Generic (Parquet + HMS) | Hive Metastore table parameters with key prefix `rcp.*` |

**Required properties:**
```
rcp.envelope_id         = <UUID>
rcp.revocation_status   = active | amended | revoked | disputed | provisional
rcp.custodial_authority = <URI>
rcp.revocation_endpoint = <URI>   (if available)
rcp.envelope_json       = <full RCP-0 JSON, base64-encoded>
```

### 2.2 Partition-level attachment

For `purpose-specific` revocation (RCP-1 REVOKE with `scope: purpose-specific`), the platform MUST support partition-level metadata overrides, so that specific partitions can be marked `revoked` without revoking the entire table.

---

## 3. Query Enforcement

### 3.1 Query plan check (O2)

Before executing any query that touches an RCP-governed table, the query engine MUST:

1. Read `rcp.revocation_status` from table properties.
2. If status is `revoked` or `disputed`: **abort query** and return `RCP_REVOKED` error to the caller.
3. If status is `active` or `amended`: check that the query intent (as declared or inferred) is within `authorized_purposes`.
4. If purpose check fails: return `RCP_OUT_OF_SCOPE` error.

Recommended implementation point: a **pre-execution rule** in the query optimizer or a **row-level security policy** that fires before any scan.

### 3.2 Failure semantics

| Condition | Behaviour |
|-----------|-----------|
| `revocation_status = revoked` | Fail closed. Query aborted. Error surfaced to caller. |
| `revocation_status = disputed` | Fail closed. Same as `revoked`. |
| `revocation_endpoint` unreachable | Fail closed. Cached status used; if cache expired (> 1 hour), query blocked. |
| `rcp.*` metadata missing on ingested table | Warn. Table flagged as `ungovernered`. Queries permitted but logged. |

---

## 4. Revocation Propagation

### 4.1 Derived table propagation (O3)

When a REVOKE message is received for envelope X:

1. Table with `rcp.envelope_id = X` is immediately marked `revoked` in table properties.
2. The system MUST identify all tables whose `rcp.envelope_json` includes `derived_from: [... X ...]`.
3. Each derived table is also marked `revoked` and a REVOKE message is issued for its envelope.
4. Cached query results derived from the table are invalidated.
5. All steps MUST complete within 24 hours (O3 SLA).

### 4.2 Snapshot and time-travel

Revocation applies to **all snapshots**, not only the current one. A query using `VERSION AS OF` or `TIMESTAMP AS OF` on a revoked table MUST also be blocked.

### 4.3 Export and copy tracking

If a table has been exported to an external system (e.g., via `COPY INTO`, `EXPORT`, or a data share), the exporting system MUST:
- Record the destination in the RCP-1 audit log at export time.
- Propagate REVOKE to the destination system when revocation occurs.

---

## 5. Audit Trail (O5)

Each of the following events MUST produce an audit log entry (see RCP-1 Section 5 for format):

- Table ingestion with RCP-0 envelope attached.
- Query execution on RCP-governed table (with outcome: permitted / blocked).
- Revocation status change.
- Derived table identification and propagation.
- Export to external system.

---

## 6. Compliance Checklist

A data lake deployment is **RCP-2 Profile A compliant** if:

- [ ] RCP-0 envelopes are stored as table-level metadata at ingestion.
- [ ] Queries against `revoked` or `disputed` tables fail closed.
- [ ] Revocation propagates to derived tables within 24 hours.
- [ ] Partition-level revocation is supported for `purpose-specific` scope.
- [ ] All query executions and revocation events are recorded in the audit log.
- [ ] Time-travel queries on revoked tables are blocked.

---

## 7. Open Problems

- How to propagate revocation to external systems (e.g., BI tools, data shares) that do not implement RCP.
- How to handle `ungovenered` tables ingested before RCP adoption: retroactive envelope attachment vs. quarantine.
- Performance impact of pre-execution RCP checks in high-throughput query environments.
