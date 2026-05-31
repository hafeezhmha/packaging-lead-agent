"""Shared demo extraction and processing pipeline.

The ADK agent uses an LLM for extraction. This module provides a stable local
fallback for the WebSocket UI and evaluation runner so the demo is repeatable
without credentials.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Iterable

from .stt import transcribe_audio_with_gemini
from .tools import qualify_packaging_lead


LOG_PATH = "lead_log.jsonl"
SOURCES = ["IndiaMART", "Justdial", "WhatsApp", "Website", "Phone Transcript"]

EXAMPLES = {
    "Hot IndiaMART lead": {
        "source": "IndiaMART",
        "message": "Hi, I need 5000 custom printed boxes for my skincare brand in Bangalore. Need delivery next week.",
    },
    "Vague WhatsApp lead": {
        "source": "WhatsApp",
        "message": "Hi, do you make boxes for online shipping?",
    },
    "Urgent price request": {
        "source": "Justdial",
        "message": "What is the price for 1000 boxes? I need them tomorrow.",
    },
    "Voice/phone style": {
        "source": "Phone Transcript",
        "message": "I run a small food brand in Indiranagar and need oil-resistant food packaging for 2000 units next month. Can you confirm price today?",
    },
}


def first_number(text: str) -> int:
    match = re.search(r"\b(\d{2,7})\b", text.replace(",", ""))
    return int(match.group(1)) if match else 0


def extract_location(text: str) -> str:
    known_locations = [
        "Bangalore",
        "Bengaluru",
        "Peenya",
        "Indiranagar",
        "HSR Layout",
        "Whitefield",
        "Koramangala",
        "Electronic City",
    ]
    lowered = text.lower()
    for location in known_locations:
        if location.lower() in lowered:
            return location
    return ""


def extract_timeline(text: str) -> str:
    lowered = text.lower()
    for phrase in ["tomorrow", "today", "next week", "this week", "next month"]:
        if phrase in lowered:
            return phrase
    return ""


def extract_dimensions(text: str) -> str:
    match = re.search(
        r"\b\d+\s*[xX]\s*\d+\s*[xX]\s*\d+(?:\s*(?:inch|in|cm|mm))?\b",
        text,
    )
    return match.group(0) if match else ""


def extract_ply(text: str) -> str:
    match = re.search(r"\b\d+\s*ply\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def extract_material_strength(text: str) -> str:
    match = re.search(r"\b\d+\s*(?:bf|gsm)\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def extract_product_weight(text: str) -> str:
    match = re.search(r"\b\d+(?:\.\d+)?\s*(?:kg|kgs|kilogram|grams|gram|g)\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def extract_demo_fields(source: str, message: str, log_path: str = LOG_PATH) -> dict[str, Any]:
    """Small local stand-in for LLM extraction used by UI/eval only."""
    lowered = message.lower()
    product = "packaging"
    product_type = "unknown"
    industry = ""

    if any(term in lowered for term in ["online shipping", "e-commerce", "ecommerce", "shipping"]):
        product = "e-commerce shipping boxes"
        product_type = "ecommerce_shipping"
        industry = "e-commerce"
    if product_type == "unknown" and any(
        term in lowered for term in ["printed", "print", "skincare", "carton"]
    ):
        product = "custom printed cartons"
        product_type = "printed_carton"
    if product_type == "unknown" and any(
        term in lowered for term in ["food", "snack", "oil-resistant", "oil resistant"]
    ):
        product = "food packaging"
        product_type = "food_packaging"
        industry = "food brand"
    if any(term in lowered for term in ["industrial", "metal", "machine", "heavy"]):
        product = "industrial packaging"
        product_type = "industrial_packaging"
    if product_type == "unknown" and any(term in lowered for term in ["box", "boxes", "corrugated"]):
        product = "corrugated boxes"
        product_type = "corrugated_box"

    if "skincare" in lowered:
        industry = "skincare"

    fields: dict[str, Any] = {
        "source": source,
        "message": message,
        "product": product,
        "product_type": product_type,
        "quantity": first_number(message),
        "industry": industry,
        "location": extract_location(message),
        "timeline": extract_timeline(message),
        "dimensions": extract_dimensions(message),
        "ply": extract_ply(message),
        "material_strength": extract_material_strength(message),
        "product_weight": extract_product_weight(message),
        "extraction_confidence": "medium",
        "log_path": log_path,
    }

    if source == "Phone Transcript":
        fields["transcript_summary"] = message.replace("Caller says ", "").strip()

    if product_type == "food_packaging":
        if "oil" in lowered:
            fields["barrier_requirement"] = "oil-resistant barrier"
        if "food" in lowered:
            fields["food_grade_requirement"] = "food-grade material"

    if product_type == "ecommerce_shipping":
        if "fragile" in lowered or "break" in lowered:
            fields["fragility"] = "fragile product"
        if "print" in lowered or "logo" in lowered:
            fields["branding_printing_need"] = "printing/logo needed"

    if "unsupported" in lowered or "plastic water bottle" in lowered:
        fields["product"] = "plastic water bottles"
        fields["product_type"] = "unknown"

    return fields


def recent_logs(log_path: str = LOG_PATH, limit: int = 5) -> list[dict[str, Any]]:
    path = Path(log_path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(rows))


def stream_process_events(
    source: str,
    message: str,
    *,
    input_type: str = "text",
    transcript: str = "",
    audio_bytes: int = 0,
    audio_base64: str = "",
    log_path: str = LOG_PATH,
) -> Iterable[dict[str, Any]]:
    started = time.perf_counter()
    raw_message = transcript or message
    yield {"event": "received", "data": {"type": input_type, "source": source, "message": message}}

    if input_type == "voice":
        transcription = transcribe_audio_with_gemini(audio_base64) if audio_base64 else {
            "ok": False,
            "transcript": "",
            "mode": "fallback_no_audio",
            "error": "No audio payload was provided.",
        }
        if transcription["ok"]:
            raw_message = transcription["transcript"]
        else:
            raw_message = transcript or message
        yield {
            "event": "transcription",
            "data": {
                "transcript": raw_message,
                "audio_bytes": audio_bytes,
                "mode": transcription["mode"] if transcription["ok"] else "browser_speech_recognition_or_manual_fallback",
                "gemini_attempted": bool(audio_base64),
                "gemini_error": "" if transcription["ok"] else transcription.get("error", ""),
                "note": (
                    "Gemini transcribed the uploaded browser microphone audio."
                    if transcription["ok"]
                    else "Gemini transcription was unavailable or failed, so the browser/manual transcript is used."
                ),
            },
        }

    extracted = extract_demo_fields(source, raw_message, log_path=log_path)
    yield {"event": "extraction", "data": extracted}

    result = qualify_packaging_lead(**extracted)
    yield {
        "event": "validation",
        "data": {
            "missing_fields": result["missing_fields"],
            "safety_flags": result["safety_flags"],
            "next_questions": result["next_questions"],
        },
    }
    yield {
        "event": "lead_score",
        "data": {
            "lead_status": result["lead_status"],
            "extraction_confidence": result["extraction_confidence"],
            "handoff_required": result["handoff_required"],
            "handoff_trigger": result["handoff_trigger"],
            "latency_seconds": round(time.perf_counter() - started, 4),
        },
    }

    reply = result["suggested_response"]
    for chunk in _chunk_text(reply):
        yield {"event": "assistant_chunk", "data": chunk}

    yield {
        "event": "handoff",
        "data": {
            "required": result["handoff_required"],
            "trigger": result["handoff_trigger"],
            "summary": result["handoff_summary"],
        },
    }
    yield {"event": "lead_log", "data": {"latest": result["log_record"], "recent": recent_logs(log_path)}}
    yield {"event": "done", "data": {"latency_seconds": round(time.perf_counter() - started, 4)}}


def _chunk_text(text: str, size: int = 42) -> Iterable[str]:
    words = text.split()
    chunk: list[str] = []
    length = 0
    for word in words:
        chunk.append(word)
        length += len(word) + 1
        if length >= size:
            yield " ".join(chunk) + " "
            chunk = []
            length = 0
    if chunk:
        yield " ".join(chunk)
