# RCP-2 Profile C: Consent Interface

> **Profile:** C | **Status:** Draft 0.1 | **Part of:** [RCP Protocol](../README.md)

This profile specifies the behavioural requirements for **consent interfaces** that expose RCP-governed data to communities, users, and operators. It translates CARE's Authority to Control principle into concrete interface obligations.

---

## 1. Motivation

Existing consent interfaces are designed around a Western individual-privacy model: a single user, a single click, a binary yes/no. This model cannot represent:
- A hapū authorising data use collectively under conditions that change when relationships change.
- A community's right to amend or revoke consent after the fact.
- Minority positions within a collective that dissent from a majority decision.

Profile C specifies what interfaces MUST do differently to support relational, collective, perpetual consent. The central obligation is: **interfaces MUST NOT collapse collective governance into a single boolean**.

---

## 2. Core Interface Obligations

### 2.1 Authority visibility

Interfaces MUST display the `custodial_authority` to users before any consent action:
- Authority name and type (`individual`, `collective`, `institution`) MUST be visible.
- If `type = collective`, the interface MUST indicate that this is a collective authority, not an individual one.
- The authority's identifier (URI) MUST be accessible (e.g., as a link) for users who wish to verify it.

**Prohibited pattern:** Hiding collective authority behind a single data controller name without surfacing the community governance structure.

### 2.2 Purpose scope display

Interfaces MUST display `authorized_purposes` as a human-readable, bounded list:
- Each purpose MUST be presented as a distinct, labelled item.
- Purposes MUST NOT be aggregated into a single "I agree to all uses" option.
- If a requested action is not in `authorized_purposes`, the interface MUST make this visible and MUST block the action.

### 2.3 Relational obligations disclosure

If `relational_obligations` is non-empty, the interface MUST surface a plain-language explanation of each obligation:
- E.g., `tapu` → "This data carries sacred significance; certain uses are permanently prohibited."
- E.g., `return-to-community` → "Results derived from this data must be returned to the community."

---

## 3. AMEND and REVOKE as First-Class Actions

### 3.1 AMEND

Interfaces for authority holders MUST expose an **Amend** action that allows:
- Adding or removing `authorized_purposes`.
- Updating `conditions`.
- Updating `relational_obligations`.

AMEND MUST NOT require the authority to revoke and re-grant. It is a distinct, lighter action.

### 3.2 REVOKE

Interfaces for authority holders MUST expose a **Revoke** action that:
- Is prominently accessible, not buried in settings.
- Supports `scope: full` (revoke all) and `scope: purpose-specific` (revoke one or more purposes).
- Clearly explains the downstream effects (e.g., "This will deregister all models trained on this dataset.").
- Does NOT require legal justification; the community's authority to revoke is unconditional.

**Prohibited pattern:** Requiring communities to navigate a support ticket or legal process to revoke consent.

---

## 4. Collective Consent Representation

### 4.1 Collective authorization display

When `custodial_authority.type = collective`, the interface MUST:
- Show the collective's name and, where available, its governance structure (e.g., "Authorised by Te Waka Governance Board, 7 members").
- NOT present consent as having been given by a named individual on behalf of the collective.
- NOT use first-person singular language ("I agree") for collective consent.

### 4.2 Minority position support

Interfaces that support internal collective deliberation (e.g., governance portals for iwi or hapū) MUST:
- Allow individual members to register dissent or abstention, not only majority approval.
- Store dissent in the audit log (as a note on the RCP-1 GRANT message, not as a veto).
- Surface the existence of minority positions to downstream users where relevant.

This operationalises the heterogeneity-preserving governance principle: **governance interfaces must not collapse genuine internal deliberation into a single consent vector**.

---

## 5. Status Display

Interfaces serving end users (data consumers, researchers, developers) MUST display current `revocation_status` clearly:

| Status | Interface behaviour |
|--------|---------------------|
| `active` | Access permitted; display authority and purposes |
| `amended` | Access permitted; display updated purposes with change notice |
| `provisional` | Access restricted; display pending authorisation notice |
| `revoked` | Access blocked; display plain-language revocation notice |
| `disputed` | Access blocked; display dispute notice; do NOT reveal dispute details |

---

## 6. Temporal and Conditional Consent

If `conditions` specifies temporal limits (e.g., "Access expires 31 December 2025") or contextual conditions:
- The interface MUST display these conditions prominently before any consent action.
- The interface MUST automatically trigger an AMEND or REVOKE check when conditions approach expiry.
- Expired conditions MUST result in status transition to `provisional` pending renewal.

---

## 7. Accessibility and Language

- Consent interfaces for Indigenous communities MUST support the community's preferred language.
- Plain-language summaries of obligations and purposes MUST be available.
- Interfaces MUST be accessible to community members who are not technical users.

---

## 8. Compliance Checklist

A consent interface is **RCP-2 Profile C compliant** if:

- [ ] `custodial_authority` name and type are visible before any consent action.
- [ ] Collective authority is explicitly labelled; first-person singular language is absent.
- [ ] `authorized_purposes` are displayed as a bounded, itemised list.
- [ ] AMEND and REVOKE are first-class, prominently accessible actions.
- [ ] Purpose-specific revocation is supported.
- [ ] Minority positions can be registered in collective deliberation flows.
- [ ] `revocation_status` is displayed to data consumers.
- [ ] Temporal and conditional consent triggers are implemented.
- [ ] Community language support is provided.

---

## 9. Open Problems

- **Designing for low-bandwidth and low-literacy contexts:** Many Indigenous communities access governance interfaces on mobile devices with limited connectivity. RCP-2 Profile C does not yet specify offline-capable consent flows.
- **Governance portal standards:** There is no standard for community governance portals that implement AMEND/REVOKE at the community level. This is a significant HCI research gap.
- **Consent UI testing with communities:** Profile C requirements are derived from CARE principles and the Māori case analysis; empirical usability testing with Indigenous communities is needed to validate and refine them.
