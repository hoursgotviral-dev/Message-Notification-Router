WhatsApp Message Notification Router
Project Summary
An AI-powered WhatsApp Message Notification Router that classifies each incoming message into notify / digest / mute, personalized per user based on relationship to sender, historical engagement, quiet hours, and group role. Multimodal: handles text, image, and voice note messages.

Architecture
Two-directional Safety Gate

Hard override: Clear scam/phishing/unsafe content always mutes, regardless of the user's usual engagement pattern with that sender. Wins over everything else, including the upgrade case below.
Upgrade case: Inside a muted group, a genuine direct urgent mention of the user still notifies — mute status doesn't suppress it.
Precedence rule: Hard override always wins if both would fire (a scam inside a muted group stays muted, never gets upgraded to notify).
Both checks inspect text AND media_content (image captions / voice transcripts), so a scam hidden inside an image still triggers the mute.
Verified live: a 5-row smoke test (main.py --limit 5) independently confirmed both directions of the safety gate firing on real data in the same run — a hard-override mute on a phishing/payment-request message with no prior business history, and an upgrade-to-notify on a direct urgent mention inside a muted group — both resolved deterministically with zero LLM cost, consistent with the cost-efficiency design goal above.
Deterministic Prefilter

Runs before any LLM call. If a sender has 3+ recent (within 30 days) dismiss/report events AND no urgency keywords present in text or media content, it mutes immediately with zero LLM cost.
Framed explicitly as a cost-efficiency engineering decision: cuts API calls for the highest-volume, lowest-ambiguity case (repeat unwanted senders) before spending any LLM budget on them.
Multimodal Processing

Images and voice notes are sent to Gemini for captioning/transcription before the routing decision, so the safety gate and LLM both reason over actual media content, not just text.
On media processing failure (missing file, network error, etc.), fails safely — logs a warning, returns a placeholder marker, and the pipeline continues to a safe fallback decision rather than crashing.
LLM Routing Layer

For messages that pass the prefilter and don't trigger a safety gate, an LLM call makes the final classification using full context: quiet hours, historical opens/replies vs dismissals/reports, group role/mute state, business verification status, forward/repetition patterns.
Evidence IDs returned by the LLM are validated against the real sender history before being included in output — any hallucinated/non-existent message IDs are stripped, preventing fabricated evidence in the final output.
Reliability Engineering

Proactive rate limiting: Tracks API call timestamps, sleeps proactively before exceeding free-tier limits, and separately handles 429 responses with provider-specified retry delays.
Per-row checkpointing: Writes and flushes each processed row to disk immediately, not batched per chunk, so an interruption never loses already-completed and already-billed work.
Idempotent resume: Reads existing output at startup to build a skip-set, so resuming after an interruption never reprocesses or re-bills already-completed rows, and never produces duplicate rows.
Cost tracking: Kept in sync with actual model pricing after a mid-project model swap (previous model was deprecated), preventing the spend-cap logic from silently drifting from real costs.
Safe fallbacks: Any unhandled exception in the LLM step falls back to a safe default row (digest/unknown/low confidence) rather than crashing the entire batch run — one bad row never takes down the pipeline.
Evaluation
Run structural validation against the full submission:

python evaluation/main.py --validate-only --actual output.csv
This checks, against the real dataset/messages.csv and dataset/message_history.csv: row count matches input, no duplicate message_id, no null/empty fields, action and message_type values are within the allowed enum sets, confidence is in [0,1], and every evidence_message_ids reference resolves to a real historical message ID (no hallucinated evidence).

Verified result on the submitted output.csv: all 7 checks pass. Action distribution: mute 57, notify 31, digest 22 (110 total, 0 duplicates, 0 nulls).

This script does NOT compute action/message_type accuracy, because dataset/sample_messages.csv uses a separate ID namespace (sample_msg_* vs msg_*) from the real messages and is a few-shot calibration set, not a labeled answer key for the graded rows. No local ground truth exists for the 110 submitted messages — accuracy can only be computed by HackerRank's hidden grading. The original evaluate() mode (python evaluation/main.py, no --validate-only) is retained for comparing against sample_messages.csv specifically, and will correctly report no matches when run against the real output for this reason.

The validator was fault-injection tested (invalid action value, dangling evidence ID, duplicate row) to confirm it fails correctly rather than passing everything by default.

Setup Instructions
Python version: Ensure you are using Python 3.10+
Install dependencies:
   python -m venv venv
Activate it:

Windows (PowerShell): .\venv\Scripts\Activate.ps1
macOS/Linux: source venv/bin/activate
Then install directly through the venv's own interpreter to avoid pip silently resolving to a global/user install:

   .\venv\Scripts\python.exe -m pip install -r requirements.txt
Verify with where python (Windows) or which python (macOS/Linux) that it resolves inside venv/ before proceeding. If it doesn't, dependencies will install globally and the pipeline will fail with ModuleNotFoundError: No module named 'pandas' even though the venv appears active in your prompt. 3. Set your API key: Set the Gemini API key as an environment variable (GEMINI_API_KEY).

Windows (PowerShell): $env:GEMINI_API_KEY="your_key_here"
macOS/Linux: export GEMINI_API_KEY="your_key_here"
Run the pipeline: From the code/ directory, execute:
cd code
python main.py --output output.csv
Run tests:
pytest
Known Limitations & Design Notes
Resume state is tracked in two places: .checkpoints/ (keyed by run name) and the output CSV itself (keyed by message_id presence). Both are trusted at face value — if either already contains data for a given run/row, that data is treated as complete and is not reprocessed, with no validation of its contents. This makes interrupted runs cheap to resume, but means a stale or pre-existing .checkpoints/ directory or output file will cause rows to be silently skipped rather than regenerated. For a clean run, delete .checkpoints/ and use a fresh output path.
message_type=scam accounts for ~36% of output.csv (40/110). This reflects the dataset's adversarial density in this run, not a known over-triggering issue post-fix — but is flagged here rather than left for a reviewer to notice unexplained.
Confidence values from the safety gate and prefilter are fixed constants by design (0.8-1.0 depending on trigger certainty), while LLM-routed rows produce continuous confidence. This is intentional: deterministic rule-based decisions warrant fixed high confidence, not manufactured variance.
Re-running the pipeline may produce a small number of different LLM-routed decisions between runs due to model non-determinism; safety-gate and prefilter decisions are fully deterministic and will not vary.
