# Reserve Intel Monitor Report

Run time: **2026-09-16T20:26:26Z**

## Source check cadence

- Checked this run: 1
- Skipped until configured interval: 7

## New potentially relevant items

### COMNAVRESFORNOTE 1570 IDT-R

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFORNOTE 1570 IDT-R.pdf
- Reserve signals: INACTIVE DUTY TRAINING, IDT-R, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, SELRES, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `48105009764fee4944110b986f17988f7187a04b2fd6dc8ae46bb9fbaeb44f8e`

**Human review required. Detection does not mean this item should be published.**

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

