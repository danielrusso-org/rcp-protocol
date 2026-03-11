# RCP-2 Profile B: ML Pipeline

> **Profile:** B | **Status:** Draft 0.1 | **Part of:** [RCP Protocol](../README.md)

This profile specifies how RCP-0 and RCP-1 are implemented in **machine learning pipelines**, covering data ingestion for training, model artefacts, and deployed inference endpoints.

---

## 1. Scope

This profile applies to:
- ML training pipelines that consume datasets (batch or streaming).
- Model artefact stores (MLflow, Hugging Face Hub, custom registries).
- Inference endpoints (REST APIs, batch scoring jobs, embedded models).
- Feature stores that materialise features from RCP-governed datasets.

---

## 2. Envelope Inheritance

The key design principle of the ML profile is **envelope inheritance**: when a model is trained on RCP-governed data, the model artefact inherits the envelope.

### 2.1 Training

At the start of a training job:
1. The pipeline MUST issue `QUERY(envelope_id, action="train")` for each RCP-governed dataset in the training corpus.
2. If any QUERY returns `permitted: false` or `status: revoked/disputed`, the training job MUST be **blocked**.
3. If all QUERYs return `permitted: true`, the training job proceeds.
4. A new RCP-0 envelope is created for the model artefact with:
   - `derived_from`: list of all training dataset `envelope_id`s.
   - `custodial_authority`: inherited from the most restrictive training dataset envelope.
   - `authorized_purposes`: intersection of all training dataset `authorized_purposes`.
   - `revocation_authority`: inherited from training datasets (union of all revocation authorities).

> **Design note:** Taking the **intersection** of `authorized_purposes` ensures that a model cannot be used for purposes not permitted by all its training data sources. This operationalises the whakapapa principle: the model's governance lineage is the sum of its data lineage.

### 2.2 Fine-tuning and transfer learning

Fine-tuning a base model on RCP-governed data creates a new model artefact with:
- `derived_from`: the base model's `envelope_id` plus all fine-tuning dataset `envelope_id`s.
- Purposes and authority inherited as in Section 2.1.

If the base model has no RCP envelope (e.g., a public foundation model), fine-tuning on RCP-governed data creates a new RCP envelope for the resulting artefact.

---

## 3. Model Artefact Storage

The RCP-0 envelope is stored as **model metadata** in the artefact store.

| Platform | Mechanism |
|----------|-----------|
| MLflow | Model tags with key prefix `rcp.*`; full envelope in `rcp.envelope_json` |
| Hugging Face Hub | Model card `metadata` section with `rcp:` prefix keys |
| Kubeflow | Pipeline run metadata with RCP envelope as a named artefact |
| Custom registries | Store envelope as a sidecar JSON file `{model_name}.rcp.json` |

**Required model card fields (Hugging Face / equivalent):**
```yaml
rcp_version: "0.1"
rcp_envelope_id: "<UUID>"
rcp_custodial_authority: "<URI>"
rcp_revocation_status: "active"
rcp_authorized_purposes:
  - "<purpose1>"
  - "<purpose2>"
```

---

## 4. Inference Endpoint Enforcement

### 4.1 Endpoint registration check

Before registering a model as a live inference endpoint, the serving platform MUST:
1. Check the model's RCP envelope status.
2. Block registration if status is `revoked` or `disputed`.
3. Record the endpoint URI in the RCP-1 audit log as a "materialisation event".

### 4.2 Runtime check

Inference endpoints for RCP-governed models MUST:
1. Check envelope status on each inference request (or cache with a TTL of ≤ 1 hour).
2. Return HTTP 451 (Unavailable For Legal Reasons) with an RCP error body if status is `revoked` or `disputed`.

### 4.3 Deregistration on revocation (O3)

When a REVOKE message is received for any envelope in the model's `derived_from` chain:
1. All inference endpoints serving that model MUST be **deregistered** within 24 hours.
2. Batch scoring jobs using the model MUST be cancelled or blocked.
3. The deregistration event MUST be recorded in the audit log.

---

## 5. Feature Store Integration

Feature stores that materialise features from RCP-governed datasets inherit the envelope:
- Feature groups derived from RCP-governed tables carry an RCP envelope.
- Serving features from a `revoked` feature group MUST be blocked.
- Feature pipelines MUST propagate REVOKE to all feature groups derived from a revoked source.

---

## 6. Model Card Requirements

Model cards for RCP-governed models MUST include a **Governance** section that surfaces:
- `custodial_authority.name` and type (individual/collective/institution).
- `authorized_purposes` as a human-readable list.
- `revocation_status` (current).
- A link to the full RCP-0 envelope JSON.
- A statement of relational obligations (from `relational_obligations` field).

This makes community authority visible to model consumers, not only to pipeline engineers.

---

## 7. Compliance Checklist

An ML pipeline deployment is **RCP-2 Profile B compliant** if:

- [ ] Training jobs issue QUERY for all RCP-governed datasets before training.
- [ ] Model artefacts inherit RCP-0 envelopes from training data via `derived_from`.
- [ ] `authorized_purposes` on models are the intersection of training dataset purposes.
- [ ] Inference endpoints check envelope status before serving.
- [ ] Endpoints are deregistered within 24 hours of a REVOKE on any source envelope.
- [ ] Model cards surface `custodial_authority` and `authorized_purposes`.
- [ ] All training, registration, and revocation events are in the audit log.

---

## 8. Open Problems

- **Foundation model provenance:** Large foundation models are trained on heterogeneous corpora; retroactive RCP envelope attachment is an open research problem.
- **Intersection semantics at scale:** Computing the intersection of `authorized_purposes` across thousands of training datasets is computationally and semantically non-trivial.
- **Distillation and synthetic data:** If a model generates synthetic data from RCP-governed training data, does the synthetic data inherit the envelope? RCP-0.1 does not specify this. Proposed conservative default: yes.
- **Federated learning:** How to handle RCP envelopes when training data never leaves the community's infrastructure (federated/split learning).
