"""Shared demo extraction and processing pipeline.

The ADK agent uses an LLM for extraction. This module provides a stable local
fallback for the WebSocket UI and evaluation runner so the demo is repeatable
without credentials.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable
import urllib.error
import urllib.request

from dotenv import load_dotenv

from .stt import transcribe_audio_with_gemini
from .tools import qualify_packaging_lead


LOG_PATH = "lead_log.jsonl"
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
SOURCES = ["IndiaMART", "Justdial", "WhatsApp", "Website", "Phone Transcript"]
EXTRACTION_METADATA_KEYS = {"extraction_mode", "extraction_error"}

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
    "Messy printed carton": {
        "source": "WhatsApp",
        "message": "Bro need approx 2k mono cartons for skin care, 10x6x4 cm, 4 colour print, matte lamination, artwork ready. Bommanahalli side. Can you quote fast?",
    },
    "Messy food-packaging call": {
        "source": "Phone Transcript",
        "message": "Caller runs a small cafe cloud kitchen. Needs grease proof food boxes, around fifteen hundred pieces, oil barrier and food safe material, delivery Whitefield this week. Asked if price can be confirmed today.",
    },
}


def first_number(text: str) -> int:
    normalized = text.replace(",", "").lower()
    compact_match = re.search(r"\b(\d+(?:\.\d+)?)\s*k\b", normalized)
    if compact_match:
        return int(float(compact_match.group(1)) * 1000)
    lakh_match = re.search(r"\b(\d+(?:\.\d+)?)\s*lakh\b", normalized)
    if lakh_match:
        return int(float(lakh_match.group(1)) * 100000)
    match = re.search(r"\b(\d{2,7})\b", normalized)
    if match:
        return int(match.group(1))

    number_words = {
        "five thousand": 5000,
        "three thousand": 3000,
        "two thousand": 2000,
        "fifteen hundred": 1500,
        "twelve hundred": 1200,
        "one thousand": 1000,
        "eight hundred": 800,
        "five hundred": 500,
    }
    for phrase, value in number_words.items():
        if phrase in normalized:
            return value
    return 0


def extract_location(text: str) -> str:
    known_locations = [
        "Bangalore",
        "Bengaluru",
        "Peenya",
        "Indiranagar",
        "HSR Layout",
        "Whitefield",
        "Bommanahalli",
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
    for phrase in ["tomorrow", "today", "next week", "this week", "next month", "eod"]:
        if phrase in lowered:
            return phrase
    return ""


def extract_dimensions(text: str) -> str:
    match = re.search(
        r"\b\d+\s*(?:[xX]|by)\s*\d+\s*(?:[xX]|by)\s*\d+(?:\s*(?:inch|in|cm|mm))?\b",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(0) if match else ""


def extract_ply(text: str) -> str:
    match = re.search(r"\b\d+\s*-?\s*ply\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def extract_material_strength(text: str) -> str:
    match = re.search(r"\b\d+\s*(?:bf|gsm)\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def extract_product_weight(text: str) -> str:
    match = re.search(r"\b\d+(?:\.\d+)?\s*(?:kg|kgs|kilogram|grams|gram|g)\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def extract_print_colors(text: str) -> str:
    match = re.search(r"\b\d+\s*(?:colour|color|colours|colors)\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def extract_finish_lamination(text: str) -> str:
    lowered = text.lower()
    for phrase in ["matte lamination", "gloss lamination", "lamination", "matte", "gloss"]:
        if phrase in lowered:
            return phrase
    return ""


def extract_artwork_ready(text: str) -> str:
    lowered = text.lower()
    if "artwork ready" in lowered or "design ready" in lowered:
        return "yes"
    if "artwork not ready" in lowered or "design not ready" in lowered:
        return "no"
    return ""


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
        "print_colors": extract_print_colors(message),
        "finish_lamination": extract_finish_lamination(message),
        "artwork_ready": extract_artwork_ready(message),
        "extraction_confidence": "medium",
        "extraction_mode": "heuristic_fallback",
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


def extract_fields(source: str, message: str, log_path: str = LOG_PATH) -> dict[str, Any]:
    """Use Gemini extraction when configured; fall back to deterministic heuristics."""
    ai_result = extract_fields_with_gemini(source, message, log_path=log_path)
    if ai_result["ok"]:
        return ai_result["fields"]

    fields = extract_demo_fields(source, message, log_path=log_path)
    fields["extraction_mode"] = "heuristic_fallback"
    fields["extraction_error"] = ai_result["error"]
    return fields


def extract_fields_with_gemini(source: str, message: str, log_path: str = LOG_PATH) -> dict[str, Any]:
    load_dotenv(override=False)
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "fields": {}, "error": "GOOGLE_API_KEY is not set."}

    prompt = _extraction_prompt(source, message)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_TEXT_MODEL}:generateContent?key={api_key}"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_json = json.loads(response.read().decode("utf-8"))
        extracted_json = _extract_text(response_json)
        fields = _normalize_ai_fields(json.loads(extracted_json), source, message, log_path)
        fields["extraction_mode"] = "gemini_text_extraction"
        return {"ok": True, "fields": fields, "error": ""}
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return {"ok": False, "fields": {}, "error": str(exc)}


def _extract_text(response_json: dict[str, Any]) -> str:
    candidates = response_json.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    return " ".join(part.get("text", "").strip() for part in parts).strip()


def _extraction_prompt(source: str, message: str) -> str:
    return f"""
Extract a packaging MSME sales lead into strict JSON.

Business: PackLead, a custom corrugated and printed packaging manufacturer.
Supported product_type values:
- corrugated_box
- printed_carton
- food_packaging
- ecommerce_shipping
- industrial_packaging
- unknown

Rules:
- Return only JSON. No markdown.
- Use empty strings for unknown text fields and 0 for unknown quantity.
- Do not invent specs.
- Set extraction_confidence to high, medium, or low.
- For phone calls, add transcript_summary.
- Preserve the original customer message in message.

JSON keys:
source, message, product, product_type, quantity, industry, location, timeline,
dimensions, ply, material_strength, paperboard_gsm, print_colors,
finish_lamination, artwork_ready, food_grade_requirement, barrier_requirement,
certification_concern, product_weight, fragility, shipment_volume,
branding_printing_need, industrial_product_type, handling_storage_requirement,
budget_range, contact_name, company_name, phone, email, transcript_summary,
intent, extraction_confidence.

Lead source: {source}
Customer message:
{message}
""".strip()


def _normalize_ai_fields(
    extracted: dict[str, Any],
    source: str,
    message: str,
    log_path: str,
) -> dict[str, Any]:
    fallback = extract_demo_fields(source, message, log_path=log_path)
    text_keys = [
        "source",
        "message",
        "product",
        "product_type",
        "industry",
        "location",
        "timeline",
        "dimensions",
        "ply",
        "material_strength",
        "paperboard_gsm",
        "print_colors",
        "finish_lamination",
        "artwork_ready",
        "food_grade_requirement",
        "barrier_requirement",
        "certification_concern",
        "product_weight",
        "fragility",
        "shipment_volume",
        "branding_printing_need",
        "industrial_product_type",
        "handling_storage_requirement",
        "budget_range",
        "contact_name",
        "company_name",
        "phone",
        "email",
        "transcript_summary",
        "intent",
        "extraction_confidence",
    ]
    fields = fallback.copy()
    for key in text_keys:
        value = extracted.get(key)
        if value is not None:
            fields[key] = str(value).strip()
    quantity = extracted.get("quantity", fallback.get("quantity", 0))
    try:
        fields["quantity"] = int(quantity)
    except (TypeError, ValueError):
        fields["quantity"] = fallback.get("quantity", 0)
    fields["source"] = fields.get("source") or source
    fields["message"] = fields.get("message") or message
    fields["log_path"] = log_path
    return fields


def recent_logs(log_path: str = LOG_PATH, limit: int = 5) -> list[dict[str, Any]]:
    if not log_path:
        return []
    path = Path(log_path)
    if not path.exists() or not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(rows))


def qualification_kwargs(extracted: dict[str, Any]) -> dict[str, Any]:
    """Remove UI/debug extraction metadata before calling the business tool."""
    return {
        key: value
        for key, value in extracted.items()
        if key not in EXTRACTION_METADATA_KEYS
    }


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
        if transcript:
            transcription = {
                "ok": True,
                "transcript": transcript,
                "mode": "manual_transcript",
                "error": "",
            }
            raw_message = transcript
        else:
            transcription = transcribe_audio_with_gemini(audio_base64) if audio_base64 else {
                "ok": False,
                "transcript": "",
                "mode": "fallback_no_audio",
                "error": "No audio payload was provided.",
            }
            if transcription["ok"]:
                raw_message = transcription["transcript"]
            else:
                raw_message = message
        yield {
            "event": "transcription",
            "data": {
                "transcript": raw_message,
                "audio_bytes": audio_bytes,
                "mode": transcription["mode"] if transcription["ok"] else "browser_speech_recognition_or_manual_fallback",
                "gemini_attempted": bool(audio_base64 and not transcript),
                "gemini_error": "" if transcription["ok"] else transcription.get("error", ""),
                "note": (
                    "Using the edited/manual transcript supplied from the UI."
                    if transcript
                    else
                    "Gemini transcribed the uploaded browser microphone audio."
                    if transcription["ok"]
                    else "Gemini transcription was unavailable or failed, so the browser/manual transcript is used."
                ),
            },
        }

    extracted = extract_fields(source, raw_message, log_path=log_path)
    yield {"event": "extraction", "data": extracted}

    result = qualify_packaging_lead(**qualification_kwargs(extracted))
    yield {
        "event": "validation",
        "data": {
            "missing_fields": result["missing_fields"],
            "safety_flags": result["safety_flags"],
            "next_questions": result["next_questions"],
        },
    }
    yield {
        "event": "conversation_check",
        "data": {
            "stage": result["conversation_stage"],
            "clarifying_questions": result["clarifying_questions"],
            "handoff_trigger": result["handoff_trigger"],
        },
    }
    yield {
        "event": "lead_score",
        "data": {
            "lead_status": result["lead_status"],
            "extraction_confidence": result["extraction_confidence"],
            "handoff_required": result["handoff_required"],
            "handoff_trigger": result["handoff_trigger"],
            "conversation_stage": result["conversation_stage"],
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
