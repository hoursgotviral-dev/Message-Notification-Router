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

def test_muted_group_urgency_language():
    # Muted group + urgency language -> upgrade, notify, urgent.
    bundle = {
        "message": {"conversation_type": "group", "message_text": "we need help now"},
        "group_member": {"group_muted_by_user": 1},
        "user_business_history": {"activity_count_180d": 5}
    }
    res = apply_safety_gates(bundle)
    assert res is not None
    assert res[0] == "notify"
    assert res[1] == "urgent"
    assert "urgent language" in res[2].lower()

def test_muted_group_bare_user_id_does_not_upgrade():
    # Muted group + user_id without urgency language -> NO upgrade.
    bundle = {
        "message": {"conversation_type": "group", "message_text": "u123 did you see the email?"},
        "group_member": {"group_muted_by_user": 1},
        "user": {"user_id": "u123"},
        "user_business_history": {"activity_count_180d": 5}
    }
    res = apply_safety_gates(bundle)
    assert res is None

def test_muted_group_scam_wins_over_urgency():
    # Muted group + scam payment request WITH urgency language -> hard override wins, mute, scam.
    bundle = {
        "message": {"conversation_type": "group", "message_text": "urgent! you are a winner! send payment asap to claim your prize."},
        "group_member": {"group_muted_by_user": 1},
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

def test_forward_chain_without_urgency():
    # Forward chain, fwd_count>=5, no urgency keyword but has forward_spam_kws -> mute, spam
    bundle = {
        "message": {"message_text": "forward this to ten people for luck changes", "forwarded_count": 7},
        "user_business_history": {"activity_count_180d": 5}
    }
    res = apply_safety_gates(bundle)
    assert res is not None
    assert res[0] == "mute"
    assert res[1] == "spam"
    assert "chain-message pattern" in res[2].lower()

def test_muted_group_mention_upgrades_without_urgency():
    # Muted group message with @mention and NO urgency keyword -> upgrade, notify, urgent
    bundle = {
        "message": {"conversation_type": "group", "message_text": "@u_001 doctor appointment moved... please confirm", "user_id": "u_001"},
        "group_member": {"group_muted_by_user": 1},
        "user_business_history": {"activity_count_180d": 5}
    }
    res = apply_safety_gates(bundle)
    assert res is not None
    assert res[0] == "notify"
    assert res[1] == "urgent"
    assert "direct mention overrides group mute" in res[2].lower()

def test_legitimate_payment_mention_does_not_trigger():
    # Bare payment keyword with no urgency/links/sensitive info -> None
    bundle = {
        "message": {"conversation_type": "group", "message_text": "Can you join with failed-payment screenshots?"},
        "user_business_history": {}
    }
    res = apply_safety_gates(bundle)
    assert res is None

def test_legitimate_claim_mention_does_not_trigger():
    # Bare claim keyword with no urgency/links/sensitive info -> None
    bundle = {
        "message": {"conversation_type": "personal", "message_text": "claim your prescription pickup details"},
        "user_business_history": {}
    }
    res = apply_safety_gates(bundle)
    assert res is None
