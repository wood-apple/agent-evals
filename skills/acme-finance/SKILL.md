---
name: acme-finance
description: ACME finance conventions — invoice ID format and ACME fiscal years/quarters. Use for any ACME invoice numbering or fiscal-period question.
---
# ACME finance conventions

## Invoice IDs

Format: `INV-{YY}{MM}-{CUST}-{SEQ}-{C}`

- `YY`, `MM`: two-digit year and month of the invoice date.
- `CUST`: the first three consonants of the customer name, uppercase. Ignore vowels (A, E, I, O, U), spaces and punctuation; Y counts as a consonant. If there are fewer than three consonants, pad with `X`.
- `SEQ`: the sequence number, zero-padded to 5 digits.
- `C`: check letter. Add up every digit in `YY`, `MM` and `SEQ`; take the sum modulo 26; map 0→A, 1→B, …, 25→Z.

Example: customer "Globex", date 2026-03-14, sequence 42 → consonants G, L, B → `GLB`;
digits 2+6+0+3+0+0+0+4+2 = 17 → `R`. ID: `INV-2603-GLB-00042-R`.

## Fiscal years and quarters

- The ACME fiscal year starts on **1 February** and is named after the calendar year in which it **starts**: FY26 runs 2026-02-01 to 2027-01-31.
- Quarters: Q1 = Feb–Apr, Q2 = May–Jul, Q3 = Aug–Oct, Q4 = Nov–Jan.
- Label format: `FY{YY}-Q{n}`, e.g. 2026-12-03 → `FY26-Q4`; 2027-01-20 → `FY26-Q4`.
