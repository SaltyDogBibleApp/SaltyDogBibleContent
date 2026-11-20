# Reserve Intel Monitor Report

Run time: **2026-11-20T20:07:28Z**

## Source check cadence

- Checked this run: 7
- Skipped until configured interval: 4

## New potentially relevant items

### COMNAVRESFOR NOTICE 1001

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFOR NOTICE 1001.pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `c1c4c22015da214e03bc0f04488f6964f2c4257175c7bc14778f547223323f96`

**Human review required. Detection does not mean this item should be published.**

### 5050 - FORCE MEDICAL SYMPOSIUM LOI

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/5050 - FORCE MEDICAL SYMPOSIUM LOI.pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `7554303b0d901bd72a1036300986109e9bd54789d07fa71bf720e973dd6281cc`

**Human review required. Detection does not mean this item should be published.**

## Source-check errors

- **Navy Reserve RESPERSMAN — RPM Acronyms** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERMAN Authorization Letter** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERSMAN Table of Contents** — HTTP Error 404: Not Found

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

