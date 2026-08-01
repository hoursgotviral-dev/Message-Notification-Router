import os
import pandas as pd

def load_tables(dataset_dir: str) -> dict:
    tables = {}
    
    def load_and_index(filename, index_cols):
        path = os.path.join(dataset_dir, filename)
        if os.path.exists(path):
            df = pd.read_csv(path)
            if not df.empty:
                if isinstance(index_cols, list):
                    df = df.drop_duplicates(subset=index_cols, keep='last')
                else:
                    df = df.drop_duplicates(subset=[index_cols], keep='last')
                return df.set_index(index_cols, drop=False)
        return pd.DataFrame()

    tables['messages'] = load_and_index('messages.csv', 'message_id')
    tables['users'] = load_and_index('users.csv', 'user_id')
    tables['groups'] = load_and_index('groups.csv', 'group_id')
    tables['group_members'] = load_and_index('group_members.csv', ['group_id', 'user_id'])
    tables['business_accounts'] = load_and_index('business_accounts.csv', 'business_id')
    tables['user_business_history'] = load_and_index('user_business_history.csv', ['user_id', 'business_id'])
    tables['images'] = load_and_index('images.csv', 'image_id')
    tables['voice_notes'] = load_and_index('voice_notes.csv', 'voice_note_id')
    
    path_mh = os.path.join(dataset_dir, 'message_history.csv')
    if os.path.exists(path_mh):
        df_mh = pd.read_csv(path_mh)
        if not df_mh.empty:
            df_mh = df_mh.sort_values('created_at', ascending=False)
            tables['message_history'] = df_mh.groupby(['user_id', 'sender_user_id'])
        else:
            tables['message_history'] = pd.DataFrame().groupby(lambda x: x)
    else:
        tables['message_history'] = pd.DataFrame().groupby(lambda x: x)

    tables['message_events'] = load_and_index('message_events.csv', 'message_id')

    path_dns = os.path.join(dataset_dir, 'daily_notification_summary.csv')
    if os.path.exists(path_dns):
        df_dns = pd.read_csv(path_dns)
        if not df_dns.empty:
            df_dns = df_dns.sort_values('date', ascending=False)
            tables['daily_notification_summary'] = df_dns.groupby('user_id')
        else:
            tables['daily_notification_summary'] = pd.DataFrame().groupby(lambda x: x)
    else:
        tables['daily_notification_summary'] = pd.DataFrame().groupby(lambda x: x)

    return tables


def build_message_bundle(message_id: str, t: dict) -> dict:
    bundle = {}
    
    df_msg = t.get('messages')
    if df_msg is None or df_msg.empty or message_id not in df_msg.index:
        return bundle
        
    msg_row = df_msg.loc[message_id].to_dict()
    bundle['message'] = msg_row
    
    user_id = msg_row.get('user_id')
    
    df_users = t.get('users')
    if df_users is not None and not df_users.empty and user_id in df_users.index:
        bundle['user'] = df_users.loc[user_id].to_dict()
    else:
        bundle['user'] = {}

    conv_type = msg_row.get('conversation_type')
    
    if conv_type == 'group':
        group_id = msg_row.get('group_id')
        df_groups = t.get('groups')
        if df_groups is not None and not df_groups.empty and group_id in df_groups.index:
            bundle['group'] = df_groups.loc[group_id].to_dict()
        else:
            bundle['group'] = {}
            
        df_gm = t.get('group_members')
        if df_gm is not None and not df_gm.empty and (group_id, user_id) in df_gm.index:
            bundle['group_member'] = df_gm.loc[(group_id, user_id)].to_dict()
        else:
            bundle['group_member'] = {}

    elif conv_type == 'business':
        business_id = msg_row.get('business_id')
        df_biz = t.get('business_accounts')
        if df_biz is not None and not df_biz.empty and business_id in df_biz.index:
            bundle['business'] = df_biz.loc[business_id].to_dict()
        else:
            bundle['business'] = {}
            
        df_ubh = t.get('user_business_history')
        if df_ubh is not None and not df_ubh.empty and (user_id, business_id) in df_ubh.index:
            bundle['user_business_history'] = df_ubh.loc[(user_id, business_id)].to_dict()
        else:
            bundle['user_business_history'] = {}

    media_type = msg_row.get('media_type')
    media_id = msg_row.get('media_id')
    if pd.notna(media_id):
        if media_type == 'image':
            df_img = t.get('images')
            if df_img is not None and not df_img.empty and media_id in df_img.index:
                bundle['image'] = df_img.loc[media_id].to_dict()
        elif media_type == 'voice':
            df_voice = t.get('voice_notes')
            if df_voice is not None and not df_voice.empty and media_id in df_voice.index:
                bundle['voice_note'] = df_voice.loc[media_id].to_dict()

    sender_user_id = msg_row.get('sender_user_id')
    bundle['sender_history'] = []
    bundle['sender_history_events'] = []
    
    mh_group = t.get('message_history')
    if mh_group is not None:
        try:
            hist_df = mh_group.get_group((user_id, sender_user_id))
            bundle['sender_history'] = hist_df.to_dict('records')
            
            df_ev = t.get('message_events')
            if df_ev is not None and not df_ev.empty:
                hist_ids = hist_df['message_id'].tolist()
                valid_ids = [mid for mid in hist_ids if mid in df_ev.index]
                if valid_ids:
                    events = df_ev.loc[valid_ids]
                    if isinstance(events, pd.Series):
                        bundle['sender_history_events'] = [events.to_dict()]
                    else:
                        bundle['sender_history_events'] = events.to_dict('records')
        except KeyError:
            pass
        except Exception:
            pass

    dns_group = t.get('daily_notification_summary')
    bundle['daily_notification_summary'] = []
    if dns_group is not None:
        try:
            dns_df = dns_group.get_group(user_id)
            bundle['daily_notification_summary'] = dns_df.to_dict('records')
        except KeyError:
            pass
        except Exception:
            pass

    return bundle


def evidence_candidates(bundle: dict, max_n: int = 5) -> list:
    hist = bundle.get('sender_history', [])
    return [msg['message_id'] for msg in hist[:max_n]]
