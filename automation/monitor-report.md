# Reserve Intel Monitor Report

Run time: **2026-09-18T16:21:40Z**

## Source check cadence

- Checked this run: 2
- Skipped until configured interval: 9

## New potentially relevant items

### CNRFNOTE 1001 - FY27 FEG

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/CNRFNOTE 1001 - FY27 FEG.pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, SELRES, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `b28ad5af38f6e8ce66bdbd29a16969659ed9b135b585c40a6f435d7f57f539bc`

**Human review required. Detection does not mean this item should be published.**

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

