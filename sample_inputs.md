# Sample Inputs

Use these in `adk run packaging_lead_intake` or `adk web` after configuring
credentials.

## 1. Hot IndiaMART Printed Carton Lead

Customer:

> Source: IndiaMART. Need 5000 custom printed boxes for skincare brand in Bangalore. Delivery next week.

Expected behavior:

- Extract source, product type, quantity, industry, location, timeline, and confidence.
- Classify as Hot.
- Ask only the next best 3-4 printed carton questions.
- Generate a human handoff summary because the lead is hot and urgent.

## 2. Vague WhatsApp E-commerce Lead

Customer:

> Source: WhatsApp. Hi, do you make corrugated boxes for e-commerce shipping?

Expected behavior:

- Recognize `ecommerce_shipping`.
- Do not hand off yet.
- Ask for product weight, fragility, shipment volume, and branding/printing need.

## 3. Price + Urgent Request

Customer:

> Source: Justdial. What is the price for 1000 boxes? I need delivery tomorrow.

Expected behavior:

- Do not quote a price.
- Do not promise delivery.
- Trigger `price_request` handoff.
- Include missing corrugated box details in the handoff.

## 4. Food Packaging Inquiry

Customer:

> Source: Website. We need packaging for ready-to-eat snacks, 8000 pieces. Need oil barrier and food-grade material, delivery in Whitefield.

Expected behavior:

- Recognize `food_packaging`.
- Ask for dimensions, exact food-grade requirement, and any certification concern if mentioned.
- Treat as sales review if details are nearly quote-ready.

## 5. Industrial Packaging Inquiry

Customer:

> Source: Website. Need cartons for metal parts, 20 kg each, 1000 pieces, 18x12x10 inch, storage in warehouse, delivery Peenya.

Expected behavior:

- Recognize `industrial_packaging`.
- Mark as Hot if key details are present.
- Generate handoff summary for feasibility and pricing review.

## 6. Phone Transcript

Customer:

> Source: Phone Transcript. Caller says they sell snack jars online. They need shipping boxes, around two thousand per month, product weighs 700 grams, some jars break in transit, wants logo printing, delivery to HSR Layout.

Expected behavior:

- Summarize the transcript.
- Extract e-commerce shipping fields.
- Ask for box dimensions.
- Generate a handoff because the lead is bulk/hot.

## 7. Spam or Irrelevant

Customer:

> Source: Website. Congratulations, your crypto lottery prize is ready.

Expected behavior:

- Mark as Spam.
- Do not send to sales as Hot or Warm.
