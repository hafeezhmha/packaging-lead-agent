"""Evaluation runner for BLRPackworks lead-intake prototype."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from packaging_lead_intake.pipeline import extract_demo_fields, qualification_kwargs
from packaging_lead_intake.tools import qualify_packaging_lead


TEST_CASES_PATH = Path("eval/test_cases.json")
EVAL_LOG_PATH = "eval/eval_lead_log.jsonl"


def main() -> None:
    cases = json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))
    results = [run_case(case) for case in cases]
    print_report(results)


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    extracted = extract_demo_fields(case["source"], case["message"], log_path=EVAL_LOG_PATH)
    result = qualify_packaging_lead(**qualification_kwargs(extracted))
    latency = time.perf_counter() - started
    task_completed = bool(result["suggested_response"] or result["handoff_summary"])
    voice_case = case.get("input_type") == "voice" or case["source"] == "Phone Transcript"
    voice_completed = voice_case and bool(case["message"]) and task_completed

    checks = {
        "product_type": result["lead"]["product_type"] == case["expected_product_type"],
        "lead_status": result["lead_status"] == case["expected_lead_status"],
        "handoff_required": result["handoff_required"] == case["expected_handoff_required"],
        "handoff_trigger": result["handoff_trigger"] == case["expected_handoff_trigger"],
        "missing_fields": _missing_field_score(
            expected=case["expected_missing_fields"],
            actual=result["missing_fields"],
        ),
        "safety": safety_check(case, result),
    }
    failed = []
    for name, value in checks.items():
        passed = value if isinstance(value, bool) else value["passed"]
        if not passed:
            failed.append(name)

    return {
        "id": case["id"],
        "latency": latency,
        "expected": {
            "product_type": case["expected_product_type"],
            "lead_status": case["expected_lead_status"],
            "handoff_required": case["expected_handoff_required"],
            "handoff_trigger": case["expected_handoff_trigger"],
            "missing_fields": case["expected_missing_fields"],
        },
        "actual": {
            "product_type": result["lead"]["product_type"],
            "lead_status": result["lead_status"],
            "handoff_required": result["handoff_required"],
            "handoff_trigger": result["handoff_trigger"],
            "missing_fields": result["missing_fields"],
            "suggested_response": result["suggested_response"],
        },
        "checks": checks,
        "failed": failed,
        "passed": not failed,
        "task_completed": task_completed,
        "voice_case": voice_case,
        "voice_completed": voice_completed,
        "contained": not result["handoff_required"],
        "human_handoff": result["handoff_required"],
        "fallback_or_low_confidence": (
            result["extraction_confidence"] == "low"
            or result["handoff_trigger"] in {"low_confidence", "unsupported_request"}
        ),
    }


def _missing_field_score(expected: list[str], actual: list[str]) -> dict[str, Any]:
    if not expected:
        return {"passed": not actual, "score": 1.0 if not actual else 0.0}
    expected_set = set(expected)
    actual_set = set(actual)
    score = len(expected_set & actual_set) / len(expected_set)
    return {"passed": score >= 0.75, "score": score}


def safety_check(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    text = f"{result['suggested_response']} {result['handoff_summary']}".lower()
    violations = []
    safety = case.get("safety", {})
    if safety.get("should_not_quote_price") and _contains_bad_price(text):
        violations.append("quoted_price")
    if safety.get("should_not_promise_delivery") and _contains_delivery_promise(text):
        violations.append("promised_delivery")
    if safety.get("should_handoff_to_human") and not result["handoff_required"]:
        violations.append("missing_handoff")
    return {"passed": not violations, "violations": violations}


def _contains_bad_price(text: str) -> bool:
    allowed_context = ["1000 boxes", "2000 units", "5000 custom", "3000 10x8x4"]
    scrubbed = text
    for phrase in allowed_context:
        scrubbed = scrubbed.replace(phrase, "")
    return bool(re.search(r"(₹|rs\.?|inr)\s*\d+|\d+\s*(per box|/box)", scrubbed))


def _contains_delivery_promise(text: str) -> bool:
    bad_phrases = [
        "we can deliver tomorrow",
        "delivery is confirmed",
        "guaranteed delivery",
        "will deliver by",
    ]
    return any(phrase in text for phrase in bad_phrases)


def print_report(results: list[dict[str, Any]]) -> None:
    total = len(results)
    product_accuracy = avg_bool(results, "product_type")
    status_accuracy = avg_bool(results, "lead_status")
    handoff_accuracy = avg_bool(results, "handoff_required")
    trigger_accuracy = avg_bool(results, "handoff_trigger")
    missing_accuracy = sum(r["checks"]["missing_fields"]["score"] for r in results) / total
    safety_violations = sum(len(r["checks"]["safety"]["violations"]) for r in results)
    avg_latency = sum(r["latency"] for r in results) / total
    task_completion_rate = sum(1 for r in results if r["task_completed"] and r["passed"]) / total
    containment_rate = sum(1 for r in results if r["contained"]) / total
    human_handoff_rate = sum(1 for r in results if r["human_handoff"]) / total
    fallback_low_conf_rate = sum(1 for r in results if r["fallback_or_low_confidence"]) / total
    voice_cases = [r for r in results if r["voice_case"]]
    voice_completion_rate = (
        sum(1 for r in voice_cases if r["voice_completed"]) / len(voice_cases)
        if voice_cases
        else 0.0
    )

    print("Evaluation Results")
    print(
        "Note: this is a controlled baseline evaluation against deterministic "
        "demo extraction and business-rule code, not a claim of real-world "
        "LLM/STT production performance."
    )
    for result in results:
        mark = "PASS" if result["passed"] else "FAIL"
        print(f"- {result['id']}: {mark}")
        print(f"  expected: {json.dumps(result['expected'], ensure_ascii=True)}")
        print(f"  actual:   {json.dumps(result['actual'], ensure_ascii=True)}")
        if result["failed"]:
            print(f"  failed checks: {', '.join(result['failed'])}")

    print("\nEvaluation Summary")
    print(f"- Product Classification Accuracy: {product_accuracy:.1%}")
    print(f"- Lead Status Accuracy: {status_accuracy:.1%}")
    print(f"- Handoff Decision Accuracy: {handoff_accuracy:.1%}")
    print(f"- Handoff Trigger Accuracy: {trigger_accuracy:.1%}")
    print(f"- Missing Field Detection Accuracy: {missing_accuracy:.1%}")
    print(f"- Safety Violations: {safety_violations}")
    print(f"- Task Completion Rate: {task_completion_rate:.1%}")
    print(f"- Containment Rate: {containment_rate:.1%}")
    print(f"- Human Handoff Rate: {human_handoff_rate:.1%}")
    print(f"- Fallback / Low Confidence Rate: {fallback_low_conf_rate:.1%}")
    print(f"- Average Processing Latency: {avg_latency:.4f}s")
    print(f"- Voice Flow Completion Rate: {voice_completion_rate:.1%}")


def avg_bool(results: list[dict[str, Any]], check_name: str) -> float:
    return sum(1 for result in results if result["checks"][check_name]) / len(results)


if __name__ == "__main__":
    main()
