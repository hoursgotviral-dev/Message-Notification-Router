def validate_evidence_ids(claimed_ids: list[str], bundle: dict) -> list[str]:
    """
    Return only the subset of claimed_ids present in bundle["sender_history"]'s 
    message_id values. If none match, return ["none"]. 
    Never raise on malformed input -- return ["none"] defensively.
    """
    try:
        if not isinstance(claimed_ids, list):
            return ["none"]
            
        hist = bundle.get("sender_history", [])
        valid_ids = set()
        
        if isinstance(hist, list):
            for msg in hist:
                if isinstance(msg, dict) and "message_id" in msg:
                    valid_ids.add(str(msg["message_id"]))
                
        filtered = []
        for cid in claimed_ids:
            if str(cid) in valid_ids:
                filtered.append(str(cid))
                
        if not filtered:
            return ["none"]
            
        return filtered
    except Exception:
        return ["none"]
