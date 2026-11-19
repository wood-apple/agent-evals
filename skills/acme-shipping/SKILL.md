---
name: acme-shipping
description: ACME Ground shipping rate card and pricing procedure (zones, dimensional weight, surcharges, rounding). Use to quote any ACME shipping price.
---
# ACME Ground rate card

1. **Zone** from the first digit of the destination ZIP code: 0–3 → A, 4–6 → B, 7–9 → C.
2. **Billable weight** = the larger of actual weight (kg) and dimensional weight, where dimensional weight = L × W × H (cm) / 5000.
3. **Units** = billable weight divided by 0.5 kg, rounded **up** to a whole number (every started half-kilo counts).
4. **Subtotal** = base + units × per-unit rate:

| zone | base (USD) | per 0.5 kg (USD) |
|------|-----------:|-----------------:|
| A | 4.10 | 1.20 |
| B | 5.25 | 1.45 |
| C | 6.80 | 1.90 |

5. **Fuel surcharge**: multiply the subtotal by 1.075.
6. Round to cents, **half up** (use decimal arithmetic, not binary floats).

Example: 1.1 kg, 10×10×10 cm, ZIP 20500 → zone A; dim weight 0.2 kg → billable 1.1 kg → 3 units; subtotal 4.10 + 3.60 = 7.70; ×1.075 = 8.2775 → **8.28**.
