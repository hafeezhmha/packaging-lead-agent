"""FastAPI WebSocket demo UI for PackLead."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from packlead.config_loader import load_business_config
from packlead.pipeline import EXAMPLES, SOURCES, recent_logs, stream_process_events


HOST = "127.0.0.1"
PORT = 8765
app = FastAPI(title="PackLead Demo")


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse(_render_html())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            message_type = payload.get("type", "text")
            source = payload.get("source", "Website")
            message = payload.get("message", "")
            transcript = payload.get("transcript", "")
            audio_b64 = payload.get("audio_base64", "")
            audio_bytes = _audio_size(audio_b64)

            for event in stream_process_events(
                source=source,
                message=message,
                input_type=message_type,
                transcript=transcript,
                audio_bytes=audio_bytes,
                audio_base64=audio_b64,
            ):
                await websocket.send_json(event)
                await asyncio.sleep(0.08)
    except WebSocketDisconnect:
        return


def _audio_size(audio_b64: str) -> int:
    if not audio_b64:
        return 0
    try:
        return len(base64.b64decode(audio_b64.split(",")[-1]))
    except Exception:
        return 0


def _render_html() -> str:
    config = load_business_config()
    sources_options = "".join(f"<option>{source}</option>" for source in SOURCES)
    examples_json = json.dumps(EXAMPLES)
    recent_json = json.dumps(recent_logs())
    business = config["business"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PackLead WebSocket Demo</title>
  <style>
    :root {{ --border:#d8dee4; --bg:#f6f8fa; --panel:#ffffff; --text:#1f2328; --muted:#667085; --blue:#0969da; --blue-soft:#eef6ff; --ok:#067647; --ok-soft:#ecfdf3; --warn:#b54708; --warn-soft:#fff7ed; --bad:#b42318; --bad-soft:#fef3f2; --shadow:0 1px 2px rgba(16,24,40,.06); }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--text); background:linear-gradient(180deg,#f8fbff 0,#f6f8fa 260px); }}
    header {{ padding:24px 32px; background:rgba(255,255,255,.92); border-bottom:1px solid var(--border); }}
    h1 {{ margin:0 0 8px; font-size:30px; letter-spacing:0; }}
    h2 {{ margin:0 0 12px; font-size:17px; }}
    h3 {{ margin:14px 0 8px; font-size:14px; }}
    main {{ max-width:1280px; margin:0 auto; padding:20px; }}
    .muted {{ color:var(--muted); }}
    .eyebrow {{ margin:0 0 8px; color:var(--blue); font-weight:800; font-size:13px; text-transform:uppercase; letter-spacing:.04em; }}
    .header-row {{ display:flex; justify-content:space-between; align-items:flex-start; gap:20px; }}
    .header-copy {{ max-width:860px; }}
    .header-badges {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; min-width:260px; }}
    .badge {{ border:1px solid var(--border); background:white; border-radius:999px; padding:7px 10px; font-size:13px; font-weight:700; color:#344054; }}
    .card {{ background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:16px; box-shadow:var(--shadow); }}
    .workspace {{ display:grid; grid-template-columns:420px minmax(0,1fr); gap:18px; align-items:start; }}
    .results-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
    .summary-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px; }}
    .summary-card {{ background:white; border:1px solid var(--border); border-radius:8px; padding:13px; box-shadow:var(--shadow); }}
    .summary-card span {{ display:block; color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; margin-bottom:6px; }}
    .summary-card strong {{ display:block; font-size:18px; min-height:24px; }}
    .pipeline {{ display:grid; grid-template-columns:repeat(6,1fr); gap:8px; margin-bottom:16px; }}
    .pipeline div {{ background:var(--blue-soft); border:1px solid #b6d7ff; border-radius:8px; padding:10px; text-align:center; font-size:12px; font-weight:800; }}
    label {{ display:block; font-weight:700; margin:12px 0 6px; }}
    select, textarea, input {{ width:100%; border:1px solid var(--border); border-radius:6px; padding:10px; font:inherit; background:white; }}
    select:focus, textarea:focus {{ outline:2px solid #b6d7ff; border-color:var(--blue); }}
    textarea {{ min-height:112px; resize:vertical; }}
    button {{ border:1px solid var(--blue); background:var(--blue); color:white; border-radius:6px; padding:10px 13px; font-weight:800; cursor:pointer; transition:.12s ease; }}
    button:hover {{ filter:brightness(.96); }}
    button.secondary {{ background:white; color:var(--blue); }}
    button.danger {{ border-color:var(--bad); background:var(--bad); }}
    button:disabled {{ opacity:.55; cursor:not-allowed; }}
    .actions, .samples {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
    .samples button {{ font-size:13px; padding:8px 10px; }}
    .mode-note {{ background:#f8fafc; border:1px solid #eaecf0; border-radius:8px; padding:10px; margin-top:12px; }}
    .event-list {{ max-height:360px; overflow:auto; padding-right:4px; }}
    .event {{ border:1px solid #e4eaf2; border-left:4px solid #84c5ff; padding:9px 10px; margin:8px 0; background:#fbfdff; border-radius:7px; }}
    .event strong {{ display:block; margin-bottom:5px; font-size:13px; color:#175cd3; }}
    .event code {{ display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .kv {{ display:flex; justify-content:space-between; gap:12px; border-bottom:1px solid #edf0f2; padding:8px 0; }}
    .kv span {{ color:var(--muted); }}
    .kv strong {{ text-align:right; }}
    pre {{ white-space:pre-wrap; word-break:break-word; background:#f6f8fa; border:1px solid #eaeef2; border-radius:6px; padding:11px; margin:0; }}
    .score {{ display:inline-block; padding:8px 14px; border-radius:999px; color:white; font-weight:800; }}
    .Hot {{ background:var(--bad); }} .Warm {{ background:var(--warn); }} .Cold {{ background:#175cd3; }} .Spam {{ background:#475467; }}
    .safety {{ background:#fffaf0; border-color:#f2c94c; }}
    .reply {{ font-size:17px; line-height:1.55; margin:0; }}
    .reply:empty::before {{ content:"Assistant reply will stream here."; color:var(--muted); }}
    .conversation {{ display:grid; gap:10px; }}
    .chat-turn {{ border:1px solid #e4eaf2; border-radius:8px; padding:10px; background:#fbfdff; }}
    .chat-turn strong {{ display:block; margin-bottom:5px; color:#175cd3; }}
    .log-item {{ border-top:1px solid #edf0f2; padding:10px 0; }}
    .log-item:first-child {{ border-top:0; }}
    code {{ background:#eef2f6; border-radius:4px; padding:2px 5px; }}
    .section-title {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
    .status-dot {{ width:9px; height:9px; border-radius:50%; background:#98a2b3; display:inline-block; margin-right:6px; }}
    .status-dot.live {{ background:var(--ok); box-shadow:0 0 0 3px var(--ok-soft); }}
    .full-span {{ grid-column:1 / -1; }}
    @media (max-width: 1050px) {{ .workspace {{ grid-template-columns:1fr; }} .summary-grid {{ grid-template-columns:repeat(2,1fr); }} .header-row {{ flex-direction:column; }} .header-badges {{ justify-content:flex-start; }} }}
    @media (max-width: 720px) {{ .results-grid,.pipeline,.summary-grid {{ grid-template-columns:1fr; }} main {{ padding:12px; }} header {{ padding:18px; }} }}
  </style>
</head>
<body>
  <header>
    <div class="header-row">
      <div class="header-copy">
        <p class="eyebrow">MSME packaging lead intake</p>
        <h1>PackLead Demo</h1>
        <p class="muted">{business["description"]}</p>
      </div>
      <div class="header-badges">
        <span class="badge">WebSocket streaming</span>
        <span class="badge">Gemini STT</span>
        <span class="badge">Human handoff</span>
      </div>
    </div>
  </header>
  <main>
    <section class="summary-grid">
      <div class="summary-card"><span>Lead score</span><strong id="statusScore">-</strong></div>
      <div class="summary-card"><span>Handoff</span><strong id="statusHandoff">-</strong></div>
      <div class="summary-card"><span>Transcription</span><strong id="statusMode">-</strong></div>
      <div class="summary-card"><span>Latency</span><strong id="statusLatency">-</strong></div>
    </section>

    <section class="pipeline">
      <div>Customer Input</div><div>Extraction</div><div>Validation / Scoring</div><div>Safe Response</div><div>Handoff</div><div>Lead Log</div>
    </section>

    <section class="workspace">
      <div class="card">
        <div class="section-title"><h2>Lead Intake</h2><span class="muted">Text or voice</span></div>
        <label>Lead source</label>
        <select id="source">{sources_options}</select>
        <label>Customer message</label>
        <textarea id="message"></textarea>
        <div class="samples" id="samples"></div>
        <div class="actions">
          <button id="processText">Process Text Lead</button>
          <button id="recordVoice" class="secondary">Record Voice</button>
          <button id="stopVoice" class="danger" disabled>Stop Recording</button>
        </div>
        <label>Customer clarification</label>
        <textarea id="clarification" placeholder="Add the client's answer to the AI questions, then continue qualification."></textarea>
        <button id="continueQualification" class="secondary">Continue Qualification</button>
        <div class="mode-note">
          <p class="muted" id="voiceStatus">Voice mode records microphone audio and sends it to the backend for Gemini transcription when GOOGLE_API_KEY is configured. Browser speech recognition/manual transcript edit is the fallback.</p>
          <label style="display:flex;gap:8px;align-items:center;font-weight:500;margin:8px 0 0;">
            <input id="ttsToggle" type="checkbox" style="width:auto;">
            Read assistant reply aloud using browser TTS
          </label>
          <p class="muted" style="margin:6px 0 0;">TTS is optional and demo-only. It uses browser Web Speech Synthesis, not production voice generation.</p>
        </div>
        <label>Voice transcript</label>
        <textarea id="transcript" placeholder="Transcript appears here. You can edit before processing."></textarea>
        <button id="processVoice" class="secondary">Process Voice Transcript</button>
      </div>

      <div class="card">
        <div class="section-title"><h2>Streaming Event Timeline</h2><span class="muted"><span id="connectionDot" class="status-dot"></span><span id="connectionStatus">Connecting</span></span></div>
        <div id="events" class="event-list"><p class="muted">Run a text or voice sample to see WebSocket events.</p></div>
      </div>
    </section>

    <section class="results-grid">
      <div class="card">
        <h2>Extracted Lead Details</h2>
        <div id="extraction"><p class="muted">Waiting for extraction event.</p></div>
      </div>
      <div class="card">
        <h2>Validation / Missing Details</h2>
        <div id="validation"><p class="muted">Waiting for validation event.</p></div>
      </div>
    </section>

    <section class="results-grid">
      <div class="card">
        <h2>Lead Score + Handoff</h2>
        <div id="score"><p class="muted">Waiting for lead score event.</p></div>
      </div>
      <div class="card safety">
        <h2>Safety</h2>
        <p>No price quote. No delivery promise. No inventory, discount, or final quotation commitment. Risky cases go to a human.</p>
      </div>
    </section>

    <section class="card">
      <h2>AI Qualification Conversation</h2>
      <div class="conversation" id="conversation"><p class="muted">AI/client clarification flow will appear here before human handoff.</p></div>
    </section>

    <section class="card">
      <h2>AI Customer Reply</h2>
      <p class="reply" id="reply"></p>
    </section>

    <section class="card">
      <h2>Human Handoff Summary</h2>
      <pre id="handoff">No handoff yet.</pre>
    </section>

    <section class="card">
      <h2>Recent Lead Log</h2>
      <div id="leadLog"></div>
    </section>
  </main>

  <script>
    const examples = {examples_json};
    const initialLogs = {recent_json};
    let socket;
    let mediaRecorder;
    let audioChunks = [];
    let recognition;
    let finalTranscript = "";
    let replyForSpeech = "";

    function connect() {{
      socket = new WebSocket(`ws://${{location.host}}/ws`);
      socket.onopen = () => {{
        document.querySelector("#connectionStatus").textContent = "Connected";
        document.querySelector("#connectionDot").classList.add("live");
      }};
      socket.onmessage = (msg) => handleEvent(JSON.parse(msg.data));
      socket.onclose = () => {{
        document.querySelector("#connectionStatus").textContent = "Reconnecting";
        document.querySelector("#connectionDot").classList.remove("live");
        setTimeout(connect, 800);
      }};
    }}

    function kv(rows) {{
      return rows.map(([k,v]) => `<div class="kv"><span>${{escapeHtml(k)}}</span><strong>${{escapeHtml(v || "-")}}</strong></div>`).join("");
    }}
    function list(items) {{
      if (!items || !items.length) return "<p class='muted'>None</p>";
      return "<ul>" + items.map(x => `<li>${{escapeHtml(x)}}</li>`).join("") + "</ul>";
    }}
    function escapeHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
    }}
    function addEvent(name, data) {{
      const events = document.querySelector("#events");
      if (events.querySelector(".muted")) events.innerHTML = "";
      if (name === "assistant_chunk") {{
        let stream = events.querySelector('[data-event="assistant_stream"] code');
        if (!stream) {{
          const div = document.createElement("div");
          div.className = "event";
          div.dataset.event = "assistant_stream";
          div.innerHTML = `<strong>assistant_stream</strong><code></code>`;
          events.appendChild(div);
          stream = div.querySelector("code");
        }}
        stream.textContent = `${{stream.textContent}}${{data}}`.slice(0, 140);
        return;
      }}
      const div = document.createElement("div");
      div.className = "event";
      div.innerHTML = `<strong>${{escapeHtml(name)}}</strong><code>${{escapeHtml(JSON.stringify(data).slice(0, 140))}}</code>`;
      events.appendChild(div);
    }}
    function resetOutput() {{
      document.querySelector("#events").innerHTML = "";
      document.querySelector("#extraction").innerHTML = "<p class='muted'>Waiting for extraction event.</p>";
      document.querySelector("#validation").innerHTML = "<p class='muted'>Waiting for validation event.</p>";
      document.querySelector("#score").innerHTML = "<p class='muted'>Waiting for lead score event.</p>";
      document.querySelector("#conversation").innerHTML = "<p class='muted'>AI/client clarification flow will appear here before human handoff.</p>";
      document.querySelector("#reply").textContent = "";
      replyForSpeech = "";
      document.querySelector("#handoff").textContent = "No handoff yet.";
      document.querySelector("#statusScore").textContent = "-";
      document.querySelector("#statusHandoff").textContent = "-";
      document.querySelector("#statusMode").textContent = "-";
      document.querySelector("#statusLatency").textContent = "-";
      if (window.speechSynthesis) window.speechSynthesis.cancel();
    }}
    function send(payload) {{
      resetOutput();
      if (!socket || socket.readyState !== WebSocket.OPEN) connect();
      setTimeout(() => socket.send(JSON.stringify(payload)), 120);
    }}
    function handleEvent(event) {{
      addEvent(event.event, event.data || "");
      if (event.event === "transcription") {{
        document.querySelector("#transcript").value = event.data.transcript || "";
        document.querySelector("#voiceStatus").textContent = `Transcription mode: ${{event.data.mode}}. ${{event.data.note || ""}}`;
        document.querySelector("#statusMode").textContent = event.data.mode || "voice";
      }}
      if (event.event === "extraction") {{
        const d = event.data;
        document.querySelector("#extraction").innerHTML = kv([
          ["mode", d.extraction_mode],
          ["source", d.source], ["product type", d.product_type], ["product", d.product],
          ["quantity", d.quantity], ["industry", d.industry], ["location", d.location],
          ["timeline", d.timeline], ["dimensions", d.dimensions], ["confidence", d.extraction_confidence]
        ]);
      }}
      if (event.event === "validation") {{
        document.querySelector("#validation").innerHTML = `<h3>Missing Details</h3>${{list(event.data.missing_fields)}}<h3>Next Questions</h3>${{list(event.data.next_questions)}}<h3>Safety Flags</h3><pre>${{escapeHtml(JSON.stringify(event.data.safety_flags, null, 2))}}</pre>`;
      }}
      if (event.event === "conversation_check") {{
        const questions = event.data.clarifying_questions || [];
        const stageLabel = event.data.stage === "needs_clarification"
          ? "AI should ask the client before handoff"
          : "No more AI clarification needed before handoff";
        document.querySelector("#conversation").innerHTML = `
          <div class="chat-turn"><strong>AI Check</strong><span>${{escapeHtml(stageLabel)}}</span></div>
          <div class="chat-turn"><strong>AI to Client</strong>${{list(questions)}}</div>
          <div class="chat-turn"><strong>Next Step</strong><span>${{questions.length ? "Wait for the client answer, then continue qualification." : "Prepare the human handoff summary."}}</span></div>
        `;
      }}
      if (event.event === "lead_score") {{
        const d = event.data;
        document.querySelector("#score").innerHTML = `<div class="score ${{escapeHtml(d.lead_status)}}">${{escapeHtml(d.lead_status)}}</div>` + kv([
          ["handoff required", d.handoff_required ? "yes" : "no"], ["handoff trigger", d.handoff_trigger],
          ["conversation stage", d.conversation_stage],
          ["confidence", d.extraction_confidence], ["latency", `${{d.latency_seconds}}s`]
        ]);
        document.querySelector("#statusScore").textContent = d.lead_status || "-";
        document.querySelector("#statusHandoff").textContent = d.handoff_required ? d.handoff_trigger : "No";
        document.querySelector("#statusLatency").textContent = `${{d.latency_seconds}}s`;
      }}
      if (event.event === "assistant_chunk") {{
        document.querySelector("#reply").textContent += event.data;
        replyForSpeech += event.data;
      }}
      if (event.event === "handoff") {{
        document.querySelector("#handoff").textContent = event.data.summary || "No human handoff required yet.";
      }}
      if (event.event === "done") speakReplyIfEnabled();
      if (event.event === "lead_log") renderLogs(event.data.recent || []);
    }}
    function renderLogs(rows) {{
      const target = document.querySelector("#leadLog");
      if (!rows.length) {{ target.innerHTML = "<p class='muted'>No logged leads yet.</p>"; return; }}
      target.innerHTML = rows.map(row => `<div class="log-item"><strong>${{escapeHtml(row.lead_status)}}</strong> <span>${{escapeHtml(row.source)}}</span> <code>${{escapeHtml(row.handoff_trigger)}}</code><p>${{escapeHtml(row.raw_message)}}</p></div>`).join("");
    }}

    document.querySelector("#processText").onclick = () => send({{
      type: "text", source: document.querySelector("#source").value, message: document.querySelector("#message").value
    }});
    document.querySelector("#continueQualification").onclick = () => {{
      const source = document.querySelector("#source").value;
      const transcript = document.querySelector("#transcript").value.trim();
      const original = source === "Phone Transcript" && transcript ? transcript : document.querySelector("#message").value.trim();
      const clarification = document.querySelector("#clarification").value.trim();
      if (!clarification) return;
      send({{
        type: "text",
        source,
        message: `${{original}}\nCustomer clarification: ${{clarification}}`
      }});
    }};
    document.querySelector("#processVoice").onclick = () => send({{
      type: "voice", source: "Phone Transcript", message: document.querySelector("#message").value,
      transcript: document.querySelector("#transcript").value, audio_base64: window.lastAudioBase64 || ""
    }});
    Object.entries(examples).forEach(([name, data]) => {{
      const btn = document.createElement("button");
      btn.className = "secondary";
      btn.textContent = name;
      btn.onclick = () => {{
        document.querySelector("#source").value = data.source;
        document.querySelector("#message").value = data.message;
        document.querySelector("#transcript").value = data.source === "Phone Transcript" ? data.message : "";
        document.querySelector("#clarification").value = "";
      }};
      document.querySelector("#samples").appendChild(btn);
    }});

    async function startRecording() {{
      finalTranscript = "";
      audioChunks = [];
      const stream = await navigator.mediaDevices.getUserMedia({{audio: true}});
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = async () => {{
        const blob = new Blob(audioChunks, {{type: "audio/webm"}});
        window.lastAudioBase64 = await blobToDataUrl(blob);
        stream.getTracks().forEach(t => t.stop());
      }};
      mediaRecorder.start();
      startSpeechRecognition();
      document.querySelector("#recordVoice").disabled = true;
      document.querySelector("#stopVoice").disabled = false;
      document.querySelector("#voiceStatus").textContent = "Recording... speak the customer inquiry, then stop.";
    }}
    function stopRecording() {{
      if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
      if (recognition) recognition.stop();
      document.querySelector("#recordVoice").disabled = false;
      document.querySelector("#stopVoice").disabled = true;
      document.querySelector("#voiceStatus").textContent = "Recording stopped. Confirm/edit transcript, then Process Voice Transcript.";
    }}
    function startSpeechRecognition() {{
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {{
        document.querySelector("#voiceStatus").textContent = "Browser speech recognition is unavailable. Audio is captured; type or paste transcript before processing.";
        return;
      }}
      recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-IN";
      recognition.onresult = (event) => {{
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {{
          const text = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalTranscript += text + " ";
          else interim += text;
        }}
        document.querySelector("#transcript").value = (finalTranscript + interim).trim();
      }};
      recognition.start();
    }}
    function blobToDataUrl(blob) {{
      return new Promise(resolve => {{
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blob);
      }});
    }}
    function speakReplyIfEnabled() {{
      const enabled = document.querySelector("#ttsToggle").checked;
      if (!enabled || !replyForSpeech.trim()) return;
      if (!("speechSynthesis" in window)) {{
        document.querySelector("#voiceStatus").textContent = "Browser TTS is unavailable in this browser.";
        return;
      }}
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(replyForSpeech);
      utterance.lang = "en-IN";
      utterance.rate = 1;
      window.speechSynthesis.speak(utterance);
    }}
    document.querySelector("#recordVoice").onclick = startRecording;
    document.querySelector("#stopVoice").onclick = stopRecording;
    renderLogs(initialLogs);
    connect();
  </script>
</body>
</html>"""


def main() -> None:
    port = int(os.environ.get("PORT", PORT))
    uvicorn.run("ui:app", host=HOST, port=port, reload=False)


if __name__ == "__main__":
    main()
