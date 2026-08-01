import pytest
from prefilter import should_prefilter_mute

def test_fires_on_clean_history():
    bundle = {
        "message": {"created_at": "2023-02-01T12:00:00", "message_text": "hello there"},
        "sender_history": [
            {"message_id": "m1", "created_at": "2023-01-20T10:00:00"},
            {"message_id": "m2", "created_at": "2023-01-21T10:00:00"},
            {"message_id": "m3", "created_at": "2023-01-22T10:00:00"}
        ],
        "sender_history_events": [
            {"message_id": "m1", "notification_dismissed": 1},
            {"message_id": "m2", "notification_dismissed": 1},
            {"message_id": "m3", "message_reported": 1}
        ]
    }
    mute, reason = should_prefilter_mute(bundle)
    assert mute is True
    assert reason == "repeated recent dismissals, no urgency signal"

def test_doesnt_fire_when_stale():
    bundle = {
        "message": {"created_at": "2023-03-01T12:00:00", "message_text": "hello there"},
        "sender_history": [
            {"message_id": "m1", "created_at": "2022-12-01T10:00:00"}, # > 30 days old
            {"message_id": "m2", "created_at": "2023-02-21T10:00:00"},
            {"message_id": "m3", "created_at": "2023-02-22T10:00:00"}
        ],
        "sender_history_events": [
            {"message_id": "m1", "notification_dismissed": 1},
            {"message_id": "m2", "notification_dismissed": 1},
            {"message_id": "m3", "message_reported": 1}
        ]
    }
    mute, reason = should_prefilter_mute(bundle)
    assert mute is False

def test_doesnt_fire_when_urgency_in_text():
    bundle = {
        "message": {"created_at": "2023-02-01T12:00:00", "message_text": "hello there, need help now"},
        "sender_history": [
            {"message_id": "m1", "created_at": "2023-01-20T10:00:00"},
            {"message_id": "m2", "created_at": "2023-01-21T10:00:00"},
            {"message_id": "m3", "created_at": "2023-01-22T10:00:00"}
        ],
        "sender_history_events": [
            {"message_id": "m1", "notification_dismissed": 1},
            {"message_id": "m2", "notification_dismissed": 1},
            {"message_id": "m3", "message_reported": 1}
        ]
    }
    mute, reason = should_prefilter_mute(bundle)
    assert mute is False

def test_doesnt_fire_when_urgency_in_media():
    bundle = {
        "message": {"created_at": "2023-02-01T12:00:00", "message_text": "hello"},
        "media_content": "emergency broadcast",
        "sender_history": [
            {"message_id": "m1", "created_at": "2023-01-20T10:00:00"},
            {"message_id": "m2", "created_at": "2023-01-21T10:00:00"},
            {"message_id": "m3", "created_at": "2023-01-22T10:00:00"}
        ],
        "sender_history_events": [
            {"message_id": "m1", "notification_dismissed": 1},
            {"message_id": "m2", "notification_dismissed": 1},
            {"message_id": "m3", "message_reported": 1}
        ]
    }
    mute, reason = should_prefilter_mute(bundle)
    assert mute is False
