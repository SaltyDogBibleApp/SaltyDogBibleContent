# Reserve Intel Monitor Report

Run time: **2026-10-23T17:02:51Z**

## Source check cadence

- Checked this run: 5
- Skipped until configured interval: 6

## New potentially relevant items

### DFAS Military Pay Tables — source content changed

- Source: **DFAS Military Pay Tables**
- Type: `pay_tables`
- URL: https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/
- Reserve signals: DRILL PAY, BASIC PAY, AVIATION INCENTIVE PAY, BAS, ALLOWANCE
- Category hints: Pay & Benefits
- Detection: `source_changed_in_place`
- Source fingerprint: `648891ad72a43fc6173e2b9ac6f82adb6b8f21415fe95b4bb9c394b72891c5a4`
- Previous fingerprint: `72782b2d67b717be715db75b3028c1daef772cf3b4759f91cead08ea51319867`

**Human review required. Detection does not mean this item should be published.**

## Official sources changed in place

- **DFAS Military Pay Tables** — https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/

These pages changed without exposing a clean new linked item. Review the official source before drafting Intel.

## Source-check errors

- **Navy Reserve RESPERSMAN — RPM Acronyms** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERMAN Authorization Letter** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERSMAN Table of Contents** — HTTP Error 404: Not Found

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

