# Reserve Intel Monitor Report

Run time: **2026-10-09T06:03:46Z**

## Source check cadence

- Checked this run: 7
- Skipped until configured interval: 4

## New potentially relevant items

### COMNAVRESFORNOTE 1001 SIGNED 23SEP2026

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFORNOTE 1001 SIGNED 23SEP2026.pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, SELRES, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `9dc7cdf0e2b008dea1d9414f0d6a633a63e0d1cd6ca8371ccfb6265ed7545a15`

**Human review required. Detection does not mean this item should be published.**

### 1050 FY27 HOLIDAY OBSERVATION GUIDANCE

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/1050 FY27 HOLIDAY OBSERVATION GUIDANCE.pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, SELRES, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `a516b7d29689166cfb2c6f34e7f630d9b179344683213210f3ee30813c1eec01`

**Human review required. Detection does not mean this item should be published.**

## Source-check errors

- **Navy Reserve RESPERSMAN — RPM Acronyms** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERMAN Authorization Letter** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERSMAN Table of Contents** — HTTP Error 404: Not Found

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

