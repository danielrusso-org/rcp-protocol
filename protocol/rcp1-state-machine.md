# RCP-1: Consent and Revocation Protocol

> **Layer:** RCP-1 | **Status:** Draft 0.1 | **Part of:** [RCP Protocol](../README.md)

RCP-1 defines the **messages** and **state machine** that govern the lifecycle of an RCP-0 envelope. It specifies what participating systems must do to be RCP-1 compliant.

---

## 1. Rationale

A provenance envelope (RCP-0) is only as useful as the protocol that keeps it alive and actionable across system boundaries. RCP-1 answers three questions:

1. **How is an envelope created?** (`GRANT`)
2. **How is it updated when community authority changes?** (`AMEND`)
3. **How is it terminated when community authority is withdrawn?** (`REVOKE`)

The protocol is deliberately minimal: six message types, one state machine, five compliance obligations. This minimalism is intentional — it lowers the barrier to adoption across heterogeneous stacks.

---

## 2. Message Types

All messages are sent by an **authority** (the custodial or revocation authority named in the envelope) or by a **participating system** (any system that ingests, processes, or serves RCP-governed data).

### 2.1 GRANT

```
GRANT(
  authority:        Authority,      -- who is granting
  dataset_id:       string,         -- what dataset
  purposes:         [string],       -- bounded permitted uses
  conditions?:      string,         -- optional conditions
  obligations?:     [string]        -- optional obligation keys
) -> envelope_id: UUID
```

**Effect:** Creates a new RCP-0 envelope with `revocation_status: active`. Returns the new `envelope_id`.  
**Precondition:** Authority must have standing (i.e., be a recognised custodial authority for this dataset).  
**Error:** `NACK(no-standing)` if authority cannot be verified.

---

### 2.2 AMEND

```
AMEND(
  authority:        Authority,      -- must match custodial_authority in envelope
  envelope_id:      UUID,
  new_purposes?:    [string],       -- replaces authorized_purposes if provided
  new_conditions?:  string,         -- replaces conditions if provided
  new_obligations?: [string]        -- replaces relational_obligations if provided
) -> envelope_id: UUID              -- same envelope_id, updated
```

**Effect:** Updates purposes, conditions, or obligations. Status transitions to `amended`. The previous state is preserved in the audit log.  
**Precondition:** `revocation_status` must be `active` or `amended`.  
**Error:** `NACK(revoked)` if envelope is already revoked or disputed.

---

### 2.3 REVOKE

```
REVOKE(
  authority:        Authority,      -- must match revocation_authority in envelope
  envelope_id:      UUID,
  scope:            "full" | "purpose-specific",
  purposes?:        [string],       -- required if scope = purpose-specific
  reason?:          string          -- optional human-readable reason
) -> void
```

**Effect:** Status transitions to `revoked`. Participating systems MUST propagate revocation to all systems holding derived envelopes (`derived_from` chain) within the compliance SLA (recommended: 24 hours).  
**Precondition:** Authority must match `revocation_authority` in the envelope.  
**Error:** `NACK(no-standing)` if authority mismatch.

> **Design note:** `purpose-specific` revocation allows a community to withdraw consent for one use (e.g., commercial AI training) while retaining consent for another (e.g., health research). This operationalises the tikanga principle that authority is contextual, not monolithic.

---

### 2.4 QUERY

```
QUERY(
  envelope_id:      UUID,
  action:           string          -- the intended action (e.g., "train", "share", "publish")
) -> {
  status:           RevocationStatus,
  permitted:        boolean,
  conditions?:      string
}
```

**Effect:** Returns current envelope status and whether the requested action is within `authorized_purposes`.  
**Obligation:** Participating systems MUST issue a QUERY before any material use of governed data.

---

### 2.5 ACK

```
ACK(
  envelope_id:      UUID,
  message_type:     string,         -- the message being acknowledged
  system_id:        string          -- acknowledging system identifier
) -> void
```

**Effect:** Confirms receipt and compliance. Recorded in the audit log.

---

### 2.6 NACK

```
NACK(
  envelope_id:      UUID,
  code:             NACKCode,
  reason?:          string
) -> void
```

**NACK Codes:**

| Code | Meaning |
|------|---------|
| `no-standing` | The sender does not have authority to perform the requested action |
| `out-of-scope` | The requested action is not within `authorized_purposes` |
| `revoked` | The envelope has status `revoked`; access denied |
| `disputed` | The envelope has status `disputed`; access denied pending resolution |
| `not-found` | No envelope found for the given `envelope_id` |
| `malformed` | The message did not conform to the RCP-1 message schema |

---

## 3. State Machine

### 3.1 States

| State | Meaning |
|-------|---------|
| `provisional` | Envelope created but authority not yet confirmed |
| `active` | Authority granted; data use permitted per `authorized_purposes` |
| `amended` | Authority updated; previous state preserved in audit log |
| `revoked` | Authority withdrawn; data use prohibited |
| `disputed` | Revocation contested; treated as `revoked` until resolved |

### 3.2 Transition Diagram

```
                    GRANT
[provisional] ─────────────────> [active]
                                    │
                             AMEND  │  REVOKE
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    v               v               v
               [amended]        [revoked]      [disputed]
                    │
               AMEND│  REVOKE
                    │
                    ├──────────> [revoked]
                    └──────────> [disputed]
```

### 3.3 Transition Rules

| From | Message | To | Guard |
|------|---------|----|-------|
| `provisional` | `GRANT` | `active` | Authority has standing |
| `active` | `AMEND` | `amended` | Authority matches `custodial_authority` |
| `active` | `REVOKE` | `revoked` | Authority matches `revocation_authority` |
| `active` | `REVOKE` (contested) | `disputed` | Revocation contested by another authority |
| `amended` | `AMEND` | `amended` | Authority matches `custodial_authority` |
| `amended` | `REVOKE` | `revoked` | Authority matches `revocation_authority` |
| `disputed` | (resolution) | `revoked` | Dispute resolved in favour of revocation |
| `disputed` | (resolution) | `active` | Dispute resolved in favour of continued use |
| `revoked` | — | — | Terminal state; no transitions out |

### 3.4 Key Invariants

1. **`revoked` is terminal.** Once revoked, an envelope cannot be reinstated. A new GRANT creates a new envelope with a new `envelope_id`.
2. **`disputed` fails closed.** Systems MUST treat `disputed` as `revoked` for access control until resolved.
3. **Revocation propagates.** A REVOKE on envelope X triggers REVOKE on all envelopes whose `derived_from` includes X.
4. **Audit log is append-only.** Status transitions are recorded but not deleted.

---

## 4. Participating System Obligations

A system is **RCP-1 compliant** if and only if it satisfies all five obligations:

| # | Obligation | SLA |
|---|------------|-----|
| O1 | Accept and store RCP-0 envelopes at data ingestion | At ingest time |
| O2 | Issue a QUERY before any material use of governed data | Before use |
| O3 | Propagate REVOKE to downstream systems and derived datasets | ≤ 24 hours |
| O4 | Return NACK(revoked) to any downstream request after revocation | Immediately |
| O5 | Maintain an immutable audit log of all RCP-1 message exchanges | Perpetual |

**Material use** includes: model training, publishing, sharing with third parties, making publicly accessible, using in inference endpoints.

---

## 5. Audit Log Entry Format

Each RCP-1 message exchange produces an audit log entry:

```json
{
  "log_id": "<uuid>",
  "envelope_id": "<uuid>",
  "message_type": "GRANT | AMEND | REVOKE | QUERY | ACK | NACK",
  "sender_id": "<system or authority URI>",
  "timestamp": "<ISO 8601>",
  "previous_status": "<RevocationStatus>",
  "new_status": "<RevocationStatus>",
  "payload_hash": "<SHA-256 of message payload>"
}
```

Audit logs MUST be:
- Append-only (no deletions or modifications).
- Accessible to the `custodial_authority` and `revocation_authority` on request.
- Retained for the full lifecycle of the envelope plus a minimum of 7 years.

---

## 6. Open Research Problems

- **Federated propagation at scale:** How to guarantee O3 (24-hour propagation) across systems with no shared coordination layer, particularly when downstream systems are not RCP-aware.
- **Authority verification:** How to implement a lightweight, decentralised registry for verifying custodial authority standing (analogous to PKI but for community governance).
- **Dispute resolution protocol:** RCP-1.0 does not specify how `disputed` envelopes are resolved. This is a deliberate gap, recognising that dispute resolution is a governance process, not a technical one. A future RCP-1.1 may specify an arbitration interface.
- **Purpose codebook standardisation:** `authorized_purposes` are free strings in v0.1. A shared codebook (analogous to SPDX for licences) would improve interoperability.
