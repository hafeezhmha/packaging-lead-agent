"""Speech-to-text helpers for the BLRPackworks voice demo."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any

from dotenv import load_dotenv


GEMINI_TRANSCRIPTION_MODEL = os.environ.get(
    "GEMINI_TRANSCRIPTION_MODEL", "gemini-2.5-flash"
)


def transcribe_audio_with_gemini(audio_data_url: str) -> dict[str, Any]:
    """Transcribe browser-recorded audio with Gemini using GOOGLE_API_KEY.

    Returns a dict with ok/transcript/mode/error keys. The caller is expected to
    fall back to browser or manual transcript if ok is false.
    """
    load_dotenv(override=False)
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return {
            "ok": False,
            "transcript": "",
            "mode": "fallback_no_google_api_key",
            "error": "GOOGLE_API_KEY is not set.",
        }

    if not audio_data_url:
        return {
            "ok": False,
            "transcript": "",
            "mode": "fallback_no_audio",
            "error": "No audio payload was provided.",
        }

    try:
        mime_type, audio_b64 = _split_data_url(audio_data_url)
        _validate_base64(audio_b64)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Transcribe this customer voice inquiry for a "
                                "packaging sales lead intake assistant. Return "
                                "only the transcript text. Do not summarize."
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": audio_b64,
                            }
                        },
                    ],
                }
            ]
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_TRANSCRIPTION_MODEL}:generateContent?key={api_key}"
        )
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            response_json = json.loads(response.read().decode("utf-8"))
        transcript = _extract_text(response_json)
        if not transcript:
            return {
                "ok": False,
                "transcript": "",
                "mode": "fallback_empty_gemini_transcript",
                "error": "Gemini returned an empty transcript.",
            }
        return {
            "ok": True,
            "transcript": transcript,
            "mode": "gemini_audio_transcription",
            "error": "",
            "mime_type": mime_type,
            "model": GEMINI_TRANSCRIPTION_MODEL,
        }
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "transcript": "",
            "mode": "fallback_gemini_transcription_failed",
            "error": str(exc),
        }


def _split_data_url(audio_data_url: str) -> tuple[str, str]:
    if audio_data_url.startswith("data:"):
        header, audio_b64 = audio_data_url.split(",", 1)
        mime_type = header.removeprefix("data:").split(";")[0] or "audio/webm"
        return mime_type, audio_b64
    return "audio/webm", audio_data_url


def _validate_base64(audio_b64: str) -> None:
    base64.b64decode(audio_b64, validate=True)


def _extract_text(response_json: dict[str, Any]) -> str:
    candidates = response_json.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    return " ".join(part.get("text", "").strip() for part in parts).strip()
