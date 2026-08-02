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
    
    phishing_kws = ["prize", "win", "winner", "urgent payment", "phishing", "scam", "free money", "lottery"]
    payment_kws = ["pay", "payment", "bank", "credit card", "ssn", "social security", "account number", "transfer", "wire", "invoice", "claim"]
    urgency_kws = ["urgent", "emergency", "asap", "help", "call me", "now"]
    sensitive_kws = ["otp", "pin", "verification code", "login", "password", "card number", "cvv"]
    
    has_phishing = contains_any(full_text, phishing_kws)
    has_payment = contains_any(full_text, payment_kws)
    has_urgency = contains_any(full_text, urgency_kws)
    has_sensitive = contains_any(full_text, sensitive_kws)
    has_suspicious_link = bool(re.search(r'(bit\.ly|http://)', full_text))

    has_phishing_or_payment = has_phishing or (has_payment and (has_suspicious_link or has_urgency or has_sensitive))
    
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
        
    forward_spam_kws = ["forward this", "share this", "do not ignore", "sending to all", "blessings", "luck changes", "share with"]
    if fwd_count >= 5:
        if contains_any(full_text, urgency_kws):
            return ("mute", "spam", "highly forwarded message with urgency language", 0.9)
        elif contains_any(full_text, forward_spam_kws):
            return ("mute", "spam", "highly forwarded chain-message pattern (mass-share request)", 0.9)
        
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
    
    upgrade_urgency_kws = ["urgent", "emergency", "call me", "asap", "help now"]
    has_urgency = contains_any(full_text, upgrade_urgency_kws)
    
    user_id = bundle.get("message", {}).get("user_id")
    has_mention = user_id and f"@{user_id}".lower() in full_text
    
    if has_urgency:
        return ("notify", "urgent", "urgent language overrides group mute", 0.85)
    elif has_mention:
        return ("notify", "urgent", "direct mention overrides group mute", 0.85)
        
    return None

def apply_safety_gates(bundle: dict) -> tuple[str, str, str, float] | None:
    hard = hard_override_check(bundle)
    if hard:
        return hard
    upgrade = upgrade_override_check(bundle)
    if upgrade:
        return upgrade
    return None
