# Ledgerly 4.2.0 — 2026-11-12

## Highlights
- Approve many expenses at once straight from the review queue. (ACME-790)
- The mobile app now has a dark mode. (ACME-799)

## Fixes
- Multi-currency invoices now round amounts the same way as the ledger. (ACME-755)
- CSV exports now include the last row even when the file has no trailing newline. (ACME-812)

## Breaking changes
- The /v1/reports endpoint now requires the `reports:read` scope; update your API clients to request it. (ACME-801)
