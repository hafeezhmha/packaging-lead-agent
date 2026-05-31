# Demo Output

These examples show the intended founder-demo flow: raw message, extracted
fields, deterministic decision, assistant reply, and handoff context.

## Flow 1: Hot IndiaMART Lead

Raw message:

> Need 5000 custom printed boxes for skincare brand in Bangalore. Delivery next week.

Extracted fields:

```json
{
  "source": "IndiaMART",
  "product": "custom printed cartons",
  "product_type": "printed_carton",
  "quantity": 5000,
  "industry": "skincare",
  "location": "Bangalore",
  "timeline": "next week",
  "extraction_confidence": "high"
}
```

Deterministic decision:

```json
{
  "lead_status": "Hot",
  "handoff_required": true,
  "handoff_trigger": "urgent_timeline",
  "missing_fields": [
    "dimensions",
    "paperboard/GSM",
    "number of print colors",
    "finish/lamination",
    "artwork readiness"
  ],
  "next_questions": [
    "dimensions",
    "paperboard/GSM",
    "number of print colors",
    "finish/lamination"
  ]
}
```

Assistant reply:

> BLRPackworks can help with custom printed cartons. This sounds urgent, so I will pass it to sales for quick confirmation. Please share dimensions, paperboard/GSM, number of print colors, finish/lamination.

Handoff summary:

```text
Lead Source: IndiaMART
Lead Status: Hot
Extraction Confidence: high
Handoff Trigger: urgent_timeline

Customer Need:
5000 custom printed cartons for skincare in Bangalore

Known Details:
- Product: custom printed cartons
- Product type: printed_carton
- Quantity: 5000
- Industry: skincare
- Location: Bangalore
- Timeline: next week

Missing Details:
- dimensions
- paperboard/GSM
- number of print colors
- finish/lamination
- artwork readiness

Risk/Notes:
- IndiaMART lead may be partial; qualify before sales spends time.
- Customer may expect a fast delivery confirmation.
- Do not quote price without exact specifications.
- Do not promise delivery dates or inventory availability without human confirmation.

Suggested Human Action:
Call customer within 30 minutes to collect dimensions, paperboard/GSM, number of print colors, finish/lamination.

Suggested Human Script:
Hi, this is from BLRPackworks. I saw your requirement for 5000 custom printed cartons for skincare in Bangalore. To prepare an accurate quote, could you confirm dimensions, paperboard/GSM, number of print colors, finish/lamination?
```

## Flow 2: Vague WhatsApp Lead

Raw message:

> Hi, do you make corrugated boxes for e-commerce shipping?

Extracted fields:

```json
{
  "source": "WhatsApp",
  "product": "corrugated boxes for e-commerce shipping",
  "product_type": "ecommerce_shipping",
  "industry": "e-commerce",
  "extraction_confidence": "high"
}
```

Missing details:

```json
[
  "product weight",
  "fragility",
  "approximate shipment volume",
  "branding/printing need",
  "box dimensions",
  "delivery location"
]
```

Assistant follow-up:

> Yes, BLRPackworks can help with corrugated boxes for e-commerce shipping. Please share product weight, fragility, approximate shipment volume, branding/printing need.

## Flow 3: Urgent Price Request

Raw message:

> What is the price for 1000 boxes? I need delivery tomorrow.

Safety behavior:

- No numeric price is generated.
- No delivery promise is made.
- Human handoff is required.

Handoff trigger:

```json
{
  "handoff_required": true,
  "handoff_trigger": "price_request"
}
```

Handoff summary:

```text
Lead Source: Justdial
Lead Status: Cold
Extraction Confidence: medium
Handoff Trigger: price_request

Customer Need:
1000 boxes

Known Details:
- Product: boxes
- Product type: corrugated_box
- Quantity: 1000
- Timeline: tomorrow

Missing Details:
- length x width x height
- ply
- BF/GSM or material strength
- product weight
- delivery location

Risk/Notes:
- Justdial lead may be partial; qualify before sales spends time.
- Customer asked for price or quotation.
- Customer asked for delivery, inventory, discount, or final commitment.
- Customer may expect a fast delivery confirmation.
- Do not quote price without exact specifications.
- Do not promise delivery dates or inventory availability without human confirmation.

Suggested Human Action:
Call customer within 30 minutes to collect length x width x height, ply, BF/GSM or material strength, product weight.
```

## Flow 4: Phone Transcript

Transcript:

> Caller says they sell snack jars online. They need shipping boxes, around two thousand per month, product weighs 700 grams, some jars break in transit, wants logo printing, delivery to HSR Layout.

Summary:

> Customer sells snack jars online and needs e-commerce shipping boxes for fragile 700 g products, about 2000 per month, with logo printing and delivery to HSR Layout.

Extracted lead:

```json
{
  "source": "Phone Transcript",
  "product": "e-commerce shipping boxes",
  "product_type": "ecommerce_shipping",
  "quantity": 2000,
  "industry": "food e-commerce",
  "location": "HSR Layout, Bangalore",
  "product_weight": "700 g",
  "fragility": "glass jars can break in transit",
  "shipment_volume": "about 2000 per month",
  "branding_printing_need": "logo printing",
  "extraction_confidence": "medium"
}
```

Suggested human action:

> Call customer within 30 minutes to collect box dimensions.
