import csv
import json
from llm_client import call_model
from prefilter import should_prefilter_mute
from safety_gate import apply_safety_gates
from prompt_template import build_prompt, load_few_shot_from_samples
from validate_evidence import validate_evidence_ids

def format_evidence(candidates: list) -> str:
    if not candidates or candidates == ["none"]:
        return "none"
    return ";".join(candidates)

def run_sample_test():
    few_shot = load_few_shot_from_samples('../dataset/sample_messages.csv')
    
    with open('../dataset/sample_messages.csv', 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
        
    print(f"Loaded {len(rows)} rows from sample_messages.csv")
    
    with open('test_output.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"])
        writer.writeheader()
        
        for row in rows:
            message_id = row['message_id']
            # minimal bundle
            bundle = {
                "message": {
                    "message_id": message_id,
                    "message_text": row.get("message_text", ""),
                    "conversation_type": row.get("conversation_type", ""),
                    "forwarded_count": int(row.get("forwarded_count", 0)) if row.get("forwarded_count") else 0,
                    "media_type": row.get("media_type", ""),
                    "media_id": row.get("media_id", "")
                },
                "user": {"user_id": row.get("user_id", "")},
                "group_member": {},
                "business": {},
                "user_business_history": {},
                "sender_history": [],
                "sender_events": {}
            }
            
            # 1. Prefilter
            prefiltered, pref_reason = should_prefilter_mute(bundle)
            if prefiltered:
                writer.writerow({
                    "message_id": message_id, "action": "mute", "message_type": "unknown",
                    "reason": pref_reason, "confidence": 0.8, "evidence_message_ids": "none"
                })
                continue
                
            # 2. Safety Gate
            gate = apply_safety_gates(bundle)
            if gate:
                action, msg_type, reason, conf = gate
                writer.writerow({
                    "message_id": message_id, "action": action, "message_type": msg_type,
                    "reason": reason, "confidence": conf, "evidence_message_ids": "none"
                })
                continue
                
            # 3. LLM
            prompt_list = build_prompt(bundle, few_shot)
            sys_str = prompt_list[0]["content"]
            user_str = prompt_list[1]["content"]
            
            try:
                res = call_model(user_str, system=sys_str, response_format="json_object")
                raw_text = res.get("text", "{}").strip()
                if raw_text.startswith("```json"): raw_text = raw_text[7:]
                elif raw_text.startswith("```"): raw_text = raw_text[3:]
                if raw_text.endswith("```"): raw_text = raw_text[:-3]
                
                parsed = json.loads(raw_text.strip())
                
                # In minimal bundle without history, validate_evidence_ids might strip all evidence.
                # We'll just pass raw evidence for test output, or pass through validation.
                ev_ids = parsed.get("evidence_message_ids", [])
                valid_ev = validate_evidence_ids(ev_ids, bundle)
                
                writer.writerow({
                    "message_id": message_id,
                    "action": parsed.get("action", "digest"),
                    "message_type": parsed.get("message_type", "unknown"),
                    "reason": parsed.get("reason", "LLM decided"),
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "evidence_message_ids": format_evidence(valid_ev)
                })
            except Exception as e:
                print(f"Error on {message_id}: {e}")
                writer.writerow({
                    "message_id": message_id, "action": "digest", "message_type": "unknown",
                    "reason": "processing error", "confidence": 0.0, "evidence_message_ids": "none"
                })
                
if __name__ == '__main__':
    run_sample_test()
