import pytest
from safety_gate import apply_safety_gates

def test_unverified_business_payment_request():
    # Unverified business + payment request -> hard override, mute, scam.
    bundle = {
        "message": {"message_text": "Please send your payment immediately."},
        "business": {"verified": 0},
        "user_business_history": {"activity_count_180d": 5} # bypass rule 1 if needed
    }
    res = apply_safety_gates(bundle)
    assert res is not None
    assert res[0] == "mute"
    assert res[1] == "scam"
    assert "unverified business" in res[2].lower()

def test_muted_group_user_name_call_me():
    # Muted group + user's name + "call me" -> upgrade, notify, urgent.
    bundle = {
        "message": {"conversation_type": "group", "message_text": "hey u123, call me now"},
        "group_member": {"group_muted_by_user": 1},
        "user": {"user_id": "u123"},
        "user_business_history": {"activity_count_180d": 5} # bypass rule 1
    }
    res = apply_safety_gates(bundle)
    assert res is not None
    assert res[0] == "notify"
    assert res[1] == "urgent"
    assert "direct urgent mention" in res[2].lower()

def test_muted_group_scam_wins_over_mention():
    # Muted group + scam payment request even with direct mention -> hard override wins, mute, scam.
    bundle = {
        "message": {"conversation_type": "group", "message_text": "u123, you are a winner! send payment to claim your prize."},
        "group_member": {"group_muted_by_user": 1},
        "user": {"user_id": "u123"},
        "user_business_history": {} # triggers rule 1: phishing/payment with NO prior history
    }
    res = apply_safety_gates(bundle)
    assert res is not None
    assert res[0] == "mute" # hard override wins
    assert res[1] == "scam"
    assert "phishing or payment" in res[2].lower()

def test_normal_message_nothing_triggers():
    # Normal message, nothing triggers -> returns None
    bundle = {
        "message": {"conversation_type": "personal", "message_text": "Hey, what are you up to today?"},
        "user": {"user_id": "u123"},
        "user_business_history": {"activity_count_180d": 5}
    }
    res = apply_safety_gates(bundle)
    assert res is None
