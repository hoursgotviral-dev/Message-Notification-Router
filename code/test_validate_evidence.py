import pytest
from validate_evidence import validate_evidence_ids

def test_all_valid():
    bundle = {
        "sender_history": [
            {"message_id": "m1"},
            {"message_id": "m2"},
            {"message_id": "m3"}
        ]
    }
    claimed = ["m1", "m3"]
    res = validate_evidence_ids(claimed, bundle)
    assert res == ["m1", "m3"]

def test_some_hallucinated():
    bundle = {
        "sender_history": [
            {"message_id": "m1"},
            {"message_id": "m2"}
        ]
    }
    claimed = ["m1", "m_hallucinated", "m2", "fake_id"]
    res = validate_evidence_ids(claimed, bundle)
    assert res == ["m1", "m2"]

def test_empty_or_malformed_input():
    bundle = {
        "sender_history": [
            {"message_id": "m1"}
        ]
    }
    # Empty list
    assert validate_evidence_ids([], bundle) == ["none"]
    # None instead of list
    assert validate_evidence_ids(None, bundle) == ["none"]
    # "none" literal string passed accidentally
    assert validate_evidence_ids("none", bundle) == ["none"]
    
    # Bundle has no history
    empty_bundle = {}
    assert validate_evidence_ids(["m1"], empty_bundle) == ["none"]
