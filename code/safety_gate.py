import re

def contains_any(text, keywords):
    if not text: 
        return False
    text = text.lower()
    for kw in keywords:
        if re.search(r'\b' + re.escape(kw.lower()) + r'\b', text):
            return True
    return False

def get_full_text(bundle: dict) -> str:
    msg_text = str(bundle.get("message", {}).get("message_text") or "")
    media_text = str(bundle.get("media_content") or "")
    return (msg_text + " " + media_text).strip()

def hard_override_check(bundle: dict) -> tuple[str, str, str, float] | None:
    full_text = get_full_text(bundle).lower()
    msg = bundle.get("message", {})
    
    phishing_kws = ["prize", "win", "winner", "claim", "urgent payment", "phishing", "scam", "free money", "lottery"]
    payment_kws = ["pay", "payment", "bank", "credit card", "ssn", "social security", "account number", "transfer", "wire", "invoice"]
    urgency_kws = ["urgent", "emergency", "asap", "help", "call me", "now"]

    has_phishing_or_payment = contains_any(full_text, phishing_kws) or contains_any(full_text, payment_kws)
    
    if has_phishing_or_payment:
        ubh = bundle.get("user_business_history", {})
        has_history = False
        if ubh:
            # Check for prior orders/opt-ins
            acts = ubh.get("activity_count_180d")
            if acts is not None and int(acts) > 0:
                has_history = True
            elif ubh.get("allows_promotions") in (1, True, "1", "True", "true", 1.0):
                has_history = True
                
        if not has_history:
            return ("mute", "scam", "phishing or payment request with no prior business history", 0.9)

    biz = bundle.get("business")
    if biz:
        is_verified = biz.get("verified") in (1, True, "1", "True", "true", 1.0)
        if not is_verified and contains_any(full_text, payment_kws):
            return ("mute", "scam", "unverified business requesting payment or personal info", 0.9)
            
    fwd_count = msg.get("forwarded_count", 0)
    try:
        fwd_count = int(fwd_count) if fwd_count else 0
    except ValueError:
        fwd_count = 0
        
    if fwd_count >= 5 and contains_any(full_text, urgency_kws):
        return ("mute", "spam", "highly forwarded message with urgency language", 0.9)
        
    return None

def upgrade_override_check(bundle: dict) -> tuple[str, str, str, float] | None:
    msg = bundle.get("message", {})
    if msg.get("conversation_type") != "group":
        return None
        
    gm = bundle.get("group_member", {})
    is_muted = gm.get("group_muted_by_user") in (1, True, "1", "True", "true", 1.0)
    if not is_muted:
        return None
        
    full_text = get_full_text(bundle).lower()
    
    user_id = bundle.get("user", {}).get("user_id")
    has_mention = False
    if user_id and str(user_id).lower() in full_text:
        has_mention = True
        
    upgrade_urgency_kws = ["urgent", "emergency", "call me", "asap", "help now"]
    has_urgency = contains_any(full_text, upgrade_urgency_kws)
    
    if has_mention or has_urgency:
        return ("notify", "urgent", "direct urgent mention overrides group mute", 0.85)
        
    return None

def apply_safety_gates(bundle: dict) -> tuple[str, str, str, float] | None:
    hard = hard_override_check(bundle)
    if hard:
        return hard
    upgrade = upgrade_override_check(bundle)
    if upgrade:
        return upgrade
    return None
