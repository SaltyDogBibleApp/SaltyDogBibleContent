# Reserve Intel Monitor Report

Run time: **2026-10-19T22:18:54Z**

## Source check cadence

- Checked this run: 8
- Skipped until configured interval: 3

## New potentially relevant items

### Chief of Navy Reserve

- Source: **MyNavyHR Reserve Officer Boards**
- Type: `reserve_board`
- URL: https://www.navyreserve.navy.mil/
- Reserve signals: RESERVE OFFICER, TAR, PROMOTION
- Category hints: Admin, Policy, Training & Readiness

**Human review required. Detection does not mean this item should be published.**

### Navy Reserve Homeport

- Source: **MyNavyHR Reserve Officer Boards**
- Type: `reserve_board`
- URL: https://nrh.navyreserve.navy.mil/
- Reserve signals: RESERVE OFFICER, TAR, PROMOTION
- Category hints: Admin, Policy, Training & Readiness

**Human review required. Detection does not mean this item should be published.**

### Chief of Navy Reserve

- Source: **MyNavyHR Reserve Officer Continuation and Retention**
- Type: `reserve_board`
- URL: https://www.navyreserve.navy.mil/
- Reserve signals: CONTINUATION, RETENTION, TAR, RESERVE OFFICER
- Category hints: Policy, Admin, Retirement

**Human review required. Detection does not mean this item should be published.**

### Navy Reserve Homeport

- Source: **MyNavyHR Reserve Officer Continuation and Retention**
- Type: `reserve_board`
- URL: https://nrh.navyreserve.navy.mil/
- Reserve signals: CONTINUATION, RETENTION, TAR, RESERVE OFFICER
- Category hints: Policy, Admin, Retirement

**Human review required. Detection does not mean this item should be published.**

### DFAS Military Pay Tables — source content changed

- Source: **DFAS Military Pay Tables**
- Type: `pay_tables`
- URL: https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/
- Reserve signals: DRILL PAY, BASIC PAY, AVIATION INCENTIVE PAY, BAS, ALLOWANCE
- Category hints: Pay & Benefits
- Detection: `source_changed_in_place`
- Source fingerprint: `72782b2d67b717be715db75b3028c1daef772cf3b4759f91cead08ea51319867`
- Previous fingerprint: `fdd4970584dfe534ae0f73c55c945f74899850bf395443c32bd0c175d0ea94d9`

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

