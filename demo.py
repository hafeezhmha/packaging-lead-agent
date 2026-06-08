"""Local deterministic demo for the PackLead tool.

This script does not call an LLM. It shows the rule-based layer that the ADK
agent uses after the model extracts fields from a customer message.
"""

from __future__ import annotations

import json

from packlead.tools import qualify_packaging_lead


DEMO_CASES = [
    {
        "name": "Hot IndiaMART printed carton lead",
        "kwargs": {
            "source": "IndiaMART",
            "message": "Need 5000 custom printed boxes for skincare brand in Bangalore. Delivery next week.",
            "product": "custom printed cartons",
            "product_type": "printed_carton",
            "quantity": 5000,
            "industry": "skincare",
            "location": "Bangalore",
            "timeline": "next week",
            "extraction_confidence": "high",
            "log_path": "lead_log.jsonl",
        },
    },
    {
        "name": "Vague WhatsApp corrugated inquiry",
        "kwargs": {
            "source": "WhatsApp",
            "message": "Hi, do you make corrugated boxes for e-commerce shipping?",
            "product": "corrugated boxes for e-commerce shipping",
            "product_type": "ecommerce_shipping",
            "industry": "e-commerce",
            "extraction_confidence": "high",
            "log_path": "lead_log.jsonl",
        },
    },
    {
        "name": "Urgent price request",
        "kwargs": {
            "source": "Justdial",
            "message": "What is the price for 1000 boxes? I need delivery tomorrow.",
            "product": "boxes",
            "product_type": "corrugated_box",
            "quantity": 1000,
            "timeline": "tomorrow",
            "extraction_confidence": "medium",
            "log_path": "lead_log.jsonl",
        },
    },
    {
        "name": "Spam",
        "kwargs": {
            "source": "Website",
            "message": "Congratulations, your crypto lottery prize is ready.",
            "intent": "spam",
            "extraction_confidence": "high",
            "log_path": "lead_log.jsonl",
        },
    },
    {
        "name": "Complete quote-ready industrial packaging lead",
        "kwargs": {
            "source": "Website",
            "message": "We need 1200 industrial cartons for metal components, 20 kg each, 18x12x10 inch, stacked warehouse storage, delivery in Peenya.",
            "product": "industrial cartons",
            "product_type": "industrial_packaging",
            "industrial_product_type": "metal components",
            "quantity": 1200,
            "product_weight": "20 kg each",
            "dimensions": "18x12x10 inch",
            "handling_storage_requirement": "stacked warehouse storage",
            "location": "Peenya, Bangalore",
            "extraction_confidence": "high",
            "log_path": "lead_log.jsonl",
        },
    },
    {
        "name": "Phone transcript lead",
        "kwargs": {
            "source": "Phone Transcript",
            "message": "Caller says they sell snack jars online. They need shipping boxes, around two thousand per month, product weighs 700 grams, some jars break in transit, wants logo printing, delivery to HSR Layout.",
            "transcript_summary": "Customer sells snack jars online and needs e-commerce shipping boxes for fragile 700 g products, about 2000 per month, with logo printing and delivery to HSR Layout.",
            "product": "e-commerce shipping boxes",
            "product_type": "ecommerce_shipping",
            "quantity": 2000,
            "industry": "food e-commerce",
            "location": "HSR Layout, Bangalore",
            "product_weight": "700 g",
            "fragility": "glass jars can break in transit",
            "shipment_volume": "about 2000 per month",
            "branding_printing_need": "logo printing",
            "extraction_confidence": "medium",
            "log_path": "lead_log.jsonl",
        },
    },
]


def main() -> None:
    for case in DEMO_CASES:
        result = qualify_packaging_lead(**case["kwargs"])
        print(f"\n## {case['name']}")
        print(
            json.dumps(
                {
                    "source": result["source"],
                    "lead_status": result["lead_status"],
                    "product_type": result["lead"]["product_type"],
                    "extraction_confidence": result["extraction_confidence"],
                    "missing_fields": result["missing_fields"],
                    "next_questions": result["next_questions"],
                    "handoff_required": result["handoff_required"],
                    "handoff_trigger": result["handoff_trigger"],
                    "suggested_response": result["suggested_response"],
                    "handoff_summary": result["handoff_summary"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
