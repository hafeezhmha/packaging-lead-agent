# PackLead Playbook

## 1. Business Problem

BLRPackworks receives inbound packaging leads from IndiaMART, Justdial,
WhatsApp, website forms, and phone calls. The sales team has to read every
message, understand the requirement, ask missing questions, avoid unsafe pricing
or delivery commitments, and decide whether the customer deserves a call.

The bottleneck is not final quotation. The bottleneck is first-response intake
and qualification.

## 2. Chosen MSME Segment

The assistant focuses on one MSME segment only: custom packaging / manufacturing.

BLRPackworks is a Peenya-based custom corrugated and printed packaging
manufacturer serving D2C brands, e-commerce sellers, food brands, and industrial
customers.

## 3. Why BLRPackworks

This segment is a good test case because leads are messy, specs matter,
pricing is unsafe without exact details, and sales follow-up speed matters. It
also has realistic lead sources: IndiaMART, Justdial, WhatsApp, website, and
phone calls.

## 4. Normal Human Workflow Before AI

1. Read the inquiry or listen to the phone call.
2. Identify product type: corrugated, printed carton, food packaging, e-commerce, industrial.
3. Extract quantity, dimensions, material, use case, delivery location, and timeline.
4. Ask product-specific missing questions.
5. Avoid quoting price until specs are clear.
6. Prioritize bulk or urgent leads.
7. Call the customer when pricing, delivery, feasibility, or final commitment is involved.

## 5. AI-Assisted Workflow

```text
Customer Message / Voice Transcript
↓
LLM Extraction
↓
Deterministic Validation + Lead Scoring
↓
Safe Customer Response
↓
Human Handoff Summary
↓
Local Lead Log
```

The UI streams these stages over WebSocket so the user can see the process
step by step.

## 6. What AI Handles

- Messy language understanding.
- Product type classification.
- Field extraction.
- Phone transcript summarization.
- Natural customer-facing replies.

In the local UI, extraction uses Gemini when `GOOGLE_API_KEY` is configured. If
Gemini is unavailable, it falls back to stable local heuristics so the flow still
runs. In both paths, the extracted fields go through the same deterministic
qualification tool.

## 7. What Deterministic Code Handles

- Required field checks.
- Product-specific missing fields.
- Lead scoring.
- Handoff trigger selection.
- Safety validation.
- Handoff summary formatting.
- JSONL lead logging.

This separation is intentional: AI understands messy input, deterministic code
controls business rules and safety.

## 8. Human Handoff Rules

Handoff happens for:

- price requests
- urgent timelines
- delivery commitments
- discount requests
- final quotation requests
- hot leads
- complete quote-ready leads
- unsupported requests
- low-confidence extraction

## 9. Handoff Context

The handoff summary includes:

- Lead Source
- Lead Status
- Extraction Confidence
- Handoff Trigger
- Customer Need
- Known Details
- Missing Details
- Risk/Notes
- Suggested Human Action
- Suggested Human Script

## 10. WebSocket Streaming

The UI connects to:

```text
ws://127.0.0.1:8765/ws
```

Incoming text payload:

```json
{
  "type": "text",
  "source": "IndiaMART",
  "message": "Hi, I need 5000 custom printed boxes for my skincare brand in Bangalore. Need delivery next week."
}
```

Outgoing event sequence:

- `received`
- `transcription` for voice
- `extraction`
- `validation`
- `lead_score`
- `assistant_chunk`
- `handoff`
- `lead_log`
- `done`

## 11. Voice Input Flow

The UI has a real microphone record button.

Current voice flow:

```text
Mic button
↓
Browser records microphone audio
↓
Audio is sent to backend over WebSocket
↓
Backend tries Gemini audio transcription with GOOGLE_API_KEY
↓
If Gemini fails, browser speech recognition/manual transcript is used
↓
Backend processes transcript through the same lead pipeline
↓
Events stream back to UI
```

If `GOOGLE_API_KEY` is missing or Gemini transcription fails, the UI still
records audio and uses browser speech recognition/manual transcript edit as the
fallback. This is a local voice flow, not call-center-grade speech-to-text
infrastructure.

Optional TTS is browser-based. When enabled in the UI, the assistant reply is
read aloud using the browser Web Speech Synthesis API. There is no production
TTS provider in this implementation.

Current AI/STT/TTS status:

- WebSocket UI extraction uses Gemini text extraction when `GOOGLE_API_KEY` is
  configured, with stable demo heuristics in `packlead/pipeline.py`
  as fallback.
- ADK/Gemini extraction is available separately through
  `packlead/agent.py` with Gemini API key or Vertex AI credentials.
- The WebSocket UI and ADK agent are separate entry points, but both use Gemini
  for messy language understanding when configured and share deterministic
  qualification logic after extraction.
- Voice input is browser microphone capture sent to the backend. Backend
  attempts Gemini audio transcription with `GOOGLE_API_KEY`; browser Web Speech
  API/manual transcript edit remains the fallback.
- A single `GOOGLE_API_KEY` from `.env` is used server-side for both ADK/Gemini
  agent calls and Gemini audio transcription. The key is never exposed to
  frontend JavaScript.
- Production STT/TTS could use Gemini audio, Google Speech-to-Text, Deepgram,
  Whisper, or a similar provider.

To verify the key before demo:

```bash
python verify_gemini.py --audio path/to/short_voice_sample.webm
```

This makes a Gemini text call and a Gemini audio transcription call using the
same `GOOGLE_API_KEY`.

## 12. Configuring For Similar MSMEs

The business is defined in:

```text
config/business_config.json
```

To adapt this to a similar MSME, change:

- business name and description
- lead sources
- product/service categories
- required fields
- lead scoring thresholds
- handoff triggers
- safe response rules
- suggested human script
- source-specific behavior

There is a documentation-only example at:

```text
config/similar_msme_config_example.json
```

## 13. Add A New Product Type

Edit `config/business_config.json` and add a new key under
`product_categories`:

```json
{
  "new_product_type": {
    "display_name": "new product",
    "required_fields": [
      ["field_key", "Customer-facing field label"]
    ]
  }
}
```

Then update the extraction layer so it can classify messages into that product
type.

## 14. Change Required Fields

Update the `required_fields` list for the product category in
`business_config.json`. The deterministic missing-field logic reads from this
config.

## 15. Add Handoff Rules

Add the trigger name to `handoff_triggers` in config and implement the condition
in `packlead/tools.py`. The trigger should correspond to a real
business risk, not a generic automation idea.

## 16. Run The Demo

```bash
python ui.py
```

Open:

```text
http://127.0.0.1:8765
```

## 17. Run Evaluation Metrics

```bash
python eval.py
```

Test cases live in:

```text
eval/test_cases.json
```

## 18. Interpret Eval Results

Metrics include:

- Product Classification Accuracy
- Lead Status Accuracy
- Handoff Decision Accuracy
- Handoff Trigger Accuracy
- Missing Field Detection Accuracy
- Safety Violations
- Task Completion Rate
- Containment Rate
- Human Handoff Rate
- Fallback / Low Confidence Rate
- Average Processing Latency
- Voice Flow Completion Rate

Failures should be treated as feedback on extraction, rules, or test
expectations. The goal is to show that the approach is testable, not to pretend
the first pass is perfect.

The current evaluation is a controlled baseline against deterministic demo
extraction and business-rule code. It is useful for checking the pipeline and
safety behavior, but it is not a claim of real-world LLM or STT performance.

## 19. Known Limitations

- Voice transcription can use Gemini audio through `GOOGLE_API_KEY`, with
  browser speech recognition/manual fallback. It is not production call-center
  STT infrastructure.
- TTS is browser Web Speech Synthesis only, not production TTS.
- No real WhatsApp, IndiaMART, Justdial, website, or phone integration.
- No pricing engine.
- No delivery feasibility or inventory check.
- No CRM beyond JSONL lead log.
- Local UI extraction uses Gemini when configured, with deterministic fallback
  heuristics; the ADK agent is available as a separate console entry point.

## 20. Production Next Steps

- Route the WebSocket backend directly through the ADK agent runtime.
- Add real STT provider for voice.
- Add CRM or lead database.
- Add authenticated sales dashboard.
- Add pricing/feasibility tools behind human approval.
- Expand evaluation with real historical leads.
