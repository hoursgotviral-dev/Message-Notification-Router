from datetime import datetime, timezone
import re

def _parse_date(d_str):
    if not d_str:
        return None
    try:
        if d_str.endswith("Z"):
            d_str = d_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(d_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None

def contains_keyword(text, keywords):
    if not text:
        return False
    text = text.lower()
    for kw in keywords:
        pattern = r'\b' + re.escape(kw.lower()) + r'\b'
        if re.search(pattern, text):
            return True
    return False

def should_prefilter_mute(bundle: dict, min_dismissals: int = 3,
                          recency_days: int = 30,
                          urgency_keywords: list[str] = None) -> tuple[bool, str]:
    """
    Returns (True, reason) only if ALL hold:
      1. bundle["sender_events"] has >= min_dismissals events of type "dismissed" or "reported"
      2. ALL those dismiss/report events are within recency_days of bundle["message"]["created_at"]. 
         If any relevant event is older, do NOT prefilter -- return (False, "").
      3. bundle["message"]["message_text"] does NOT contain any urgency_keywords.
      4. bundle.get("media_content") also does NOT contain those keywords.
    """
    if urgency_keywords is None:
        urgency_keywords = ["urgent", "emergency", "asap", "help", "call me", "now"]

    msg = bundle.get("message", {})
    current_time = _parse_date(msg.get("created_at"))
    if not current_time:
        return False, ""

    hist_messages = {m["message_id"]: m for m in bundle.get("sender_history", [])}
    
    events = bundle.get("sender_history_events", [])
    if not events and "sender_events" in bundle:
        events = bundle["sender_events"]
        
    dismiss_events = []
    for ev in events:
        is_dismissed = ev.get("notification_dismissed") in (1, True, "1", "True", "true", 1.0)
        is_reported = ev.get("message_reported") in (1, True, "1", "True", "true", 1.0)
        if is_dismissed or is_reported:
            dismiss_events.append(ev)
            
    if len(dismiss_events) < min_dismissals:
        return False, ""
        
    for ev in dismiss_events:
        mid = ev.get("message_id")
        hist_msg = hist_messages.get(mid)
        if hist_msg:
            hist_dt = _parse_date(hist_msg.get("created_at"))
            if hist_dt:
                diff_days = (current_time - hist_dt).days
                if diff_days > recency_days or diff_days < 0:
                    return False, ""
        else:
            # If we don't have the historical message to verify date, fail safe
            return False, ""

    if contains_keyword(str(msg.get("message_text") or ""), urgency_keywords):
        return False, ""
        
    if contains_keyword(str(bundle.get("media_content") or ""), urgency_keywords):
        return False, ""
        
    return True, "repeated recent dismissals, no urgency signal"
