from packaging_lead_intake.tools import qualify_packaging_lead
from packaging_lead_intake.pipeline import stream_process_events


def test_price_request_must_not_produce_numeric_price(tmp_path):
    result = qualify_packaging_lead(
        source="Justdial",
        message="What is the price for 1000 boxes?",
        product="corrugated boxes",
        product_type="corrugated_box",
        quantity=1000,
        log_path=str(tmp_path / "leads.jsonl"),
    )

    assert result["handoff_trigger"] == "price_request"
    assert "1000" not in result["suggested_response"]
    assert "Pricing depends" in result["suggested_response"]
    assert "Before I pass this to sales" in result["suggested_response"]
    assert result["conversation_stage"] == "needs_clarification"


def test_urgent_delivery_request_triggers_handoff(tmp_path):
    result = qualify_packaging_lead(
        source="WhatsApp",
        message="Need boxes tomorrow, urgent delivery.",
        product="boxes",
        product_type="corrugated_box",
        timeline="tomorrow",
        log_path=str(tmp_path / "leads.jsonl"),
    )

    assert result["handoff_required"] is True
    assert result["handoff_trigger"] == "urgent_timeline"


def test_spam_not_sent_to_sales_as_hot_or_warm(tmp_path):
    result = qualify_packaging_lead(
        source="Website",
        message="Crypto lottery prize available now.",
        intent="spam",
        log_path=str(tmp_path / "leads.jsonl"),
    )

    assert result["lead_status"] == "Spam"
    assert result["handoff_required"] is False


def test_bulk_printed_box_lead_becomes_hot(tmp_path):
    result = qualify_packaging_lead(
        source="IndiaMART",
        message="Need 5000 printed cartons for skincare brand in Bangalore.",
        product="printed cartons",
        product_type="printed_carton",
        quantity=5000,
        industry="skincare",
        location="Bangalore",
        log_path=str(tmp_path / "leads.jsonl"),
    )

    assert result["lead_status"] == "Hot"
    assert result["handoff_required"] is True


def test_vague_corrugated_inquiry_asks_follow_up_questions(tmp_path):
    result = qualify_packaging_lead(
        source="WhatsApp",
        message="Do you make corrugated boxes for e-commerce shipping?",
        product="corrugated boxes for e-commerce shipping",
        product_type="ecommerce_shipping",
        log_path=str(tmp_path / "leads.jsonl"),
    )

    assert result["handoff_required"] is False
    assert 1 <= len(result["next_questions"]) <= 4
    assert "Please share" in result["suggested_response"]


def test_unsupported_request_triggers_human_review(tmp_path):
    result = qualify_packaging_lead(
        source="Website",
        message="Can you manufacture plastic water bottles?",
        product="plastic water bottles",
        extraction_confidence="medium",
        log_path=str(tmp_path / "leads.jsonl"),
    )

    assert result["handoff_required"] is True
    assert result["handoff_trigger"] == "unsupported_request"


def test_complete_quote_ready_lead_generates_handoff_summary(tmp_path):
    result = qualify_packaging_lead(
        source="Website",
        message="Need 3000 10x8x4 inch 5 ply corrugated boxes for 2 kg products in Peenya.",
        product="corrugated boxes",
        product_type="corrugated_box",
        quantity=3000,
        dimensions="10x8x4 inch",
        ply="5 ply",
        material_strength="32 BF",
        product_weight="2 kg",
        location="Peenya, Bangalore",
        log_path=str(tmp_path / "leads.jsonl"),
    )

    assert result["lead_status"] == "Hot"
    assert result["missing_fields"] == []
    assert result["handoff_required"] is True
    assert "Suggested Human Script:" in result["handoff_summary"]
    assert (tmp_path / "leads.jsonl").exists()


def test_voice_processing_prefers_edited_transcript(tmp_path):
    events = list(
        stream_process_events(
            source="Phone Transcript",
            message="old browser text",
            input_type="voice",
            transcript="edited transcript for 2000 food boxes in Indiranagar",
            audio_base64="data:audio/webm;base64,not-real-audio",
            log_path=str(tmp_path / "leads.jsonl"),
        )
    )

    transcription = next(event for event in events if event["event"] == "transcription")
    extraction = next(event for event in events if event["event"] == "extraction")

    assert transcription["data"]["transcript"] == "edited transcript for 2000 food boxes in Indiranagar"
    assert transcription["data"]["mode"] == "manual_transcript"
    assert transcription["data"]["gemini_attempted"] is False
    assert extraction["data"]["message"] == "edited transcript for 2000 food boxes in Indiranagar"


def test_stream_emits_conversation_check_before_handoff(tmp_path):
    events = list(
        stream_process_events(
            source="Justdial",
            message="What is the price for 1000 boxes? I need them tomorrow.",
            log_path=str(tmp_path / "leads.jsonl"),
        )
    )
    names = [event["event"] for event in events]
    conversation = next(event for event in events if event["event"] == "conversation_check")

    assert names.index("conversation_check") < names.index("handoff")
    assert conversation["data"]["stage"] == "needs_clarification"
    assert conversation["data"]["clarifying_questions"]


def test_stream_allows_disabled_log_path():
    events = list(
        stream_process_events(
            source="WhatsApp",
            message="Do you make boxes for online shipping?",
            log_path="",
        )
    )

    lead_log = next(event for event in events if event["event"] == "lead_log")
    assert lead_log["data"]["recent"] == []
