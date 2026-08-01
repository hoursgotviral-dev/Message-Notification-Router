import json
import pandas as pd
import os

ACTIONS = ["notify", "digest", "mute"]
MESSAGE_TYPES = [
    "personal", "urgent", "event", "payment", "business_update",
    "promotion", "greeting", "forward", "spam", "scam", "unknown"
]

SYSTEM_PROMPT = f"""You are an intelligent notification-routing engine for WhatsApp.
Your goal is to decide whether a new incoming message should interrupt the user now (notify), wait for later (digest), or be suppressed entirely (mute).

CRITICAL INSTRUCTIONS:
1. You must output ONLY a valid JSON object. No markdown fences, no preamble, no postscript.
2. The JSON object must contain exactly these keys:
   - "action": string, MUST be exactly one of {ACTIONS}.
   - "message_type": string, MUST be exactly one of {MESSAGE_TYPES}.
   - "reason": string, a short explanation for your decision.
   - "confidence": float between 0.0 and 1.0.
   - "evidence_message_ids": list of strings, IDs of historical messages supporting the decision (if any), or empty list/["none"].

DECISION PRIORITY (in strict order):
1. HARD OVERRIDE (Scam/Phishing): If the message contains clear scam, phishing, or unsafe content, you MUST ALWAYS output action="mute", regardless of the user's usual engagement with that sender.
2. UPGRADE CASE (Urgent Mention): If the message is inside a muted group, but is a genuine urgent direct mention of this user, you MUST output action="notify" (group mute status does not suppress this).
3. PERSONALIZATION: Otherwise, personalize the decision using the provided context:
   - The user's quiet hours / do-not-disturb window.
   - The user's historical engagement (opens/replies vs dismissals/reports).
   - Group role and mute state.
   - Business verification and past order history.
   - Repetition and forward patterns.
4. REPEATED DISMISSALS: If there are repeated dismissals/reports for this sender with no overriding exceptions, output action="mute".

EVIDENCE IDS:
You MUST ONLY cite evidence_message_ids that are actually present in the provided sender history. NEVER invent or hallucinate IDs.
"""

def format_bundle_for_prompt(bundle: dict) -> str:
    compact = bundle.copy()
    
    hist = compact.get("sender_history", [])
    if len(hist) > 15:
        compact["sender_history"] = hist[:15]
        
    events = compact.get("sender_history_events", [])
    if len(events) > 15:
        compact["sender_history_events"] = events[:15]
        
    return json.dumps(compact, separators=(',', ':'))

def build_prompt(bundle: dict, few_shot_examples: str = "") -> list:
    """
    Return a messages list (system + user turns) ready for llm_client.call_model().
    """
    prompt = ""
    if few_shot_examples:
        prompt += f"Here are some reference examples to calibrate your routing:\n\n{few_shot_examples}\n\n"
        
    prompt += "Please evaluate the following message bundle and provide your JSON routing decision:\n"
    prompt += format_bundle_for_prompt(bundle)
    
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

def load_few_shot_from_samples(sample_csv_path: str, n: int = 4) -> str:
    if not os.path.exists(sample_csv_path):
        return ""
        
    df = pd.read_csv(sample_csv_path)
    if df.empty:
        return ""
        
    n = min(n, len(df))
    samples = df.head(n)
    
    few_shot_str = ""
    for idx, row in samples.iterrows():
        bundle_subset = {
            "message": {
                "message_text": row.get("message_text", ""),
                "conversation_type": row.get("conversation_type", ""),
            }
        }
        
        action = row.get("action", "")
        msg_type = row.get("message_type", "")
        reason = row.get("reason", "")
        conf = row.get("confidence", 0.0)
        evidence = row.get("evidence_message_ids", "")
        
        if pd.isna(evidence) or not evidence or str(evidence).strip().lower() == "none":
            evidence_list = ["none"]
        else:
            evidence_list = str(evidence).split(",")
            
        expected_out = {
            "action": action,
            "message_type": msg_type,
            "reason": reason,
            "confidence": conf,
            "evidence_message_ids": evidence_list
        }
        
        few_shot_str += f"Input:\n{json.dumps(bundle_subset, separators=(',', ':'))}\n"
        few_shot_str += f"Output:\n{json.dumps(expected_out, separators=(',', ':'))}\n\n"
        
    return few_shot_str.strip()
