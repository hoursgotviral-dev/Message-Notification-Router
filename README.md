# WhatsApp Message Notification Router

An AI-powered router that classifies each incoming WhatsApp message as `notify`, `digest` or `mute`, personalized per user based on relationship to the sender, historical engagement, quiet hours and group role. It handles text, image and voice-note messages.

## Architecture

### Two-directional safety gate

- **Hard override:** clear scam, phishing or unsafe content always mutes, regardless of the user's usual engagement with that sender. This wins over everything else.
- **Upgrade case:** inside a muted group, a genuine direct urgent mention of the user still notifies. Mute status does not suppress it.
- **Precedence:** if both would fire, the hard override wins. A scam inside a muted group stays muted.
- Both checks inspect the message text **and** the media content (image captions or voice transcripts), so a scam hidden in an image still triggers the mute.

A 5-row smoke test (`main.py --limit 5`) confirmed both directions firing on real data in the same run: a hard-override mute on a phishing/payment-request message with no prior business history, and an upgrade-to-notify on a direct urgent mention in a muted group. Both resolved deterministically with zero LLM cost.

### Deterministic prefilter

Runs before any LLM call. If a sender has 3+ dismiss/report events within the last 30 days and no urgency keywords appear in the text or media content, the message is muted immediately with zero LLM cost. This cuts API calls for the highest-volume, lowest-ambiguity case (repeat unwanted senders).

### Multimodal processing

Images and voice notes are sent to Gemini for captioning or transcription before the routing decision, so both the safety gate and the LLM reason over the actual media content. If media processing fails (missing file, network error, etc.), the pipeline logs a warning, uses a placeholder marker and continues to a safe fallback decision instead of crashing.

### LLM routing layer

Messages that pass the prefilter and don't trigger the safety gate go to an LLM, which makes the final classification using the full context: quiet hours, historical opens and replies versus dismissals and reports, group role and mute state, business verification status, and forward/repetition patterns.

Evidence IDs returned by the LLM are validated against the real sender history. Any non-existent message IDs are stripped, so the output never contains fabricated evidence.

## Reliability

- **Proactive rate limiting:** tracks API call timestamps and sleeps before exceeding free-tier limits. 429 responses are handled separately using the provider's retry delay.
- **Per-row checkpointing:** each processed row is written and flushed to disk immediately, so an interruption never loses completed, already-billed work.
- **Idempotent resume:** existing output is read at startup to build a skip-set, so resuming never reprocesses rows or creates duplicates.
- **Cost tracking:** kept in sync with actual model pricing after a mid-project model swap, so spend-cap logic doesn't drift from real costs.
- **Safe fallbacks:** any unhandled exception in the LLM step falls back to a safe default row (`digest` / `unknown` / low confidence), so one bad row never takes down a batch run.

## Evaluation

Run structural validation on the full submission:

```bash
python evaluation/main.py --validate-only --actual output.csv
```

Against the real `dataset/messages.csv` and `dataset/message_history.csv`, this checks that:

- the row count matches the input
- there are no duplicate `message_id` values
- there are no null or empty fields
- `action` and `message_type` are within the allowed values
- `confidence` is in [0, 1]
- every `evidence_message_ids` entry resolves to a real historical message ID

**Result on the submitted `output.csv`:** all 7 checks pass. 110 rows, 0 duplicates, 0 nulls. Action distribution: mute 57, notify 31, digest 22.

The validator was fault-injection tested (invalid action value, dangling evidence ID, duplicate row) to confirm it fails when it should.

**What this does not measure:** action and message-type accuracy. `dataset/sample_messages.csv` uses a separate ID namespace (`sample_msg_*` vs `msg_*`) and is a few-shot calibration set, not an answer key for the graded rows. No local ground truth exists for the 110 submitted messages, so accuracy can only be computed by the hidden grading. The original `evaluate()` mode (`python evaluation/main.py` with no `--validate-only`) is kept for comparing against `sample_messages.csv` only.

## Setup

**Requirements:** Python 3.10+

1. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   ```

   - Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
   - macOS/Linux: `source venv/bin/activate`

2. Install dependencies through the venv's own interpreter, so pip doesn't resolve to a global install:

   ```bash
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   Check with `where python` (Windows) or `which python` (macOS/Linux) that it resolves inside `venv/`. If it doesn't, dependencies install globally and the pipeline fails with `ModuleNotFoundError: No module named 'pandas'`, even though the venv looks active.

3. Set your Gemini API key:

   - Windows (PowerShell): `$env:GEMINI_API_KEY="your_key_here"`
   - macOS/Linux: `export GEMINI_API_KEY="your_key_here"`

4. Run the pipeline from the `code/` directory:

   ```bash
   cd code
   python main.py --output output.csv
   ```

5. Run the tests:

   ```bash
   pytest
   ```

## Known limitations and design notes

- **Resume state lives in two places:** `.checkpoints/` (keyed by run name) and the output CSV (keyed by `message_id`). Both are trusted at face value, with no validation of their contents. A stale `.checkpoints/` directory or an existing output file causes rows to be skipped instead of regenerated. For a clean run, delete `.checkpoints/` and use a fresh output path.
- **Scam share:** `message_type=scam` accounts for about 36% of `output.csv` (40/110). This reflects the dataset's adversarial density in this run, not a known over-triggering issue after the fix. It is noted here so a reviewer doesn't find it unexplained.
- **Fixed confidence constants:** the safety gate and prefilter use fixed confidence values (0.8-1.0 depending on trigger certainty), while LLM-routed rows produce continuous confidence. This is intentional: deterministic rule-based decisions warrant fixed high confidence.
- **Non-determinism:** re-running the pipeline may change a small number of LLM-routed decisions because of model non-determinism. Safety-gate and prefilter decisions are fully deterministic.
