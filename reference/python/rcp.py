"""Minimal Python reference implementation of RCP (Relational Consent and Provenance)

This module provides a lightweight, reference implementation of the RCP protocol
for use in data pipelines, ML training jobs, and governance applications.

Usage:
    from rcp import RCPEnvelope, query_envelope, create_envelope

    # Attach envelope at ingest
    envelope = create_envelope(
        dataset_id="my-dataset",
        custodial_authority={"id": "https://iwi.example.org", "name": "Te Waka", "type": "collective"},
        authorized_purposes=["health-research", "non-commercial"],
        consent_record_id="https://iwi.example.org/consent/2024-001"
    )

    # Check before use
    status = query_envelope(envelope, action="train")
    if not status["permitted"]:
        raise PermissionError(f"Action blocked: {status['status']}")
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Literal, TypedDict
from enum import Enum


class RevocationStatus(Enum):
    """RCP-0 envelope revocation status"""
    PROVISIONAL = "provisional"
    ACTIVE = "active"
    AMENDED = "amended"
    REVOKED = "revoked"
    DISPUTED = "disputed"


class AuthorityType(Enum):
    """Type of authority holder"""
    INDIVIDUAL = "individual"
    COLLECTIVE = "collective"
    INSTITUTION = "institution"


class Authority(TypedDict):
    """Authority record"""
    id: str  # URI
    name: str
    type: Literal["individual", "collective", "institution"]
    contact: Optional[str]


class RCPEnvelope(TypedDict, total=False):
    """RCP-0 Envelope conforming to schema/rcp0-envelope.json"""
    rcp_version: str
    envelope_id: str
    dataset_id: str
    custodial_authority: Authority
    authorized_purposes: List[str]
    relational_obligations: List[str]
    consent_record_id: str
    consent_granted_at: str  # ISO 8601
    revocation_authority: Authority
    revocation_endpoint: Optional[str]
    revocation_status: Literal["provisional", "active", "amended", "revoked", "disputed"]
    revocation_status_updated_at: str  # ISO 8601
    derived_from: List[str]
    conditions: Optional[str]


def create_envelope(
    dataset_id: str,
    custodial_authority: Authority,
    authorized_purposes: List[str],
    consent_record_id: str,
    revocation_authority: Optional[Authority] = None,
    relational_obligations: Optional[List[str]] = None,
    conditions: Optional[str] = None,
    derived_from: Optional[List[str]] = None,
    revocation_endpoint: Optional[str] = None,
) -> RCPEnvelope:
    """
    Create a new RCP-0 envelope.

    Args:
        dataset_id: Identifier for the governed dataset
        custodial_authority: The community or entity holding governance authority
        authorized_purposes: Bounded list of permitted uses
        consent_record_id: URI to the authoritative consent record
        revocation_authority: Who can revoke (defaults to custodial_authority)
        relational_obligations: Optional obligation keys (e.g., 'tapu', 'genealogical')
        conditions: Optional free-text conditions on use
        derived_from: Optional parent envelope_ids for whakapapa lineage
        revocation_endpoint: Optional URI for revocation status checks

    Returns:
        RCPEnvelope dict conforming to schema/rcp0-envelope.json
    """
    now = datetime.now(timezone.utc).isoformat()
    envelope_id = str(uuid.uuid4())

    envelope: RCPEnvelope = {
        "rcp_version": "0.1",
        "envelope_id": envelope_id,
        "dataset_id": dataset_id,
        "custodial_authority": custodial_authority,
        "authorized_purposes": authorized_purposes,
        "consent_record_id": consent_record_id,
        "consent_granted_at": now,
        "revocation_authority": revocation_authority or custodial_authority,
        "revocation_status": "active",
        "revocation_status_updated_at": now,
    }

    if relational_obligations:
        envelope["relational_obligations"] = relational_obligations
    if conditions:
        envelope["conditions"] = conditions
    if derived_from:
        envelope["derived_from"] = derived_from
    if revocation_endpoint:
        envelope["revocation_endpoint"] = revocation_endpoint

    return envelope


def query_envelope(envelope: RCPEnvelope, action: str) -> Dict:
    """
    RCP-1 QUERY: check if an action is permitted under the envelope.

    Args:
        envelope: The RCP-0 envelope to query
        action: The intended action (e.g., 'train', 'share', 'publish')

    Returns:
        Dict with keys:
            - status (str): current revocation_status
            - permitted (bool): whether the action is allowed
            - conditions (str | None): applicable conditions if any
    """
    status = envelope["revocation_status"]

    # Fail closed for revoked or disputed
    if status in ["revoked", "disputed"]:
        return {"status": status, "permitted": False, "conditions": None}

    # Check if action is within authorized_purposes
    # In a real implementation, this would use a purpose taxonomy
    # For now, exact string match
    permitted = action in envelope.get("authorized_purposes", [])

    return {
        "status": status,
        "permitted": permitted,
        "conditions": envelope.get("conditions"),
    }


def revoke_envelope(envelope: RCPEnvelope, scope: Literal["full", "purpose-specific"] = "full", purposes: Optional[List[str]] = None) -> RCPEnvelope:
    """
    RCP-1 REVOKE: mark an envelope as revoked.

    Args:
        envelope: The envelope to revoke
        scope: 'full' revokes all use; 'purpose-specific' revokes only listed purposes
        purposes: Required if scope='purpose-specific'

    Returns:
        Updated envelope with status 'revoked'

    Note:
        In a production system, this would:
        - Verify that the caller has revocation_authority standing
        - Propagate REVOKE to derived envelopes (derived_from chain)
        - Record the event in an audit log
        - Notify downstream systems via revocation_endpoint
    """
    if scope == "purpose-specific" and not purposes:
        raise ValueError("purpose-specific revocation requires 'purposes' argument")

    if scope == "full":
        envelope["revocation_status"] = "revoked"
    elif scope == "purpose-specific" and purposes:
        # Remove purposes from authorized list
        envelope["authorized_purposes"] = [
            p for p in envelope.get("authorized_purposes", []) if p not in purposes
        ]
        envelope["revocation_status"] = "amended"

    envelope["revocation_status_updated_at"] = datetime.now(timezone.utc).isoformat()
    return envelope


def amend_envelope(envelope: RCPEnvelope, new_purposes: Optional[List[str]] = None, new_conditions: Optional[str] = None) -> RCPEnvelope:
    """
    RCP-1 AMEND: update purposes or conditions.

    Args:
        envelope: The envelope to amend
        new_purposes: Optional replacement authorized_purposes
        new_conditions: Optional replacement conditions

    Returns:
        Updated envelope with status 'amended'

    Note:
        In a production system, this would:
        - Verify that the caller has custodial_authority standing
        - Record the previous state in an audit log
        - Notify downstream systems
    """
    if envelope["revocation_status"] in ["revoked", "disputed"]:
        raise ValueError(f"Cannot amend envelope in status {envelope['revocation_status']}")

    if new_purposes:
        envelope["authorized_purposes"] = new_purposes
    if new_conditions:
        envelope["conditions"] = new_conditions

    envelope["revocation_status"] = "amended"
    envelope["revocation_status_updated_at"] = datetime.now(timezone.utc).isoformat()
    return envelope


def serialize_envelope(envelope: RCPEnvelope) -> str:
    """Serialize envelope to JSON for storage (e.g., in table metadata)"""
    return json.dumps(envelope)


def deserialize_envelope(json_str: str) -> RCPEnvelope:
    """Deserialize envelope from JSON"""
    return json.loads(json_str)


# Example usage
if __name__ == "__main__":
    # Example 1: Create envelope for Māori health survey
    envelope = create_envelope(
        dataset_id="maori-health-survey-2024",
        custodial_authority={
            "id": "https://www.tewaka.maori.nz",
            "name": "Te Waka",
            "type": "collective",
        },
        authorized_purposes=["iwi-health-research", "non-commercial", "anonymised-aggregate-only"],
        relational_obligations=["return-to-community", "tapu"],
        consent_record_id="https://www.tewaka.maori.nz/consent/2024-001",
        conditions="Data may not be used in commercial AI training. Results must be returned to the community within 12 months."
    )

    print("Created envelope:")
    print(json.dumps(envelope, indent=2))

    # Example 2: Query before training
    result = query_envelope(envelope, action="iwi-health-research")
    print(f"\nQuery for 'iwi-health-research': permitted={result['permitted']}")

    result = query_envelope(envelope, action="commercial-ai-training")
    print(f"Query for 'commercial-ai-training': permitted={result['permitted']}")

    # Example 3: Revoke
    revoked = revoke_envelope(envelope.copy(), scope="full")
    print(f"\nAfter REVOKE: status={revoked['revocation_status']}")

    result = query_envelope(revoked, action="iwi-health-research")
    print(f"Query after revoke: permitted={result['permitted']}")
