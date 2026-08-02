import pandas as pd
import argparse
import sys
import os

def validate(actual_csv_path: str, dataset_messages_path: str, dataset_history_path: str):
    print(f"Validating {actual_csv_path}...")
    if not os.path.exists(actual_csv_path):
        print(f"Error: {actual_csv_path} not found.")
        sys.exit(1)
    if not os.path.exists(dataset_messages_path):
        print(f"Error: {dataset_messages_path} not found.")
        sys.exit(1)
    if not os.path.exists(dataset_history_path):
        print(f"Error: {dataset_history_path} not found.")
        sys.exit(1)

    actual = pd.read_csv(actual_csv_path)
    messages = pd.read_csv(dataset_messages_path)
    
    history_ids = set()
    if os.path.exists(dataset_history_path):
        history = pd.read_csv(dataset_history_path)
        if 'message_id' in history.columns:
            history_ids = set(history['message_id'].astype(str))
    
    actual_count = len(actual)
    expected_count = len(messages)
    print(f"1. Row count -> Actual: {actual_count}, Expected: {expected_count}")
    if actual_count != expected_count:
        print("FAIL: Row counts do not match.")
        sys.exit(1)

    if actual['message_id'].duplicated().any():
        print("FAIL: Duplicate message_id found.")
        sys.exit(1)
    print("2. No duplicate message_id -> PASS")

    if actual.isnull().any().any():
        print("FAIL: Null values found in output.")
        sys.exit(1)
    if actual.astype(str).apply(lambda col: col.str.strip() == "").any().any():
        print("FAIL: Empty string values found in output.")
        sys.exit(1)
    print("3. No null/empty values -> PASS")

    valid_actions = {"notify", "digest", "mute"}
    if not actual['action'].isin(valid_actions).all():
        invalid = actual[~actual['action'].isin(valid_actions)]['action'].unique()
        print(f"FAIL: Invalid actions found: {invalid}")
        sys.exit(1)
    print("4. Every action in valid set -> PASS")

    valid_types = {"personal", "urgent", "event", "payment", "business_update", "promotion", "greeting", "forward", "spam", "scam", "unknown"}
    if not actual['message_type'].isin(valid_types).all():
        invalid = actual[~actual['message_type'].isin(valid_types)]['message_type'].unique()
        print(f"FAIL: Invalid message_types found: {invalid}")
        sys.exit(1)
    print("5. Every message_type in valid set -> PASS")

    try:
        conf_floats = actual['confidence'].astype(float)
        if not conf_floats.between(0, 1).all():
            print("FAIL: Confidence values out of range [0,1].")
            sys.exit(1)
    except ValueError:
        print("FAIL: Confidence values could not be parsed as float.")
        sys.exit(1)
    print("6. Confidence values in [0,1] -> PASS")

    for idx, row in actual.iterrows():
        ev = str(row['evidence_message_ids']).strip()
        if ev.lower() != "none" and ev != "":
            ids = [e.strip() for e in ev.split(";")]
            for eid in ids:
                if eid not in history_ids:
                    print(f"FAIL: Row {row['message_id']} has hallucinated/dangling evidence ID: {eid}")
                    sys.exit(1)
    print("7. Evidence IDs exist in message_history.csv -> PASS")

    print("\n========== VALIDATION SUMMARY ==========")
    print("All validation checks PASSED.")
    print("========================================")
    sys.exit(0)

def evaluate(sample_csv_path: str, output_csv_path: str):
    if not os.path.exists(sample_csv_path):
        print(f"Error: Expected dataset file not found at {sample_csv_path}")
        sys.exit(1)
    if not os.path.exists(output_csv_path):
        print(f"Error: Actual output file not found at {output_csv_path}")
        sys.exit(1)

    expected = pd.read_csv(sample_csv_path)
    actual = pd.read_csv(output_csv_path)
    
    if "message_id" not in expected.columns or "message_id" not in actual.columns:
        print("Error: Both CSVs must have a 'message_id' column.")
        sys.exit(1)
        
    merged = pd.merge(expected, actual, on="message_id", suffixes=('_exp', '_act'))
    
    if merged.empty:
        print("No matching message_ids found between the two files.")
        sys.exit(0)
        
    action_matches = 0
    type_matches = 0
    total = len(merged)
    mismatch_count = 0
    
    for idx, row in merged.iterrows():
        msg_id = row["message_id"]
        act_exp = str(row.get("action_exp", "")).strip().lower()
        act_act = str(row.get("action_act", "")).strip().lower()
        
        type_exp = str(row.get("message_type_exp", "")).strip().lower()
        type_act = str(row.get("message_type_act", "")).strip().lower()
        
        reason_exp = str(row.get("reason_exp", ""))
        reason_act = str(row.get("reason_act", ""))
        
        ev_exp = str(row.get("evidence_message_ids_exp", ""))
        ev_act = str(row.get("evidence_message_ids_act", ""))
        
        is_mismatch = (act_exp != act_act) or (type_exp != type_act)
        
        if act_exp == act_act:
            action_matches += 1
        if type_exp == type_act:
            type_matches += 1
            
        print(f"--- Message ID: {msg_id} ---")
        print(f"Action: Expected [{act_exp}] vs Actual [{act_act}]")
        print(f"Type:   Expected [{type_exp}] vs Actual [{type_act}]")
        print(f"Reason (Expected): {reason_exp}")
        print(f"Reason (Actual):   {reason_act}")
        print(f"Evidence (Expected): {ev_exp}")
        print(f"Evidence (Actual):   {ev_act}")
        
        if is_mismatch and mismatch_count < 5:
            mismatch_count += 1
            print(f">>> FULL MISMATCH ROW (Count: {mismatch_count}) <<<")
            import pprint
            pprint.pprint(row.to_dict())
            
        print("-" * 50)
        
    action_pct = (action_matches / total) * 100
    type_pct = (type_matches / total) * 100
    
    print("\n========== EVALUATION SUMMARY ==========")
    print(f"Rows compared: {total}")
    print(f"Action match rate:       {action_pct:.1f}% ({action_matches}/{total})")
    print(f"Message Type match rate: {type_pct:.1f}% ({type_matches}/{total})")
    print("========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate output against ground truth or validate format")
    # Assuming this script is run from the `code` directory as `python evaluation/main.py`
    parser.add_argument("--expected", default="../dataset/sample_messages.csv", help="Path to expected CSV (sample_messages.csv)")
    parser.add_argument("--actual", default="output.csv", help="Path to actual CSV (output.csv)")
    parser.add_argument("--validate-only", action="store_true", help="Run validation checks instead of accuracy comparison")
    parser.add_argument("--dataset-messages", default="../dataset/messages.csv", help="Path to dataset messages.csv")
    parser.add_argument("--dataset-history", default="../dataset/message_history.csv", help="Path to dataset message_history.csv")
    args = parser.parse_args()
    
    if args.validate_only:
        validate(args.actual, args.dataset_messages, args.dataset_history)
    else:
        evaluate(args.expected, args.actual)
