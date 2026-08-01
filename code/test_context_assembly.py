import os
import pandas as pd
from context_assembly import load_tables, build_message_bundle, evidence_candidates

def test_personal_message_bundle(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    
    pd.DataFrame([{
        'message_id': 'm1', 'user_id': 'u1', 'conversation_type': 'personal',
        'group_id': None, 'business_id': None, 'sender_user_id': 's1',
        'created_at': '2023-01-01', 'message_text': 'hi',
        'media_type': None, 'media_id': None
    }]).to_csv(dataset_dir / "messages.csv", index=False)
    
    pd.DataFrame([{'user_id': 'u1', 'messages_opened_30d': 5}]).to_csv(dataset_dir / "users.csv", index=False)
    
    t = load_tables(str(dataset_dir))
    bundle = build_message_bundle('m1', t)
    
    assert bundle['message']['message_id'] == 'm1'
    assert bundle['user']['user_id'] == 'u1'
    assert 'group' not in bundle
    assert 'business' not in bundle

def test_group_message_bundle(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    
    pd.DataFrame([{
        'message_id': 'm2', 'user_id': 'u1', 'conversation_type': 'group',
        'group_id': 'g1', 'business_id': None, 'sender_user_id': 's1',
        'created_at': '2023-01-01', 'message_text': 'hi team',
        'media_type': None, 'media_id': None
    }]).to_csv(dataset_dir / "messages.csv", index=False)
    
    pd.DataFrame([{'group_id': 'g1', 'group_name': 'Devs'}]).to_csv(dataset_dir / "groups.csv", index=False)
    pd.DataFrame([{'group_id': 'g1', 'user_id': 'u1', 'role': 'member'}]).to_csv(dataset_dir / "group_members.csv", index=False)
    
    t = load_tables(str(dataset_dir))
    bundle = build_message_bundle('m2', t)
    
    assert bundle['group']['group_id'] == 'g1'
    assert bundle['group_member']['role'] == 'member'

def test_evidence_candidates(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    
    pd.DataFrame([{
        'message_id': 'm3', 'user_id': 'u1', 'conversation_type': 'personal',
        'group_id': None, 'business_id': None, 'sender_user_id': 's1',
        'created_at': '2023-01-01T12:00:00', 'message_text': 'hi',
        'media_type': None, 'media_id': None
    }]).to_csv(dataset_dir / "messages.csv", index=False)
    
    pd.DataFrame([
        {'message_id': 'h1', 'user_id': 'u1', 'sender_user_id': 's1', 'created_at': '2023-01-01T10:00:00'},
        {'message_id': 'h2', 'user_id': 'u1', 'sender_user_id': 's1', 'created_at': '2023-01-01T11:00:00'},
        {'message_id': 'h3', 'user_id': 'u1', 'sender_user_id': 's2', 'created_at': '2023-01-01T11:30:00'}
    ]).to_csv(dataset_dir / "message_history.csv", index=False)
    
    t = load_tables(str(dataset_dir))
    bundle = build_message_bundle('m3', t)
    
    ev = evidence_candidates(bundle)
    assert len(ev) == 2
    assert ev[0] == 'h2'
    assert ev[1] == 'h1'
