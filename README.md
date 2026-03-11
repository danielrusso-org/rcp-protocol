# RCP — Relational Consent and Provenance Protocol

> **Version:** 0.1-draft | **Status:** Proposal | **License:** MIT
>
> Companion artifact to: Russo, D. et al. "Indigenous Data Governance and Software Engineering: Structural Lessons from the Māori Case" — *ACM Transactions on Software Engineering and Methodology* (under review).

---

## Overview

RCP is a minimal three-layer protocol that makes **collective, revocable, community-level data governance** a first-class concern in software and data systems. It is motivated by the structural gap documented in the companion paper: communities — particularly Indigenous communities — articulate governance requirements that current SE notations, methods, and tools cannot express. RCP proposes the missing protocol layer.

RCP is positioned as a **CARE-aligned counterpart to FAIR**. Where FAIR (Findable, Accessible, Interoperable, Reusable) optimises for open data sharing, CARE (Collective Benefit, Authority to Control, Responsibility, Ethics) centres community authority and relational accountability. RCP makes CARE machine-actionable at infrastructural scale.

The protocol is analogous in scope to TCP/IP: just as TCP/IP separates routing concerns from application logic, RCP separates **relational accountability concerns** from application and pipeline logic. Any compliant system attaches, reads, and enforces RCP envelopes without needing to re-implement governance logic from scratch.

---

## Protocol Layers

| Layer | Name | Role |
|-------|------|------|
| RCP-0 | Relational Provenance Envelope | Portable header attached to any dataset or model |
| RCP-1 | Consent and Revocation Protocol | Message types and state machine for authority lifecycle |
| RCP-2 | Enforcement Profiles | Host-system bindings for data lakes, ML pipelines, consent UIs |

---

## RCP-0: Relational Provenance Envelope

RCP-0 extends standard W3C PROV-style lineage from:
> *"What transformations were applied?"*

to:
> *"Who granted authority for this use, under what conditions, and who retains the right to say stop?"*

This extension operationalises the *whakapapa* principle from Māori data governance: provenance is not only computational but **relational and accountable**.

### Envelope Fields

See [`schema/rcp0-envelope.json`](schema/rcp0-envelope.json) for the normative JSON Schema.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `rcp_version` | string | yes | Protocol version, e.g. `"0.1"` |
| `envelope_id` | string (UUID) | yes | Globally unique identifier for this envelope |
| `dataset_id` | string | yes | Identifier of the governed dataset or model |
| `custodial_authority` | object | yes | Community or entity holding governance authority |
| `custodial_authority.id` | string (URI) | yes | Stable, resolvable identifier for the authority holder |
| `custodial_authority.name` | string | yes | Human-readable name |
| `custodial_authority.type` | enum | yes | `individual` \| `collective` \| `institution` |
| `authorized_purposes` | array[string] | yes | Bounded list of permitted uses (from codebook) |
| `relational_obligations` | array[string] | no | Obligation keys (e.g. `tapu`, `genealogical`, `commercial-prohibited`) |
| `consent_record_id` | string (URI) | yes | Pointer to the consent record that authorised this envelope |
| `consent_granted_at` | string (ISO 8601) | yes | Timestamp of authority grant |
| `revocation_authority` | object | yes | Who can revoke; same structure as `custodial_authority` |
| `revocation_endpoint` | string (URI) | no | Resolvable endpoint to check/trigger revocation |
| `revocation_status` | enum | yes | `provisional` \| `active` \| `amended` \| `revoked` \| `disputed` |
| `revocation_status_updated_at` | string (ISO 8601) | yes | Timestamp of last status change |
| `derived_from` | array[string] | no | Parent `envelope_id`s, enabling whakapapa-style lineage chains |
| `conditions` | string | no | Free-text or structured conditions on use |

### Key Design Decisions

1. **`custodial_authority.type: collective`** is a first-class value — not an edge case. A hapū, iwi, or community board is a valid authority holder.
2. **`revocation_status`** is a required field with a defined state machine (see RCP-1). It is not optional metadata.
3. **`derived_from`** chains envelopes across transformations, so downstream datasets inherit the governance lineage of their sources.
4. The envelope is **attached at ingestion**, not reconstructed after the fact.

---

## RCP-1: Consent and Revocation Protocol

RCP-1 defines the **messages** that participating systems exchange to manage an envelope's lifecycle, and the **state machine** that governs valid transitions.

### Message Types

| Message | Sender | Effect |
|---------|--------|--------|
| `GRANT(authority, dataset_id, purposes, conditions)` | Custodial authority | Creates a new RCP-0 envelope with status `active` |
| `AMEND(authority, envelope_id, new_purposes, new_conditions)` | Custodial authority | Updates purposes/conditions; status → `amended` |
| `REVOKE(authority, envelope_id, scope, reason)` | Revocation authority | Status → `revoked`; scope may be `full` or `purpose-specific` |
| `QUERY(envelope_id, action)` | Any participating system | Returns current status and whether `action` is permitted |
| `ACK` | Receiving system | Confirms receipt and compliance |
| `NACK(code, reason)` | Receiving system | Refused; codes: `no-standing`, `out-of-scope`, `revoked`, `disputed` |

### State Machine

```
[created]
    |
    v
[provisional] --GRANT--> [active] --AMEND--> [amended]
                              |                    |
                              +----REVOKE----------+
                              |                    |
                              v                    v
                          [revoked]           [disputed]
```

**Transition rules:**
- A system **MUST** check status via `QUERY` before any material use (training, sharing, publishing).
- A `REVOKE` message propagates to all systems holding a derived envelope (`derived_from` chain).
- `disputed` is entered when revocation is contested; systems **MUST** treat `disputed` as `revoked` until resolved.
- Status transitions are **append-only** in the audit log but the current status is **mutable**.

### Participating System Obligations

A system is **RCP-1 compliant** if it:
1. Accepts and stores RCP-0 envelopes at data ingestion.
2. Issues a `QUERY` before any material use of governed data.
3. Propagates `REVOKE` messages to downstream systems and derived datasets within a defined SLA (recommended: 24 hours).
4. Returns `NACK(revoked)` to any downstream request after revocation.
5. Maintains an immutable audit log of all RCP-1 message exchanges.

---

## RCP-2: Enforcement Profiles

RCP-2 specifies how RCP-0 and RCP-1 are implemented in specific infrastructure substrates. Each profile must define:
- Where in the architecture RCP checks occur.
- Failure semantics (fail-closed vs. quarantine vs. log-and-flag).
- How revocation events surface in audit trails.

### Profile A: Data Lake

See [`profiles/data-lake-profile.md`](profiles/data-lake-profile.md).

- RCP-0 envelope stored as table-level metadata (e.g., Delta Lake `TBLPROPERTIES`, Apache Iceberg table properties).
- `QUERY` issued at query plan compilation; queries against `revoked` envelopes fail with `RCP_REVOKED` error.
- `REVOKE` propagates to derived tables and cached snapshots, not only the root table.
- Partition-level scope supported for `purpose-specific` revocation.

### Profile B: ML Pipeline

See [`profiles/ml-pipeline-profile.md`](profiles/ml-pipeline-profile.md).

- Models trained on RCP-governed data **inherit** the envelope via `derived_from`.
- Training jobs check status at start; jobs on `revoked` data are blocked.
- Deployed inference endpoints carry the inherited envelope and are deregistered on `REVOKE`.
- Model cards must surface `custodial_authority` and `authorized_purposes`.

### Profile C: Consent Interface

See [`profiles/consent-interface-profile.md`](profiles/consent-interface-profile.md).

- Interfaces **MUST** expose `custodial_authority.type` — collective authority is visible, not hidden behind an individual proxy.
- `authorized_purposes` are shown as bounded, human-readable scope descriptors.
- `AMEND` and `REVOKE` are first-class UI actions, not buried in settings.
- Interfaces **MUST NOT** collapse collective consent into a single boolean.

---

## Repository Structure

```
rcp-protocol/
├── README.md                        # This document — protocol specification
├── LICENSE                          # MIT
├── schema/
│   └── rcp0-envelope.json           # Normative JSON Schema for RCP-0 envelope
├── protocol/
│   └── rcp1-state-machine.md        # RCP-1 message types and state machine (formal)
├── profiles/
│   ├── data-lake-profile.md         # RCP-2 Profile A
│   ├── ml-pipeline-profile.md       # RCP-2 Profile B
│   └── consent-interface-profile.md # RCP-2 Profile C
└── reference/
    ├── python/
    │   └── rcp.py                   # Minimal Python reference implementation
    └── typescript/
        └── rcp.ts                   # Minimal TypeScript reference implementation
```

---

## Relationship to Existing Standards

| Standard / Framework | Relationship to RCP |
|----------------------|---------------------|
| W3C PROV | RCP-0 extends PROV with relational accountability fields |
| FAIR Principles | RCP is a CARE-aligned complement; addresses authority and revocation that FAIR does not |
| CARE Principles | RCP operationalises CARE's "Authority to Control" as a machine-actionable protocol |
| GDPR / consent frameworks | RCP generalises consent to collective, perpetual, revocable form — not one-time individual |
| Apache Atlas / OpenLineage | RCP-2 profiles can be implemented as lineage backends for these tools |

---

## Open Research Problems

RCP-0.1 is deliberately minimal. It seeds the following open research agenda, mapped to the SE lifecycle:

1. **Formal specification of RCP-0 in requirements languages** (SysML, use-case contracts): how to express custodial obligations as acceptance criteria.
2. **Scalable RCP-1 propagation**: how to implement 24-hour revocation propagation across federated cloud data lakes without centralised coordination.
3. **RCP-2 ML profile at training scale**: how to handle large foundation models trained on heterogeneous RCP-governed corpora.
4. **Governance API design for collective deliberation**: how to expose `AMEND` and `REVOKE` to communities with genuine internal dissent, without collapsing minority positions.
5. **Interoperability with existing consent registries**: mapping RCP-1 messages to GDPR consent records, Indigenous data sovereignty registries (e.g., Te Mana Raraunga).

---

## How to Cite

If you use or build on RCP in research, please cite:

```bibtex
@misc{russo2026rcp,
  author       = {Russo, Daniel},
  title        = {{RCP}: Relational Consent and Provenance Protocol (v0.1-draft)},
  year         = {2026},
  howpublished = {\url{https://github.com/danielrusso-org/rcp-protocol}},
  note         = {Companion artifact to Russo et al., TOSEM (under review)}
}
```

---

## Contributing

RCP is an open protocol proposal. Contributions, critiques, and implementation reports are welcome via Issues and Pull Requests. Particularly sought:
- Feedback from Indigenous data sovereignty practitioners.
- Implementation reports against the RCP-2 profiles.
- Formal verification of the RCP-1 state machine.

---

*RCP is named after its three layers: Relational · Consent · Provenance.*
