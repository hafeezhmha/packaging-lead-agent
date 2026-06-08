"""Verify Gemini text and audio transcription calls with one GOOGLE_API_KEY.

Usage:
    python verify_gemini.py --audio path/to/voice.webm

The script never exposes the API key to the frontend. It reads `.env` on the
server side and calls Gemini directly from Python.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from packlead.stt import transcribe_audio_with_gemini


TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audio",
        required=True,
        help="Path to a short audio file containing speech, e.g. webm/wav/mp3.",
    )
    args = parser.parse_args()

    load_dotenv(override=False)
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        print("FAIL: GOOGLE_API_KEY is not set in .env or environment.")
        return 1

    text_ok = verify_text_call(api_key)
    audio_ok = verify_audio_call(Path(args.audio))

    if text_ok and audio_ok:
        print("\nVerification passed: one GOOGLE_API_KEY works for text and audio transcription.")
        return 0
    print("\nVerification failed. See messages above.")
    return 1


def verify_text_call(api_key: str) -> bool:
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Reply with exactly: PackLead Gemini text check OK"
                        )
                    }
                ],
            }
        ]
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{TEXT_MODEL}:generateContent?key={api_key}"
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
        text = extract_text(response_json)
        print(f"Text Gemini call: OK")
        print(f"Text response: {text}")
        return bool(text)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Text Gemini call: FAIL ({exc})")
        return False


def verify_audio_call(audio_path: Path) -> bool:
    if not audio_path.exists():
        print(f"Audio transcription call: FAIL ({audio_path} does not exist)")
        return False
    mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/webm"
    audio_b64 = audio_path.read_bytes()
    import base64

    data_url = f"data:{mime_type};base64,{base64.b64encode(audio_b64).decode('ascii')}"
    result = transcribe_audio_with_gemini(data_url)
    if not result["ok"]:
        print(f"Audio transcription call: FAIL ({result['mode']}: {result['error']})")
        return False
    print("Audio transcription call: OK")
    print(f"Transcription model: {result.get('model')}")
    print(f"Transcript: {result['transcript']}")
    return True


def extract_text(response_json: dict) -> str:
    candidates = response_json.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    return " ".join(part.get("text", "").strip() for part in parts).strip()


if __name__ == "__main__":
    sys.exit(main())
