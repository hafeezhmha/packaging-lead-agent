"""Deterministic tools for packaging lead intake and handoff decisions."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_loader import load_business_config


BUSINESS_CONFIG = load_business_config()
COMPANY_NAME = BUSINESS_CONFIG["business"]["name"]
COMPANY_PROFILE = BUSINESS_CONFIG["business"]["description"]
COMPANY_CAPABILITIES = BUSINESS_CONFIG["capabilities"]

VALID_SOURCES = {
    "indiamart": "IndiaMART",
    "justdial": "Justdial",
    "whatsapp": "WhatsApp",
    "website": "Website",
    "phone transcript": "Phone Transcript",
    "phone": "Phone Transcript",
}

PRICE_KEYWORDS = [
    "price",
    "pricing",
    "rate",
    "cost",
    "quote",
    "quotation",
    "how much",
    "rs",
    "inr",
    "₹",
]

COMMITMENT_KEYWORDS = [
    "deliver tomorrow",
    "delivery tomorrow",
    "guarantee",
    "confirm delivery",
    "available now",
    "in stock",
    "final price",
    "discount",
]

URGENCY_KEYWORDS = [
    "urgent",
    "tomorrow",
    "asap",
    "immediately",
    "today",
    "next week",
    "this week",
    "fast delivery",
]

SPAM_KEYWORDS = [
    "lottery",
    "crypto",
    "casino",
    "job offer",
    "loan approved",
    "free money",
]

PRODUCT_FIELD_RULES = {
    product_type: [tuple(item) for item in product_config["required_fields"]]
    for product_type, product_config in BUSINESS_CONFIG["product_categories"].items()
}

FOLLOW_UP_LIMIT = BUSINESS_CONFIG["qualification_rules"]["follow_up_question_limit"]
BULK_QUANTITY_THRESHOLD = BUSINESS_CONFIG["qualification_rules"]["bulk_quantity_threshold"]
WARM_MISSING_FIELD_LIMIT = BUSINESS_CONFIG["qualification_rules"]["warm_missing_field_limit"]


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, int | float):
        return value > 0
    return bool(str(value).strip())


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    for keyword in keywords:
        if keyword in {"rs", "inr"}:
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                return True
            continue
        if keyword in lowered:
            return True
    return False


def _normalize_source(source: str) -> str:
    return VALID_SOURCES.get(_clean(source).lower(), _clean(source) or "Website")


def _infer_product_type(product: str, message: str, explicit_type: str) -> str:
    if explicit_type in PRODUCT_FIELD_RULES:
        return explicit_type

    combined = f"{product} {message}".lower()
    if any(term in combined for term in ["e-commerce", "ecommerce", "shipping"]):
        return "ecommerce_shipping"
    if any(term in combined for term in ["printed", "print", "carton", "skincare", "cosmetic"]):
        return "printed_carton"
    if any(term in combined for term in ["food", "food-grade", "oil", "moisture"]):
        return "food_packaging"
    if any(term in combined for term in ["industrial", "machine", "heavy", "export"]):
        return "industrial_packaging"
    if any(term in combined for term in ["corrugated", "box", "boxes", "ply"]):
        return "corrugated_box"
    return "unknown"


def _is_supported_product(product_type: str, product: str, message: str) -> bool:
    if product_type in PRODUCT_FIELD_RULES:
        return True
    combined = f"{product} {message}".lower()
    return any(
        term in combined
        for term in [
            "box",
            "boxes",
            "carton",
            "cartons",
            "corrugated",
            "packaging",
            "printed",
            "shipping",
        ]
    )


def _missing_fields(lead: dict[str, Any]) -> list[str]:
    product_type = lead["product_type"]
    rules = PRODUCT_FIELD_RULES.get(product_type)
    if not rules:
        return ["supported packaging product type", "quantity", "delivery location"]

    missing = [label for key, label in rules if not _present(lead.get(key))]

    if product_type == "food_packaging" and _present(lead.get("certification_concern")):
        if "certification concern" not in missing:
            missing.append("certification concern")

    return missing


def _next_best_questions(product_type: str, missing_fields: list[str]) -> list[str]:
    if not missing_fields:
        return []
    return missing_fields[:FOLLOW_UP_LIMIT]


def _source_note(source: str) -> str:
    source_behavior = BUSINESS_CONFIG.get("source_behavior", {})
    if source in source_behavior:
        return source_behavior[source]
    return "Lead source is not standard; verify context before follow-up."


def _score_lead(
    lead: dict[str, Any],
    missing_fields: list[str],
    urgent: bool,
    spam: bool,
    unsupported: bool,
) -> str:
    if spam:
        return "Spam"
    if unsupported:
        return "Cold"

    has_product = lead["product_type"] != "unknown" or _present(lead.get("product"))
    has_quantity = _present(lead.get("quantity"))
    has_location = _present(lead.get("location"))
    quantity = int(lead.get("quantity") or 0)
    has_business_intent = has_product and (
        has_quantity
        or _present(lead.get("industry"))
        or _present(lead.get("company_name"))
    )

    if has_product and has_quantity and has_location and (
        urgent or quantity >= BULK_QUANTITY_THRESHOLD
    ):
        return "Hot"
    if has_business_intent and len(missing_fields) <= WARM_MISSING_FIELD_LIMIT:
        return "Warm"
    if has_product or has_business_intent:
        return "Cold"
    return "Cold"


def _handoff_trigger(
    status: str,
    missing_fields: list[str],
    price_request: bool,
    commitment_request: bool,
    urgent: bool,
    unsupported: bool,
    confidence: str,
) -> str:
    if status == "Spam":
        return "none"
    if price_request:
        return "price_request"
    if commitment_request:
        return "delivery_commitment"
    if urgent:
        return "urgent_timeline"
    if unsupported:
        return "unsupported_request"
    if confidence.lower() == "low":
        return "low_confidence"
    if status == "Hot":
        return "hot_lead"
    if not missing_fields and status in {"Hot", "Warm"}:
        return "complete_quote_ready"
    return "none"


def _handoff_required(trigger: str) -> bool:
    return trigger != "none"


def _customer_need(lead: dict[str, Any]) -> str:
    parts = []
    if _present(lead.get("quantity")):
        parts.append(str(lead["quantity"]))
    if _present(lead.get("product")):
        parts.append(str(lead["product"]))
    elif lead["product_type"] != "unknown":
        parts.append(lead["product_type"].replace("_", " "))
    if _present(lead.get("industry")):
        parts.append(f"for {lead['industry']}")
    if _present(lead.get("location")):
        parts.append(f"in {lead['location']}")
    return " ".join(parts) or "Packaging inquiry"


def _suggested_response(
    lead: dict[str, Any],
    missing_fields: list[str],
    status: str,
    price_request: bool,
    commitment_request: bool,
    urgent: bool,
    unsupported: bool,
) -> str:
    if status == "Spam":
        return (
            f"{COMPANY_NAME} can help with corrugated shipping boxes, printed "
            "cartons, food-grade packaging inquiries, e-commerce packaging, and "
            "industrial packaging. Please share a packaging requirement if you have one."
        )

    if unsupported:
        return BUSINESS_CONFIG["response_templates"]["unsupported_request"]

    next_questions = _next_best_questions(lead["product_type"], missing_fields)
    if price_request:
        if next_questions:
            fields = ", ".join(next_questions)
            return (
                f"{BUSINESS_CONFIG['response_templates']['price_request']} "
                f"Before I pass this to sales, please share {fields}."
            )
        return BUSINESS_CONFIG["response_templates"]["price_request"]

    if commitment_request:
        if next_questions:
            fields = ", ".join(next_questions)
            return (
                f"{BUSINESS_CONFIG['response_templates']['commitment_request']} "
                f"Before I pass this to sales, please share {fields}."
            )
        return BUSINESS_CONFIG["response_templates"]["commitment_request"]

    if next_questions:
        fields = ", ".join(next_questions)
        product = lead.get("product") or lead["product_type"].replace("_", " ")
        prefix = f"Yes, {COMPANY_NAME} can help with {product}."
        if urgent:
            prefix = (
                f"{COMPANY_NAME} can help with {product}. This sounds urgent, "
                "so I will pass it to sales for quick confirmation."
            )
        return f"{prefix} Please share {fields}."

    return (
        "Thanks, I have the key details needed for sales review. I will prepare "
        "a handoff so the team can confirm feasibility, pricing, and delivery timeline."
    )


def _suggested_human_action(status: str, trigger: str, missing_fields: list[str]) -> str:
    if status == "Hot" or trigger in {"urgent_timeline", "price_request", "delivery_commitment"}:
        action = "Call customer within 30 minutes"
    else:
        action = "Review lead and follow up"

    if missing_fields:
        return f"{action} to collect {', '.join(missing_fields[:FOLLOW_UP_LIMIT])}."
    return f"{action} to confirm feasibility, pricing, and delivery timeline."


def _suggested_human_script(lead: dict[str, Any], missing_fields: list[str]) -> str:
    details = _next_best_questions(lead["product_type"], missing_fields)
    if not details:
        details = ["final specifications", "delivery address", "expected timeline"]

    need = _customer_need(lead)
    return BUSINESS_CONFIG["suggested_human_script"].format(
        business_name=COMPANY_NAME,
        customer_need=need,
        missing_fields=", ".join(details),
    )


def _handoff_summary(
    lead: dict[str, Any],
    status: str,
    missing_fields: list[str],
    trigger: str,
    risk_notes: list[str],
) -> str:
    known_details = {
        "Product": lead.get("product"),
        "Product type": lead.get("product_type"),
        "Quantity": lead.get("quantity") if _present(lead.get("quantity")) else None,
        "Industry": lead.get("industry"),
        "Location": lead.get("location"),
        "Timeline": lead.get("timeline"),
        "Dimensions": lead.get("dimensions"),
        "Ply": lead.get("ply"),
        "BF/GSM or material strength": lead.get("material_strength"),
        "Paperboard/GSM": lead.get("paperboard_gsm"),
        "Print colors": lead.get("print_colors"),
        "Finish/lamination": lead.get("finish_lamination"),
        "Artwork ready": lead.get("artwork_ready"),
        "Food-grade requirement": lead.get("food_grade_requirement"),
        "Moisture/oil barrier": lead.get("barrier_requirement"),
        "Certification concern": lead.get("certification_concern"),
        "Product weight": lead.get("product_weight"),
        "Fragility": lead.get("fragility"),
        "Shipment volume": lead.get("shipment_volume"),
        "Branding/printing need": lead.get("branding_printing_need"),
        "Handling/storage": lead.get("handling_storage_requirement"),
        "Budget range": lead.get("budget_range"),
        "Company": lead.get("company_name"),
        "Contact": lead.get("contact_name"),
        "Phone": lead.get("phone"),
        "Email": lead.get("email"),
    }

    known_lines = [
        f"- {label}: {value}"
        for label, value in known_details.items()
        if _present(value)
    ]
    missing_lines = [f"- {field}" for field in missing_fields] or ["- None"]
    risk_lines = [f"- {note}" for note in risk_notes]

    return "\n".join(
        [
            f"Lead Source: {lead['source']}",
            f"Lead Status: {status}",
            f"Extraction Confidence: {lead['extraction_confidence']}",
            f"Handoff Trigger: {trigger}",
            "",
            "Customer Need:",
            _customer_need(lead),
            "",
            "Known Details:",
            "\n".join(known_lines) if known_lines else "- No useful business details captured",
            "",
            "Missing Details:",
            "\n".join(missing_lines),
            "",
            "Risk/Notes:",
            "\n".join(risk_lines),
            "- Do not quote price without exact specifications.",
            "- Do not promise delivery dates or inventory availability without human confirmation.",
            "",
            "Suggested Human Action:",
            _suggested_human_action(status, trigger, missing_fields),
            "",
            "Suggested Human Script:",
            _suggested_human_script(lead, missing_fields),
        ]
    )


def _risk_notes(
    source: str,
    trigger: str,
    price_request: bool,
    commitment_request: bool,
    urgent: bool,
    unsupported: bool,
    confidence: str,
) -> list[str]:
    notes = [_source_note(source)]
    if price_request:
        notes.append("Customer asked for price or quotation.")
    if commitment_request:
        notes.append("Customer asked for delivery, inventory, discount, or final commitment.")
    if urgent:
        notes.append("Customer may expect a fast delivery confirmation.")
    if unsupported:
        notes.append("Request may be outside known company capabilities.")
    if confidence.lower() == "low":
        notes.append("Extraction confidence is low; human should verify details.")
    if trigger == "complete_quote_ready":
        notes.append("Core quote details are captured; human should confirm feasibility and pricing.")
    if trigger == "hot_lead":
        notes.append("Lead qualifies as hot due to bulk quantity or strong intent.")
    return notes


def _log_lead(log_path: str, record: dict[str, Any]) -> None:
    if not log_path:
        return
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def qualify_packaging_lead(
    message: str,
    source: str = "Website",
    product: str = "",
    product_type: str = "",
    quantity: int = 0,
    industry: str = "",
    location: str = "",
    timeline: str = "",
    dimensions: str = "",
    ply: str = "",
    material_strength: str = "",
    material_gsm: str = "",
    paperboard_gsm: str = "",
    print_colors: str = "",
    finish_lamination: str = "",
    artwork_ready: str = "",
    food_grade_requirement: str = "",
    barrier_requirement: str = "",
    certification_concern: str = "",
    product_weight: str = "",
    fragility: str = "",
    shipment_volume: str = "",
    branding_printing_need: str = "",
    industrial_product_type: str = "",
    handling_storage_requirement: str = "",
    printing_type: str = "",
    budget_range: str = "",
    contact_name: str = "",
    company_name: str = "",
    phone: str = "",
    email: str = "",
    transcript_summary: str = "",
    intent: str = "packaging_inquiry",
    extraction_confidence: str = "medium",
    confidence: str = "",
    log_path: str = "lead_log.jsonl",
) -> dict[str, Any]:
    """Qualify a packaging lead after the LLM extracts fields from the message.

    Args:
        message: Original customer message or phone transcript.
        source: IndiaMART, Justdial, WhatsApp, Website, or Phone Transcript.
        product: Packaging product requested, if known.
        product_type: corrugated_box, printed_carton, food_packaging,
            ecommerce_shipping, industrial_packaging, or unknown.
        quantity: Number of units requested. Use 0 when unknown.
        industry: Customer industry such as skincare, food, D2C, manufacturing.
        location: Delivery or customer location.
        timeline: Requested delivery or purchase timeline.
        dimensions: Box/carton dimensions, if provided.
        ply: Corrugated ply, if provided.
        material_strength: BF/GSM/material strength for corrugated boxes.
        material_gsm: Backward-compatible material/GSM field.
        paperboard_gsm: Paperboard/GSM for printed cartons.
        print_colors: Number of print colors.
        finish_lamination: Finish or lamination requirement.
        artwork_ready: Whether print artwork is ready.
        food_grade_requirement: Food-grade requirement for food packaging.
        barrier_requirement: Moisture/oil barrier need.
        certification_concern: Any customer-mentioned certification concern.
        product_weight: Weight of packed product.
        fragility: Fragility information for e-commerce shipping.
        shipment_volume: Approximate shipment volume.
        branding_printing_need: Branding or printing need.
        industrial_product_type: Product being packed for industrial packaging.
        handling_storage_requirement: Handling or storage requirement.
        printing_type: Backward-compatible printing field.
        budget_range: Customer budget range, if provided. This is not a quote.
        contact_name: Customer contact name, if provided.
        company_name: Customer company name, if provided.
        phone: Customer phone, if provided.
        email: Customer email, if provided.
        transcript_summary: Clean summary when source is Phone Transcript.
        intent: LLM-classified intent.
        extraction_confidence: LLM extraction confidence: high, medium, or low.
        confidence: Backward-compatible confidence field.
        log_path: JSONL path for local lead logging. Empty string disables logging.

    Returns:
        A deterministic qualification record with missing fields, lead status,
        confidence, handoff trigger, suggested response, handoff summary, and
        local log status.
    """
    source = _normalize_source(source)
    confidence_value = _clean(extraction_confidence or confidence or "medium").lower()
    if confidence_value not in {"high", "medium", "low"}:
        confidence_value = "medium"

    material_strength_value = _clean(material_strength) or _clean(material_gsm)
    product_type_value = _infer_product_type(product, message, _clean(product_type))
    if product_type_value == "printed_carton" and not _clean(print_colors):
        print_colors = _clean(printing_type)

    lead = {
        "source": source,
        "raw_message": _clean(message),
        "transcript_summary": _clean(transcript_summary),
        "product": _clean(product),
        "product_type": product_type_value,
        "quantity": quantity if quantity > 0 else 0,
        "industry": _clean(industry),
        "location": _clean(location),
        "timeline": _clean(timeline),
        "dimensions": _clean(dimensions),
        "ply": _clean(ply),
        "material_strength": material_strength_value,
        "paperboard_gsm": _clean(paperboard_gsm),
        "print_colors": _clean(print_colors),
        "finish_lamination": _clean(finish_lamination),
        "artwork_ready": _clean(artwork_ready),
        "food_grade_requirement": _clean(food_grade_requirement),
        "barrier_requirement": _clean(barrier_requirement),
        "certification_concern": _clean(certification_concern),
        "product_weight": _clean(product_weight),
        "fragility": _clean(fragility),
        "shipment_volume": _clean(shipment_volume),
        "branding_printing_need": _clean(branding_printing_need),
        "industrial_product_type": _clean(industrial_product_type) or _clean(product),
        "handling_storage_requirement": _clean(handling_storage_requirement),
        "budget_range": _clean(budget_range),
        "contact_name": _clean(contact_name),
        "company_name": _clean(company_name),
        "phone": _clean(phone),
        "email": _clean(email),
        "intent": _clean(intent),
        "extraction_confidence": confidence_value,
    }

    text = f"{message} {timeline}"
    price_request = _contains_any(text, PRICE_KEYWORDS)
    commitment_request = _contains_any(text, COMMITMENT_KEYWORDS)
    urgent = _contains_any(text, URGENCY_KEYWORDS)
    spam = _contains_any(text, SPAM_KEYWORDS) or intent.lower() in {"spam", "irrelevant"}
    supported_product = _is_supported_product(product_type_value, product, message)
    unsupported = not spam and bool(message.strip()) and not supported_product
    missing = _missing_fields(lead) if not spam and not unsupported else []
    status = _score_lead(lead, missing, urgent, spam, unsupported)
    trigger = _handoff_trigger(
        status=status,
        missing_fields=missing,
        price_request=price_request,
        commitment_request=commitment_request,
        urgent=urgent,
        unsupported=unsupported,
        confidence=confidence_value,
    )
    handoff = _handoff_required(trigger)
    notes = _risk_notes(
        source=source,
        trigger=trigger,
        price_request=price_request,
        commitment_request=commitment_request,
        urgent=urgent,
        unsupported=unsupported,
        confidence=confidence_value,
    )
    handoff_summary = (
        _handoff_summary(lead, status, missing, trigger, notes) if handoff else ""
    )
    next_questions = _next_best_questions(product_type_value, missing)
    conversation_stage = "needs_clarification" if next_questions else "ready_for_handoff"
    if status == "Spam":
        conversation_stage = "closed"
    elif unsupported:
        conversation_stage = "human_review"
    elif not handoff and not next_questions:
        conversation_stage = "qualified_without_handoff"

    result = {
        "company": {
            "name": COMPANY_NAME,
            "profile": COMPANY_PROFILE,
            "capabilities": COMPANY_CAPABILITIES,
        },
        "lead": lead,
        "source": source,
        "missing_fields": missing,
        "next_questions": next_questions,
        "clarifying_questions": next_questions,
        "conversation_stage": conversation_stage,
        "lead_status": status,
        "extraction_confidence": confidence_value,
        "urgency": "high" if urgent else "normal",
        "safety_flags": {
            "price_request": price_request,
            "commitment_request": commitment_request,
            "unsupported_request": unsupported,
            "spam_or_irrelevant": spam,
        },
        "handoff_required": handoff,
        "handoff_trigger": trigger,
        "handoff_summary": handoff_summary,
        "suggested_response": _suggested_response(
            lead=lead,
            missing_fields=missing,
            status=status,
            price_request=price_request,
            commitment_request=commitment_request,
            urgent=urgent,
            unsupported=unsupported,
        ),
    }

    log_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "raw_message": lead["raw_message"],
        "extracted_lead": lead,
        "lead_status": status,
        "extraction_confidence": confidence_value,
        "handoff_required": handoff,
        "handoff_trigger": trigger,
        "handoff_summary": handoff_summary,
    }
    _log_lead(log_path, log_record)
    result["log_record"] = log_record
    result["log_path"] = log_path
    return result
