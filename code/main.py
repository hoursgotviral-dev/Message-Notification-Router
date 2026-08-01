import os
import sys
import csv
import json
import logging
import argparse

from llm_client import call_model
from checkpoint import CheckpointRunner, FileStateStore

from context_assembly import load_tables, build_message_bundle
from media_preprocessing import get_media_content
from prefilter import should_prefilter_mute
from safety_gate import apply_safety_gates
from prompt_template import build_prompt, load_few_shot_from_samples
from validate_evidence import validate_evidence_ids

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Cost estimation constants (USD per token -> converted to INR)
USD_TO_INR = 83.0
COST_RATES_USD = {
    "gemini": {"input": 0.25 / 1e6, "output": 1.50 / 1e6},  # Rates for gemini-3.5-flash-lite
    "claude": {"input": 0.25 / 1e6, "output": 1.25 / 1e6},
    "openrouter": {"input": 0.0, "output": 0.0},
}

OUTPUT_FIELDNAMES = ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"]

def calculate_cost_inr(provider: str, usage: dict) -> float:
    if not usage or provider not in COST_RATES_USD:
        return 0.0
    
    in_tokens = 0
    out_tokens = 0
    
    if provider == "gemini":
        in_tokens = usage.get("promptTokenCount", 0)
        out_tokens = usage.get("candidatesTokenCount", 0)
    elif provider in ("claude", "openrouter"):
        in_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        out_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
        
    rates = COST_RATES_USD.get(provider, {"input": 0, "output": 0})
    cost_usd = (in_tokens * rates["input"]) + (out_tokens * rates["output"])
    return cost_usd * USD_TO_INR

def evidence_candidates(bundle: dict) -> list:
    hist = bundle.get("sender_history", [])
    return [str(m["message_id"]) for m in hist if "message_id" in m]

def format_evidence(candidates: list) -> str:
    if not candidates or candidates == ["none"]:
        return "none"
    return ";".join(candidates)

def process_row(message_id: str, tables: dict, few_shot: str) -> dict:
    safe_default = {
        "message_id": message_id,
        "action": "digest",
        "message_type": "unknown",
        "reason": "processing error, defaulted to digest",
        "confidence": 0.0,
        "evidence_message_ids": "none",
        "cost_inr": 0.0
    }
    
    try:
        # 1. build context bundle
        bundle = build_message_bundle(message_id, tables)
        
        # 2. handle media if present
        if bundle.get("media"):
            bundle["media_content"] = get_media_content(bundle)
            
        # 3. prefilter logic
        prefiltered, pref_reason = should_prefilter_mute(bundle)
        if prefiltered:
            return {
                "message_id": message_id,
                "action": "mute",
                "message_type": "unknown",
                "reason": pref_reason,
                "confidence": 0.8,
                "evidence_message_ids": format_evidence(evidence_candidates(bundle)),
                "cost_inr": 0.0
            }
            
        # 4. safety gate override
        gate_result = apply_safety_gates(bundle)
        if gate_result is not None:
            action, msg_type, reason, conf = gate_result
            return {
                "message_id": message_id,
                "action": action,
                "message_type": msg_type,
                "reason": reason,
                "confidence": conf,
                "evidence_message_ids": format_evidence(evidence_candidates(bundle)),
                "cost_inr": 0.0
            }
            
        # 5. LLM routing call
        try:
            prompt_list = build_prompt(bundle, few_shot)
            system_str = prompt_list[0]["content"]
            user_str = prompt_list[1]["content"]
            
            llm_res = call_model(user_str, system=system_str, response_format="json_object")
            cost = calculate_cost_inr(llm_res.get("provider_used"), llm_res.get("usage"))
            
            raw_text = llm_res.get("text", "{}")
            raw_text = raw_text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            parsed = json.loads(raw_text.strip())
            
            ev_ids = parsed.get("evidence_message_ids", [])
            valid_ev = validate_evidence_ids(ev_ids, bundle)
            
            return {
                "message_id": message_id,
                "action": parsed.get("action", "digest"),
                "message_type": parsed.get("message_type", "unknown"),
                "reason": parsed.get("reason", "LLM decided"),
                "confidence": float(parsed.get("confidence", 0.5)),
                "evidence_message_ids": format_evidence(valid_ev),
                "cost_inr": cost
            }
            
        except Exception as e:
            logger.error(f"Error in LLM step for {message_id}: {e}")
            return safe_default
            
    except Exception as e:
        logger.error(f"Error in pipeline for {message_id}: {e}")
        return safe_default

def make_chunk_step(chunk: list, tables: dict, few_shot: str, output_file: str, spend_cap: float, log_every: int):
    def step_func(state: dict) -> dict:
        file_exists = os.path.exists(output_file)
        is_empty = not file_exists or os.path.getsize(output_file) == 0
        
        results = []
        for msg_id in chunk:
            if state["total_cost"] >= spend_cap:
                logger.error(f"Spend cap of {spend_cap} INR exceeded! Halting.")
                raise RuntimeError("Spend cap exceeded")
                
            res = process_row(msg_id, tables, few_shot)
            
            state["total_cost"] += res.pop("cost_inr", 0.0)
            state["rows_processed"] += 1
            
            if state["rows_processed"] % log_every == 0:
                logger.info(f"Progress: {state['rows_processed']} rows | Cost: {state['total_cost']:.2f} INR")
                
            results.append(res)
            
        if results:
            with open(output_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
                if is_empty:
                    writer.writeheader()
                writer.writerows(results)
                
        return state
    return step_func

def main():
    if not any([os.getenv("GEMINI_API_KEY"), os.getenv("ANTHROPIC_API_KEY"), os.getenv("OPENROUTER_API_KEY")]):
        logger.error("No API key is set for any provider. Please set at least one.")
        sys.exit(1)
        
    spend_cap_inr = float(os.getenv("SPEND_CAP_INR", "500"))
    
    parser = argparse.ArgumentParser(description="LLM Orchestration Pipeline")
    parser.add_argument("--input", default="../dataset/messages.csv", help="Path to input CSV")
    parser.add_argument("--output", default="output.csv", help="Path to output CSV")
    parser.add_argument("--dataset-dir", default="../dataset/", help="Path to dataset directory")
    parser.add_argument("--checkpoint-dir", default=".checkpoints", help="Directory for checkpoints")
    parser.add_argument("--log-every", type=int, default=1, help="Log progress every N rows")
    parser.add_argument("--checkpoint-every", type=int, default=10, help="Checkpoint every N rows")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N rows (for testing)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    logger.info("Loading tables...")
    tables = load_tables(args.dataset_dir)
    
    few_shot = load_few_shot_from_samples(os.path.join(args.dataset_dir, "sample_messages.csv"))

    with open(args.input, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_message_ids = [row["message_id"] for row in reader if "message_id" in row]

    if args.limit:
        all_message_ids = all_message_ids[:args.limit]

    store = FileStateStore(directory=args.checkpoint_dir)
    run_id = os.path.basename(args.input).replace(".csv", "_run")
    if args.limit:
        run_id += f"_limit{args.limit}"
        
    runner = CheckpointRunner(run_id=run_id, store=store)
    
    chunks = [all_message_ids[i:i + args.checkpoint_every] for i in range(0, len(all_message_ids), args.checkpoint_every)]
    
    for i, chunk in enumerate(chunks):
        step_name = f"chunk_{i}"
        runner.add_step(step_name, make_chunk_step(chunk, tables, few_shot, args.output, spend_cap_inr, args.log_every))
        
    initial_state = {
        "total_cost": 0.0,
        "rows_processed": 0
    }
    
    logger.info(f"Starting pipeline. Spend cap: {spend_cap_inr} INR")
    final_state = runner.run(initial_state)
    
    logger.info("========== RUN SUMMARY ==========")
    logger.info(f"Total rows processed: {final_state['rows_processed']}")
    logger.info(f"Total cost estimate:  {final_state['total_cost']:.2f} INR")
    logger.info("=================================")

if __name__ == "__main__":
    main()
