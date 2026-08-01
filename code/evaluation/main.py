import pandas as pd
import argparse
import sys
import os

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
        print("-" * 50)
        
    action_pct = (action_matches / total) * 100
    type_pct = (type_matches / total) * 100
    
    print("\n========== EVALUATION SUMMARY ==========")
    print(f"Rows compared: {total}")
    print(f"Action match rate:       {action_pct:.1f}% ({action_matches}/{total})")
    print(f"Message Type match rate: {type_pct:.1f}% ({type_matches}/{total})")
    print("========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate output against ground truth")
    # Assuming this script is run from the `code` directory as `python evaluation/main.py`
    parser.add_argument("--expected", default="../dataset/sample_messages.csv", help="Path to expected CSV (sample_messages.csv)")
    parser.add_argument("--actual", default="output.csv", help="Path to actual CSV (output.csv)")
    args = parser.parse_args()
    
    evaluate(args.expected, args.actual)
